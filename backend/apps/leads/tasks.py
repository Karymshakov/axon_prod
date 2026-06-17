"""
Celery tasks for the leads app.
"""
import logging
from celery import shared_task
from django.core.management import call_command

logger = logging.getLogger(__name__)


@shared_task(name='leads.run_agent_check')
def run_agent_check():
    """
    Periodic task to run the AI agent check on all leads.
    Evaluates each lead and sends follow-up messages where appropriate.
    """
    from .agent_service import agent_service

    logger.info("Starting AI agent check...")
    results = agent_service.run_agent_check()
    logger.info(f"AI agent check completed: {results}")

    return results


@shared_task(name='leads.cleanup_expired_comms_media')
def cleanup_expired_comms_media(days: int = 30):
    """
    Periodic task to remove old communication media files from local storage.
    """
    logger.info("Starting expired communication media cleanup...")
    call_command('cleanup_comms_media', days=days)
    logger.info("Expired communication media cleanup completed")

    return {'retention_days': days}
