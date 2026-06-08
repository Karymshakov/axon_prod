from auditlog.registry import auditlog
from django.conf import settings
from django.db import models

ORG_FK = dict(
    to='organizations.Organization',
    on_delete=models.CASCADE,
    null=True,
    blank=True,
    related_name='+',
    db_index=True,
)


class Segment(models.Model):
    """Configurable lead segments (e.g., Individual, Business)."""

    organization = models.ForeignKey(**ORG_FK)
    name = models.CharField(max_length=100)
    key = models.CharField(max_length=50)
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'id']
        unique_together = [('organization', 'key')]
        verbose_name = 'Segment'
        verbose_name_plural = 'Segments'

    def __str__(self):
        return self.name


class PipelineStage(models.Model):
    """Pipeline stage for lead status tracking."""

    organization = models.ForeignKey(**ORG_FK)
    name = models.CharField(max_length=100)
    key = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    order = models.IntegerField(default=0)
    is_final = models.BooleanField(
        default=False,
        help_text='Final stage - AI agent will not follow up on leads in this stage'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'id']
        unique_together = [('organization', 'key')]
        verbose_name = 'Pipeline Stage'
        verbose_name_plural = 'Pipeline Stages'

    def __str__(self):
        return self.name


class Lead(models.Model):
    STATUS_NEW = 'new'
    STATUS_ATTEMPTED = 'attempted'
    STATUS_CONTACTED = 'contacted'
    STATUS_UNQUALIFIED = 'unqualified'
    STATUS_NURTURING = 'nurturing'
    STATUS_CONVERTED = 'converted'

    STATUS_CHOICES = [
        (STATUS_NEW, 'New'),
        (STATUS_ATTEMPTED, 'Attempted to Contact / Working'),
        (STATUS_CONTACTED, 'Contacted / Connected'),
        (STATUS_UNQUALIFIED, 'Unqualified / Disqualified'),
        (STATUS_NURTURING, 'Nurturing / Pending'),
        (STATUS_CONVERTED, 'Converted'),
    ]

    # Contact Details
    contact_person = models.CharField(max_length=255, blank=True)
    job_title = models.CharField(max_length=200, blank=True, help_text="Contact's job title/position")
    email = models.EmailField(blank=True)
    secondary_email = models.EmailField(blank=True, help_text='Alternative email address')
    phone = models.CharField(max_length=50, blank=True)
    mobile_phone = models.CharField(max_length=50, blank=True, help_text='Mobile phone number')
    office_phone = models.CharField(max_length=50, blank=True, help_text='Office/direct line')
    website = models.URLField(blank=True, help_text='Company website')
    linkedin_url = models.URLField(blank=True, help_text='LinkedIn profile URL')

    # Location/Geography
    address = models.CharField(max_length=500, blank=True, help_text='Street address')
    city = models.CharField(max_length=100, blank=True)
    state_province = models.CharField(max_length=100, blank=True, help_text='State or Province')
    postal_code = models.CharField(max_length=20, blank=True, help_text='ZIP or Postal code')
    country = models.CharField(max_length=100, blank=True, help_text='Country')
    timezone = models.CharField(max_length=50, blank=True, help_text='Timezone for scheduling')

    # Lead Management
    segment = models.CharField(max_length=50, default='individual', help_text='Lead segment (from Segment model)')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_NEW)
    source = models.CharField(max_length=100, blank=True, help_text='Where the lead came from')
    estimated_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)
    last_contacted = models.DateField(null=True, blank=True)

    # Communication Tracking
    preferred_contact_method = models.CharField(max_length=50, blank=True, help_text='Email, Phone, Telegram, etc.')
    preferred_contact_time = models.CharField(max_length=100, blank=True, help_text='Best time to reach them')
    language = models.CharField(max_length=50, blank=True, help_text='Preferred language')
    do_not_contact = models.BooleanField(default=False, help_text='Opted out of communication')
    email_bounced = models.BooleanField(default=False, help_text='Email is invalid/bounced')
    unsubscribed_at = models.DateTimeField(null=True, blank=True, help_text='When they opted out')

    # Hotel Booking Details
    check_in_date = models.DateField(null=True, blank=True, help_text='Guest check-in date')
    check_out_date = models.DateField(null=True, blank=True, help_text='Guest check-out date')
    guest_count = models.PositiveSmallIntegerField(null=True, blank=True, help_text='Number of guests')
    room_type_preference = models.CharField(max_length=200, blank=True, help_text='Preferred room type, e.g. Deluxe Balcony')
    MEAL_PLAN_CHOICES = [
        ('none', 'No meal plan'),
        ('breakfast', 'Breakfast only'),
        ('lunch', 'Lunch only'),
        ('dinner', 'Dinner only'),
        ('half_board_bl', 'Half-board: Breakfast + Lunch'),
        ('half_board_bd', 'Half-board: Breakfast + Dinner'),
        ('full_board', 'Full board'),
    ]
    meal_plan = models.CharField(max_length=20, blank=True, choices=MEAL_PLAN_CHOICES, help_text='Meal plan preference')

    # Summary & Next Steps
    problem_description = models.TextField(blank=True, help_text='Summary of the lead / what they are looking for')
    next_steps = models.TextField(blank=True, help_text='Planned next actions for this lead')
    # Tax / Case Details (legacy - kept for data integrity)
    tax_years = models.CharField(max_length=100, blank=True, help_text='Tax years involved, e.g. 2021-2023')
    COMPLEXITY_CHOICES = [
        (1, '1 – Simple'),
        (2, '2 – Moderate'),
        (3, '3 – Complex'),
        (4, '4 – Very Complex'),
        (5, '5 – Highly Complex'),
    ]
    complexity_score = models.IntegerField(null=True, blank=True, choices=COMPLEXITY_CHOICES, help_text='Case complexity score 1-5')

    # Sales Process
    next_follow_up_date = models.DateField(null=True, blank=True, help_text='Scheduled next action')
    expected_close_date = models.DateField(null=True, blank=True, help_text='Projected conversion date')
    lost_reason = models.CharField(max_length=200, blank=True, help_text='Why they didn\'t convert')
    competitor = models.CharField(max_length=200, blank=True, help_text='Which competitor they chose')
    referral_source = models.CharField(max_length=200, blank=True, help_text='Who referred them')
    campaign_source = models.CharField(max_length=200, blank=True, help_text='Marketing campaign')

    # Source-specific identifiers
    telegram_user_id = models.CharField(max_length=100, blank=True, help_text='Telegram user ID (unique identifier)')
    telegram_username = models.CharField(max_length=100, blank=True, help_text='Telegram username (without @)')
    telegram_chat_id = models.CharField(max_length=100, blank=True, db_index=True, help_text='Telegram chat ID for direct messaging')
    instagram_user_id = models.CharField(max_length=100, blank=True, db_index=True, help_text='Instagram user ID')
    instagram_username = models.CharField(max_length=100, blank=True, help_text='Instagram username (without @)')
    whatsapp_phone = models.CharField(max_length=50, blank=True, db_index=True, help_text='WhatsApp phone number')

    # Organization
    organization = models.ForeignKey(**ORG_FK)

    # Assignment
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_leads',
        help_text='User this lead is assigned to',
    )

    # Instagram intent classification
    INTENT_TIER_BOOKING = 'booking_intent'
    INTENT_TIER_SOFT = 'soft_interest'
    INTENT_TIER_NOT_RELEVANT = 'not_relevant'
    INTENT_TIER_CHOICES = [
        (INTENT_TIER_BOOKING, 'Booking Intent'),
        (INTENT_TIER_SOFT, 'Soft Interest'),
        (INTENT_TIER_NOT_RELEVANT, 'Not Relevant'),
    ]
    instagram_intent_tier = models.CharField(
        max_length=20,
        choices=INTENT_TIER_CHOICES,
        blank=True,
        null=True,
        help_text='Instagram DM intent classification (booking_intent / soft_interest / not_relevant)',
    )

    # AI Agent tracking
    ai_followup_count = models.IntegerField(default=0, help_text='Number of AI-initiated follow-ups sent')
    last_ai_followup_at = models.DateTimeField(null=True, blank=True, help_text='Last AI follow-up timestamp')
    ai_paused = models.BooleanField(default=False, help_text='AI responses paused — manager has taken over the conversation')
    ai_paused_at = models.DateTimeField(null=True, blank=True, help_text='When AI was paused')
    ai_paused_by = models.CharField(max_length=255, blank=True, help_text='Name of user who paused AI')
    agent_context = models.JSONField(
        default=dict,
        blank=True,
        help_text='Shared context store for multi-agent routing (current_agent, booking_step, collected, etc.)',
    )

    # AI-driven proactive scheduling
    next_follow_up_at = models.DateTimeField(
        null=True, blank=True,
        help_text='AI-scheduled datetime for the next proactive outreach',
    )
    next_follow_up_hint = models.TextField(
        blank=True,
        help_text="AI's reasoning for the scheduled follow-up",
    )

    # Objection tracking
    OBJECTION_TYPES = [
        ('price', 'Price/Budget'),
        ('timing', 'Timing/Not Ready'),
        ('competitor', 'Using Competitor'),
        ('authority', 'Not Decision Maker'),
        ('need', 'No Need'),
        ('other', 'Other'),
    ]
    current_objection = models.CharField(max_length=50, blank=True, choices=OBJECTION_TYPES, help_text='Current objection type')
    last_objection_at = models.DateTimeField(null=True, blank=True, help_text='When last objection was detected')
    objection_count = models.IntegerField(default=0, help_text='Total objections detected')

    custom_fields = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.contact_person or f"Lead #{self.pk}"


