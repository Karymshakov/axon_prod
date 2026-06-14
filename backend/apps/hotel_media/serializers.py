from rest_framework import serializers
from .models import HotelMediaItem, HotelMediaPhoto


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
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'ai_send_count', 'is_active', 'created_at', 'updated_at']

    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file:
            url = obj.file.url
            if request is not None:
                return request.build_absolute_uri(url)
            return url
        return None
