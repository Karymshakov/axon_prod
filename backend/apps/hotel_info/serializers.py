from rest_framework import serializers
from .models import (
    HotelProfile, HotelProfileLink, HotelPolicy, HotelFAQ, HandoverContact,
    Playbook, RoomPricing, RoomCombinationNote, ReplyTemplateCategory, ReplyTemplate,
    AutomationMessageTemplate, BookingRules,
)


class HotelProfileLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = HotelProfileLink
        fields = ['id', 'label', 'url', 'order']


class HotelProfileSerializer(serializers.ModelSerializer):
    links = HotelProfileLinkSerializer(many=True, read_only=True)

    class Meta:
        model = HotelProfile
        fields = ['hotel_name', 'website', 'description', 'address', 'directions', 'links', 'updated_at']
        read_only_fields = ['links', 'updated_at']


class HotelPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = HotelPolicy
        fields = ['id', 'label', 'emoji', 'value', 'description', 'order']


class HotelFAQSerializer(serializers.ModelSerializer):
    class Meta:
        model = HotelFAQ
        fields = ['id', 'question', 'answer', 'order']


class HandoverContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = HandoverContact
        fields = ['id', 'name', 'phone', 'escalate_when', 'order']


class PlaybookSerializer(serializers.ModelSerializer):
    class Meta:
        model = Playbook
        fields = [
            'id', 'name', 'trigger_description', 'instructions', 'content',
            'is_active', 'expires_at', 'order', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class RoomCombinationNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = RoomCombinationNote
        fields = ['id', 'guest_count', 'combination_index', 'note', 'combination_type', 'is_custom', 'rooms', 'updated_at']
        read_only_fields = ['id', 'updated_at']


class RoomPricingSerializer(serializers.ModelSerializer):
    def validate_guest_type(self, value):
        if value == 'family':
            raise serializers.ValidationError(
                'Family inventory is request-only and cannot be sold automatically.'
            )
        return value

    class Meta:
        model = RoomPricing
        fields = [
            'id',
            'kategoria_nomera',
            'kolichestvo_chelovek',
            'guest_type',
            'deystvitelno_s',
            'deystvitelno_do',
            'dni_nedeli',
            'standartny_tarif',
            's_zavtrakom',
            'polupansion',
            'polny_pansion',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ReplyTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReplyTemplate
        fields = ['id', 'category', 'title', 'text', 'channel', 'tags', 'order', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class ReplyTemplateCategorySerializer(serializers.ModelSerializer):
    templates = ReplyTemplateSerializer(many=True, read_only=True)

    class Meta:
        model = ReplyTemplateCategory
        fields = ['id', 'name', 'order', 'is_active', 'templates', 'created_at', 'updated_at']
        read_only_fields = ['id', 'templates', 'created_at', 'updated_at']


class AutomationMessageTemplateSerializer(serializers.ModelSerializer):
    event_label = serializers.CharField(source='get_event_key_display', read_only=True)
    language_label = serializers.CharField(source='get_language_display', read_only=True)

    class Meta:
        model = AutomationMessageTemplate
        fields = [
            'id', 'event_key', 'event_label', 'language', 'language_label',
            'channel', 'text', 'is_active', 'updated_at',
        ]
        read_only_fields = ['id', 'event_label', 'language_label', 'updated_at']


class BookingRulesSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookingRules
        fields = [
            'child_free_max_age',
            'child_free_requires_no_bed',
            'family_rooms_self_service_enabled',
            'followup_delay_minutes',
            'updated_at',
        ]
        read_only_fields = ['family_rooms_self_service_enabled', 'updated_at']

