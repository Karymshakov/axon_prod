import asyncio
import os
import logging
import requests
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .telegram_service import telegram_service
from .instagram_service import instagram_service
from .whatsapp_service import whatsapp_service
from .ringcentral_service import ringcentral_service
from .models import TelegramConfig, RingCentralConfig, AIConfig, InstagramAppConfig, WhatsAppAppConfig
from .serializers import AIConfigSerializer


class _OrgNotSet:
    """Sentinel: user is authenticated but has no current_organization set."""


_NO_ORG = _OrgNotSet()


def _get_org(request):
    """
    Returns:
    - None: superadmin (all-access, get_config falls back to first())
    - Organization instance: user's current org
    - _NO_ORG sentinel: non-superadmin with no current_organization set
    """
    user = request.user
    if getattr(user, 'is_superadmin', False):
        return None  # superadmin: no filter, use db fallback
    org = getattr(user, 'current_organization', None)
    return org if org is not None else _NO_ORG


def _no_org_response(connected_key='configured'):
    """Return a 'not connected' response when the user has no organization."""
    from rest_framework.response import Response as R
    return R({connected_key: False})

logger = logging.getLogger(__name__)


def _get_webhook_base_url():
    """Get the public-facing HTTPS base URL for webhook registration.

    Reads APP_DOMAIN from environment. Must be a publicly accessible HTTPS URL
    (e.g. a Cloudflare tunnel). Returns None if not configured.
    """
    domain = os.environ.get('APP_DOMAIN', '').strip().rstrip('/')
    if not domain:
        return None
    if not domain.startswith('http'):
        return f'https://{domain}'
    return domain


def _register_telegram_webhook(bot_token, base_url_override=None):
    """Register the webhook URL with Telegram. Returns (success, message)."""
    import time

    base_url = base_url_override or _get_webhook_base_url()
    if not base_url:
        return False, 'Could not determine public webhook URL'

    webhook_url = f'{base_url}/api/telegram-webhook/'
    for attempt in range(3):
        try:
            response = requests.post(
                f'https://api.telegram.org/bot{bot_token}/setWebhook',
                json={'url': webhook_url, 'allowed_updates': ['message']},
                timeout=10,
            )
            data = response.json()
            if data.get('ok'):
                logger.info(f'Telegram webhook registered: {webhook_url}')
                return True, webhook_url
            # Retry on rate-limit
            if data.get('error_code') == 429:
                retry_after = data.get('parameters', {}).get('retry_after', 2)
                logger.warning(f'Telegram rate-limited, retrying in {retry_after}s (attempt {attempt+1})')
                time.sleep(retry_after)
                continue
            logger.error(f'Telegram setWebhook failed: {data}')
            return False, data.get('description', 'Failed to register webhook')
        except Exception as e:
            logger.error(f'Error registering Telegram webhook: {e}')
            return False, str(e)
    return False, 'Failed to register webhook after retries'


