from django.db.models import Q
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from .models import HotelMediaItem, HotelMediaPhoto, MediaFingerprint, SocialContentItem
from .serializers import HotelMediaItemSerializer, HotelMediaPhotoSerializer, MediaFingerprintSerializer, SocialContentItemSerializer
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

    def _rebuild_item_fingerprints_safely(self, item):
        try:
            from .services import rebuild_hotel_media_item_fingerprints

            rebuild_hotel_media_item_fingerprints(item)
        except Exception:
            # Fingerprints are an acceleration/matching layer. Media CRUD must stay
            # available even while migrations are rolling out or a file cannot be hashed.
            pass

    def perform_create(self, serializer):
        user = self.request.user
        if getattr(user, 'is_superadmin', False):
            org = getattr(user, 'current_organization', None)
            item = serializer.save(organization=org) if org else serializer.save()
        else:
            item = serializer.save(organization=self._get_organization())
        self._rebuild_item_fingerprints_safely(item)

    def perform_update(self, serializer):
        item = serializer.save()
        self._rebuild_item_fingerprints_safely(item)

    @action(detail=True, methods=['post'])
    def increment_ai_sends(self, request, pk=None):
        item = self.get_object()
        item.ai_send_count += 1
        item.save(update_fields=['ai_send_count'])
        return Response({'ai_send_count': item.ai_send_count})

    @action(detail=True, methods=['post'], url_path='rebuild-fingerprints')
    def rebuild_fingerprints(self, request, pk=None):
        from .services import rebuild_hotel_media_item_fingerprints

        item = self.get_object()
        count = rebuild_hotel_media_item_fingerprints(item)
        return Response({'fingerprints_created': count})

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
            photo = HotelMediaPhoto.objects.create(item=item, file=compressed, order=next_order)
            try:
                from .services import rebuild_hotel_media_photo_fingerprints

                rebuild_hotel_media_photo_fingerprints(photo)
            except Exception:
                pass
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


class SocialContentItemViewSet(OrganizationQuerysetMixin, viewsets.ModelViewSet):
    queryset = SocialContentItem.objects.all()
    serializer_class = SocialContentItemSerializer
    filterset_fields = ['platform', 'content_type', 'status', 'review_status', 'category', 'room_category']

    def perform_create(self, serializer):
        serializer.save(organization=self._get_organization(), source=SocialContentItem.SOURCE_MANUAL)

    def get_queryset(self):
        queryset = super().get_queryset().exclude(status=SocialContentItem.STATUS_DELETED)
        search = self.request.query_params.get('search')
        needs_review = self.request.query_params.get('needs_review')

        if search:
            queryset = queryset.filter(
                Q(title__icontains=search)
                | Q(caption__icontains=search)
                | Q(external_id__icontains=search)
                | Q(reply_guidance__icontains=search)
                | Q(manager_notes__icontains=search)
            )
        if needs_review in {'1', 'true', 'yes'}:
            queryset = queryset.filter(review_status=SocialContentItem.REVIEW_NEEDS_REVIEW)
        return queryset.order_by('-posted_at', '-created_at')

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.status = SocialContentItem.STATUS_DELETED
        instance.is_active = False
        instance.save(update_fields=['status', 'is_active'])
        instance.fingerprints.all().delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'], url_path='mark-reviewed')
    def mark_reviewed(self, request, pk=None):
        item = self.get_object()
        item.review_status = SocialContentItem.REVIEW_REVIEWED
        item.save(update_fields=['review_status', 'updated_at'])
        serializer = self.get_serializer(item)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='rebuild-fingerprints')
    def rebuild_fingerprints(self, request, pk=None):
        from .services import rebuild_social_content_fingerprints

        item = self.get_object()
        count = rebuild_social_content_fingerprints(item)
        return Response({'fingerprints_created': count})

    @action(detail=False, methods=['post'], url_path='sync-instagram')
    def sync_instagram(self, request):
        from .services import sync_instagram_social_content

        result = sync_instagram_social_content(organization=self._get_organization())
        return Response(result)


class MediaFingerprintViewSet(OrganizationQuerysetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = MediaFingerprint.objects.select_related(
        'hotel_media_item',
        'hotel_media_photo',
        'social_content_item',
    )
    serializer_class = MediaFingerprintSerializer
    filterset_fields = ['hash_kind', 'hotel_media_item', 'social_content_item']
