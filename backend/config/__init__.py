# Import Celery app so Django loads it on startup
from .celery import app as celery_app

__all__ = ('celery_app',)
