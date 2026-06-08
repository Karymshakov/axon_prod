from django.contrib import admin
from .models import HotelMediaItem


@admin.register(HotelMediaItem)
class HotelMediaItemAdmin(admin.ModelAdmin):
    list_display = ['title', 'media_type', 'category', 'ai_send_count', 'is_active', 'created_at']
    list_filter = ['media_type', 'category', 'is_active']
    search_fields = ['title', 'description']
