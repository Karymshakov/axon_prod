from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Q, F
from django.utils import timezone
import asyncio
from .models import Lead, PipelineStage, Segment, Customer, LeadNote, LeadActivity, Task, LeadGoal
from .telegram_service import telegram_service
from .goal_manager import goal_manager
from .channel_ai_control import is_channel_ai_globally_paused
from .serializers import (
    LeadSerializer,
    PipelineStageSerializer,
    SegmentSerializer,
    CustomerSerializer,
    LeadNoteSerializer,
    LeadActivitySerializer,
    TaskSerializer,
    LeadGoalSerializer,
)
from apps.organizations.mixins import OrganizationQuerysetMixin
from apps.flows.models import LeadFlowState


AI_MEMORY_RESET_FIELDS = {
    'notes': '',
    'problem_description': '',
    'next_steps': '',
    'preferred_contact_time': '',
    'check_in_date': None,
    'check_out_date': None,
    'guest_count': None,
    'room_type_preference': '',
    'meal_plan': '',
    'ai_followup_count': 0,
    'last_ai_followup_at': None,
    'agent_context': {},
    'current_objection': '',
    'last_objection_at': None,
    'objection_count': 0,
}

AI_ACTIVITY_TYPES_TO_CLEAR = [
    LeadActivity.TYPE_AI_STATUS_CHANGE,
    LeadActivity.TYPE_OBJECTION_DETECTED,
    LeadActivity.TYPE_TASK_AUTO_COMPLETED,
    LeadActivity.TYPE_GOAL_CREATED,
    LeadActivity.TYPE_GOAL_COMPLETED,
]


def _reset_lead_ai_memory(lead: Lead, user_name: str) -> tuple[Lead, dict]:
    """Clear per-lead AI memory/state while preserving lead record and message history."""
    reset_summary = {
        'cleared_fields': [field for field, value in AI_MEMORY_RESET_FIELDS.items() if getattr(lead, field) != value],
        'flow_state_cleared': False,
        'ai_goals_deleted': 0,
        'ai_tasks_deleted': 0,
        'ai_activities_deleted': 0,
    }

    with transaction.atomic():
        locked_lead = Lead.objects.select_for_update().get(pk=lead.pk)

        for field, value in AI_MEMORY_RESET_FIELDS.items():
            setattr(locked_lead, field, value)
        locked_lead.save(update_fields=list(AI_MEMORY_RESET_FIELDS.keys()))

        flow_state_deleted, _ = LeadFlowState.objects.filter(lead=locked_lead).delete()
        reset_summary['flow_state_cleared'] = bool(flow_state_deleted)

        ai_goals = locked_lead.goals.filter(is_ai_generated=True)
        reset_summary['ai_goals_deleted'] = ai_goals.count()
        ai_goals.delete()

        ai_tasks = locked_lead.tasks.filter(is_ai_generated=True)
        reset_summary['ai_tasks_deleted'] = ai_tasks.count()
        ai_tasks.delete()

        ai_activities = LeadActivity.objects.filter(lead=locked_lead).filter(
            Q(activity_type__in=AI_ACTIVITY_TYPES_TO_CLEAR)
            | Q(activity_type__in=[LeadActivity.TYPE_TASK_CREATED, LeadActivity.TYPE_TASK_COMPLETED], metadata__is_ai_generated=True)
        )
        reset_summary['ai_activities_deleted'] = ai_activities.count()
        ai_activities.delete()

        LeadActivity.objects.create(
            lead=locked_lead,
            organization=locked_lead.organization,
            activity_type=LeadActivity.TYPE_LEAD_UPDATED,
            description=f'🧪 {user_name} reset AI memory for testing',
            metadata={
                'action': 'reset_ai_memory',
                'user': user_name,
                'cleared_fields': reset_summary['cleared_fields'],
                'flow_state_cleared': reset_summary['flow_state_cleared'],
                'ai_goals_deleted': reset_summary['ai_goals_deleted'],
                'ai_tasks_deleted': reset_summary['ai_tasks_deleted'],
                'ai_activities_deleted': reset_summary['ai_activities_deleted'],
            },
        )

    lead.refresh_from_db()
    return lead, reset_summary


class PipelineStageViewSet(OrganizationQuerysetMixin, viewsets.ModelViewSet):
    queryset = PipelineStage.objects.all()
    serializer_class = PipelineStageSerializer


class SegmentViewSet(OrganizationQuerysetMixin, viewsets.ModelViewSet):
    queryset = Segment.objects.all()
    serializer_class = SegmentSerializer


