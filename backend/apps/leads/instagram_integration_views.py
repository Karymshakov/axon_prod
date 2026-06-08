"""
Instagram integration views — OAuth flow + status + disconnect + token refresh.

Uses the Instagram Login API (instagram.com/oauth/authorize).
App ID and Secret are read from environment variables:
  INSTAGRAM_APP_ID      — defaults to the published app ID
  INSTAGRAM_APP_SECRET  — required

Endpoints (all under /api/integrations/instagram/):
  GET  status/          – current connection status
  GET  authorize/       – redirect to Meta OAuth (plain view, no JWT required)
  GET  callback/        – exchange code, store token, close popup (plain view)
  POST disconnect/      – remove token from DB
  POST refresh-token/   – exchange current token for a new 60-day token
"""
import json
import logging
import os
import threading
import urllib.parse
from datetime import timedelta
from urllib.parse import urlparse

import requests
from django.core.cache import cache
from django.core import signing
from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import InstagramAppConfig, InstagramConnection


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

logger = logging.getLogger(__name__)

INSTAGRAM_AUTH_URL = 'https://www.instagram.com/oauth/authorize'
INSTAGRAM_TOKEN_URL = 'https://api.instagram.com/oauth/access_token'
INSTAGRAM_GRAPH_URL = 'https://graph.instagram.com'

OAUTH_SCOPES = [
    'instagram_business_basic',
    'instagram_business_manage_messages',
    'instagram_business_manage_comments',
    'instagram_business_content_publish',
    'instagram_business_manage_insights',
]

OAUTH_STATE_SALT = 'instagram-oauth-state'
INSTAGRAM_CALLBACK_PATHS = (
    '/api/integrations/instagram/callback/',
    '/api/integrations/instagram-oauth/callback/',
)


class InstagramOAuthUserError(Exception):
    """Exception whose message is safe to show directly in the UI."""


def _normalize_callback_uri(uri: str) -> str:
    parsed = urlparse(uri.strip())
    path = parsed.path.rstrip('/') + '/'
    return parsed._replace(path=path, params='', query='', fragment='').geturl()


def _current_callback_uri() -> str:
    from .integration_views import _get_webhook_base_url

    return f'{_get_webhook_base_url()}{INSTAGRAM_CALLBACK_PATHS[0]}'


def _callback_uri_diagnostics() -> dict:
    configured = os.environ.get('INSTAGRAM_CALLBACK_URL', '').strip()
    current = _current_callback_uri()

    if not configured:
        return {
            'redirect_uri': current,
            'configured_redirect_uri': '',
            'callback_warning': '',
            'using_fallback': True,
        }

    normalized_configured = _normalize_callback_uri(configured)
    parsed_configured = urlparse(normalized_configured)
    parsed_current = urlparse(current)

    host_matches = (
        parsed_configured.scheme == parsed_current.scheme
        and parsed_configured.netloc == parsed_current.netloc
    )
    path_matches = parsed_configured.path in INSTAGRAM_CALLBACK_PATHS
    callback_warning = ''
    redirect_uri = normalized_configured

    if not host_matches:
        callback_warning = (
            'Instagram is configured to return to a different web address than this workspace. '
            'The authorization can finish in Meta but never return here, so the connection stays incomplete.'
        )
        redirect_uri = current
    elif not path_matches:
        callback_warning = (
            'Instagram is configured with a callback path this workspace does not handle. '
            'Update the callback URL to the standard Instagram callback for this workspace.'
        )
        redirect_uri = current

    return {
        'redirect_uri': redirect_uri,
        'configured_redirect_uri': normalized_configured,
        'callback_warning': callback_warning,
        'using_fallback': redirect_uri != normalized_configured,
    }


def _record_oauth_diagnostics(org, **updates):
    if org is None:
        return

    cache_key = f'instagram_oauth_diag:{org.pk}'
    diagnostics = cache.get(cache_key, {})
    diagnostics.update(updates)
    cache.set(cache_key, diagnostics, timeout=60 * 60 * 24)


def _read_oauth_diagnostics(org) -> dict:
    if org is None or not hasattr(org, 'pk'):
        return {}
    return cache.get(f'instagram_oauth_diag:{org.pk}', {}) or {}


