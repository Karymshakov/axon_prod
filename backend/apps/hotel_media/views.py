from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from .models import HotelMediaItem, HotelMediaPhoto
from .serializers import HotelMediaItemSerializer, HotelMediaPhotoSerializer
from .utils import compress_image_for_telegram
from apps.organizations.mixins import OrganizationQuerysetMixin


class HotelMediaItemViewSet(OrganizationQuerysetMixin, viewsets.ModelViewSet):
    queryset = HotelMediaItem.objects.filter(is_active=True)
    serializer_class = HotelMediaItemSerializer
    filterset_fields = ['media_type', 'category', 'is_active']

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def get_queryset(self):
        user = self.request.user
        queryset = HotelMediaItem.objects.filter(is_active=True)
        if not getattr(user, 'is_superadmin', False):
            org = self._get_organization()
            queryset = queryset.filter(organization=org)

        media_type = self.request.query_params.get('media_type')
        category = self.request.query_params.get('category')
        search = self.request.query_params.get('search')

        if media_type:
            queryset = queryset.filter(media_type=media_type)
        if category:
            queryset = queryset.filter(category=category)
        if search:
            queryset = (
                queryset.filter(title__icontains=search)
                | queryset.filter(description__icontains=search)
                | queryset.filter(tags__icontains=search)
            )
        return queryset.order_by('-created_at')

    @action(detail=True, methods=['post'])
    def increment_ai_sends(self, request, pk=None):
        item = self.get_object()
        item.ai_send_count += 1
        item.save(update_fields=['ai_send_count'])
        return Response({'ai_send_count': item.ai_send_count})

    @action(detail=True, methods=['post'], url_path='add-photos',
            parser_classes=[MultiPartParser, FormParser])
    def add_photos(self, request, pk=None):
        item = self.get_object()
        files = request.FILES.getlist('files')
        if not files:
            return Response({'detail': 'No files provided.'}, status=status.HTTP_400_BAD_REQUEST)

        next_order = item.photos.count()
        for f in files:
            compressed = compress_image_for_telegram(f, filename=f.name)
            HotelMediaPhoto.objects.create(item=item, file=compressed, order=next_order)
            next_order += 1

        serializer = HotelMediaItemSerializer(item, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class HotelMediaPhotoViewSet(viewsets.GenericViewSet):
    queryset = HotelMediaPhoto.objects.all()
    serializer_class = HotelMediaPhotoSerializer

    def destroy(self, request, pk=None):
        photo = self.get_object()
        photo.file.delete(save=False)
        photo.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
