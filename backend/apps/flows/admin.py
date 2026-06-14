from django.contrib import admin
from .models import (
    AgentConfig,
    AIFlowMode,
    AIModelConfig,
    AITool,
    ConversationFlow,
    FlowCard,
    FlowConnection,
    LeadFlowState,
    ManagerTransferConfig,
)

@admin.register(ConversationFlow)
class ConversationFlowAdmin(admin.ModelAdmin):
    list_display = ('name', 'organization', 'is_active', 'updated_at')
    list_filter = ('is_active', 'organization')
    search_fields = ('name', 'description')


@admin.register(FlowCard)
class FlowCardAdmin(admin.ModelAdmin):
    list_display = ('title', 'flow', 'card_type', 'created_at')
    list_filter = ('card_type', 'flow__organization')
    search_fields = ('title', 'goal', 'message_template')
    filter_horizontal = ('playbooks',)


@admin.register(FlowConnection)
class FlowConnectionAdmin(admin.ModelAdmin):
    list_display = ('source_card', 'target_card', 'condition_label', 'flow')
    list_filter = ('flow__organization',)
    search_fields = ('condition_label', 'condition_keywords')


@admin.register(AITool)
class AIToolAdmin(admin.ModelAdmin):
    list_display = ('name', 'display_name', 'organization', 'is_enabled', 'updated_at')
    list_filter = ('is_enabled', 'organization')
    search_fields = ('name', 'display_name', 'description')


admin.site.register(AIFlowMode)
admin.site.register(AIModelConfig)
admin.site.register(ManagerTransferConfig)
admin.site.register(AgentConfig)
admin.site.register(LeadFlowState)
