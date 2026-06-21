import logging

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import HotelMediaItem, HotelMediaPhoto, SocialContentItem

logger = logging.getLogger(__name__)


def _safe_on_commit(callback):
    try:
        transaction.on_commit(callback)
    except RuntimeError:
        callback()


@receiver(post_save, sender=HotelMediaItem)
def rebuild_item_fingerprints_on_save(sender, instance: HotelMediaItem, **kwargs):
    update_fields = kwargs.get('update_fields')
    if update_fields is not None and 'file' not in set(update_fields):
        return

    def _rebuild():
        try:
            from .services import rebuild_hotel_media_item_fingerprints

            count = rebuild_hotel_media_item_fingerprints(instance)
            logger.info('Rebuilt %s fingerprints for HotelMediaItem %s', count, instance.id)
        except Exception as exc:
            logger.warning('Could not rebuild fingerprints for HotelMediaItem %s: %s', instance.id, exc)

    _safe_on_commit(_rebuild)


@receiver(post_save, sender=HotelMediaPhoto)
def rebuild_photo_fingerprints_on_save(sender, instance: HotelMediaPhoto, **kwargs):
    update_fields = kwargs.get('update_fields')
    if update_fields is not None and 'file' not in set(update_fields):
        return

    def _rebuild():
        try:
            from .services import rebuild_hotel_media_photo_fingerprints

            count = rebuild_hotel_media_photo_fingerprints(instance)
            logger.info('Rebuilt %s fingerprints for HotelMediaPhoto %s', count, instance.id)
        except Exception as exc:
            logger.warning('Could not rebuild fingerprints for HotelMediaPhoto %s: %s', instance.id, exc)

    _safe_on_commit(_rebuild)


@receiver(post_save, sender=SocialContentItem)
def rebuild_social_content_fingerprints_on_save(sender, instance: SocialContentItem, **kwargs):
    update_fields = kwargs.get('update_fields')
    relevant_fields = {'linked_media_item', 'media_url', 'thumbnail_url'}
    if update_fields is not None and not relevant_fields.intersection(set(update_fields)):
        return

    def _rebuild():
        try:
            from .services import rebuild_social_content_fingerprints

            count = rebuild_social_content_fingerprints(instance)
            logger.info('Rebuilt %s fingerprints for SocialContentItem %s', count, instance.id)
            if not instance.fingerprints.exists():
                from .tasks import rebuild_social_content_fingerprints_task

                rebuild_social_content_fingerprints_task.apply_async(
                    args=[instance.id],
                    countdown=20,
                )
                logger.info('Scheduled fingerprint retry for SocialContentItem %s', instance.id)
        except Exception as exc:
            logger.warning('Could not rebuild fingerprints for SocialContentItem %s: %s', instance.id, exc)

    _safe_on_commit(_rebuild)
