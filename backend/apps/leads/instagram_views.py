import os
import re
import logging
import time
import threading
import requests
from datetime import date
from .instagram_integration_views import _get_app_config
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
        if len(pending_messages) > 1:
            combined_text = '\n'.join(
                m.metadata.get('text', '') for m in pending_messages
                if m.metadata and m.metadata.get('text')
            ).strip() or text
            logger.info(f"Lead {lead.id}: pooled {len(pending_messages)} Instagram messages into one response")
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
            msg_text = meta.get('text', '') or activity.description or ''
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
            is_pooled=len(pending_messages) > 1,
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
            all_message_ids = []  # Collect every part's message_id for echo detection
            last_result = None
            for i, part in enumerate(message_parts):
                if i > 0:
                    _send_typing()
                result = instagram_service.send_message(sender_id, part)
                if result:
                    last_result = result
                    part_mid = result.get('message_id')
                    if part_mid:
                        all_message_ids.append(part_mid)

            if last_result:
                sent_activity = LeadActivity.objects.create(
                    lead=lead,
                    organization=lead.organization,
                    activity_type=LeadActivity.TYPE_INSTAGRAM_SENT,
                    description=f"AI auto-response: {ai_response[:100]}{'...' if len(ai_response) > 100 else ''}",
                    echo_origin=LeadActivity.ECHO_ORIGIN_CRM,
                    metadata={
                        'message_id': last_result.get('message_id'),
                        # Store every part's ID so echo detection can identify any
                        # of the sent parts, not just the last one.
                        'all_message_ids': all_message_ids,
                        'text': ai_response,
                        'is_ai_generated': True,
                        'echo_origin': LeadActivity.ECHO_ORIGIN_CRM,
                    }
                )
                logger.info(f"Sent AI auto-response to lead {lead.id} via Instagram ({len(message_parts)} message(s))")

                if config.proactive_outreach_enabled and agent_service._has_promise_keywords(combined_text):
                    import threading
                    _conv_summary = '\n'.join(
                        m.get('content', '')[:200] for m in conversation_history[-4:]
                    ) if conversation_history else combined_text[:300]
                    threading.Thread(
                        target=agent_service._schedule_next_followup,
                        args=(lead.id, _conv_summary, sent_activity.id),
                        daemon=True,
                    ).start()
                elif config.proactive_outreach_enabled:
                    logger.info(
                        f"Lead {lead.id}: skipped generic proactive follow-up scheduling in reactive Instagram chat"
                    )

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
                role = "user" if activity.activity_type == LeadActivity.TYPE_INSTAGRAM_RECEIVED else "assistant"
                msg_text = activity.metadata.get('text', '') if activity.metadata else activity.description
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
                    lead.save()
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

                # Determine a human-readable label for non-text messages
                if not message_text:
                    attachments = message.get('attachments', [])
                    if attachments:
                        attachment_type = attachments[0].get('type', 'attachment')
                        message_text = f'[{attachment_type.capitalize()} received]'
                    elif message.get('sticker_id'):
                        message_text = '[Sticker received]'
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
                current_activity = LeadActivity.objects.create(
                    lead=lead,
                    organization=lead.organization,
                    activity_type=LeadActivity.TYPE_INSTAGRAM_RECEIVED,
                    description=f'Received from Instagram: {message_text[:100]}{"..." if len(message_text) > 100 else ""}',
                    metadata={
                        'message': message_text,
                        'text': message_text,
                        'message_id': mid,
                        'sender_id': sender_id,
                    }
                )

                # Stamp last_contacted so the CRM reflects when the guest last wrote
                Lead.objects.filter(id=lead.id).update(last_contacted=date.today())

                logger.info(f"Received Instagram message from lead {lead.id}: {message_text[:50]}")

                # Spawn background thread when AI is configured — classification runs
                # regardless of auto_response; the thread decides whether to reply.
                config = AIConfig.get_config(org=lead.organization)
                if ai_service.is_configured():
                    _delayed_instagram_ai_response.delay(
                        lead.id, current_activity.id, sender_id, message_text
                    )

        return Response({'ok': True})

    except Exception as e:
        logger.error(f"Error processing Instagram webhook: {e}", exc_info=True)
        # Still return 200 to Instagram to avoid retries
        return Response({'ok': True})
