import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='hotel_media.sync_instagram_social_content')
def sync_instagram_social_content_task():
    """Periodic sync of Instagram posts/reels/stories into the content registry."""
    from .services import sync_instagram_social_content

    logger.info('Starting Instagram social content sync...')
    result = sync_instagram_social_content()
    logger.info('Instagram social content sync completed: %s', result)
    return result

