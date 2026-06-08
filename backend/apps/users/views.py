import io
import json
import zipfile

from django.core.management import call_command
from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from django.utils.text import slugify
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from apps.organizations.models import OrganizationMember

from .serializers import LoginSerializer, UserSerializer, UserProfileSerializer
from .models import User


def _can_export_dev_database(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    if getattr(user, 'is_superadmin', False):
        return True

    organization = getattr(user, 'current_organization', None)
    if organization is None:
        return False

    return OrganizationMember.objects.filter(
        organization=organization,
        user=user,
        role__in=[OrganizationMember.Role.OWNER, OrganizationMember.Role.ADMIN],
        is_active=True,
    ).exists()


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    serializer = LoginSerializer(data=request.data, context={'request': request})
    serializer.is_valid(raise_exception=True)
    user = serializer.validated_data['user']
    refresh = RefreshToken.for_user(user)
    return Response({
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'user': UserSerializer(user).data,
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def refresh_token(request):
    refresh = request.data.get('refresh')
    if not refresh:
        return Response({'detail': 'Refresh token required'}, status=400)
    try:
        token = RefreshToken(refresh)
        return Response({'access': str(token.access_token)})
    except TokenError:
        return Response({'detail': 'Invalid or expired token'}, status=401)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    refresh = request.data.get('refresh')
    if not refresh:
        return Response({'detail': 'Refresh token required'}, status=400)
    try:
        token = RefreshToken(refresh)
        token.blacklist()
        return Response({'detail': 'Logged out'})
    except TokenError:
        return Response({'detail': 'Invalid token'}, status=400)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_me(request):
    return Response(UserSerializer(request.user).data)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_profile(request):
    serializer = UserProfileSerializer(request.user, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(UserSerializer(request.user).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def export_dev_database(request):
    if not _can_export_dev_database(request.user):
        return Response(
            {'detail': 'You do not have permission to export the full development database.'},
            status=403,
        )

    snapshot_buffer = io.StringIO()
    call_command(
        'dumpdata',
        format='json',
        indent=2,
        database='default',
        stdout=snapshot_buffer,
        stderr=io.StringIO(),
    )

    exported_at = timezone.now()
    exported_at_slug = exported_at.strftime('%Y%m%d-%H%M%S')
    fixture_filename = f'omnios-dev-snapshot-{exported_at_slug}.json'
    archive_filename = f'omnios-dev-snapshot-{exported_at_slug}.zip'

    metadata = {
        'exported_at': exported_at.isoformat(),
        'exported_by': request.user.email,
        'format': 'django-json-fixture',
        'restore_command': f'python manage.py loaddata {fixture_filename}',
        'notes': [
            'This snapshot includes development database records and preserved primary/foreign key relationships.',
            'Environment variables, API keys, and other runtime secrets are not included in this archive.',
        ],
    }
    restore_readme = '\n'.join([
        'OmniOS Development Database Snapshot',
        '',
        f'Exported at: {exported_at.isoformat()}',
        f'Exported by: {request.user.email}',
        '',
        'Restore locally:',
        f'1. Place {fixture_filename} somewhere accessible to your local project.',
        f'2. Run: python manage.py loaddata {fixture_filename}',
        '',
        'Important:',
        '- This archive contains database data only.',
        '- Environment variables, API keys, and service credentials must still be configured locally.',
    ])

    archive_buffer = io.BytesIO()
    with zipfile.ZipFile(archive_buffer, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(fixture_filename, snapshot_buffer.getvalue())
        archive.writestr('metadata.json', json.dumps(metadata, indent=2))
        archive.writestr('RESTORE.md', restore_readme)

    response = HttpResponse(archive_buffer.getvalue(), content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{archive_filename}"'
    response['X-Export-Format'] = 'django-json-fixture-zip'
    return response


@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    """
    Create a new user + organization in one atomic transaction.
    Body: { email, password, name, organization_name }
    Returns: { access, refresh, user, organization }
    """
    from rest_framework import authentication
    from apps.organizations.models import Organization, OrganizationMember
    from apps.organizations.serializers import OrganizationSerializer

    email = request.data.get('email', '').strip().lower()
    password = request.data.get('password', '')
    name = request.data.get('name', '').strip()
    org_name = request.data.get('organization_name', '').strip()

    errors = {}
    if not email:
        errors['email'] = 'Email is required.'
    elif User.objects.filter(email=email).exists():
        errors['email'] = 'An account with this email already exists.'
    if not password or len(password) < 8:
        errors['password'] = 'Password must be at least 8 characters.'
    if not org_name:
        errors['organization_name'] = 'Organization name is required.'
    if errors:
        return Response(errors, status=400)

    with transaction.atomic():
        user = User.objects.create_user(email=email, password=password, name=name)

        slug = slugify(org_name)
        base_slug = slug
        counter = 1
        while Organization.objects.filter(slug=slug).exists():
            slug = f'{base_slug}-{counter}'
            counter += 1

        org = Organization.objects.create(
            name=org_name,
            slug=slug,
            owner=user,
            plan=Organization.Plan.FREE,
        )
        OrganizationMember.objects.create(
            organization=org,
            user=user,
            role=OrganizationMember.Role.OWNER,
        )
        user.current_organization = org
        user.save(update_fields=['current_organization'])

    refresh = RefreshToken.for_user(user)
    return Response({
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'user': UserSerializer(user).data,
        'organization': OrganizationSerializer(org, context={'request': request}).data,
    }, status=201)
