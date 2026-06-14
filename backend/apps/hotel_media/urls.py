from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import HotelMediaItemViewSet, HotelMediaPhotoViewSet

router = DefaultRouter()
router.register(r'hotel-media', HotelMediaItemViewSet, basename='hotel-media')

urlpatterns = router.urls + [
    path('hotel-media/photos/<int:pk>/', HotelMediaPhotoViewSet.as_view({'delete': 'destroy'}), name='hotel-media-photo-delete'),
]
