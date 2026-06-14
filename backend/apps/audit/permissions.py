from rest_framework.permissions import IsAuthenticated


class IsAdminUser(IsAuthenticated):
    """Allows access only to authenticated admin users."""

    def has_permission(self, request, view):
        return super().has_permission(request, view) and getattr(request.user, 'is_admin', False)
