import base64
import logging
import time
import requests
from typing import Optional

logger = logging.getLogger(__name__)

RC_BASE = 'https://platform.ringcentral.com'
RC_TOKEN_URL = f'{RC_BASE}/restapi/oauth/token'


class RingCentralService:
    """Service for RingCentral API calls using JWT authentication."""

    def __init__(self):
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0

    def _get_config(self):
        from .models import RingCentralConfig
        return RingCentralConfig.get_config()

    def is_configured(self) -> bool:
        config = self._get_config()
        return bool(config and config.client_id and config.client_secret and config.jwt_token)

    def get_access_token(self) -> Optional[str]:
        """
        Exchange JWT for a short-lived access token (valid ~60 min).
        Caches the token in memory and refreshes when expired.
        """
        if self._access_token and time.time() < self._token_expires_at - 60:
            return self._access_token

        config = self._get_config()
        if not config:
            return None

        # Basic auth header: base64(client_id:client_secret)
        credentials = f'{config.client_id}:{config.client_secret}'
        auth_header = base64.b64encode(credentials.encode()).decode()

        try:
            response = requests.post(
                RC_TOKEN_URL,
                headers={
                    'Authorization': f'Basic {auth_header}',
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                data={
                    'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
                    'assertion': config.jwt_token,
                },
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            self._access_token = data['access_token']
            self._token_expires_at = time.time() + data.get('expires_in', 3600)
            logger.info('RingCentral access token refreshed successfully')
            return self._access_token
        except Exception as e:
            logger.error(f'RingCentral token exchange failed: {e}')
            self._access_token = None
            return None

    def _auth_headers(self) -> dict:
        token = self.get_access_token()
        return {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'} if token else {}

    def get_account_info(self) -> Optional[dict]:
        """Verify credentials by fetching account info."""
        try:
            response = requests.get(
                f'{RC_BASE}/restapi/v1.0/account/~',
                headers=self._auth_headers(),
                timeout=10,
            )
            if response.ok:
                return response.json()
            logger.error(f'RingCentral account info failed: {response.status_code} {response.text}')
            return None
        except Exception as e:
            logger.error(f'RingCentral account info error: {e}')
            return None

    def send_sms(self, to_phone: str, text: str) -> Optional[dict]:
        """Send an SMS from the configured account phone number."""
        config = self._get_config()
        if not config:
            return None

        ext = config.extension_id or '~'
        try:
            response = requests.post(
                f'{RC_BASE}/restapi/v1.0/account/~/extension/{ext}/sms',
                headers=self._auth_headers(),
                json={
                    'from': {'phoneNumber': config.account_phone},
                    'to': [{'phoneNumber': to_phone}],
                    'text': text,
                },
                timeout=15,
            )
            if response.ok:
                data = response.json()
                logger.info(f'RingCentral SMS sent to {to_phone}, id={data.get("id")}')
                return data
            logger.error(f'RingCentral SMS failed: {response.status_code} {response.text}')
            return None
        except Exception as e:
            logger.error(f'RingCentral SMS error: {e}')
            return None

    def ringout(self, to_phone: str, caller_id: str = None) -> Optional[dict]:
        """
        Initiate a RingOut call: RingCentral calls the agent's phone first,
        then connects to the lead when they answer.
        """
        config = self._get_config()
        if not config:
            return None

        ext = config.extension_id or '~'
        from_phone = caller_id or config.account_phone
        try:
            response = requests.post(
                f'{RC_BASE}/restapi/v1.0/account/~/extension/{ext}/ringout',
                headers=self._auth_headers(),
                json={
                    'from': {'phoneNumber': from_phone},
                    'to': {'phoneNumber': to_phone},
                    'callerId': {'phoneNumber': config.account_phone},
                    'playPrompt': False,
                },
                timeout=15,
            )
            if response.ok:
                data = response.json()
                logger.info(f'RingOut initiated to {to_phone}, id={data.get("id")}')
                return data
            logger.error(f'RingOut failed: {response.status_code} {response.text}')
            return None
        except Exception as e:
            logger.error(f'RingOut error: {e}')
            return None

    def get_recording_content(self, recording_id: str) -> Optional[bytes]:
        """Download the binary MP3 content of a call recording."""
        try:
            response = requests.get(
                f'{RC_BASE}/restapi/v1.0/account/~/recording/{recording_id}/content',
                headers={
                    'Authorization': f'Bearer {self.get_access_token()}',
                    'Accept': 'audio/mpeg',
                },
                timeout=60,
                stream=True,
            )
            if response.ok:
                return response.content
            logger.error(f'Recording download failed: {response.status_code}')
            return None
        except Exception as e:
            logger.error(f'Recording download error: {e}')
            return None

    def subscribe_webhooks(self, webhook_url: str) -> Optional[str]:
        """
        Register a webhook subscription for SMS and call recording events.
        Returns the subscription ID or None on failure.
        """
        config = self._get_config()
        try:
            response = requests.post(
                f'{RC_BASE}/restapi/v1.0/subscription',
                headers=self._auth_headers(),
                json={
                    'eventFilters': [
                        '/restapi/v1.0/account/~/extension/~/message-store/instant?type=SMS',
                        '/restapi/v1.0/account/~/telephony/sessions?withRecordings=true',
                    ],
                    'deliveryMode': {
                        'transportType': 'WebHook',
                        'address': webhook_url,
                    },
                    'expiresIn': 630720000,  # ~20 years (max allowed)
                },
                timeout=15,
            )
            if response.ok:
                data = response.json()
                subscription_id = data.get('id')
                logger.info(f'RingCentral webhook subscription created: {subscription_id}')
                # Persist subscription ID in config
                if config and subscription_id:
                    config.webhook_subscription_id = subscription_id
                    config.save(update_fields=['webhook_subscription_id'])
                return subscription_id
            logger.error(f'Webhook subscription failed: {response.status_code} {response.text}')
            return None
        except Exception as e:
            logger.error(f'Webhook subscription error: {e}')
            return None

    def delete_subscription(self, subscription_id: str) -> bool:
        """Delete a webhook subscription."""
        try:
            response = requests.delete(
                f'{RC_BASE}/restapi/v1.0/subscription/{subscription_id}',
                headers=self._auth_headers(),
                timeout=10,
            )
            return response.ok or response.status_code == 404
        except Exception as e:
            logger.error(f'Delete subscription error: {e}')
            return False


# Singleton instance
ringcentral_service = RingCentralService()
