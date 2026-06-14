from django.db import models
from django.utils import timezone

ORG_FK = dict(
    to='organizations.Organization',
    on_delete=models.CASCADE,
    null=True,
    blank=True,
    related_name='+',
    db_index=True,
)


class ConversationFlow(models.Model):
    organization = models.ForeignKey(**ORG_FK)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=False)
    global_prompt = models.TextField(
        blank=True,
        help_text='Global instructions injected into every flow-guided AI response for this flow.',
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.is_active:
            ConversationFlow.objects.filter(organization=self.organization).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)


class FlowCard(models.Model):
    CARD_TYPE_ENTRY = 'entry'
    CARD_TYPE_NORMAL = 'normal'
    CARD_TYPE_ESCALATION = 'escalation'
    CARD_TYPE_CHOICES = [
        (CARD_TYPE_ENTRY, 'Entry'),
        (CARD_TYPE_NORMAL, 'Normal'),
        (CARD_TYPE_ESCALATION, 'Escalation'),
    ]

    flow = models.ForeignKey(ConversationFlow, related_name='cards', on_delete=models.CASCADE)
    card_type = models.CharField(max_length=20, choices=CARD_TYPE_CHOICES, default=CARD_TYPE_NORMAL)
    title = models.CharField(max_length=255)
    message_template = models.TextField(blank=True, default='', help_text='Message template with {placeholder} support')
    goal = models.TextField(
        blank=True,
        default='',
        help_text='Business goal for this stage, e.g. collect dates or qualify the lead.',
    )
    required_fields = models.JSONField(
        default=list,
        blank=True,
        help_text='Lead/custom field names that should be collected before leaving this stage.',
    )
    success_conditions = models.JSONField(
        default=dict,
        blank=True,
        help_text='Structured conditions that mark this stage as complete.',
    )
    allowed_tools = models.JSONField(
        default=list,
        blank=True,
        help_text='Optional list of AI tool names allowed while this card is active.',
    )
    response_policy = models.JSONField(
        default=dict,
        blank=True,
        help_text='Stage-specific response rules such as answer_then_return or max length.',
    )
    return_to_funnel_instruction = models.TextField(
        blank=True,
        default='',
        help_text='Instruction for returning to this stage after side questions.',
    )
    playbooks = models.ManyToManyField(
        'hotel_info.Playbook',
        blank=True,
        related_name='flow_card_set',
        help_text='Playbooks to inject into AI context when this card is active',
    )
    position_x = models.FloatField(default=0)
    position_y = models.FloatField(default=0)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.flow.name} / {self.title}'


class FlowConnection(models.Model):
    flow = models.ForeignKey(ConversationFlow, related_name='connections', on_delete=models.CASCADE)
    source_card = models.ForeignKey(FlowCard, related_name='outgoing_connections', on_delete=models.CASCADE)
    target_card = models.ForeignKey(FlowCard, related_name='incoming_connections', on_delete=models.CASCADE)
    condition_label = models.CharField(max_length=255, blank=True)
    condition_keywords = models.TextField(blank=True, help_text='Comma-separated keywords that trigger this path')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.source_card.title} → {self.target_card.title}'


class AIFlowMode(models.Model):
    """Singleton: global AI mode (freeform vs flow_guided)."""
    MODE_FREEFORM = 'freeform'
    MODE_FLOW_GUIDED = 'flow_guided'
    MODE_CHOICES = [
        (MODE_FREEFORM, 'Freeform'),
        (MODE_FLOW_GUIDED, 'Flow-guided'),
    ]

    organization = models.ForeignKey(**ORG_FK)
    mode = models.CharField(max_length=20, choices=MODE_CHOICES, default=MODE_FREEFORM)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'AI Flow Mode'
        verbose_name_plural = 'AI Flow Mode'

    @classmethod
    def get_mode(cls, org=None):
        if org is not None:
            if not hasattr(org, "pk"):
                return None  # sentinel: user has no org set
            obj, _ = cls.objects.get_or_create(organization=org)
            return obj
        return cls.objects.first()

    def __str__(self):
        return f'Mode: {self.mode}'


class AITool(models.Model):
    """
    Configurable AI tool definition. The description field is what OpenAI reads
    to decide when to call the tool. The name must match the Python handler in
    _execute_pricing_tool(). Parameters schema stays hardcoded.
    """
    organization = models.ForeignKey(**ORG_FK)
    name = models.CharField(max_length=100)
    display_name = models.CharField(max_length=255)
    description = models.TextField()
    parameters_schema = models.JSONField(blank=True, null=True, help_text="JSON schema for tool parameters")
    runtime_config = models.JSONField(blank=True, null=True, help_text="Runtime config settings")
    is_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['organization', 'name'],
                name='flows_aitool_unique_org_name',
            ),
        ]

    def __str__(self):
        return self.display_name


