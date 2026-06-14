from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import PermissionDenied

from apps.organizations.models import OrganizationMember
from .models import User
from .serializers import AdminUserSerializer


class IsAdminUser(IsAuthenticated):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        user = request.user
        if getattr(user, 'is_superadmin', False) or getattr(user, 'is_admin', False):
            return True
        org = getattr(user, 'current_organization', None)
        if org is None:
            return False
        return OrganizationMember.objects.filter(
            organization=org,
            user=user,
            role__in=[OrganizationMember.Role.OWNER, OrganizationMember.Role.ADMIN],
            is_active=True,
        ).exists()


PORTAL_ROLE_ADMIN = 'admin'
PORTAL_ROLE_MANAGER = 'manager'
LEGACY_PORTAL_ROLE_SUPPORT = User.Role.SUPPORT
PORTAL_ROLES = {PORTAL_ROLE_ADMIN, PORTAL_ROLE_MANAGER, LEGACY_PORTAL_ROLE_SUPPORT}


def _get_current_organization(request):
    org = getattr(request.user, 'current_organization', None)
    if org is None:
        raise PermissionDenied('No active organization. Please select an organization first.')
    if not getattr(request.user, 'is_superadmin', False):
        is_member = OrganizationMember.objects.filter(
            organization=org,
            user=request.user,
            is_active=True,
        ).exists()
        if not is_member:
            raise PermissionDenied('You are not a member of this organization.')
    return org


def _member_to_portal_role(member):
    if member.role in [OrganizationMember.Role.OWNER, OrganizationMember.Role.ADMIN]:
        return PORTAL_ROLE_ADMIN
    return PORTAL_ROLE_MANAGER


def _org_role_from_portal(role):
    return OrganizationMember.Role.ADMIN if role == PORTAL_ROLE_ADMIN else OrganizationMember.Role.MEMBER


def _attach_portal_fields(user, member):
    user._portal_role = _member_to_portal_role(member)
    user._portal_is_active = bool(member.is_active and user.is_active)
    user._portal_member = member
    return user


def _member_queryset(org):
    return OrganizationMember.objects.filter(organization=org).select_related('user')


def _serialize_user(user, member):
    return AdminUserSerializer(_attach_portal_fields(user, member)).data


def _validate_portal_role(role):
    if role not in PORTAL_ROLES:
        return Response({'role': ['Allowed roles: admin, manager.']}, status=status.HTTP_400_BAD_REQUEST)
    return None


@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_stats(request):
    from django.utils import timezone
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    org = _get_current_organization(request)
    members = _member_queryset(org)
    total = members.count()
    active = members.filter(is_active=True, user__is_active=True).count()
    new_this_month = members.filter(user__created_at__gte=month_start).count()

    return Response({
        'total_users': total,
        'active_users': active,
        'new_this_month': new_this_month,
        'role_breakdown': {
            PORTAL_ROLE_ADMIN: members.filter(
                role__in=[OrganizationMember.Role.OWNER, OrganizationMember.Role.ADMIN],
            ).count(),
            PORTAL_ROLE_MANAGER: members.filter(role=OrganizationMember.Role.MEMBER).count(),
        },
    })


