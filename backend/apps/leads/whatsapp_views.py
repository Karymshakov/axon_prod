import re
import logging
import time
import threading
from datetime import date
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status as http_status
from .models import Lead, LeadActivity, AIConfig, WhatsAppConfig
from .ai_diagnostics import (
    OUTCOME_DELAYED,
    OUTCOME_FAILED,
    OUTCOME_SKIPPED,
    add_diagnostic_step,
    evaluate_auto_reply_eligibility,
    finalize_diagnostics,
    generate_with_blank_retry,
    initialize_inbound_diagnostics,
)
from .ai_service import ai_service
from .ai_memory import filter_activities_since_last_ai_reset
from .whatsapp_service import whatsapp_service
from .agent_service import agent_service
from .agent_dispatcher import agent_dispatcher
from .channel_ai_control import get_channel_ai_status_label, is_channel_ai_globally_paused
from .media_utils import (
    MEDIA_PLACEHOLDERS,
    activity_text_for_ai,
    extension_from_filename,
    incoming_media_path,
    is_media_only_activity_metadata,
    media_metadata as build_media_metadata,
)
from .services.media_context import build_unresolved_media_summary, resolve_activity_media_context

logger = logging.getLogger(__name__)


_FAKE_EMAIL_DOMAINS = {
    'example.com', 'example.org', 'example.net', 'example.io',
    'test.com', 'test.org', 'test.net',
    'placeholder.com', 'email.com', 'domain.com', 'yourdomain.com',
}

_FAKE_EMAIL_LOCALS = {
    'john.doe', 'jane.doe', 'firstname.lastname', 'test',
    'user', 'name', 'email', 'sample', 'demo',
}


def _is_fake_email(email: str) -> bool:
    """Return True if email looks like a placeholder/fake address that should not be saved."""
    if not email or '@' not in email:
        return False
    local, _, domain = email.rpartition('@')
    if domain.lower() in _FAKE_EMAIL_DOMAINS:
        return True
    if local.lower() in _FAKE_EMAIL_LOCALS:
        return True
    return False


def _is_our_company(name: str, company_profile: str) -> bool:
    """Return True if name appears to be our own company (strips markdown before comparing)."""
    if not name or not company_profile:
        return False
    plain = re.sub(r'[*_`#>]', '', company_profile).lower()
    return name.lower().strip() in plain


def _split_into_messages(text: str) -> list:
    """
    Split a multi-paragraph AI response into individual chat messages by double newlines.
    This preserves newlines and formatting (lists, bullets) inside each paragraph.
    """
    if not text:
        return []
    parts = re.split(r'\n{2,}', text)
    return [p.strip() for p in parts if p.strip()]


