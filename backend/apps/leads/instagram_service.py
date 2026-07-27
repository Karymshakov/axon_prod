import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)

# Instagram Login API always uses graph.instagram.com.
INSTAGRAM_GRAPH_MESSAGES_BASE = 'https://graph.instagram.com/v25.0'


class InstagramService:
    """Service for interacting with Instagram Graph API (Instagram Login flow)."""

    def __init__(self):
        # Credentials are always resolved per request/workspace.
        self.access_token = None
        self.instagram_user_id = None

    def _credentials(self, org=None) -> tuple[str | None, str | None]:
        """Return request-local credentials so parallel organizations cannot race."""
        try:
            from .models import InstagramConnection

            config = InstagramConnection.get_config(org)
            if config:
                return (
                    config.access_token or None,
                    config.instagram_user_id
                    or config.instagram_business_account_id
                    or None,
                )
        except Exception as exc:
            logger.error('Could not load Instagram config: %s', exc, exc_info=True)
        return None, None

    def _load_config(self, org=None):
        """Keep legacy attributes populated for diagnostics only."""
        self.access_token, self.instagram_user_id = self._credentials(org)

    def is_configured(self, org=None) -> bool:
        """Return True if an access token is stored (regardless of expiry)."""
        access_token, _ = self._credentials(org)
        return bool(access_token)

    def send_message(self, recipient_id: str, text: str, org=None, raise_exception: bool = False) -> Optional[dict]:
        """Send a message to an Instagram user via graph.instagram.com."""
        access_token, instagram_user_id = self._credentials(org)
        if not access_token:
            logger.error("Instagram not configured")
            if raise_exception:
                raise Exception("Instagram is not connected. Please connect your Instagram Business Account in Settings.")
            return None
        try:
            response = requests.post(
                f'{INSTAGRAM_GRAPH_MESSAGES_BASE}/{instagram_user_id or "me"}/messages',
                json={
                    "recipient": {"id": recipient_id},
                    "message": {"text": text},
                    "access_token": access_token,
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
            error_detail = ""
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = f" - Response: {e.response.text}"
                except Exception:
                    pass
            logger.error(f"Failed to send Instagram message to {recipient_id}: {e}{error_detail}")
            if raise_exception:
                raise Exception(f"Meta API error: {e.response.text if hasattr(e, 'response') and e.response is not None else str(e)}")
            return None

    def send_private_reply_to_comment(
        self,
        comment_id: str,
        text: str,
        org=None,
        raise_exception: bool = False,
    ) -> Optional[dict]:
        """Send one private Instagram reply addressed to a public comment."""
        access_token, instagram_user_id = self._credentials(org)
        if not access_token:
            if raise_exception:
                raise Exception('Instagram is not connected.')
            return None
        try:
            response = requests.post(
                f'{INSTAGRAM_GRAPH_MESSAGES_BASE}/{instagram_user_id or "me"}/messages',
                json={
                    'recipient': {'comment_id': comment_id},
                    'message': {'text': text},
                    'access_token': access_token,
                },
                timeout=10,
            )
            response.raise_for_status()
            result = response.json()
            return {
                'comment_id': comment_id,
                'message_id': result.get('message_id'),
                'recipient_id': result.get('recipient_id'),
                'text': text,
            }
        except requests.exceptions.RequestException as exc:
            detail = ''
            if getattr(exc, 'response', None) is not None:
                detail = getattr(exc.response, 'text', '')
            logger.error(
                'Failed to send Instagram private reply for comment %s: %s %s',
                comment_id,
                exc,
                detail,
            )
            if raise_exception:
                raise
            return None

    def send_image_url(self, recipient_id: str, image_url: str, caption: str = None, org=None) -> Optional[dict]:
        """Send an image attachment to an Instagram user via graph.instagram.com.

        image_url must be a publicly accessible HTTPS URL — Instagram's servers
        fetch it and deliver it as an attachment in the DM conversation.
        caption is accepted for API symmetry but Instagram DM attachments do not
        render captions; the AI should follow up with a text message instead.
        """
        return self.send_attachment_url(recipient_id, image_url, attachment_type='image', org=org)

    def send_attachment_url(self, recipient_id: str, media_url: str, attachment_type: str = 'image', org=None) -> Optional[dict]:
        """Send a media attachment URL to an Instagram user."""
        access_token, instagram_user_id = self._credentials(org)
        if not access_token:
            logger.error("Instagram not configured")
            return None

        api_attachment_type = attachment_type if attachment_type in {'image', 'video', 'audio', 'file'} else 'image'
        try:
            response = requests.post(
                f'{INSTAGRAM_GRAPH_MESSAGES_BASE}/{instagram_user_id or "me"}/messages',
                json={
                    "recipient": {"id": recipient_id},
                    "message": {
                        "attachment": {
                            "type": api_attachment_type,
                            "payload": {"url": media_url},
                        }
                    },
                    "access_token": access_token,
                },
                timeout=15,
            )
            response.raise_for_status()
            result = response.json()
            logger.info(f"Sent Instagram {api_attachment_type} to {recipient_id}: {media_url}")
            return {
                'recipient_id': recipient_id,
                'message_id': result.get('message_id'),
                'media_url': media_url,
            }
        except requests.exceptions.RequestException as e:
            error_detail = ''
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = f' — {e.response.text}'
                except Exception:
                    pass
            logger.error(f"Failed to send Instagram {api_attachment_type} to {recipient_id}: {e}{error_detail}")
            return None

    def send_typing_indicator(self, recipient_id: str, org=None) -> None:
        """
        Send a typing indicator to an Instagram user.
        Shows for ~20 s; call every 4 s to keep it continuous.
        Never raises — a typing failure must not break the response flow.
        """
        access_token, instagram_user_id = self._credentials(org)
        if not access_token:
            return
        try:
            requests.post(
                f'{INSTAGRAM_GRAPH_MESSAGES_BASE}/{instagram_user_id or "me"}/messages',
                json={
                    "recipient": {"id": recipient_id},
                    "sender_action": "typing_on",
                    "access_token": access_token,
                },
                timeout=5,
            )
        except Exception as e:
            logger.warning(f"Failed to send Instagram typing indicator to {recipient_id}: {e}")


# Singleton instance
instagram_service = InstagramService()
