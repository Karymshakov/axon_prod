from rest_framework import serializers
from .models import (
    HotelProfile, HotelProfileLink, HotelPolicy, HotelFAQ, HandoverContact,
    Playbook, RoomPricing, RoomCombinationNote,
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
