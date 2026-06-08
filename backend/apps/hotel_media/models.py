from django.db import models

ORG_FK = dict(
    to='organizations.Organization',
    on_delete=models.CASCADE,
    null=True,
    blank=True,
    related_name='+',
    db_index=True,
)


class HotelMediaItem(models.Model):
    MEDIA_TYPE_PHOTO = 'photo'
    MEDIA_TYPE_VIDEO = 'video'
    MEDIA_TYPE_DOCUMENT = 'document'
    MEDIA_TYPE_CHOICES = [
        (MEDIA_TYPE_PHOTO, 'Photo'),
        (MEDIA_TYPE_VIDEO, 'Video'),
        (MEDIA_TYPE_DOCUMENT, 'Document'),
    ]

    ROOM_CATEGORY_STANDARD_QUEEN = 'standard_queen'
    ROOM_CATEGORY_STANDARD_TWIN = 'standard_twin'
    ROOM_CATEGORY_COMFORT = 'comfort'
    ROOM_CATEGORY_FAMILY = 'family'
    ROOM_CATEGORY_OTHER = 'other'
    ROOM_CATEGORY_CHOICES = [
        ('standard_queen', 'Standard Queen'),
        ('standard_twin', 'Standard Twin'),
        ('comfort', 'Comfort'),
        ('family', 'Family'),
        ('other', 'Other'),
    ]

    CATEGORY_ROOMS = 'rooms'
    CATEGORY_CAFETERIA = 'cafeteria'
    CATEGORY_POOL = 'pool'
    CATEGORY_SPA = 'spa'
    CATEGORY_CONFERENCE = 'conference'
    CATEGORY_EXTERIOR = 'exterior'
    CATEGORY_LOBBY = 'lobby'
    CATEGORY_OTHER = 'other'
    CATEGORY_CHOICES = [
        (CATEGORY_ROOMS, 'Guest Rooms'),
        (CATEGORY_CAFETERIA, 'Cafeteria & Dining'),
        (CATEGORY_POOL, 'Pool'),
        (CATEGORY_SPA, 'Spa & Wellness'),
        (CATEGORY_CONFERENCE, 'Conference & Events'),
        (CATEGORY_EXTERIOR, 'Exterior & Views'),
        (CATEGORY_LOBBY, 'Lobby & Common Areas'),
        (CATEGORY_OTHER, 'Other'),
    ]

    organization = models.ForeignKey(**ORG_FK)
    title = models.CharField(max_length=255)
    description = models.TextField(
        blank=True,
        help_text='AI uses this to decide when to send this media to leads',
    )
    tags = models.JSONField(default=list, blank=True, help_text='List of tag strings')
    category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES,
        default=CATEGORY_OTHER,
    )
    room_category = models.CharField(
        max_length=50,
        choices=ROOM_CATEGORY_CHOICES,
        blank=True,
        null=True,
        help_text='Room type for AI photo tool (only for Rooms category)',
    )
    media_type = models.CharField(
        max_length=20,
        choices=MEDIA_TYPE_CHOICES,
        default=MEDIA_TYPE_PHOTO,
    )
    file = models.FileField(
        upload_to='hotel_media/',
        null=True,
        blank=True,
        help_text='Uploaded file (photo, video, document)',
    )
    video_url = models.URLField(
        blank=True,
        help_text='External video URL (YouTube, Vimeo, etc.)',
    )
    ai_send_count = models.PositiveIntegerField(
        default=0,
        help_text='Number of times the AI agent has sent this item to leads',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Hotel Media Item'
        verbose_name_plural = 'Hotel Media Items'

    def __str__(self):
        return self.title


class HotelMediaPhoto(models.Model):
    """Individual photo belonging to a HotelMediaItem album."""
    item = models.ForeignKey(
        HotelMediaItem,
        on_delete=models.CASCADE,
        related_name='photos',
    )
    file = models.FileField(upload_to='hotel_media/')
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'created_at']
        verbose_name = 'Hotel Media Photo'
        verbose_name_plural = 'Hotel Media Photos'

    def __str__(self):
        return f"{self.item.title} — photo {self.pk}"
