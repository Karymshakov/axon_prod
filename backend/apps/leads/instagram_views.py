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
from django.utils import timezone
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


def _split_into_messages(text: str, max_length: int = 950) -> list:
    """Keep a normal reply in one DM and split only when the channel limit requires it."""
    cleaned = (text or '').strip()
    if not cleaned:
        return []
    if len(cleaned) <= max_length:
        return [cleaned]

    chunks: list[str] = []
    current = ''
    for paragraph in re.split(r'\n{2,}', cleaned):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        candidates = [paragraph]
        if len(paragraph) > max_length:
            candidates = re.split(r'(?<=[.!?])\s+', paragraph)
        for candidate in candidates:
            candidate = candidate.strip()
            while len(candidate) > max_length:
                split_at = candidate.rfind(' ', 0, max_length + 1)
                if split_at < max_length // 2:
                    split_at = max_length
                piece, candidate = candidate[:split_at].strip(), candidate[split_at:].strip()
                if current:
                    chunks.append(current)
                    current = ''
                if piece:
                    chunks.append(piece)
            proposed = f'{current}\n\n{candidate}'.strip() if current else candidate
            if len(proposed) <= max_length:
                current = proposed
            else:
                chunks.append(current)
                current = candidate
    if current:
        chunks.append(current)
    return chunks


