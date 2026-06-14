from rest_framework.exceptions import PermissionDenied
from .models import OrganizationMember


class OrganizationQuerysetMixin:
    """
    Automatically scopes querysets to the current organization.

    Superadmins bypass all org filters and see everything.

    The current organization is resolved from:
    1. request.organization (set by middleware or view)
    2. user.current_organization fallback

    Usage:
        class MyViewSet(OrganizationQuerysetMixin, ModelViewSet):
            ...
    """

    def _get_organization(self):
        # Check request-level org (set by middleware or the view itself)
        org = getattr(self.request, 'organization', None)
        if org is not None:
            return org
        # Fallback: user's current_organization field
        user = self.request.user
        org = getattr(user, 'current_organization', None)
        if org is None:
            raise PermissionDenied('No active organization. Please select an organization.')
        # Verify membership (superadmin bypasses)
        if not getattr(user, 'is_superadmin', False):
            if not OrganizationMember.objects.filter(
                organization=org, user=user, is_active=True
            ).exists():
                raise PermissionDenied('You are not a member of this organization.')
        return org

    def get_queryset(self):
        user = self.request.user
        if getattr(user, 'is_superadmin', False):
            return super().get_queryset()
        org = self._get_organization()
        return super().get_queryset().filter(organization=org)

    def perform_create(self, serializer):
        user = self.request.user
        if getattr(user, 'is_superadmin', False):
            serializer.save()
        else:
            org = self._get_organization()
            serializer.save(organization=org)