def _extract_error_message(response: requests.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        text = response.text.strip()
        return text[:400] if text else f'HTTP {response.status_code}'

    error = data.get('error') if isinstance(data, dict) else None
    if isinstance(error, dict):
        return str(error.get('error_user_msg') or error.get('message') or data)
    if isinstance(data, dict):
        return str(data.get('error_message') or data.get('message') or data)
    return str(data)


def _friendly_oauth_error(detail: str) -> str:
    message = (detail or '').strip()
    lower = message.lower()

    if 'redirect_uri' in lower:
        return (
            'Instagram is redirecting to a different callback address than this workspace expects. '
            'Update the Instagram callback URL in Meta to exactly match this workspace and try again.'
        )
    if 'invalid scope' in lower or 'permission' in lower or 'permissions' in lower:
        return (
            'Meta rejected one or more requested Instagram permissions. Confirm the app has Instagram messaging permissions approved and that the account is allowed to use them.'
        )
    if 'app not set up' in lower or 'app isn' in lower or 'app is not active' in lower:
        return (
            'This Meta app is not allowed to complete Instagram login for this account yet. Put the app in Live mode or add this Instagram/Facebook user as a tester before reconnecting.'
        )
    if 'business' in lower and 'account' in lower:
        return (
            'This Instagram account is not eligible for messaging access. Use a Business or Creator account that is linked to a Facebook Page, then try again.'
        )
    if 'page' in lower and ('link' in lower or 'linked' in lower or 'connect' in lower):
        return (
            'Instagram login completed, but the account is not linked to a Facebook Page. Link the Instagram account to a Facebook Page, then reconnect.'
        )
    if 'code' in lower and ('expired' in lower or 'invalid' in lower):
        return 'Instagram authorization expired before it could be saved. Start the connection again and complete it in one session.'
    if 'unsupported request' in lower:
        return (
            'Meta accepted the login but rejected the account for API access. Check that Instagram messaging is enabled for the app and that the connected account meets Meta eligibility requirements.'
        )
    return message or 'Instagram authorization failed before the account could be saved.'


def _raise_for_instagram_response(response: requests.Response, default_message: str) -> None:
    if response.ok:
        return
    detail = _extract_error_message(response) or default_message
    raise InstagramOAuthUserError(_friendly_oauth_error(detail))


def _get_app_config(org=None):
    return InstagramAppConfig.get_config(org=org)


def _get_app_id(org=None) -> str:
    app_config = _get_app_config(org=org)
    val = (app_config.app_id if app_config and app_config.app_id else os.environ.get('INSTAGRAM_APP_ID', '')).strip()
    if not val:
        raise ValueError('INSTAGRAM_APP_ID environment variable is required')
    return val


def _get_app_secret(org=None) -> str:
    app_config = _get_app_config(org=org)
    val = (
        app_config.app_secret
        if app_config and app_config.app_secret
        else os.environ.get('INSTAGRAM_APP_SECRET', '')
    ).strip()
    if not val:
        raise ValueError('INSTAGRAM_APP_SECRET environment variable is required')
    return val


def _get_redirect_uri() -> str:
    return _callback_uri_diagnostics()['redirect_uri']


def _build_oauth_state(org) -> str:
    payload = {}
    if org is not None and hasattr(org, 'pk'):
        payload['org_id'] = org.pk
    return signing.dumps(payload, salt=OAUTH_STATE_SALT) if payload else ''


def _resolve_org_from_state(state: str):
    if not state:
        return None, False

    try:
        payload = signing.loads(state, salt=OAUTH_STATE_SALT, max_age=3600)
    except signing.BadSignature:
        logger.warning('Instagram OAuth callback received invalid state')
        return None, True

    org_id = payload.get('org_id')
    if not org_id:
        return None, True

    from apps.organizations.models import Organization

    return Organization.objects.filter(id=org_id).first(), True


def _popup_close_html(payload: dict) -> str:
    safe_payload = {**payload, 'created_at': int(timezone.now().timestamp() * 1000)}
    payload_json = json.dumps(safe_payload)
    return f"""<!DOCTYPE html>
<html>
<head><title>Instagram</title></head>
<body>
<script>
  try {{
    try {{
      window.localStorage.setItem('cayu.instagram.oauth.result', JSON.stringify({payload_json}));
    }} catch (storageError) {{}}
    if (window.opener) {{
      window.opener.postMessage({payload_json}, '*');
    }}
  }} catch(e) {{}}
  window.close();
</script>
<p>You can close this window.</p>
</body>
</html>"""


def _exchange_code(app_id: str, app_secret: str, code: str, redirect_uri: str) -> dict:
    """
    Exchange auth code for short-lived token, then upgrade to long-lived (60-day).

    Step 1: POST api.instagram.com/oauth/access_token  → short-lived token
    Step 2: GET  graph.instagram.com/access_token?grant_type=ig_exchange_token → long-lived
    """
    resp = requests.post(
        INSTAGRAM_TOKEN_URL,
        data={
            'client_id': app_id,
            'client_secret': app_secret,
            'grant_type': 'authorization_code',
            'redirect_uri': redirect_uri,
            'code': code,
        },
        timeout=15,
    )
    _raise_for_instagram_response(resp, 'Instagram token exchange failed.')
    short_data = resp.json()
    short_token = short_data.get('access_token')
    if not short_token:
        raise ValueError(f"No access_token in token response: {short_data}")

    ll_resp = requests.get(
        f'{INSTAGRAM_GRAPH_URL}/access_token',
        params={
            'grant_type': 'ig_exchange_token',
            'client_id': app_id,
            'client_secret': app_secret,
            'access_token': short_token,
        },
        timeout=15,
    )
    _raise_for_instagram_response(ll_resp, 'Instagram long-lived token exchange failed.')
    ll_data = ll_resp.json()
    long_token = ll_data.get('access_token')
    expires_in = ll_data.get('expires_in', 5183944)  # ~60 days
    if not long_token:
        raise ValueError(f"No long-lived token in response: {ll_data}")

    return {
        'access_token': long_token,
        'expiry': timezone.now() + timedelta(seconds=int(expires_in)),
    }


def _fetch_profile(access_token: str) -> dict:
    """Fetch Instagram user profile from graph.instagram.com/me."""
    resp = requests.get(
        f'{INSTAGRAM_GRAPH_URL}/me',
        params={
            'fields': 'id,username,profile_picture_url,account_type',
            'access_token': access_token,
        },
        timeout=15,
    )
    _raise_for_instagram_response(resp, 'Instagram profile lookup failed.')
    data = resp.json()
    user_id = data.get('id')
    if not user_id:
        raise ValueError(f"No user id in profile response: {data}")
    return {
        'instagram_user_id': user_id,
        'instagram_username': data.get('username', ''),
        'profile_picture_url': data.get('profile_picture_url', ''),
        'account_type': data.get('account_type', ''),
    }


# ─────────────────────────────────────────────────────────────────────────────
# API views
# ─────────────────────────────────────────────────────────────────────────────

def _auto_subscribe_webhook(conn_id: int) -> None:
    """Background thread: subscribe the connected Instagram account to receive webhook events.

    Idempotent — safe to call multiple times. Sets webhook_subscribed=True on success.
    """
    from django.db import close_old_connections
    close_old_connections()
    try:
        conn = InstagramConnection.objects.get(id=conn_id)
        resp = requests.post(
            f'{INSTAGRAM_GRAPH_URL}/v21.0/me/subscribed_apps',
            params={
                'subscribed_fields': 'messages',
                'access_token': conn.access_token,
            },
            timeout=10,
        )
        data = resp.json()
        if resp.ok and data.get('success'):
            InstagramConnection.objects.filter(id=conn_id).update(webhook_subscribed=True)
            logger.info(f"Auto-subscribed Instagram webhook for @{conn.instagram_username}")
        else:
            logger.warning(f"Instagram auto-subscription response: {data}")
    except Exception as e:
        logger.warning(f"Instagram auto-subscription failed: {e}")
    finally:
        close_old_connections()


def _auto_refresh_token(conn_id: int) -> None:
    """Background thread: refresh the long-lived token when it is close to expiry."""
    from django.db import close_old_connections
    close_old_connections()
    try:
        conn = InstagramConnection.objects.get(id=conn_id)
        resp = requests.get(
            f'{INSTAGRAM_GRAPH_URL}/refresh_access_token',
            params={
                'grant_type': 'ig_refresh_token',
                'access_token': conn.access_token,
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        new_token = data.get('access_token')
        expires_in = data.get('expires_in', 5183944)
        if new_token:
            new_expiry = timezone.now() + timedelta(seconds=int(expires_in))
            # Reset webhook_subscribed so the next status poll re-subscribes with the new token.
            # Meta requires a fresh /me/subscribed_apps call after a token rotation.
            InstagramConnection.objects.filter(id=conn_id).update(
                access_token=new_token,
                token_expiry=new_expiry,
                webhook_subscribed=False,
            )
            logger.info(f"Auto-refreshed Instagram token for @{conn.instagram_username} (new expiry: {new_expiry.date()})")
            # Re-subscribe immediately using the new token rather than waiting for next status poll.
            _auto_subscribe_webhook(conn_id)
        else:
            logger.warning(f"Instagram auto-refresh: no token in response: {data}")
    except Exception as e:
        logger.warning(f"Instagram auto-refresh failed: {e}")
    finally:
        close_old_connections()


@api_view(['GET'])
def instagram_status(request):
    """Return current Instagram connection status plus app config info.

    Side-effects (non-blocking, background threads):
    - If webhook not yet subscribed: fires POST /me/subscribed_apps automatically.
    - If token expiring within 14 days: fires token refresh automatically.
    """
    from .integration_views import _get_webhook_base_url
    base_url = _get_webhook_base_url()
    webhook_url = f"{base_url}/api/integrations/instagram/webhook/"
    callback_info = _callback_uri_diagnostics()
    org, err = _org_guard(request, {'connected': False, 'webhook_url': webhook_url})
    if err is not None:
        return err
    embed_url = '/api/integrations/instagram/authorize/'
    oauth_state = _build_oauth_state(org)
    if oauth_state:
        embed_url = f'{embed_url}?state={urllib.parse.quote(oauth_state)}'
    diagnostics = _read_oauth_diagnostics(org)
    conn = InstagramConnection.get_config(org=org)
    if not conn:
        return Response({
            'connected': False,
            'webhook_url': webhook_url,
            'embed_url': embed_url,
            'callback_url': callback_info['redirect_uri'],
            'callback_warning': callback_info['callback_warning'],
            'configured_callback_url': callback_info['configured_redirect_uri'],
            'oauth_last_started_at': diagnostics.get('oauth_last_started_at'),
            'oauth_last_callback_at': diagnostics.get('oauth_last_callback_at'),
            'oauth_last_status': diagnostics.get('oauth_last_status', ''),
            'oauth_last_error': diagnostics.get('oauth_last_error', ''),
        })

    # Auto-subscribe webhook in the background if not yet done.
    if not conn.webhook_subscribed and conn.access_token and not conn.is_token_expired:
        threading.Thread(
            target=_auto_subscribe_webhook,
            args=(conn.id,),
            daemon=True,
        ).start()

    # Auto-refresh token in the background when within 14 days of expiry.
    if conn.is_expiring_soon and not conn.is_token_expired:
        threading.Thread(
            target=_auto_refresh_token,
            args=(conn.id,),
            daemon=True,
        ).start()

    return Response({
        'connected': True,
        'instagram_username': conn.instagram_username,
        'profile_picture_url': conn.profile_picture_url,
        'token_expired': conn.is_token_expired,
        'token_expiring_soon': conn.is_expiring_soon,
        'token_expiry': conn.token_expiry.isoformat() if conn.token_expiry else None,
        'connected_at': conn.connected_at.isoformat() if conn.connected_at else None,
        'webhook_url': webhook_url,
        'embed_url': embed_url,
        'callback_url': callback_info['redirect_uri'],
        'callback_warning': callback_info['callback_warning'],
        'configured_callback_url': callback_info['configured_redirect_uri'],
        'oauth_last_started_at': diagnostics.get('oauth_last_started_at'),
        'oauth_last_callback_at': diagnostics.get('oauth_last_callback_at'),
        'oauth_last_status': diagnostics.get('oauth_last_status', ''),
        'oauth_last_error': diagnostics.get('oauth_last_error', ''),
    })


@csrf_exempt
def instagram_authorize(request):
    """Redirect user's browser to Instagram OAuth consent page.

    Plain Django view (no JWT) so it works inside a popup opened via window.open().
    """
    oauth_state = request.GET.get('state', '').strip()
    state_org = None
    if oauth_state:
        state_org, state_valid = _resolve_org_from_state(oauth_state)
        if not state_valid or state_org is None:
            return HttpResponse(
                'This Instagram connection request expired or is missing its workspace. Please close this window and start again from Integrations.',
                status=400,
            )

    try:
        _get_app_secret(org=state_org)
    except ValueError:
        return HttpResponse(
            'Instagram App Secret is not configured. Add your Meta app credentials in Settings before reconnecting Instagram.',
            status=400,
        )

    callback_info = _callback_uri_diagnostics()
    redirect_uri = callback_info['redirect_uri']
    _record_oauth_diagnostics(
        state_org,
        oauth_last_started_at=timezone.now().isoformat(),
        oauth_last_status='pending',
        oauth_last_error=callback_info['callback_warning'] if callback_info['callback_warning'] else '',
        oauth_last_redirect_uri=redirect_uri,
    )
    if callback_info['callback_warning']:
        logger.warning('Instagram OAuth callback URI mismatch detected: %s', callback_info['callback_warning'])
    params = {
        'client_id': _get_app_id(org=state_org),
        'redirect_uri': redirect_uri,
        'scope': ','.join(OAUTH_SCOPES),
        'response_type': 'code',
        'force_reauth': 'true',
    }
    if oauth_state:
        params['state'] = oauth_state
    from django.shortcuts import redirect as django_redirect
    return django_redirect(INSTAGRAM_AUTH_URL + '?' + urllib.parse.urlencode(params))


@csrf_exempt
def instagram_callback(request):
    """Handle Meta OAuth redirect — exchange code, store token, close popup.

    Plain Django view (no JWT). Returns HTML that posts a message to opener.
    """
    error = request.GET.get('error')
    oauth_state = request.GET.get('state', '').strip()
    org, state_valid = _resolve_org_from_state(oauth_state)
    if org is not None:
        _record_oauth_diagnostics(
            org,
            oauth_last_callback_at=timezone.now().isoformat(),
        )

    if error:
        error_desc = request.GET.get('error_description', error)
        friendly_error = _friendly_oauth_error(error_desc)
        logger.warning(f"Instagram OAuth error: {error_desc}")
        _record_oauth_diagnostics(
            org,
            oauth_last_status='error',
            oauth_last_error=friendly_error,
        )
        return HttpResponse(_popup_close_html({'event': 'instagram_error', 'error': friendly_error}))

    code = request.GET.get('code')
    if not code:
        return HttpResponse(_popup_close_html({
            'event': 'instagram_error',
            'error': 'No authorization code received',
        }))

    if not state_valid or org is None:
        return HttpResponse(_popup_close_html({
            'event': 'instagram_error',
            'error': 'Instagram authorization finished, but the CRM could not match it to your current workspace. Please reconnect from the Integrations page and try again.',
        }))

    app_id = _get_app_id(org=org)
    app_secret = _get_app_secret(org=org)
    if not app_secret:
        return HttpResponse(_popup_close_html({
            'event': 'instagram_error',
            'error': 'App Secret not configured',
        }))

    try:
        redirect_uri = _get_redirect_uri()
        token_data = _exchange_code(app_id, app_secret, code, redirect_uri)
        profile = _fetch_profile(token_data['access_token'])

        conn = InstagramConnection.get_config(org=org)
        if conn:
            conn.access_token = token_data['access_token']
            conn.token_expiry = token_data['expiry']
            conn.instagram_user_id = profile['instagram_user_id']
            conn.instagram_username = profile['instagram_username']
            conn.profile_picture_url = profile['profile_picture_url']
            conn.connected_at = timezone.now()
            conn.webhook_subscribed = False  # Will be set True after subscription below
            conn.save()
        else:
            InstagramConnection.objects.create(
                organization=org,
                access_token=token_data['access_token'],
                token_expiry=token_data['expiry'],
                instagram_user_id=profile['instagram_user_id'],
                instagram_username=profile['instagram_username'],
                profile_picture_url=profile['profile_picture_url'],
                connected_at=timezone.now(),
            )

        _record_oauth_diagnostics(
            org,
            oauth_last_status='success',
            oauth_last_error='',
            oauth_last_redirect_uri=redirect_uri,
        )

        logger.info(f"Instagram connected: @{profile['instagram_username']} ({profile['instagram_user_id']})")

        # Subscribe this Instagram account to receive webhook messages.
        # Without this step the app-level webhook URL is configured but Meta
        # never delivers DMs for the connected account.
        try:
            sub_resp = requests.post(
                f'{INSTAGRAM_GRAPH_URL}/v21.0/me/subscribed_apps',
                params={
                    'subscribed_fields': 'messages',
                    'access_token': token_data['access_token'],
                },
                timeout=10,
            )
            sub_data = sub_resp.json()
            if sub_resp.ok and sub_data.get('success'):
                InstagramConnection.objects.filter(
                    instagram_user_id=profile['instagram_user_id']
                ).update(webhook_subscribed=True)
                logger.info(f"Instagram webhook subscription activated for @{profile['instagram_username']}")
            else:
                friendly_sub_error = _friendly_oauth_error(_extract_error_message(sub_resp))
                _record_oauth_diagnostics(
                    org,
                    oauth_last_status='error',
                    oauth_last_error=friendly_sub_error,
                )
                logger.warning(f"Instagram webhook subscription response: {sub_data}")
        except Exception as sub_e:
            logger.warning(f"Instagram webhook subscription call failed: {sub_e}")

        return HttpResponse(_popup_close_html({
            'event': 'instagram_connected',
            'instagram_username': profile['instagram_username'],
            'profile_picture_url': profile['profile_picture_url'],
        }))

    except Exception as e:
        user_message = str(e) if isinstance(e, InstagramOAuthUserError) else _friendly_oauth_error(str(e))
        _record_oauth_diagnostics(
            org,
            oauth_last_status='error',
            oauth_last_error=user_message,
        )
        logger.error(f"Instagram OAuth callback failed: {e}", exc_info=True)
        return HttpResponse(_popup_close_html({
            'event': 'instagram_error',
            'error': user_message,
        }))


@api_view(['POST'])
def instagram_disconnect(request):
    """Unsubscribe webhook on Meta's side, then wipe the connection record."""
    org, err = _org_guard(request, {'status': 'disconnected'})
    if err is not None:
        return err
    conn = InstagramConnection.get_config(org=org)
    if conn:
        # Step 1: Tell Meta to stop delivering webhook events for this account.
        # We do this before wiping the token so we still have valid credentials.
        # Errors here are non-fatal — the record is deleted regardless so future
        # webhooks will be rejected by the connection-state guard in the handler.
        if conn.access_token and not conn.is_token_expired:
            try:
                resp = requests.delete(
                    f'{INSTAGRAM_GRAPH_URL}/v21.0/me/subscribed_apps',
                    params={'access_token': conn.access_token},
                    timeout=10,
                )
                if resp.ok:
                    logger.info(
                        f"Instagram webhook unsubscribed for @{conn.instagram_username} "
                        f"(account {conn.instagram_user_id})"
                    )
                else:
                    logger.warning(
                        f"Instagram webhook unsubscribe returned {resp.status_code}: {resp.text[:200]}"
                    )
            except Exception as e:
                logger.warning(f"Instagram webhook unsubscribe request failed: {e}")
        else:
            logger.info(
                f"Instagram disconnect: skipping Meta unsubscribe (token expired or missing) "
                f"for @{conn.instagram_username}"
            )

        # Step 2: Hard-delete the connection record — wipes access_token,
        # instagram_user_id, instagram_username, and all other identifying fields.
        conn.delete()

    return Response({'status': 'disconnected'})


@api_view(['POST'])
def instagram_refresh_token(request):
    """Refresh the long-lived Instagram token (valid within 60 days of issue)."""
    org, err = _org_guard(request, {'error': 'Not connected'})
    if err is not None:
        return err
    conn = InstagramConnection.get_config(org=org)
    if not conn or not conn.access_token:
        return Response({'error': 'Not connected'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        resp = requests.get(
            f'{INSTAGRAM_GRAPH_URL}/refresh_access_token',
            params={
                'grant_type': 'ig_refresh_token',
                'access_token': conn.access_token,
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        new_token = data.get('access_token')
        expires_in = data.get('expires_in', 5183944)
        if not new_token:
            return Response({'error': 'No token returned'}, status=status.HTTP_502_BAD_GATEWAY)

        conn.access_token = new_token
        conn.token_expiry = timezone.now() + timedelta(seconds=int(expires_in))
        # Reset so the status poll re-subscribes with the refreshed token.
        conn.webhook_subscribed = False
        conn.save()

        # Re-subscribe in background immediately — don't make the user wait for next status poll.
        threading.Thread(
            target=_auto_subscribe_webhook,
            args=(conn.id,),
            daemon=True,
        ).start()

        return Response({
            'status': 'refreshed',
            'token_expiry': conn.token_expiry.isoformat(),
        })
    except Exception as e:
        logger.error(f"Instagram token refresh failed: {e}")
        return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)