def _delayed_whatsapp_ai_response(lead_id: int, activity_id: int, sender_phone: str, message_id: str, text: str) -> None:
    """
    Background thread: pool window sleep, then generate and send an AI response.

    Runs after the webhook has already returned 200 to Meta so that Meta delivers
    subsequent messages immediately (instead of waiting for the long-running request
    to finish).  This is what makes last-message-wins pooling work: all concurrent
    messages sleep simultaneously, and only the winner (latest activity) calls the AI.
    """
    from django.db import close_old_connections
    close_old_connections()

    try:
        lead = Lead.objects.get(id=lead_id)
        org = lead.organization
        config = AIConfig.get_config(org)
        current_activity = LeadActivity.objects.get(id=activity_id)

        if not is_channel_ai_globally_paused('whatsapp', config=config, lead=lead):
            agent_service.process_incoming_message(lead, text, channel='whatsapp')

        add_diagnostic_step(
            activity_id,
            'ai_status_checked',
            'AI status re-checked before processing',
            detail=get_channel_ai_status_label('whatsapp', config=config, lead=lead) if not lead.ai_paused else 'Paused for this lead',
            status='success' if not lead.ai_paused and not is_channel_ai_globally_paused('whatsapp', config=config, lead=lead) else 'warning',
        )
        eligible, eligibility_reason = evaluate_auto_reply_eligibility(
            lead,
            channel='whatsapp',
            config=config,
            ai_ready=ai_service.is_configured(),
            channel_ready=whatsapp_service.is_configured(org),
            destination=sender_phone,
            allow_final_stage=True,
        )
        add_diagnostic_step(
            activity_id,
            'eligibility_checked',
            'Auto-reply check re-run',
            detail=eligibility_reason,
            status='success' if eligible else 'warning',
        )
        if not eligible:
            finalize_diagnostics(
                activity_id,
                result=OUTCOME_SKIPPED,
                summary=f'Skipped — {eligibility_reason}',
                status='warning',
            )
            return

        try:
            whatsapp_service.mark_as_read(message_id, org=org)
        except Exception:
            pass

        if config.response_delay > 0:
            add_diagnostic_step(
                activity_id,
                'batching_delay',
                'Batching rule delay',
                detail=f'Waiting {config.response_delay} seconds for follow-up messages before replying',
                status='info',
            )
            remaining = config.response_delay
            while remaining > 0:
                time.sleep(min(4, remaining))
                remaining -= 4

        latest_received = LeadActivity.objects.filter(
            lead=lead,
            activity_type=LeadActivity.TYPE_WHATSAPP_RECEIVED,
        ).order_by('-created_at').first()
        if latest_received and latest_received.id != current_activity.id:
            logger.info(
                f"Lead {lead.id}: skipping response, newer WhatsApp message "
                f"#{latest_received.id} will respond to the batch"
            )
            add_diagnostic_step(
                activity_id,
                'batched_into_newer_message',
                'Batching rule grouped this message into a newer one',
                detail='A newer inbound message arrived during the wait window, so that newer message will receive the AI reply for this batch',
                status='warning',
            )
            finalize_diagnostics(
                activity_id,
                result=OUTCOME_DELAYED,
                summary='Delayed — grouped into a newer inbound message before a reply was generated',
                status='warning',
            )
            return

        last_ai_sent = LeadActivity.objects.filter(
            lead=lead,
            activity_type=LeadActivity.TYPE_WHATSAPP_SENT,
        ).order_by('-created_at').first()
        pending_filter = {'lead': lead, 'activity_type': LeadActivity.TYPE_WHATSAPP_RECEIVED}
        if last_ai_sent:
            pending_filter['created_at__gt'] = last_ai_sent.created_at
        pending_messages = list(LeadActivity.objects.filter(**pending_filter).order_by('created_at'))
        pending_text_messages = [
            m for m in pending_messages
            if not is_media_only_activity_metadata(m.metadata)
        ]
        if len(pending_text_messages) > 1:
            combined_text = '\n'.join(
                activity_text_for_ai(m.metadata) for m in pending_text_messages
                if m.metadata and activity_text_for_ai(m.metadata)
            ).strip() or text
            logger.info(f"Lead {lead.id}: pooled {len(pending_text_messages)} WhatsApp messages into one response")
        else:
            combined_text = text

        pending_ids = {m.id for m in pending_messages}
        from .ai_service import build_activity_history
        activity_history = build_activity_history(lead, exclude_ids=pending_ids)

        conversation_history = []
        manager_message_count = 0
        whatsapp_activities = filter_activities_since_last_ai_reset(
            LeadActivity.objects.filter(
                lead=lead,
                activity_type__in=[LeadActivity.TYPE_WHATSAPP_RECEIVED, LeadActivity.TYPE_WHATSAPP_SENT]
            ),
            lead,
        ).order_by('created_at').only('id', 'activity_type', 'metadata', 'description')

        for activity in whatsapp_activities:
            if activity.id in pending_ids:
                continue
            meta = activity.metadata or {}
            if is_media_only_activity_metadata(meta):
                continue
            msg_text = activity_text_for_ai(meta, activity.description)
            if activity.activity_type == LeadActivity.TYPE_WHATSAPP_RECEIVED:
                conversation_history.append({"role": "user", "content": msg_text})
            elif meta.get('is_manager_manual'):
                manager_message_count += 1
                conversation_history.append({
                    "role": "system",
                    "content": f"[MANAGER MESSAGE] The human manager (not you) sent this to the client: \"{msg_text}\"",
                })
            else:
                conversation_history.append({"role": "assistant", "content": msg_text})

        if manager_message_count > 0:
            conversation_history.insert(0, {
                "role": "system",
                "content": (
                    "IMPORTANT: Part of this conversation was handled by a human manager. "
                    "Messages marked [MANAGER MESSAGE] were sent by the manager, not by you. "
                    "Continue the conversation naturally, taking into account everything the manager communicated. "
                    "Do NOT contradict or repeat what the manager already told the client."
                ),
            })

        add_diagnostic_step(
            activity_id,
            'generation_started',
            'AI response generation started',
            detail='Preparing a reply for the latest inbound message',
            status='info',
        )

        lead_data = {
            'contact_person': lead.contact_person,
            'source': lead.source,
            'phone': lead.phone,
            'email': lead.email,
            'check_in_date': str(lead.check_in_date) if lead.check_in_date else None,
            'check_out_date': str(lead.check_out_date) if lead.check_out_date else None,
            'guest_count': lead.guest_count,
            'room_type_preference': lead.room_type_preference,
            'meal_plan': lead.meal_plan,
            'discovery_source': lead.discovery_source,
            'discovery_source_detail': lead.discovery_source_detail,
        }
        def _generate_ai_response() -> str | None:
            return agent_dispatcher.dispatch(
                lead, combined_text, lead_data, conversation_history,
                is_pooled=len(pending_text_messages) > 1,
                activity_history=activity_history,
            )

        try:
            ai_response = generate_with_blank_retry(activity_id, _generate_ai_response)
        except Exception as generation_error:
            logger.error(f"Lead {lead.id}: AI generation failed: {generation_error}", exc_info=True)
            add_diagnostic_step(
                activity_id,
                'generation_failed',
                'AI request failed',
                detail='The AI provider failed while generating a reply',
                status='error',
            )
            add_diagnostic_step(
                activity_id,
                'retry_attempt',
                'Retry attempted',
                detail='No automatic retry was attempted for this failure',
                status='warning',
            )
            finalize_diagnostics(
                activity_id,
                result=OUTCOME_FAILED,
                summary='Failed — the AI request did not complete successfully',
                status='error',
            )
            return

        if not ai_response:
            return

        lead.refresh_from_db()
        if lead.ai_paused and lead.ai_paused_by != 'AI Handoff':
            logger.info(f"Lead {lead_id}: AI response suppressed — ai_paused was set during generation")
            add_diagnostic_step(
                activity_id,
                'paused_mid_process',
                'AI status changed during processing',
                detail='AI was paused for this lead before the reply could be sent',
                status='warning',
            )
            finalize_diagnostics(
                activity_id,
                result=OUTCOME_SKIPPED,
                summary='Skipped — AI was paused for this lead while the reply was being prepared',
                status='warning',
            )
            return

        add_diagnostic_step(
            activity_id,
            'channel_send_started',
            'WhatsApp send started',
            detail='Sending the generated reply back to the conversation',
            status='info',
        )

        message_parts = _split_into_messages(ai_response)
        last_result = None
        successful_parts = 0
        for part in message_parts:
            result = whatsapp_service.send_message(sender_phone, part, org=org)
            if result:
                last_result = result
                successful_parts += 1

        if last_result:
            sent_activity = LeadActivity.objects.create(
                lead=lead,
                organization=org,
                activity_type=LeadActivity.TYPE_WHATSAPP_SENT,
                description=f"AI auto-response: {ai_response[:100]}{'...' if len(ai_response) > 100 else ''}",
                metadata={
                    'message_id': last_result.get('message_id'),
                    'text': ai_response,
                    'is_ai_generated': True,
                }
            )
            logger.info(f"Sent AI auto-response to lead {lead.id} via WhatsApp ({len(message_parts)} message(s))")

            agent_service.schedule_idle_or_promise_followup(lead, combined_text, conversation_history, sent_activity.id)

            add_diagnostic_step(
                activity_id,
                'channel_send_succeeded',
                'WhatsApp send succeeded',
                detail=f'Sent {successful_parts} message part(s) back to WhatsApp',
                status='success',
            )
            finalize_diagnostics(
                activity_id,
                result='replied',
                summary='Reply sent successfully on WhatsApp',
                status='success',
            )
        else:
            add_diagnostic_step(
                activity_id,
                'channel_send_failed',
                'WhatsApp send failed',
                detail='WhatsApp did not confirm delivery of the generated reply',
                status='error',
            )
            finalize_diagnostics(
                activity_id,
                result=OUTCOME_FAILED,
                summary='Failed — the reply was generated but WhatsApp did not send it',
                status='error',
            )
            return

        try:
            summary = ai_service.generate_conversation_summary(lead)
            if summary:
                Lead.objects.filter(id=lead_id).update(notes=summary)
                logger.info(f"Updated conversation summary for lead {lead_id}: {summary[:60]}")
        except Exception as _se:
            logger.warning(f"Failed to update summary for lead {lead_id}: {_se}")

        if config.auto_extract_data:
            conversation_history_for_extract = []
            for activity in filter_activities_since_last_ai_reset(
                LeadActivity.objects.filter(
                    lead=lead,
                    activity_type__in=[LeadActivity.TYPE_WHATSAPP_RECEIVED, LeadActivity.TYPE_WHATSAPP_SENT]
                ),
                lead,
            ).order_by('created_at'):
                if is_media_only_activity_metadata(activity.metadata):
                    continue
                role = "user" if activity.activity_type == LeadActivity.TYPE_WHATSAPP_RECEIVED else "assistant"
                msg_text = activity_text_for_ai(activity.metadata, activity.description)
                conversation_history_for_extract.append({"role": role, "content": msg_text})

            our_company_name = config.company_profile.split('\n')[0] if config.company_profile else None
            extracted_data = ai_service.extract_lead_data(text, conversation_history_for_extract, our_company_name, lead.organization)
            if extracted_data:
                from apps.leads.services.stage_resolver import mark_name_confirmed_by_user

                updated_fields = []
                if extracted_data.get('contact_person'):
                    if lead.contact_person != extracted_data['contact_person']:
                        lead.contact_person = extracted_data['contact_person']
                        updated_fields.append('contact_person')
                    if mark_name_confirmed_by_user(lead):
                        updated_fields.append('agent_context')
                if extracted_data.get('phone') and lead.phone != extracted_data['phone']:
                    lead.phone = extracted_data['phone']
                    updated_fields.append('phone')
                if extracted_data.get('email') and not _is_fake_email(extracted_data['email']) and lead.email != extracted_data['email']:
                    lead.email = extracted_data['email']
                    updated_fields.append('email')
                if extracted_data.get('check_in_date') and str(lead.check_in_date or '') != extracted_data['check_in_date']:
                    lead.check_in_date = extracted_data['check_in_date']
                    updated_fields.append('check_in_date')
                if extracted_data.get('check_out_date') and str(lead.check_out_date or '') != extracted_data['check_out_date']:
                    lead.check_out_date = extracted_data['check_out_date']
                    updated_fields.append('check_out_date')
                if extracted_data.get('guest_count') and lead.guest_count != int(extracted_data['guest_count']):
                    lead.guest_count = int(extracted_data['guest_count'])
                    updated_fields.append('guest_count')
                if extracted_data.get('room_type_preference') and lead.room_type_preference != extracted_data['room_type_preference']:
                    lead.room_type_preference = extracted_data['room_type_preference']
                    updated_fields.append('room_type_preference')
                if extracted_data.get('meal_plan'):
                    valid_meal_plans = {'none', 'breakfast', 'lunch', 'dinner', 'half_board_bl', 'half_board_bd', 'full_board'}
                    if extracted_data['meal_plan'] in valid_meal_plans and lead.meal_plan != extracted_data['meal_plan']:
                        lead.meal_plan = extracted_data['meal_plan']
                        updated_fields.append('meal_plan')

                if extracted_data.get('discovery_source'):
                    from apps.leads.services.discovery_sources import normalize_discovery_source
                    discovery_source = normalize_discovery_source(extracted_data['discovery_source'], lead.organization)
                    if discovery_source and lead.discovery_source != discovery_source:
                        lead.discovery_source = discovery_source
                        updated_fields.append('discovery_source')

                if extracted_data.get('discovery_source_detail') and lead.discovery_source_detail != extracted_data['discovery_source_detail']:
                    lead.discovery_source_detail = str(extracted_data['discovery_source_detail'])[:255]
                    updated_fields.append('discovery_source_detail')

                if updated_fields:
                    lead.save(update_fields=list(dict.fromkeys(updated_fields)))
                    logger.info(f"Auto-extracted and updated fields for lead {lead.id}: {updated_fields}")

    except Exception as e:
        try:
            add_diagnostic_step(
                activity_id,
                'internal_exception',
                'Internal exception',
                detail='Processing stopped because of an unexpected internal error',
                status='error',
            )
            finalize_diagnostics(
                activity_id,
                result=OUTCOME_FAILED,
                summary='Failed — an internal exception interrupted AI auto-reply processing',
                status='error',
            )
        except Exception:
            pass
        logger.error(f"Error in background WhatsApp AI response for lead {lead_id}: {e}", exc_info=True)
    finally:
        close_old_connections()