class LeadNote(models.Model):
    """Notes/comments on a lead."""

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='lead_notes')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Lead Note'
        verbose_name_plural = 'Lead Notes'

    def __str__(self):
        return f"Note on {self.lead.contact_person or str(self.lead.pk)} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"


class LeadActivity(models.Model):
    """Activity timeline for automatic tracking of lead changes."""

    TYPE_STATUS_CHANGE = 'status_change'
    TYPE_NOTE_ADDED = 'note_added'
    TYPE_LEAD_CREATED = 'lead_created'
    TYPE_LEAD_UPDATED = 'lead_updated'
    TYPE_TASK_CREATED = 'task_created'
    TYPE_TASK_COMPLETED = 'task_completed'
    TYPE_TELEGRAM_SENT = 'telegram_sent'
    TYPE_TELEGRAM_RECEIVED = 'telegram_received'
    TYPE_INSTAGRAM_SENT = 'instagram_sent'
    TYPE_INSTAGRAM_RECEIVED = 'instagram_received'
    TYPE_WHATSAPP_SENT = 'whatsapp_sent'
    TYPE_WHATSAPP_RECEIVED = 'whatsapp_received'
    # RingCentral activity types
    TYPE_RINGCENTRAL_SMS_SENT = 'ringcentral_sms_sent'
    TYPE_RINGCENTRAL_SMS_RECEIVED = 'ringcentral_sms_received'
    TYPE_RINGCENTRAL_CALL_STARTED = 'ringcentral_call_started'
    TYPE_RINGCENTRAL_CALL_ENDED = 'ringcentral_call_ended'
    TYPE_RINGCENTRAL_CALL_ANALYZED = 'ringcentral_call_analyzed'
    # New AI autonomy activity types
    TYPE_AI_STATUS_CHANGE = 'ai_status_change'
    TYPE_OBJECTION_DETECTED = 'objection_detected'
    TYPE_TASK_AUTO_COMPLETED = 'task_auto_completed'
    TYPE_GOAL_COMPLETED = 'goal_completed'
    TYPE_GOAL_CREATED = 'goal_created'

    ACTIVITY_TYPES = [
        (TYPE_STATUS_CHANGE, 'Status Changed'),
        (TYPE_NOTE_ADDED, 'Note Added'),
        (TYPE_LEAD_CREATED, 'Lead Created'),
        (TYPE_LEAD_UPDATED, 'Lead Updated'),
        (TYPE_TASK_CREATED, 'Task Created'),
        (TYPE_TASK_COMPLETED, 'Task Completed'),
        (TYPE_TELEGRAM_SENT, 'Telegram Message Sent'),
        (TYPE_TELEGRAM_RECEIVED, 'Telegram Message Received'),
        (TYPE_INSTAGRAM_SENT, 'Instagram Message Sent'),
        (TYPE_INSTAGRAM_RECEIVED, 'Instagram Message Received'),
        (TYPE_WHATSAPP_SENT, 'WhatsApp Message Sent'),
        (TYPE_WHATSAPP_RECEIVED, 'WhatsApp Message Received'),
        # RingCentral activities
        (TYPE_RINGCENTRAL_SMS_SENT, 'RingCentral SMS Sent'),
        (TYPE_RINGCENTRAL_SMS_RECEIVED, 'RingCentral SMS Received'),
        (TYPE_RINGCENTRAL_CALL_STARTED, 'Phone Call Started'),
        (TYPE_RINGCENTRAL_CALL_ENDED, 'Phone Call Ended'),
        (TYPE_RINGCENTRAL_CALL_ANALYZED, 'Phone Call Analysis'),
        # AI autonomy activities
        (TYPE_AI_STATUS_CHANGE, 'AI Changed Status'),
        (TYPE_OBJECTION_DETECTED, 'Objection Detected'),
        (TYPE_TASK_AUTO_COMPLETED, 'AI Completed Task'),
        (TYPE_GOAL_COMPLETED, 'Goal Achieved'),
        (TYPE_GOAL_CREATED, 'Goal Created'),
    ]

    ECHO_ORIGIN_CRM = 'crm'
    ECHO_ORIGIN_INSTAGRAM_APP = 'instagram_app'
    ECHO_ORIGIN_CHOICES = [
        (ECHO_ORIGIN_CRM, 'CRM (sent via dashboard)'),
        (ECHO_ORIGIN_INSTAGRAM_APP, 'Native Instagram app'),
    ]

    organization = models.ForeignKey(**ORG_FK)
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='activities')
    activity_type = models.CharField(max_length=50, choices=ACTIVITY_TYPES)
    description = models.TextField()
    metadata = models.JSONField(null=True, blank=True, help_text='Additional data about the activity')
    is_read = models.BooleanField(default=False, help_text='Whether this inbound message has been read by staff')
    echo_origin = models.CharField(
        max_length=20,
        choices=ECHO_ORIGIN_CHOICES,
        blank=True,
        null=True,
        help_text='For Instagram sent activities: crm = sent from dashboard, instagram_app = sent via native app',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Lead Activity'
        verbose_name_plural = 'Lead Activities'

    def __str__(self):
        return f"{self.lead.contact_person or str(self.lead.pk)} - {self.get_activity_type_display()}"


class Task(models.Model):
    """Tasks and reminders for lead follow-ups."""

    organization = models.ForeignKey(**ORG_FK)

    TASK_TYPES = [
        ('call', 'Call'),
        ('email', 'Email'),
        ('meeting', 'Meeting'),
        ('follow_up', 'Follow Up'),
        ('send_info', 'Send Information'),
        ('send_case_study', 'Send Case Study'),
        ('request_meeting', 'Request Meeting'),
        ('send_proposal', 'Send Proposal'),
        ('other', 'Other'),
    ]

    # Execution types for auto-executable tasks
    EXECUTION_TYPES = [
        ('send_message', 'Send Message'),
        ('send_document', 'Send Document'),
        ('update_status', 'Update Status'),
        ('schedule_followup', 'Schedule Follow-up'),
        ('none', 'Manual Task'),
    ]

    STATUS_PENDING = 'pending'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_IN_PROGRESS = 'in_progress'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='tasks')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    task_type = models.CharField(max_length=20, choices=TASK_TYPES, default='follow_up')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    due_date = models.DateField()
    completed_at = models.DateTimeField(null=True, blank=True)

    # Auto-execution fields
    is_auto_executable = models.BooleanField(default=False, help_text='Can AI execute this task automatically')
    execution_type = models.CharField(max_length=30, choices=EXECUTION_TYPES, default='none', help_text='How to execute this task')
    execution_content = models.TextField(blank=True, help_text='Content to send/action to take')
    executed_at = models.DateTimeField(null=True, blank=True, help_text='When AI executed this task')
    execution_result = models.TextField(blank=True, help_text='Result of auto-execution')
    is_ai_generated = models.BooleanField(default=False, help_text='Was this task created by AI')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['due_date', '-created_at']
        verbose_name = 'Task'
        verbose_name_plural = 'Tasks'

    def __str__(self):
        return f"{self.title} - {self.lead.contact_person or str(self.lead.pk)}"


