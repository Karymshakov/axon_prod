import os
import mimetypes
import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)
GRAPH_API_VERSION = 'v25.0'


class WhatsAppService:
    """Service for interacting with WhatsApp Business Cloud API."""

    def __init__(self):
        self.access_token = None
        self.phone_number_id = None
        self._load_config()

    def _load_config(self, org=None):
        """Load configuration from database."""
        # Reset first so a disconnect is always reflected immediately
        self.access_token = None
        self.phone_number_id = None
        try:
            from .models import WhatsAppConfig
            config = WhatsAppConfig.get_config(org)
            if config:
                self.access_token = config.access_token
                self.phone_number_id = config.phone_number_id
        except Exception as e:
            logger.error(f"Could not load WhatsApp config: {e}", exc_info=True)

    def is_configured(self, org=None) -> bool:
        """Check if WhatsApp is properly configured."""
        self._load_config(org)  # Reload config in case it changed
        return bool(self.access_token and self.phone_number_id)

    def send_message(self, recipient_phone: str, text: str, org=None, raise_exception: bool = False) -> Optional[dict]:
        """
        Send a WhatsApp message via Cloud API.

        Args:
            recipient_phone: Recipient's phone number (with country code, no + or spaces)
            text: Message text
            org: Organization instance

        Returns:
            Message data if successful, None otherwise
        """
        if not self.is_configured(org):
            logger.error("WhatsApp not configured")
            return None

        try:
            # WhatsApp Cloud API endpoint
            url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{self.phone_number_id}/messages"

            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }

            # Format phone number: remove +, spaces, dashes for WhatsApp API
            formatted_phone = recipient_phone.replace('+', '').replace('-', '').replace(' ', '')
            logger.info(f"Sending WhatsApp message to formatted phone: {formatted_phone}")

            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": formatted_phone,
                "type": "text",
                "text": {
                    "preview_url": False,
                    "body": text
                }
            }

            response = requests.post(url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()

            result = response.json()
            message_id = result.get('messages', [{}])[0].get('id')

            return {
                'recipient_phone': recipient_phone,
                'message_id': message_id,
                'text': text,
            }
        except requests.exceptions.RequestException as e:
            # Log detailed error response from WhatsApp API
            error_detail = ""
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = f" - Response: {e.response.text}"
                except Exception:
                    pass
            logger.error(f"Failed to send WhatsApp message to {recipient_phone}: {e}{error_detail}")
            if raise_exception:
                raise Exception(f"Meta API error: {e.response.text if hasattr(e, 'response') and e.response is not None else str(e)}")
            return None

    def mark_as_read(self, message_id: str, org=None) -> None:
        """
        Mark an incoming WhatsApp message as read (shows blue double-checkmarks).
        WhatsApp Cloud API has no typing indicator, so this is the best immediate
        feedback available. Never raises — a failure must not break the response flow.
        """
        if not self.is_configured(org) or not message_id:
            return
        try:
            url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{self.phone_number_id}/messages"
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json',
            }
            payload = {
                "messaging_product": "whatsapp",
                "status": "read",
                "message_id": message_id,
            }
            requests.post(url, json=payload, headers=headers, timeout=5)
        except Exception as e:
            logger.warning(f"Failed to mark WhatsApp message {message_id} as read: {e}")

    def get_phone_number_info(self, org=None) -> Optional[dict]:
        """Get information about the WhatsApp Business Phone Number."""
        if not self.is_configured(org):
            return None

        try:
            url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{self.phone_number_id}"
            params = {
                'fields': 'display_phone_number,verified_name,quality_rating',
                'access_token': self.access_token
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get WhatsApp phone number info: {e}")
            return None

    def upload_media(self, file_path: str, mime_type: str = 'image/jpeg', org=None) -> Optional[str]:
        """
        Upload media to Meta WhatsApp Business API.

        Returns:
            Media ID if successful, None otherwise
        """
        if not self.is_configured(org):
            logger.error("WhatsApp not configured")
            return None
        try:
            url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{self.phone_number_id}/media"
            headers = {
                'Authorization': f'Bearer {self.access_token}',
            }
            with open(file_path, 'rb') as f:
                files = {
                    'file': (os.path.basename(file_path), f, mime_type)
                }
                data = {
                    'messaging_product': 'whatsapp'
                }
                response = requests.post(url, headers=headers, files=files, data=data, timeout=20)
                response.raise_for_status()
                return response.json().get('id')
        except Exception as e:
            logger.error(f"Failed to upload WhatsApp media {file_path}: {e}", exc_info=True)
            return None

    def send_photo(self, recipient_phone: str, file_path: str, caption: str = None, org=None, raise_exception: bool = False) -> Optional[dict]:
        """
        Upload a local photo file and send it as a WhatsApp message.
        """
        if not self.is_configured(org):
            logger.error("WhatsApp not configured")
            return None

        # Guess mime type or use default image/jpeg
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            mime_type = 'image/jpeg'

        media_id = self.upload_media(file_path, mime_type=mime_type, org=org)
        if not media_id:
            logger.error("Failed to upload WhatsApp photo media")
            if raise_exception:
                raise Exception("Failed to upload media to WhatsApp Cloud API")
            return None

        try:
            url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{self.phone_number_id}/messages"
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            formatted_phone = recipient_phone.replace('+', '').replace('-', '').replace(' ', '')

            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": formatted_phone,
                "type": "image",
                "image": {
                    "id": media_id,
                }
            }
            if caption:
                payload["image"]["caption"] = caption

            response = requests.post(url, json=payload, headers=headers, timeout=15)
            response.raise_for_status()
            result = response.json()
            message_id = result.get('messages', [{}])[0].get('id')

            return {
                'recipient_phone': recipient_phone,
                'message_id': message_id,
                'media_id': media_id,
            }
        except Exception as e:
            logger.error(f"Failed to send WhatsApp photo to {recipient_phone}: {e}")
            if raise_exception:
                raise
            return None

    def download_media(self, media_id: str, dest_path: str, org=None) -> bool:
        """Download media from WhatsApp Cloud API using its media_id."""
        if not self.is_configured(org):
            logger.error("WhatsApp not configured")
            return False
        try:
            headers = {
                'Authorization': f'Bearer {self.access_token}',
            }
            # Step 1: Get media URL
            url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{media_id}"
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            media_info = response.json()
            download_url = media_info.get('url')
            if not download_url:
                logger.error(f"No media download URL found for ID {media_id}")
                return False

            # Step 2: Download media file
            media_response = requests.get(download_url, headers=headers, timeout=20)
            media_response.raise_for_status()

            # Save the file
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            with open(dest_path, 'wb') as f:
                f.write(media_response.content)
            logger.info(f"Successfully downloaded WhatsApp media {media_id} to {dest_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to download WhatsApp media {media_id}: {e}", exc_info=True)
            return False


# Singleton instance
whatsapp_service = WhatsAppService()
