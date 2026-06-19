import os
import re
import logging
import time
import threading
import requests
from datetime import date
from urllib.parse import parse_qs, urlparse
from .instagram_integration_views import _get_app_config
from django.db import models
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status as http_status
from .models import Lead, LeadActivity, AIConfig, InstagramConnection
from .ai_service import ai_service
from .ai_memory import filter_activities_since_last_ai_reset
from .instagram_service import instagram_service
from .agent_service import agent_service
from .agent_dispatcher import agent_dispatcher
from .channel_ai_control import is_channel_ai_globally_paused
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
INSTAGRAM_GRAPH_API_VERSION = 'v25.0'


def _get_verify_token() -> str:
    app_config = _get_app_config()
    if app_config and app_config.webhook_verify_token:
        return app_config.webhook_verify_token
    return os.environ.get('INSTAGRAM_VERIFY_TOKEN', '')


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


_INSTAGRAM_SOCIAL_ATTACHMENT_TYPES = {
    'share': 'post',
    'ig_post': 'post',
    'ig_reel': 'reel',
    'ig_story': 'story',
}
_INSTAGRAM_CONTEXT_ID_KEYS = {
    'id',
    'media_id',
    'story_id',
    'share_id',
    'reel_id',
    'post_id',
    'attachment_id',
    'asset_id',
}
_INSTAGRAM_CONTEXT_URL_KEYS = {
    'url',
    'media_url',
    'thumbnail_url',
    'permalink',
    'story_url',
    'share_url',
}


def _append_unique(values: list[str], value: str | int | None) -> None:
    cleaned = str(value or '').strip()
    if cleaned and cleaned not in values:
        values.append(cleaned)


def _collect_nested_key_values(value, keys: set[str]) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            if key in keys:
                if isinstance(nested, list):
                    for item in nested:
                        _append_unique(found, item)
                elif not isinstance(nested, dict):
                    _append_unique(found, nested)
            for item in _collect_nested_key_values(nested, keys):
                _append_unique(found, item)
    elif isinstance(value, list):
        for nested in value:
            for item in _collect_nested_key_values(nested, keys):
                _append_unique(found, item)
    return found


def _collect_nested_urls(value) -> list[str]:
    urls: list[str] = []
    if isinstance(value, dict):
        for nested in value.values():
            for item in _collect_nested_urls(nested):
                _append_unique(urls, item)
    elif isinstance(value, list):
        for nested in value:
            for item in _collect_nested_urls(nested):
                _append_unique(urls, item)
    else:
        text = str(value or '').strip()
        if text.startswith(('http://', 'https://')):
            _append_unique(urls, text)
    return urls


def _ids_from_instagram_url(value: str) -> list[str]:
    parsed = urlparse(str(value or '').strip())
    params = parse_qs(parsed.query)
    ids: list[str] = []
    for key in ('id', 'media_id', 'story_id', 'share_id', 'reel_id', 'post_id', 'asset_id'):
        for item in params.get(key, []):
            _append_unique(ids, item)
    return ids


def _first_present(values: list[str]) -> str:
    return values[0] if values else ''


def _extract_instagram_content_context(event: dict, message: dict, attachments: list | None = None) -> dict:
    """Extract story/post/share identifiers from Instagram messaging payloads.

    Meta payload shapes vary by event type and API version, so this intentionally
    keeps the raw sub-payloads while normalizing the IDs we can use for lookup.
    """
    attachments = attachments or []
    context: dict = {}

    reply_to = message.get('reply_to') if isinstance(message.get('reply_to'), dict) else {}
    story = reply_to.get('story') if isinstance(reply_to.get('story'), dict) else {}
    if story:
        story_id = str(story.get('id') or story.get('story_id') or '').strip()
        if story_id:
            context['story_id'] = story_id
            context['content_type'] = 'story'
        if story.get('url'):
            context['story_url'] = story.get('url')
        context['raw_story'] = story

    referral = event.get('referral') if isinstance(event.get('referral'), dict) else {}
    if referral:
        ref_id = str(referral.get('media_id') or referral.get('id') or referral.get('ref') or '').strip()
        if ref_id:
            context['media_id'] = ref_id
            context.setdefault('content_type', 'post')
        referral_urls = _collect_nested_urls(referral)
        if referral_urls:
            context['urls'] = list(dict.fromkeys([*(context.get('urls') or []), *referral_urls]))
            context.setdefault('share_url', referral_urls[0])
        context['raw_referral'] = referral

    for attachment in attachments:
        if not isinstance(attachment, dict):
            continue
        payload = attachment.get('payload') if isinstance(attachment.get('payload'), dict) else {}
        attachment_type = str(attachment.get('type') or '').strip()
        content_type = _INSTAGRAM_SOCIAL_ATTACHMENT_TYPES.get(attachment_type)
        if not content_type:
            continue

        context.setdefault('content_type', content_type)
        context.setdefault('attachment_type', attachment_type)

        id_values = _collect_nested_key_values(
            {'attachment': attachment, 'payload': payload},
            _INSTAGRAM_CONTEXT_ID_KEYS,
        )
        url_values = _collect_nested_urls({'attachment': attachment, 'payload': payload})
        for url in url_values:
            for url_id in _ids_from_instagram_url(url):
                _append_unique(id_values, url_id)
        if url_values:
            context['urls'] = list(dict.fromkeys([*(context.get('urls') or []), *url_values]))
            context.setdefault('share_url', url_values[0])
            if content_type == 'story':
                context.setdefault('story_url', url_values[0])

        primary_id = _first_present(id_values)
        if primary_id:
            context.setdefault('media_id', primary_id)
            if content_type == 'story':
                context.setdefault('story_id', primary_id)
            elif content_type == 'reel':
                context.setdefault('reel_id', primary_id)
                context.setdefault('share_id', primary_id)
            else:
                context.setdefault('post_id', primary_id)
                context.setdefault('share_id', primary_id)

        keyed_urls = _collect_nested_key_values(
            {'attachment': attachment, 'payload': payload},
            _INSTAGRAM_CONTEXT_URL_KEYS,
        )
        for key, context_key in (
            ('url', 'share_url'),
            ('media_url', 'media_url'),
            ('thumbnail_url', 'thumbnail_url'),
            ('permalink', 'permalink'),
            ('story_url', 'story_url'),
            ('share_url', 'share_url'),
        ):
            value = _first_present(_collect_nested_key_values({'attachment': attachment, 'payload': payload}, {key}))
            if value:
                context.setdefault(context_key, value)
        if keyed_urls:
            context['urls'] = list(dict.fromkeys([*(context.get('urls') or []), *keyed_urls]))

        context.setdefault('raw_attachments', []).append(attachment)

    return context