class Customer(models.Model):
    """Customer converted from a lead."""

    organization = models.ForeignKey(**ORG_FK)

    STATUS_ACTIVE = 'active'
    STATUS_INACTIVE = 'inactive'

    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_INACTIVE, 'Inactive'),
    ]

    # Link to original lead (preserved, not deleted)
    lead = models.OneToOneField(Lead, on_delete=models.SET_NULL, null=True, blank=True, related_name='customer')

    # Basic contact info
    contact_person = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=50, blank=True)

    # Business info
    segment = models.CharField(max_length=50, default='individual', help_text='Customer segment (from Segment model)')
    source = models.CharField(max_length=100, blank=True, help_text='Where the customer came from')
    customer_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    notes = models.TextField(blank=True)

    # Communication channels (copied from lead for quick access)
    telegram_chat_id = models.CharField(max_length=100, blank=True, help_text='Telegram chat ID for direct messaging')
    telegram_username = models.CharField(max_length=100, blank=True, help_text='Telegram username (without @)')
    instagram_user_id = models.CharField(max_length=100, blank=True, help_text='Instagram user ID')
    instagram_username = models.CharField(max_length=100, blank=True, help_text='Instagram username (without @)')
    whatsapp_phone = models.CharField(max_length=50, blank=True, help_text='WhatsApp phone number')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Customer'
        verbose_name_plural = 'Customers'

    def __str__(self):
        return self.contact_person or f"Customer #{self.pk}"


