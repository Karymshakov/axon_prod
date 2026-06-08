from django.contrib.auth import get_user_model
from django.utils.text import slugify
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Organization, OrganizationMember
from .permissions import IsOrganizationAdmin, IsOrganizationOwner, IsSuperAdmin
from .serializers import (
    OrganizationSerializer,
    OrganizationCreateSerializer,
    OrganizationMemberSerializer,
)

User = get_user_model()


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def organization_list_create(request):
    """GET: list orgs the user belongs to. POST: create new org."""
    if request.method == 'GET':
        if getattr(request.user, 'is_superadmin', False):
            orgs = Organization.objects.all()
        else:
            org_ids = OrganizationMember.objects.filter(
                user=request.user, is_active=True
            ).values_list('organization_id', flat=True)
            orgs = Organization.objects.filter(id__in=org_ids)
        serializer = OrganizationSerializer(orgs, many=True, context={'request': request})
        return Response(serializer.data)

    # POST - create
    serializer = OrganizationCreateSerializer(data=request.data, context={'request': request})
    serializer.is_valid(raise_exception=True)
    org = serializer.save()
    return Response(OrganizationSerializer(org, context={'request': request}).data,
                    status=status.HTTP_201_CREATED)


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def organization_detail(request, slug):
    """GET: org details. PATCH: update (admin/owner only)."""
    try:
        org = Organization.objects.get(slug=slug)
    except Organization.DoesNotExist:
        return Response({'error': 'Organization not found'}, status=404)

    # Check membership
    is_super = getattr(request.user, 'is_superadmin', False)
    if not is_super:
        member = OrganizationMember.objects.filter(
            organization=org, user=request.user, is_active=True
        ).first()
        if not member:
            return Response({'error': 'Not a member'}, status=403)

    if request.method == 'GET':
        return Response(OrganizationSerializer(org, context={'request': request}).data)

    # PATCH - admin/owner only
    if not is_super:
        if member.role not in [OrganizationMember.Role.OWNER, OrganizationMember.Role.ADMIN]:
            return Response({'error': 'Admin or owner required'}, status=403)
    serializer = OrganizationSerializer(org, data=request.data, partial=True,
                                         context={'request': request})
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def switch_organization(request, slug):
    """Set user's current_organization."""
    try:
        org = Organization.objects.get(slug=slug)
    except Organization.DoesNotExist:
        return Response({'error': 'Organization not found'}, status=404)

    is_super = getattr(request.user, 'is_superadmin', False)
    if not is_super:
        if not OrganizationMember.objects.filter(
            organization=org, user=request.user, is_active=True
        ).exists():
            return Response({'error': 'Not a member of this organization'}, status=403)

    request.user.current_organization = org
    request.user.save(update_fields=['current_organization'])
    return Response({
        'success': True,
        'organization': OrganizationSerializer(org, context={'request': request}).data,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def organization_members(request, slug):
    try:
        org = Organization.objects.get(slug=slug)
    except Organization.DoesNotExist:
        return Response({'error': 'Organization not found'}, status=404)

    is_super = getattr(request.user, 'is_superadmin', False)
    if not is_super and not OrganizationMember.objects.filter(
        organization=org, user=request.user, is_active=True
    ).exists():
        return Response({'error': 'Not a member'}, status=403)

    members = org.members.filter(is_active=True).select_related('user')
    return Response(OrganizationMemberSerializer(members, many=True).data)


@api_view(['PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def organization_member_detail(request, slug, user_id):
    try:
        org = Organization.objects.get(slug=slug)
    except Organization.DoesNotExist:
        return Response({'error': 'Organization not found'}, status=404)

    is_super = getattr(request.user, 'is_superadmin', False)
    if not is_super:
        actor = OrganizationMember.objects.filter(
            organization=org, user=request.user, is_active=True
        ).first()
        if not actor or actor.role not in [OrganizationMember.Role.OWNER, OrganizationMember.Role.ADMIN]:
            return Response({'error': 'Admin or owner required'}, status=403)

    try:
        member = OrganizationMember.objects.get(organization=org, user_id=user_id)
    except OrganizationMember.DoesNotExist:
        return Response({'error': 'Member not found'}, status=404)

    if request.method == 'PATCH':
        new_role = request.data.get('role')
        if new_role not in [r.value for r in OrganizationMember.Role]:
            return Response({'error': 'Invalid role'}, status=400)
        member.role = new_role
        member.save(update_fields=['role'])
        return Response(OrganizationMemberSerializer(member).data)

    # DELETE - remove member
    if member.role == OrganizationMember.Role.OWNER:
        return Response({'error': 'Cannot remove the owner'}, status=400)
    member.is_active = False
    member.save(update_fields=['is_active'])
    return Response({'success': True})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def invite_member(request, slug):
    """Invite a user by email. If user exists, add them. Otherwise return invite token (future)."""
    try:
        org = Organization.objects.get(slug=slug)
    except Organization.DoesNotExist:
        return Response({'error': 'Organization not found'}, status=404)

    is_super = getattr(request.user, 'is_superadmin', False)
    if not is_super:
        actor = OrganizationMember.objects.filter(
            organization=org, user=request.user, is_active=True
        ).first()
        if not actor or actor.role not in [OrganizationMember.Role.OWNER, OrganizationMember.Role.ADMIN]:
            return Response({'error': 'Admin or owner required'}, status=403)

    email = request.data.get('email', '').strip().lower()
    role = request.data.get('role', OrganizationMember.Role.MEMBER)
    if not email:
        return Response({'error': 'Email is required'}, status=400)

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response({'error': 'User not found. Self-registration coming soon.'}, status=404)

    member, created = OrganizationMember.objects.get_or_create(
        organization=org, user=user,
        defaults={'role': role, 'is_active': True}
    )
    if not created:
        member.is_active = True
        member.role = role
        member.save(update_fields=['is_active', 'role'])

    # Set current_organization if the invited user doesn't have one set yet
    if not user.current_organization:
        user.current_organization = org
        user.save(update_fields=['current_organization'])

    return Response({
        'success': True,
        'created': created,
        'member': OrganizationMemberSerializer(member).data,
    }, status=201 if created else 200)


# ── Owner: delete organization ──────────────────────────────────────────────

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_organization(request, slug):
    """Delete an organization. Owner only."""
    try:
        org = Organization.objects.get(slug=slug)
    except Organization.DoesNotExist:
        return Response({'error': 'Organization not found'}, status=404)

    is_super = getattr(request.user, 'is_superadmin', False)
    if not is_super:
        member = OrganizationMember.objects.filter(
            organization=org, user=request.user, is_active=True,
            role=OrganizationMember.Role.OWNER,
        ).first()
        if not member:
            return Response({'error': 'Owner access required'}, status=403)

    org.delete()
    return Response({'success': True})


# ── Superadmin endpoints ────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsSuperAdmin])
def superadmin_orgs(request):
    if request.method == 'GET':
        orgs = Organization.objects.all().order_by('-created_at')
        return Response(OrganizationSerializer(orgs, many=True, context={'request': request}).data)

    # POST — create org manually
    from django.utils.text import slugify as _slugify
    name = request.data.get('name', '').strip()
    owner_email = request.data.get('owner_email', '').strip().lower()
    plan = request.data.get('plan', Organization.Plan.FREE)

    if not name:
        return Response({'error': 'name is required'}, status=400)
    try:
        owner = User.objects.get(email=owner_email)
    except User.DoesNotExist:
        return Response({'error': f'User {owner_email} not found'}, status=400)

    slug = _slugify(name)
    base = slug
    counter = 1
    while Organization.objects.filter(slug=slug).exists():
        slug = f'{base}-{counter}'
        counter += 1

    org = Organization.objects.create(name=name, slug=slug, owner=owner, plan=plan)
    OrganizationMember.objects.create(organization=org, user=owner, role=OrganizationMember.Role.OWNER)
    if not owner.current_organization:
        owner.current_organization = org
        owner.save(update_fields=['current_organization'])
    return Response(OrganizationSerializer(org, context={'request': request}).data, status=201)


@api_view(['GET', 'PATCH'])
@permission_classes([IsSuperAdmin])
def superadmin_org_detail(request, slug):
    """Detail + update for a specific org."""
    try:
        org = Organization.objects.get(slug=slug)
    except Organization.DoesNotExist:
        return Response({'error': 'Organization not found'}, status=404)

    if request.method == 'GET':
        from django.db.models import Count
        data = OrganizationSerializer(org, context={'request': request}).data
        # Add usage stats
        data['stats'] = {
            'lead_count': org.leads.count() if hasattr(org, 'leads') else 0,
            'member_count': org.members.filter(is_active=True).count(),
        }
        return Response(data)

    # PATCH — update plan, is_active, name
    allowed_fields = {'plan', 'is_active', 'name'}
    update_data = {k: v for k, v in request.data.items() if k in allowed_fields}
    serializer = OrganizationSerializer(org, data=update_data, partial=True, context={'request': request})
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsSuperAdmin])
def superadmin_impersonate(request, user_id):
    """Return a JWT access token scoped to the target user."""
    from rest_framework_simplejwt.tokens import RefreshToken
    try:
        target = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=404)
    refresh = RefreshToken.for_user(target)
    return Response({
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'user_id': target.id,
        'email': target.email,
    })
