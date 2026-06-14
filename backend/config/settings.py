"""
Django settings for the project.
"""
from datetime import timedelta
from pathlib import Path
import sys
import io

if sys.platform == 'win32' and not getattr(sys, '_utf8_wrapped', False):
    sys._utf8_wrapped = True
    try:
        if hasattr(sys.stdout, 'encoding') and sys.stdout.encoding.lower() != 'utf-8':
            if hasattr(sys.stdout, 'detach'):
                try:
                    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8', errors='replace')
                except Exception:
                    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
            else:
                sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        if hasattr(sys.stderr, 'encoding') and sys.stderr.encoding.lower() != 'utf-8':
            if hasattr(sys.stderr, 'detach'):
                try:
                    sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding='utf-8', errors='replace')
                except Exception:
                    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
            else:
                sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except (AttributeError, ValueError, io.UnsupportedOperation):
        pass

import environ

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Initialize environ
env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, ['localhost', '127.0.0.1']),
    CORS_ALLOWED_ORIGINS=(list, ['http://localhost:5173', 'http://localhost:8081']),
)

# Read .env file from project root (parent of backend/), but keep any
# already-injected runtime secrets authoritative. This prevents stale local
# values from overriding working platform-managed credentials.
environ.Env.read_env(BASE_DIR.parent / '.env', overwrite=False)

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env('DJANGO_SECRET_KEY', default='django-insecure-change-me-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env.bool('DJANGO_DEBUG', default=False)
ENVIRONMENT = env('ENVIRONMENT', default='development')
ENABLE_PRODUCTION_SECURITY = env.bool('ENABLE_PRODUCTION_SECURITY', default=ENVIRONMENT == 'production')

ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[
    "crimson-tower-1231.sandbox.cayu.app",
    "*.sandbox.cayu.app",
    "*.nip.io",
    ".trycloudflare.com",
    ".ngrok-free.app",
    ".loca.lt",
    "localhost",
    "127.0.0.1",
])

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third party
    'rest_framework',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'django_filters',
    'drf_spectacular',
    # Audit
    'auditlog',
    # Project apps
    'apps.organizations',
    'apps.users',
    'apps.leads',
    'apps.audit',
    'apps.hotel_media',
    'apps.hotel_info',
    'apps.flows',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'auditlog.middleware.AuditlogMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# Database
DATABASES = {
    'default': env.db('DATABASE_URL', default='postgresql://postgres:postgres@localhost:5433/app_dev')
}

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files (uploaded by users)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# CORS
CORS_ALLOWED_ORIGINS = env('CORS_ALLOWED_ORIGINS')
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGIN_REGEXES = [
    r'^https://[\w-]+\.cloudfront\.net$',  # CloudFront distributions
    r'^https://[\w-]+\.nip\.io$',  # nip.io for IP-based access
]

# Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'apps.users.authentication.AuditlogJWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
    ],
}

# Simple JWT
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# Custom User Model
AUTH_USER_MODEL = 'users.User'

# drf-spectacular settings
SPECTACULAR_SETTINGS = {
    'TITLE': 'API',
    'DESCRIPTION': 'API documentation',
    'VERSION': '1.0.0',
}

# Logging - write Django logs to backend/logs/ directory
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{asctime} {levelname} {name} {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': LOGS_DIR / 'django.log',
            'formatter': 'verbose',
            'encoding': 'utf-8',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console', 'file'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
}

# =============================================================================
# Celery Configuration (Redis broker)
# =============================================================================
CELERY_BROKER_URL = env('CELERY_BROKER_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = env('CELERY_RESULT_BACKEND', default=CELERY_BROKER_URL)
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# Celery Beat Schedule (periodic tasks)
# The AI agent check frequency is configurable via AIConfig.check_frequency_hours
# This schedule runs hourly and the task itself checks if it should actually execute
CELERY_BEAT_SCHEDULE = {
    'ai-agent-check': {
        'task': 'leads.run_agent_check',
        'schedule': 1800.0,  # Every 30 min — catches short promises ("через пару часов")
    },
}

# =============================================================================
# Production Security Settings (ECS Fargate / AWS)
# =============================================================================
X_FRAME_OPTIONS = 'ALLOWALL'

if ENABLE_PRODUCTION_SECURITY:
    # HTTPS settings
    SECURE_SSL_REDIRECT = env.bool('SECURE_SSL_REDIRECT', default=False)
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    # HSTS settings
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

    # CSRF trusted origins (ECS/ALB domains)
    CSRF_TRUSTED_ORIGINS = [
        'https://*.cloudfront.net',
        'https://*.amazonaws.com',  # ALB domains
    ]

# Cayu DB introspection (injected by cayu-pilot, only available in sandbox)
try:
    import config.cayu_db_introspection  # noqa: F401
    MIDDLEWARE.insert(1, 'config.cayu_db_introspection.CayuDbIntrospectionMiddleware')
except ImportError:
    pass