class LeadViewSet(OrganizationQuerysetMixin, viewsets.ModelViewSet):
    queryset = Lead.objects.select_related('assigned_to').all()
    serializer_class = LeadSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'segment', 'source', 'assigned_to']
    search_fields = ['contact_person', 'email', 'notes']
    ordering_fields = ['last_message_at', 'last_contacted', 'created_at', 'contact_person']
    ordering = ['-last_message_at']

    def get_queryset(self):
        from django.db.models import Max
        from django.db.models.functions import Coalesce
        user = self.request.user
        active_task_statuses = [Task.STATUS_PENDING, Task.STATUS_IN_PROGRESS]
        message_activity_types = [
            'telegram_sent', 'telegram_received',
            'instagram_sent', 'instagram_received',
            'whatsapp_sent', 'whatsapp_received',
            'ringcentral_sms_sent', 'ringcentral_sms_received',
        ]
        base_qs = (
            Lead.objects
            .select_related('assigned_to', 'organization')
            .prefetch_related('customer')
            .annotate(
                last_message_at=Coalesce(
                    Max(
                        'activities__created_at',
                        filter=Q(activities__activity_type__in=message_activity_types)
                    ),
                    'created_at'
                ),
                active_tasks_count=Count(
                    'tasks',
                    filter=Q(tasks__status__in=active_task_statuses),
                    distinct=True,
                ),
                overdue_tasks_count=Count(
                    'tasks',
                    filter=Q(
                        tasks__status__in=active_task_statuses,
                        tasks__due_date__lt=timezone.now().date(),
                    ),
                    distinct=True,
                ),
            )
            .order_by(F('last_message_at').desc(nulls_last=True))
        )
        if getattr(user, 'is_superadmin', False):
            return base_qs
        org = self._get_organization()
        return base_qs.filter(organization=org)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get lead counts grouped by status, using pipeline stages as keys."""
        user = request.user
        org = None if getattr(user, 'is_superadmin', False) else self._get_organization()
        stages_qs = PipelineStage.objects.all().order_by('order', 'id')
        if org:
            stages_qs = stages_qs.filter(organization=org)
        result = {stage.key: 0 for stage in stages_qs}

        lead_qs = Lead.objects.values('status').annotate(count=Count('id'))
        if org:
            lead_qs = lead_qs.filter(organization=org)
        for stat in lead_qs:
            result[stat['status']] = stat['count']

        result['total'] = sum(result.values())
        return Response(result)

    @action(detail=False, methods=['get'])
    def source_stats(self, request):
        """Get lead counts grouped by source."""
        user = request.user
        org = None if getattr(user, 'is_superadmin', False) else self._get_organization()
        queryset = Lead.objects.exclude(source='').values('source').annotate(count=Count('id')).order_by('-count')
        if org:
            queryset = queryset.filter(organization=org)
        return Response([{'source': s['source'], 'count': s['count']} for s in queryset])

    @action(detail=True, methods=['post'])
    def convert_to_customer(self, request, pk=None):
        """Convert a lead to a customer while preserving lead history."""
        lead = self.get_object()

        # Check if already converted
        if hasattr(lead, 'customer') and lead.customer:
            return Response(
                {'error': 'This lead has already been converted to a customer'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create customer from lead data, keeping lead linked
        customer = Customer.objects.create(
            lead=lead,  # Keep link to preserve history
            organization=lead.organization,
            contact_person=lead.contact_person,
            email=lead.email,
            phone=lead.phone,
            notes=lead.notes,
            segment=lead.segment,
            source=lead.source,
            # Copy communication channels
            telegram_chat_id=lead.telegram_chat_id,
            telegram_username=lead.telegram_username,
            instagram_user_id=lead.instagram_user_id,
            instagram_username=lead.instagram_username,
            whatsapp_phone=lead.whatsapp_phone,
        )

        # Update lead status to converted (but keep the record)
        lead.status = Lead.STATUS_CONVERTED
        lead.save()

        # Create activity for conversion
        LeadActivity.objects.create(
            lead=lead,
            organization=lead.organization,
            activity_type=LeadActivity.TYPE_STATUS_CHANGE,
            description=f'Lead converted to customer',
            metadata={'customer_id': customer.id},
        )

        return Response(CustomerSerializer(customer).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def assignable_users(self, request):
        """Get list of active users who can be assigned to leads."""
        User = get_user_model()
        users = User.objects.filter(is_active=True).values('id', 'name', 'email')
        return Response([
            {'id': u['id'], 'name': u['name'] or u['email'], 'email': u['email']}
            for u in users
        ])

    @action(detail=True, methods=['get'])
    def goals(self, request, pk=None):
        """Get all goals for a lead."""
        lead = self.get_object()
        goals = lead.goals.all().order_by('priority', '-created_at')
        return Response(LeadGoalSerializer(goals, many=True).data)

    @action(detail=True, methods=['post'])
    def initialize_goals(self, request, pk=None):
        """Initialize goals for this lead based on their current status."""
        lead = self.get_object()
        created_goals = goal_manager.create_initial_goals(lead)
        return Response({
            'created': len(created_goals),
            'goals': LeadGoalSerializer(created_goals, many=True).data,
        })

    @action(detail=True, methods=['post'])
    def handback(self, request, pk=None):
        """Hand AI control back to the AI agent after a manual takeover."""
        lead = self.get_object()
        user_name = request.user.name or request.user.email if request.user.is_authenticated else 'Unknown'
        Lead.objects.filter(id=lead.id).update(ai_paused=False, ai_paused_at=None, ai_paused_by='')
        LeadActivity.objects.create(
            lead=lead,
            organization=lead.organization,
            activity_type=LeadActivity.TYPE_LEAD_UPDATED,
            description=f'🤖 AI agent re-enabled by {user_name}',
            metadata={'action': 'handback_to_ai', 'user': user_name},
        )
        lead.refresh_from_db()
        return Response(LeadSerializer(lead).data)

    @action(detail=True, methods=['post'], url_path='toggle-ai-pause')
    def toggle_ai_pause(self, request, pk=None):
        """Toggle AI pause state for a lead."""
        user_name = request.user.name or request.user.email if request.user.is_authenticated else 'Unknown'

        with transaction.atomic():
            lead = Lead.objects.select_for_update().get(pk=self.get_object().pk)

            if lead.ai_paused:
                lead.ai_paused = False
                lead.ai_paused_at = None
                lead.ai_paused_by = ''
                lead.save(update_fields=['ai_paused', 'ai_paused_at', 'ai_paused_by'])
                LeadActivity.objects.create(
                    lead=lead,
                    organization=lead.organization,
                    activity_type=LeadActivity.TYPE_LEAD_UPDATED,
                    description=f'🤖 AI agent re-enabled by {user_name}',
                    metadata={'action': 'ai_resumed', 'user': user_name},
                )
            else:
                lead.ai_paused = True
                lead.ai_paused_at = timezone.now()
                lead.ai_paused_by = user_name
                lead.save(update_fields=['ai_paused', 'ai_paused_at', 'ai_paused_by'])
                LeadActivity.objects.create(
                    lead=lead,
                    organization=lead.organization,
                    activity_type=LeadActivity.TYPE_LEAD_UPDATED,
                    description=f'🙋 {user_name} took manual control — AI paused',
                    metadata={'action': 'ai_paused', 'user': user_name},
                )

        return Response(LeadSerializer(lead).data)

    @action(detail=True, methods=['post'], url_path='reset-ai-memory')
    def reset_ai_memory(self, request, pk=None):
        """Temporary test-only action to clear AI memory/state for one lead."""
        lead = self.get_object()
        user_name = request.user.name or request.user.email if request.user.is_authenticated else 'Unknown'
        lead, reset_summary = _reset_lead_ai_memory(lead, user_name)
        return Response({
            'lead': LeadSerializer(lead).data,
            'reset_summary': reset_summary,
        })

    @action(detail=True, methods=['post'], url_path='generate-copilot-suggestion')
    def generate_copilot_suggestion(self, request, pk=None):
        """Generate a suggested response from the AI agent without sending it."""
        lead = self.get_object()
        from apps.leads.agent_service import agent_service
        suggestion = agent_service.generate_response_for_lead(lead)
        if suggestion:
            return Response({'suggestion': suggestion})
        return Response({'suggestion': ''}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='ai-prompt-preview')
    def ai_prompt_preview(self, request, pk=None):
        """Build a prompt/decision preview without calling the LLM or executing tools."""
        lead = self.get_object()
        from apps.leads.services.prompt_preview import build_prompt_preview

        include_content = request.data.get('include_content', True)
        if isinstance(include_content, str):
            include_content = include_content.lower() not in {'0', 'false', 'no', 'off'}

        preview = build_prompt_preview(
            lead,
            request.data.get('message', '') or '',
            lead_data=request.data.get('lead_data') or {},
            conversation_history=request.data.get('conversation_history') or [],
            include_content=bool(include_content),
        )
        return Response(preview)

    @action(detail=True, methods=['post'])
    def trigger_instagram_ai_response(self, request, pk=None):
        """Manually trigger an AI response to the lead's most recent Instagram DM."""
        import threading
        from .instagram_views import _delayed_instagram_ai_response
        from .instagram_service import instagram_service

        lead = self.get_object()

        if is_channel_ai_globally_paused('instagram', lead=lead):
            return Response(
                {'error': 'Instagram AI is paused globally in settings'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not lead.instagram_user_id:
            return Response(
                {'error': 'Lead has no Instagram user ID'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        latest_activity = LeadActivity.objects.filter(
            lead=lead,
            activity_type=LeadActivity.TYPE_INSTAGRAM_RECEIVED,
        ).order_by('-created_at').first()

        if not latest_activity:
            return Response(
                {'error': 'No Instagram messages found for this lead'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        message_text = (
            latest_activity.metadata.get('text', '') if latest_activity.metadata else latest_activity.description
        )
        _delayed_instagram_ai_response.delay(
            lead.id, latest_activity.id, lead.instagram_user_id, message_text, force_response=True
        )
        return Response({'status': 'triggered'})

    @action(detail=True, methods=['post'])
    def send_telegram(self, request, pk=None):
        """Send a Telegram message to the lead."""
        lead = self.get_object()

        # Check if lead has Telegram chat ID
        if not lead.telegram_chat_id:
            return Response(
                {'error': 'Lead does not have a Telegram chat ID'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get message from request
        message = request.data.get('message', '')
        if not message:
            return Response(
                {'error': 'Message is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if Telegram bot is configured
        if not telegram_service.is_configured():
            return Response(
                {'error': 'Telegram bot is not configured. Please add TELEGRAM_BOT_TOKEN in Integrations settings.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Send message using Telegram service (async)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(
                telegram_service.send_message(lead.telegram_chat_id, message)
            )
            loop.close()

            if result:
                # Create activity record
                LeadActivity.objects.create(
                    lead=lead,
                    activity_type='telegram_sent',
                    description=f'Telegram message sent: {message[:100]}{"..." if len(message) > 100 else ""}',
                    metadata={
                        'message': message,
                        'message_id': result.get('message_id'),
                        'chat_id': result.get('chat_id'),
                    }
                )

                return Response({'message': 'Message sent successfully', 'data': result})
            else:
                return Response(
                    {'error': 'Failed to send message'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        except Exception as e:
            return Response(
                {'error': f'Failed to send Telegram message: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class LeadNoteViewSet(OrganizationQuerysetMixin, viewsets.ModelViewSet):
    queryset = LeadNote.objects.all()
    serializer_class = LeadNoteSerializer
    filterset_fields = ['lead']

    def get_queryset(self):
        user = self.request.user
        base_qs = super(OrganizationQuerysetMixin, self).get_queryset()
        if getattr(user, 'is_superadmin', False):
            return base_qs
        org = self._get_organization()
        return base_qs.filter(lead__organization=org)

    def perform_create(self, serializer):
        user = self.request.user
        org = None if getattr(user, 'is_superadmin', False) else self._get_organization()
        note = serializer.save()
        LeadActivity.objects.create(
            lead=note.lead,
            organization=org,
            activity_type='note_added',
            description=f'Note added: {note.content[:50]}...' if len(note.content) > 50 else f'Note added: {note.content}',
        )


class LeadActivityViewSet(OrganizationQuerysetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = LeadActivity.objects.all()
    serializer_class = LeadActivitySerializer
    filterset_fields = ['lead', 'activity_type']


# Inbound activity types per channel — only these count as "unread"
_INBOUND_TYPES = {
    'telegram': ['telegram_received'],
    'instagram': ['instagram_received'],
    'whatsapp': ['whatsapp_received'],
    'sms': ['ringcentral_sms_received'],
}
_ALL_INBOUND = [t for types in _INBOUND_TYPES.values() for t in types]


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def communications_unread_counts(request):
    """
    Returns unread inbound message counts per lead, per channel.
    Response: { lead_id: { channel: count, ... }, ... }
    Also includes a 'total' field with the sum across all leads/channels.
    """
    user = request.user
    org = getattr(user, 'current_organization', None)
    qs = LeadActivity.objects.filter(activity_type__in=_ALL_INBOUND, is_read=False)
    if not getattr(user, 'is_superadmin', False):
        if org:
            qs = qs.filter(organization=org)
        else:
            qs = qs.none()
    rows = qs.values('lead_id', 'activity_type').annotate(count=Count('id'))

    # Reverse map: activity_type → channel name
    type_to_channel = {t: ch for ch, types in _INBOUND_TYPES.items() for t in types}

    result: dict = {}
    total = 0
    for row in rows:
        lead_id = str(row['lead_id'])
        channel = type_to_channel.get(row['activity_type'], 'other')
        count = row['count']
        result.setdefault(lead_id, {})[channel] = count
        total += count

    return Response({'counts': result, 'total': total})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def communications_mark_read(request):
    """
    Mark all inbound activities as read for a specific lead + channel.
    Body: { lead_id: int, channel: str }
    """
    lead_id = request.data.get('lead_id')
    channel = request.data.get('channel')
    if not lead_id or not channel:
        return Response({'error': 'lead_id and channel are required'}, status=400)

    inbound_types = _INBOUND_TYPES.get(channel, [])
    if not inbound_types:
        return Response({'error': f'Unknown channel: {channel}'}, status=400)

    user = request.user
    org = getattr(user, 'current_organization', None)
    qs = LeadActivity.objects.filter(lead_id=lead_id, activity_type__in=inbound_types, is_read=False)
    if not getattr(user, 'is_superadmin', False):
        if org:
            qs = qs.filter(organization=org)
        else:
            qs = qs.none()
    marked = qs.update(is_read=True)

    return Response({'marked_read': marked})


class TaskViewSet(OrganizationQuerysetMixin, viewsets.ModelViewSet):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    filterset_fields = ['lead', 'status', 'task_type']

    def perform_create(self, serializer):
        user = self.request.user
        org = None if getattr(user, 'is_superadmin', False) else self._get_organization()
        task = serializer.save(organization=org)
        LeadActivity.objects.create(
            lead=task.lead,
            organization=org,
            activity_type='task_created',
            description=f'Task created: {task.title}',
            metadata={'task_id': task.id, 'due_date': str(task.due_date)},
        )

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Mark a task as completed."""
        task = self.get_object()
        if task.status == Task.STATUS_COMPLETED:
            return Response({'error': 'Task is already completed'}, status=status.HTTP_400_BAD_REQUEST)

        task.status = Task.STATUS_COMPLETED
        task.completed_at = timezone.now()
        task.save()

        # Create activity for task completed
        LeadActivity.objects.create(
            lead=task.lead,
            activity_type='task_completed',
            description=f'Task completed: {task.title}',
            metadata={'task_id': task.id},
        )

        return Response(TaskSerializer(task).data)


class CustomerViewSet(OrganizationQuerysetMixin, viewsets.ModelViewSet):
    queryset = Customer.objects.select_related('lead', 'organization').all()
    serializer_class = CustomerSerializer


class LeadGoalViewSet(OrganizationQuerysetMixin, viewsets.ModelViewSet):
    queryset = LeadGoal.objects.all()
    serializer_class = LeadGoalSerializer
    filterset_fields = ['lead', 'status', 'goal_type', 'priority']

    def perform_create(self, serializer):
        user = self.request.user
        org = None if getattr(user, 'is_superadmin', False) else self._get_organization()
        goal = serializer.save(organization=org)
        LeadActivity.objects.create(
            lead=goal.lead,
            organization=org,
            activity_type=LeadActivity.TYPE_GOAL_CREATED,
            description=f'Goal created: {goal.get_goal_type_display()}',
            metadata={
                'goal_id': goal.id,
                'goal_type': goal.goal_type,
                'priority': goal.priority,
            },
        )

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Mark a goal as completed."""
        goal = self.get_object()
        if goal.status == LeadGoal.STATUS_COMPLETED:
            return Response({'error': 'Goal is already completed'}, status=status.HTTP_400_BAD_REQUEST)

        goal_manager.complete_goal(goal, request.data.get('current_value'))

        return Response(LeadGoalSerializer(goal).data)

    @action(detail=False, methods=['post'])
    def initialize_for_lead(self, request):
        """Initialize goals for a lead based on their current status and missing info."""
        lead_id = request.data.get('lead_id')
        if not lead_id:
            return Response({'error': 'lead_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            lead = Lead.objects.get(pk=lead_id)
        except Lead.DoesNotExist:
            return Response({'error': 'Lead not found'}, status=status.HTTP_404_NOT_FOUND)

        created_goals = goal_manager.create_initial_goals(lead)
        return Response({
            'created': len(created_goals),
            'goals': LeadGoalSerializer(created_goals, many=True).data,
        })
