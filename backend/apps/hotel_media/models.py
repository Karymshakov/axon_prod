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


class SocialContentItem(models.Model):
    """Published social content that can explain incoming story/post replies."""

    PLATFORM_INSTAGRAM = 'instagram'
    PLATFORM_CHOICES = [
        (PLATFORM_INSTAGRAM, 'Instagram'),
    ]

    TYPE_POST = 'post'
    TYPE_REEL = 'reel'
    TYPE_STORY = 'story'
    TYPE_HIGHLIGHT = 'highlight'
    TYPE_EVENT = 'event'
    TYPE_UNKNOWN = 'unknown'
    CONTENT_TYPE_CHOICES = [
        (TYPE_POST, 'Post'),
        (TYPE_REEL, 'Reel'),
        (TYPE_STORY, 'Story'),
        (TYPE_HIGHLIGHT, 'Highlight'),
        (TYPE_EVENT, 'Event / Campaign'),
        (TYPE_UNKNOWN, 'Unknown'),
    ]

    STATUS_ACTIVE = 'active'
    STATUS_EXPIRED = 'expired'
    STATUS_ARCHIVED = 'archived'
    STATUS_DELETED = 'deleted'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_EXPIRED, 'Expired'),
        (STATUS_ARCHIVED, 'Archived'),
        (STATUS_DELETED, 'Deleted'),
    ]

    REVIEW_AUTO = 'auto'
    REVIEW_NEEDS_REVIEW = 'needs_review'
    REVIEW_REVIEWED = 'reviewed'
    REVIEW_STATUS_CHOICES = [
        (REVIEW_AUTO, 'Auto-tagged'),
        (REVIEW_NEEDS_REVIEW, 'Needs manager review'),
        (REVIEW_REVIEWED, 'Reviewed'),
    ]

    SOURCE_AUTO_SYNC = 'auto_sync'
    SOURCE_WEBHOOK = 'webhook'
    SOURCE_MANUAL = 'manual'
    SOURCE_CHOICES = [
        (SOURCE_AUTO_SYNC, 'Auto sync'),
        (SOURCE_WEBHOOK, 'Webhook'),
        (SOURCE_MANUAL, 'Manual'),
    ]

    AUTOMATION_NONE = 'none'
    AUTOMATION_COMMENT_ANY = 'comment_any'
    AUTOMATION_COMMENT_EXACT = 'comment_exact'
    AUTOMATION_CHOICES = [
        (AUTOMATION_NONE, 'Disabled'),
        (AUTOMATION_COMMENT_ANY, 'Any comment'),
        (AUTOMATION_COMMENT_EXACT, 'Comment matches configured phrases'),
    ]

    organization = models.ForeignKey(**ORG_FK)
    platform = models.CharField(max_length=30, choices=PLATFORM_CHOICES, default=PLATFORM_INSTAGRAM)
    external_id = models.CharField(
        max_length=128,
        blank=True,
        db_index=True,
        help_text='Platform media/story/post ID when available',
    )
    parent_external_id = models.CharField(
        max_length=128,
        blank=True,
        db_index=True,
        help_text='Parent post/reel/highlight ID for derived story or share events',
    )
    content_type = models.CharField(max_length=30, choices=CONTENT_TYPE_CHOICES, default=TYPE_UNKNOWN)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    review_status = models.CharField(max_length=30, choices=REVIEW_STATUS_CHOICES, default=REVIEW_NEEDS_REVIEW)
    source = models.CharField(max_length=30, choices=SOURCE_CHOICES, default=SOURCE_AUTO_SYNC)

    linked_media_item = models.ForeignKey(
        HotelMediaItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='social_content_items',
        help_text='Curated hotel media item this social content represents, if known',
    )
    title = models.CharField(max_length=255, blank=True)
    caption = models.TextField(blank=True)
    category = models.CharField(
        max_length=50,
        choices=HotelMediaItem.CATEGORY_CHOICES,
        blank=True,
        help_text='Main topic/category managers and AI should use for this content',
    )
    room_category = models.CharField(
        max_length=50,
        choices=HotelMediaItem.ROOM_CATEGORY_CHOICES,
        blank=True,
        null=True,
        help_text='Room type if this content is about a specific room category',
    )
    playbook_keys = models.JSONField(
        default=list,
        blank=True,
        help_text='Optional playbook keys to prefer when a guest replies to this content',
    )
    auto_tags = models.JSONField(default=list, blank=True)
    reply_guidance = models.TextField(
        blank=True,
        help_text='Short manager-approved guidance/template for replies to this content',
    )
    manager_notes = models.TextField(blank=True)
    automation_enabled = models.BooleanField(default=False)
    automation_trigger = models.CharField(
        max_length=30,
        choices=AUTOMATION_CHOICES,
        default=AUTOMATION_NONE,
    )
    automation_trigger_values = models.JSONField(
        default=list,
        blank=True,
        help_text='Exact phrases for comment_exact; matching is normalized and case-insensitive.',
    )
    automation_reply_ru = models.TextField(blank=True)
    automation_reply_ky = models.TextField(blank=True)
    automation_reply_en = models.TextField(blank=True)
    automation_starts_at = models.DateTimeField(null=True, blank=True)
    automation_ends_at = models.DateTimeField(null=True, blank=True)
    automation_promotes_to_lead = models.BooleanField(
        default=False,
        help_text='If false, campaign delivery itself does not create a sales lead.',
    )
    automation_followup_allowed = models.BooleanField(
        default=False,
        help_text='Follow-ups remain disabled until the guest shows sales intent.',
    )

    media_url = models.TextField(blank=True)
    thumbnail_url = models.TextField(blank=True)
    permalink = models.URLField(blank=True)
    posted_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-posted_at', '-created_at']
        verbose_name = 'Social Content Item'
        verbose_name_plural = 'Social Content Items'
        constraints = [
            models.UniqueConstraint(
                fields=['organization', 'platform', 'external_id'],
                condition=~models.Q(external_id=''),
                name='uniq_social_content_external_id_per_org',
            ),
        ]
        indexes = [
            models.Index(fields=['organization', 'platform', 'content_type', 'status']),
            models.Index(fields=['organization', 'review_status']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        label = self.title or self.caption[:60] or self.external_id or f'Social content #{self.pk}'
        return f'{self.get_platform_display()} {self.get_content_type_display()}: {label}'

    @property
    def effective_category(self):
        if self.category:
            return self.category
        if self.linked_media_item_id:
            return self.linked_media_item.category
        return ''

    @property
    def effective_room_category(self):
        if self.room_category:
            return self.room_category
        if self.linked_media_item_id:
            return self.linked_media_item.room_category
        return ''


class SocialAutomationDelivery(models.Model):
    """Idempotent audit row for an Instagram comment-to-DM automation."""

    STATUS_PENDING = 'pending'
    STATUS_SENT = 'sent'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_SENT, 'Sent'),
        (STATUS_FAILED, 'Failed'),
    ]

    organization = models.ForeignKey(**ORG_FK)
    social_content_item = models.ForeignKey(
        SocialContentItem,
        on_delete=models.CASCADE,
        related_name='automation_deliveries',
    )
    external_event_id = models.CharField(max_length=255)
    recipient_id = models.CharField(max_length=128, blank=True)
    trigger_text = models.TextField(blank=True)
    reply_text = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    response_message_id = models.CharField(max_length=255, blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['organization', 'external_event_id'],
                name='uniq_social_automation_event_per_org',
            ),
        ]

    def __str__(self):
        return f'{self.external_event_id}: {self.status}'


