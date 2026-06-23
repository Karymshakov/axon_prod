"""
Autonomous AI Agent Service for proactive lead follow-ups.

The agent periodically reviews all active leads and sends contextual,
AI-generated follow-up messages to move leads toward conversion.

Enhanced with autonomous capabilities:
- Conversation analysis for stage progression
- Smart objection handling with rebuttals
- Goal-directed conversation management
- Auto-executable task creation and execution
"""
import json
import logging
import asyncio
import re
import uuid
from datetime import date, datetime, timedelta
from typing import Optional
from django.utils import timezone
from django.db import transaction
from django.db.models import Q
from .models import Lead, LeadActivity, LeadNote, LeadGoal, PipelineStage, AIConfig, Task
from .telegram_service import telegram_service
from .instagram_service import instagram_service
from .whatsapp_service import whatsapp_service
from .ai_service import ai_service
from .conversation_analyzer import conversation_analyzer
from .goal_manager import goal_manager
from .task_executor import task_executor
from .channel_ai_control import is_channel_ai_globally_paused

logger = logging.getLogger(__name__)

INBOUND_MESSAGE_ACTIVITY_TYPES = (
    LeadActivity.TYPE_TELEGRAM_RECEIVED,
    LeadActivity.TYPE_INSTAGRAM_RECEIVED,
    LeadActivity.TYPE_WHATSAPP_RECEIVED,
    LeadActivity.TYPE_RINGCENTRAL_SMS_RECEIVED,
)

# Keywords that indicate a time-based promise in any supported language
_PROMISE_KEYWORDS = [
    # Russian
    'напишу', 'позвоню', 'свяжусь', 'отвечу', 'перезвоню', 'уточню', 'узнаю',
    'напиши', 'напишите', 'напомни', 'напомните', 'свяжитесь', 'перезвоните',
    'завтра', 'послезавтра', 'после обеда', 'вечером', 'утром', 'ночью',
    'через час', 'через пару', 'через несколько', 'позже напишу', 'позже отвечу',
    'скажу', 'сообщу', 'дам знать', 'дам ответ', 'напишите позже', 'напомните позже',
    # English
    "i'll write", "i'll reply", "i'll respond", "i'll get back", "i'll contact",
    "i'll call", 'will write', 'will reply', 'will respond', 'will get back',
    'will call', 'will contact', 'tomorrow', 'later today', 'this evening',
    'this afternoon', 'in an hour', 'in a few hours', 'will let you know',
    'write me', 'message me', 'remind me', 'contact me', 'call me',
    # Kyrgyz
    'жазам', 'чалам', 'байланышам', 'эртең', 'кечинде', 'кийинчерээк', 'билдирем',
]



_MANAGER_HANDOFF_RESPONSE_RE = re.compile(
    '|'.join([
        r'\bmanager\b.{0,80}\b(?:contact|reach|call|write|message|touch)\b',
        r'\bpassed\b.{0,80}\bmanager\b',
        r'\btransfer(?:red)?\b.{0,80}\bmanager\b',
        r'\u043c\u0435\u043d\u0435\u0434\u0436\u0435\u0440.{0,80}\u0441\u0432\u044f\u0436',
        r'\u043c\u0435\u043d\u0435\u0434\u0436\u0435\u0440.{0,80}\u043d\u0430\u043f\u0438\u0448',
        r'\u043c\u0435\u043d\u0435\u0434\u0436\u0435\u0440.{0,80}\u043f\u043e\u0437\u0432\u043e\u043d',
        r'\u043f\u0435\u0440\u0435\u0434\u0430[^\n]{0,80}\u043c\u0435\u043d\u0435\u0434\u0436',
        r'\u043f\u0435\u0440\u0435\u0434\u0430[^\n]{0,80}\u0432\u0430\u0441[^\n]{0,80}\u043c\u0435\u043d\u0435\u0434\u0436',
    ]),
    re.IGNORECASE | re.DOTALL,
)


