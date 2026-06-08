"""URL configuration for the project."""
from django.conf import settings
from django.contrib import admin
from django.urls import path, include, re_path
from django.views.generic import RedirectView
from django.views.static import serve
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.audit import views as audit_views


@api_view(['GET'])
@permission_classes([AllowAny])
def health(request):
    return Response({
        'status': 'ok',
        'message': 'Hello from Django!',
    })


urlpatterns = [
    # Redirect old /admin/users URL to /portal/users (avoids Django admin interception)
    path('admin/users', RedirectView.as_view(url='/portal/users', permanent=True)),
    path('admin/', admin.site.urls),
    path('api/health/', health, name='health'),
    path('api/auth/', include('apps.users.urls')),
    path('api/organizations/', include('apps.organizations.urls')),
    path('api/', include('apps.leads.urls')),
    path('api/', include('apps.hotel_media.urls')),
    path('api/', include('apps.hotel_info.urls')),
    path('api/', include('apps.flows.urls')),
    path('api/admin/audit-logs/', audit_views.admin_audit_logs, name='admin-audit-logs'),
    # Serve media files unconditionally (works regardless of DEBUG setting)
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]

# API documentation - only available in DEBUG mode
if settings.DEBUG:
    from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

    urlpatterns += [
        path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
        path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    ]
