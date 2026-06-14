from django.contrib.auth import get_user_model
from django.utils.text import slugify
from rest_framework import serializers
from .models import Organization, OrganizationMember

User = get_user_model()


class OrganizationMemberSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.name', read_only=True)
    user_id = serializers.IntegerField(source='user.id', read_only=True)

    class Meta:
        model = OrganizationMember
        fields = ['id', 'user_id', 'user_email', 'user_name', 'role', 'joined_at', 'is_active']
        read_only_fields = ['id', 'joined_at', 'user_id', 'user_email', 'user_name']


class OrganizationSerializer(serializers.ModelSerializer):
    owner_email = serializers.EmailField(source='owner.email', read_only=True)
    member_count = serializers.SerializerMethodField()
    current_user_role = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = [
            'id', 'name', 'slug', 'logo', 'plan', 'is_active',
            'owner_email', 'trial_ends_at', 'org_settings',
            'member_count', 'current_user_role', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'slug', 'owner_email', 'created_at', 'updated_at']

    def get_member_count(self, obj):
        return obj.members.filter(is_active=True).count()

    def get_current_user_role(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        member = obj.members.filter(user=request.user, is_active=True).first()
        return member.role if member else None


class OrganizationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ['name', 'plan']

    def create(self, validated_data):
        user = self.context['request'].user
        name = validated_data['name']
        slug = slugify(name)
        # Ensure unique slug
        base_slug = slug
        counter = 1
        while Organization.objects.filter(slug=slug).exists():
            slug = f'{base_slug}-{counter}'
            counter += 1
        org = Organization.objects.create(
            name=name,
            slug=slug,
            plan=validated_data.get('plan', Organization.Plan.FREE),
            owner=user,
        )
        OrganizationMember.objects.create(
            organization=org,
            user=user,
            role=OrganizationMember.Role.OWNER,
        )
        # Set as current org if user has none
        if not user.current_organization:
            user.current_organization = org
            user.save(update_fields=['current_organization'])
        return org
