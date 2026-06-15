from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import ConversationFlow, FlowCard, FlowConnection, AIFlowMode, AITool, AIModelConfig, ManagerTransferConfig, AgentConfig
from .serializers import (
    ConversationFlowListSerializer,
    ConversationFlowDetailSerializer,
    FlowCardSerializer,
    FlowConnectionSerializer,
    AIFlowModeSerializer,
    AIToolSerializer,
    AIModelConfigSerializer,
    ManagerTransferConfigSerializer,
    AgentConfigSerializer,
)
from apps.organizations.mixins import OrganizationQuerysetMixin


def _get_org(request):
    user = request.user
    if getattr(user, 'is_superadmin', False):
        return None
    org = getattr(user, 'current_organization', None)
    if org is None:
        from rest_framework.exceptions import PermissionDenied
        raise PermissionDenied('No active organization. Please select an organization.')
    return org


class ConversationFlowViewSet(OrganizationQuerysetMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = ConversationFlow.objects.all()

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ConversationFlowDetailSerializer
        return ConversationFlowListSerializer

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = ConversationFlowDetailSerializer(instance)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        flow = self.get_object()
        flow.is_active = True
        flow.save()
        return Response({'status': 'activated', 'id': flow.pk})


class FlowCardViewSet(OrganizationQuerysetMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = FlowCard.objects.all()
    serializer_class = FlowCardSerializer

    def get_queryset(self):
        user = self.request.user
        flow_id = self.kwargs.get('flow_pk')
        qs = FlowCard.objects.all()
        if flow_id:
            qs = qs.filter(flow_id=flow_id)
        if not getattr(user, 'is_superadmin', False):
            org = self._get_organization()
            qs = qs.filter(flow__organization=org)
        return qs

    def perform_create(self, serializer):
        user = self.request.user
        flow_id = self.kwargs.get('flow_pk')
        org = None if getattr(user, 'is_superadmin', False) else self._get_organization()
        kwargs = {}
        if flow_id:
            kwargs['flow_id'] = int(flow_id)
        serializer.save(**kwargs)

    @action(detail=True, methods=['get'], url_path='prompt-preview')
    def prompt_preview(self, request, pk=None, flow_pk=None):
        """
        Show what the AI will see (system prompt + stage policy) for this card.

        Optional query params:
          - lead_id: if provided, uses the real lead's collected data for a live preview.
          - sample_*: any field name prefixed with ``sample_`` is added to sample_data
            (e.g. ``?sample_check_in_date=2026-07-10&sample_guest_count=2``).
        """
        card = self.get_object()
        lead_id = request.query_params.get('lead_id')

        if lead_id:
            try:
                from apps.leads.models import Lead
                from apps.leads.services.prompt_preview import build_prompt_preview, build_lead_data_from_model

                lead = Lead.objects.get(pk=lead_id)
                org = getattr(lead, 'organization', None)
                # permission check: same org as current user
                user_org = getattr(request.user, 'current_organization', None)
                if user_org and org and org.pk != user_org.pk and not getattr(request.user, 'is_superadmin', False):
                    return Response({'error': 'Lead not in your organization.'}, status=status.HTTP_403_FORBIDDEN)

                lead_data = build_lead_data_from_model(lead)
                preview = build_prompt_preview(lead, message='', lead_data=lead_data)
                preview['mode'] = 'live_lead'
                return Response(preview)
            except Exception as exc:
                return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        # Card-only preview with optional sample data
        sample_data: dict = {}
        for key, value in request.query_params.items():
            if key.startswith('sample_'):
                field_name = key[len('sample_'):]
                sample_data[field_name] = value

        from apps.leads.services.prompt_preview import build_card_policy_preview
        preview = build_card_policy_preview(card, sample_data=sample_data or None)
        preview['mode'] = 'card_only'
        return Response(preview)

    @action(detail=False, methods=['get'], url_path='schema')
    def schema(self, request, flow_pk=None):
        """
        Return valid values for ``required_fields`` and ``allowed_tools`` for autocomplete.
        """
        from apps.leads.services.stage_resolver import LEAD_STAGE_FIELDS, FIELD_ALIASES
        from apps.leads.services.booking_tools import _TOOL_PARAMS
        from apps.flows.models import AITool

        org = _get_org(request)

        # All tools: built-in + DB-configured
        builtin_tools = sorted(_TOOL_PARAMS.keys())
        db_tool_qs = AITool.objects.all()
        if org is not None:
            from django.db.models import Q
            db_tool_qs = db_tool_qs.filter(Q(organization=org) | Q(organization__isnull=True))
        db_tools = list(db_tool_qs.values('name', 'display_name', 'is_enabled'))

        all_tool_names = sorted(set(builtin_tools) | {t['name'] for t in db_tools})

        # All field names with aliases
        canonical_fields = list(LEAD_STAGE_FIELDS)
        alias_map = {alias: canonical for alias, canonical in FIELD_ALIASES.items()}

        return Response({
            'required_fields': {
                'canonical': canonical_fields,
                'aliases': alias_map,
                'description': 'Use canonical names in required_fields. Aliases are auto-normalised.',
            },
            'allowed_tools': {
                'all': all_tool_names,
                'builtin': builtin_tools,
                'custom_db': db_tools,
                'description': (
                    'Names listed in allowed_tools restrict the tools available to the LLM on this stage. '
                    'Empty list means all tools are allowed.'
                ),
            },
            'response_policy_keys': [
                'faq_policy',
                'tone',
                'max_length',
                'language',
                'objection_handling',
            ],
        })


class FlowConnectionViewSet(OrganizationQuerysetMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = FlowConnection.objects.all()
    serializer_class = FlowConnectionSerializer

    def get_queryset(self):
        user = self.request.user
        flow_id = self.kwargs.get('flow_pk')
        qs = FlowConnection.objects.all()
        if flow_id:
            qs = qs.filter(flow_id=flow_id)
        if not getattr(user, 'is_superadmin', False):
            org = self._get_organization()
            qs = qs.filter(flow__organization=org)
        return qs

    def perform_create(self, serializer):
        user = self.request.user
        flow_id = self.kwargs.get('flow_pk')
        org = None if getattr(user, 'is_superadmin', False) else self._get_organization()
        kwargs = {}
        if flow_id:
            kwargs['flow_id'] = int(flow_id)
        serializer.save(**kwargs)


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def ai_flow_mode(request):
    org = _get_org(request)
    obj = AIFlowMode.get_mode(org=org)
    if request.method == 'GET':
        return Response(AIFlowModeSerializer(obj).data)
    serializer = AIFlowModeSerializer(obj, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


class AIToolViewSet(OrganizationQuerysetMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = AIToolSerializer
    queryset = AITool.objects.all()
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def ai_model_config(request):
    org = _get_org(request)
    obj = AIModelConfig.get_config(org=org)
    if request.method == 'GET':
        return Response(AIModelConfigSerializer(obj).data)
    serializer = AIModelConfigSerializer(obj, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


class AgentConfigViewSet(OrganizationQuerysetMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = AgentConfigSerializer
    queryset = AgentConfig.objects.all()
    http_method_names = ['get', 'patch', 'head', 'options']

    @action(detail=True, methods=['get'], url_path=r'context/(?P<lead_id>[0-9]+)')
    def context(self, request, pk=None, lead_id=None):
        """Read-only debug view of a lead's shared agent_context."""
        try:
            from apps.leads.models import Lead
            lead = Lead.objects.only('agent_context').get(pk=lead_id)
            return Response({'lead_id': int(lead_id), 'agent_context': lead.agent_context or {}})
        except Lead.DoesNotExist:
            return Response({'error': 'Lead not found'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def transfer_config(request):
    org = _get_org(request)
    obj = ManagerTransferConfig.get_config(org=org)
    if request.method == 'GET':
        return Response(ManagerTransferConfigSerializer(obj).data)
    serializer = ManagerTransferConfigSerializer(obj, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)