class TelegramConfig(models.Model):
    """Telegram bot configuration (singleton model)."""

    organization = models.ForeignKey(**ORG_FK)
    bot_token = models.CharField(max_length=255)
    bot_username = models.CharField(max_length=255)
    bot_first_name = models.CharField(max_length=255, blank=True)
    connected_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Telegram Configuration'
        verbose_name_plural = 'Telegram Configuration'

    def __str__(self):
        return f"@{self.bot_username}"

    def save(self, *args, **kwargs):
        if not self.pk and TelegramConfig.objects.filter(organization=self.organization).exists():
            raise ValueError('Only one Telegram configuration can exist per organization')
        return super().save(*args, **kwargs)

    @classmethod
    def get_config(cls, org=None):
        """Get the org-scoped singleton config instance."""
        if org is not None:
            if not hasattr(org, "pk"):
                return None  # sentinel: user has no org set
            return cls.objects.filter(organization=org).first()
        return cls.objects.first()


class InstagramConnection(models.Model):
    """Instagram Business Account connection via Meta OAuth (Instagram Login API).

    Singleton model. App ID and Secret come from environment variables
    INSTAGRAM_APP_ID and INSTAGRAM_APP_SECRET.
    """

    organization = models.ForeignKey(**ORG_FK)
    access_token = models.TextField(help_text='Long-lived User Access Token (60 days)')
    token_expiry = models.DateTimeField(null=True, blank=True, help_text='Expiry datetime of the long-lived token')
    instagram_user_id = models.CharField(max_length=100, help_text='Instagram user ID returned by /me (app-scoped)')
    instagram_business_account_id = models.CharField(
        max_length=100, blank=True,
        help_text='Instagram Business Account ID as it appears in webhook entry.id (set on first webhook receipt)',
    )
    instagram_username = models.CharField(max_length=255, blank=True, help_text='Instagram username')
    profile_picture_url = models.TextField(blank=True)
    connected_at = models.DateTimeField(null=True, blank=True)
    webhook_subscribed = models.BooleanField(default=False, help_text='Whether POST /me/subscribed_apps has been called to activate DM delivery')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Instagram Connection'
        verbose_name_plural = 'Instagram Connection'

    def __str__(self):
        return f"@{self.instagram_username}" if self.instagram_username else f'Instagram ({self.instagram_user_id})'

    def save(self, *args, **kwargs):
        if not self.pk and InstagramConnection.objects.filter(organization=self.organization).exists():
            raise ValueError('Only one Instagram connection can exist per organization')
        return super().save(*args, **kwargs)

    @classmethod
    def get_config(cls, org=None):
        if org is not None:
            if not hasattr(org, "pk"):
                return None  # sentinel: user has no org set
            return cls.objects.filter(organization=org).first()
        return cls.objects.first()

    @property
    def is_token_expired(self) -> bool:
        from django.utils import timezone
        if not self.token_expiry:
            return False
        return timezone.now() >= self.token_expiry

    @property
    def is_expiring_soon(self) -> bool:
        """Returns True if token expires within 7 days."""
        from datetime import timedelta
        from django.utils import timezone
        if not self.token_expiry:
            return False
        return timezone.now() >= (self.token_expiry - timedelta(days=7))