def _handle_echo_event(mid: str, echo_text: str, guest_user_id: str, org_id: int = None) -> None:
    """
    Process an Instagram echo event in a background thread.

    Called when Meta reflects a sent DM back to the webhook (is_echo=True).
    Runs with a 3-second delay before checking the DB so that any concurrent
    CRM thread (AI auto-response, dashboard send) has time to write its
    LeadActivity before we look it up.

    Without this delay there is a race: Meta delivers the echo within
    milliseconds, but our activity is created AFTER send_message() returns.
    Reading the DB immediately would find nothing → falsely flag the lead
    as a native-app takeover and set ai_paused=True.

    Also checks metadata['all_message_ids'] so that echoes from each sentence
    part of a multi-part AI response are correctly identified as CRM echoes —
    only the last part's message_id is stored as 'message_id', but all parts
    are stored in 'all_message_ids'.
    """
    from django.db import close_old_connections
    from datetime import date as _date
    from django.db.models import Q
    close_old_connections()

    try:
        # Wait before checking — lets the CRM activity creation win the race.
        time.sleep(3)

        # A CRM echo is identified by its message_id stored in the LeadActivity
        # created at send time with echo_origin='crm'.  Multi-part responses
        # store ALL sent message_ids under 'all_message_ids'.
        crm_echo = LeadActivity.objects.filter(
            echo_origin=LeadActivity.ECHO_ORIGIN_CRM,
        ).filter(
            Q(metadata__message_id=mid) |
            Q(metadata__all_message_ids__contains=[mid])
        ).first()

        if crm_echo is None:
            # Not found in CRM activity log → native Instagram app send.
            try:
                echo_lead = Lead.objects.get(instagram_user_id=guest_user_id, organization_id=org_id)

                # Only pause AI if this lead has prior CRM-sent messages.
                # No prior CRM history → stale echo from a deleted/recreated lead.
                has_crm_sent = LeadActivity.objects.filter(
                    lead=echo_lead,
                    activity_type=LeadActivity.TYPE_INSTAGRAM_SENT,
                    echo_origin=LeadActivity.ECHO_ORIGIN_CRM,
                ).exists()

                if echo_text:
                    LeadActivity.objects.create(
                        lead=echo_lead,
                        organization=echo_lead.organization,
                        activity_type=LeadActivity.TYPE_INSTAGRAM_SENT,
                        description=f"Sent via Instagram app: {echo_text[:100]}{'...' if len(echo_text) > 100 else ''}",
                        echo_origin=LeadActivity.ECHO_ORIGIN_INSTAGRAM_APP,
                        metadata={
                            'message_id': mid,
                            'text': echo_text,
                            'sent_via': 'native_app',
                        },
                    )
                    Lead.objects.filter(id=echo_lead.id).update(last_contacted=_date.today())

                if has_crm_sent and not echo_lead.ai_paused:
                    Lead.objects.filter(id=echo_lead.id).update(ai_paused=True)
                    LeadActivity.objects.create(
                        lead=echo_lead,
                        organization=echo_lead.organization,
                        activity_type=LeadActivity.TYPE_LEAD_UPDATED,
                        description='Manager took over via Instagram app',
                        echo_origin=LeadActivity.ECHO_ORIGIN_INSTAGRAM_APP,
                        metadata={'message_id': mid},
                    )
                    logger.info(f"Lead {echo_lead.id}: AI paused — manager sent via native Instagram app")
                elif not has_crm_sent:
                    logger.info(
                        f"Echo mid={mid} for lead {echo_lead.id}: "
                        f"no prior CRM sends — AI not paused "
                        f"(stale echo or first native send on new lead)"
                    )
            except Lead.DoesNotExist:
                pass
    except Exception as e:
        logger.warning(f"Echo origin check failed (mid={mid}): {e}")
    finally:
        close_old_connections()


