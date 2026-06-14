"""
Cayu Database Introspection Middleware

Lightweight middleware that exposes /api/_cayu/db/ endpoints for production database
introspection. Injected into user projects via inject.py.

Auth: Bearer token checked against CAYU_ERROR_REPORTING_TOKEN env var
(already set in every ECS task definition).

Endpoints:
  GET /api/_cayu/db/models/                          — list all user-defined models
  GET /api/_cayu/db/data/<app>/<model>/[?page=&...]   — paginated model data

Self-contained: all constants and helpers are inlined (no cayu-pilot imports).
"""

import json
import os
import re
from django.http import JsonResponse
from django.apps import apps
from django.db import OperationalError, DatabaseError
from django.db.models import Q
from django.core.serializers.json import DjangoJSONEncoder

# --- Inlined constants (from db_config.py) ---

SYSTEM_APPS = [
    'django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes',
    'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles',
    'rest_framework', 'corsheaders', 'django_filters', 'drf_spectacular',
    'storages', 'celery', 'django_celery_beat', 'django_celery_results',
    'allauth', 'anymail', 'cayu_sdk',
]

HIDDEN_MODELS = {
    ('accounts', 'oauthstate'),
    ('accounts', 'pendingauthtoken'),
    ('accounts', 'cayuoauthprofile'),
}

SENSITIVE_PATTERNS = [
    r'password', r'token', r'secret', r'key', r'credential',
    r'api_key', r'access_token', r'refresh_token', r'private',
]

# --- Inlined helpers (from helpers.py) ---


def _is_system_app(app_name):
    return any(app_name.startswith(s) or app_name == s for s in SYSTEM_APPS)


def _is_sensitive(field_name):
    field_lower = field_name.lower()
    return any(re.search(p, field_lower) for p in SENSITIVE_PATTERNS)


def _get_model_fields(meta):
    return [f for f in meta.get_fields()
            if hasattr(f, 'name') and (not f.is_relation or f.many_to_one)]


def _get_field_info(field):
    info = {
        'name': field.name,
        'type': field.get_internal_type(),
        'nullable': field.null,
        'primary_key': field.primary_key,
        'unique': field.unique,
    }
    if hasattr(field, 'max_length') and field.max_length:
        info['max_length'] = field.max_length
    if hasattr(field, 'related_model') and field.related_model:
        related_meta = field.related_model._meta
        info['related_model'] = f'{related_meta.app_label}.{related_meta.model_name}'
    return info


# --- Middleware ---


class CayuDbIntrospectionMiddleware:
    PREFIX = '/api/_cayu/db/'

    def __init__(self, get_response):
        self.get_response = get_response
        self.token = os.environ.get('CAYU_ERROR_REPORTING_TOKEN', '')

    def __call__(self, request):
        if not request.path.startswith(self.PREFIX):
            return self.get_response(request)

        if not self.token:
            return JsonResponse({'error': 'Introspection not configured'}, status=503)

        auth = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth.startswith('Bearer ') or auth[7:] != self.token:
            return JsonResponse({'error': 'Unauthorized'}, status=401)

        path = request.path[len(self.PREFIX):]  # strip prefix

        if path == 'models/' or path == 'models':
            return self._list_models()

        # Match: data/<app_label>/<model_name>/ or data/<app_label>/<model_name>
        m = re.match(r'^data/([a-zA-Z_][a-zA-Z0-9_]*)/([a-zA-Z_][a-zA-Z0-9_]*)/?$', path)
        if m:
            return self._get_model_data(request, m.group(1), m.group(2))

        return JsonResponse({'error': 'Not found'}, status=404)

    def _list_models(self):
        models = []
        for app_config in apps.get_app_configs():
            if _is_system_app(app_config.name):
                continue
            for model in app_config.get_models():
                meta = model._meta
                if meta.abstract:
                    continue
                if (meta.app_label, meta.model_name) in HIDDEN_MODELS:
                    continue
                try:
                    count = model.objects.count()
                except (OperationalError, DatabaseError):
                    count = None
                models.append({
                    'app_label': meta.app_label,
                    'model_name': model.__name__,
                    'verbose_name': str(meta.verbose_name),
                    'verbose_name_plural': str(meta.verbose_name_plural),
                    'db_table': meta.db_table,
                    'fields': [_get_field_info(f) for f in _get_model_fields(meta)],
                    'record_count': count,
                })
        return JsonResponse(
            {'models': models, 'total_count': len(models)},
            encoder=DjangoJSONEncoder,
        )

    def _get_model_data(self, request, app_label, model_name):
        try:
            model = apps.get_model(app_label, model_name)
        except LookupError:
            return JsonResponse({'error': 'Model not found'}, status=404)

        meta = model._meta
        if (meta.app_label, meta.model_name) in HIDDEN_MODELS:
            return JsonResponse({'error': 'Access denied'}, status=403)

        try:
            app_config = apps.get_app_config(app_label)
            if _is_system_app(app_config.name):
                return JsonResponse({'error': 'Access denied'}, status=403)
        except LookupError:
            return JsonResponse({'error': 'App not found'}, status=404)

        page = int(request.GET.get('page', 1))
        page_size = min(int(request.GET.get('page_size', 50)), 100)
        order_by = request.GET.get('order_by')
        search = request.GET.get('search')

        field_names = [f.name for f in _get_model_fields(meta)]
        qs = model.objects.all()

        if search:
            text_fields = [f.name for f in meta.get_fields()
                          if hasattr(f, 'name') and f.get_internal_type() in ('CharField', 'TextField')]
            if text_fields:
                q = Q()
                for fn in text_fields:
                    q |= Q(**{f'{fn}__icontains': search})
                qs = qs.filter(q)

        try:
            total_count = qs.count()
        except (OperationalError, DatabaseError) as e:
            return JsonResponse({'error': str(e)}, status=500)

        if order_by:
            clean = order_by.lstrip('-')
            if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', clean) and clean in field_names:
                qs = qs.order_by(order_by)
            else:
                qs = qs.order_by('pk')
        else:
            qs = qs.order_by('pk')

        offset = (page - 1) * page_size
        qs = qs[offset:offset + page_size]

        try:
            data = []
            for row in qs.values(*field_names):
                for k, v in list(row.items()):
                    if hasattr(v, 'isoformat'):
                        row[k] = v.isoformat()
                    elif _is_sensitive(k) and v is not None:
                        row[k] = '***'
                data.append(row)
        except (OperationalError, DatabaseError) as e:
            return JsonResponse({'error': str(e)}, status=500)

        return JsonResponse({
            'app_label': app_label,
            'model_name': model_name,
            'fields': field_names,
            'data': data,
            'total_count': total_count,
            'page': page,
            'page_size': page_size,
            'has_more': (offset + page_size) < total_count,
        }, encoder=DjangoJSONEncoder)
