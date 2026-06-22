import re
import logging
import asyncio
import os
import tempfile
import time
import threading
from datetime import date
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status as http_status
from .models import Lead, LeadActivity, AIConfig
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
from .telegram_service import telegram_service
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


# Photos are compressed at upload time. This limit is only used as a safety
# check for pre-existing uncompressed files (legacy fallback at send time).
_TELEGRAM_PHOTO_MAX_BYTES = 8 * 1024 * 1024   # 8 MB safety threshold

def _split_into_messages(text: str) -> list:
    """
    Split a multi-paragraph AI response into individual chat messages by double newlines.
    This preserves newlines and formatting (lists, bullets) inside each paragraph.
    """
    if not text:
        return []
    parts = re.split(r'\n{2,}', text)
    return [p.strip() for p in parts if p.strip()]


def _apply_fast_lead_extraction(lead, text: str) -> list[str]:
    """Persist obvious fields without an LLM call."""
    updated_fields = []
    value = text or ''

    email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', value)
    if email_match and not _is_fake_email(email_match.group(0)) and lead.email != email_match.group(0):
        lead.email = email_match.group(0)
        updated_fields.append('email')

    phone_match = re.search(r'[\+]?[(]?[0-9]{1,3}[)]?[-\s\.]?[(]?[0-9]{1,4}[)]?[-\s\.]?[0-9]{1,4}[-\s\.]?[0-9]{1,9}', value)
    phone_value = ''
    if phone_match:
        digits = re.sub(r'\D', '', phone_match.group(0))
        if len(digits) >= 7 and lead.phone != phone_match.group(0):
            phone_value = phone_match.group(0)
            lead.phone = phone_value
            updated_fields.append('phone')
        elif len(digits) >= 7:
            phone_value = phone_match.group(0)



    try:
        from apps.leads.services.booking_tools import _extract_guest_count_from_text, _infer_relative_booking_dates

        guest_count = _extract_guest_count_from_text(value)
        if guest_count and lead.guest_count != guest_count:
            lead.guest_count = guest_count
            updated_fields.append('guest_count')

        check_in, check_out = _infer_relative_booking_dates(value)
        existing_check_in = lead.check_in_date
        existing_check_out = lead.check_out_date
        if (
            check_in
            and not check_out
            and existing_check_in
            and not existing_check_out
        ):
            try:
                inferred_date = date.fromisoformat(check_in)
                if inferred_date > existing_check_in:
                    check_out = check_in
                    check_in = None
            except (TypeError, ValueError):
                pass

        if check_in and str(lead.check_in_date or '') != check_in:
            lead.check_in_date = check_in
            updated_fields.append('check_in_date')
        if check_out and str(lead.check_out_date or '') != check_out:
            lead.check_out_date = check_out
            updated_fields.append('check_out_date')
    except Exception:
        pass

    lowered = value.lower()
    meal_plan = None
    if 'полный пансион' in lowered or ('завтрак' in lowered and 'обед' in lowered and 'ужин' in lowered):
        meal_plan = 'full_board'
    elif 'полупансион' in lowered:
        meal_plan = 'half_board_bd'
    elif 'завтрак' in lowered:
        meal_plan = 'breakfast'
    elif re.search(r'\bбез\s+пит', lowered):
        meal_plan = 'none'
    if meal_plan and lead.meal_plan != meal_plan:
        lead.meal_plan = meal_plan
        updated_fields.append('meal_plan')

    if updated_fields:
        lead.save(update_fields=list(dict.fromkeys(updated_fields)))
    return list(dict.fromkeys(updated_fields))


def _should_update_conversation_summary(lead) -> bool:
    if not (lead.notes or '').strip():
        return True
    inbound_count = LeadActivity.objects.filter(
        lead=lead,
        activity_type__in=[
            LeadActivity.TYPE_TELEGRAM_RECEIVED,
            LeadActivity.TYPE_INSTAGRAM_RECEIVED,
            LeadActivity.TYPE_WHATSAPP_RECEIVED,
        ],
    ).count()
    return inbound_count > 0 and inbound_count % 4 == 0