class MediaFingerprint(models.Model):
    """Perceptual hashes used to match screenshots and reposted media."""

    KIND_PHASH = 'phash'
    KIND_DHASH = 'dhash'
    KIND_AHASH = 'ahash'
    KIND_CENTER_PHASH = 'center_phash'
    KIND_COLORHASH = 'colorhash'
    KIND_CHOICES = [
        (KIND_PHASH, 'Perceptual hash'),
        (KIND_DHASH, 'Difference hash'),
        (KIND_AHASH, 'Average hash'),
        (KIND_CENTER_PHASH, 'Center-crop perceptual hash'),
        (KIND_COLORHASH, 'Color hash'),
    ]

    organization = models.ForeignKey(**ORG_FK)
    hotel_media_item = models.ForeignKey(
        HotelMediaItem,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='fingerprints',
    )
    hotel_media_photo = models.ForeignKey(
        HotelMediaPhoto,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='fingerprints',
    )
    social_content_item = models.ForeignKey(
        SocialContentItem,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='fingerprints',
    )
    hash_kind = models.CharField(max_length=30, choices=KIND_CHOICES)
    hash_value = models.CharField(max_length=256)
    bit_length = models.PositiveSmallIntegerField(default=64)
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    frame_second = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    crop_label = models.CharField(max_length=50, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['hash_kind', 'id']
        verbose_name = 'Media Fingerprint'
        verbose_name_plural = 'Media Fingerprints'
        indexes = [
            models.Index(fields=['organization', 'hash_kind']),
            models.Index(fields=['hash_kind', 'hash_value']),
            models.Index(fields=['hotel_media_item']),
            models.Index(fields=['social_content_item']),
        ]

    def __str__(self):
        target = self.social_content_item or self.hotel_media_photo or self.hotel_media_item
        return f'{self.hash_kind}: {target or self.pk}'
