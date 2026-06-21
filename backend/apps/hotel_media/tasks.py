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


@shared_task(bind=True, name='hotel_media.rebuild_social_content_fingerprints', max_retries=4)
def rebuild_social_content_fingerprints_task(self, item_id: int):
    """Retry transient Meta/CDN failures while a new story URL is still valid."""
    from .models import SocialContentItem
    from .services import rebuild_social_content_fingerprints

    try:
        item = SocialContentItem.objects.get(pk=item_id, is_active=True)
    except SocialContentItem.DoesNotExist:
        return {'item_id': item_id, 'status': 'missing'}

    count = rebuild_social_content_fingerprints(item)
    if not item.fingerprints.exists():
        countdowns = (20, 60, 180, 300)
        countdown = countdowns[min(self.request.retries, len(countdowns) - 1)]
        logger.warning(
            'No fingerprints available for SocialContentItem %s; retrying in %ss',
            item_id,
            countdown,
        )
        raise self.retry(countdown=countdown)

    return {'item_id': item_id, 'status': 'ready', 'fingerprints': count}