class InstagramAppConfig(models.Model):
    """Meta App credentials for Instagram OAuth (singleton model).

    Stores App ID, App Secret, and Webhook Verify Token.
    Views fall back to environment variables if DB values are empty.
    """

    organization = models.ForeignKey(**ORG_FK)
    app_id = models.CharField(max_length=100, blank=True, default='',
                              help_text='Meta App ID (defaults to built-in app)')
    app_secret = models.CharField(max_length=255, blank=True,
                                  help_text='Meta App Secret — required for OAuth')
    webhook_verify_token = models.CharField(max_length=255, blank=True,
                                            default='cayu_instagram_webhook_2024',
                                            help_text='Token used to verify Meta webhook subscription')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Instagram App Config'
        verbose_name_plural = 'Instagram App Config'

    def save(self, *args, **kwargs):
        if not self.pk and InstagramAppConfig.objects.filter(organization=self.organization).exists():
            raise ValueError('Only one Instagram app config can exist per organization')
        return super().save(*args, **kwargs)

    @classmethod
    def get_config(cls, org=None):
        if org is not None:
            if not hasattr(org, "pk"):
                return None  # sentinel: user has no org set
            return cls.objects.filter(organization=org).first()
        return cls.objects.first()


class WhatsAppAppConfig(models.Model):
    """Meta App credentials for WhatsApp OAuth (singleton model).

    Stores App ID and App Secret used for the Embedded Signup OAuth flow.
    Views fall back to environment variables if DB values are empty.
    """

    organization = models.ForeignKey(**ORG_FK)
    app_id = models.CharField(max_length=100, blank=True, default='',
                              help_text='Meta App ID (defaults to built-in app)')
    app_secret = models.CharField(max_length=255, blank=True,
                                  help_text='Meta App Secret — required for OAuth')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'WhatsApp App Config'
        verbose_name_plural = 'WhatsApp App Config'

    def save(self, *args, **kwargs):
        if not self.pk and WhatsAppAppConfig.objects.filter(organization=self.organization).exists():
            raise ValueError('Only one WhatsApp app config can exist per organization')
        return super().save(*args, **kwargs)

    @classmethod
    def get_config(cls, org=None):
        if org is not None:
            if not hasattr(org, "pk"):
                return None  # sentinel: user has no org set
            return cls.objects.filter(organization=org).first()
        return cls.objects.first()


