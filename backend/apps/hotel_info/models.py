from django.db import models
from django.utils import timezone

ORG_FK = dict(
    to='organizations.Organization',
    on_delete=models.CASCADE,
    null=True,
    blank=True,
    related_name='+',
    db_index=True,
)


class HotelProfile(models.Model):
    """Singleton — basic hotel info the AI uses for introductions and general queries."""

    organization = models.ForeignKey(**ORG_FK)
    hotel_name = models.CharField(max_length=255, blank=True)
    website = models.CharField(max_length=500, blank=True)
    description = models.TextField(blank=True, help_text='Short intro the AI uses when guests ask about the hotel.')
    address = models.CharField(max_length=500, blank=True)
    directions = models.TextField(blank=True, help_text='Turn-by-turn directions the AI shares when guests ask how to get here.')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Hotel Profile'
        verbose_name_plural = 'Hotel Profile'

    def __str__(self):
        return self.hotel_name or 'Hotel Profile'

    def save(self, *args, **kwargs):
        if not self.pk and HotelProfile.objects.filter(organization=self.organization).exists():
            raise ValueError('Only one HotelProfile can exist per organization')
        super().save(*args, **kwargs)

    @classmethod
    def get_profile(cls, org=None):
        if org is not None:
            if not hasattr(org, "pk"):
                return None  # sentinel: user has no org set
            obj, _ = cls.objects.get_or_create(organization=org)
            return obj
        return cls.objects.first()


class HotelProfileLink(models.Model):
    """Shareable links attached to the hotel profile (Google Maps, booking page, etc.)."""

    profile = models.ForeignKey(HotelProfile, on_delete=models.CASCADE, related_name='links')
    label = models.CharField(max_length=100)
    url = models.CharField(max_length=500)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f'{self.label}: {self.url}'


class HotelPolicy(models.Model):
    """A single hotel rule or policy the AI can quote to guests."""

    organization = models.ForeignKey(**ORG_FK)
    label = models.CharField(max_length=100, help_text='e.g. Animals / Pets, Parking, Smoking')
    emoji = models.CharField(max_length=10, blank=True, help_text='Optional emoji prefix')
    value = models.CharField(max_length=255, help_text='e.g. Allowed, Paid parking available, Not allowed')
    description = models.TextField(blank=True, help_text='Optional detail the AI can share when guests ask follow-up questions.')
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']
        verbose_name = 'Hotel Policy'
        verbose_name_plural = 'Hotel Policies'

    def __str__(self):
        return f'{self.label}: {self.value}'


class HotelFAQ(models.Model):
    """Frequently asked question with a prepared answer for the AI."""

    organization = models.ForeignKey(**ORG_FK)
    question = models.TextField()
    answer = models.TextField()
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']
        verbose_name = 'Hotel FAQ'
        verbose_name_plural = 'Hotel FAQs'

    def __str__(self):
        return self.question[:80]


class HandoverContact(models.Model):
    """Manager / staff contact the AI can share when it cannot help directly."""

    organization = models.ForeignKey(**ORG_FK)
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=50)
    escalate_when = models.CharField(max_length=500, blank=True, help_text='Describe when this person should be contacted.')
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']
        verbose_name = 'Handover Contact'
        verbose_name_plural = 'Handover Contacts'

    def __str__(self):
        return f'{self.name} ({self.phone})'


class RoomPricing(models.Model):
    """
    A single pricing row for a room category + guest count combination.
    Structured pricing the AI can quote accurately.
    """

    GUEST_TYPE_ANY = 'any'
    GUEST_TYPE_FAMILY = 'family'
    GUEST_TYPE_CHOICES = [
        ('any', 'Any'),
        ('family', 'Family'),
    ]

    organization = models.ForeignKey(**ORG_FK)
    kategoria_nomera = models.CharField(max_length=100, help_text='Room category, e.g. Стандарт, Комфорт')
    kolichestvo_chelovek = models.IntegerField(help_text='Number of guests (1–4)')
    guest_type = models.CharField(
        max_length=10,
        choices=GUEST_TYPE_CHOICES,
        default='any',
        help_text='any = standard/comfort rooms; family = family rooms (only suggested when kids are present)',
    )
    deystvitelno_s = models.DateField(null=True, blank=True, help_text='Valid from date')
    deystvitelno_do = models.DateField(null=True, blank=True, help_text='Valid until date')
    dni_nedeli = models.JSONField(default=list, blank=True, help_text='List of Russian weekday names')
    standartny_tarif = models.DecimalField(max_digits=10, decimal_places=0, null=True, blank=True, help_text='Base rate KGS')
    s_zavtrakom = models.DecimalField(max_digits=10, decimal_places=0, null=True, blank=True, help_text='With breakfast KGS')
    polupansion = models.DecimalField(max_digits=10, decimal_places=0, null=True, blank=True, help_text='Half board KGS')
    polny_pansion = models.DecimalField(max_digits=10, decimal_places=0, null=True, blank=True, help_text='Full board KGS')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['id']
        verbose_name = 'Room Pricing'
        verbose_name_plural = 'Room Pricing'

    def __str__(self):
        return f'{self.kategoria_nomera} × {self.kolichestvo_chelovek} чел.'


class RoomCombinationNote(models.Model):
    """Per-combination metadata: notes, type overrides, and custom user-added combinations."""
    guest_count = models.IntegerField(help_text='Number of guests (1–10)')
    combination_index = models.IntegerField(help_text='0-based index within the guest count group')
    note = models.TextField(blank=True)
    combination_type = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        choices=[('Основной', 'Основной'), ('Альтернатива', 'Альтернатива'), ('Семейный', 'Семейный')],
        help_text='Manually set type; null = auto-assigned from pricing',
    )
    is_custom = models.BooleanField(
        default=False,
        help_text='True for user-added combinations; False for auto-generated ones',
    )
    is_hidden = models.BooleanField(
        default=False,
        help_text='True hides this combination from the API and AI responses',
    )
    rooms = models.JSONField(
        default=None,
        null=True,
        blank=True,
        help_text='List of room type strings for custom combinations',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('guest_count', 'combination_index')]
        ordering = ['guest_count', 'combination_index']
        verbose_name = 'Room Combination Note'
        verbose_name_plural = 'Room Combination Notes'

    def __str__(self):
        return f'{self.guest_count} guests / combo {self.combination_index}'


class Playbook(models.Model):
    """Topic-specific context injected into AI responses when the topic is detected."""

    organization = models.ForeignKey(**ORG_FK)
    name = models.CharField(max_length=100)
    trigger_description = models.TextField(
        blank=True,
        help_text="Describe in plain language when this playbook should activate.",
    )
    instructions = models.TextField(
        blank=True,
        help_text="How the AI should respond in this scenario.",
    )
    content = models.TextField(
        blank=True,
        help_text="Additional facts, tables, or examples (markdown supported).",
    )
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Optional expiry. Playbook stops being injected into AI once this date/time passes.",
    )
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return self.name
