import io
import logging
import threading
import tempfile
import os
from django.db import models as db_models
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from .models import Lead, LeadActivity, LeadNote
from .ringcentral_service import ringcentral_service

logger = logging.getLogger(__name__)


def _find_lead_by_phone(phone: str) -> 'Lead | None':
    """
    Look up a lead by phone number across all phone fields.
    Normalizes by stripping non-digit characters for comparison.
    """
    if not phone:
        return None

    digits = ''.join(c for c in phone if c.isdigit())
    # Try exact match first, then suffix match (last 10 digits)
    for field in ('phone', 'mobile_phone', 'office_phone'):
        lead = Lead.objects.filter(**{field: phone}).first()
        if lead:
            return lead

    # Fallback: match on last 10 digits
    if len(digits) >= 10:
        suffix = digits[-10:]
        for field in ('phone', 'mobile_phone', 'office_phone'):
            for lead in Lead.objects.exclude(**{field: ''}):
                lead_digits = ''.join(c for c in getattr(lead, field) if c.isdigit())
                if lead_digits.endswith(suffix):
                    return lead
    return None


def _analyze_call_recording(lead_id: int, activity_id: int, recording_id: str):
    """
    Background task: download recording, transcribe via Whisper,
    analyze with GPT, then update the lead and create activity.
    """
    import django
    django.setup()  # Ensure Django is set up in background thread

    try:
        from openai import OpenAI
        from .models import Lead, LeadActivity, LeadNote
        import os

        api_key = os.environ.get('CAYU_OPENAI_API_KEY') or os.environ.get('OPENAI_API_KEY')
        if not api_key:
            logger.warning('OpenAI API key not available for call analysis')
            return

        client = OpenAI(api_key=api_key)

        # 1. Download recording
        audio_content = ringcentral_service.get_recording_content(recording_id)
        if not audio_content:
            logger.error(f'Could not download recording {recording_id}')
            return

        logger.info(f'Downloaded recording {recording_id} ({len(audio_content)} bytes)')

        # 2. Transcribe via Whisper
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
            tmp.write(audio_content)
            tmp_path = tmp.name

        try:
            with open(tmp_path, 'rb') as audio_file:
                transcript_response = client.audio.transcriptions.create(
                    model='whisper-1',
                    file=audio_file,
                    response_format='text',
                )
            transcript = str(transcript_response)
            logger.info(f'Transcribed recording {recording_id}: {len(transcript)} chars')
        finally:
            os.unlink(tmp_path)

        if not transcript.strip():
            logger.warning(f'Empty transcript for recording {recording_id}')
            return

        # 3. AI analysis
        lead = Lead.objects.filter(id=lead_id).first()
        if not lead:
            return

        lead_context = f"Lead: {lead.contact_person or 'Unknown'}"

        analysis_prompt = f"""Analyze this phone call transcript and provide:
1. A brief summary (2-3 sentences) of what was discussed
2. Key action items or next steps mentioned
3. Any lead information provided: tax years, problem/need, preferred call time, phone number, email
4. Overall sentiment: positive / neutral / negative

LANGUAGE NOTE: The transcript may be in Russian, Kyrgyz, English, or a mix of these. Extract information regardless of the language used. Return extracted field values in the exact language used in the transcript.

{lead_context}

Transcript:
{transcript[:4000]}

Respond as JSON with keys: summary, action_items (list), extracted_data (dict with keys: problem_description, preferred_contact_time, phone, email - only include if mentioned), sentiment"""

        from apps.leads.ai_service import ai_service as _ai_service
        analysis_client = _ai_service.client if _ai_service.is_configured() else client
        analysis_model = _ai_service._model if _ai_service.is_configured() else 'gpt-4o-mini'
        analysis_response = analysis_client.chat.completions.create(
            model=analysis_model,
            messages=[{'role': 'user', 'content': analysis_prompt}],
            response_format={'type': 'json_object'},
            temperature=0.3,
            max_tokens=800,
        )

        import json
        analysis = json.loads(analysis_response.choices[0].message.content)
        logger.info(f'AI analysis complete for recording {recording_id}')

        # 4. Save transcript as LeadNote
        note_content = f"📞 Call Transcript\n\n{transcript}"
        LeadNote.objects.create(lead=lead, content=note_content)

        # 5. Save analysis as LeadActivity
        summary = analysis.get('summary', '')
        action_items = analysis.get('action_items', [])
        sentiment = analysis.get('sentiment', '')
        description = f"AI Call Analysis: {summary}"
        if action_items:
            description += f"\n\nAction items:\n" + '\n'.join(f'• {item}' for item in action_items)

        LeadActivity.objects.create(
            lead=lead,
            activity_type=LeadActivity.TYPE_RINGCENTRAL_CALL_ANALYZED,
            description=description,
            metadata={
                'recording_id': recording_id,
                'transcript': transcript,
                'summary': summary,
                'action_items': action_items,
                'sentiment': sentiment,
                'extracted_data': analysis.get('extracted_data', {}),
            }
        )

        # 6. Auto-update lead fields if new data found
        extracted = analysis.get('extracted_data', {})
        updated_fields = []
        placeholder_values = {
            'not mentioned', 'not specified', 'not provided', 'not available',
            'n/a', 'na', 'none', 'null', 'unknown', '-', '—', '',
            'не указано', 'не указан', 'не указана', 'не указаны',
            'нет', 'нету', 'отсутствует', 'пусто',
            'белгисиз', 'жок', 'айтылган жок', 'берилген жок', 'маалымат жок',
        }

        def should_update(value):
            return value and str(value).strip().lower() not in placeholder_values

        if should_update(extracted.get('problem_description')) and not lead.problem_description:
            lead.problem_description = extracted['problem_description']
            updated_fields.append('problem_description')
        if should_update(extracted.get('preferred_contact_time')) and not lead.preferred_contact_time:
            lead.preferred_contact_time = extracted['preferred_contact_time']
            updated_fields.append('preferred_contact_time')
        if should_update(extracted.get('phone')) and not lead.phone:
            lead.phone = extracted['phone']
            updated_fields.append('phone')
        if should_update(extracted.get('email')) and not lead.email:
            lead.email = extracted['email']
            updated_fields.append('email')

        if updated_fields:
            lead.save()
            logger.info(f'Auto-updated lead {lead_id} fields from call: {updated_fields}')

        # 7. Update the call_ended activity with recording info
        activity = LeadActivity.objects.filter(id=activity_id).first()
        if activity and activity.metadata:
            meta = activity.metadata.copy()
            meta['recording_id'] = recording_id
            meta['has_analysis'] = True
            activity.metadata = meta
            activity.save(update_fields=['metadata'])

    except Exception as e:
        logger.error(f'Error analyzing call recording {recording_id}: {e}', exc_info=True)


