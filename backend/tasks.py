"""
Sample Celery tasks for testing the worker setup.

Usage:
    from tasks import example_task
    example_task.delay("Hello, Celery!")
"""

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def example_task(message: str) -> str:
    """Example Celery task for testing the worker setup."""
    logger.info(f"Processing task with message: {message}")
    return f"Processed: {message}"
