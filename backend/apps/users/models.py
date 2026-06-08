from auditlog.registry import auditlog
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('role', 'admin')
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        ADMIN = 'admin', 'Admin / Manager'
        SUPPORT = 'support', 'Support'
        TAX_ACCOUNTANT = 'tax_accountant', 'Tax Accountant'

    class Language(models.TextChoices):
        EN = 'en', 'English'
        RU = 'ru', 'Russian'

    email = models.EmailField(unique=True, max_length=255)
    name = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_admin = models.BooleanField(default=False)
    is_superadmin = models.BooleanField(default=False, help_text='Platform super-admin: can access all organizations')
    role = models.CharField(max_length=50, choices=Role.choices, default=Role.SUPPORT)
    language = models.CharField(max_length=10, choices=Language.choices, default=Language.RU)
    current_organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        help_text='The organization the user is currently viewing',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        db_table = 'users'

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        # Keep is_admin in sync with the role field
        self.is_admin = self.role == self.Role.ADMIN
        super().save(*args, **kwargs)


auditlog.register(User, exclude_fields=['password', 'last_login'])
