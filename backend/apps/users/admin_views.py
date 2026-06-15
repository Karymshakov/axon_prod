from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models import User
from .serializers import AdminUserSerializer, AdminUserCreateSerializer, AdminUserUpdateSerializer


class IsAdminUser(IsAuthenticated):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and getattr(request.user, 'is_admin', False)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_stats(request):
    from django.utils import timezone
    from datetime import timedelta
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    total = User.objects.count()
    active = User.objects.filter(is_active=True).count()
    new_this_month = User.objects.filter(created_at__gte=month_start).count()

    role_breakdown = {}
    for role_value, role_label in User.Role.choices:
        role_breakdown[role_value] = User.objects.filter(role=role_value).count()

    return Response({
        'total_users': total,
        'active_users': active,
        'new_this_month': new_this_month,
        'role_breakdown': role_breakdown,
    })


@api_view(['GET', 'POST'])
@permission_classes([IsAdminUser])
def admin_users_list(request):
    if request.method == 'GET':
        qs = User.objects.all()

        search = request.query_params.get('search', '')
        if search:
            qs = qs.filter(Q(email__icontains=search) | Q(name__icontains=search))

        role = request.query_params.get('role', '')
        if role:
            qs = qs.filter(role=role)

        status_filter = request.query_params.get('status', '')
        if status_filter == 'active':
            qs = qs.filter(is_active=True)
        elif status_filter == 'inactive':
            qs = qs.filter(is_active=False)

        ordering = request.query_params.get('ordering', '-created_at')
        allowed_orderings = ['email', '-email', 'name', '-name', 'created_at', '-created_at', 'role', '-role']
        if ordering in allowed_orderings:
            qs = qs.order_by(ordering)

        return Response(AdminUserSerializer(qs, many=True).data)

    # POST — create new user
    serializer = AdminUserCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()
    return Response(AdminUserSerializer(user).data, status=status.HTTP_201_CREATED)


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAdminUser])
def admin_user_detail(request, pk):
    try:
        user = User.objects.get(pk=pk)
    except User.DoesNotExist:
        return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        return Response(AdminUserSerializer(user).data)

    if request.method == 'PATCH':
        # Prevent admin from deactivating or demoting themselves
        if user == request.user:
            if 'is_active' in request.data and not request.data['is_active']:
                return Response({'detail': 'You cannot deactivate your own account.'}, status=status.HTTP_400_BAD_REQUEST)
            if 'role' in request.data and request.data['role'] != User.Role.ADMIN:
                return Response({'detail': 'You cannot change your own role.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = AdminUserUpdateSerializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(AdminUserSerializer(user).data)

    # DELETE
    if user == request.user:
        return Response({'detail': 'You cannot delete your own account.'}, status=status.HTTP_400_BAD_REQUEST)
    user.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)
