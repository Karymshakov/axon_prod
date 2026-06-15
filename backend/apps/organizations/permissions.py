from rest_framework.permissions import BasePermission
from .models import OrganizationMember


class IsOrganizationMember(BasePermission):
    """User must be an active member of the current organization."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if getattr(request.user, 'is_superadmin', False):
            return True
        org = getattr(request, 'organization', None)
        if org is None:
            return False
        return OrganizationMember.objects.filter(
            organization=org, user=request.user, is_active=True
        ).exists()


class IsOrganizationAdmin(BasePermission):
    """User must be owner or admin of the current organization."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if getattr(request.user, 'is_superadmin', False):
            return True
        org = getattr(request, 'organization', None)
        if org is None:
            return False
        return OrganizationMember.objects.filter(
            organization=org,
            user=request.user,
            role__in=[OrganizationMember.Role.OWNER, OrganizationMember.Role.ADMIN],
            is_active=True,
        ).exists()


class IsOrganizationOwner(BasePermission):
    """User must be owner of the current organization."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if getattr(request.user, 'is_superadmin', False):
            return True
        org = getattr(request, 'organization', None)
        if org is None:
            return False
        return OrganizationMember.objects.filter(
            organization=org,
            user=request.user,
            role=OrganizationMember.Role.OWNER,
            is_active=True,
        ).exists()


class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and getattr(request.user, 'is_superadmin', False)
        )
