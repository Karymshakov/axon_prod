import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)


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
            url = f"https://graph.facebook.com/v23.0/{self.phone_number_id}/messages"

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
            url = f"https://graph.facebook.com/v23.0/{self.phone_number_id}/messages"
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
            url = f"https://graph.facebook.com/v23.0/{self.phone_number_id}"
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


# Singleton instance
whatsapp_service = WhatsAppService()