from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, JsonResponse
import json

@csrf_exempt
def whatsapp_webhook(request):
    """
    Webhook endpoint for receiving WhatsApp messages via Cloud API.

    GET: Webhook verification (Meta sends challenge)
    POST: Incoming message handling
    """
    # Webhook verification (GET request)
    if request.method == 'GET':
        mode = request.GET.get('hub.mode', '')
        verify_token = request.GET.get('hub.verify_token', '')
        challenge = request.GET.get('hub.challenge', '')

        import os as _os
        
        # Meta doesn't send an org identifier in the verify request.
        # We must check all WhatsApp configurations to see if the verify_token matches.
        is_valid = False
        
        if verify_token and WhatsAppConfig.objects.filter(verify_token=verify_token).exists():
            is_valid = True
        else:
            env_token = _os.environ.get('WHATSAPP_WEBHOOK_VERIFY_TOKEN') or 'cayu_whatsapp_verify_token_2024'
            if verify_token == env_token:
                is_valid = True

        if mode == 'subscribe' and is_valid:
            return HttpResponse(challenge, content_type='text/plain')
        else:
            return HttpResponse('Invalid verify token', status=403)

    # Incoming message handling (POST request)
    try:
        # If no WhatsApp config exists at all, silently acknowledge and stop.
        if not WhatsAppConfig.objects.exists():
            return JsonResponse({'ok': True})

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'ok': True})

        entries = data.get('entry', [])
        if not entries:
            return JsonResponse({'ok': True})

        for entry in entries:
            changes = entry.get('changes', [])
            for change in changes:
                if change.get('field') != 'messages':
                    continue

                value = change.get('value', {})
                messages = value.get('messages', [])
                contacts = value.get('contacts', [])

                metadata = value.get('metadata', {})
                phone_number_id = metadata.get('phone_number_id')
                
                # Determine which organization owns this WhatsApp number
                _wa_config = None
                if phone_number_id:
                    _wa_config = WhatsAppConfig.objects.filter(phone_number_id=phone_number_id).first()
                
                if not _wa_config:
                    # Fallback to the first available config if phone_number_id is missing/unmatched
                    _wa_config = WhatsAppConfig.objects.first()
                
                if not _wa_config:
                    logger.info("No WhatsApp config found in database")
                    continue
                    
                _wa_org = _wa_config.organization
                _lead_filter = {'organization': _wa_org} if _wa_org else {}

                # Build a contact lookup
                contact_lookup = {}
                for contact in contacts:
                    wa_id = contact.get('wa_id')
                    if wa_id:
                        contact_lookup[wa_id] = contact.get('profile', {}).get('name', '')

                for message in messages:
                    msg_type = message.get('type')
                    if msg_type not in ('text', 'image', 'video', 'audio'):
                        continue

                    sender_phone = message.get('from', '')
                    message_id = message.get('id', '')
                    contact_name = contact_lookup.get(sender_phone, '')

                    media_type = {
                        'image': 'photo',
                        'video': 'video',
                        'audio': 'audio',
                    }.get(msg_type)
                    caption = ''
                    if media_type:
                        media_payload = message.get(msg_type, {})
                        caption = media_payload.get('caption', '')
                        message_text = caption or MEDIA_PLACEHOLDERS.get(media_type, '[Файл получен]')
                    else:
                        media_payload = {}
                        message_text = message.get('text', {}).get('body', '')

                    is_media_only = bool(media_type) and not caption.strip()

                    if not sender_phone or not message_text:
                        continue

                    # Skip messages from our own number
                    if _wa_config.display_phone_number:
                        our_number = _wa_config.display_phone_number.replace('+', '').replace(' ', '').replace('-', '')
                        their_number = sender_phone.replace('+', '').replace(' ', '').replace('-', '')
                        if our_number == their_number:
                            logger.info(f"Skipping message from our own number {sender_phone}")
                            continue

                    # Find or create lead by whatsapp_phone — scoped to this org
                    created_new_lead = False
                    lead = Lead.objects.filter(whatsapp_phone=sender_phone, **_lead_filter).first()
                    if not lead:
                        # Fallback to general phone
                        lead = Lead.objects.filter(phone=sender_phone, **_lead_filter).first()
                        if lead:
                            lead.whatsapp_phone = sender_phone
                            lead.save(update_fields=['whatsapp_phone'])
                        else:
                            lead = Lead.objects.create(
                                whatsapp_phone=sender_phone,
                                contact_person=contact_name,
                                source='WhatsApp',
                                status=Lead.STATUS_NEW,
                                organization=_wa_org,
                                custom_fields={},
                            )
                            created_new_lead = True
                            name_info = f" ({contact_name})" if contact_name else ""
                            LeadActivity.objects.create(
                                lead=lead,
                                organization=_wa_org,
                                activity_type='lead_created',
                                description=f'Lead auto-created from WhatsApp contact: {sender_phone}{name_info}',
                            )
                            logger.info(f"Auto-created lead {lead.id} from WhatsApp: {sender_phone}{name_info}")

                    # Deduplicate by message_id
                    if message_id and LeadActivity.objects.filter(metadata__message_id=message_id).exists():
                        logger.info(f"Skipping duplicate WhatsApp message {message_id}")
                        continue

                    # Download media attachments for manager playback in the CRM.
                    # The AI receives only message text/captions, never the file.
                    media_metadata = {}
                    if media_type:
                        try:
                            media_id = media_payload.get('id')
                            if media_id:
                                message_id_clean = re.sub(r'[^a-zA-Z0-9_\-]', '_', message_id)
                                mime_type = media_payload.get('mime_type')
                                file_name = media_payload.get('filename')
                                default_ext = '.jpg' if media_type == 'photo' else '.mp4' if media_type == 'video' else '.ogg'
                                extension = extension_from_filename(file_name, mime_type, default_ext)
                                dest_path, file_url = incoming_media_path('wa', message_id_clean, extension)

                                download_success = whatsapp_service.download_media(media_id, dest_path, org=_wa_org)
                                if download_success:
                                    media_metadata = build_media_metadata(media_type, file_url, mime_type, file_name)
                                    logger.info(f"Downloaded guest {media_type} from WhatsApp: {media_metadata['file_url']}")
                        except Exception as e:
                            logger.error(f"Error downloading incoming WhatsApp media: {e}", exc_info=True)

                    # Create activity for received message
                    metadata = {
                        'message': message_text,
                        'text': message_text,
                        'message_id': message_id,
                        'sender_phone': sender_phone,
                        'contact_name': contact_name,
                    }
                    if media_metadata:
                        metadata.update(media_metadata)

                    if media_type:
                        desc_media = {
                            'photo': 'photo',
                            'video': 'video',
                            'audio': 'audio',
                        }.get(media_type, 'attachment')
                        desc = f"Received {desc_media} from WhatsApp" + (f": {caption}" if caption else "")
                    else:
                        desc = f'Received from WhatsApp: {message_text[:100]}{"..." if len(message_text) > 100 else ""}'

                    current_activity = LeadActivity.objects.create(
                        lead=lead,
                        organization=_wa_org,
                        activity_type=LeadActivity.TYPE_WHATSAPP_RECEIVED,
                        description=desc,
                        metadata=metadata
                    )
                    media_context = None
                    if media_metadata:
                        try:
                            media_context = resolve_activity_media_context(current_activity)
                        except Exception as exc:
                            logger.warning(f"Could not resolve incoming WhatsApp media context: {exc}")

                    ai_input_text = (
                        (current_activity.metadata or {}).get('ai_text')
                        if media_context
                        else message_text
                    ) or message_text
                    unresolved_media_prompt = ''
                    if media_metadata and not media_context:
                        unresolved_media_prompt = build_unresolved_media_summary(current_activity.metadata)
                        ai_input_text = unresolved_media_prompt
                        unresolved_metadata = dict(current_activity.metadata or {})
                        unresolved_metadata['visual_summary'] = unresolved_media_prompt
                        unresolved_metadata['ai_text'] = unresolved_media_prompt
                        unresolved_metadata['media_context_unresolved'] = True
                        current_activity.metadata = unresolved_metadata
                        current_activity.save(update_fields=['metadata'])

                    initialize_inbound_diagnostics(
                        current_activity,
                        lead=lead,
                        channel='whatsapp',
                        message_text=ai_input_text,
                        created_new_lead=created_new_lead,
                    )

                    # Stamp last_contacted so the CRM reflects when the guest last wrote
                    Lead.objects.filter(id=lead.id).update(last_contacted=date.today())

                    logger.info(f"Received WhatsApp message from lead {lead.id}: {message_text[:50]}")

                    # Spawn background thread only when AI auto-response is active —
                    # silent mode means no processing at all (matches Telegram/Instagram).
                    ai_config = AIConfig.get_config(org=_wa_org)
                    ai_ok = ai_service.is_configured()
                    whatsapp_ok = whatsapp_service.is_configured(org=_wa_org)
                    eligible, eligibility_reason = evaluate_auto_reply_eligibility(
                        lead,
                        channel='whatsapp',
                        config=ai_config,
                        ai_ready=ai_ok,
                        channel_ready=whatsapp_ok,
                        destination=sender_phone,
                        allow_final_stage=True,
                    )
                    add_diagnostic_step(
                        current_activity.id,
                        'ai_status_checked',
                        'AI status checked',
                        detail=get_channel_ai_status_label('whatsapp', config=ai_config, lead=lead) if not lead.ai_paused else 'Paused for this lead',
                        status='success' if not lead.ai_paused and not is_channel_ai_globally_paused('whatsapp', config=ai_config, lead=lead) else 'warning',
                    )
                    add_diagnostic_step(
                        current_activity.id,
                        'eligibility_checked',
                        'Auto-reply check',
                        detail=eligibility_reason,
                        status='success' if eligible else 'warning',
                    )
                    if eligible and (not is_media_only or media_context or unresolved_media_prompt):
                        thread = threading.Thread(
                            target=_delayed_whatsapp_ai_response,
                            args=(lead.id, current_activity.id, sender_phone, message_id, ai_input_text),
                            daemon=True,
                        )
                        thread.start()
                    else:
                        skip_reason = 'media-only message' if is_media_only else eligibility_reason
                        finalize_diagnostics(
                            current_activity.id,
                            result=OUTCOME_SKIPPED,
                            summary=f'Skipped — {skip_reason}',
                            status='warning',
                        )

        return JsonResponse({'ok': True})

    except Exception as e:
        logger.error(f"Error processing WhatsApp webhook: {e}", exc_info=True)
        # Still return 200 to Meta to avoid retries
        return JsonResponse({'ok': True})
