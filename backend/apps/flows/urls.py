from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ConversationFlowViewSet, FlowCardViewSet, FlowConnectionViewSet, ai_flow_mode, AIToolViewSet, ai_model_config, transfer_config, AgentConfigViewSet

router = DefaultRouter()
router.register(r'flows', ConversationFlowViewSet, basename='flows')
router.register(r'flow-cards', FlowCardViewSet, basename='flow-cards')
router.register(r'flow-connections', FlowConnectionViewSet, basename='flow-connections')
router.register(r'ai-tools', AIToolViewSet, basename='ai-tools')
router.register(r'agents', AgentConfigViewSet, basename='agents')

urlpatterns = [
    # mode/ must come BEFORE router include to avoid flows/{pk}/ swallowing it
    path('flows/mode/', ai_flow_mode, name='ai-flow-mode'),
    path('ai-model-config/', ai_model_config, name='ai-model-config'),
    path('transfer-config/', transfer_config, name='transfer-config'),
    # Nested: cards/connections scoped to a flow
    path('flows/<int:flow_pk>/cards/', FlowCardViewSet.as_view({'get': 'list', 'post': 'create'}), name='flow-cards-nested'),
    path('flows/<int:flow_pk>/cards/<int:pk>/prompt-preview/', FlowCardViewSet.as_view({'get': 'prompt_preview'}), name='flow-card-prompt-preview'),
    path('flows/<int:flow_pk>/connections/', FlowConnectionViewSet.as_view({'get': 'list', 'post': 'create'}), name='flow-connections-nested'),
    path('flow-cards/schema/', FlowCardViewSet.as_view({'get': 'schema'}), name='flow-card-schema'),
    path('', include(router.urls)),
]