class AIModelConfig(models.Model):
    """Singleton: AI model parameters for guest-facing conversation."""
    organization = models.ForeignKey(**ORG_FK)
    temperature = models.FloatField(default=0.7)
    max_tokens = models.IntegerField(default=500)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'AI Model Config'
        verbose_name_plural = 'AI Model Config'

    @classmethod
    def get_config(cls, org=None):
        if org is not None:
            if not hasattr(org, "pk"):
                return None  # sentinel: user has no org set
            obj, _ = cls.objects.get_or_create(organization=org, defaults={'temperature': 0.7, 'max_tokens': 500})
            return obj
        return cls.objects.first()

    def __str__(self):
        return f'temperature={self.temperature}, max_tokens={self.max_tokens}'


class ManagerTransferConfig(models.Model):
    """Singleton: where to send manager notifications when the AI escalates."""
    CHANNEL_TELEGRAM = 'telegram'
    CHANNEL_WHATSAPP = 'whatsapp'
    CHANNEL_CHOICES = [
        (CHANNEL_TELEGRAM, 'Telegram'),
        (CHANNEL_WHATSAPP, 'WhatsApp'),
    ]

    organization = models.ForeignKey(**ORG_FK)
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default=CHANNEL_TELEGRAM)
    recipient_id = models.CharField(max_length=255, blank=True)
    manager_name = models.CharField(max_length=255, blank=True)
    notification_template = models.TextField(
        blank=True,
        help_text=(
            'Custom notification message template. Leave blank to use the default. '
            'Available variables: {reason}, {guest_name}, {guest_phone}, {guest_email}, '
            '{platform}, {checkin_date}, {checkout_date}, {nights}, {guest_count}, '
            '{room_description}, {meal_plan}, {price_per_night}, {total_price}, {notes}, {contact_id}'
        ),
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Manager Transfer Config'
        verbose_name_plural = 'Manager Transfer Config'

    @classmethod
    def get_config(cls, org=None):
        if org is not None:
            if not hasattr(org, "pk"):
                return None  # sentinel: user has no org set
            obj, _ = cls.objects.get_or_create(organization=org, defaults={'channel': cls.CHANNEL_TELEGRAM})
            return obj
        return cls.objects.first()

    def __str__(self):
        return f'{self.channel}: {self.recipient_id}'


class LeadFlowState(models.Model):
    """Tracks which card a lead is currently at in a flow."""
    lead = models.OneToOneField('leads.Lead', related_name='flow_state', on_delete=models.CASCADE)
    flow = models.ForeignKey(ConversationFlow, on_delete=models.SET_NULL, null=True, blank=True)
    current_card = models.ForeignKey(FlowCard, on_delete=models.SET_NULL, null=True, blank=True)
    is_complete = models.BooleanField(default=False)
    is_escalated = models.BooleanField(default=False)
    collected_data = models.JSONField(default=dict, blank=True)
    started_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Lead {self.lead_id} @ {self.current_card}'


class AgentConfig(models.Model):
    """Configuration for each AI agent (booking, cs, consultant, router)."""

    AGENT_BOOKING = 'booking'
    AGENT_CS = 'cs'
    AGENT_CONSULTANT = 'consultant'
    AGENT_ROUTER = 'router'
    AGENT_CHOICES = [
        (AGENT_BOOKING, 'Booking Agent'),
        (AGENT_CS, 'Customer Service Agent'),
        (AGENT_CONSULTANT, 'Consultant Agent'),
        (AGENT_ROUTER, 'Intent Router'),
    ]

    organization = models.ForeignKey(**ORG_FK)
    name = models.CharField(max_length=50, unique=True, choices=AGENT_CHOICES)
    display_name = models.CharField(max_length=255)
    system_prompt = models.TextField(blank=True)
    playbooks = models.ManyToManyField(
        'hotel_info.Playbook',
        blank=True,
        related_name='agent_configs',
    )
    tools = models.JSONField(
        default=list,
        blank=True,
        help_text='List of tool names available to this agent',
    )
    is_editable = models.BooleanField(
        default=True,
        help_text='Intent Router is not editable',
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = 'Agent Config'
        verbose_name_plural = 'Agent Configs'

    def __str__(self):
        return self.display_name