@api_view(['POST'])
@permission_classes([AllowAny])
def ringcentral_webhook(request):
    """
    Webhook endpoint for RingCentral events (SMS and call recording).

    RingCentral first sends a validation request with Validation-Token header.
    After that, events come as POST with JSON body.
    """
    # --- Webhook validation handshake ---
    validation_token = request.headers.get('Validation-Token')
    if validation_token:
        return Response(
            {},
            status=200,
            headers={'Validation-Token': validation_token},
        )

    try:
        data = request.data
        event = data.get('event', '')
        body = data.get('body', {})

        # --- Inbound SMS ---
        if 'message-store/instant' in event or (
            body.get('type') == 'SMS' and body.get('direction') == 'Inbound'
        ):
            _handle_inbound_sms(body)

        # --- Call session / recording events ---
        elif 'telephony/sessions' in event:
            _handle_call_session(body)

        return Response({'ok': True})

    except Exception as e:
        logger.error(f'Error processing RingCentral webhook: {e}', exc_info=True)
        return Response({'ok': True})


def _handle_inbound_sms(body: dict):
    """Process an inbound SMS message event."""
    try:
        from_number = body.get('from', {}).get('phoneNumber', '')
        text = body.get('subject', '') or body.get('text', '')
        message_id = str(body.get('id', ''))

        if not from_number or not text:
            return

        lead = _find_lead_by_phone(from_number)
        if not lead:
            logger.info(f'RingCentral inbound SMS from unknown number {from_number} — no matching lead')
            return

        LeadActivity.objects.create(
            lead=lead,
            activity_type=LeadActivity.TYPE_RINGCENTRAL_SMS_RECEIVED,
            description=f'Received SMS: {text[:100]}{"..." if len(text) > 100 else ""}',
            metadata={
                'text': text,
                'from': from_number,
                'message_id': message_id,
            }
        )
        logger.info(f'Logged inbound RingCentral SMS for lead {lead.id}')

    except Exception as e:
        logger.error(f'Error handling inbound SMS: {e}', exc_info=True)