@api_view(['GET', 'POST'])
@permission_classes([IsAdminUser])
def admin_users_list(request):
    org = _get_current_organization(request)

    if request.method == 'GET':
        members = _member_queryset(org)

        search = request.query_params.get('search', '')
        if search:
            members = members.filter(Q(user__email__icontains=search) | Q(user__name__icontains=search))

        role = request.query_params.get('role', '')
        if role:
            if role == PORTAL_ROLE_ADMIN:
                members = members.filter(role__in=[OrganizationMember.Role.OWNER, OrganizationMember.Role.ADMIN])
            elif role in [PORTAL_ROLE_MANAGER, LEGACY_PORTAL_ROLE_SUPPORT]:
                members = members.filter(role=OrganizationMember.Role.MEMBER)
            else:
                members = members.none()

        status_filter = request.query_params.get('status', '')
        if status_filter == 'active':
            members = members.filter(is_active=True, user__is_active=True)
        elif status_filter == 'inactive':
            members = members.filter(Q(is_active=False) | Q(user__is_active=False))

        ordering = request.query_params.get('ordering', '-created_at')
        ordering_map = {
            'email': 'user__email',
            '-email': '-user__email',
            'name': 'user__name',
            '-name': '-user__name',
            'created_at': 'user__created_at',
            '-created_at': '-user__created_at',
            'role': 'role',
            '-role': '-role',
        }
        members = members.order_by(ordering_map.get(ordering, '-user__created_at'))

        users = [_attach_portal_fields(member.user, member) for member in members]
        return Response(AdminUserSerializer(users, many=True).data)

    role = request.data.get('role', PORTAL_ROLE_MANAGER)
    role_error = _validate_portal_role(role)
    if role_error:
        return role_error

    email = (request.data.get('email') or '').strip().lower()
    name = (request.data.get('name') or '').strip()
    password = request.data.get('password') or ''
    if not email:
        return Response({'email': ['Email is required.']}, status=status.HTTP_400_BAD_REQUEST)
    if not name:
        return Response({'name': ['Name is required.']}, status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.filter(email__iexact=email).first()
    if user is None:
        if len(password) < 8:
            return Response({'password': ['Password must be at least 8 characters.']}, status=status.HTTP_400_BAD_REQUEST)
        user = User.objects.create_user(
            email=email,
            password=password,
            name=name,
            role=User.Role.SUPPORT,
        )
    else:
        user.name = name
        user.save(update_fields=['name'])

    member, _ = OrganizationMember.objects.update_or_create(
        organization=org,
        user=user,
        defaults={
            'role': _org_role_from_portal(role),
            'is_active': bool(request.data.get('is_active', True)),
        },
    )

    if user.current_organization_id != org.id:
        user.current_organization = org
        user.save(update_fields=['current_organization'])

    return Response(_serialize_user(user, member), status=status.HTTP_201_CREATED)


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAdminUser])
def admin_user_detail(request, pk):
    org = _get_current_organization(request)
    member = _member_queryset(org).filter(user_id=pk).first()
    if member is None:
        return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
    user = member.user

    if request.method == 'GET':
        return Response(_serialize_user(user, member))

    if request.method == 'PATCH':
        role = request.data.get('role')
        if role is not None:
            role_error = _validate_portal_role(role)
            if role_error:
                return role_error

        if user == request.user:
            if 'is_active' in request.data and not request.data['is_active']:
                return Response({'detail': 'You cannot deactivate your own account.'}, status=status.HTTP_400_BAD_REQUEST)
            if role is not None and role != User.Role.ADMIN:
                return Response({'detail': 'You cannot change your own role.'}, status=status.HTTP_400_BAD_REQUEST)

        if member.role == OrganizationMember.Role.OWNER and role in [PORTAL_ROLE_MANAGER, LEGACY_PORTAL_ROLE_SUPPORT]:
            return Response({'detail': 'Organization owner cannot be demoted here.'}, status=status.HTTP_400_BAD_REQUEST)

        update_fields = []
        if 'name' in request.data:
            user.name = (request.data.get('name') or '').strip()
            update_fields.append('name')
        if 'email' in request.data:
            email = (request.data.get('email') or '').strip().lower()
            if not email:
                return Response({'email': ['Email is required.']}, status=status.HTTP_400_BAD_REQUEST)
            if User.objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
                return Response({'email': ['A user with this email already exists.']}, status=status.HTTP_400_BAD_REQUEST)
            user.email = email
            update_fields.append('email')
        if update_fields:
            user.save(update_fields=update_fields)

        member_update_fields = []
        if role is not None and member.role != OrganizationMember.Role.OWNER:
            member.role = _org_role_from_portal(role)
            member_update_fields.append('role')
        if 'is_active' in request.data:
            member.is_active = bool(request.data.get('is_active'))
            member_update_fields.append('is_active')
        if member_update_fields:
            member.save(update_fields=member_update_fields)
        if user.current_organization_id != org.id:
            user.current_organization = org
            user.save(update_fields=['current_organization'])

        return Response(_serialize_user(user, member))

    # DELETE
    if user == request.user:
        return Response({'detail': 'You cannot remove yourself from the organization.'}, status=status.HTTP_400_BAD_REQUEST)
    if member.role == OrganizationMember.Role.OWNER:
        return Response({'detail': 'Organization owner cannot be removed here.'}, status=status.HTTP_400_BAD_REQUEST)
    member.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)
