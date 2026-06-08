from rest_framework import serializers
from .models import ConversationFlow, FlowCard, FlowConnection, AIFlowMode, LeadFlowState, AITool, AIModelConfig, ManagerTransferConfig, AgentConfig


class FlowConnectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FlowConnection
        fields = ['id', 'flow', 'source_card', 'target_card', 'condition_label', 'condition_keywords', 'created_at']
        # flow is set by perform_create via URL param, must be read_only
        read_only_fields = ['id', 'flow', 'created_at']


class FlowCardSerializer(serializers.ModelSerializer):
    outgoing_connections = FlowConnectionSerializer(many=True, read_only=True)
    playbook_names = serializers.SerializerMethodField()

    class Meta:
        model = FlowCard
        fields = [
            'id', 'flow', 'card_type', 'title', 'message_template',
            'goal', 'required_fields', 'success_conditions', 'allowed_tools',
            'response_policy', 'return_to_funnel_instruction',
            'playbooks', 'playbook_names', 'position_x', 'position_y',
            'created_at', 'outgoing_connections',
        ]
        read_only_fields = ['id', 'flow', 'playbook_names', 'created_at']

    def get_playbook_names(self, obj):
        return list(obj.playbooks.values_list('name', flat=True))


class ConversationFlowListSerializer(serializers.ModelSerializer):
    card_count = serializers.SerializerMethodField()

    class Meta:
        model = ConversationFlow
        fields = ['id', 'name', 'description', 'is_active', 'global_prompt', 'card_count', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_card_count(self, obj):
        return obj.cards.count()


class ConversationFlowDetailSerializer(serializers.ModelSerializer):
    cards = FlowCardSerializer(many=True, read_only=True)
    connections = FlowConnectionSerializer(many=True, read_only=True)

    class Meta:
        model = ConversationFlow
        fields = ['id', 'name', 'description', 'is_active', 'global_prompt', 'cards', 'connections', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class AIFlowModeSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIFlowMode
        fields = ['mode', 'updated_at']
        read_only_fields = ['updated_at']


class LeadFlowStateSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeadFlowState
        fields = ['id', 'lead', 'flow', 'current_card', 'is_complete', 'is_escalated', 'collected_data', 'started_at', 'updated_at']
        read_only_fields = ['id', 'started_at', 'updated_at']


class AIToolSerializer(serializers.ModelSerializer):
    class Meta:
        model = AITool
        fields = [
            'id', 'name', 'display_name', 'description',
            'parameters_schema', 'runtime_config', 'is_enabled',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class AIModelConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIModelConfig
        fields = ['temperature', 'max_tokens', 'updated_at']
        read_only_fields = ['updated_at']

    def validate_temperature(self, value):
        if not (0.0 <= value <= 1.0):
            raise serializers.ValidationError('Temperature must be between 0.0 and 1.0')
        return value

    def validate_max_tokens(self, value):
        if not (100 <= value <= 1000):
            raise serializers.ValidationError('max_tokens must be between 100 and 1000')
        return value


class AgentConfigSerializer(serializers.ModelSerializer):
    playbook_names = serializers.SerializerMethodField()

    class Meta:
        model = AgentConfig
        fields = [
            'id', 'name', 'display_name', 'system_prompt',
            'playbooks', 'playbook_names', 'tools', 'is_editable',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'name', 'is_editable', 'created_at', 'updated_at', 'playbook_names']

    def get_playbook_names(self, obj):
        return list(obj.playbooks.values_list('name', flat=True))

    def validate(self, attrs):
        return attrs


class ManagerTransferConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = ManagerTransferConfig
        fields = ['channel', 'recipient_id', 'manager_name', 'notification_template', 'updated_at']
        read_only_fields = ['updated_at']

    def validate(self, attrs):
        channel = attrs.get('channel', getattr(self.instance, 'channel', 'telegram'))
        recipient_id = attrs.get('recipient_id', getattr(self.instance, 'recipient_id', ''))
        if channel == 'telegram' and recipient_id and recipient_id.startswith('@'):
            raise serializers.ValidationError(
                {'recipient_id': 'Enter a numeric Chat ID, not a @username. '
                                 'Use @userinfobot in Telegram to get your numeric ID.'}
            )
        return attrs
