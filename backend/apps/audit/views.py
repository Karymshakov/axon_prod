from datetime import datetime

from django.db.models import Q

from auditlog.models import LogEntry
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .pagination import ConfigurablePageNumberPagination
from .permissions import IsAdminUser
from .serializers import AuditLogSerializer


# Map action names to LogEntry action constants
ACTION_MAP = {
    'create': LogEntry.Action.CREATE,
    'update': LogEntry.Action.UPDATE,
    'delete': LogEntry.Action.DELETE,
}

# Valid ordering fields for audit logs
VALID_AUDIT_ORDERINGS = {
    'timestamp': 'timestamp',
    '-timestamp': '-timestamp',
}


def parse_date(date_str):
    """Parse YYYY-MM-DD date string, return None if invalid."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str.strip(), '%Y-%m-%d').date()
    except (ValueError, TypeError, AttributeError):
        return None


@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_audit_logs(request):
    """
    List audit logs (admin only) with pagination and filtering.

    Query params:
    - page: Page number (default: 1)
    - page_size: Items per page (10, 25, 50, 100; default: 25)
    - search: Search by object representation or actor email/name
    - action: Filter by action type (create, update, delete)
    - date_from: Filter logs on or after this date (YYYY-MM-DD)
    - date_to: Filter logs on or before this date (YYYY-MM-DD)
    - ordering: Sort by field (timestamp, -timestamp)
    """
    # Default ordering
    ordering = request.query_params.get('ordering', '-timestamp')
    if ordering not in VALID_AUDIT_ORDERINGS:
        ordering = '-timestamp'

    logs = LogEntry.objects.select_related('actor', 'content_type').order_by(VALID_AUDIT_ORDERINGS[ordering])

    # Search filter
    search = request.query_params.get('search', '').strip()
    if search:
        logs = logs.filter(
            Q(object_repr__icontains=search) |
            Q(actor__email__icontains=search) |
            Q(actor__name__icontains=search)
        )

    # Actor (user) filter
    actor = request.query_params.get('actor', '').strip()
    if actor:
        logs = logs.filter(
            Q(actor__email__icontains=actor) |
            Q(actor__name__icontains=actor)
        )

    # Action filter
    action = request.query_params.get('action', '').strip().lower()
    if action in ACTION_MAP:
        logs = logs.filter(action=ACTION_MAP[action])

    # Date range filters
    date_from = parse_date(request.query_params.get('date_from'))
    date_to = parse_date(request.query_params.get('date_to'))
    if date_from:
        logs = logs.filter(timestamp__date__gte=date_from)
    if date_to:
        logs = logs.filter(timestamp__date__lte=date_to)

    # Paginate
    paginator = ConfigurablePageNumberPagination()
    paginated_logs = paginator.paginate_queryset(logs, request)
    serializer = AuditLogSerializer(paginated_logs, many=True)
    return paginator.get_paginated_response(serializer.data)
