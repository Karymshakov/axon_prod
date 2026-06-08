"""
Celery tasks for the leads app.
"""
import logging
from celery import shared_task

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
