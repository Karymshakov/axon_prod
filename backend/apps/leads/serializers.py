from rest_framework import serializers
from .models import Lead, PipelineStage, Segment, Customer, LeadNote, LeadActivity, Task, LeadGoal, AIConfig


class SegmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Segment
        fields = [
            'id',
            'name',
            'key',
            'order',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class PipelineStageSerializer(serializers.ModelSerializer):
    class Meta:
        model = PipelineStage
        fields = [
            'id',
            'name',
            'key',
            'description',
            'order',
            'is_final',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class LeadSerializer(serializers.ModelSerializer):
    segment_display = serializers.SerializerMethodField()
    # Override to accept any pipeline stage key, not just the hardcoded STATUS_CHOICES
    status = serializers.CharField()
    latest_note = serializers.SerializerMethodField()
    last_contact_channel = serializers.SerializerMethodField()
    active_goals_count = serializers.SerializerMethodField()
    current_objection_display = serializers.CharField(source='get_current_objection_display', read_only=True)
    assigned_to_name = serializers.SerializerMethodField()

    def get_segment_display(self, obj):
        if obj.segment:
            segment = Segment.objects.filter(key=obj.segment).first()
            if segment:
                return segment.name
        return obj.segment or ''

    def get_latest_note(self, obj):
        latest = obj.lead_notes.first()
        if latest:
            return latest.content
        # Fall back to lead.notes which holds the AI-generated conversation summary
        return obj.notes or ''

    def get_active_goals_count(self, obj):
        return obj.goals.filter(status=LeadGoal.STATUS_ACTIVE).count()

    def get_assigned_to_name(self, obj):
        if obj.assigned_to:
            return obj.assigned_to.name or obj.assigned_to.email
        return None

    def get_last_contact_channel(self, obj):
        """Get the channel used for the most recent communication."""
        communication_types = [
            LeadActivity.TYPE_TELEGRAM_SENT,
            LeadActivity.TYPE_TELEGRAM_RECEIVED,
            LeadActivity.TYPE_INSTAGRAM_SENT,
            LeadActivity.TYPE_INSTAGRAM_RECEIVED,
            LeadActivity.TYPE_WHATSAPP_SENT,
            LeadActivity.TYPE_WHATSAPP_RECEIVED,
        ]
        last_activity = obj.activities.filter(
            activity_type__in=communication_types
        ).order_by('-created_at').first()

        if not last_activity:
            return None

        # Map activity type to channel name and contact info
        channel_map = {
            LeadActivity.TYPE_TELEGRAM_SENT: ('Telegram', obj.telegram_username and f'@{obj.telegram_username}'),
            LeadActivity.TYPE_TELEGRAM_RECEIVED: ('Telegram', obj.telegram_username and f'@{obj.telegram_username}'),
            LeadActivity.TYPE_INSTAGRAM_SENT: ('Instagram', obj.instagram_username and f'@{obj.instagram_username}'),
            LeadActivity.TYPE_INSTAGRAM_RECEIVED: ('Instagram', obj.instagram_username and f'@{obj.instagram_username}'),
            LeadActivity.TYPE_WHATSAPP_SENT: ('WhatsApp', obj.whatsapp_phone),
            LeadActivity.TYPE_WHATSAPP_RECEIVED: ('WhatsApp', obj.whatsapp_phone),
        }

        channel, contact = channel_map.get(last_activity.activity_type, (None, None))
        return {
            'channel': channel,
            'contact': contact or '-',
        } if channel else None

    class Meta:
        model = Lead
        fields = [
            'id',
            # Contact Details
            'contact_person',
            'job_title',
            'email',
            'secondary_email',
            'phone',
            'mobile_phone',
            'office_phone',
            'website',
            'linkedin_url',
            # Location/Geography
            'address',
            'city',
            'state_province',
            'postal_code',
            'country',
            'timezone',
            # Lead Management
            'segment',
            'segment_display',
            'status',
            'source',
            'estimated_value',
            'notes',
            'last_contacted',
            # Hotel Booking Details
            'check_in_date',
            'check_out_date',
            'guest_count',
            'room_type_preference',
            'meal_plan',
            # Summary & Next Steps
            'problem_description',
            'next_steps',
            # Communication Tracking
            'preferred_contact_method',
            'preferred_contact_time',
            'language',
            'do_not_contact',
            'email_bounced',
            'unsubscribed_at',
            # Sales Process
            'next_follow_up_date',
            'expected_close_date',
            'lost_reason',
            'competitor',
            'referral_source',
            'campaign_source',
            # Source-specific identifiers
            'telegram_user_id',
            'telegram_username',
            'telegram_chat_id',
            'instagram_user_id',
            'instagram_username',
            'whatsapp_phone',
            # Instagram intent classification
            'instagram_intent_tier',
            # Manual takeover
            'ai_paused',
            'ai_paused_at',
            'ai_paused_by',
            # Assignment
            'assigned_to',
            'assigned_to_name',
            # AI Agent tracking
            'ai_followup_count',
            'last_ai_followup_at',
            # Objection tracking
            'current_objection',
            'current_objection_display',
            'last_objection_at',
            'objection_count',
            # Timestamps
            'created_at',
            'updated_at',
            # Computed fields
            'latest_note',
            'last_contact_channel',
            'active_goals_count',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'latest_note', 'last_contact_channel', 'active_goals_count', 'assigned_to_name', 'ai_paused_at', 'ai_paused_by']


class LeadNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeadNote
        fields = [
            'id',
            'lead',
            'content',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class LeadActivitySerializer(serializers.ModelSerializer):
    activity_type_display = serializers.CharField(source='get_activity_type_display', read_only=True)

    class Meta:
        model = LeadActivity
        fields = [
            'id',
            'lead',
            'activity_type',
            'activity_type_display',
            'description',
            'metadata',
            'is_read',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class TaskSerializer(serializers.ModelSerializer):
    task_type_display = serializers.CharField(source='get_task_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    execution_type_display = serializers.CharField(source='get_execution_type_display', read_only=True)
    is_overdue = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = [
            'id',
            'lead',
            'title',
            'description',
            'task_type',
            'task_type_display',
            'status',
            'status_display',
            'due_date',
            'completed_at',
            # Auto-execution fields
            'is_auto_executable',
            'execution_type',
            'execution_type_display',
            'execution_content',
            'executed_at',
            'execution_result',
            'is_ai_generated',
            # Timestamps
            'is_overdue',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'completed_at', 'executed_at', 'execution_result']

    def get_is_overdue(self, obj):
        from datetime import date
        return obj.status == Task.STATUS_PENDING and obj.due_date < date.today()


class CustomerSerializer(serializers.ModelSerializer):
    segment_display = serializers.SerializerMethodField()
    customer_status_display = serializers.CharField(source='get_customer_status_display', read_only=True)
    lead_id = serializers.IntegerField(source='lead.id', read_only=True, allow_null=True)
    has_telegram = serializers.SerializerMethodField()
    has_instagram = serializers.SerializerMethodField()
    has_whatsapp = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = [
            'id',
            'lead',
            'lead_id',
            'contact_person',
            'email',
            'phone',
            # Business info
            'segment',
            'segment_display',
            'source',
            'customer_status',
            'customer_status_display',
            'notes',
            # Communication channels
            'telegram_chat_id',
            'telegram_username',
            'instagram_user_id',
            'instagram_username',
            'whatsapp_phone',
            # Computed fields
            'has_telegram',
            'has_instagram',
            'has_whatsapp',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'lead', 'lead_id', 'created_at', 'updated_at']

    def get_segment_display(self, obj):
        if obj.segment:
            segment = Segment.objects.filter(key=obj.segment).first()
            if segment:
                return segment.name
        return obj.segment or ''

    def get_has_telegram(self, obj):
        return bool(obj.telegram_chat_id)

    def get_has_instagram(self, obj):
        return bool(obj.instagram_user_id)

    def get_has_whatsapp(self, obj):
        return bool(obj.whatsapp_phone)


class LeadGoalSerializer(serializers.ModelSerializer):
    goal_type_display = serializers.CharField(source='get_goal_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)

    class Meta:
        model = LeadGoal
        fields = [
            'id',
            'lead',
            'goal_type',
            'goal_type_display',
            'status',
            'status_display',
            'priority',
            'priority_display',
            'description',
            'target_value',
            'achieved_value',
            'attempts',
            'is_ai_generated',
            'completed_at',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'completed_at', 'attempts', 'is_ai_generated']


class AIConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIConfig
        fields = [
            'id',
            # Auto-Response (Reactive)
            'ai_auto_response',
            'auto_extract_data',
            'response_delay',
            'telegram_ai_paused',
            'instagram_ai_paused',
            'whatsapp_ai_paused',
            'system_prompt',
            'company_profile',
            # Proactive Outreach
            'proactive_outreach_enabled',
            'check_frequency_hours',
            'inactivity_threshold_days',
            'max_followup_attempts',
            # Autonomy Settings
            'auto_status_progression',
            'smart_objection_handling',
            'auto_execute_tasks',
            'conversation_goals_enabled',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

