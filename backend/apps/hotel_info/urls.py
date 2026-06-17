from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (
    hotel_profile, prompt_preview,
    room_combinations, room_combination_note,
    room_combination_room_types, create_custom_combination, delete_custom_combination,
    hide_auto_combination,
    HotelProfileLinkViewSet, HotelPolicyViewSet, HotelFAQViewSet, HandoverContactViewSet,
    PlaybookViewSet, RoomPricingViewSet,
)

router = DefaultRouter()
router.register(r'hotel-profile-links', HotelProfileLinkViewSet, basename='hotel-profile-link')
router.register(r'hotel-policies', HotelPolicyViewSet, basename='hotel-policy')
router.register(r'hotel-faqs', HotelFAQViewSet, basename='hotel-faq')
router.register(r'handover-contacts', HandoverContactViewSet, basename='handover-contact')
router.register(r'playbooks', PlaybookViewSet, basename='playbook')
router.register(r'room-pricing', RoomPricingViewSet, basename='room-pricing')

urlpatterns = [
    path('hotel-profile/', hotel_profile, name='hotel-profile'),
    path('ai/prompt-preview/', prompt_preview, name='ai-prompt-preview'),
    path('room-combinations/', room_combinations, name='room-combinations'),
    path('room-combinations/room-types/', room_combination_room_types, name='room-combination-room-types'),
    path('room-combinations/custom/', create_custom_combination, name='room-combination-create-custom'),
    path('room-combinations/custom/<int:pk>/', delete_custom_combination, name='room-combination-delete-custom'),
    path('room-combinations/notes/<int:guest_count>/<int:combination_index>/', room_combination_note, name='room-combination-note'),
    path('room-combinations/hide/<int:guest_count>/<int:combination_index>/', hide_auto_combination, name='room-combination-hide'),
] + router.urls
