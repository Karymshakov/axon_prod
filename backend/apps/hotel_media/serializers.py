from rest_framework import serializers
from .models import HotelMediaItem, HotelMediaPhoto, MediaFingerprint, SocialContentItem


class HotelMediaPhotoSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = HotelMediaPhoto
        fields = ['id', 'file_url', 'order', 'created_at']
        read_only_fields = ['id', 'created_at']

    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file:
            url = obj.file.url
            if request is not None:
                return request.build_absolute_uri(url)
            return url
        return None


class HotelMediaItemSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    media_type_display = serializers.CharField(source='get_media_type_display', read_only=True)
    photos = HotelMediaPhotoSerializer(many=True, read_only=True)
    fingerprint_count = serializers.SerializerMethodField()

    class Meta:
        model = HotelMediaItem
        fields = [
            'id',
            'title',
            'description',
            'tags',
            'category',
            'category_display',
            'room_category',
            'media_type',
            'media_type_display',
            'file',
            'file_url',
            'video_url',
            'ai_send_count',
            'is_active',
            'photos',
            'fingerprint_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'ai_send_count', 'is_active', 'fingerprint_count', 'created_at', 'updated_at']

    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file:
            url = obj.file.url
            if request is not None:
                return request.build_absolute_uri(url)
            return url
        return None

    def get_fingerprint_count(self, obj):
        return getattr(obj, 'fingerprints', None).count() if getattr(obj, 'pk', None) else 0


class SocialContentItemSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    content_type_display = serializers.CharField(source='get_content_type_display', read_only=True)
    platform_display = serializers.CharField(source='get_platform_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    review_status_display = serializers.CharField(source='get_review_status_display', read_only=True)
    linked_media_title = serializers.CharField(source='linked_media_item.title', read_only=True)
    effective_category = serializers.CharField(read_only=True)
    effective_room_category = serializers.CharField(read_only=True)
    fingerprint_count = serializers.SerializerMethodField()

    class Meta:
        model = SocialContentItem
        fields = [
            'id',
            'platform',
            'platform_display',
            'external_id',
            'parent_external_id',
            'content_type',
            'content_type_display',
            'status',
            'status_display',
            'review_status',
            'review_status_display',
            'source',
            'linked_media_item',
            'linked_media_title',
            'title',
            'caption',
            'category',
            'category_display',
            'room_category',
            'effective_category',
            'effective_room_category',
            'playbook_keys',
            'auto_tags',
            'reply_guidance',
            'manager_notes',
            'media_url',
            'thumbnail_url',
            'permalink',
            'posted_at',
            'expires_at',
            'last_synced_at',
            'metadata',
            'is_active',
            'fingerprint_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'source', 'fingerprint_count', 'created_at', 'updated_at']

    def get_fingerprint_count(self, obj):
        return obj.fingerprints.count() if getattr(obj, 'pk', None) else 0


class MediaFingerprintSerializer(serializers.ModelSerializer):
    hash_kind_display = serializers.CharField(source='get_hash_kind_display', read_only=True)
    hotel_media_title = serializers.CharField(source='hotel_media_item.title', read_only=True)
    social_content_title = serializers.CharField(source='social_content_item.title', read_only=True)

    class Meta:
        model = MediaFingerprint
        fields = [
            'id',
            'hotel_media_item',
            'hotel_media_title',
            'hotel_media_photo',
            'social_content_item',
            'social_content_title',
            'hash_kind',
            'hash_kind_display',
            'hash_value',
            'bit_length',
            'width',
            'height',
            'frame_second',
            'crop_label',
            'metadata',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']