class AgentService:
    """Autonomous AI agent for proactive lead outreach with enhanced capabilities."""

    def process_incoming_message(self, lead: Lead, message: str, channel: str, *, lightweight: bool = False) -> dict:
        """
        Process an incoming message from a lead with full autonomous analysis.

        This method is called when a lead sends a message via any channel.
        It analyzes the message, updates goals, handles objections, and
        potentially progresses the lead's status.

        Args:
            lead: The lead who sent the message
            message: The message text
            channel: The channel (telegram, instagram, whatsapp)

        Returns:
            dict with analysis results and actions taken
        """
        config = AIConfig.get_config(org=lead.organization)
        result = {
            'analyzed': True,
            'actions_taken': [],
            'stage_changed': False,
            'objection_detected': None,
            'goals_completed': [],
            'response_context': {},
        }

        # Promise lifecycle: any incoming message means the lead responded — clear pending promise
        update_fields = []
        _pending = lead.agent_context.get('pending_promise', {})
        if _pending and not _pending.get('followup_sent'):
            _ctx = lead.agent_context.copy()
            _ctx.pop('pending_promise', None)
            _ctx['ignore_schedule_before'] = timezone.now().isoformat()
            _ctx['last_fulfilled_promise'] = {
                'text': _pending.get('text', ''),
                'deadline': _pending.get('deadline'),
                'fulfilled_at': timezone.now().isoformat(),
            }
            lead.agent_context = _ctx
            update_fields.append('agent_context')
            result['actions_taken'].append('Promise fulfilled — lead responded')

        # Any inbound message cancels the previously scheduled AI follow-up for
        # this conversation turn, UNLESS it is an active assistant request (guest asked us to contact them).
        is_assistant_request = lead.agent_context.get('scheduled_followup_request', {}).get('kind') == 'assistant_request'
        if lead.next_follow_up_at and not is_assistant_request:
            if 'agent_context' not in update_fields:
                _ctx = lead.agent_context.copy()
                _ctx['ignore_schedule_before'] = timezone.now().isoformat()
                _ctx['last_fulfilled_promise'] = {
                    'text': lead.next_follow_up_hint,
                    'deadline': lead.next_follow_up_at.isoformat(),
                    'fulfilled_at': timezone.now().isoformat(),
                }
                lead.agent_context = _ctx
                update_fields.append('agent_context')
            lead.next_follow_up_at = None
            lead.next_follow_up_hint = ''
            update_fields.extend(['next_follow_up_at', 'next_follow_up_hint'])
            result['actions_taken'].append('Cleared scheduled follow-up — lead responded')
        elif lead.next_follow_up_at and is_assistant_request:
            result['actions_taken'].append('Kept scheduled assistant request')

        if update_fields:
            lead.save(update_fields=list(dict.fromkeys(update_fields)))

        if is_channel_ai_globally_paused(channel, config=config, lead=lead):
            result.update({
                'analyzed': False,
                'skipped': True,
                'skip_reason': f'{channel.title()} AI is paused globally',
            })
            return result

        # Get conversation history for context
        conversation_history = self._get_conversation_history(lead)

        # Step 1: Analyze the message
        basic_analysis = conversation_analyzer.analyze_message(lead, message, is_incoming=True)

        # Step 2: Deep AI analysis if enabled
        ai_analysis = {}
        if (
            not lightweight
            and (
                config.auto_status_progression
                or config.smart_objection_handling
                or config.conversation_goals_enabled
            )
        ):
            ai_analysis = conversation_analyzer.analyze_with_ai(lead, message, conversation_history)

        # Step 3: Handle objection detection
        objection_type = ai_analysis.get('objection_detected') or basic_analysis.get('objection_detected')
        if objection_type and config.smart_objection_handling:
            conversation_analyzer.process_objection(
                lead,
                objection_type,
                ai_analysis.get('objection_details', '')
            )
            result['objection_detected'] = objection_type
            result['actions_taken'].append(f'Recorded objection: {objection_type}')

            # Get rebuttal context for response generation
            rebuttal = self._get_objection_rebuttal(objection_type)
            if rebuttal:
                result['response_context']['objection_rebuttal'] = rebuttal

        # Step 4: Handle goal completions
        goals_achieved = ai_analysis.get('goals_achieved', []) + basic_analysis.get('goals_achieved', [])
        goals_achieved = list(set(goals_achieved))  # Deduplicate

        if goals_achieved and config.conversation_goals_enabled:
            completed = goal_manager.complete_goals_by_types(lead, goals_achieved)
            result['goals_completed'] = completed
            if completed:
                result['actions_taken'].append(f'Completed goals: {", ".join(result["goals_completed"])}')

        # Step 5: Extract and update contact data
        extracted = basic_analysis.get('extracted_data', {})
        if extracted.get('email') and not lead.email:
            lead.email = extracted['email']
            lead.save(update_fields=['email'])
            result['actions_taken'].append(f'Extracted email: {extracted["email"]}')

        if extracted.get('phone') and not lead.phone:
            lead.phone = extracted['phone']
            lead.save(update_fields=['phone'])
            result['actions_taken'].append(f'Extracted phone: {extracted["phone"]}')

        # Step 6: Handle status progression
        # First try AI analysis; fall back to basic keyword/signal analysis
        # (basic_analysis always fires for new/attempted leads on any inbound message)
        if config.auto_status_progression:
            new_status = (
                conversation_analyzer.should_progress_status(lead, ai_analysis)
                or basic_analysis.get('stage_signal')
            )
            if new_status:
                reason = ai_analysis.get('stage_reason', 'Inbound message received')
                conversation_analyzer.progress_lead_status(lead, new_status, reason)
                result['stage_changed'] = True
                result['new_status'] = new_status
                result['actions_taken'].append(f'Progressed status to: {new_status}')

                # Update goals for new stage
                if config.conversation_goals_enabled:
                    goal_manager.update_goals_for_stage_change(lead, new_status)

        # Step 7: Build response context for message generation
        if config.conversation_goals_enabled:
            result['response_context']['goals'] = goal_manager.get_goals_context_for_ai(lead)
            active_goals = lead.goals.filter(status=LeadGoal.STATUS_ACTIVE).order_by('-priority', '-created_at')
            if active_goals.exists():
                result['response_context']['primary_goal'] = active_goals.first().goal_type

        result['response_context']['sentiment'] = ai_analysis.get('sentiment', 'neutral')
        result['response_context']['urgency'] = ai_analysis.get('urgency_level', 'medium')
        result['response_context']['buying_signals'] = ai_analysis.get('buying_signals', [])

        # Step 8: Detect a new time-based promise/request in this message.
        # Deterministic assistant requests like "жду 2 минуты" must work even
        # in lightweight channel mode, because they are exact agreed follow-ups.
        _fast_assistant_request = self._extract_relative_deadline(message, ignore_hedging=True)
        if self._schedule_assistant_followup_request(lead, _fast_assistant_request, message):
            result['actions_taken'].append(
                f"Scheduled requested follow-up at {_fast_assistant_request['deadline']}"
            )
        elif not lightweight and self._has_promise_keywords(message):
            _promise_data = self._extract_promise(message, lead)
            if _promise_data:
                kind = _promise_data.get('kind') or 'lead_promise'
                if kind == 'assistant_request':
                    if self._schedule_assistant_followup_request(lead, _promise_data, message):
                        result['actions_taken'].append(
                            f"Scheduled requested follow-up at {_promise_data['deadline']}"
                        )
                else:
                    _ctx = lead.agent_context.copy()
                    _ctx['pending_promise'] = _promise_data
                    lead.agent_context = _ctx
                    lead.save(update_fields=['agent_context'])
                    result['actions_taken'].append(
                        f"Promise detected: will follow up after {_promise_data['deadline']}"
                    )
                    logger.info(
                        f'Promise detected for lead {lead.id}: deadline={_promise_data["deadline"]}'
                    )

        logger.info(f"Processed incoming message for lead {lead.id}: {len(result['actions_taken'])} actions taken")
        return result

    def generate_response_for_lead(self, lead: Lead, context: dict = None) -> Optional[str]:
        """
        Generate an AI response for a lead, incorporating autonomous context.

        Args:
            lead: The lead to respond to
            context: Optional context from process_incoming_message

        Returns:
            Generated message string or None
        """
        config = AIConfig.get_config()
        context = context or {}

        latest_guest_activity = self._get_latest_guest_message_activity(lead)
        if not latest_guest_activity:
            logger.info("No inbound guest message found for lead %s; skipping AI suggestion", lead.id)
            return None

        latest_guest_message = self._get_activity_text(latest_guest_activity)
        if not latest_guest_message:
            logger.info("Latest inbound guest message for lead %s has no text; skipping AI suggestion", lead.id)
            return None

        # Gather full lead context
        lead_context = self._gather_lead_context(lead)

        # Build the prompt with autonomous enhancements
        goals_context = context.get('goals', '')
        objection_context = ''
        if context.get('objection_rebuttal'):
            objection_context = f"\n\nOBJECTION HANDLING:\nThe lead raised an objection. Use this rebuttal guidance:\n{context['objection_rebuttal']}"

        primary_goal = context.get('primary_goal', '')
        goal_instruction = ''
        if primary_goal:
            goal_instruction = f"\n\nPRIMARY GOAL: Your main objective in this message is to {primary_goal.replace('_', ' ')}."

        sentiment = context.get('sentiment', 'neutral')
        urgency = context.get('urgency', 'medium')

        prompt = f"""You are an AI sales agent. Generate a response for this lead.

LEAD CONTEXT:
- Company: {lead_context['company_name']}
- Contact: {lead_context['contact_person']}
- Current Stage: {lead_context['stage_name']}
- Sentiment: {sentiment}
- Urgency Level: {urgency}

LATEST GUEST MESSAGE TO ANSWER:
{latest_guest_message}

{goals_context}
{objection_context}
{goal_instruction}

COMPANY PROFILE:
{config.company_profile}

INSTRUCTIONS:
1. Reply to the latest guest message above, not to manager notes, system events, or outgoing manager messages.
2. Use outgoing manager messages only as context so you do not contradict or repeat them.
3. Generate a natural, conversational response (2-4 sentences).
4. If handling an objection, address it empathetically but persistently.
5. Work toward the primary goal if specified.
6. Be warm and professional.
7. Include a clear next step or question.

Return ONLY the message text, nothing else."""

        from .ai_service import build_activity_history
        history = build_activity_history(lead)

        messages = [{"role": "system", "content": config.system_prompt}]
        if history:
            messages.append({"role": "system", "content": history})
        messages.extend(lead_context['conversation_history'])
        messages.append({"role": "user", "content": prompt})

        try:
            response = ai_service.generate_response_with_messages(messages)
            if response:
                response = response.strip()
                if response.startswith('"') and response.endswith('"'):
                    response = response[1:-1]
                return response
        except Exception as e:
            logger.error(f"Error generating response for lead {lead.id}: {e}", exc_info=True)

        return None

    def _get_activity_text(self, activity: LeadActivity) -> str:
        from .media_utils import activity_text_for_ai

        metadata = activity.metadata or {}
        return activity_text_for_ai(metadata, activity.description).strip()

    def _get_latest_guest_message_activity(self, lead: Lead) -> Optional[LeadActivity]:
        from .media_utils import is_media_only_activity_metadata

        activities = lead.activities.filter(
            activity_type__in=INBOUND_MESSAGE_ACTIVITY_TYPES,
        ).order_by('-created_at')[:20]

        for activity in activities:
            if is_media_only_activity_metadata(activity.metadata):
                continue
            if self._get_activity_text(activity):
                return activity
        return None

    def _get_objection_rebuttal(self, objection_type: str) -> Optional[str]:
        """Get rebuttal content for an objection type."""
        return None

    def _get_conversation_history(self, lead: Lead) -> list:
        """Get conversation history formatted for AI analysis."""
        messages = lead.activities.filter(
            activity_type__in=[
                'telegram_sent', 'telegram_received',
                'instagram_sent', 'instagram_received',
                'whatsapp_sent', 'whatsapp_received'
            ]
        ).order_by('-created_at')[:20]

        conversation = []
        for msg in reversed(list(messages)):
            role = 'assistant' if msg.activity_type in ['telegram_sent', 'instagram_sent', 'whatsapp_sent'] else 'user'
            text = self._get_activity_text(msg)
            conversation.append({'role': role, 'content': text})

        return conversation

    def _has_promise_keywords(self, message: str) -> bool:
        msg = message.lower()
        return any(kw in msg for kw in _PROMISE_KEYWORDS)

    def _looks_like_assistant_followup_request(self, message: str) -> bool:
        msg = (message or '').lower()
        request_markers = (
            'напиши', 'напишите', 'напомни', 'напомните', 'свяжитесь',
            'перезвоните', 'отправь', 'отправьте', 'скинь', 'скиньте',
            'покажи', 'покажите', 'write me', 'message me', 'remind me',
            'contact me', 'call me', 'send', 'show',
            'жду', 'подожду', 'ожидаю', 'буду ждать', 'wait',
        )
        return any(marker in msg for marker in request_markers)

    def _extract_relative_deadline(self, message: str, ignore_hedging: bool = False) -> dict | None:
        """Fast deterministic parser for common relative times like 'через 2 минуты'."""
        msg = (message or '').lower()
        # If it has ranges, uncertainty, or flexible phrasing, let the AI handle it, unless explicitly ignored.
        if not ignore_hedging:
            if '-' in msg or '–' in msg or '—' in msg or 'или' in msg or 'наверное' in msg or 'примерно' in msg or 'где-то' in msg or 'может' in msg:
                return None
        patterns = [
            r'через\s+(?P<a>\d+)(?:\s*[-–—]\s*(?P<b>\d+))?\s*(?P<unit>минут\w*|мин\.?|час\w*|дн\w*)',
            r'(?P<unit>минут\w*|мин\.?|час\w*)\s+через\s+(?P<a>\d+)(?:\s*[-–—]\s*(?P<b>\d+))?',
            r'(?:жду|подожду|ожидаю|буду\s+ждать)\s+(?P<a>\d+)(?:\s*[-–—]\s*(?P<b>\d+))?\s*(?P<unit>минут\w*|мин\.?|час\w*|дн\w*)',
            r'(?:wait|waiting)\s+(?P<a>\d+)(?:\s*[-–—]\s*(?P<b>\d+))?\s*(?P<unit>minute\w*|min\.?|hour\w*|day\w*)',
            r'in\s+(?P<a>\d+)(?:\s*[-–—]\s*(?P<b>\d+))?\s*(?P<unit>minute\w*|min\.?|hour\w*|day\w*)',
        ]
        match = None
        for pattern in patterns:
            match = re.search(pattern, msg, flags=re.IGNORECASE | re.UNICODE)
            if match:
                break
        if not match:
            return None

        amount = int(match.group('b') or match.group('a'))
        unit = match.group('unit')
        if unit.startswith(('мин', 'minute', 'min')):
            delta = timedelta(minutes=amount)
        elif unit.startswith(('час', 'hour')):
            delta = timedelta(hours=amount)
        elif unit.startswith(('дн', 'day')):
            delta = timedelta(days=amount)
        else:
            return None

        deadline = timezone.now() + delta
        return {
            'deadline': deadline.isoformat(),
            'text': message[:200],
            'detected_at': timezone.now().isoformat(),
            'followup_sent': False,
            'kind': 'assistant_request' if self._looks_like_assistant_followup_request(message) else 'lead_promise',
        }

    def _schedule_assistant_followup_request(self, lead: Lead, request_data: dict, message: str) -> bool:
        if not request_data or request_data.get('kind') != 'assistant_request':
            return False
        follow_up_at = self._deadline_to_utc(request_data.get('deadline'), lead)
        if not follow_up_at or follow_up_at <= timezone.now():
            return False
        _ctx = lead.agent_context.copy()
        _ctx['scheduled_followup_request'] = request_data
        lead.agent_context = _ctx
        lead.next_follow_up_at = follow_up_at
        lead.next_follow_up_hint = (
            f'Guest asked us to write later: "{request_data.get("text", message[:160])}"'
        )[:500]
        lead.save(update_fields=['agent_context', 'next_follow_up_at', 'next_follow_up_hint'])
        logger.info(
            f'Guest-requested follow-up scheduled for lead {lead.id}: '
            f'deadline={request_data["deadline"]}'
        )
        return True

    def _deadline_to_utc(self, raw_deadline: str, lead: Lead):
        try:
            from datetime import datetime, timezone as datetime_timezone
            import zoneinfo

            cleaned = str(raw_deadline).replace('Z', '+00:00')
            dt = datetime.fromisoformat(cleaned)
            if dt.tzinfo is None:
                local_tz = zoneinfo.ZoneInfo(lead.timezone or 'Asia/Bishkek')
                dt = dt.replace(tzinfo=local_tz)
            return dt.astimezone(datetime_timezone.utc)
        except Exception as exc:
            logger.warning(f'Failed to parse follow-up deadline for lead {lead.id}: {raw_deadline} ({exc})')
            return None

    def _get_followup_prompt_context(self, lead: Lead) -> str:
        """
        Load sales-editable follow-up guidance from active playbooks and agent configs.
        This keeps the policy in prompts/docs while the code only executes dates.
        """
        try:
            from django.db.models import Q
            from apps.hotel_info.models import Playbook
            from apps.flows.models import AgentConfig

            extra_guidance = ""
            if lead and lead.organization_id:
                agent_config = AgentConfig.objects.filter(name='followup', organization=lead.organization).first()
                if agent_config and agent_config.system_prompt:
                    extra_guidance = f"{agent_config.system_prompt}\n\n"

            qs = Playbook.objects.filter(is_active=True)
            if lead and lead.organization_id:
                qs = qs.filter(organization=lead.organization)
            qs = qs.filter(
                Q(name__icontains='follow')
                | Q(name__icontains='follow-up')
                | Q(name__icontains='напомин')
                | Q(name__icontains='обещ')
                | Q(name__icontains='перезвон')
                | Q(trigger_description__icontains='follow')
                | Q(trigger_description__icontains='напомин')
                | Q(trigger_description__icontains='обещ')
                | Q(trigger_description__icontains='перезвон')
            ).order_by('order', 'id')[:3]

            blocks = []
            for pb in qs:
                text = '\n'.join(
                    part for part in (pb.instructions, pb.content)
                    if part and part.strip()
                ).strip()
                if text:
                    blocks.append(f"[{pb.name}]\n{text[:1500]}")
            
            playbook_text = ""
            if blocks:
                playbook_text = "Sales-editable follow-up guidance from playbooks:\n" + "\n\n".join(blocks) + "\n\n"

            return f"{extra_guidance}{playbook_text}"
        except Exception as exc:
            logger.warning(f'Follow-up prompt context load failed: {exc}')
            return ''

    def _extract_promise(self, message: str, lead: Lead) -> dict | None:
        """Extract a lead promise or a guest request for us to follow up later."""
        deterministic = self._extract_relative_deadline(message)
        if deterministic:
            return deterministic

        if not ai_service.is_configured():
            return None
        now = timezone.now()
        prompt_context = self._get_followup_prompt_context(lead)
        prompt = (
            f'Does this message contain either of these time-based follow-up signals?\n'
            f'A) The lead promises to write/call/respond later.\n'
            f'B) The lead asks the assistant/hotel to write/call/remind/contact them later.\n'
            f'Message: "{message}"\n'
            f'Current date-time (UTC+6 Bishkek): {now.strftime("%Y-%m-%d %H:%M")}\n\n'
            f'{prompt_context}'
            'If YES — extract the deadline as an ISO datetime (best approximation).\n'
            'Examples: "напишу завтра до обеда" → next day ~12:00, kind="lead_promise"; '
            '"напишите мне через 2 минуты" → current time + 2 minutes, kind="assistant_request"; '
            '"remind me tomorrow" → next day ~10:00, kind="assistant_request".\n'
            'Hedged/uncertain phrasing still counts when a future time is present.\n'
            'For ranges, use the later bound unless the prompt context says otherwise.\n\n'
            'Respond ONLY as JSON:\n'
            '{"has_promise": true, "kind": "lead_promise|assistant_request", "deadline": "YYYY-MM-DDTHH:MM:SS", "promise_text": "exact phrase"}\n'
            'or: {"has_promise": false}'
        )
        try:
            _max_tokens = 2048 if getattr(ai_service, 'provider', None) == 'gemini' else 100
            response = ai_service.client.chat.completions.create(
                model=ai_service._model,
                messages=[{'role': 'user', 'content': prompt}],
                response_format={'type': 'json_object'},
                temperature=0,
                max_tokens=_max_tokens,
            )
            data = json.loads(response.choices[0].message.content)
            if data.get('has_promise'):
                deadline = data.get('deadline')
                if not deadline:
                    det = self._extract_relative_deadline(message, ignore_hedging=True)
                    if det:
                        deadline = det.get('deadline')
                if deadline:
                    return {
                        'deadline': deadline,
                        'text': data.get('promise_text', message[:200]),
                        'detected_at': now.isoformat(),
                        'followup_sent': False,
                        'kind': data.get('kind') or (
                            'assistant_request'
                            if self._looks_like_assistant_followup_request(message)
                            else 'lead_promise'
                        ),
                    }
        except Exception as e:
            logger.warning(f'Promise extraction failed for lead {lead.id}: {e}')
        return None

    def _schedule_next_followup(self, lead_id: int, conversation_summary: str, sent_activity_id: int | None = None) -> None:
        """
        Background task: ask AI when to schedule the next proactive follow-up or
        agreed/promised follow-up time, then persist it to Lead.next_follow_up_at.

        Called (via daemon thread) after each successful AI response so the webhook
        is never blocked. Silently swallows all errors — scheduling is best-effort.
        """
        from django.db import close_old_connections
        close_old_connections()
        try:
            lead = Lead.objects.select_related('organization').get(id=lead_id)
            config = AIConfig.get_config(org=lead.organization)

            if lead.ai_paused:
                Lead.objects.filter(id=lead_id).update(next_follow_up_at=None, next_follow_up_hint='')
                logger.info(
                    f"Skipping follow-up scheduling for lead {lead_id}: AI is paused "
                    f"(paused_by={lead.ai_paused_by or 'unknown'})"
                )
                return

            if sent_activity_id:
                sent_activity = LeadActivity.objects.filter(id=sent_activity_id, lead=lead).only('id', 'created_at').first()
                if not sent_activity:
                    logger.info(f'Skipping follow-up scheduling for lead {lead_id}: sent activity disappeared')
                    return
                newer_outgoing_exists = LeadActivity.objects.filter(
                    lead=lead,
                    id__gt=sent_activity_id,
                    activity_type__in=[
                        LeadActivity.TYPE_TELEGRAM_SENT,
                        LeadActivity.TYPE_INSTAGRAM_SENT,
                        LeadActivity.TYPE_WHATSAPP_SENT,
                    ],
                ).exists()
                if newer_outgoing_exists:
                    logger.info(
                        f'Skipping stale follow-up scheduling for lead {lead_id}: '
                        f'newer outgoing message exists after activity {sent_activity_id}'
                    )
                    return
                newer_inbound_exists = LeadActivity.objects.filter(
                    lead=lead,
                    created_at__gt=sent_activity.created_at,
                    activity_type__in=[
                        LeadActivity.TYPE_TELEGRAM_RECEIVED,
                        LeadActivity.TYPE_INSTAGRAM_RECEIVED,
                        LeadActivity.TYPE_WHATSAPP_RECEIVED,
                    ],
                ).exists()
                if newer_inbound_exists:
                    logger.info(
                        f'Skipping follow-up scheduling for lead {lead_id}: '
                        f'lead already responded after activity {sent_activity_id}'
                    )
                    return

            if not config.proactive_outreach_enabled or not ai_service.is_configured():
                return

            remaining = config.max_followup_attempts - lead.ai_followup_count
            if remaining <= 0:
                return

            now = timezone.now()
            tz_name = lead.timezone or 'Asia/Bishkek'
            import zoneinfo
            local_tz = zoneinfo.ZoneInfo(tz_name)
            local_now = now.astimezone(local_tz)

            # Retrieve conversation history from DB to ensure it includes the latest outgoing response
            conv_history = self._get_conversation_history(lead)
            conversation_text = ""
            for turn in conv_history[-6:]:
                role_name = "Guest" if turn['role'] == 'user' else "AI Bot"
                conversation_text += f"{role_name}: {turn['content']}\n"

            if not conversation_text:
                conversation_text = f"Guest: {conversation_summary}"

            prompt_context = self._get_followup_prompt_context(lead)
            ignore_schedule_before = (lead.agent_context or {}).get('ignore_schedule_before')
            fulfilled_promise = (lead.agent_context or {}).get('last_fulfilled_promise') or {}
            fulfilled_note = ''
            if ignore_schedule_before:
                fulfilled_note = (
                    f"Important lifecycle state:\n"
                    f"- The guest has already responded at/after {ignore_schedule_before}.\n"
                    f"- Ignore any old promise/request made before that moment; it is already fulfilled.\n"
                )
                if fulfilled_promise.get('text'):
                    fulfilled_note += f"- Fulfilled promise text: \"{fulfilled_promise.get('text')}\"\n"
                if fulfilled_promise.get('deadline'):
                    fulfilled_note += f"- Fulfilled promise deadline: {fulfilled_promise.get('deadline')}\n"
                fulfilled_note += (
                    "- Only schedule a specific time if the latest guest message or your latest bot reply "
                    "created a new future promise after that moment.\n\n"
                )

            prompt = (
                f"You just replied to a lead. Decide when to schedule the next follow-up message.\n\n"
                f"Current local time ({tz_name}): {local_now.strftime('%A, %Y-%m-%d %H:%M')}\n"
                f"Remaining follow-up budget: {remaining} of {config.max_followup_attempts}\n\n"
                f"{prompt_context}"
                f"{fulfilled_note}"
                f"Recent conversation:\n{conversation_text}\n\n"
                f"Task:\n"
                f"1. Check if there is an agreed, promised, or requested specific time/date for the next follow-up/contact in the recent conversation (e.g., guest asked to be contacted today at 19:00, or bot promised to reply tomorrow at 10:00).\n"
                f"   - Do not reuse a specific-time promise if the guest has already responded after it.\n"
                f"2. If YES:\n"
                f"   - Set 'has_scheduled_time' to true.\n"
                f"   - Calculate the exact scheduled datetime in ISO format (YYYY-MM-DDTHH:MM:SS) in the local timezone ({tz_name}), taking into account the current time.\n"
                f"   - Set 'reason' to a short explanation of what was scheduled.\n"
                f"3. If NO (proactive follow-up fallback):\n"
                f"   - Set 'has_scheduled_time' to false.\n"
                f"   - Decide when to send the next proactive follow-up IF the lead goes silent:\n"
                f"     * Interested lead, active conversation -> 8-24 hours\n"
                f"     * Lukewarm / browsing -> 24-48 hours\n"
                f"     * Cold or just checking prices -> 48-72 hours\n"
                f"     * If conversation is fully resolved or lead booked -> 0 hours\n"
                f"   - Set 'hours_until_next' to the number of hours.\n"
                f"   - Set 'reason' to a short explanation.\n\n"
                f"Respond ONLY as JSON in this format:\n"
                f"{{\n"
                f"  \"has_scheduled_time\": true,\n"
                f"  \"scheduled_datetime\": \"YYYY-MM-DDTHH:MM:SS\",\n"
                f"  \"hours_until_next\": 0,\n"
                f"  \"reason\": \"...\"\n"
                f"}}"
            )

            _max_tokens = 2048 if getattr(ai_service, 'provider', None) == 'gemini' else 150
            resp = ai_service.client.chat.completions.create(
                model=ai_service._model,
                messages=[{'role': 'user', 'content': prompt}],
                response_format={'type': 'json_object'},
                temperature=0,
                max_tokens=_max_tokens,
            )
            data = json.loads(resp.choices[0].message.content)

            follow_up_at = None
            hint = data.get('reason', '')[:500]

            if data.get('has_scheduled_time') and data.get('scheduled_datetime'):
                try:
                    from datetime import datetime, timezone as datetime_timezone
                    dt_naive = datetime.fromisoformat(data['scheduled_datetime'])
                    if dt_naive.tzinfo is None:
                        dt_aware = dt_naive.replace(tzinfo=local_tz)
                    else:
                        dt_aware = dt_naive

                    follow_up_at = dt_aware.astimezone(datetime_timezone.utc)
                    if follow_up_at < now:
                        # Don't schedule in the past
                        follow_up_at = None
                        logger.warning(f"AI returned scheduled_datetime in the past: {data['scheduled_datetime']}")
                    else:
                        fulfilled_deadline_raw = fulfilled_promise.get('deadline')
                        if fulfilled_deadline_raw:
                            try:
                                fulfilled_deadline = datetime.fromisoformat(fulfilled_deadline_raw)
                                if fulfilled_deadline.tzinfo is None:
                                    fulfilled_deadline = fulfilled_deadline.replace(tzinfo=local_tz)
                                fulfilled_deadline_utc = fulfilled_deadline.astimezone(datetime_timezone.utc)
                                if abs((follow_up_at - fulfilled_deadline_utc).total_seconds()) <= 60:
                                    logger.info(
                                        f'Ignoring stale fulfilled follow-up deadline for lead {lead.id}: '
                                        f'{follow_up_at}'
                                    )
                                    follow_up_at = None
                                    data['has_scheduled_time'] = False
                                    data['hours_until_next'] = data.get('hours_until_next') or 24
                            except Exception as stale_parse_err:
                                logger.warning(
                                    f"Failed to parse fulfilled promise deadline "
                                    f"{fulfilled_deadline_raw}: {stale_parse_err}"
                                )
                        if follow_up_at:
                            logger.info(f"AI scheduled exact follow-up for lead {lead.id} at {follow_up_at} (local: {dt_aware})")
                except Exception as parse_err:
                    logger.warning(f"Failed to parse scheduled_datetime {data.get('scheduled_datetime')}: {parse_err}")

            if not follow_up_at:
                hours = int(data.get('hours_until_next', 0))
                if hours <= 0:
                    Lead.objects.filter(id=lead_id).update(
                        next_follow_up_at=None, next_follow_up_hint=''
                    )
                    logger.info(f'No follow-up scheduled for lead {lead_id} — conversation resolved')
                    return

                # Default proactive follow-up is now 10 minutes (0.16 hours) if lead goes silent
                follow_up_at = now + timedelta(minutes=10)
                hint = f"10-minute idle follow-up: {hint}"
                logger.info(
                    f'Scheduled proactive 10-minute follow-up for lead {lead_id} at {follow_up_at} '
                    f'— {hint[:80]}'
                )

            # Multiple scheduling threads may finish out of order after rapid
            # chat turns. Keep the earliest future appointment so a generic
            # proactive follow-up cannot overwrite "write in 2 minutes".
            current_schedule = (
                Lead.objects
                .filter(id=lead_id)
                .values('next_follow_up_at', 'next_follow_up_hint')
                .first()
            )
            existing_follow_up_at = (
                current_schedule.get('next_follow_up_at')
                if current_schedule else None
            )
            if (
                existing_follow_up_at
                and existing_follow_up_at > now
                and existing_follow_up_at <= follow_up_at
            ):
                logger.info(
                    f'Keeping earlier follow-up for lead {lead_id} at '
                    f'{existing_follow_up_at}; new candidate was {follow_up_at}'
                )
                return

            Lead.objects.filter(id=lead_id).update(
                next_follow_up_at=follow_up_at,
                next_follow_up_hint=hint,
            )
        except Exception as e:
            logger.warning(f'_schedule_next_followup failed for lead {lead_id}: {e}')


    def schedule_idle_or_promise_followup(self, lead: Lead, combined_text: str, conversation_history: list, sent_activity_id: int) -> None:
        """
        Schedule either an exact promise follow-up (using LLM in background thread)
        if promise keywords are present, or a default 10-minute idle follow-up directly.
        """
        config = AIConfig.get_config(org=lead.organization)
        if not config.proactive_outreach_enabled:
            return

        try:
            lead.refresh_from_db(fields=['ai_paused', 'ai_paused_by', 'next_follow_up_at', 'next_follow_up_hint'])
        except Exception:
            pass

        if lead.ai_paused:
            Lead.objects.filter(id=lead.id).update(next_follow_up_at=None, next_follow_up_hint='')
            logger.info(
                f"Lead {lead.id}: follow-up scheduling skipped because AI is paused "
                f"(paused_by={lead.ai_paused_by or 'unknown'})"
            )
            return

        sent_text = ''
        if sent_activity_id:
            try:
                sent_activity = LeadActivity.objects.filter(id=sent_activity_id, lead=lead).only('metadata', 'description').first()
                if sent_activity:
                    sent_text = (sent_activity.metadata or {}).get('text') or sent_activity.description or ''
            except Exception as exc:
                logger.warning(f"Lead {lead.id}: could not inspect sent activity {sent_activity_id}: {exc}")

        if sent_text and _MANAGER_HANDOFF_RESPONSE_RE.search(sent_text):
            Lead.objects.filter(id=lead.id).update(next_follow_up_at=None, next_follow_up_hint='')
            logger.info(
                f"Lead {lead.id}: follow-up scheduling skipped after manager handoff response"
            )
            return

        if self._has_promise_keywords(combined_text):
            import threading
            _conv_summary = '\n'.join(
                m.get('content', '')[:200] for m in conversation_history[-4:]
            ) if conversation_history else combined_text[:300]
            threading.Thread(
                target=self._schedule_next_followup,
                args=(lead.id, _conv_summary, sent_activity_id),
                daemon=True,
            ).start()
            logger.info(f"Lead {lead.id}: dispatched LLM promise follow-up scheduling")
        else:
            follow_up_at = timezone.now() + timedelta(minutes=10)
            Lead.objects.filter(id=lead.id).update(
                next_follow_up_at=follow_up_at,
                next_follow_up_hint="Lead idle for 10 minutes after bot reply"
            )
            logger.info(f"Lead {lead.id}: scheduled 10-minute idle follow-up directly at {follow_up_at}")

    def execute_pending_auto_tasks(self, lead: Lead = None) -> dict:
        """
        Execute all pending auto-executable tasks.

        Args:
            lead: Optional lead to filter tasks for

        Returns:
            dict with execution results
        """
        config = AIConfig.get_config()

        if not config.auto_execute_tasks:
            return {'executed': 0, 'failed': 0, 'disabled': True}

        tasks = task_executor.get_pending_auto_tasks(lead)
        executed = 0
        failed = 0

        for task in tasks:
            if task_executor.execute_task(task):
                executed += 1
            else:
                failed += 1

        logger.info(f"Auto-task execution: {executed} executed, {failed} failed")
        return {'executed': executed, 'failed': failed}

    def create_smart_task(
        self,
        lead: Lead,
        title: str,
        task_type: str,
        auto_execute: bool = True,
        execution_type: str = 'send_message',
        days_due: int = 1,
        description: str = '',
        execution_content: str = ''
    ) -> Task:
        """
        Create a smart task that can be auto-executed.

        Args:
            lead: The lead for this task
            title: Task title
            task_type: Type of task (call, email, follow_up, etc.)
            auto_execute: Whether the task should be auto-executed
            execution_type: How to execute (send_message, send_document, schedule_followup)
            days_due: Days until due
            description: Task description
            execution_content: Content to use for execution

        Returns:
            Created Task object
        """
        return task_executor.create_auto_task(
            lead=lead,
            title=title,
            task_type=task_type,
            execution_type=execution_type if auto_execute else 'none',
            days_due=days_due,
            description=description,
            execution_content=execution_content
        )

    def initialize_lead_goals(self, lead: Lead) -> list:
        """
        Initialize conversation goals for a new or existing lead.

        Creates appropriate goals based on the lead's current status
        and missing information.

        Returns:
            List of created LeadGoal objects
        """
        config = AIConfig.get_config()

        if not config.conversation_goals_enabled:
            return []

        return goal_manager.create_initial_goals(lead)

    def run_agent_check(self, force: bool = False) -> dict:
        """
        Main agent loop - check all leads and send follow-ups where needed.

        Args:
            force: If True (manual trigger), skip inactivity threshold checks and send to all eligible leads

        Returns:
            Dictionary with results: {processed: int, messaged: int, skipped: int, errors: int}
        """
        config = AIConfig.get_config()

        if not config.proactive_outreach_enabled:
            logger.info("Proactive outreach is disabled")
            return {'processed': 0, 'messaged': 0, 'skipped': 0, 'errors': 0, 'disabled': True}

        if not ai_service.is_configured():
            logger.warning("AI service not configured - cannot run agent")
            return {'processed': 0, 'messaged': 0, 'skipped': 0, 'errors': 0, 'ai_not_configured': True}

        results = {'processed': 0, 'messaged': 0, 'skipped': 0, 'errors': 0}

        # Get all leads that are candidates for follow-up
        leads = self._get_followup_candidates(config)

        for lead in leads:
            results['processed'] += 1

            try:
                should_follow_up, reason = self._should_follow_up(lead, config, force=force)

                if not should_follow_up:
                    logger.debug(f"Skipping lead {lead.id} ({lead.contact_person}): {reason}")
                    results['skipped'] += 1
                    continue

                # Generate and send the message
                success = self._send_followup(lead, config, force=force)

                if success:
                    results['messaged'] += 1
                else:
                    results['skipped'] += 1

            except Exception as e:
                logger.error(f"Error processing lead {lead.id}: {e}", exc_info=True)
                results['errors'] += 1

        logger.info(f"Agent check complete: {results}")
        return results

    def _get_followup_candidates(self, config: AIConfig):
        """Get leads that are potential candidates for follow-up."""
        # Get final stage keys to exclude
        final_stages = PipelineStage.objects.filter(is_final=True).values_list('key', flat=True)
        now = timezone.now()

        # Query leads that:
        # 1. Are not in final stages
        # 2. Have a communication channel (Telegram, Instagram, or WhatsApp)
        # 3. Are not marked do_not_contact
        # 4. Haven't exceeded max follow-up attempts unless a follow-up is already scheduled
        leads = Lead.objects.filter(
            do_not_contact=False,
            ai_paused=False,
        ).filter(
            Q(telegram_chat_id__gt='') | Q(instagram_user_id__gt='') | Q(whatsapp_phone__gt='')
        ).exclude(
            status__in=list(final_stages)
        ).filter(
            Q(ai_followup_count__lt=config.max_followup_attempts)
            | Q(next_follow_up_at__lte=now)
            | Q(agent_context__pending_promise__followup_sent=False)
        )

        # Deduplicate candidates to avoid spamming if duplicate leads exist for the same chat/channel.
        # Group by channel identifier and keep only the latest active lead (by id / created_at).
        active_candidates = []
        seen_tg = set()
        seen_ig = set()
        seen_wa = set()

        for lead in leads.order_by('-id'):
            is_valid = False

            # Check Telegram
            if lead.telegram_chat_id:
                if lead.telegram_chat_id in seen_tg:
                    continue
                seen_tg.add(lead.telegram_chat_id)
                is_valid = True

            # Check Instagram
            if lead.instagram_user_id:
                if lead.instagram_user_id in seen_ig:
                    continue
                seen_ig.add(lead.instagram_user_id)
                is_valid = True

            # Check WhatsApp
            if lead.whatsapp_phone:
                if lead.whatsapp_phone in seen_wa:
                    continue
                seen_wa.add(lead.whatsapp_phone)
                is_valid = True

            if is_valid:
                active_candidates.append(lead)

        return active_candidates

    def _should_follow_up(self, lead: Lead, config: AIConfig, force: bool = False) -> tuple[bool, str]:
        """
        Determine if a lead should receive a follow-up message.

        Args:
            lead: The lead to evaluate
            config: AI configuration settings
            force: If True (manual trigger), skip timing checks

        Returns:
            (should_follow_up: bool, reason: str)
        """
        now = timezone.now()

        # Check if lead has a communication channel configured (always required)
        has_telegram = lead.telegram_chat_id and telegram_service.is_configured_sync() and not is_channel_ai_globally_paused('telegram', config=config, lead=lead)
        has_instagram = lead.instagram_user_id and instagram_service.is_configured() and not is_channel_ai_globally_paused('instagram', config=config, lead=lead)
        has_whatsapp = lead.whatsapp_phone and whatsapp_service.is_configured(org=lead.organization) and not is_channel_ai_globally_paused('whatsapp', config=config, lead=lead)

        if not has_telegram and not has_instagram and not has_whatsapp:
            return False, "No active AI messaging channel"

        # Check if lead is in a final stage (always skip these)
        stage = self._get_lead_stage(lead)
        if stage and stage.is_final:
            return False, f"Lead is in final stage '{stage.name}'"

        # Check for an unfulfilled promise whose deadline has passed (highest priority)
        _pending_promise = lead.agent_context.get('pending_promise', {})
        if _pending_promise and not _pending_promise.get('followup_sent'):
            _deadline_str = _pending_promise.get('deadline')
            if _deadline_str:
                try:
                    from datetime import datetime
                    _deadline = datetime.fromisoformat(_deadline_str)
                    if not _deadline.tzinfo:
                        from django.utils.timezone import make_aware
                        _deadline = make_aware(_deadline)
                    if now > _deadline:
                        return True, f"Promise deadline passed: \"{_pending_promise.get('text', '')[:80]}\""
                except Exception as _e:
                    logger.warning(f'Failed to parse promise deadline for lead {lead.id}: {_e}')

        # AI-scheduled follow-up takes full control over timing for this lead
        if lead.next_follow_up_at:
            hours_overdue = (now - lead.next_follow_up_at).total_seconds() / 3600
            if hours_overdue < 0:
                # Still in the future — wait
                return False, f"Scheduled for {lead.next_follow_up_at.strftime('%Y-%m-%d %H:%M')}"
            if hours_overdue > 48:
                # Celery was likely down — stale schedule, clear and fall through to inactivity
                Lead.objects.filter(id=lead.id).update(next_follow_up_at=None, next_follow_up_hint='')
                lead.next_follow_up_at = None
                logger.info(f'Cleared stale follow-up schedule for lead {lead.id} (overdue {hours_overdue:.0f}h)')
            else:
                return True, f"Scheduled follow-up: {lead.next_follow_up_hint[:80] or 'AI-decided'}"

        # For manual triggers (force=True), skip timing checks
        if force:
            return True, "Manual trigger - force send"

        if lead.ai_followup_count >= config.max_followup_attempts:
            return False, f"Reached follow-up limit ({lead.ai_followup_count}/{config.max_followup_attempts})"

        # Check if we've already followed up recently (within check frequency)
        if lead.last_ai_followup_at:
            hours_since_followup = (now - lead.last_ai_followup_at).total_seconds() / 3600
            if hours_since_followup < config.check_frequency_hours:
                return False, f"Recent follow-up ({hours_since_followup:.1f}h ago)"

        # Check days since last activity
        last_activity = self._get_last_activity_date(lead)
        if last_activity:
            days_since_activity = (now.date() - last_activity).days
            if days_since_activity < config.inactivity_threshold_days:
                return False, f"Recent activity ({days_since_activity} days ago)"

        return True, "Ready for follow-up"

    def _get_last_activity_date(self, lead: Lead):
        """Get the date of the last meaningful activity for a lead."""
        # Check last_contacted field
        if lead.last_contacted:
            return lead.last_contacted

        # Check last activity timestamp
        last_activity = lead.activities.first()
        if last_activity:
            return last_activity.created_at.date()

        # Fall back to lead creation date
        return lead.created_at.date()

    def _get_lead_stage(self, lead: Lead) -> PipelineStage | None:
        """Get the pipeline stage for a lead based on its status."""
        try:
            return PipelineStage.objects.filter(
                key=lead.status
            ).first()
        except Exception:
            return None

    def _gather_lead_context(self, lead: Lead) -> dict:
        """Gather all relevant context for a lead to generate a follow-up message."""
        # Get recent activities
        activities = lead.activities.all()[:10]
        activity_summary = []
        for activity in activities:
            desc = activity.description or ""
            if 'AI sent ' in desc and 'photo(s)' in desc:
                continue
            activity_summary.append({
                'type': activity.get_activity_type_display(),
                'description': activity.description,
                'date': activity.created_at.strftime('%Y-%m-%d %H:%M')
            })

        # Get notes
        notes = lead.lead_notes.all()[:5]
        notes_text = [note.content for note in notes]

        # Get conversation history from activities
        messages = lead.activities.filter(
            activity_type__in=['telegram_sent', 'telegram_received', 'instagram_sent', 'instagram_received', 'whatsapp_sent', 'whatsapp_received']
        ).order_by('-created_at')[:20]

        conversation = []
        for msg in reversed(list(messages)):
            role = 'assistant' if msg.activity_type in ['telegram_sent', 'instagram_sent', 'whatsapp_sent'] else 'user'
            text = self._get_activity_text(msg)
            if text and 'AI sent ' in text and 'photo(s)' in text:
                continue
            conversation.append({'role': role, 'content': text})

        # Get stage info
        stage = self._get_lead_stage(lead)

        return {
            'lead_id': lead.id,
            'company_name': lead.contact_person or 'Unknown',
            'contact_person': lead.contact_person or 'Unknown',
            'status': lead.status,
            'stage_name': stage.name if stage else lead.status,
            'stage_description': stage.description if stage else '',
            'days_since_last_contact': (timezone.now().date() - self._get_last_activity_date(lead)).days,
            'followup_attempt': lead.ai_followup_count + 1,
            'notes': notes_text,
            'recent_activities': activity_summary,
            'conversation_history': conversation,
            'estimated_value': str(lead.estimated_value) if lead.estimated_value else None,
            'source': lead.source,
            'pending_promise': lead.agent_context.get('pending_promise'),
        }

    def _generate_followup_message(self, lead: Lead, context: dict, config: AIConfig) -> str | None:
        """Generate a contextual follow-up message using AI with autonomous enhancements."""
        # Get goals context if enabled
        goals_context = ''
        goal_instruction = ''
        if config.conversation_goals_enabled:
            goals_context = goal_manager.get_goals_context_for_ai(lead)
            active_goals = lead.goals.filter(status=LeadGoal.STATUS_ACTIVE).order_by('-priority', '-created_at')
            if active_goals.exists():
                primary_goal = active_goals.first()
                if primary_goal.priority > LeadGoal.PRIORITY_LOW:
                    goal_instruction = f"\n\nPRIMARY GOAL: Your main objective is to {primary_goal.goal_type.replace('_', ' ')}. Work toward this naturally in your message."

        # Get objection context if there's a current objection
        objection_context = ''
        if lead.current_objection and config.smart_objection_handling:
            rebuttal = self._get_objection_rebuttal(lead.current_objection)
            if rebuttal:
                objection_context = f"\n\nOBJECTION TO ADDRESS:\nThe lead previously raised a {lead.current_objection} objection. Address it using this guidance:\n{rebuttal[:500]}"

        # Promise context — if the lead made a commitment and didn't follow through
        promise_context = ''
        _pp = context.get('pending_promise', {})
        if _pp and not _pp.get('followup_sent'):
            promise_context = (
                f'\n\nIMPORTANT — BROKEN PROMISE FOLLOW-UP:\n'
                f'The lead previously said: "{_pp.get("text", "")}"\n'
                f'They promised to write/call by {_pp.get("deadline", "a specific time")} but never did.\n'
                f'Gently reference this: acknowledge they mentioned they would write, remain warm and patient, '
                f'and ask if they are still interested or if anything came up.'
            )

        # Scheduled follow-up context — if a specific follow-up time was agreed/scheduled
        scheduled_context = ''
        if lead.next_follow_up_hint:
            hint_str = lead.next_follow_up_hint
            if "10-minute" in hint_str or "10 minutes" in hint_str or "idle" in hint_str:
                scheduled_context = (
                    f'\n\nIMPORTANT — 10-MINUTE IDLE NUDGE:\n'
                    f'The guest has been silent for 10 minutes since your last response.\n'
                    f'Act as a proactive, friendly, but highly focused sales manager.\n'
                    f'Gently follow up to check if they are ready to proceed with booking or have any questions.\n'
                    f'CRITICAL: Do NOT apologize for keeping them waiting, and do NOT apologize for the delay (you did not delay; the guest went silent).\n'
                    f'CRITICAL GREETING RULE (ПРАВИЛО ПРИВЕТСТВИЯ):\n'
                    f'Always use the time-neutral greeting "Доброго времени суток" (or no greeting at all if the conversation flows naturally without it).\n'
                    f'NEVER use time-specific greetings like "Добрый день", "Доброе утро", "Добрый вечер", or "Доброй ночи" under any circumstances because it could be night or another time of day.\n'
                    f'Приветствие должно быть строго нейтральным по времени суток. Пишите исключительно "Доброго времени суток" (или обходитесь без приветствия, если диалог продолжается естественно). Категорически ЗАПРЕЩЕНО писать "Добрый день", "Доброе утро", "Добрый вечер" или "Доброй ночи", так как автосообщение отправляется в любое время суток.\n'
                    f'Instead, focus on moving the booking forward naturally and presenting the value of Nomad Camp.'
                )
            else:
                scheduled_context = (
                    f'\n\nIMPORTANT — SCHEDULED FOLLOW-UP:\n'
                    f'This message is being sent at a scheduled time because: "{lead.next_follow_up_hint}".\n'
                    f'Make sure to address this context directly. For example, if you promised to tell them about rooms at 19:00, '
                    f'provide the rooms information or pick up the booking conversation exactly where it left off, referencing the scheduled time if appropriate.\n'
                    f'CRITICAL: Do NOT make submissive apologies for delays unless you actually delayed.'
                )

        prompt = f"""You are an AI sales agent. Your goal is to move this lead toward conversion.

LEAD CONTEXT:
- Company: {context['company_name']}
- Contact: {context['contact_person']}
- Current Stage: {context['stage_name']}
- Stage Description: {context['stage_description']}
- Days Since Last Contact: {context['days_since_last_contact']}
- Follow-up Attempt: {context['followup_attempt']} of {config.max_followup_attempts}
- Estimated Value: {context['estimated_value'] or 'Not specified'}
- Lead Source: {context['source'] or 'Not specified'}

{goals_context}

NOTES FROM SALES TEAM:
{chr(10).join(context['notes']) if context['notes'] else 'No notes recorded'}

RECENT ACTIVITY:
{chr(10).join([f"- {a['date']}: {a['type']} - {a['description']}" for a in context['recent_activities'][:5]]) if context['recent_activities'] else 'No recent activity'}

COMPANY PROFILE:
{config.company_profile}
{objection_context}
{goal_instruction}
{promise_context}
{scheduled_context}

INSTRUCTIONS:
1. Generate a short, personalized follow-up message (2-4 sentences max)
2. Reference previous conversations or notes naturally if relevant
3. Move the conversation forward - ask a question, propose next steps, or provide value
4. If there's an objection to address, handle it empathetically but persistently
5. Work toward the primary goal if specified
6. Be warm and professional, not pushy
7. If this is attempt {context['followup_attempt']}, be more direct about next steps
8. GREETING RULE (ПРАВИЛО ПРИВЕТСТВИЯ): Always use the time-neutral greeting "Доброго времени суток" (or no greeting if contextually appropriate). NEVER use time-specific greetings like "Добрый день", "Доброе утро", or "Добрый вечер".
Всегда используйте нейтральное по времени приветствие «Доброго времени суток» (или пишите без приветствия, если диалог продолжается естественно). Категорически ЗАПРЕЩЕНО использовать привязанные ко времени приветствия вроде «Добрый день», «Доброе утро», «Добрый вечер» или «Доброй ночи», поскольку автонапоминания отправляются в любое время суток (включая ночь).

Return ONLY the message text, nothing else."""

        # Try to assemble booking prompt to get rich system instructions and active card requirements
        try:
            from apps.leads.services.llm_client import build_activity_history
            activity_history = build_activity_history(lead)
        except Exception:
            activity_history = ""

        lead_data = {
            'contact_person': lead.contact_person,
            'phone': lead.phone,
            'email': lead.email,
            'check_in_date': str(lead.check_in_date) if lead.check_in_date else None,
            'check_out_date': str(lead.check_out_date) if lead.check_out_date else None,
            'guest_count': lead.guest_count,
            'room_type_preference': lead.room_type_preference,
            'meal_plan': lead.meal_plan,
            'source': lead.source,
            'company_name': getattr(lead, 'company_name', None) or lead.contact_person,
        }

        try:
            prompt_res = ai_service._assemble_booking_prompt(
                message="",
                lead_data=lead_data,
                conversation_history=context['conversation_history'],
                selected_media=None,
                is_pooled=False,
                activity_history=activity_history,
                lead=lead,
            )
            from apps.leads.services.prompt_assembly import consolidate_system_messages
            messages = consolidate_system_messages(prompt_res.messages)
            while messages and messages[-1].get('role') == 'user' and not messages[-1].get('content', '').strip():
                messages.pop()
        except Exception as e:
            logger.warning(f"Failed to assemble booking prompt for follow-up, falling back: {e}")
            messages = [{"role": "system", "content": config.system_prompt}]
            messages.extend(context['conversation_history'][-10:])
        messages.append({"role": "user", "content": prompt})


        try:
            response = ai_service.generate_response_with_messages(messages)
            if response:
                # Clean up the response
                response = response.strip()
                # Remove any quotes if the AI wrapped the message
                if response.startswith('"') and response.endswith('"'):
                    response = response[1:-1]
                return response
        except Exception as e:
            logger.error(f"Error generating follow-up message: {e}", exc_info=True)

        return None

    def _get_objection_rebuttal(self, objection_type: str) -> Optional[str]:
        """Get rebuttal content for an objection type."""
        return None

    def _claim_followup(self, lead: Lead, config: AIConfig, force: bool = False) -> tuple[Lead, str, str] | None:
        """
        Atomically claim a follow-up before generating text.

        This prevents duplicate sends when two agent-loop processes pick up the
        same due lead at the same time.
        """
        claim_id = str(uuid.uuid4())
        now = timezone.now()
        claim_ttl = timedelta(minutes=10)

        with transaction.atomic():
            locked = Lead.objects.select_for_update().get(id=lead.id)
            ctx = (locked.agent_context or {}).copy()
            existing_claim = ctx.get('followup_claim') or {}
            claimed_at_raw = existing_claim.get('claimed_at')
            if claimed_at_raw:
                try:
                    claimed_at = datetime.fromisoformat(claimed_at_raw)
                    if not claimed_at.tzinfo:
                        claimed_at = timezone.make_aware(claimed_at)
                    if now - claimed_at < claim_ttl:
                        return None
                except Exception:
                    pass

            should_follow_up, reason = self._should_follow_up(locked, config, force=force)
            if not should_follow_up:
                return None

            ctx['followup_claim'] = {
                'id': claim_id,
                'claimed_at': now.isoformat(),
                'reason': reason,
            }
            locked.agent_context = ctx
            locked.save(update_fields=['agent_context'])

        locked.refresh_from_db()
        return locked, claim_id, reason

    def _release_followup_claim(self, lead_id: int, claim_id: str) -> None:
        try:
            with transaction.atomic():
                lead = Lead.objects.select_for_update().get(id=lead_id)
                ctx = (lead.agent_context or {}).copy()
                claim = ctx.get('followup_claim') or {}
                if claim.get('id') == claim_id:
                    ctx.pop('followup_claim', None)
                    lead.agent_context = ctx
                    lead.save(update_fields=['agent_context'])
        except Exception as exc:
            logger.warning(f'Failed to release follow-up claim for lead {lead_id}: {exc}')

    def _send_followup(self, lead: Lead, config: AIConfig, force: bool = False) -> bool:
        """Generate and send a follow-up message to a lead."""
        claimed = self._claim_followup(lead, config, force=force)
        if not claimed:
            logger.info(f"Lead {lead.id}: follow-up skipped — already claimed or no longer due")
            return False

        lead, claim_id, claim_reason = claimed

        # Gather context
        context = self._gather_lead_context(lead)

        # Generate message
        message = self._generate_followup_message(lead, context, config)

        if not message:
            logger.warning(f"Failed to generate message for lead {lead.id}")
            self._release_followup_claim(lead.id, claim_id)
            return False

        # Re-fetch lead to catch ai_paused set mid-generation
        lead.refresh_from_db()
        if lead.ai_paused:
            logger.info(f"Lead {lead.id}: follow-up suppressed — ai_paused was set during generation")
            self._release_followup_claim(lead.id, claim_id)
            return False

        has_telegram = lead.telegram_chat_id and telegram_service.is_configured_sync() and not is_channel_ai_globally_paused('telegram', config=config, lead=lead)
        has_instagram = lead.instagram_user_id and instagram_service.is_configured() and not is_channel_ai_globally_paused('instagram', config=config, lead=lead)
        has_whatsapp = lead.whatsapp_phone and whatsapp_service.is_configured(org=lead.organization) and not is_channel_ai_globally_paused('whatsapp', config=config, lead=lead)

        if not has_telegram and not has_instagram and not has_whatsapp:
            logger.info(f"Lead {lead.id}: follow-up suppressed — no active AI channel available")
            self._release_followup_claim(lead.id, claim_id)
            return False

        # Send via appropriate channel
        success = False
        channel = None

        try:
            if has_telegram:
                clean_msg = message
                if 'AI sent ' in message and 'photo(s)' in message:
                    lines = message.split('\n')
                    clean_msg = '\n'.join(lines[1:]).strip()
                    from apps.leads.ai_service import ai_service
                    media_items = ai_service.select_media_items_for_response(
                        clean_msg,
                        context.get('conversation_history', ''),
                        organization=lead.organization
                    )
                    if media_items:
                        self._send_telegram_media_items(lead, media_items)
                success = self._send_telegram(lead, clean_msg)
                channel = 'telegram'
            elif has_instagram:
                success = self._send_instagram(lead, message)
                channel = 'instagram'
            elif has_whatsapp:
                success = self._send_whatsapp(lead, message)
                channel = 'whatsapp'
        except Exception:
            self._release_followup_claim(lead.id, claim_id)
            raise

        if success:
            # Update lead tracking
            lead.ai_followup_count += 1
            lead.last_ai_followup_at = timezone.now()
            lead.last_contacted = timezone.now().date()
            lead.save(update_fields=['ai_followup_count', 'last_ai_followup_at', 'last_contacted'])

            # Mark the pending promise as followed up so we don't send duplicates
            _pp = lead.agent_context.get('pending_promise', {})
            if _pp and not _pp.get('followup_sent'):
                _ctx = lead.agent_context.copy()
                _ctx['pending_promise']['followup_sent'] = True
                _ctx['pending_promise']['followup_sent_at'] = timezone.now().isoformat()
                claim = (_ctx.get('followup_claim') or {})
                if claim.get('id') == claim_id:
                    _ctx.pop('followup_claim', None)
                lead.agent_context = _ctx
                lead.save(update_fields=['agent_context'])
            else:
                _ctx = (lead.agent_context or {}).copy()
                claim = (_ctx.get('followup_claim') or {})
                if claim.get('id') == claim_id:
                    _ctx.pop('followup_claim', None)
                    lead.agent_context = _ctx
                    lead.save(update_fields=['agent_context'])

            # Clear the AI-scheduled follow-up time — will be rescheduled when lead replies
            if lead.next_follow_up_at:
                lead.next_follow_up_at = None
                lead.next_follow_up_hint = ''
                lead.save(update_fields=['next_follow_up_at', 'next_follow_up_hint'])

            logger.info(
                f"Sent AI follow-up to lead {lead.id} via {channel} "
                f"(attempt {lead.ai_followup_count}, claim_reason={claim_reason})"
            )

            # Initialize goals if enabled and lead doesn't have any
            if config.conversation_goals_enabled:
                if not lead.goals.filter(status=LeadGoal.STATUS_ACTIVE).exists():
                    goal_manager.create_initial_goals(lead)

            # Generate smart tasks (auto-executable if enabled)
            try:
                tasks = self._generate_tasks_for_lead(lead, context, config)
                if tasks:
                    logger.info(f"AI created {len(tasks)} task(s) for lead {lead.id}")
            except Exception as e:
                logger.error(f"Error generating tasks for lead {lead.id}: {e}", exc_info=True)

            # Execute pending auto-tasks if enabled
            if config.auto_execute_tasks:
                try:
                    exec_result = self.execute_pending_auto_tasks(lead)
                    if exec_result.get('executed', 0) > 0:
                        logger.info(f"Auto-executed {exec_result['executed']} task(s) for lead {lead.id}")
                except Exception as e:
                    logger.error(f"Error executing auto-tasks for lead {lead.id}: {e}", exc_info=True)

        if not success:
            self._release_followup_claim(lead.id, claim_id)

        return success

    def _generate_tasks_for_lead(self, lead: Lead, context: dict, config: AIConfig) -> list[Task]:
        """
        Generate relevant tasks for a lead based on conversation history and pipeline stage.

        Returns a list of created Task objects.
        """
        # Check if lead already has pending tasks to avoid duplicates
        pending_tasks_count = lead.tasks.filter(status=Task.STATUS_PENDING).count()
        if pending_tasks_count >= 3:
            logger.info(f"Lead {lead.id} already has {pending_tasks_count} pending tasks, skipping task generation")
            return []

        prompt = f"""You are an AI sales assistant. Analyze this lead's context and suggest 1-2 actionable tasks.

LEAD CONTEXT:
- Company: {context['company_name']}
- Contact: {context['contact_person']}
- Current Stage: {context['stage_name']}
- Stage Description: {context['stage_description']}
- Days Since Last Contact: {context['days_since_last_contact']}
- Follow-up Attempt: {context['followup_attempt']}
- Estimated Value: {context['estimated_value'] or 'Not specified'}

NOTES FROM SALES TEAM:
{chr(10).join(context['notes']) if context['notes'] else 'No notes recorded'}

RECENT CONVERSATION:
{chr(10).join([f"- {msg['role'].upper()}: {msg['content'][:200]}" for msg in context['conversation_history'][-5:]]) if context['conversation_history'] else 'No conversation yet'}

RECENT ACTIVITY:
{chr(10).join([f"- {a['date']}: {a['type']} - {a['description'][:100]}" for a in context['recent_activities'][:5]]) if context['recent_activities'] else 'No recent activity'}

TASK GUIDELINES BY STAGE:
- New Lead/Initial Contact: Schedule discovery call, Send product information
- Qualified/Demo: Prepare demo, Send case studies, Schedule technical discussion
- Proposal: Follow up on proposal, Address objections, Schedule contract review
- Negotiation: Finalize terms, Get stakeholder approval, Send final contract

Based on the conversation and stage, suggest 1-2 specific tasks. For each task provide:
1. A clear, actionable title (max 100 chars)
2. Task type: call, email, meeting, follow_up, or other
3. Days until due (1-14 based on urgency)
4. Brief description explaining why this task is important

Return your response in this exact JSON format:
[
  {{"title": "Task title here", "type": "call", "days_due": 3, "description": "Why this task matters"}}
]

Return ONLY the JSON array, no other text."""

        messages = [
            {"role": "system", "content": "You are a helpful sales assistant that suggests actionable tasks. Always respond with valid JSON only."},
            {"role": "user", "content": prompt}
        ]

        try:
            response = ai_service.generate_response_with_messages(messages)
            if not response:
                logger.warning(f"No response from AI for task generation for lead {lead.id}")
                return []

            # Parse the JSON response
            response = response.strip()
            # Handle markdown code blocks if present
            if response.startswith('```'):
                response = response.split('```')[1]
                if response.startswith('json'):
                    response = response[4:]
                response = response.strip()

            try:
                task_suggestions = json.loads(response)
            except json.JSONDecodeError as exc:
                logger.error(f"Failed to parse task suggestions JSON for lead {lead.id}: {exc} | Raw: {response}")
                LeadActivity.objects.create(
                    lead=lead,
                    organization=lead.organization,
                    activity_type='system_error',
                    description='AI returned invalid format while generating tasks.',
                    metadata={'raw_response': response, 'error': str(exc)},
                )
                return []

            if not isinstance(task_suggestions, list):
                logger.warning(f"Invalid task suggestions format for lead {lead.id}")
                return []

            created_tasks = []
            today = date.today()

            for suggestion in task_suggestions[:2]:  # Max 2 tasks
                if not isinstance(suggestion, dict) or 'title' not in suggestion:
                    continue

                # Calculate due date
                days_due = min(max(int(suggestion.get('days_due', 3)), 1), 14)
                due_date = today + timedelta(days=days_due)

                # Map task type
                task_type = suggestion.get('type', 'follow_up')
                valid_types = ['call', 'email', 'meeting', 'follow_up', 'other']
                if task_type not in valid_types:
                    task_type = 'follow_up'

                # Determine if task should be auto-executable
                is_auto = config.auto_execute_tasks
                exec_type = 'none'
                if is_auto:
                    # Map task types to execution types
                    exec_type_mapping = {
                        'follow_up': 'send_message',
                        'email': 'send_message',
                        'call': 'none',  # Calls require manual action
                        'meeting': 'none',  # Meetings require manual action
                        'other': 'send_document',
                    }
                    exec_type = exec_type_mapping.get(task_type, 'send_message')

                # Create the task
                task = Task.objects.create(
                    lead=lead,
                    title=suggestion['title'][:255],
                    description=suggestion.get('description', '')[:500],
                    task_type=task_type,
                    due_date=due_date,
                    status=Task.STATUS_PENDING,
                    is_auto_executable=is_auto and exec_type != 'none',
                    execution_type=exec_type,
                    is_ai_generated=True,
                )
                created_tasks.append(task)

                # Log task creation activity
                LeadActivity.objects.create(
                    lead=lead,
                    organization=lead.organization,
                    activity_type=LeadActivity.TYPE_TASK_CREATED,
                    description=f"AI Agent created task: {task.title}",
                    metadata={
                        'task_id': task.id,
                        'task_title': task.title,
                        'task_type': task_type,
                        'due_date': str(due_date),
                        'is_ai_generated': True,
                    }
                )

                logger.info(f"AI created task for lead {lead.id}: {task.title} (due: {due_date})")

            return created_tasks

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI task suggestions for lead {lead.id}: {e}")
            return []
        except Exception as e:
            logger.error(f"Error generating tasks for lead {lead.id}: {e}", exc_info=True)
            return []

    def _send_telegram_media_items(self, lead: Lead, media_items: list) -> int:
        """Send media items to the lead via Telegram."""
        if not lead.telegram_chat_id or not media_items:
            return 0
        file_sources = []
        for item in media_items:
            source = None
            if hasattr(item, 'file') and item.file:
                try:
                    source = item.file.path
                except NotImplementedError:
                    source = item.file.url
                except Exception:
                    source = getattr(item, 'file', None)
            else:
                source = getattr(item, 'url', None) or getattr(item, 'file_url', None)
            if source:
                file_sources.append(source)
        if not file_sources:
            return 0
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            if len(file_sources) == 1:
                result = loop.run_until_complete(
                    telegram_service.send_photo(lead.telegram_chat_id, file_sources[0])
                )
                sent_count = 1 if result else 0
            else:
                result = loop.run_until_complete(
                    telegram_service.send_media_group(lead.telegram_chat_id, file_sources)
                )
                sent_count = len(result) if result else 0
            loop.close()
            return sent_count
        except Exception as e:
            logger.error(f"Error sending Telegram media items to lead {lead.id}: {e}", exc_info=True)
            return 0

    def _send_telegram(self, lead: Lead, message: str) -> bool:
        """Send a message via Telegram."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(
                telegram_service.send_message(lead.telegram_chat_id, message)
            )
            loop.close()

            if result:
                LeadActivity.objects.create(
                    lead=lead,
                    organization=lead.organization,
                    activity_type=LeadActivity.TYPE_TELEGRAM_SENT,
                    description=f"AI Agent follow-up: {message[:100]}{'...' if len(message) > 100 else ''}",
                    metadata={
                        'message_id': result.get('message_id'),
                        'text': message,
                        'is_ai_agent': True,
                        'followup_attempt': lead.ai_followup_count + 1,
                    }
                )
                return True
            return False
        except Exception as e:
            logger.error(f"Error sending Telegram message to lead {lead.id}: {e}", exc_info=True)
            return False

    def _send_instagram(self, lead: Lead, message: str) -> bool:
        """Send a message via Instagram."""
        try:
            result = instagram_service.send_message(lead.instagram_user_id, message)

            if result:
                LeadActivity.objects.create(
                    lead=lead,
                    organization=lead.organization,
                    activity_type=LeadActivity.TYPE_INSTAGRAM_SENT,
                    description=f"AI Agent follow-up: {message[:100]}{'...' if len(message) > 100 else ''}",
                    echo_origin=LeadActivity.ECHO_ORIGIN_CRM,
                    metadata={
                        'message_id': result.get('message_id'),
                        'text': message,
                        'is_ai_agent': True,
                        'followup_attempt': lead.ai_followup_count + 1,
                        'echo_origin': LeadActivity.ECHO_ORIGIN_CRM,
                    }
                )
                return True
            return False
        except Exception as e:
            logger.error(f"Error sending Instagram message to lead {lead.id}: {e}", exc_info=True)
            return False

    def _send_whatsapp(self, lead: Lead, message: str) -> bool:
        """Send a message via WhatsApp."""
        try:
            result = whatsapp_service.send_message(lead.whatsapp_phone, message, org=lead.organization)

            if result:
                LeadActivity.objects.create(
                    lead=lead,
                    organization=lead.organization,
                    activity_type=LeadActivity.TYPE_WHATSAPP_SENT,
                    description=f"AI Agent follow-up: {message[:100]}{'...' if len(message) > 100 else ''}",
                    metadata={
                        'message_id': result.get('message_id'),
                        'text': message,
                        'is_ai_agent': True,
                        'followup_attempt': lead.ai_followup_count + 1,
                    }
                )
                return True
            return False
        except Exception as e:
            logger.error(f"Error sending WhatsApp message to lead {lead.id}: {e}", exc_info=True)
            return False


# Singleton instance
agent_service = AgentService()
