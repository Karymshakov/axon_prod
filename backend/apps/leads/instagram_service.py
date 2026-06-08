import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)

# Instagram Login API always uses graph.instagram.com
INSTAGRAM_MESSAGES_URL = 'https://graph.instagram.com/v21.0/me/messages'


class InstagramService:
    """Service for interacting with Instagram Graph API (Instagram Login flow)."""

    def __init__(self):
        self.access_token = None
        self._load_config()

    def _load_config(self):
        """Load configuration from database."""
        self.access_token = None
        try:
            from .models import InstagramConnection
            config = InstagramConnection.get_config()
            if config:
                self.access_token = config.access_token
        except Exception as e:
            logger.error(f"Could not load Instagram config: {e}", exc_info=True)

    def is_configured(self) -> bool:
        """Return True if an access token is stored (regardless of expiry)."""
        self._load_config()
        return bool(self.access_token)

    def send_message(self, recipient_id: str, text: str) -> Optional[dict]:
        """Send a message to an Instagram user via graph.instagram.com."""
        if not self.is_configured():
            logger.error("Instagram not configured")
            return None

        try:
            response = requests.post(
                INSTAGRAM_MESSAGES_URL,
                json={
                    "recipient": {"id": recipient_id},
                    "message": {"text": text},
                    "access_token": self.access_token,
                },
                timeout=10,
            )
            response.raise_for_status()
            result = response.json()
            return {
                'recipient_id': recipient_id,
                'message_id': result.get('message_id'),
                'text': text,
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send Instagram message to {recipient_id}: {e}")
            return None

    def send_image_url(self, recipient_id: str, image_url: str, caption: str = None) -> Optional[dict]:
        """Send an image attachment to an Instagram user via graph.instagram.com.

        image_url must be a publicly accessible HTTPS URL — Instagram's servers
        fetch it and deliver it as an attachment in the DM conversation.
        caption is accepted for API symmetry but Instagram DM attachments do not
        render captions; the AI should follow up with a text message instead.
        """
        if not self.is_configured():
            logger.error("Instagram not configured")
            return None

        try:
            response = requests.post(
                INSTAGRAM_MESSAGES_URL,
                json={
                    "recipient": {"id": recipient_id},
                    "message": {
                        "attachment": {
                            "type": "image",
                            "payload": {"url": image_url},
                        }
                    },
                    "access_token": self.access_token,
                },
                timeout=15,
            )
            response.raise_for_status()
            result = response.json()
            logger.info(f"Sent Instagram image to {recipient_id}: {image_url}")
            return {
                'recipient_id': recipient_id,
                'message_id': result.get('message_id'),
                'image_url': image_url,
            }
        except requests.exceptions.RequestException as e:
            error_detail = ''
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = f' — {e.response.text}'
                except Exception:
                    pass
            logger.error(f"Failed to send Instagram image to {recipient_id}: {e}{error_detail}")
            return None

    def send_typing_indicator(self, recipient_id: str) -> None:
        """
        Send a typing indicator to an Instagram user.
        Shows for ~20 s; call every 4 s to keep it continuous.
        Never raises — a typing failure must not break the response flow.
        """
        if not self.is_configured():
            return
        try:
            requests.post(
                INSTAGRAM_MESSAGES_URL,
                json={
                    "recipient": {"id": recipient_id},
                    "sender_action": "typing_on",
                    "access_token": self.access_token,
                },
                timeout=5,
            )
        except Exception as e:
            logger.warning(f"Failed to send Instagram typing indicator to {recipient_id}: {e}")


# Singleton instance
instagram_service = InstagramService()