def _delayed_ai_response(lead_id: int, activity_id: int, chat_id: str, text: str, username: str) -> None:
    """
    Background thread: handle pool window sleep, then generate and send an AI response.

    Runs after the webhook has already returned 200 to Telegram so that Telegram
    delivers subsequent messages immediately (instead of waiting for the long-running
    request to finish before sending the next one).  This is what makes the
    last-message-wins pooling work: all concurrent messages sleep simultaneously,
    and only the winner (latest activity) proceeds to call the AI.
    """
    from django.db import close_old_connections

    close_old_connections()

    logger.info(f"Background AI thread started for lead {lead_id}")
    try:
        lead = Lead.objects.get(id=lead_id)
        config = AIConfig.get_config(org=lead.organization)
        current_activity = LeadActivity.objects.get(id=activity_id)

        if not is_channel_ai_globally_paused('telegram', config=config, lead=lead):
            agent_service.process_incoming_message(lead, text, channel='telegram', lightweight=True)

        add_diagnostic_step(
            activity_id,
            'ai_status_checked',
            'AI status re-checked before processing',
            detail=get_channel_ai_status_label('telegram', config=config, lead=lead) if not lead.ai_paused else 'Paused for this lead',
            status='success' if not lead.ai_paused and not is_channel_ai_globally_paused('telegram', config=config, lead=lead) else 'warning',
        )

        eligible, eligibility_reason = evaluate_auto_reply_eligibility(
            lead,
            channel='telegram',
            config=config,
            ai_ready=ai_service.is_configured(),
            channel_ready=telegram_service.is_configured_sync(),
            destination=chat_id,
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
            logger.info(f"Lead {lead_id}: AI response skipped ({eligibility_reason})")
            finalize_diagnostics(
                activity_id,
                result=OUTCOME_SKIPPED,
                summary=f'Skipped — {eligibility_reason}',
                status='warning',
            )
            return

        def _send_typing():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(telegram_service.send_chat_action(chat_id, 'typing'))
                loop.close()
            except Exception:
                pass

        _send_typing()

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
                if remaining > 0:
                    _send_typing()

        latest_received = LeadActivity.objects.filter(
            lead=lead,
            activity_type='telegram_received',
        ).order_by('-created_at').first()
        if latest_received and latest_received.id != current_activity.id:
            logger.info(
                f"Lead {lead.id}: skipping response, newer message "
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
            activity_type=LeadActivity.TYPE_TELEGRAM_SENT,
        ).order_by('-created_at').first()
        pending_filter = {'lead': lead, 'activity_type': 'telegram_received'}
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
            logger.info(f"Lead {lead.id}: pooled {len(pending_text_messages)} messages into one response")
        else:
            combined_text = text

        pending_ids = {m.id for m in pending_messages}

        from .ai_service import build_activity_history
        activity_history = build_activity_history(lead, exclude_ids=pending_ids)

        conversation_history = []
        manager_message_count = 0
        telegram_activities = filter_activities_since_last_ai_reset(
            LeadActivity.objects.filter(
                lead=lead,
                activity_type__in=['telegram_received', 'telegram_sent']
            ),
            lead,
        ).order_by('created_at').only('id', 'activity_type', 'metadata', 'description')

        for activity in telegram_activities:
            if activity.id in pending_ids:
                continue
            meta = activity.metadata or {}
            if is_media_only_activity_metadata(meta):
                continue
            msg_text = activity_text_for_ai(meta, activity.description)
            if (
                activity.activity_type == LeadActivity.TYPE_TELEGRAM_SENT
                and not meta.get('text')
                and (
                    meta.get('media_id')
                    or meta.get('room_category')
                    or meta.get('photos_sent')
                    or (activity.description or '').lower().startswith('ai sent')
                )
            ):
                continue
            if activity.activity_type == 'telegram_received':
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

        _send_typing()
        add_diagnostic_step(
            activity_id,
            'generation_started',
            'AI response generation started',
            detail='Preparing a reply for the latest inbound message',
            status='info',
        )

        # Media sending should be decided by the configured AI flow/tool prompt,
        # not by channel-level keyword matching.
        selected_media = None

        fast_updated = _apply_fast_lead_extraction(lead, combined_text)
        if fast_updated:
            logger.info(f"Fast-extracted and updated fields for lead {lead.id}: {fast_updated}")

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
                selected_media=selected_media, is_pooled=len(pending_text_messages) > 1,
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

        album_photos = []
        album_file_urls = []
        album_photo_objs = []
        if selected_media and selected_media.media_type == 'photo':
            sent_photo_ids: set = set()
            prev_meta_qs = LeadActivity.objects.filter(
                lead=lead,
                activity_type=LeadActivity.TYPE_TELEGRAM_SENT,
                metadata__media_id=selected_media.id,
            ).values_list('metadata', flat=True)
            for meta in prev_meta_qs:
                if meta and isinstance(meta.get('sent_photo_ids'), list):
                    sent_photo_ids.update(meta['sent_photo_ids'])

            def _photo_path(photo):
                return os.path.join(settings.MEDIA_ROOT, photo.file.name)

            all_photos = [p for p in selected_media.photos.all() if p.file and os.path.isfile(_photo_path(p))]
            unsent = [p for p in all_photos if p.id not in sent_photo_ids]
            if not unsent:
                unsent = all_photos
            photos_to_send = unsent[:3]

            if photos_to_send:
                for p in photos_to_send:
                    photo_path = _photo_path(p)
                    album_photos.append(photo_path)
                    album_file_urls.append(p.file.url)
                    album_photo_objs.append(p)
            elif selected_media.file:
                file_path = os.path.join(settings.MEDIA_ROOT, selected_media.file.name)
                if os.path.isfile(file_path):
                    album_photos.append(file_path)
                    album_file_urls.append(selected_media.file.url)
                else:
                    logger.warning(f"Lead {lead.id}: selected media file missing, skipped: {file_path}")

        add_diagnostic_step(
            activity_id,
            'channel_send_started',
            'Telegram send started',
            detail='Sending the generated reply back to the conversation',
            status='info',
        )

        message_parts = _split_into_messages(ai_response)
        result = None
        successful_parts = 0
        for i, part in enumerate(message_parts):
            if i > 0:
                _send_typing()

            async def _send_part(msg=part):
                return await telegram_service.send_message(chat_id, msg)

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                part_result = loop.run_until_complete(_send_part())
                if part_result:
                    result = part_result
                    successful_parts += 1
            except Exception as send_exc:
                logger.error(f"Failed to send message part for lead {lead.id}: {send_exc}", exc_info=True)
            finally:
                loop.close()

        if result:
            sent_activity = LeadActivity.objects.create(
                lead=lead,
                organization=lead.organization,
                activity_type=LeadActivity.TYPE_TELEGRAM_SENT,
                description=f"AI auto-response: {ai_response[:100]}{'...' if len(ai_response) > 100 else ''}",
                metadata={
                    'message_id': result.get('message_id'),
                    'text': ai_response,
                    'is_ai_generated': True,
                }
            )
            logger.info(f"Sent AI auto-response to lead {lead.id} ({len(message_parts)} message(s))")

            agent_service.schedule_idle_or_promise_followup(lead, combined_text, conversation_history, sent_activity.id)

            add_diagnostic_step(
                activity_id,
                'channel_send_succeeded',
                'Telegram send succeeded',
                detail=f'Sent {successful_parts} message part(s) back to Telegram',
                status='success',
            )
            finalize_diagnostics(
                activity_id,
                result='replied',
                summary='Reply sent successfully on Telegram',
                status='success',
            )
        else:
            add_diagnostic_step(
                activity_id,
                'channel_send_failed',
                'Telegram send failed',
                detail='Telegram did not confirm delivery of the generated reply',
                status='error',
            )
            finalize_diagnostics(
                activity_id,
                result=OUTCOME_FAILED,
                summary='Failed — the reply was generated but Telegram did not send it',
                status='error',
            )
            return

        media_result = None
        if selected_media:
            try:
                send_paths = list(album_photos)
                temp_paths = []
                if selected_media.media_type == 'photo':
                    from apps.hotel_media.utils import compress_image_for_telegram
                    send_paths = []
                    for photo_path in album_photos:
                        if os.path.getsize(photo_path) > _TELEGRAM_PHOTO_MAX_BYTES:
                            with open(photo_path, 'rb') as fh:
                                cf = compress_image_for_telegram(fh, filename=os.path.basename(photo_path))
                            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tf:
                                tf.write(cf.read())
                                send_paths.append(tf.name)
                                temp_paths.append(tf.name)
                            logger.info(f"Legacy compress: {photo_path} → {os.path.getsize(send_paths[-1]) // 1024}KB")
                        else:
                            send_paths.append(photo_path)

                async def _send_media():
                    if selected_media.media_type == 'photo' and send_paths:
                        if len(send_paths) > 1:
                            return await telegram_service.send_media_group(chat_id, send_paths, caption=selected_media.title)
                        return await telegram_service.send_photo(chat_id, send_paths[0], caption=selected_media.title)
                    if selected_media.media_type == 'document' and selected_media.file:
                        file_path = os.path.join(settings.MEDIA_ROOT, selected_media.file.name)
                        return await telegram_service.send_document(chat_id, file_path, caption=selected_media.title)
                    if selected_media.media_type == 'video' and selected_media.video_url:
                        video_msg = f"🎥 {selected_media.title}: {selected_media.video_url}"
                        return await telegram_service.send_message(chat_id, video_msg)
                    return None

                media_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(media_loop)
                try:
                    media_result = media_loop.run_until_complete(_send_media())
                finally:
                    media_loop.close()
                    for tp in temp_paths:
                        try:
                            os.unlink(tp)
                        except Exception:
                            pass
            except Exception as media_exc:
                logger.error(f"Failed to send media for lead {lead.id}: {media_exc}", exc_info=True)

        if selected_media and media_result:
            from apps.hotel_media.models import HotelMediaItem
            HotelMediaItem.objects.filter(pk=selected_media.pk).update(ai_send_count=selected_media.ai_send_count + 1)
            LeadActivity.objects.create(
                lead=lead,
                organization=lead.organization,
                activity_type=LeadActivity.TYPE_TELEGRAM_SENT,
                description=f"AI sent media: {selected_media.title}",
                metadata={
                    'media_id': selected_media.id,
                    'media_type': selected_media.media_type,
                    'media_title': selected_media.title,
                    'file_url': album_file_urls[0] if album_file_urls else (selected_media.file.url if selected_media.file else None),
                    'file_urls': album_file_urls,
                    'sent_photo_ids': [p.id for p in album_photo_objs],
                    'is_ai_generated': True,
                }
            )
            logger.info(f"AI sent media item {selected_media.id} ({len(album_photos)} photo(s)) to lead {lead.id}")

        if _should_update_conversation_summary(lead):
            try:
                summary = ai_service.generate_conversation_summary(lead)
                if summary:
                    Lead.objects.filter(id=lead_id).update(notes=summary)
                    logger.info(f"Updated conversation summary for lead {lead_id}: {summary[:60]}")
            except Exception as _se:
                logger.warning(f"Failed to update summary for lead {lead_id}: {_se}")
        else:
            logger.info(f"Lead {lead.id}: skipped conversation summary refresh to reduce LLM load")

        if config.auto_extract_data:
            # Re-use the conversation_history already built for the booking agent.
            # It ends with the current user message (pending_ids excluded), so
            # extract_lead_data will correctly append it as the final user turn.
            our_company_name = config.company_profile.split('\n')[0] if config.company_profile else None
            try:
                from apps.leads.services.stage_resolver import is_reliable_contact_person

                has_guest_name = is_reliable_contact_person(lead)
            except Exception:
                has_guest_name = bool(lead.contact_person)
            should_run_llm_extractor = not all([
                has_guest_name,
                lead.phone,
                lead.check_in_date,
                lead.check_out_date,
                lead.guest_count,
                lead.room_type_preference,
                lead.meal_plan,
                lead.discovery_source,
            ])
            if not should_run_llm_extractor:
                logger.info(f"Lead {lead.id}: skipped LLM extractor; key booking fields already present")
                extracted_data = {}
            else:
                extracted_data = ai_service.extract_lead_data(text, conversation_history, our_company_name, lead.organization)
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
                if extracted_data.get('problem_description') and lead.problem_description != extracted_data['problem_description']:
                    lead.problem_description = extracted_data['problem_description']
                    updated_fields.append('problem_description')
                if extracted_data.get('preferred_contact_time') and lead.preferred_contact_time != extracted_data['preferred_contact_time']:
                    lead.preferred_contact_time = extracted_data['preferred_contact_time']
                    updated_fields.append('preferred_contact_time')
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
        logger.error(f"Error in background AI response for lead {lead_id}: {e}", exc_info=True)
    finally:
        close_old_connections()


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])  # Telegram webhook needs public access
def telegram_webhook(request):
    """
    Webhook endpoint for receiving Telegram messages.

    Telegram sends updates in this format:
    {
        "update_id": 123456789,
        "message": {
            "message_id": 1,
            "from": {
                "id": 12345678,
                "is_bot": false,
                "first_name": "John",
                "username": "johndoe"
            },
            "chat": {
                "id": 12345678,
                "first_name": "John",
                "username": "johndoe",
                "type": "private"
            },
            "date": 1234567890,
            "text": "Hello!"
        }
    }
    """
    try:
        data = request.data

        # Extract message data
        message = data.get('message', {})
        if not message:
            # Not a message update, ignore
            return Response({'ok': True})

        chat = message.get('chat', {})
        chat_id = str(chat.get('id', ''))
        text = message.get('text', '')
        photo = message.get('photo')
        video = message.get('video') or message.get('video_note')
        audio = message.get('audio') or message.get('voice')
        caption = message.get('caption', '')
        from_user = message.get('from', {})
        username = from_user.get('username', '')

        is_photo = bool(photo)
        media_type = None
        media_payload = None
        if is_photo:
            media_type = 'photo'
            media_payload = photo[-1]
        elif video:
            media_type = 'video'
            media_payload = video
        elif audio:
            media_type = 'audio'
            media_payload = audio

        is_media_only = bool(media_type) and not (text or caption).strip()
        if media_type and not text:
            text = caption or MEDIA_PLACEHOLDERS.get(media_type, '[Файл получен]')

        if not chat_id or not text:
            return Response({'ok': True})

        # Silently ignore all messages from the manager notification group chat.
        # That chat is outbound-only — the bot posts transfer alerts there and
        # must never process replies/messages from it as leads.
        try:
            from apps.flows.models import ManagerTransferConfig
            transfer_cfg = ManagerTransferConfig.get_config()
            if transfer_cfg and transfer_cfg.recipient_id and chat_id == str(transfer_cfg.recipient_id):
                if chat.get('type') != 'private':
                    return Response({'ok': True})
        except Exception:
            pass  # If config is unavailable, continue normal processing

        # Determine which organization this webhook belongs to via TelegramConfig
        from .models import TelegramConfig, PipelineStage
        _tg_config = TelegramConfig.get_config()
        _tg_org = _tg_config.organization if _tg_config else None

        # Find or create lead by telegram_user_id or chat_id — scoped to this org
        user_id = str(from_user.get('id', ''))
        _lead_filter = {'organization': _tg_org} if _tg_org else {}

        created_new_lead = False
        try:
            # Try to find by telegram_user_id first (most reliable)
            if user_id:
                lead = Lead.objects.get(telegram_user_id=user_id, **_lead_filter)
            else:
                lead = Lead.objects.get(telegram_chat_id=chat_id, **_lead_filter)
        except Lead.DoesNotExist:
            # Auto-create lead for new Telegram contacts
            first_name = from_user.get('first_name', '')
            last_name = from_user.get('last_name', '')

            # Build contact name from available information
            name_parts = []
            if first_name:
                name_parts.append(first_name)
            if last_name:
                name_parts.append(last_name)
            contact_name = ' '.join(name_parts) if name_parts else username

            # Use first pipeline stage key scoped to this org
            stage_filter = {'organization': _tg_org} if _tg_org else {}
            first_stage = PipelineStage.objects.filter(**stage_filter).order_by('order').first()
            initial_status = first_stage.key if first_stage else Lead.STATUS_NEW

            lead = Lead.objects.create(
                contact_person=contact_name or '',
                telegram_user_id=user_id,
                telegram_chat_id=chat_id,
                telegram_username=username,
                source='Telegram',
                status=initial_status,
                organization=_tg_org,
                custom_fields={},
            )
            created_new_lead = True

            # Log lead creation
            LeadActivity.objects.create(
                lead=lead,
                organization=_tg_org,
                activity_type='lead_created',
                description=f'Lead auto-created from Telegram contact: @{username or chat_id}',
            )

            logger.info(f"Auto-created lead {lead.id} from Telegram chat_id: {chat_id}")

        # Deduplicate: Telegram retries webhook delivery if we don't respond within ~30s.
        # Since the pool window sleep keeps the connection open, Telegram will retry the
        # same message. Check message_id to avoid processing and responding twice.
        telegram_message_id = message.get('message_id')
        if telegram_message_id and LeadActivity.objects.filter(
            lead=lead,
            activity_type='telegram_received',
            metadata__message_id=telegram_message_id,
        ).exists():
            logger.info(
                f"Lead {lead.id}: duplicate webhook for Telegram message_id "
                f"{telegram_message_id}, ignoring retry"
            )
            return Response({'ok': True})

        # Create media metadata if an attachment is present. The AI receives only
        # text/captions; media files are stored for manager playback in the CRM.
        media_metadata = {}
        if media_type and media_payload:
            try:
                file_id = media_payload.get('file_id')
                file_unique_id = media_payload.get('file_unique_id') or file_id or media_type
                mime_type = media_payload.get('mime_type')
                file_name = media_payload.get('file_name')
                default_ext = '.jpg' if media_type == 'photo' else '.mp4' if media_type == 'video' else '.ogg'
                extension = extension_from_filename(file_name, mime_type, default_ext)
                dest_path, file_url = incoming_media_path(
                    'tg',
                    f"{message.get('message_id')}_{file_unique_id}",
                    extension,
                )

                # Download file using telegram_service
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                download_success = loop.run_until_complete(
                    telegram_service.download_file(file_id, dest_path)
                )
                loop.close()

                if download_success:
                    media_metadata = build_media_metadata(media_type, file_url, mime_type, file_name)
                    logger.info(f"Downloaded guest {media_type} from Telegram: {media_metadata['file_url']}")
            except Exception as e:
                logger.error(f"Error downloading incoming Telegram media: {e}", exc_info=True)

        # Create activity for received message
        metadata = {
            'message': text,
            'text': text,
            'message_id': message.get('message_id'),
            'chat_id': chat_id,
            'username': username,
            'from_user': from_user,
        }
        if media_metadata:
            metadata.update(media_metadata)

        reply_to_message = message.get('reply_to_message')
        if reply_to_message:
            reply_from = reply_to_message.get('from', {})
            reply_text = reply_to_message.get('text') or reply_to_message.get('caption')
            if not reply_text:
                if reply_to_message.get('photo'):
                    reply_text = '[Фото]'
                elif reply_to_message.get('video') or reply_to_message.get('video_note'):
                    reply_text = '[Видео]'
                elif reply_to_message.get('voice') or reply_to_message.get('audio'):
                    reply_text = '[Голосовое сообщение]'
                elif reply_to_message.get('document'):
                    reply_text = '[Файл]'
                else:
                    reply_text = '[Сообщение]'

            reply_sender_name = reply_from.get('first_name') or reply_from.get('username') or ('Бот' if reply_from.get('is_bot') else 'Гость')
            metadata['reply_to'] = {
                'message_id': reply_to_message.get('message_id'),
                'text': reply_text,
                'sender_name': reply_sender_name,
                'from_bot': bool(reply_from.get('is_bot')),
            }

        if media_type:
            desc_media = {
                'photo': 'photo',
                'video': 'video',
                'audio': 'audio',
            }.get(media_type, 'attachment')
            desc = f"Received {desc_media} from {username or 'unknown'}" + (f": {caption}" if caption else "")
        else:
            desc = f'Received from {username or "unknown"}: {text[:100]}{"..." if len(text) > 100 else ""}'

        current_activity = LeadActivity.objects.create(
            lead=lead,
            organization=lead.organization,
            activity_type='telegram_received',
            description=desc,
            metadata=metadata
        )
        media_context = None
        if media_metadata:
            try:
                media_context = resolve_activity_media_context(current_activity)
            except Exception as exc:
                logger.warning(f"Could not resolve incoming Telegram media context: {exc}")

        ai_input_text = (
            (current_activity.metadata or {}).get('ai_text')
            if media_context
            else text
        ) or text
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
            channel='telegram',
            message_text=ai_input_text,
            created_new_lead=created_new_lead,
        )

        # Stamp last_contacted so the CRM reflects when the guest last wrote
        Lead.objects.filter(id=lead.id).update(last_contacted=date.today())

        logger.info(f"Received Telegram message from lead {lead.id}: {text[:50]}")

        # Respond to Telegram immediately — processing happens in a background thread.
        # This prevents Telegram from queuing subsequent messages while we sleep for
        # the pool window, which is what caused messages to be processed one-by-one
        # instead of being combined into a single pooled response.
        config = AIConfig.get_config(org=lead.organization)
        ai_ok = ai_service.is_configured()
        tg_ok = telegram_service.is_configured_sync()
        eligible, eligibility_reason = evaluate_auto_reply_eligibility(
            lead,
            channel='telegram',
            config=config,
            ai_ready=ai_ok,
            channel_ready=tg_ok,
            destination=chat_id,
            allow_final_stage=True,
        )
        add_diagnostic_step(
            current_activity.id,
            'ai_status_checked',
            'AI status checked',
            detail=get_channel_ai_status_label('telegram', config=config, lead=lead) if not lead.ai_paused else 'Paused for this lead',
            status='success' if not lead.ai_paused and not is_channel_ai_globally_paused('telegram', config=config, lead=lead) else 'warning',
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
                target=_delayed_ai_response,
                args=(lead.id, current_activity.id, chat_id, ai_input_text, username),
                daemon=True,
            )
            thread.start()
            logger.info(f"Lead {lead.id}: background AI thread dispatched")
        else:
            skip_reason = 'media-only message' if is_media_only else eligibility_reason
            logger.info(f"Lead {lead.id}: skipping AI thread — {skip_reason}")
            finalize_diagnostics(
                current_activity.id,
                result=OUTCOME_SKIPPED,
                summary=f'Skipped — {skip_reason}',
                status='warning',
            )

        return Response({'ok': True})

    except Exception as e:
        logger.error(f"Error processing Telegram webhook: {e}", exc_info=True)
        # Still return 200 to Telegram to avoid retries
        return Response({'ok': True})
