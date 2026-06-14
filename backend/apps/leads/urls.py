from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    LeadViewSet,
    PipelineStageViewSet,
    SegmentViewSet,
    CustomerViewSet,
    LeadNoteViewSet,
    LeadActivityViewSet,
    TaskViewSet,
    LeadGoalViewSet,
    communications_unread_counts,
    communications_mark_read,
)
from .telegram_views import telegram_webhook
from .instagram_views import instagram_webhook
from .instagram_integration_views import (
    instagram_status,
    instagram_authorize,
    instagram_callback,
    instagram_disconnect,
    instagram_refresh_token,
)
from .whatsapp_views import whatsapp_webhook
from .whatsapp_integration_views import (
    whatsapp_authorize,
    whatsapp_callback,
    whatsapp_status,
    whatsapp_disconnect,
    resubscribe_whatsapp_webhook,
)
from .ringcentral_views import ringcentral_webhook
from .integration_views import (
    telegram_integration_status,
    save_telegram_token,
    disconnect_telegram,
    register_telegram_webhook,
    send_telegram_message_from_comms,
    send_instagram_message_from_comms,
    save_instagram_app_credentials,
    save_whatsapp_app_credentials,
    save_whatsapp_direct_config,
    resubscribe_instagram_webhook,
    send_whatsapp_message_from_comms,
    send_telegram_to_customer,
    send_instagram_to_customer,
    send_whatsapp_to_customer,
    get_ai_config,
    update_ai_config,
    run_agent_now,
    ringcentral_integration_status,
    save_ringcentral_credentials,
    disconnect_ringcentral,
    reregister_ringcentral_webhook,
    send_ringcentral_sms_from_comms,
    ringcentral_ringout,
)

router = DefaultRouter()
router.register(r'leads', LeadViewSet)
router.register(r'pipeline-stages', PipelineStageViewSet)
router.register(r'segments', SegmentViewSet)
router.register(r'customers', CustomerViewSet)
router.register(r'lead-notes', LeadNoteViewSet, basename='lead-note')
router.register(r'lead-activities', LeadActivityViewSet, basename='lead-activity')
router.register(r'tasks', TaskViewSet, basename='task')
router.register(r'lead-goals', LeadGoalViewSet, basename='lead-goal')

urlpatterns = [
    path('', include(router.urls)),
    # Telegram
    path('telegram-webhook/', telegram_webhook, name='telegram-webhook'),
    path('integrations/telegram/status/', telegram_integration_status, name='telegram-integration-status'),
    path('integrations/telegram/save-token/', save_telegram_token, name='save-telegram-token'),
    path('integrations/telegram/disconnect/', disconnect_telegram, name='disconnect-telegram'),
    path('integrations/telegram/register-webhook/', register_telegram_webhook, name='register-telegram-webhook'),
    path('communications/telegram/send/', send_telegram_message_from_comms, name='send-telegram-message-comms'),
    # Instagram
    path('integrations/instagram/status/', instagram_status, name='instagram-status'),
    path('integrations/instagram/authorize/', instagram_authorize, name='instagram-authorize'),
    path('integrations/instagram/callback/', instagram_callback, name='instagram-callback'),
    path('integrations/instagram-oauth/callback/', instagram_callback, name='instagram-oauth-callback'),
    path('integrations/instagram/disconnect/', instagram_disconnect, name='instagram-disconnect'),
    path('integrations/instagram/refresh-token/', instagram_refresh_token, name='instagram-refresh-token'),
    path('integrations/instagram/webhook/', instagram_webhook, name='instagram-webhook'),
    path('instagram-webhook/', instagram_webhook, name='instagram-webhook-legacy'),  # Meta dashboard may have old URL
    path('communications/instagram/send/', send_instagram_message_from_comms, name='send-instagram-message-comms'),
    path('integrations/instagram/save-app-credentials/', save_instagram_app_credentials, name='save-instagram-app-credentials'),
    path('integrations/whatsapp/save-app-credentials/', save_whatsapp_app_credentials, name='save-whatsapp-app-credentials'),
    path('integrations/instagram/resubscribe-webhook/', resubscribe_instagram_webhook, name='resubscribe-instagram-webhook'),
    # WhatsApp
    path('whatsapp-webhook/', whatsapp_webhook, name='whatsapp-webhook'),
    path('integrations/whatsapp-oauth/authorize/', whatsapp_authorize, name='whatsapp-oauth-authorize'),
    path('integrations/whatsapp-oauth/callback/', whatsapp_callback, name='whatsapp-oauth-callback'),
    path('integrations/whatsapp/status/', whatsapp_status, name='whatsapp-status'),
    path('integrations/whatsapp/disconnect/', whatsapp_disconnect, name='whatsapp-disconnect'),
    path('integrations/whatsapp/resubscribe-webhook/', resubscribe_whatsapp_webhook, name='resubscribe-whatsapp-webhook'),
    path('integrations/whatsapp/connect/', save_whatsapp_direct_config, name='whatsapp-direct-connect'),
    path('communications/whatsapp/send/', send_whatsapp_message_from_comms, name='send-whatsapp-message-comms'),
    # Customer messaging
    path('communications/telegram/send-customer/', send_telegram_to_customer, name='send-telegram-to-customer'),
    path('communications/instagram/send-customer/', send_instagram_to_customer, name='send-instagram-to-customer'),
    path('communications/whatsapp/send-customer/', send_whatsapp_to_customer, name='send-whatsapp-to-customer'),
    # Communications unread counts
    path('communications/unread-counts/', communications_unread_counts, name='communications-unread-counts'),
    path('communications/mark-read/', communications_mark_read, name='communications-mark-read'),
    # AI Config
    path('ai-config/', get_ai_config, name='ai-config'),
    path('ai-config/update/', update_ai_config, name='update-ai-config'),
    # AI Agent
    path('ai-agent/run/', run_agent_now, name='run-agent-now'),
    # RingCentral
    path('ringcentral-webhook/', ringcentral_webhook, name='ringcentral-webhook'),
    path('integrations/ringcentral/status/', ringcentral_integration_status, name='ringcentral-integration-status'),
    path('integrations/ringcentral/save-credentials/', save_ringcentral_credentials, name='save-ringcentral-credentials'),
    path('integrations/ringcentral/disconnect/', disconnect_ringcentral, name='disconnect-ringcentral'),
    path('integrations/ringcentral/reregister-webhook/', reregister_ringcentral_webhook, name='reregister-ringcentral-webhook'),
    path('communications/ringcentral/send-sms/', send_ringcentral_sms_from_comms, name='send-ringcentral-sms-comms'),
    path('communications/ringcentral/ringout/', ringcentral_ringout, name='ringcentral-ringout'),
]
