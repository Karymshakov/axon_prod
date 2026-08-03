from rest_framework import serializers
from django.contrib.auth import authenticate

from .models import User


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        request = self.context.get('request')
        user = authenticate(request, username=data['email'], password=data['password'])
        if not user:
            raise serializers.ValidationError('Invalid credentials')
        if not user.is_active:
            raise serializers.ValidationError('Account is inactive')
        data['user'] = user
        return data


class UserSerializer(serializers.ModelSerializer):
    current_organization_id = serializers.IntegerField(
        source='current_organization.id', read_only=True, allow_null=True
    )
    current_organization_slug = serializers.CharField(
        source='current_organization.slug', read_only=True, allow_null=True
    )
    current_organization_name = serializers.CharField(
        source='current_organization.name', read_only=True, allow_null=True
    )

    class Meta:
        model = User
        fields = [
            'id', 'email', 'name', 'is_admin', 'is_superadmin', 'is_active',
            'role', 'language',
            'current_organization_id', 'current_organization_slug', 'current_organization_name',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'is_admin', 'is_active', 'created_at', 'updated_at']


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for the authenticated user to update their own profile."""
    class Meta:
        model = User
        fields = ['language']


class AdminUserSerializer(serializers.ModelSerializer):
    """Read serializer for admin user management."""
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    organization_name = serializers.CharField(source='current_organization.name', read_only=True, default=None)
    organization_role = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'email', 'name', 'role', 'role_display',
            'is_active', 'is_admin', 'last_login', 'created_at',
            'organization_name', 'organization_role',
        ]
        read_only_fields = fields

    def get_organization_role(self, obj):
        if not obj.current_organization_id:
            return None
        membership = obj.org_memberships.filter(organization_id=obj.current_organization_id).first()
        return membership.role if membership else None


class AdminUserCreateSerializer(serializers.ModelSerializer):
    """Write serializer for creating a user from the admin portal.

    New users are attached to the creating admin's current organization so they
    see the same leads/playbooks/etc immediately instead of landing on an empty
    "new account" (rather than requiring a separate org-invite step).
    """
    password = serializers.CharField(write_only=True, required=True, min_length=8)

    class Meta:
        model = User
        fields = ['email', 'name', 'role', 'is_active', 'password']

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('A user with this email already exists.')
        return value.lower()

    def create(self, validated_data):
        from django.db import transaction
        from apps.organizations.models import OrganizationMember

        request = self.context.get('request')
        creator = getattr(request, 'user', None)
        organization = getattr(creator, 'current_organization', None)
        if organization is None:
            raise serializers.ValidationError(
                {'detail': 'Your account has no active organization to attach the new user to.'}
            )

        member_role = (
            OrganizationMember.Role.ADMIN
            if validated_data.get('role') == User.Role.ADMIN
            else OrganizationMember.Role.MEMBER
        )

        password = validated_data.pop('password')
        with transaction.atomic():
            user = User(**validated_data)
            user.set_password(password)
            user.current_organization = organization
            user.save()
            OrganizationMember.objects.create(
                organization=organization,
                user=user,
                role=member_role,
            )
        return user


class AdminUserUpdateSerializer(serializers.ModelSerializer):
    """Write serializer for updating a user from the admin portal."""

    class Meta:
        model = User
        fields = ['name', 'email', 'role', 'is_active']