@api_view(['GET'])
def telegram_integration_status(request):
    """Get Telegram bot integration status and info."""
    org = _get_org(request)
    if isinstance(org, _OrgNotSet):
        return Response({'configured': False, 'bot_username': None, 'connected_at': None})

    config = TelegramConfig.get_config(org=org)
    if config:
        return Response({
            'configured': True,
            'bot_username': config.bot_username,
            'bot_first_name': config.bot_first_name,
            'connected_at': config.connected_at.isoformat(),
        })

    # For org-scoped users: no DB config = not connected. Never fall back to the
    # global telegram_service (which holds another org's bot token) for org users.
    if org is not None:
        return Response({'configured': False, 'bot_username': None, 'connected_at': None})

    # Superadmin path only (org=None): fall back to env var / service check
    if not telegram_service.is_configured():
        return Response({'configured': False, 'bot_username': None, 'connected_at': None})

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        bot_info = loop.run_until_complete(telegram_service.get_bot_info())
        loop.close()

        if bot_info:
            return Response({
                'configured': True,
                'bot_username': bot_info.get('username'),
                'bot_first_name': bot_info.get('first_name'),
                'connected_at': None,
            })
        return Response({'configured': False, 'bot_username': None, 'connected_at': None,
                         'error': 'Failed to connect to Telegram bot'})
    except Exception as e:
        return Response({'configured': False, 'bot_username': None, 'connected_at': None,
                         'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def save_telegram_token(request):
    """Save Telegram bot token to database."""
    bot_token = request.data.get('bot_token', '').strip()

    if not bot_token:
        return Response({
            'success': False,
            'error': 'Bot token is required'
        }, status=status.HTTP_400_BAD_REQUEST)

    # Validate token format (basic check)
    if ':' not in bot_token:
        return Response({
            'success': False,
            'error': 'Invalid token format. Expected format: 123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Validate token by calling Telegram API
        telegram_api_url = f'https://api.telegram.org/bot{bot_token}/getMe'
        response = requests.get(telegram_api_url, timeout=10)

        if not response.ok:
            return Response({
                'success': False,
                'error': 'Invalid bot token. Please check the token and try again.'
            }, status=status.HTTP_400_BAD_REQUEST)

        bot_info = response.json().get('result', {})

        # Save to database (update or create)
        org = _get_org(request)
        if isinstance(org, _OrgNotSet):
            return Response({'success': False, 'error': 'No organization selected.'}, status=status.HTTP_400_BAD_REQUEST)
        config = TelegramConfig.get_config(org=org)
        if config:
            config.bot_token = bot_token
            config.bot_username = bot_info.get('username', '')
            config.bot_first_name = bot_info.get('first_name', '')
            config.save()
        else:
            config = TelegramConfig.objects.create(
                organization=org,
                bot_token=bot_token,
                bot_username=bot_info.get('username', ''),
                bot_first_name=bot_info.get('first_name', ''),
            )

        # Also try to save to environment variable (optional, may fail in development)
        try:
            env_api_url = os.environ.get('CAYU_ENV_API_URL')
            if env_api_url:
                requests.post(
                    env_api_url,
                    json={'TELEGRAM_BOT_TOKEN': bot_token},
                    headers={'Content-Type': 'application/json'},
                    timeout=5
                )
        except Exception:
            # Silently fail - env var sync is optional
            pass

        # Register webhook with Telegram
        webhook_registered, webhook_result = _register_telegram_webhook(bot_token)
        if not webhook_registered:
            logger.warning(f'Bot saved but webhook registration failed: {webhook_result}')

        return Response({
            'success': True,
            'bot_username': bot_info.get('username'),
            'bot_first_name': bot_info.get('first_name'),
            'webhook_registered': webhook_registered,
            'webhook_url': webhook_result if webhook_registered else None,
        })

    except requests.Timeout:
        return Response({
            'success': False,
            'error': 'Request timed out. Please check your connection and try again.'
        }, status=status.HTTP_504_GATEWAY_TIMEOUT)
    except requests.RequestException as e:
        return Response({
            'success': False,
            'error': f'Network error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except Exception as e:
        return Response({
            'success': False,
            'error': f'Unexpected error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def register_telegram_webhook(request):
    """Re-register the Telegram webhook URL for an already-connected bot."""
    org = _get_org(request)
    if isinstance(org, _OrgNotSet):
        return Response({'success': False, 'error': 'No organization selected.'}, status=status.HTTP_400_BAD_REQUEST)
    config = TelegramConfig.get_config(org=org)
    if not config:
        return Response({
            'success': False,
            'error': 'Telegram bot not connected. Please connect a bot first.',
        }, status=status.HTTP_400_BAD_REQUEST)

    base_url_override = (request.data.get('base_url') or '').strip().rstrip('/') or None
    success, result = _register_telegram_webhook(config.bot_token, base_url_override=base_url_override)
    if success:
        return Response({'success': True, 'webhook_url': result})
    return Response({'success': False, 'error': result}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def disconnect_telegram(request):
    """Disconnect Telegram bot by deleting the configuration."""
    try:
        org = _get_org(request)
        if isinstance(org, _OrgNotSet):
            return Response({'success': True, 'message': 'No Telegram bot to disconnect'})
        config = TelegramConfig.get_config(org=org)
        if config:
            config.delete()

        return Response({
            'success': True,
            'message': 'Telegram bot disconnected successfully'
        })
    except Exception as e:
        return Response({
            'success': False,
            'error': f'Failed to disconnect: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def send_telegram_message_from_comms(request):
    """Send a Telegram message from the communications page."""
    lead_id = request.data.get('lead_id')
    message_text = request.data.get('message', '').strip()

    if not lead_id or not message_text:
        return Response({
            'success': False,
            'error': 'Lead ID and message are required'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        from .models import Lead, LeadActivity

        # Get the lead
        lead = Lead.objects.get(id=lead_id)

        if not lead.telegram_chat_id:
            return Response({
                'success': False,
                'error': 'This lead does not have a Telegram chat ID configured'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Send message using async
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            telegram_service.send_message(lead.telegram_chat_id, message_text)
        )
        loop.close()

        if not result:
            return Response({
                'success': False,
                'error': 'Failed to send message. Check bot configuration.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Log activity
        LeadActivity.objects.create(
            lead=lead,
            organization=lead.organization,
            activity_type=LeadActivity.TYPE_TELEGRAM_SENT,
            description=f"Sent Telegram message: {message_text[:100]}{'...' if len(message_text) > 100 else ''}",
            metadata={
                'message_id': result.get('message_id'),
                'text': message_text,
                'is_manager_manual': True,
            }
        )

        return Response({
            'success': True,
            'message_id': result.get('message_id'),
        })

    except Lead.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Lead not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_ai_config(request):
    """Get AI configuration settings."""
    org = _get_org(request)
    if isinstance(org, _OrgNotSet):
        # Return default empty config for users with no organization
        return Response(AIConfigSerializer(AIConfig()).data)
    config = AIConfig.get_config(org=org)
    serializer = AIConfigSerializer(config)
    return Response(serializer.data)


@api_view(['PATCH'])
def update_ai_config(request):
    """Update AI configuration settings."""
    org = _get_org(request)
    if isinstance(org, _OrgNotSet):
        return Response({'error': 'No organization selected.'}, status=status.HTTP_400_BAD_REQUEST)
    config = AIConfig.get_config(org=org)
    serializer = AIConfigSerializer(config, data=request.data, partial=True)

    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)




def save_instagram_token(request):
    """REMOVED."""
    return Response({'error': 'Use OAuth flow'}, status=status.HTTP_410_GONE)


@api_view(['POST'])
def save_instagram_app_credentials(request):
    """Save Meta App credentials (App ID, App Secret, Webhook Verify Token) to DB."""
    app_id = request.data.get('app_id', '').strip()
    app_secret = request.data.get('app_secret', '').strip()
    webhook_verify_token = request.data.get('webhook_verify_token', '').strip()

    if not app_secret:
        return Response({'success': False, 'error': 'App Secret is required'},
                        status=status.HTTP_400_BAD_REQUEST)

    org = _get_org(request)
    if isinstance(org, _OrgNotSet):
        return Response({'success': False, 'error': 'No organization selected.'}, status=status.HTTP_400_BAD_REQUEST)
    config = InstagramAppConfig.get_config(org=org)
    if config:
        if app_id:
            config.app_id = app_id
        config.app_secret = app_secret
        if webhook_verify_token:
            config.webhook_verify_token = webhook_verify_token
        config.save()
    else:
        InstagramAppConfig.objects.create(
            organization=org,
            app_id=app_id,
            app_secret=app_secret,
            webhook_verify_token=webhook_verify_token,
        )

    return Response({'success': True})


@api_view(['POST'])
def save_whatsapp_app_credentials(request):
    """Save Meta App credentials (App ID, App Secret) for WhatsApp OAuth to DB."""
    app_id = request.data.get('app_id', '').strip()
    app_secret = request.data.get('app_secret', '').strip()

    if not app_secret:
        return Response({'success': False, 'error': 'App Secret is required'},
                        status=status.HTTP_400_BAD_REQUEST)

    org = _get_org(request)
    if isinstance(org, _OrgNotSet):
        return Response({'success': False, 'error': 'No organization selected.'}, status=status.HTTP_400_BAD_REQUEST)
    config = WhatsAppAppConfig.get_config(org=org)
    if config:
        if app_id:
            config.app_id = app_id
        config.app_secret = app_secret
        config.save()
    else:
        WhatsAppAppConfig.objects.create(
            organization=org,
            app_id=app_id or '',
            app_secret=app_secret,
        )

    return Response({'success': True})


GRAPH_URL = 'https://graph.facebook.com/v18.0'


@api_view(['POST'])
def save_whatsapp_direct_config(request):
    """Connect WhatsApp by directly entering Phone Number ID, WABA ID, and Access Token.

    Verifies credentials by calling the Meta Graph API before saving.
    A System User Token is permanent and does not require periodic refresh.
    Optional: app_id, app_secret (saved to WhatsAppAppConfig for webhook subscription),
    and verify_token (auto-generated UUID if not provided).
    """
    import threading
    import uuid
    from .models import WhatsAppConfig
    from .whatsapp_integration_views import _auto_subscribe_webhook

    phone_number_id = request.data.get('phone_number_id', '').strip()
    waba_id = request.data.get('waba_id', '').strip()
    access_token = request.data.get('access_token', '').strip()
    app_id = request.data.get('app_id', '').strip()
    app_secret = request.data.get('app_secret', '').strip()
    verify_token = request.data.get('verify_token', '').strip()

    if not phone_number_id:
        return Response({'success': False, 'error': 'Phone Number ID is required'},
                        status=status.HTTP_400_BAD_REQUEST)
    if not waba_id:
        return Response({'success': False, 'error': 'Business Account ID is required'},
                        status=status.HTTP_400_BAD_REQUEST)
    if not access_token:
        return Response({'success': False, 'error': 'Access Token is required'},
                        status=status.HTTP_400_BAD_REQUEST)

    # Verify credentials via Meta API and fetch display phone number
    try:
        resp = requests.get(
            f'{GRAPH_URL}/{phone_number_id}',
            params={'fields': 'display_phone_number,verified_name', 'access_token': access_token},
            timeout=10,
        )
        data = resp.json()
        if not resp.ok or 'error' in data:
            err_msg = data.get('error', {}).get('message', 'Invalid credentials')
            return Response(
                {'success': False, 'error': f'Invalid credentials: {err_msg}'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        display_phone_number = data.get('display_phone_number', '')
        verified_name = data.get('verified_name', '')
    except requests.RequestException as e:
        logger.error(f'Meta API verification failed: {e}')
        return Response(
            {'success': False, 'error': 'Could not reach Meta API. Please check your credentials.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    org = _get_org(request)
    if isinstance(org, _OrgNotSet):
        return Response({'success': False, 'error': 'No organization selected.'}, status=status.HTTP_400_BAD_REQUEST)

    # Save app credentials if provided
    if app_id or app_secret:
        app_cfg = WhatsAppAppConfig.get_config(org=org)
        if app_cfg:
            if app_id:
                app_cfg.app_id = app_id
            if app_secret:
                app_cfg.app_secret = app_secret
            app_cfg.save()
        else:
            WhatsAppAppConfig.objects.create(
                organization=org,
                app_id=app_id or '',
                app_secret=app_secret,
            )

    # Generate verify_token if not supplied
    if not verify_token:
        existing = WhatsAppConfig.get_config(org=org)
        verify_token = (existing.verify_token if existing and existing.verify_token
                        else str(uuid.uuid4()))

    conn = WhatsAppConfig.get_config(org=org)
    if conn:
        conn.phone_number_id = phone_number_id
        conn.waba_id = waba_id
        conn.access_token = access_token
        conn.display_phone_number = display_phone_number
        conn.verified_name = verified_name
        conn.token_expires_at = None  # System user tokens don't expire
        conn.webhook_subscribed = False
        conn.verify_token = verify_token
        conn.save()
    else:
        conn = WhatsAppConfig.objects.create(
            organization=org,
            phone_number_id=phone_number_id,
            waba_id=waba_id,
            access_token=access_token,
            display_phone_number=display_phone_number,
            verified_name=verified_name,
            token_expires_at=None,
            verify_token=verify_token,
        )

    # Auto-subscribe WABA to webhook events in background
    threading.Thread(
        target=_auto_subscribe_webhook,
        args=(conn.id,),
        daemon=True,
    ).start()

    return Response({
        'success': True,
        'display_phone_number': display_phone_number,
        'verified_name': verified_name,
        'verify_token': verify_token,
    })


@api_view(['POST'])
def resubscribe_instagram_webhook(request):
    """Subscribe (or re-subscribe) the connected Instagram account to receive webhook events.

    Must be called once after OAuth to activate DM delivery.
    Safe to call multiple times — Meta accepts duplicate subscriptions.
    """
    from .models import InstagramConnection
    org = _get_org(request)
    if isinstance(org, _OrgNotSet):
        return Response({'success': False, 'error': 'Instagram not connected'}, status=status.HTTP_400_BAD_REQUEST)
    conn = InstagramConnection.get_config(org=org)
    if not conn or not conn.access_token:
        return Response({'success': False, 'error': 'Instagram not connected'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        resp = requests.post(
            'https://graph.instagram.com/v21.0/me/subscribed_apps',
            params={
                'subscribed_fields': 'messages',
                'access_token': conn.access_token,
            },
            timeout=10,
        )
        data = resp.json()
        if resp.ok and data.get('success'):
            logger.info(f"Instagram webhook re-subscribed for @{conn.instagram_username}")
            return Response({'success': True})
        else:
            logger.warning(f"Instagram webhook subscription response: {data}")
            return Response({'success': False, 'error': str(data)}, status=status.HTTP_502_BAD_GATEWAY)
    except Exception as e:
        logger.error(f"Instagram webhook resubscription failed: {e}")
        return Response({'success': False, 'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)


@api_view(['POST'])
def send_instagram_message_from_comms(request):
    """Send an Instagram DM from the communications page."""
    lead_id = request.data.get('lead_id')
    message_text = request.data.get('message', '').strip()

    if not lead_id or not message_text:
        return Response({
            'success': False,
            'error': 'Lead ID and message are required'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        from .models import Lead, LeadActivity

        # Get the lead
        lead = Lead.objects.get(id=lead_id)

        if not lead.instagram_user_id:
            return Response({
                'success': False,
                'error': 'This lead does not have an Instagram user ID configured'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Send message
        result = instagram_service.send_message(lead.instagram_user_id, message_text)

        if not result:
            return Response({
                'success': False,
                'error': 'Failed to send message. Check Instagram configuration.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Log activity — echo_origin='crm' lets the webhook echo handler identify
        # this message ID as a CRM send, not a native Instagram app takeover.
        LeadActivity.objects.create(
            lead=lead,
            activity_type=LeadActivity.TYPE_INSTAGRAM_SENT,
            description=f"Sent Instagram message: {message_text[:100]}{'...' if len(message_text) > 100 else ''}",
            echo_origin=LeadActivity.ECHO_ORIGIN_CRM,
            metadata={
                'message_id': result.get('message_id'),
                'text': message_text,
                'echo_origin': LeadActivity.ECHO_ORIGIN_CRM,
                'is_manager_manual': True,
            }
        )

        return Response({
            'success': True,
            'message_id': result.get('message_id'),
        })

    except Lead.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Lead not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def send_whatsapp_message_from_comms(request):
    """Send a WhatsApp message from the communications page."""
    lead_id = request.data.get('lead_id')
    message_text = request.data.get('message', '').strip()

    if not lead_id or not message_text:
        return Response({
            'success': False,
            'error': 'Lead ID and message are required'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        from .models import Lead, LeadActivity

        # Get the lead
        lead = Lead.objects.get(id=lead_id)

        if not lead.whatsapp_phone:
            return Response({
                'success': False,
                'error': 'This lead does not have a WhatsApp phone number configured'
            }, status=status.HTTP_400_BAD_REQUEST)

        org = lead.organization

        if not whatsapp_service.is_configured(org=org):
            return Response({
                'success': False,
                'error': 'WhatsApp is not configured. Please connect your WhatsApp Business Account in Settings.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Send the message
        result = whatsapp_service.send_message(lead.whatsapp_phone, message_text, org=org, raise_exception=True)

        if not result:
            return Response({
                'success': False,
                'error': 'Failed to send message via WhatsApp'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Create activity record
        LeadActivity.objects.create(
            lead=lead,
            organization=org,
            activity_type=LeadActivity.TYPE_WHATSAPP_SENT,
            description=f'WhatsApp message sent: {message_text[:100]}{"..." if len(message_text) > 100 else ""}',
            metadata={
                'message_id': result.get('message_id'),
                'text': message_text,
                'is_manager_manual': True,
            }
        )

        logger.info(f"Sent WhatsApp message to lead {lead.id}")

        return Response({
            'success': True,
            'message_id': result.get('message_id'),
        })

    except Lead.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Lead not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error sending WhatsApp message: {e}", exc_info=True)
        return Response({
            'success': False,
            'error': f'Failed to send message: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# Customer Messaging Endpoints
# =============================================================================

@api_view(['POST'])
def send_telegram_to_customer(request):
    """Send a Telegram message to a customer."""
    customer_id = request.data.get('customer_id')
    message_text = request.data.get('message', '').strip()

    if not customer_id or not message_text:
        return Response({
            'success': False,
            'error': 'Customer ID and message are required'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        from .models import Customer, LeadActivity

        customer = Customer.objects.get(id=customer_id)

        if not customer.telegram_chat_id:
            return Response({
                'success': False,
                'error': 'This customer does not have a Telegram chat ID configured'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Send message using async
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            telegram_service.send_message(customer.telegram_chat_id, message_text)
        )
        loop.close()

        if not result:
            return Response({
                'success': False,
                'error': 'Failed to send message. Check bot configuration.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Log activity on the linked lead if exists
        if customer.lead:
            LeadActivity.objects.create(
                lead=customer.lead,
                activity_type=LeadActivity.TYPE_TELEGRAM_SENT,
                description=f"Sent Telegram message (as customer): {message_text[:100]}{'...' if len(message_text) > 100 else ''}",
                metadata={
                    'message_id': result.get('message_id'),
                    'text': message_text,
                    'customer_id': customer.id,
                }
            )

        return Response({
            'success': True,
            'message_id': result.get('message_id'),
        })

    except Customer.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Customer not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def send_instagram_to_customer(request):
    """Send an Instagram message to a customer."""
    customer_id = request.data.get('customer_id')
    message_text = request.data.get('message', '').strip()

    if not customer_id or not message_text:
        return Response({
            'success': False,
            'error': 'Customer ID and message are required'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        from .models import Customer, LeadActivity

        customer = Customer.objects.get(id=customer_id)

        if not customer.instagram_user_id:
            return Response({
                'success': False,
                'error': 'This customer does not have an Instagram user ID configured'
            }, status=status.HTTP_400_BAD_REQUEST)

        result = instagram_service.send_message(customer.instagram_user_id, message_text)

        if not result:
            return Response({
                'success': False,
                'error': 'Failed to send message. Check Instagram configuration.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Log activity on the linked lead if exists
        if customer.lead:
            LeadActivity.objects.create(
                lead=customer.lead,
                activity_type=LeadActivity.TYPE_INSTAGRAM_SENT,
                description=f"Sent Instagram message (as customer): {message_text[:100]}{'...' if len(message_text) > 100 else ''}",
                echo_origin=LeadActivity.ECHO_ORIGIN_CRM,
                metadata={
                    'message_id': result.get('message_id'),
                    'text': message_text,
                    'customer_id': customer.id,
                    'echo_origin': LeadActivity.ECHO_ORIGIN_CRM,
                }
            )

        return Response({
            'success': True,
            'message_id': result.get('message_id'),
        })

    except Customer.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Customer not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def send_whatsapp_to_customer(request):
    """Send a WhatsApp message to a customer."""
    customer_id = request.data.get('customer_id')
    message_text = request.data.get('message', '').strip()

    if not customer_id or not message_text:
        return Response({
            'success': False,
            'error': 'Customer ID and message are required'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        from .models import Customer, LeadActivity

        customer = Customer.objects.get(id=customer_id)

        if not customer.whatsapp_phone:
            return Response({
                'success': False,
                'error': 'This customer does not have a WhatsApp phone number configured'
            }, status=status.HTTP_400_BAD_REQUEST)

        org = customer.organization

        if not whatsapp_service.is_configured(org=org):
            return Response({
                'success': False,
                'error': 'WhatsApp is not configured. Please connect your WhatsApp Business Account in Settings.'
            }, status=status.HTTP_400_BAD_REQUEST)

        result = whatsapp_service.send_message(customer.whatsapp_phone, message_text, org=org, raise_exception=True)

        if not result:
            return Response({
                'success': False,
                'error': 'Failed to send message via WhatsApp'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Log activity on the linked lead if exists
        if customer.lead:
            LeadActivity.objects.create(
                lead=customer.lead,
                organization=org,
                activity_type=LeadActivity.TYPE_WHATSAPP_SENT,
                description=f"Sent WhatsApp message (as customer): {message_text[:100]}{'...' if len(message_text) > 100 else ''}",
                metadata={
                    'message_id': result.get('message_id'),
                    'text': message_text,
                    'customer_id': customer.id,
                }
            )

        return Response({
            'success': True,
            'message_id': result.get('message_id'),
        })

    except Customer.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Customer not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error sending WhatsApp message to customer: {e}", exc_info=True)
        return Response({
            'success': False,
            'error': f'Failed to send message: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# AI Agent Endpoints
# =============================================================================

@api_view(['POST'])
def run_agent_now(request):
    """Manually trigger the AI agent to check all leads (force mode - skips timing checks)."""
    from .agent_service import agent_service

    try:
        # Manual trigger uses force=True to skip inactivity threshold checks
        results = agent_service.run_agent_check(force=True)
        return Response({
            'success': True,
            'results': results
        })
    except Exception as e:
        logger.error(f"Error running agent: {e}", exc_info=True)
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# RingCentral Integration Endpoints
# =============================================================================

@api_view(['GET'])
def ringcentral_integration_status(request):
    """Return current RingCentral connection status and account details."""
    org = _get_org(request)
    if isinstance(org, _OrgNotSet):
        return Response({'connected': False})
    config = RingCentralConfig.get_config(org=org)
    if not config:
        return Response({'connected': False})

    account_info = None
    if ringcentral_service.is_configured():
        account_info = ringcentral_service.get_account_info()

    return Response({
        'connected': True,
        'account_phone': config.account_phone,
        'extension_id': config.extension_id,
        'has_webhook': bool(config.webhook_subscription_id),
        'account_info': account_info,
        'connected_at': config.connected_at.isoformat() if config.connected_at else None,
    })


@api_view(['POST'])
def save_ringcentral_credentials(request):
    """Save RingCentral credentials and test the connection."""
    client_id = request.data.get('client_id', '').strip()
    client_secret = request.data.get('client_secret', '').strip()
    jwt_token = request.data.get('jwt_token', '').strip()
    account_phone = request.data.get('account_phone', '').strip()
    extension_id = request.data.get('extension_id', '~').strip() or '~'

    if not all([client_id, client_secret, jwt_token, account_phone]):
        return Response({
            'success': False,
            'error': 'client_id, client_secret, jwt_token, and account_phone are required',
        }, status=status.HTTP_400_BAD_REQUEST)

    org = _get_org(request)
    if isinstance(org, _OrgNotSet):
        return Response({'success': False, 'error': 'No organization selected.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        config = RingCentralConfig.get_config(org=org)
        if config:
            # Delete old subscription before updating
            if config.webhook_subscription_id:
                ringcentral_service.delete_subscription(config.webhook_subscription_id)
            config.client_id = client_id
            config.client_secret = client_secret
            config.jwt_token = jwt_token
            config.account_phone = account_phone
            config.extension_id = extension_id
            config.webhook_subscription_id = ''
            config.save()
        else:
            config = RingCentralConfig.objects.create(
                organization=org,
                client_id=client_id,
                client_secret=client_secret,
                jwt_token=jwt_token,
                account_phone=account_phone,
                extension_id=extension_id,
            )

        # Reset cached token so it will re-authenticate
        ringcentral_service._access_token = None
        ringcentral_service._token_expires_at = 0

        # Test connection
        account_info = ringcentral_service.get_account_info()
        if not account_info:
            return Response({
                'success': False,
                'error': 'Could not connect to RingCentral. Please check your credentials.',
            }, status=status.HTTP_400_BAD_REQUEST)

        # Register webhook
        base_url = _get_webhook_base_url()
        if base_url:
            webhook_url = f'{base_url}/api/ringcentral-webhook/'
            ringcentral_service.subscribe_webhooks(webhook_url)

        return Response({
            'success': True,
            'account_info': account_info,
        })

    except Exception as e:
        logger.error(f'Error saving RingCentral credentials: {e}', exc_info=True)
        return Response({
            'success': False,
            'error': str(e),
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def disconnect_ringcentral(request):
    """Remove RingCentral credentials and cancel webhook subscription."""
    try:
        org = _get_org(request)
        if isinstance(org, _OrgNotSet):
            return Response({'success': True})
        config = RingCentralConfig.get_config(org=org)
        if config:
            if config.webhook_subscription_id:
                ringcentral_service.delete_subscription(config.webhook_subscription_id)
            config.delete()

        # Clear cached token
        ringcentral_service._access_token = None
        ringcentral_service._token_expires_at = 0

        return Response({'success': True})

    except Exception as e:
        logger.error(f'Error disconnecting RingCentral: {e}', exc_info=True)
        return Response({
            'success': False,
            'error': str(e),
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def reregister_ringcentral_webhook(request):
    """Cancel any existing webhook subscription and register a fresh one with the correct URL."""
    try:
        org = _get_org(request)
        if isinstance(org, _OrgNotSet):
            return Response({'success': False, 'error': 'RingCentral is not configured.'}, status=status.HTTP_400_BAD_REQUEST)
        config = RingCentralConfig.get_config(org=org)
        if not config:
            return Response({'success': False, 'error': 'RingCentral is not configured.'}, status=status.HTTP_400_BAD_REQUEST)

        # Cancel old subscription if present
        if config.webhook_subscription_id:
            ringcentral_service.delete_subscription(config.webhook_subscription_id)
            config.webhook_subscription_id = ''
            config.save(update_fields=['webhook_subscription_id'])

        # Re-subscribe with the correct URL
        base_url = _get_webhook_base_url()
        if not base_url:
            return Response({'success': False, 'error': 'Could not determine public webhook URL.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        webhook_url = f'{base_url}/api/ringcentral-webhook/'
        subscription_id = ringcentral_service.subscribe_webhooks(webhook_url)

        if subscription_id:
            return Response({'success': True, 'webhook_url': webhook_url})
        else:
            return Response({'success': False, 'error': 'Failed to register webhook with RingCentral.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    except Exception as e:
        logger.error(f'Error re-registering RingCentral webhook: {e}', exc_info=True)
        return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def send_ringcentral_sms_from_comms(request):
    """Send an SMS via RingCentral from the communications page."""
    from .models import Lead, LeadActivity

    lead_id = request.data.get('lead_id')
    message_text = request.data.get('message', '').strip()

    if not lead_id or not message_text:
        return Response({
            'success': False,
            'error': 'lead_id and message are required',
        }, status=status.HTTP_400_BAD_REQUEST)

    if not ringcentral_service.is_configured():
        return Response({
            'success': False,
            'error': 'RingCentral is not configured',
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        lead = Lead.objects.get(id=lead_id)
        to_phone = lead.phone or lead.mobile_phone or lead.office_phone
        if not to_phone:
            return Response({
                'success': False,
                'error': 'Lead has no phone number',
            }, status=status.HTTP_400_BAD_REQUEST)

        result = ringcentral_service.send_sms(to_phone, message_text)
        if not result:
            return Response({
                'success': False,
                'error': 'Failed to send SMS via RingCentral',
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        LeadActivity.objects.create(
            lead=lead,
            activity_type=LeadActivity.TYPE_RINGCENTRAL_SMS_SENT,
            description=f'Sent SMS: {message_text[:100]}{"..." if len(message_text) > 100 else ""}',
            metadata={
                'text': message_text,
                'to': to_phone,
                'message_id': str(result.get('id', '')),
            }
        )

        return Response({'success': True, 'message_id': str(result.get('id', ''))})

    except Lead.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Lead not found',
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f'Error sending RingCentral SMS: {e}', exc_info=True)
        return Response({
            'success': False,
            'error': str(e),
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def ringcentral_ringout(request):
    """Initiate a RingOut call to a lead via RingCentral."""
    from .models import Lead, LeadActivity

    lead_id = request.data.get('lead_id')

    if not lead_id:
        return Response({
            'success': False,
            'error': 'lead_id is required',
        }, status=status.HTTP_400_BAD_REQUEST)

    if not ringcentral_service.is_configured():
        return Response({
            'success': False,
            'error': 'RingCentral is not configured',
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        lead = Lead.objects.get(id=lead_id)
        to_phone = lead.phone or lead.mobile_phone or lead.office_phone
        if not to_phone:
            return Response({
                'success': False,
                'error': 'Lead has no phone number',
            }, status=status.HTTP_400_BAD_REQUEST)

        result = ringcentral_service.ringout(to_phone)
        if not result:
            return Response({
                'success': False,
                'error': 'Failed to initiate call via RingCentral',
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        LeadActivity.objects.create(
            lead=lead,
            activity_type=LeadActivity.TYPE_RINGCENTRAL_CALL_STARTED,
            description=f'Outbound call initiated to {to_phone}',
            metadata={
                'ringout_id': str(result.get('id', '')),
                'direction': 'outbound',
                'remote_phone': to_phone,
                'status': 'initiated',
            }
        )

        return Response({'success': True, 'ringout_id': str(result.get('id', ''))})

    except Lead.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Lead not found',
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f'Error initiating RingCentral RingOut: {e}', exc_info=True)
        return Response({
            'success': False,
            'error': str(e),
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
