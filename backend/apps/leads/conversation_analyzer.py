"""
Conversation Analyzer Service for AI Agent.

Analyzes incoming messages to detect:
- Stage progression signals
- Objections
- Goal completions
- Buying signals
"""
import json
import logging
from typing import Optional
from django.utils import timezone
from .models import Lead, LeadActivity, LeadGoal, PipelineStage
from .ai_service import ai_service

logger = logging.getLogger(__name__)


class ConversationAnalyzer:
    """Analyzes conversations to extract insights for the AI agent."""

    # Booking confirmation signals — trigger progression to the first is_final=True stage
    BOOKING_CONFIRMATION_SIGNALS = [
        # English
        'confirmed', 'i confirm', 'i will come', "i'll come", "we'll come",
        'we will come', 'booking confirmed', 'book it', 'we are coming',
        'i am coming', 'count us in', 'we are in', "let's book", 'reserved',
        'deal', 'agreed', 'see you then', 'see you soon',
        # Russian
        'подтверждаю', 'приеду', 'придём', 'придем', 'приедем', 'приезжаем',
        'забронировали', 'бронирую', 'записываемся', 'договорились',
        'ждите нас', 'будем', 'да приедем', 'подтверждено', 'берём', 'берем',
        'записали', 'заедем',
        # Kyrgyz
        'келебиз', 'келем', 'броньдойбуз', 'ырасталды',
        'жакшы келебиз', 'күтө тур', 'резервдейбиз',
    ]

    # Engagement signals that indicate a lead is responding (for early-stage progression)
    EARLY_ENGAGEMENT_SIGNALS = [
        'responded', 'replied', 'hello', 'hi', 'привет', 'здравствуйте', 'салам',
    ]

    # Interest signals for mid-stage progression
    INTEREST_SIGNALS = [
        'interested', 'tell me more', 'how much', 'pricing', 'cost', 'sounds good',
        'интересует', 'расскажите', 'сколько стоит', 'цена', 'хочу узнать',
        'кызыктырат', 'канча турат',
    ]

    def _get_stages(self):
        """Fetch all pipeline stages from DB ordered by order field."""
        return list(PipelineStage.objects.all().order_by('order'))

    def _get_final_stage_key(self, stages):
        """Return the key of the first stage with is_final=True, or None."""
        for stage in stages:
            if stage.is_final:
                return stage.key
        return None

    def _get_next_stage_key(self, current_key, stages):
        """Return the next stage key in order after current_key, or None."""
        current_order = None
        for stage in stages:
            if stage.key == current_key:
                current_order = stage.order
                break
        if current_order is None:
            return None
        for stage in stages:
            if stage.order > current_order and not stage.is_final:
                return stage.key
        return None

    def _is_final_stage(self, stage_key, stages):
        """Return True if the given stage key is a final stage."""
        for stage in stages:
            if stage.key == stage_key:
                return stage.is_final
        return False

    def _has_final_booking_data(self, lead: Lead) -> bool:
        """AI may mark final only after concrete booking and contact data exists."""
        return bool(
            (lead.phone or lead.whatsapp_phone or lead.mobile_phone)
            and lead.check_in_date
            and lead.check_out_date
            and lead.guest_count
            and lead.room_type_preference
        )

    # Objection patterns
    OBJECTION_PATTERNS = {
        'price': [
            'too expensive', 'too costly', 'budget', 'cant afford', "can't afford",
            'cheaper', 'lower price', 'discount', 'too much', 'price is high',
        ],
        'timing': [
            'not now', 'later', 'not ready', 'busy', 'bad time', 'next month',
            'next year', 'not the right time', 'maybe later', 'in the future',
        ],
        'competitor': [
            'already using', 'have a provider', 'working with', 'competitor',
            'another vendor', 'current solution', 'happy with',
        ],
        'authority': [
            'need to check', 'ask my', 'talk to', 'boss', 'manager', 'team',
            'not my decision', 'decision maker', 'approval', 'stakeholder',
        ],
        'need': [
            "don't need", 'not interested', 'not looking', "we're fine",
            'no need', 'not for us', 'not relevant', 'pass',
        ],
    }

    # Goal completion indicators
    GOAL_INDICATORS = {
        'collect_email': ['@', 'email is', 'my email', 'email:', 'send to'],
        'collect_phone': ['my number', 'call me at', 'phone is', 'reach me at'],
        'schedule_call': ['call me', 'schedule a call', 'lets talk', 'available at', 'free at'],
        'schedule_meeting': ['meet', 'meeting', 'visit', 'come by', 'appointment'],
        'qualify_lead': ['interested', 'need', 'looking for', 'budget is', 'timeline'],
    }

    def analyze_message(self, lead: Lead, message: str, is_incoming: bool = True) -> dict:
        """
        Analyze a message and return insights.

        Returns:
            dict: {
                'stage_signal': str or None,  # Suggested next stage
                'objection_detected': str or None,  # Objection type
                'goals_achieved': list,  # List of achieved goal types
                'buying_signals': list,  # Detected buying signals
                'extracted_data': dict,  # Any extracted contact info
            }
        """
        message_lower = message.lower()
        result = {
            'stage_signal': None,
            'objection_detected': None,
            'goals_achieved': [],
            'buying_signals': [],
            'extracted_data': {},
        }

        # Only analyze incoming messages for signals
        if not is_incoming:
            return result

        # Fetch stages from DB once
        stages = self._get_stages()
        final_stage_key = self._get_final_stage_key(stages)
        current_stage_key = lead.status

        # Check if current stage is already final — no progression needed
        if self._is_final_stage(current_stage_key, stages):
            # Still detect objections/goals below, just no stage signals
            pass
        else:
            # Check for booking confirmation signals first — jump to first final stage
            if final_stage_key and self._has_final_booking_data(lead):
                for signal in self.BOOKING_CONFIRMATION_SIGNALS:
                    if signal in message_lower:
                        result['stage_signal'] = final_stage_key
                        result['buying_signals'].append(signal)
                        break

            # If no direct conversion signal, check normal stage progression
            if not result['stage_signal']:
                next_stage_key = self._get_next_stage_key(current_stage_key, stages)

                # Determine if this is an early-stage lead (first 2 stages by order)
                current_order = None
                first_order = stages[0].order if stages else None
                second_order = stages[1].order if len(stages) > 1 else None
                for stage in stages:
                    if stage.key == current_stage_key:
                        current_order = stage.order
                        break

                is_early_stage = (
                    current_order is not None and first_order is not None
                    and (current_order == first_order or current_order == second_order)
                )

                if next_stage_key:
                    if is_early_stage:
                        # Early stages: any inbound message means they responded → progress
                        result['stage_signal'] = next_stage_key
                        result['buying_signals'].append('inbound_message_received')
                    else:
                        # Later stages: require interest or booking signals
                        for signal in self.INTEREST_SIGNALS:
                            if signal in message_lower:
                                result['stage_signal'] = next_stage_key
                                result['buying_signals'].append(signal)
                                break

        # Check for objections
        for objection_type, patterns in self.OBJECTION_PATTERNS.items():
            for pattern in patterns:
                if pattern in message_lower:
                    result['objection_detected'] = objection_type
                    break
            if result['objection_detected']:
                break

        # Check for goal completions
        for goal_type, indicators in self.GOAL_INDICATORS.items():
            for indicator in indicators:
                if indicator in message_lower:
                    result['goals_achieved'].append(goal_type)
                    break

        # Extract email if present
        import re
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        emails = re.findall(email_pattern, message)
        if emails:
            result['extracted_data']['email'] = emails[0]
            if 'collect_email' not in result['goals_achieved']:
                result['goals_achieved'].append('collect_email')

        # Extract phone if present
        phone_pattern = r'[\+]?[(]?[0-9]{1,3}[)]?[-\s\.]?[(]?[0-9]{1,4}[)]?[-\s\.]?[0-9]{1,4}[-\s\.]?[0-9]{1,9}'
        phones = re.findall(phone_pattern, message)
        if phones:
            # Filter out short numbers
            valid_phones = [p for p in phones if len(re.sub(r'\D', '', p)) >= 7]
            if valid_phones:
                result['extracted_data']['phone'] = valid_phones[0]
                if 'collect_phone' not in result['goals_achieved']:
                    result['goals_achieved'].append('collect_phone')

        return result

    def analyze_with_ai(self, lead: Lead, message: str, conversation_history: list) -> dict:
        """
        Use AI to perform deep analysis of the conversation.

        Returns structured analysis including stage recommendation,
        objection type, and goal progress.
        """
        # Get current stage info
        current_stage = lead.status
        stages = list(PipelineStage.objects.all().order_by('order'))
        stage_list_desc = '\n'.join(
            f"  - {s.key} ({s.name}){' [FINAL/CONVERTED]' if s.is_final else ''}"
            for s in stages
        )
        final_stages = [s.key for s in stages if s.is_final]
        final_stage_note = (
            f"Final/converted stage(s): {', '.join(final_stages)}"
            if final_stages else "No final stages defined"
        )

        # Get active goals
        active_goals = list(lead.goals.filter(status=LeadGoal.STATUS_ACTIVE).values_list('goal_type', flat=True))

        prompt = f"""Analyze this lead conversation and provide structured insights.

LEAD INFO:
- Contact: {lead.contact_person or 'Unknown'}
- Current Stage: {current_stage}
- Active Goals: {', '.join(active_goals) if active_goals else 'None'}
- Has Email: {'Yes' if lead.email else 'No'}
- Has Phone: {'Yes' if lead.phone else 'No'}

PIPELINE STAGES (in order):
{stage_list_desc}
{final_stage_note}

RECENT CONVERSATION:
{chr(10).join([f"{'LEAD' if msg.get('role') == 'user' else 'AGENT'}: {msg.get('content', '')[:200]}" for msg in conversation_history[-5:]])}

LATEST MESSAGE FROM LEAD:
{message}

Analyze and respond in this exact JSON format:
{{
    "should_progress_stage": true/false,
    "recommended_stage": "stage_key or null",
    "stage_reason": "why to progress or not",
    "objection_detected": "price/timing/competitor/authority/need/null",
    "objection_details": "specific objection if any",
    "goals_achieved": ["goal_type1", "goal_type2"],
    "new_goals_suggested": ["goal_type1"],
    "buying_signals": ["signal1", "signal2"],
    "sentiment": "positive/neutral/negative",
    "urgency_level": "high/medium/low",
    "extracted_email": "email or null",
    "extracted_phone": "phone or null"
}}

BOOKING CONFIRMATION RULE (highest priority): recommend a final/converted stage ONLY after the lead has concrete booking details and contact data saved: phone, check-in date, check-out date, guest count, and chosen room. A phrase like "хочу забронировать", "забронируйте", "book it", or "келебиз" WITHOUT those details is only booking intent, not a final conversion. In that case, keep should_progress_stage false or suggest a non-final next stage.

Only use stage keys from the PIPELINE STAGES list above. Never invent stage keys.
For all other cases, only suggest stage progression if there's clear evidence."""

        try:
            response = ai_service.generate_response_with_messages([
                {"role": "system", "content": "You are a sales conversation analyst. Respond with valid JSON only."},
                {"role": "user", "content": prompt}
            ])

            if not response:
                return {}

            # Parse JSON response
            response = response.strip()
            if response.startswith('```'):
                response = response.split('```')[1]
                if response.startswith('json'):
                    response = response[4:]
                response = response.strip()

            return json.loads(response)

        except Exception as e:
            logger.error(f"Error in AI conversation analysis: {e}")
            return {}

    def should_progress_status(self, lead: Lead, analysis: dict) -> Optional[str]:
        """
        Determine if lead should be moved to a new status.

        Returns the new status key if progression should happen, None otherwise.
        """
        if not analysis.get('should_progress_stage'):
            return None

        recommended = analysis.get('recommended_stage')
        if not recommended:
            return None

        # Verify the stage exists
        stage = PipelineStage.objects.filter(
            key=recommended
        ).first()

        if not stage:
            return None

        if stage.is_final and not self._has_final_booking_data(lead):
            logger.info(
                f"Blocked final-stage progression for lead {lead.id}: "
                "booking/contact data is incomplete"
            )
            return None

        # Don't go backwards
        current_order = PipelineStage.objects.filter(
            key=lead.status
        ).values_list('order', flat=True).first()

        new_order = PipelineStage.objects.filter(
            key=recommended
        ).values_list('order', flat=True).first()

        if current_order is not None and new_order is not None:
            if new_order <= current_order:
                return None

        return recommended

    def process_objection(self, lead: Lead, objection_type: str, details: str = '') -> None:
        """
        Record an objection detection on a lead.
        """
        lead.current_objection = objection_type
        lead.last_objection_at = timezone.now()
        lead.objection_count += 1
        lead.save(update_fields=['current_objection', 'last_objection_at', 'objection_count'])

        # Log activity
        LeadActivity.objects.create(
            lead=lead,
            activity_type=LeadActivity.TYPE_OBJECTION_DETECTED,
            description=f"Objection detected: {objection_type}",
            metadata={
                'objection_type': objection_type,
                'details': details,
                'total_objections': lead.objection_count,
            }
        )

        logger.info(f"Objection detected for lead {lead.id}: {objection_type}")

    def progress_lead_status(self, lead: Lead, new_status: str, reason: str = '') -> bool:
        """
        Progress a lead to a new status (AI-initiated).
        """
        old_status = lead.status
        lead.status = new_status
        lead.save(update_fields=['status'])

        # Log activity
        LeadActivity.objects.create(
            lead=lead,
            activity_type=LeadActivity.TYPE_AI_STATUS_CHANGE,
            description=f"AI moved lead from {old_status} to {new_status}",
            metadata={
                'old_status': old_status,
                'new_status': new_status,
                'reason': reason,
                'is_ai_action': True,
            }
        )

        logger.info(f"AI progressed lead {lead.id} from {old_status} to {new_status}: {reason}")
        return True


# Singleton instance
conversation_analyzer = ConversationAnalyzer()