_INSTAGRAM_SOCIAL_ATTACHMENT_TYPES = {
    'share': 'post',
    'ig_post': 'post',
    'ig_reel': 'reel',
    'ig_story': 'story',
    'story_mention': 'story',
}
_INSTAGRAM_CONTEXT_ID_KEYS = {
    'media_id',
    'story_id',
    'share_id',
    'reel_id',
    'post_id',
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
        if attachment_type == 'story_mention':
            context['event_type'] = 'story_mention'

        id_values = _collect_nested_key_values(
            {'attachment': attachment, 'payload': payload},
            _INSTAGRAM_CONTEXT_ID_KEYS,
        )
        url_values = _collect_nested_urls({'attachment': attachment, 'payload': payload})
        for url in url_values:
            for url_id in _ids_from_instagram_url(url):
                _append_unique(id_values, url_id)
        if not id_values:
            # Generic nested `id` values may belong to the sender or webhook
            # attachment. Only a direct payload ID is safe as a final fallback.
            _append_unique(id_values, payload.get('id'))
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


def _instagram_event_type(message: dict, context: dict) -> str:
    if context.get('event_type') == 'story_mention':
        return 'story_mention'
    attachment_types = {
        str(item.get('type') or '').strip()
        for item in (message.get('attachments') or [])
        if isinstance(item, dict)
    }
    if 'story_mention' in attachment_types:
        return 'story_mention'
    if isinstance(message.get('reply_to'), dict) and message['reply_to'].get('story'):
        return 'story_reply'
    if context.get('content_type') in {'post', 'reel'}:
        return 'content_reply'
    return 'direct_message'


def _lead_language(lead, message_text: str = '') -> str:
    from apps.hotel_info.services.automation_templates import normalize_language

    configured = normalize_language(getattr(lead, 'language', ''), default='')
    if configured:
        return configured
    text = (message_text or '').lower()
    if any(char in text for char in 'ңөү'):
        return 'ky'
    if re.search(r'[а-яё]', text):
        return 'ru'
    if re.search(r'[a-z]', text):
        return 'en'
    return 'ru'


def _send_logged_instagram_message(lead, recipient_id: str, text: str, *, event_key: str) -> LeadActivity | None:
    if not text:
        return None
    result = instagram_service.send_message(recipient_id, text, org=lead.organization)
    if not result:
        return None
    message_id = result.get('message_id')
    return LeadActivity.objects.create(
        lead=lead,
        organization=lead.organization,
        activity_type=LeadActivity.TYPE_INSTAGRAM_SENT,
        description=f'Instagram automation ({event_key}): {text[:100]}',
        echo_origin=LeadActivity.ECHO_ORIGIN_CRM,
        metadata={
            'message_id': message_id,
            'all_message_ids': [message_id] if message_id else [],
            'text': text,
            'automation_event': event_key,
            'is_ai_generated': False,
            'echo_origin': LeadActivity.ECHO_ORIGIN_CRM,
        },
    )


def _normalize_campaign_trigger(value: str) -> str:
    return ' '.join(str(value or '').casefold().split())


def _instagram_entry_changes(entry: dict) -> list[dict]:
    """Normalize both webhook shapes used by Meta for field changes."""
    changes = [
        change
        for change in (entry.get('changes') or [])
        if isinstance(change, dict)
    ]
    if entry.get('field'):
        direct_change = {
            'field': entry.get('field'),
            'value': entry.get('value'),
        }
        if direct_change not in changes:
            changes.append(direct_change)
    return changes


def _instagram_connection_for_entry(entry_account_id: str | None) -> InstagramConnection | None:
    """Resolve a webhook to its workspace instead of using the first connection."""
    account_id = str(entry_account_id or '').strip()
    connections = InstagramConnection.objects.exclude(access_token='').select_related('organization')
    if account_id:
        exact = connections.filter(
            models.Q(instagram_business_account_id=account_id)
            | models.Q(instagram_user_id=account_id)
        ).first()
        if exact:
            return exact

    unbound = list(
        connections.filter(instagram_business_account_id='')
        .order_by('id')[:2]
    )
    if account_id and len(unbound) == 1:
        connection = unbound[0]
        InstagramConnection.objects.filter(pk=connection.pk).update(
            instagram_business_account_id=account_id,
        )
        connection.instagram_business_account_id = account_id
        logger.info('Stored Instagram Business Account ID: %s', account_id)
        return connection

    logger.warning(
        'Instagram webhook account %s could not be mapped to one workspace',
        account_id or '<missing>',
    )
    return None


def _process_instagram_comment_change(change: dict, organization_id: int) -> None:
    """Handle one comment webhook without creating a CRM lead."""
    from django.db import close_old_connections

    close_old_connections()
    try:
        if change.get('field') not in {'comments', 'live_comments'}:
            return
        value = change.get('value') if isinstance(change.get('value'), dict) else {}
        comment_id = str(value.get('id') or value.get('comment_id') or '').strip()
        media = value.get('media') if isinstance(value.get('media'), dict) else {}
        media_id = str(media.get('id') or value.get('media_id') or '').strip()
        sender = value.get('from') if isinstance(value.get('from'), dict) else {}
        sender_id = str(sender.get('id') or '').strip()
        comment_text = str(value.get('text') or '').strip()
        if not comment_id or not media_id:
            return

        from apps.hotel_media.models import SocialAutomationDelivery, SocialContentItem

        now = timezone.now()
        item = (
            SocialContentItem.objects.filter(
                organization_id=organization_id,
                platform=SocialContentItem.PLATFORM_INSTAGRAM,
                automation_enabled=True,
                is_active=True,
                status=SocialContentItem.STATUS_ACTIVE,
            )
            .filter(models.Q(external_id=media_id) | models.Q(parent_external_id=media_id))
            .order_by('-posted_at', '-id')
            .first()
        )
        if not item:
            return
        if item.automation_starts_at and item.automation_starts_at > now:
            return
        if item.automation_ends_at and item.automation_ends_at <= now:
            return

        normalized_comment = _normalize_campaign_trigger(comment_text)
        if item.automation_trigger == SocialContentItem.AUTOMATION_COMMENT_EXACT:
            allowed = {
                _normalize_campaign_trigger(value)
                for value in (item.automation_trigger_values or [])
                if _normalize_campaign_trigger(value)
            }
            if normalized_comment not in allowed:
                return
        elif item.automation_trigger != SocialContentItem.AUTOMATION_COMMENT_ANY:
            return

        from apps.hotel_info.services.automation_templates import detect_message_language

        language = detect_message_language(comment_text)
        reply_text = {
            'ky': item.automation_reply_ky,
            'en': item.automation_reply_en,
            'ru': item.automation_reply_ru,
        }.get(language) or item.automation_reply_ru or item.automation_reply_ky or item.automation_reply_en
        reply_text = (reply_text or '').strip()
        if not reply_text:
            return

        delivery, created = SocialAutomationDelivery.objects.get_or_create(
            organization_id=organization_id,
            external_event_id=comment_id,
            defaults={
                'social_content_item': item,
                'recipient_id': sender_id,
                'trigger_text': comment_text,
                'reply_text': reply_text,
            },
        )
        if not created:
            retry_claimed = SocialAutomationDelivery.objects.filter(
                id=delivery.id,
                status=SocialAutomationDelivery.STATUS_FAILED,
            ).update(
                status=SocialAutomationDelivery.STATUS_PENDING,
                error='',
                reply_text=reply_text,
                trigger_text=comment_text,
            )
            if not retry_claimed:
                logger.info('Instagram campaign comment %s already handled', comment_id)
                return
            delivery.refresh_from_db()

        result = instagram_service.send_private_reply_to_comment(
            comment_id,
            reply_text,
            org=item.organization,
        )
        if result:
            delivery.status = SocialAutomationDelivery.STATUS_SENT
            delivery.response_message_id = str(result.get('message_id') or '')
            delivery.recipient_id = str(result.get('recipient_id') or sender_id)
            delivery.save(update_fields=[
                'status', 'response_message_id', 'recipient_id', 'updated_at',
            ])
            logger.info(
                'Sent Instagram campaign private reply for content=%s comment=%s',
                item.id,
                comment_id,
            )
        else:
            delivery.status = SocialAutomationDelivery.STATUS_FAILED
            delivery.error = 'Meta API did not confirm private reply delivery'
            delivery.save(update_fields=['status', 'error', 'updated_at'])
    except Exception as exc:
        logger.error('Instagram comment automation failed: %s', exc, exc_info=True)
    finally:
        close_old_connections()


def _handle_echo_event(
    mid: str,
    echo_text: str,
    guest_user_id: str,
    org_id: int = None,
    received_at=None,
) -> None:
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
    from django.db.models import Q
    close_old_connections()

    try:
        # Wait before checking — lets the CRM activity creation win the race.
        received_at = received_at or timezone.now()
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
                            'echo_origin': LeadActivity.ECHO_ORIGIN_INSTAGRAM_APP,
                            'is_manager_manual': True,
                            'sent_by_name': 'Instagram',
                            'sent_by_initials': 'IG',
                        },
                    )
                    from datetime import datetime as _datetime
                    from zoneinfo import ZoneInfo as _ZoneInfo

                    Lead.objects.filter(id=echo_lead.id).update(
                        last_contacted=_datetime.now(_ZoneInfo('Asia/Bishkek')).date()
                    )

                resumed_after_echo = LeadActivity.objects.filter(
                    lead=echo_lead,
                    created_at__gte=received_at,
                    metadata__action__in=['ai_resumed', 'handback_to_ai'],
                ).exists()

                if has_crm_sent and not resumed_after_echo and not echo_lead.ai_paused:
                    Lead.objects.filter(id=echo_lead.id).update(
                        ai_paused=True,
                        ai_paused_at=timezone.now(),
                        ai_paused_by='Instagram app',
                    )
                    LeadActivity.objects.create(
                        lead=echo_lead,
                        organization=echo_lead.organization,
                        activity_type=LeadActivity.TYPE_LEAD_UPDATED,
                        description='Manager took over via Instagram app',
                        echo_origin=LeadActivity.ECHO_ORIGIN_INSTAGRAM_APP,
                        metadata={
                            'message_id': mid,
                            'action': 'ai_paused',
                            'user': 'Instagram app',
                        },
                    )
                    logger.info(f"Lead {echo_lead.id}: AI paused — manager sent via native Instagram app")
                elif resumed_after_echo:
                    logger.info(
                        'Lead %s: native Instagram echo logged without pausing AI '
                        'because control was returned after the echo arrived',
                        echo_lead.id,
                    )
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
        if lead.ai_paused and lead.ai_paused_by != 'AI Handoff' and not force_response:
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
            conn = InstagramConnection.get_config(lead.organization)
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

        # Classification and response both require AI to be configured.
        if not ai_service.is_configured():
            return

        will_respond = force_response or (
            config.ai_auto_response and instagram_service.is_configured(lead.organization)
        )

        def _send_typing():
            """Fire-and-forget typing indicator. Never raises."""
            try:
                instagram_service.send_typing_indicator(sender_id, org=lead.organization)
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

        # Semantic gate runs before sales status/goals/tasks. Social courtesy and FAQ
        # conversations remain visible in Communications but never enter the CRM funnel.
        if not force_response:
            if lead.is_sales_lead and lead.instagram_intent_tier == Lead.INTENT_TIER_BOOKING:
                conversation_kind = 'sales'
            else:
                recent_context_rows = list(
                    LeadActivity.objects.filter(
                        lead=lead,
                        activity_type__in=[
                            LeadActivity.TYPE_INSTAGRAM_RECEIVED,
                            LeadActivity.TYPE_INSTAGRAM_SENT,
                        ],
                    )
                    .exclude(id__in=pending_ids)
                    .order_by('-created_at')[:8]
                )
                recent_context_rows.reverse()
                conversation_context = '\n'.join(
                    (
                        'Guest: ' if row.activity_type == LeadActivity.TYPE_INSTAGRAM_RECEIVED
                        else 'Hotel: '
                    )
                    + (
                        activity_text_for_ai(row.metadata)
                        if row.metadata and activity_text_for_ai(row.metadata)
                        else row.description
                    )
                    for row in recent_context_rows
                )
                conversation_kind = ai_service.classify_social_conversation(
                    combined_text,
                    conversation_context=conversation_context,
                )
                if conversation_kind not in {'sales', 'faq', 'courtesy', 'service'}:
                    # Classification outages must not silently demote a known sales
                    # dialogue or promote an existing social-only interaction.
                    conversation_kind = (
                        'sales'
                        if lead.is_sales_lead
                        else lead.conversation_kind
                    )

            if conversation_kind == 'sales':
                Lead.objects.filter(id=lead_id).update(
                    is_sales_lead=True,
                    conversation_kind=Lead.CONVERSATION_SALES,
                    followup_allowed=True,
                    instagram_intent_tier=Lead.INTENT_TIER_BOOKING,
                )
                lead.refresh_from_db()
                logger.info('Conversation %s promoted to the sales funnel', lead.id)
            else:
                kind_map = {
                    'faq': Lead.CONVERSATION_FAQ,
                    'service': Lead.CONVERSATION_SERVICE,
                    'courtesy': Lead.CONVERSATION_COURTESY,
                }
                tier_map = {
                    'faq': Lead.INTENT_TIER_SOFT,
                    'service': Lead.INTENT_TIER_SOFT,
                    'courtesy': Lead.INTENT_TIER_NOT_RELEVANT,
                }
                Lead.objects.filter(id=lead_id).update(
                    is_sales_lead=False,
                    conversation_kind=kind_map.get(conversation_kind, Lead.CONVERSATION_COURTESY),
                    followup_allowed=False,
                    instagram_intent_tier=tier_map.get(conversation_kind, Lead.INTENT_TIER_NOT_RELEVANT),
                    next_follow_up_at=None,
                    next_follow_up_hint='',
                )
                lead.refresh_from_db()
                if not will_respond:
                    return

                language = _lead_language(lead, combined_text)
                event_key = ''
                if conversation_kind == 'service':
                    from apps.leads.services.booking_tools import execute_transfer_to_manager

                    transfer_result = execute_transfer_to_manager(
                        {
                            'reason': 'escalation',
                            'notes': combined_text[:1000],
                            'platform': 'instagram',
                        },
                        lead=lead,
                    )
                    if transfer_result.get('status') == 'success':
                        event_key = 'manager_handoff'
                elif (
                    conversation_kind == 'courtesy'
                    and lead.origin_event_type == 'story_mention'
                ):
                    event_key = 'story_courtesy_close'

                response_text = ''
                if event_key:
                    from apps.hotel_info.services.automation_templates import get_automation_message

                    response_text = get_automation_message(
                        event_key,
                        organization=lead.organization,
                        channel='instagram',
                        language=language,
                    )
                if not response_text:
                    response_text = ai_service.generate_non_sales_reply(
                        combined_text,
                        organization=lead.organization,
                        language=language,
                    )
                    event_key = event_key or f'non_sales_{conversation_kind}'
                if response_text:
                    _send_logged_instagram_message(
                        lead,
                        sender_id,
                        response_text,
                        event_key=event_key,
                    )
                logger.info(
                    'Lead %s handled as non-sales %s; no sales workflow or follow-up',
                    lead.id,
                    conversation_kind,
                )
                return

        if not will_respond:
            return

        # Sales state progression is intentionally after the semantic gate.
        if config.ai_auto_response:
            agent_service.process_incoming_message(lead, combined_text, channel='instagram')

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
            'adult_count': lead.adult_count,
            'children_ages': lead.children_ages,
            'infant_count': lead.infant_count,
            'one_room_required': lead.one_room_required,
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
            if not force_response and Lead.objects.filter(id=lead_id, ai_paused=True).exclude(ai_paused_by='AI Handoff').exists():
                logger.info(
                    f"Lead {lead_id}: AI response suppressed — ai_paused was set during generation "
                    f"(manager took over mid-flight)"
                )
                return

            # A newer guest message may arrive while the model is generating.
            # The newer webhook owns the combined reply; sending this result would
            # answer stale context and is the main source of repeated questions.
            if not force_response and pending_messages:
                latest_received_now = LeadActivity.objects.filter(
                    lead=lead,
                    activity_type=LeadActivity.TYPE_INSTAGRAM_RECEIVED,
                ).order_by('-created_at', '-id').first()
                if latest_received_now and latest_received_now.id not in pending_ids:
                    logger.info(
                        "Lead %s: stale-generation guard — Instagram message #%s arrived "
                        "after the pending batch; suppressing the older response",
                        lead_id,
                        latest_received_now.id,
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

            # Keep short, structured replies together. Split only for channel limits.
            message_parts = _split_into_messages(ai_response)
            last_activity_id = None
            for i, part in enumerate(message_parts):
                if i > 0:
                    _send_typing()
                result = instagram_service.send_message(sender_id, part, org=lead.organization)
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
            extracted_data = ai_service.extract_lead_data(combined_text, conversation_history_for_extract, our_company_name, lead.organization)
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
                from apps.leads.services.guest_structure import apply_extracted_guest_structure

                structured_fields = apply_extracted_guest_structure(lead, extracted_data)
                if structured_fields:
                    logger.info(
                        'Updated structured guest composition for lead %s: %s',
                        lead.id,
                        structured_fields,
                    )

        # Mark handoff as completed so subsequent messages from the guest are ignored.
        if Lead.objects.filter(id=lead_id, ai_paused=True, ai_paused_by='AI Handoff').exists():
            Lead.objects.filter(id=lead_id).update(ai_paused_by='AI Handoff Completed')
            logger.info(f"Lead {lead_id}: AI Handoff marked as Completed")

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
        if not InstagramConnection.objects.exclude(access_token='').exists():
            logger.warning(
                "Instagram webhook received but no active connection — discarding payload silently"
            )
            return Response({'ok': True})

        for entry in entries:
            entry_account_id = entry.get('id')
            active_conn = _instagram_connection_for_entry(entry_account_id)
            if not active_conn:
                continue

            organization = getattr(active_conn, 'organization', None)
            if organization:
                for change in _instagram_entry_changes(entry):
                    threading.Thread(
                        target=_process_instagram_comment_change,
                        args=(change, organization.id),
                        daemon=True,
                    ).start()

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
                            args=(mid, message_text, guest_user_id, org_id, timezone.now()),
                            daemon=True,
                        ).start()
                    continue

                # Extract attachments and download media for manager playback.
                # The AI receives only text/captions, never the media file.
                attachments = message.get('attachments', [])
                instagram_content_context = _extract_instagram_content_context(event, message, attachments)
                instagram_event_type = _instagram_event_type(message, instagram_content_context)
                is_story_mention_event = instagram_event_type == 'story_mention'
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
                conn = active_conn
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
                        is_sales_lead=not is_story_mention_event,
                        conversation_kind=(
                            Lead.CONVERSATION_COURTESY
                            if is_story_mention_event
                            else Lead.CONVERSATION_SALES
                        ),
                        origin_event_type=instagram_event_type,
                        followup_allowed=not is_story_mention_event,
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

                has_booking_context = bool(
                    lead.instagram_intent_tier == Lead.INTENT_TIER_BOOKING
                    or lead.check_in_date
                    or lead.check_out_date
                    or lead.guest_count
                )
                if is_story_mention_event and not has_booking_context:
                    Lead.objects.filter(id=lead.id).update(
                        is_sales_lead=False,
                        conversation_kind=Lead.CONVERSATION_COURTESY,
                        origin_event_type='story_mention',
                        followup_allowed=False,
                        next_follow_up_at=None,
                        next_follow_up_hint='',
                    )
                    lead.refresh_from_db()

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
                    'instagram_event_type': instagram_event_type,
                }

                # A guest swipe-replying to an earlier text message (not a story/post
                # share) carries reply_to.mid pointing at that message's mid. Look up
                # the original activity so the CRM can render a Telegram-style quote.
                reply_to_raw = message.get('reply_to') if isinstance(message.get('reply_to'), dict) else {}
                reply_mid = reply_to_raw.get('mid')
                if reply_mid and not reply_to_raw.get('story'):
                    original_activity = LeadActivity.objects.filter(
                        lead=lead,
                        activity_type__in=[
                            LeadActivity.TYPE_INSTAGRAM_SENT,
                            LeadActivity.TYPE_INSTAGRAM_RECEIVED,
                        ],
                        metadata__message_id=reply_mid,
                    ).order_by('-created_at').first()
                    if original_activity:
                        original_meta = original_activity.metadata or {}
                        is_from_business = original_activity.activity_type == LeadActivity.TYPE_INSTAGRAM_SENT
                        original_text = (
                            original_meta.get('text')
                            or original_meta.get('message')
                            or original_activity.description
                            or '[Сообщение]'
                        )
                        activity_metadata['reply_to'] = {
                            'message_id': reply_mid,
                            'text': original_text,
                            'sender_name': '' if is_from_business else (lead.contact_person or 'Гость'),
                            'from_bot': is_from_business,
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
                from datetime import datetime
                from zoneinfo import ZoneInfo

                Lead.objects.filter(id=lead.id).update(
                    last_contacted=datetime.now(ZoneInfo('Asia/Bishkek')).date()
                )

                logger.info(f"Received Instagram message from lead {lead.id}: {message_text[:50]}")

                if is_story_mention_event:
                    from apps.hotel_info.services.automation_templates import get_automation_message

                    acknowledgement = get_automation_message(
                        'story_mention_ack',
                        organization=lead.organization,
                        channel='instagram',
                        language=_lead_language(lead, message_text),
                    )
                    if acknowledgement:
                        _send_logged_instagram_message(
                            lead,
                            sender_id,
                            acknowledgement,
                            event_key='story_mention_ack',
                        )
                    logger.info(
                        'Lead %s: story mention acknowledged without sales workflow',
                        lead.id,
                    )

                # Incoming stories, mentions and shared posts belong to the guest
                # conversation. They may be matched against already-synced hotel
                # content below, but must never create records in the hotel's
                # Social Content library.

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
                    unresolved_metadata = dict(current_activity.metadata or {})
                    unresolved_metadata['visual_summary'] = unresolved_media_prompt
                    unresolved_metadata['ai_text'] = unresolved_media_prompt
                    unresolved_metadata['media_context_unresolved'] = True
                    current_activity.metadata = unresolved_metadata
                    current_activity.save(update_fields=['metadata'])

                # Spawn background thread when AI is configured — classification runs
                # regardless of auto_response; the thread decides whether to reply.
                config = AIConfig.get_config(org=lead.organization)
                if is_story_mention_event:
                    logger.info(
                        'Lead %s: skipping AI task for story mention event',
                        lead.id,
                    )
                elif ai_service.is_configured() and (not is_media_only or media_context or unresolved_media_prompt):
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
