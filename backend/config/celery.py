"""
Celery configuration for background task processing.

In production (ECS Fargate), this runs as a separate container with:
    celery -A config worker -B

The -B flag enables celery beat (scheduled tasks) in the same process.
"""

import os

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('config')

# Read config from Django settings, using CELERY_ namespace
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()