def _handle_call_session(body: dict):
    """Process a telephony session event (call started/ended/recording ready)."""
    try:
        session_id = body.get('sessionId', '') or body.get('telephonySessionId', '')
        parties = body.get('parties', [])
        recordings = body.get('recordings', [])

        # Determine call direction and remote party number
        remote_phone = None
        direction = None
        duration = None
        status = None

        for party in parties:
            party_status = party.get('status', {})
            current_status = party_status.get('code', '')
            party_direction = party.get('direction', '')

            if party_direction == 'Inbound':
                direction = 'inbound'
                remote_phone = party.get('from', {}).get('phoneNumber')
            elif party_direction == 'Outbound':
                direction = 'outbound'
                remote_phone = party.get('to', {}).get('phoneNumber')

            status = current_status
            duration = party.get('duration')

        if not remote_phone:
            return

        lead = _find_lead_by_phone(remote_phone)
        if not lead:
            logger.info(f'RingCentral call event for unknown number {remote_phone}')
            return

        # Determine event type based on status
        if status in ('Setup', 'Proceeding', 'Answered'):
            # Call started
            existing = LeadActivity.objects.filter(
                lead=lead,
                activity_type=LeadActivity.TYPE_RINGCENTRAL_CALL_STARTED,
                metadata__session_id=session_id,
            ).exists()
            if not existing:
                LeadActivity.objects.create(
                    lead=lead,
                    activity_type=LeadActivity.TYPE_RINGCENTRAL_CALL_STARTED,
                    description=f'Phone call {direction}: {remote_phone}',
                    metadata={
                        'session_id': session_id,
                        'direction': direction,
                        'remote_phone': remote_phone,
                        'status': status,
                    }
                )
                logger.info(f'Logged call started for lead {lead.id}')

        elif status in ('Disconnected', 'Gone'):
            # Call ended
            activity = LeadActivity.objects.create(
                lead=lead,
                activity_type=LeadActivity.TYPE_RINGCENTRAL_CALL_ENDED,
                description=f'Phone call ended ({direction}, {duration or 0}s)',
                metadata={
                    'session_id': session_id,
                    'direction': direction,
                    'remote_phone': remote_phone,
                    'duration': duration,
                    'has_recording': bool(recordings),
                }
            )
            logger.info(f'Logged call ended for lead {lead.id}')

            # Trigger AI analysis if there's a recording
            for rec in recordings:
                recording_id = rec.get('id')
                if recording_id:
                    logger.info(f'Spawning AI analysis for recording {recording_id}')
                    t = threading.Thread(
                        target=_analyze_call_recording,
                        args=(lead.id, activity.id, recording_id),
                        daemon=True,
                    )
                    t.start()

    except Exception as e:
        logger.error(f'Error handling call session event: {e}', exc_info=True)