class WhatsAppConfig(models.Model):
    """WhatsApp Business Cloud API configuration (singleton model)."""

    organization = models.ForeignKey(**ORG_FK)
    access_token = models.TextField(help_text='WhatsApp Cloud API Access Token')
    phone_number_id = models.CharField(max_length=100, help_text='WhatsApp Business Phone Number ID')
    waba_id = models.CharField(max_length=100, blank=True, help_text='WhatsApp Business Account ID')
    display_phone_number = models.CharField(max_length=50, blank=True, help_text='Display phone number')
    verified_name = models.CharField(max_length=255, blank=True, help_text='Verified business name')
    token_expires_at = models.DateTimeField(null=True, blank=True, help_text='Token expiry (null = non-expiring)')
    webhook_subscribed = models.BooleanField(default=False, help_text='Whether WABA is subscribed to webhook events')
    verify_token = models.CharField(max_length=100, blank=True, help_text='Webhook verify token — paste into Meta App Dashboard')
    connected_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'WhatsApp Configuration'
        verbose_name_plural = 'WhatsApp Configuration'

    def __str__(self):
        return f"{self.verified_name} ({self.display_phone_number})"

    @property
    def is_token_expired(self) -> bool:
        if not self.token_expires_at:
            return False
        from django.utils import timezone
        return timezone.now() >= self.token_expires_at

    @property
    def is_expiring_soon(self) -> bool:
        """True when the token expires within 14 days."""
        if not self.token_expires_at:
            return False
        from django.utils import timezone
        from datetime import timedelta
        return timezone.now() >= (self.token_expires_at - timedelta(days=14))

    def save(self, *args, **kwargs):
        if not self.pk and WhatsAppConfig.objects.filter(organization=self.organization).exists():
            raise ValueError('Only one WhatsApp configuration can exist per organization')
        return super().save(*args, **kwargs)

    @classmethod
    def get_config(cls, org=None):
        """Get the org-scoped singleton config instance."""
        if org is not None:
            if not hasattr(org, "pk"):
                return None  # sentinel: user has no org set
            return cls.objects.filter(organization=org).first()
        return cls.objects.first()


class RingCentralConfig(models.Model):
    """RingCentral integration configuration (singleton model)."""

    organization = models.ForeignKey(**ORG_FK)
    client_id = models.CharField(max_length=255, help_text='RingCentral App Client ID')
    client_secret = models.CharField(max_length=255, help_text='RingCentral App Client Secret')
    jwt_token = models.TextField(help_text='RingCentral JWT credential (long-lived)')
    account_phone = models.CharField(max_length=50, help_text='RingCentral phone number to send from (e.g. +16465122142)')
    extension_id = models.CharField(max_length=50, blank=True, default='~', help_text='Extension ID (default: ~ for primary)')
    webhook_subscription_id = models.CharField(max_length=255, blank=True, help_text='Active webhook subscription ID')
    connected_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'RingCentral Configuration'
        verbose_name_plural = 'RingCentral Configuration'

    def __str__(self):
        return f"RingCentral ({self.account_phone})"

    def save(self, *args, **kwargs):
        if not self.pk and RingCentralConfig.objects.filter(organization=self.organization).exists():
            raise ValueError('Only one RingCentral configuration can exist per organization')
        return super().save(*args, **kwargs)

    @classmethod
    def get_config(cls, org=None):
        if org is not None:
            if not hasattr(org, "pk"):
                return None  # sentinel: user has no org set
            return cls.objects.filter(organization=org).first()
        return cls.objects.first()


