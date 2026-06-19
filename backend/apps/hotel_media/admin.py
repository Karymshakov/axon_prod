from django.contrib import admin
from .models import HotelMediaItem, HotelMediaPhoto, MediaFingerprint, SocialContentItem


@admin.register(HotelMediaItem)
class HotelMediaItemAdmin(admin.ModelAdmin):
    list_display = ['title', 'media_type', 'category', 'room_category', 'ai_send_count', 'is_active', 'created_at']
    list_filter = ['media_type', 'category', 'room_category', 'is_active']
    search_fields = ['title', 'description', 'tags']


@admin.register(HotelMediaPhoto)
class HotelMediaPhotoAdmin(admin.ModelAdmin):
    list_display = ['item', 'order', 'created_at']
    search_fields = ['item__title']


@admin.register(SocialContentItem)
class SocialContentItemAdmin(admin.ModelAdmin):
    list_display = [
        'title',
        'platform',
        'content_type',
        'status',
        'review_status',
        'category',
        'room_category',
        'posted_at',
        'expires_at',
    ]
    list_filter = ['platform', 'content_type', 'status', 'review_status', 'category', 'room_category']
    search_fields = ['title', 'caption', 'external_id', 'reply_guidance', 'manager_notes']
    raw_id_fields = ['linked_media_item']


@admin.register(MediaFingerprint)
class MediaFingerprintAdmin(admin.ModelAdmin):
    list_display = ['hash_kind', 'hotel_media_item', 'hotel_media_photo', 'social_content_item', 'bit_length', 'created_at']
    list_filter = ['hash_kind']
    search_fields = ['hash_value', 'hotel_media_item__title', 'social_content_item__title']
    raw_id_fields = ['hotel_media_item', 'hotel_media_photo', 'social_content_item']
