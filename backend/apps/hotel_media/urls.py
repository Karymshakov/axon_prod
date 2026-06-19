from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import HotelMediaItemViewSet, HotelMediaPhotoViewSet, MediaFingerprintViewSet, SocialContentItemViewSet

router = DefaultRouter()
router.register(r'hotel-media', HotelMediaItemViewSet, basename='hotel-media')
router.register(r'social-content', SocialContentItemViewSet, basename='social-content')
router.register(r'media-fingerprints', MediaFingerprintViewSet, basename='media-fingerprint')

urlpatterns = router.urls + [
    path('hotel-media/photos/<int:pk>/', HotelMediaPhotoViewSet.as_view({'delete': 'destroy'}), name='hotel-media-photo-delete'),
]