class AIConfig(models.Model):
    """AI configuration for automatic Telegram responses (singleton model)."""

    organization = models.ForeignKey(**ORG_FK)
    # AI Configuration
    ai_auto_response = models.BooleanField(default=False, help_text='Enable AI auto-response for Telegram messages')
    auto_extract_data = models.BooleanField(default=False, help_text='Automatically extract lead data from conversations')
    response_delay = models.IntegerField(default=5, help_text='Delay before sending response (seconds)')
    telegram_ai_paused = models.BooleanField(default=False, help_text='Pause AI replies and AI automation for Telegram across all leads')
    instagram_ai_paused = models.BooleanField(default=False, help_text='Pause AI replies and AI automation for Instagram across all leads')
    whatsapp_ai_paused = models.BooleanField(default=False, help_text='Pause AI replies and AI automation for WhatsApp across all leads')

    # System Prompt
    system_prompt = models.TextField(
        blank=True,
        help_text='Define AI personality and behavior',
        default='''You are Aida, a warm and professional guest relations assistant for Nomad Camp — a boutique hotel on the scenic south shore of Lake Issyk-Kul, Kyrgyzstan.

Your primary goals:
1. **Convert inquiries into bookings** — Guide every conversation toward a confirmed reservation.
2. **Be warm and hospitable** — Reflect the spirit of Kyrgyz hospitality. Be friendly, personal, and attentive.
3. **Respond in the guest\'s language** — Detect the language the guest is writing in and reply in the SAME language. Supported languages: Russian (primary), Kyrgyz, and English. If the message mixes languages, follow the dominant language. Default to Russian if unclear.
4. **Review conversation history** — ALWAYS check what has already been discussed. Never ask for information the guest already provided. Build on previous responses.
5. **Answer questions confidently** — Use the knowledge base and company profile to answer questions about pricing, availability, services, policies, and the property. If you don\'t know a specific detail, offer to connect them with staff.
6. **Handle objections gracefully** — Address concerns about price, timing, or availability with genuine solutions and helpful alternatives.
7. **Create natural urgency** — Mention seasonal demand, peak periods (summer at Issyk-Kul), or limited availability when appropriate — but never in a pushy way.
8. **Collect key booking information** — Work toward gathering: number of guests, check-in/check-out dates, meal plan preference, and contact details.
9. **Always end with a next step** — Every message should include a soft call-to-action: confirming a booking, sharing dates, or asking a clarifying question.

Tone: Warm, welcoming, knowledgeable. Like a trusted local friend who knows the property well.
Keep messages concise — guests on WhatsApp/Telegram don\'t want walls of text. Use short paragraphs and occasional bullet points for clarity.

CRITICAL: Pay attention to what the guest has already told you. Acknowledge their previous messages and move the conversation forward — don\'t repeat questions.'''
    )

    # Company Profile
    company_profile = models.TextField(
        blank=True,
        help_text='Company information and context for AI responses',
        default='''**Nomad Camp** — A Boutique Hotel on Lake Issyk-Kul

Nomad Camp is a picturesque retreat nestled on the south shore of Lake Issyk-Kul in the Issyk-Kul region of the Kyrgyz Republic. Our hotel offers cozy rooms with private balconies overlooking the azure waters of the lake and the majestic surrounding mountains — a perfect escape from city life.

**Contact & Location**
- Address: Kerimkul Ata Street, 347, Issyk-Kul region, Kyrgyz Republic
- Email: info@nomadcamp.kg
- Legal entity: OsOO "Zhartash" (Nomad Camp)

**Check-In & Check-Out**
- Check-in: 14:00
- Check-out: 12:00

**Cancellation Policy**
- Free cancellation 2 or more days before arrival
- 50% of prepayment retained for cancellations made within 24 hours of arrival
- No refund for cancellations less than 24 hours before arrival
- Changes to dates or group size are free if made 2+ days before arrival (price may change based on new dates)

**Meal Plans Available**
- Breakfast only
- Lunch only
- Dinner only
- Half-board: Breakfast + Lunch
- Half-board: Breakfast + Dinner
- Full board: Breakfast + Lunch + Dinner

**On-Site Facilities & Services**
- Nomad Cafe — a cozy in-hotel café with an open kitchen; perfect for morning coffee with lake views
- PlayStation rental (per hour)
- Computer gaming access
- Coffee break packages for conferences, seminars, and business meetings

**Payment Methods**
- Cash at check-in
- Bank card (online reservation or on arrival)
- Pre-issued corporate invoice
- Electronic payments via virtual payment systems
- Bank: Bakay Bank (VIP Center Branch), Account KGS: 1240020001251811

**Ideal Guests**
Families, couples, and groups seeking a peaceful lakeside retreat, as well as small business groups needing a scenic off-site venue for meetings and seminars.

**Unique Selling Points**
- Panoramic lake and mountain views from every balcony
- Authentic atmosphere with Kyrgyz hospitality
- Quiet south-shore location away from crowded tourist spots
- Full-board options so guests can fully relax without worrying about meals
- Versatile for both leisure holidays and small corporate retreats'''
    )

    # Proactive Outreach (Autonomous Agent)
    proactive_outreach_enabled = models.BooleanField(default=False, help_text='Enable autonomous AI follow-ups')
    check_frequency_hours = models.IntegerField(default=24, help_text='How often to check leads (hours)')
    inactivity_threshold_days = models.IntegerField(default=2, help_text='Days of inactivity before follow-up')
    max_followup_attempts = models.IntegerField(default=3, help_text='Maximum follow-up attempts per lead')

    # AI Autonomy Settings
    auto_status_progression = models.BooleanField(default=False, help_text='AI automatically moves leads through pipeline stages')
    smart_objection_handling = models.BooleanField(default=False, help_text='AI detects and handles objections automatically')
    auto_execute_tasks = models.BooleanField(default=False, help_text='AI creates and completes tasks autonomously')
    conversation_goals_enabled = models.BooleanField(default=False, help_text='AI tracks and pursues conversation goals')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'AI Configuration'
        verbose_name_plural = 'AI Configuration'

    def __str__(self):
        return f"AI Config (Auto-response: {'Enabled' if self.ai_auto_response else 'Disabled'})"

    def save(self, *args, **kwargs):
        if not self.pk and AIConfig.objects.filter(organization=self.organization).exists():
            raise ValueError('Only one AI configuration can exist per organization')
        return super().save(*args, **kwargs)

    @classmethod
    def get_config(cls, org=None):
        """Get the org-scoped singleton config instance, create if doesn't exist."""
        if org is not None:
            if not hasattr(org, 'pk'):
                return None  # sentinel: user has no org set
            config, _ = cls.objects.get_or_create(organization=org)
            return config
        # Fallback for background tasks that don't have org context
        return cls.objects.first()


