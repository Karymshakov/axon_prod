"""
WhatsApp integration views — Meta Embedded Signup OAuth flow + status + disconnect.

Supports two OAuth paths that share the same backend token exchange:
  1. JS SDK Embedded Signup (preferred): FE calls window.FB.login(), gets a code,
     POSTs it to /callback/ → BE exchanges code → JSON response.
  2. Popup redirect (fallback): FE opens /authorize/ → Meta redirects to /callback/
     with ?code= → BE exchanges code → popup-close HTML response.

App credentials are read from WhatsAppAppConfig DB first, then env vars:
  INSTAGRAM_APP_ID      — defaults to the published app ID
  INSTAGRAM_APP_SECRET  — required (same Meta app as Instagram)

Endpoints:
  GET  integrations/whatsapp-oauth/authorize/   – redirect to Meta OAuth (popup fallback)
  POST integrations/whatsapp-oauth/callback/    – exchange code from JS SDK → JSON
  GET  integrations/whatsapp-oauth/callback/    – exchange code from popup redirect → HTML
  GET  integrations/whatsapp/status/            – current connection status
  POST integrations/whatsapp/disconnect/        – clear saved token
"""
import json
import logging
import os
import threading
import urllib.parse
from datetime import timedelta

import requests
from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import WhatsAppConfig, WhatsAppAppConfig

logger = logging.getLogger(__name__)


def _get_org(request):
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return None
    if getattr(user, 'is_superadmin', False):
        return None
    return getattr(user, 'current_organization', None)


def _org_guard(request, not_connected_response: dict):
    """
    Returns (org, error_response).
    If user is non-superadmin with no org, returns (None, Response(not_connected_response)).
    """
    from rest_framework.response import Response as R
    user = getattr(request, 'user', None)
    if user and user.is_authenticated and not getattr(user, 'is_superadmin', False):
        org = getattr(user, 'current_organization', None)
        if org is None:
            return None, R(not_connected_response)
        return org, None
    return None, None  # superadmin: proceed with None org

GRAPH_URL = 'https://graph.facebook.com/v21.0'
DEFAULT_APP_ID = ''
META_SCOPES = 'whatsapp_business_management,whatsapp_business_messaging'


def _get_app_id() -> str:
    app_config = WhatsAppAppConfig.get_config()
    if app_config and app_config.app_id:
        return app_config.app_id
    return os.environ.get('INSTAGRAM_APP_ID', DEFAULT_APP_ID)


def _get_app_secret() -> str:
    app_config = WhatsAppAppConfig.get_config()
    if app_config and app_config.app_secret:
        return app_config.app_secret
    return os.environ.get('INSTAGRAM_APP_SECRET', '') or os.environ.get('META_APP_SECRET', '')


def _get_redirect_uri() -> str:
    """Return the callback URI registered in Meta App Dashboard."""
    from .integration_views import _get_webhook_base_url
    return f'{_get_webhook_base_url()}/api/integrations/whatsapp-oauth/callback/'


def _popup_close_html(payload: dict) -> str:
    payload_json = json.dumps(payload)
    return f"""<!DOCTYPE html>
<html>
<head><title>WhatsApp</title></head>
<body>
<script>
  try {{
    if (window.opener) {{
      window.opener.postMessage({payload_json}, '*');
    }}
  }} catch(e) {{}}
  window.close();
</script>
<p>You can close this window.</p>
</body>
</html>"""


