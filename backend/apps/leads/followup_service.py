import logging
import asyncio
from .models import Lead, LeadActivity, PipelineStage
from .telegram_service import telegram_service
from .instagram_service import instagram_service

logger = logging.getLogger(__name__)


class FollowUpService:
    """Service for sending automated follow-up messages based on pipeline stage."""

    def send_follow_up_for_stage(self, lead: Lead, stage: PipelineStage) -> bool:
        """
        Send a follow-up message when a lead enters a pipeline stage.

        Args:
            lead: The Lead instance
            stage: The PipelineStage the lead moved to

        Returns:
            True if message was sent successfully, False otherwise
        """
        if not stage.followup_enabled:
            logger.debug(f"Follow-up not enabled for stage '{stage.name}'")
            return False

        if not stage.followup_message_template:
            logger.debug(f"No follow-up message template for stage '{stage.name}'")
            return False

        message = self._render_template(stage.followup_message_template, lead)

        if lead.telegram_chat_id and telegram_service.is_configured():
            return self._send_telegram(lead, message, stage.name)
        elif lead.instagram_user_id and instagram_service.is_configured():
            return self._send_instagram(lead, message, stage.name)
        else:
            logger.debug(f"Lead {lead.id} has no messaging channel configured")
            return False

    def send_follow_up(self, lead: Lead, new_status: str) -> bool:
        """
        Legacy method: Send follow-up based on status.
        Finds matching pipeline stage by status key.
        """
        # Try to find a pipeline stage matching this status
        try:
            stage = PipelineStage.objects.filter(
                key=new_status,
                segment=lead.segment,
                followup_enabled=True
            ).first()

            if stage:
                return self.send_follow_up_for_stage(lead, stage)
        except Exception as e:
            logger.error(f"Error finding stage for status '{new_status}': {e}")

        return False

    def _render_template(self, template: str, lead: Lead) -> str:
        """Render a message template with lead data."""
        contact_name = lead.contact_person or 'there'

        return template.format(
            contact_person=contact_name,
            company_name='',
        )

    def _send_telegram(self, lead: Lead, message: str, stage_name: str = '') -> bool:
        """Send a follow-up message via Telegram."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(
                telegram_service.send_message(lead.telegram_chat_id, message)
            )
            loop.close()

            if result:
                LeadActivity.objects.create(
                    lead=lead,
                    activity_type=LeadActivity.TYPE_TELEGRAM_SENT,
                    description=f"Auto follow-up ({stage_name}): {message[:100]}{'...' if len(message) > 100 else ''}",
                    metadata={
                        'message_id': result.get('message_id'),
                        'text': message,
                        'is_auto_followup': True,
                        'stage': stage_name,
                    }
                )
                logger.info(f"Sent Telegram follow-up to lead {lead.id} for stage '{stage_name}'")
                return True

            return False
        except Exception as e:
            logger.error(f"Error sending Telegram follow-up to lead {lead.id}: {e}", exc_info=True)
            return False

    def _send_instagram(self, lead: Lead, message: str, stage_name: str = '') -> bool:
        """Send a follow-up message via Instagram."""
        try:
            result = instagram_service.send_message(lead.instagram_user_id, message)

            if result:
                LeadActivity.objects.create(
                    lead=lead,
                    activity_type=LeadActivity.TYPE_INSTAGRAM_SENT,
                    description=f"Auto follow-up ({stage_name}): {message[:100]}{'...' if len(message) > 100 else ''}",
                    echo_origin=LeadActivity.ECHO_ORIGIN_CRM,
                    metadata={
                        'message_id': result.get('message_id'),
                        'text': message,
                        'is_auto_followup': True,
                        'stage': stage_name,
                        'echo_origin': LeadActivity.ECHO_ORIGIN_CRM,
                    }
                )
                logger.info(f"Sent Instagram follow-up to lead {lead.id} for stage '{stage_name}'")
                return True

            return False
        except Exception as e:
            logger.error(f"Error sending Instagram follow-up to lead {lead.id}: {e}", exc_info=True)
            return False


followup_service = FollowUpService()
