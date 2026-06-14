from rest_framework import serializers
from django.contrib.auth import authenticate

from apps.organizations.models import OrganizationMember

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
    role = serializers.SerializerMethodField()
    role_display = serializers.SerializerMethodField()
    current_organization_id = serializers.IntegerField(
        source='current_organization.id', read_only=True, allow_null=True
    )
    current_organization_slug = serializers.CharField(
        source='current_organization.slug', read_only=True, allow_null=True
    )
    current_organization_name = serializers.CharField(
        source='current_organization.name', read_only=True, allow_null=True
    )
    current_organization_role = serializers.SerializerMethodField()

    def get_current_organization_role(self, obj):
        member = self._get_current_member(obj)
        return member.role if member else None

    def _get_current_member(self, obj):
        org = getattr(obj, 'current_organization', None)
        if not org:
            return None
        return OrganizationMember.objects.filter(
            organization=org,
            user=obj,
            is_active=True,
        ).first()

    def get_role(self, obj):
        if getattr(obj, 'is_superadmin', False) or getattr(obj, 'is_admin', False):
            return User.Role.ADMIN
        member = self._get_current_member(obj)
        if member and member.role in [OrganizationMember.Role.OWNER, OrganizationMember.Role.ADMIN]:
            return User.Role.ADMIN
        return 'manager'

    def get_role_display(self, obj):
        return 'Администратор' if self.get_role(obj) == User.Role.ADMIN else 'Менеджер'

    class Meta:
        model = User
        fields = [
            'id', 'email', 'name', 'is_admin', 'is_superadmin', 'is_active',
            'role', 'role_display', 'language',
            'current_organization_id', 'current_organization_slug', 'current_organization_name',
            'current_organization_role',
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
    role = serializers.SerializerMethodField()
    role_display = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()
    organization_id = serializers.SerializerMethodField()
    organization_slug = serializers.SerializerMethodField()
    organization_name = serializers.SerializerMethodField()
    organization_role = serializers.SerializerMethodField()

    def get_role(self, obj):
        return getattr(obj, '_portal_role', None) or obj.role

    def get_role_display(self, obj):
        role = self.get_role(obj)
        return 'Администратор' if role == User.Role.ADMIN else 'Менеджер'

    def get_is_active(self, obj):
        return getattr(obj, '_portal_is_active', obj.is_active)

    def _get_member(self, obj):
        return getattr(obj, '_portal_member', None)

    def get_organization_id(self, obj):
        member = self._get_member(obj)
        return member.organization_id if member else None

    def get_organization_slug(self, obj):
        member = self._get_member(obj)
        return member.organization.slug if member else None

    def get_organization_name(self, obj):
        member = self._get_member(obj)
        return member.organization.name if member else None

    def get_organization_role(self, obj):
        member = self._get_member(obj)
        return member.role if member else None

    class Meta:
        model = User
        fields = [
            'id', 'email', 'name', 'role', 'role_display',
            'is_active', 'is_admin',
            'organization_id', 'organization_slug', 'organization_name', 'organization_role',
            'last_login', 'created_at',
        ]
        read_only_fields = fields


class AdminUserCreateSerializer(serializers.ModelSerializer):
    """Write serializer for creating a user from the admin portal."""
    password = serializers.CharField(write_only=True, required=True, min_length=8)

    class Meta:
        model = User
        fields = ['email', 'name', 'role', 'is_active', 'password']

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('A user with this email already exists.')
        return value.lower()

    def validate_role(self, value):
        if value not in [User.Role.ADMIN, User.Role.SUPPORT, 'manager']:
            raise serializers.ValidationError('Allowed roles: admin, manager.')
        return value

    def create(self, validated_data):
        password = validated_data.pop('password')
        validated_data['role'] = User.Role.SUPPORT
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class AdminUserUpdateSerializer(serializers.ModelSerializer):
    """Write serializer for updating a user from the admin portal."""

    class Meta:
        model = User
        fields = ['name', 'email', 'role', 'is_active']

    def validate_role(self, value):
        if value not in [User.Role.ADMIN, User.Role.SUPPORT, 'manager']:
            raise serializers.ValidationError('Allowed roles: admin, manager.')
        return value
