from __future__ import annotations

from django.db.models import QuerySet

from .models import Lead, LeadActivity


def get_last_ai_memory_reset_at(lead: Lead):
    return (
        LeadActivity.objects.filter(
            lead=lead,
            activity_type=LeadActivity.TYPE_LEAD_UPDATED,
            metadata__action='reset_ai_memory',
        )
        .order_by('-created_at')
        .values_list('created_at', flat=True)
        .first()
    )


def filter_activities_since_last_ai_reset(queryset: QuerySet, lead: Lead) -> QuerySet:
    reset_at = get_last_ai_memory_reset_at(lead)
    if reset_at:
        return queryset.filter(created_at__gt=reset_at)
    return queryset