def _exchange_code(app_id: str, app_secret: str, code: str, redirect_uri: str = '') -> dict:
    """Exchange auth code for short-lived token, then upgrade to long-lived (60-day).

    redirect_uri must be empty string for codes obtained via the JS SDK Embedded
    Signup flow (FB.login), since the SDK does not use an explicit redirect URI.
    For the popup redirect flow it must match the registered callback URL.
    """
    post_data = {
        'client_id': app_id,
        'client_secret': app_secret,
        'grant_type': 'authorization_code',
        'code': code,
    }
    if redirect_uri:
        post_data['redirect_uri'] = redirect_uri
    resp = requests.post(
        f'{GRAPH_URL}/oauth/access_token',
        data=post_data,
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    short_token = data.get('access_token')
    if not short_token:
        raise ValueError(f"No access_token in response: {data}")

    # Exchange short-lived for long-lived (60-day) token
    ll_resp = requests.get(
        f'{GRAPH_URL}/oauth/access_token',
        params={
            'grant_type': 'fb_exchange_token',
            'client_id': app_id,
            'client_secret': app_secret,
            'fb_exchange_token': short_token,
        },
        timeout=15,
    )
    ll_resp.raise_for_status()
    ll_data = ll_resp.json()
    long_token = ll_data.get('access_token')
    expires_in = ll_data.get('expires_in', 5183944)  # ~60 days default

    if not long_token:
        # Some flows return a non-expiring system token — use short token directly
        long_token = short_token
        expires_in = None

    return {
        'access_token': long_token,
        'expiry': timezone.now() + timedelta(seconds=int(expires_in)) if expires_in else None,
    }


def _get_waba_and_phone(access_token: str) -> dict:
    """Discover WABA ID and first phone number from the access token."""
    resp = requests.get(
        f'{GRAPH_URL}/me/whatsapp_business_accounts',
        params={
            'fields': 'id,name,phone_numbers{id,display_phone_number,verified_name}',
            'access_token': access_token,
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    accounts = data.get('data', [])
    if not accounts:
        raise ValueError("No WhatsApp Business Accounts found for this token")

    waba = accounts[0]
    waba_id = waba.get('id', '')

    phones = waba.get('phone_numbers', {}).get('data', [])
    if not phones:
        # Try fetching phone numbers directly from WABA
        ph_resp = requests.get(
            f'{GRAPH_URL}/{waba_id}/phone_numbers',
            params={'fields': 'id,display_phone_number,verified_name', 'access_token': access_token},
            timeout=15,
        )
        ph_resp.raise_for_status()
        phones = ph_resp.json().get('data', [])

    if not phones:
        raise ValueError("No phone numbers found in WhatsApp Business Account")

    phone = phones[0]
    return {
        'waba_id': waba_id,
        'phone_number_id': phone.get('id', ''),
        'display_phone_number': phone.get('display_phone_number', ''),
        'verified_name': phone.get('verified_name', ''),
    }


def _auto_subscribe_webhook(config_id: int) -> None:
    """Background thread: subscribe the WABA to receive webhook events."""
    from django.db import close_old_connections
    close_old_connections()
    try:
        conn = WhatsAppConfig.objects.get(id=config_id)
        if not conn.waba_id:
            logger.warning("WhatsApp auto-subscribe: no WABA ID stored, skipping")
            return
        resp = requests.post(
            f'{GRAPH_URL}/{conn.waba_id}/subscribed_apps',
            params={'access_token': conn.access_token},
            timeout=10,
        )
        data = resp.json()
        if resp.ok and data.get('success'):
            WhatsAppConfig.objects.filter(id=config_id).update(webhook_subscribed=True)
            logger.info(f"Auto-subscribed WhatsApp webhook for WABA {conn.waba_id}")
        else:
            logger.warning(f"WhatsApp webhook subscription response: {data}")
    except Exception as e:
        logger.warning(f"WhatsApp auto-subscription failed: {e}")
    finally:
        close_old_connections()


@csrf_exempt
def whatsapp_authorize(request):
    """Redirect user's browser to Meta OAuth consent page.

    Plain Django view (no JWT) so it works inside a popup opened via window.open().
    """
    app_secret = _get_app_secret()
    if not app_secret:
        return HttpResponse(
            'Meta App Secret not configured. Set INSTAGRAM_APP_SECRET environment variable.',
            status=400,
        )

    params = {
        'client_id': _get_app_id(),
        'redirect_uri': _get_redirect_uri(),
        'scope': META_SCOPES,
        'response_type': 'code',
    }
    from django.shortcuts import redirect as django_redirect
    return django_redirect('https://www.facebook.com/dialog/oauth?' + urllib.parse.urlencode(params))


def _process_oauth_code(app_id: str, app_secret: str, code: str, redirect_uri: str = '') -> dict:
    """Exchange code, discover WABA + phone, persist to DB, start webhook subscription.

    Returns phone_data dict with display_phone_number and verified_name.
    Raises on any failure.
    """
    from django.http import JsonResponse as _JsonResponse  # noqa — only imported here
    token_data = _exchange_code(app_id, app_secret, code, redirect_uri)
    phone_data = _get_waba_and_phone(token_data['access_token'])

    conn = WhatsAppConfig.get_config()
    if conn:
        conn.access_token = token_data['access_token']
        conn.token_expires_at = token_data['expiry']
        conn.waba_id = phone_data['waba_id']
        conn.phone_number_id = phone_data['phone_number_id']
        conn.display_phone_number = phone_data['display_phone_number']
        conn.verified_name = phone_data['verified_name']
        conn.webhook_subscribed = False
        conn.save()
    else:
        conn = WhatsAppConfig.objects.create(
            access_token=token_data['access_token'],
            token_expires_at=token_data['expiry'],
            waba_id=phone_data['waba_id'],
            phone_number_id=phone_data['phone_number_id'],
            display_phone_number=phone_data['display_phone_number'],
            verified_name=phone_data['verified_name'],
        )

    logger.info(f"WhatsApp connected: {phone_data['display_phone_number']} (WABA {phone_data['waba_id']})")

    # Subscribe WABA to webhook events in background
    threading.Thread(target=_auto_subscribe_webhook, args=(conn.id,), daemon=True).start()

    return phone_data


@csrf_exempt
def whatsapp_callback(request):
    """Handle Meta OAuth code exchange — two modes:

    POST (Embedded Signup via FB JS SDK):
        Body: { "code": "..." }
        Response: JSON { success, display_phone_number, verified_name }
        Uses empty redirect_uri (FB.login does not redirect).

    GET (popup redirect fallback):
        Params: ?code=... (or ?error=...)
        Response: HTML that postMessages result and closes the popup.
    """
    from django.http import JsonResponse

    if request.method == 'POST':
        # ── JS SDK Embedded Signup path ──────────────────────────────────────
        try:
            body = json.loads(request.body or b'{}')
        except Exception:
            body = {}

        code = body.get('code', '').strip()
        if not code:
            return JsonResponse({'error': 'No authorization code provided'}, status=400)

        app_id = _get_app_id()
        app_secret = _get_app_secret()
        if not app_secret:
            return JsonResponse({'error': 'App Secret not configured. Add it in Settings → Integrations.'}, status=400)

        try:
            phone_data = _process_oauth_code(app_id, app_secret, code)
            return JsonResponse({
                'success': True,
                'display_phone_number': phone_data['display_phone_number'],
                'verified_name': phone_data['verified_name'],
            })
        except Exception as e:
            logger.error(f"WhatsApp Embedded Signup callback failed: {e}", exc_info=True)
            return JsonResponse({'error': str(e)}, status=400)

    # ── Popup redirect fallback (GET) ────────────────────────────────────────
    error = request.GET.get('error')
    if error:
        error_desc = request.GET.get('error_description', error)
        logger.warning(f"WhatsApp OAuth error: {error_desc}")
        return HttpResponse(_popup_close_html({'event': 'whatsapp_error', 'error': error_desc}))

    code = request.GET.get('code')
    if not code:
        return HttpResponse(_popup_close_html({
            'event': 'whatsapp_error',
            'error': 'No authorization code received',
        }))

    app_id = _get_app_id()
    app_secret = _get_app_secret()
    if not app_secret:
        return HttpResponse(_popup_close_html({
            'event': 'whatsapp_error',
            'error': 'App Secret not configured',
        }))

    try:
        phone_data = _process_oauth_code(app_id, app_secret, code, _get_redirect_uri())
        return HttpResponse(_popup_close_html({
            'event': 'whatsapp_connected',
            'display_phone_number': phone_data['display_phone_number'],
            'verified_name': phone_data['verified_name'],
        }))
    except Exception as e:
        logger.error(f"WhatsApp OAuth popup callback failed: {e}", exc_info=True)
        return HttpResponse(_popup_close_html({
            'event': 'whatsapp_error',
            'error': str(e),
        }))


@api_view(['GET'])
def whatsapp_status(request):
    """Return current WhatsApp connection status.

    Side-effect: if webhook not yet subscribed and WABA ID is known,
    fires background subscription attempt.
    """
    import os as _os
    org, err = _org_guard(request, {'connected': False})
    if err is not None:
        return err
    app_config = WhatsAppAppConfig.get_config(org=org)
    app_id = app_config.app_id if app_config and app_config.app_id else DEFAULT_APP_ID
    app_secret_set = bool(app_config and app_config.app_secret)

    # Build webhook URL from domain env vars
    from .integration_views import _get_webhook_base_url
    base_url = _get_webhook_base_url()
    webhook_url = f'{base_url}/api/whatsapp-webhook/'

    conn = WhatsAppConfig.get_config(org=org)
    if not conn:
        return Response({
            'connected': False,
            'app_id': app_id,
            'app_secret_set': app_secret_set,
            'webhook_url': webhook_url,
        })

    # Auto-subscribe webhook in background if not yet done
    if not conn.webhook_subscribed and conn.waba_id and conn.access_token:
        threading.Thread(
            target=_auto_subscribe_webhook,
            args=(conn.id,),
            daemon=True,
        ).start()

    return Response({
        'connected': True,
        'phone_number_id': conn.phone_number_id,
        'display_phone_number': conn.display_phone_number,
        'verified_name': conn.verified_name,
        'waba_id': conn.waba_id,
        'token_expired': conn.is_token_expired,
        'token_expiring_soon': conn.is_expiring_soon,
        'token_expires_at': conn.token_expires_at.isoformat() if conn.token_expires_at else None,
        'webhook_subscribed': conn.webhook_subscribed,
        'connected_at': conn.connected_at.isoformat() if conn.connected_at else None,
        'app_id': app_id,
        'app_secret_set': app_secret_set,
        'verify_token': conn.verify_token or '',
        'webhook_url': webhook_url,
    })


@api_view(['POST'])
def resubscribe_whatsapp_webhook(request):
    """Subscribe (or re-subscribe) the WABA to receive webhook events.

    Clears webhook_subscribed flag and re-calls the Meta subscribed_apps endpoint.
    Safe to call multiple times — Meta accepts duplicate subscriptions.
    """
    org, err = _org_guard(request, {'success': False, 'error': 'WhatsApp not connected or missing WABA ID'})
    if err is not None:
        return err
    conn = WhatsAppConfig.get_config(org=org)
    if not conn or not conn.access_token or not conn.waba_id:
        return Response({'success': False, 'error': 'WhatsApp not connected or missing WABA ID'}, status=400)

    try:
        resp = requests.post(
            f'{GRAPH_URL}/{conn.waba_id}/subscribed_apps',
            params={'access_token': conn.access_token},
            timeout=10,
        )
        data = resp.json()
        if resp.ok and data.get('success'):
            WhatsAppConfig.objects.filter(id=conn.id).update(webhook_subscribed=True)
            logger.info(f"WhatsApp webhook re-subscribed for WABA {conn.waba_id}")
            return Response({'success': True, 'waba_id': conn.waba_id})
        else:
            logger.warning(f"WhatsApp webhook resubscription response: {data}")
            return Response({'success': False, 'error': str(data)}, status=502)
    except Exception as e:
        logger.error(f"WhatsApp webhook resubscription failed: {e}")
        return Response({'success': False, 'error': str(e)}, status=502)


@api_view(['POST'])
def whatsapp_disconnect(request):
    """Delete the WhatsApp connection record."""
    org, err = _org_guard(request, {'status': 'disconnected'})
    if err is not None:
        return err
    conn = WhatsAppConfig.get_config(org=org)
    if conn:
        conn.delete()
    return Response({'status': 'disconnected'})