class LeadGoal(models.Model):
    """Conversation goals for a lead that the AI agent works toward."""

    GOAL_TYPES = [
        ('collect_email', 'Collect Email'),
        ('collect_phone', 'Collect Phone'),
        ('schedule_call', 'Schedule Call'),
        ('schedule_meeting', 'Schedule Meeting'),
        ('send_proposal', 'Send Proposal'),
        ('send_info', 'Send Information'),
        ('handle_objection', 'Handle Objection'),
        ('close_deal', 'Close Deal'),
        ('qualify_lead', 'Qualify Lead'),
        ('get_decision_maker', 'Get Decision Maker'),
    ]

    STATUS_ACTIVE = 'active'
    STATUS_COMPLETED = 'completed'
    STATUS_ABANDONED = 'abandoned'

    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_ABANDONED, 'Abandoned'),
    ]

    PRIORITY_LOW = 1
    PRIORITY_MEDIUM = 2
    PRIORITY_HIGH = 3

    PRIORITY_CHOICES = [
        (PRIORITY_LOW, 'Low'),
        (PRIORITY_MEDIUM, 'Medium'),
        (PRIORITY_HIGH, 'High'),
    ]

    organization = models.ForeignKey(**ORG_FK)
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='goals')
    goal_type = models.CharField(max_length=30, choices=GOAL_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    priority = models.IntegerField(choices=PRIORITY_CHOICES, default=PRIORITY_MEDIUM)
    description = models.TextField(blank=True, help_text='Additional context for this goal')
    target_value = models.CharField(max_length=255, blank=True, help_text='Target value to collect (e.g., specific info needed)')
    achieved_value = models.CharField(max_length=255, blank=True, help_text='Value collected when goal achieved')
    attempts = models.IntegerField(default=0, help_text='Number of attempts made toward this goal')
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    is_ai_generated = models.BooleanField(default=False, help_text='Was this goal created by AI')

    class Meta:
        ordering = ['-priority', '-created_at']
        verbose_name = 'Lead Goal'
        verbose_name_plural = 'Lead Goals'

    def __str__(self):
        return f"{self.lead.contact_person or str(self.lead.pk)} - {self.get_goal_type_display()}"


# Register all models with django-auditlog
auditlog.register(Segment)
auditlog.register(PipelineStage)
auditlog.register(Lead)
auditlog.register(LeadNote)
auditlog.register(Task)
auditlog.register(Customer)
auditlog.register(TelegramConfig, exclude_fields=['bot_token'])
auditlog.register(InstagramConnection, exclude_fields=['access_token'])
auditlog.register(WhatsAppConfig, exclude_fields=['access_token'])
auditlog.register(RingCentralConfig, exclude_fields=['client_secret', 'jwt_token'])
auditlog.register(AIConfig)
auditlog.register(LeadGoal)