from celery import shared_task

@shared_task
def _delayed_instagram_ai_response(
    lead_id: int,
    activity_id: int,
    sender_id: str,
    text: str,
    force_response: bool = False,
) -> None:
    """
    Background thread: classify intent, pool window, then generate and send an AI response.

    force_response=True bypasses the pool window and sends regardless of intent tier
    (used for manager-triggered manual responses).

    Runs after the webhook has already returned 200 to Meta so that Meta delivers
    subsequent messages immediately (instead of waiting for the long-running request
    to finish).  This is what makes last-message-wins pooling work: all concurrent
    messages sleep simultaneously, and only the winner (latest activity) calls the AI.
    """
    from django.db import close_old_connections
    close_old_connections()

    try:
        lead = Lead.objects.get(id=lead_id)
        config = AIConfig.get_config(org=lead.organization)
        current_activity = LeadActivity.objects.get(id=activity_id)

        # Respect manual takeover — manager paused AI via native Instagram app
        if lead.ai_paused and not force_response:
            logger.info(f"Lead {lead_id}: AI response skipped (ai_paused=True — manager in control)")
            return

        if is_channel_ai_globally_paused('instagram', config=config, lead=lead):
            logger.info(f"Lead {lead_id}: AI response skipped (Instagram AI paused globally)")
            return

        # Backfill username/contact_person if the webhook's username lookup failed.
        # A lead without these fields shows as a raw numeric PSID in the Communications tab,
        # making it invisible to staff. Retry here in the background thread — we have more
        # time and the token is usually valid by now.
        if not lead.instagram_username and sender_id:
            from .models import InstagramConnection
            conn = InstagramConnection.get_config()
            if conn and conn.access_token:
                try:
                    u_resp = requests.get(
                        f'https://graph.instagram.com/{INSTAGRAM_GRAPH_API_VERSION}/{sender_id}',
                        params={'fields': 'username', 'access_token': conn.access_token},
                        timeout=5,
                    )
                    if u_resp.ok:
                        fetched_username = u_resp.json().get('username') or None
                        if fetched_username:
                            update_fields = ['instagram_username']
                            lead.instagram_username = fetched_username
                            if not lead.contact_person:
                                lead.contact_person = f'@{fetched_username}'
                                update_fields.append('contact_person')
                            lead.save(update_fields=update_fields)
                            logger.info(
                                f"Lead {lead_id}: backfilled username @{fetched_username} in background thread"
                            )
                except Exception as _ue:
                    logger.warning(f"Lead {lead_id}: background username fetch failed: {_ue}")

        # Process incoming message: status progression, objection handling, goal tracking.
        # Only runs when auto-response is enabled — matches original silent-mode behaviour.
        if config.ai_auto_response:
            agent_service.process_incoming_message(lead, text, channel='instagram')

        # Classification and response both require AI to be configured.
        if not ai_service.is_configured():
            return

        will_respond = force_response or (
            config.ai_auto_response and instagram_service.is_configured()
        )

        def _send_typing():
            """Fire-and-forget typing indicator. Never raises."""
            try:
                instagram_service.send_typing_indicator(sender_id)
            except Exception:
                pass

        if not force_response:
            # Show typing immediately — instant feedback for the guest
            if will_respond:
                _send_typing()

            # Pool window: sleep in 4-second chunks, refreshing the typing indicator
            # each cycle (Instagram shows typing_on for ~20 s, but 4 s keeps it tight).
            if config.response_delay > 0:
                remaining = config.response_delay
                while remaining > 0:
                    time.sleep(min(4, remaining))
                    remaining -= 4
                    if remaining > 0 and will_respond:
                        _send_typing()

            # Last-message-wins: if a newer message arrived while sleeping, exit —
            # that request will collect and respond to the whole batch.
            latest_received = LeadActivity.objects.filter(
                lead=lead,
                activity_type=LeadActivity.TYPE_INSTAGRAM_RECEIVED,
            ).order_by('-created_at').first()
            if latest_received and latest_received.id != current_activity.id:
                logger.info(
                    f"Lead {lead.id}: skipping response, newer Instagram message "
                    f"#{latest_received.id} will respond to the batch"
                )
                return

        # Collect all messages since last AI reply and combine them so that
        # several short messages sent in quick succession are answered together.
        # Only CRM-sent messages (echo_origin='crm') define the pending window.
        # Native-app manager messages (echo_origin='instagram_app') appear in the
        # AI's conversation_history as context, but must NOT act as the boundary —
        # otherwise guest messages sent BEFORE the manager's reply would be silently
        # dropped from the next AI response's context.
        last_ai_sent = LeadActivity.objects.filter(
            lead=lead,
            activity_type=LeadActivity.TYPE_INSTAGRAM_SENT,
            echo_origin=LeadActivity.ECHO_ORIGIN_CRM,
        ).order_by('-created_at').first()
        pending_filter = {'lead': lead, 'activity_type': LeadActivity.TYPE_INSTAGRAM_RECEIVED}
        if last_ai_sent:
            pending_filter['created_at__gt'] = last_ai_sent.created_at
        pending_messages = list(
            LeadActivity.objects.filter(**pending_filter).order_by('created_at')
        )
        pending_text_messages = [
            m for m in pending_messages
            if not is_media_only_activity_metadata(m.metadata)
        ]
        if len(pending_text_messages) > 1:
            combined_text = '\n'.join(
                activity_text_for_ai(m.metadata) for m in pending_text_messages
                if m.metadata and activity_text_for_ai(m.metadata)
            ).strip() or text
            logger.info(f"Lead {lead.id}: pooled {len(pending_text_messages)} Instagram messages into one response")
        else:
            combined_text = text

        # Exclude pending (pooled) messages from history — already in combined_text.
        pending_ids = {m.id for m in pending_messages}

        # Classify intent to gate AI responses.
        # Only freeze the tier when it is already booking_intent — this protects against
        # mid-conversation short replies ("Да", "Первый") downgrading an active booking lead.
        # If the current tier is non-booking (or unset), re-classify with combined_text so
        # a lead whose first message was a greeting can still get a response once they ask
        # about booking.
        if not force_response:
            if lead.instagram_intent_tier == Lead.INTENT_TIER_BOOKING:
                tier = lead.instagram_intent_tier
                logger.info(f"Lead {lead.id}: using existing booking tier (no re-classification)")
            else:
                tier = ai_service.classify_instagram_intent(combined_text)
                Lead.objects.filter(id=lead_id).update(instagram_intent_tier=tier)
                lead.refresh_from_db()
                logger.info(f"Lead {lead.id}: classified Instagram intent as '{tier}'")

            # Only respond to booking-intent messages.
            if tier != Lead.INTENT_TIER_BOOKING:
                # We no longer return early to allow responding to greetings and soft interest
                logger.info(f"Lead {lead.id}: proceeding with AI response despite tier={tier}")

        if not will_respond:
            return

        # Full activity history (all types, no cap) for complete context.
        from .ai_service import build_activity_history
        activity_history = build_activity_history(lead, exclude_ids=pending_ids)

        # Role-based conversation turns for dialogue structure (Instagram only).
        conversation_history = []
        manager_message_count = 0
        instagram_activities = filter_activities_since_last_ai_reset(
            LeadActivity.objects.filter(
                lead=lead,
                activity_type__in=[LeadActivity.TYPE_INSTAGRAM_RECEIVED, LeadActivity.TYPE_INSTAGRAM_SENT]
            ),
            lead,
        ).order_by('created_at').only('id', 'activity_type', 'metadata', 'description')

        for activity in instagram_activities:
            if activity.id in pending_ids:
                continue  # Already in combined_text — don't duplicate in history
            meta = activity.metadata or {}
            if is_media_only_activity_metadata(meta):
                continue
            msg_text = activity_text_for_ai(meta, activity.description)
            if activity.activity_type == LeadActivity.TYPE_INSTAGRAM_RECEIVED:
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

        # Refresh typing before AI call — generation takes a few seconds
        _send_typing()

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
        ai_response = agent_dispatcher.dispatch(
            lead, combined_text, lead_data, conversation_history,
            is_pooled=len(pending_text_messages) > 1,
            activity_history=activity_history,
        )

        # Strip markdown — Instagram DMs render plain text only
        if ai_response:
            ai_response = re.sub(r'!\[.*?\]\(.*?\)', '', ai_response)       # ![img](url) → remove
            ai_response = re.sub(r'\[([^\]]+)\]\((https?://[^\)]+)\)', r'\2', ai_response)  # [text](url) → url
            ai_response = re.sub(r'\*\*(.*?)\*\*', r'\1', ai_response)      # **bold**
            ai_response = re.sub(r'\*(.*?)\*', r'\1', ai_response)          # *italic*
            ai_response = re.sub(r'__(.*?)__', r'\1', ai_response)          # __underline__
            ai_response = re.sub(r'_(.*?)_', r'\1', ai_response)            # _italic_
            ai_response = re.sub(r'`(.*?)`', r'\1', ai_response)            # `code`
            ai_response = ai_response.strip()

        if ai_response:
            # Final race-condition guard: re-read ai_paused from DB.
            # A manager could have sent from the native Instagram app during the pool window
            # or AI generation time, setting ai_paused=True after the initial check passed.
            if not force_response and Lead.objects.filter(id=lead_id, ai_paused=True).exists():
                logger.info(
                    f"Lead {lead_id}: AI response suppressed — ai_paused was set during generation "
                    f"(manager took over mid-flight)"
                )
                return

            # Concurrent-send guard: if another thread already responded while we were
            # generating (e.g., response_delay=0 or very short window lets two threads
            # race past the latest_received check), abort to avoid duplicate responses.
            if not force_response and pending_messages:
                last_pending_time = pending_messages[-1].created_at
                already_responded = LeadActivity.objects.filter(
                    lead=lead,
                    activity_type=LeadActivity.TYPE_INSTAGRAM_SENT,
                    echo_origin=LeadActivity.ECHO_ORIGIN_CRM,
                    created_at__gt=last_pending_time,
                ).exists()
                if already_responded:
                    logger.info(
                        f"Lead {lead_id}: concurrent-send guard — another thread already "
                        f"responded after our pending messages; suppressing duplicate"
                    )
                    return

            # Send each sentence as a separate message with a typing burst between
            message_parts = _split_into_messages(ai_response)
            last_activity_id = None
            for i, part in enumerate(message_parts):
                if i > 0:
                    _send_typing()
                result = instagram_service.send_message(sender_id, part)
                if result:
                    part_mid = result.get('message_id')
                    if part_mid:
                        # Log each sent message part immediately to prevent webhook echoes
                        # from falsely triggering a manual takeover/AI pause.
                        sent_activity = LeadActivity.objects.create(
                            lead=lead,
                            organization=lead.organization,
                            activity_type=LeadActivity.TYPE_INSTAGRAM_SENT,
                            description=f"AI auto-response: {part[:100]}{'...' if len(part) > 100 else ''}",
                            echo_origin=LeadActivity.ECHO_ORIGIN_CRM,
                            metadata={
                                'message_id': part_mid,
                                'all_message_ids': [part_mid],
                                'text': part,
                                'is_ai_generated': True,
                                'echo_origin': LeadActivity.ECHO_ORIGIN_CRM,
                            }
                        )
                        last_activity_id = sent_activity.id

            if last_activity_id:
                logger.info(f"Sent AI auto-response to lead {lead.id} via Instagram ({len(message_parts)} message(s))")
                agent_service.schedule_idle_or_promise_followup(lead, combined_text, conversation_history, last_activity_id)

        # Regenerate conversation summary in lead.notes after each exchange
        try:
            summary = ai_service.generate_conversation_summary(lead)
            if summary:
                Lead.objects.filter(id=lead_id).update(notes=summary)
                logger.info(f"Updated conversation summary for lead {lead_id}: {summary[:60]}")
        except Exception as _se:
            logger.warning(f"Failed to update summary for lead {lead_id}: {_se}")

        # Auto-extract lead data from the full conversation
        if config.auto_extract_data:
            conversation_history_for_extract = []
            for activity in filter_activities_since_last_ai_reset(
                LeadActivity.objects.filter(
                    lead=lead,
                    activity_type__in=[LeadActivity.TYPE_INSTAGRAM_RECEIVED, LeadActivity.TYPE_INSTAGRAM_SENT]
                ),
                lead,
            ).order_by('created_at'):
                if is_media_only_activity_metadata(activity.metadata):
                    continue
                role = "user" if activity.activity_type == LeadActivity.TYPE_INSTAGRAM_RECEIVED else "assistant"
                msg_text = activity_text_for_ai(activity.metadata, activity.description)
                conversation_history_for_extract.append({"role": role, "content": msg_text})

            our_company_name = config.company_profile.split('\n')[0] if config.company_profile else None
            extracted_data = ai_service.extract_lead_data(combined_text, conversation_history_for_extract, our_company_name)
            if extracted_data:
                from apps.leads.services.stage_resolver import mark_name_confirmed_by_user

                updated_fields = []

                if extracted_data.get('contact_person'):
                    if lead.contact_person != extracted_data['contact_person']:
                        lead.contact_person = extracted_data['contact_person']
                        updated_fields.append('contact_person')
                    if mark_name_confirmed_by_user(lead):
                        updated_fields.append('agent_context')

                if extracted_data.get('phone'):
                    if lead.phone != extracted_data['phone']:
                        lead.phone = extracted_data['phone']
                        updated_fields.append('phone')

                if extracted_data.get('email'):
                    if not _is_fake_email(extracted_data['email']):
                        if lead.email != extracted_data['email']:
                            lead.email = extracted_data['email']
                            updated_fields.append('email')

                if extracted_data.get('check_in_date'):
                    if str(lead.check_in_date or '') != extracted_data['check_in_date']:
                        lead.check_in_date = extracted_data['check_in_date']
                        updated_fields.append('check_in_date')

                if extracted_data.get('check_out_date'):
                    if str(lead.check_out_date or '') != extracted_data['check_out_date']:
                        lead.check_out_date = extracted_data['check_out_date']
                        updated_fields.append('check_out_date')

                if extracted_data.get('guest_count'):
                    if lead.guest_count != int(extracted_data['guest_count']):
                        lead.guest_count = int(extracted_data['guest_count'])
                        updated_fields.append('guest_count')

                if extracted_data.get('room_type_preference'):
                    if lead.room_type_preference != extracted_data['room_type_preference']:
                        lead.room_type_preference = extracted_data['room_type_preference']
                        updated_fields.append('room_type_preference')

                if extracted_data.get('meal_plan'):
                    valid_meal_plans = {'none', 'breakfast', 'lunch', 'dinner', 'half_board_bl', 'half_board_bd', 'full_board'}
                    if extracted_data['meal_plan'] in valid_meal_plans:
                        if lead.meal_plan != extracted_data['meal_plan']:
                            lead.meal_plan = extracted_data['meal_plan']
                            updated_fields.append('meal_plan')

                if updated_fields:
                    lead.save(update_fields=updated_fields)
                    logger.info(f"Auto-extracted and updated fields for lead {lead.id}: {updated_fields}")

    except Exception as e:
        logger.error(f"Error in background Instagram AI response for lead {lead_id}: {e}", exc_info=True)
    finally:
        close_old_connections()


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])  # Instagram webhook needs public access
def instagram_webhook(request):
    """
    Webhook endpoint for receiving Instagram messages.

    GET: Webhook verification (Instagram sends challenge)
    POST: Incoming message handling
    """
    # Webhook verification (GET request)
    if request.method == 'GET':
        verify_token = request.GET.get('hub.verify_token', '')
        challenge = request.GET.get('hub.challenge', '')

        VERIFY_TOKEN = _get_verify_token()

        if verify_token == VERIFY_TOKEN:
            return Response(int(challenge), content_type='text/plain')
        else:
            return Response('Invalid verify token', status=http_status.HTTP_403_FORBIDDEN)

    # Incoming message handling (POST request)
    try:
        data = request.data

        entries = data.get('entry', [])
        if not entries:
            return Response({'ok': True})

        # Guard: verify there is an active Instagram connection before processing anything.
        # If the account has been disconnected, we must not create leads, activities, or
        # trigger the AI — even though Meta keeps sending webhooks until unsubscribed.
        active_conn = InstagramConnection.get_config()
        if not active_conn or not active_conn.access_token:
            logger.warning(
                "Instagram webhook received but no active connection — discarding payload silently"
            )
            return Response({'ok': True})

        for entry in entries:
            entry_account_id = entry.get('id')

            # entry.id is the Instagram Business Account ID — a different namespace from
            # instagram_user_id (app-scoped /me ID). Learn and store it on first sight so
            # we can detect genuine account mismatches on future reconnections.
            if entry_account_id:
                if not active_conn.instagram_business_account_id:
                    InstagramConnection.objects.filter(pk=active_conn.pk).update(
                        instagram_business_account_id=entry_account_id
                    )
                    active_conn.instagram_business_account_id = entry_account_id
                    logger.info(f"Stored Instagram Business Account ID: {entry_account_id}")
                elif entry_account_id != active_conn.instagram_business_account_id:
                    logger.warning(
                        f"Instagram webhook entry account {entry_account_id} does not match "
                        f"stored business account {active_conn.instagram_business_account_id} — discarding"
                    )
                    continue

            messaging_events = entry.get('messaging', [])
            for event in messaging_events:
                if 'read' in event or 'delivery' in event:
                    continue

                sender = event.get('sender', {})
                message = event.get('message', {})

                sender_id = sender.get('id')
                message_text = message.get('text', '')

                if not sender_id:
                    continue

                # Handle echo events — Meta reflects every sent DM back as a webhook.
                # Processing is delegated to a background thread (_handle_echo_event)
                # which waits 3 seconds before checking the DB.  That delay is critical:
                # Meta delivers echoes within milliseconds, but our LeadActivity is only
                # written AFTER send_message() returns — creating a race window where an
                # immediate DB lookup would find nothing and falsely trigger Manual mode.
                if message.get('is_echo'):
                    mid = message.get('mid')
                    recipient = event.get('recipient', {})
                    guest_user_id = recipient.get('id')
                    
                    _ig_org = getattr(active_conn, 'organization', None)
                    org_id = _ig_org.id if _ig_org else None
                    
                    if mid and guest_user_id:
                        threading.Thread(
                            target=_handle_echo_event,
                            args=(mid, message_text, guest_user_id, org_id),
                            daemon=True,
                        ).start()
                    continue

                # Extract attachments and download media for manager playback.
                # The AI receives only text/captions, never the media file.
                attachments = message.get('attachments', [])
                instagram_content_context = _extract_instagram_content_context(event, message, attachments)
                if instagram_content_context:
                    logger.info(
                        "Extracted Instagram content context: type=%s attachment=%s ids=%s urls=%s",
                        instagram_content_context.get('content_type'),
                        instagram_content_context.get('attachment_type'),
                        {
                            key: instagram_content_context.get(key)
                            for key in ('story_id', 'media_id', 'share_id', 'reel_id', 'post_id')
                            if instagram_content_context.get(key)
                        },
                        (instagram_content_context.get('urls') or [])[:3],
                    )
                media_type = None
                media_metadata = {}
                mid = message.get('mid')

                if attachments:
                    attachment_type = attachments[0].get('type', 'attachment')
                    media_type = {
                        'image': 'photo',
                        'video': 'video',
                        'audio': 'audio',
                        'file': 'document',
                    }.get(attachment_type)
                    if media_type:
                        if not message_text:
                            message_text = MEDIA_PLACEHOLDERS.get(media_type, '[Файл получен]')
                        payload = attachments[0].get('payload', {})
                        media_url = payload.get('url')
                        if media_url and mid:
                            try:
                                mid_clean = re.sub(r'[^a-zA-Z0-9_\-]', '_', mid)

                                # Download file
                                resp = requests.get(media_url, timeout=20)
                                if resp.ok:
                                    mime_type = resp.headers.get('Content-Type', '').split(';', 1)[0] or None
                                    default_ext = '.jpg' if media_type == 'photo' else '.mp4' if media_type == 'video' else '.mp3' if media_type == 'audio' else '.bin'
                                    extension = extension_from_filename(media_url, mime_type, default_ext)
                                    dest_path, file_url = incoming_media_path('ig', mid_clean, extension)
                                    with open(dest_path, 'wb') as f:
                                        f.write(resp.content)
                                    media_metadata = build_media_metadata(media_type, file_url, mime_type)
                                    logger.info(f"Downloaded guest {media_type} from Instagram: {media_metadata['file_url']}")
                            except Exception as e:
                                logger.error(f"Error downloading incoming Instagram media: {e}", exc_info=True)

                is_media_only = bool(media_type) and not (message.get('text') or '').strip()

                if not message_text:
                    if attachments:
                        attachment_type = attachments[0].get('type', 'attachment')
                        fallback_media_type = {
                            'image': 'photo',
                            'video': 'video',
                            'audio': 'audio',
                            'file': 'document',
                        }.get(attachment_type)
                        message_text = MEDIA_PLACEHOLDERS.get(fallback_media_type or '', f'[Получено: {attachment_type}]')
                    elif message.get('sticker_id'):
                        message_text = '[Стикер получен]'
                    else:
                        # Unsupported event type — skip silently
                        continue

                # Fetch sender's username once — reused for echo detection and lead creation
                conn = InstagramConnection.get_config()
                sender_username = None
                if conn and conn.access_token:
                    try:
                        user_response = requests.get(
                            f'https://graph.instagram.com/{INSTAGRAM_GRAPH_API_VERSION}/{sender_id}',
                            params={'fields': 'username', 'access_token': conn.access_token},
                            timeout=5,
                        )
                        if user_response.ok:
                            sender_username = user_response.json().get('username') or None
                            if sender_username:
                                logger.info(f"Fetched Instagram username: @{sender_username} for sender_id: {sender_id}")
                    except Exception as e:
                        logger.warning(f"Could not fetch Instagram username for {sender_id}: {e}")

                # Skip messages from our own connected Instagram account
                if conn and conn.instagram_username and sender_username == conn.instagram_username:
                    logger.info(f"Skipping message from our own account @{sender_username}")
                    continue

                # Determine org from the active Instagram connection
                _ig_org = getattr(active_conn, 'organization', None)
                _lead_filter = {'organization': _ig_org} if _ig_org else {}

                # Find or create lead by instagram_user_id — scoped to this org
                try:
                    lead = Lead.objects.get(instagram_user_id=sender_id, **_lead_filter)
                    # Backfill username/contact for existing leads created before the username-fetch fix
                    if sender_username and (not lead.contact_person or not lead.instagram_username):
                        update_fields = []
                        if not lead.contact_person:
                            lead.contact_person = f'@{sender_username}'
                            update_fields.append('contact_person')
                        if not lead.instagram_username:
                            lead.instagram_username = sender_username
                            update_fields.append('instagram_username')
                        if update_fields:
                            lead.save(update_fields=update_fields)
                            logger.info(f"Backfilled lead {lead.id} with username @{sender_username} (fields: {update_fields})")
                except Lead.DoesNotExist:
                    lead = Lead.objects.create(
                        instagram_user_id=sender_id,
                        instagram_username=sender_username or '',
                        contact_person=f'@{sender_username}' if sender_username else '',
                        source='Instagram',
                        status=Lead.STATUS_NEW,
                        organization=_ig_org,
                        custom_fields={},
                    )

                    username_info = f" (@{sender_username})" if sender_username else ""
                    LeadActivity.objects.create(
                        lead=lead,
                        organization=_ig_org,
                        activity_type='lead_created',
                        description=f'Lead auto-created from Instagram contact: {sender_id}{username_info}',
                    )
                    logger.info(f"Auto-created lead {lead.id} from Instagram user: {sender_id}{username_info}")

                # Deduplicate by message ID — Meta uses at-least-once delivery and may
                # send the same webhook event twice. Processing a duplicate triggers a
                # second AI response for the same message.
                mid = message.get('mid')
                if mid and LeadActivity.objects.filter(
                    lead=lead,
                    activity_type=LeadActivity.TYPE_INSTAGRAM_RECEIVED,
                    metadata__message_id=mid,
                ).exists():
                    logger.info(f"Duplicate webhook for mid={mid} (lead {lead.id}) — skipping")
                    continue

                # Create activity for the received message
                activity_metadata = {
                    'message': message_text,
                    'text': message_text,
                    'message_id': mid,
                    'sender_id': sender_id,
                }
                if instagram_content_context:
                    activity_metadata['instagram_context'] = instagram_content_context
                    if instagram_content_context.get('story_id'):
                        activity_metadata['instagram_story_id'] = instagram_content_context['story_id']
                    if instagram_content_context.get('media_id'):
                        activity_metadata['instagram_media_id'] = instagram_content_context['media_id']
                    if instagram_content_context.get('share_id'):
                        activity_metadata['instagram_share_id'] = instagram_content_context['share_id']
                    if instagram_content_context.get('reel_id'):
                        activity_metadata['instagram_reel_id'] = instagram_content_context['reel_id']
                    if instagram_content_context.get('post_id'):
                        activity_metadata['instagram_post_id'] = instagram_content_context['post_id']
                if media_metadata:
                    activity_metadata.update(media_metadata)

                if media_type:
                    desc_media = {
                        'photo': 'photo',
                        'video': 'video',
                        'audio': 'audio',
                        'document': 'file',
                    }.get(media_type, 'attachment')
                    description = f'Received {desc_media} from Instagram'
                else:
                    description = f'Received from Instagram: {message_text[:100]}{"..." if len(message_text) > 100 else ""}'

                current_activity = LeadActivity.objects.create(
                    lead=lead,
                    organization=lead.organization,
                    activity_type=LeadActivity.TYPE_INSTAGRAM_RECEIVED,
                    description=description,
                    metadata=activity_metadata
                )

                # Stamp last_contacted so the CRM reflects when the guest last wrote
                Lead.objects.filter(id=lead.id).update(last_contacted=date.today())

                logger.info(f"Received Instagram message from lead {lead.id}: {message_text[:50]}")

                if instagram_content_context:
                    try:
                        from apps.hotel_media.models import SocialContentItem
                        from apps.hotel_media.services import (
                            external_id_from_url,
                            upsert_social_content_from_instagram_payload,
                        )

                        external_id = (
                            instagram_content_context.get('story_id')
                            or instagram_content_context.get('media_id')
                            or instagram_content_context.get('share_id')
                            or instagram_content_context.get('reel_id')
                            or instagram_content_context.get('post_id')
                        )
                        primary_url = (
                            instagram_content_context.get('story_url')
                            or instagram_content_context.get('share_url')
                            or instagram_content_context.get('media_url')
                            or instagram_content_context.get('permalink')
                            or next(iter(instagram_content_context.get('urls') or []), '')
                        )
                        existing_by_url = None
                        if primary_url and lead.organization:
                            existing_by_url = SocialContentItem.objects.filter(
                                organization=lead.organization,
                                platform=SocialContentItem.PLATFORM_INSTAGRAM,
                                is_active=True,
                            ).filter(
                                models.Q(media_url=primary_url)
                                | models.Q(thumbnail_url=primary_url)
                                | models.Q(permalink=primary_url)
                            ).first()
                        if not external_id and primary_url and not existing_by_url:
                            external_id = external_id_from_url(primary_url)
                        if external_id:
                            upsert_social_content_from_instagram_payload(
                                organization=lead.organization,
                                external_id=external_id,
                                content_type=instagram_content_context.get('content_type') or SocialContentItem.TYPE_UNKNOWN,
                                media_url=primary_url or '',
                                thumbnail_url=instagram_content_context.get('thumbnail_url') or '',
                                permalink=instagram_content_context.get('permalink') or '',
                                metadata=instagram_content_context,
                                source=SocialContentItem.SOURCE_WEBHOOK,
                            )
                    except Exception as exc:
                        logger.warning(f"Could not upsert Instagram social content context: {exc}")

                media_context = None
                if media_metadata or instagram_content_context:
                    try:
                        media_context = resolve_activity_media_context(current_activity)
                    except Exception as exc:
                        logger.warning(f"Could not resolve incoming Instagram media context: {exc}")

                ai_input_text = (
                    (current_activity.metadata or {}).get('ai_text')
                    if media_context
                    else message_text
                ) or message_text
                unresolved_media_prompt = ''
                if (media_metadata or instagram_content_context) and not media_context:
                    unresolved_media_prompt = build_unresolved_media_summary(current_activity.metadata)
                    ai_input_text = unresolved_media_prompt

                # Spawn background thread when AI is configured — classification runs
                # regardless of auto_response; the thread decides whether to reply.
                config = AIConfig.get_config(org=lead.organization)
                if ai_service.is_configured() and (not is_media_only or media_context or unresolved_media_prompt):
                    _delayed_instagram_ai_response.delay(
                        lead.id, current_activity.id, sender_id, ai_input_text
                    )
                elif is_media_only:
                    logger.info(f"Lead {lead.id}: skipping Instagram AI task — media-only message")

        return Response({'ok': True})

    except Exception as e:
        logger.error(f"Error processing Instagram webhook: {e}", exc_info=True)
        # Still return 200 to Instagram to avoid retries
        return Response({'ok': True})
