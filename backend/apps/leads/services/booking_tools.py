import re
import json
import logging
import os
from datetime import datetime, date, timedelta
from html import escape
from zoneinfo import ZoneInfo
from django.conf import settings

logger = logging.getLogger(__name__)

def _org_from_lead(lead):
    return getattr(lead, 'organization', None) if lead is not None else None


def _is_past_date(date_str: str) -> bool:
    if not date_str:
        return False
    try:
        ci = date.fromisoformat(date_str)
        today_bishkek = datetime.now(ZoneInfo('Asia/Bishkek')).date()
        return ci < today_bishkek
    except (ValueError, TypeError):
        return False


def _pricing_signature(group: dict | None) -> tuple:
    if not group:
        return ()
    signature = []
    for combo in group.get('combinations') or []:
        prices = tuple(sorted(
            (str(key), str(value))
            for key, value in (combo.get('prices') or {}).items()
        ))
        signature.append((
            tuple(str(room) for room in (combo.get('rooms') or [])),
            str(combo.get('type') or ''),
            bool(combo.get('available')),
            prices,
        ))
    return tuple(sorted(signature, key=repr))


def _validated_pricing_group(
    generate_room_combinations,
    *,
    guest_count: int,
    checkin_date: str,
    checkout_date: str,
    org,
) -> tuple[list, dict | None, int | None, dict | None]:
    """Require one consistent, configured tariff for every night of the stay."""
    try:
        checkin = date.fromisoformat(checkin_date)
        checkout = date.fromisoformat(checkout_date)
    except (TypeError, ValueError):
        return [], None, None, {
            'error': 'invalid_dates',
            'message': 'Даты должны быть переданы в формате YYYY-MM-DD.',
        }

    total_nights = (checkout - checkin).days
    if total_nights <= 0:
        return [], None, None, {
            'error': 'invalid_stay_dates',
            'message': 'Дата выезда должна быть позже даты заезда.',
        }
    if total_nights > 60:
        return [], None, total_nights, {
            'error': 'pricing_unavailable',
            'message': 'Для проживания дольше 60 ночей стоимость должен подтвердить менеджер.',
        }

    first_groups = []
    first_group = None
    first_signature = None
    for offset in range(total_nights):
        night = checkin + timedelta(days=offset)
        groups = generate_room_combinations(target_date=night.isoformat(), org=org)
        group = next((item for item in groups if item['guest_count'] == guest_count), None)
        if not group or not any(
            combo.get('available') for combo in group.get('combinations', [])
        ):
            return [], None, total_nights, {
                'error': 'pricing_unavailable',
                'message': (
                    f'Нет подтверждённого тарифа на ночь {night.isoformat()}. '
                    'Не называйте цену из другой даты.'
                ),
            }
        signature = _pricing_signature(group)
        if first_signature is None:
            first_groups = groups
            first_group = group
            first_signature = signature
        elif signature != first_signature:
            return [], None, total_nights, {
                'error': 'pricing_unavailable',
                'message': (
                    'Во время выбранного проживания меняется тариф. '
                    'Итоговую стоимость должен подтвердить менеджер.'
                ),
            }

    return first_groups, first_group, total_nights, None


_TOOL_PARAMS = {
    'get_room_options': {
        "type": "object",
        "properties": {
            "guest_count": {
                "type": "integer",
                "description": "Total people in the party, including children.",
            },
            "adult_count": {
                "type": "integer",
                "description": "Number of adults when children are present.",
            },
            "children_ages": {
                "type": "array",
                "items": {"type": "number", "minimum": 0, "maximum": 17},
                "description": "Ages of all children in years; use a decimal for an infant.",
            },
            "one_room_required": {
                "type": "boolean",
                "description": "True only when the guest explicitly requires everyone to stay in one room.",
            },
            "checkin_date": {
                "type": "string",
                "description": "Check-in date in YYYY-MM-DD format. Use the current date/year from the system context when the guest does not specify a year; never assume a hard-coded or stale year.",
            },
            "checkout_date": {
                "type": "string",
                "description": "Check-out date in YYYY-MM-DD format. Use the current date/year from the system context when the guest does not specify a year; never assume a hard-coded or stale year.",
            },
        },
        "required": ["guest_count", "checkin_date", "checkout_date"],
    },
    'get_room_images': {
        "type": "object",
        "properties": {
            "categories": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": ["standard_queen", "standard_twin", "comfort", "cafeteria", "pool", "spa", "exterior", "lobby", "conference"],
                },
                "description": (
                    "Room or hotel area categories to fetch photos for. "
                    "Choose from the configured media categories and conversation context. "
                    "Room categories: standard_queen, standard_twin, comfort. "
                    "Hotel area categories: cafeteria, pool, spa, exterior, lobby, conference. "
                    "Use multiple categories when guest asks to see several areas."
                ),
            },
        },
        "required": ["categories"],
    },
    'get_family_room': {
        "type": "object",
        "properties": {
            "guest_count": {
                "type": "integer",
                "description": "Number of adult guests. Do not count children under 6.",
            },
            "children_ages": {
                "type": "array",
                "items": {"type": "number", "minimum": 0, "maximum": 17},
                "description": (
                    "Ages of children in years. Use a decimal for an infant under one year "
                    "(for example, 2 months = 0.17)."
                ),
            },
            "single_room_required": {
                "type": "boolean",
                "description": (
                    "True when the family explicitly says they must stay together in one room. "
                    "Never offer a multi-room combination when this is true."
                ),
            },
            "checkin_date": {
                "type": "string",
                "description": "Check-in date in YYYY-MM-DD format. Use the current date/year from the system context when the guest does not specify a year; never assume a hard-coded or stale year.",
            },
            "checkout_date": {
                "type": "string",
                "description": "Check-out date in YYYY-MM-DD format. Use the current date/year from the system context when the guest does not specify a year; never assume a hard-coded or stale year.",
            },
        },
        "required": ["guest_count", "checkin_date", "checkout_date"],
    },
    'get_meal_plan_pricing': {
        "type": "object",
        "properties": {
            "room_type": {
                "type": "string",
                "description": "Exact selected room type from get_room_options/get_family_room, usually room_type_key.",
            },
            "guest_count": {
                "type": "integer",
                "description": "Number of adult guests used for the selected room pricing.",
            },
            "checkin_date": {
                "type": "string",
                "description": "Check-in date in YYYY-MM-DD format.",
            },
        },
        "required": ["room_type", "guest_count"],
    },
    'transfer_to_manager': {
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "enum": ["booking_complete", "corporate_request", "sports_camp", "large_group", "complaint", "refund", "unknown_question", "escalation"],
                "description": "Why this lead is being transferred.",
            },
            "guest_name": {"type": "string"},
            "guest_phone": {"type": "string"},
            "guest_email": {"type": "string"},
            "checkin_date": {"type": "string"},
            "checkout_date": {"type": "string"},
            "guest_count": {"type": "integer"},
            "room_description": {"type": "string"},
            "meal_plan": {"type": "string"},
            "price_per_night": {"type": "number"},
            "total_price": {"type": "number"},
            "notes": {"type": "string"},
            "discovery_source": {"type": "string"},
            "discovery_source_detail": {"type": "string"},
            "platform": {
                "type": "string",
                "enum": ["telegram", "whatsapp", "instagram", "other"],
            },
        },
        "required": ["reason"],
    },
}

_FALLBACK_DESCRIPTIONS = {
    'get_room_images': (
        "Send photos of hotel rooms to the guest. "
        "Call this when a guest asks to see a room, asks what a room looks like, or requests photos. "
        "Infer the room category from context: 1-2 guests → standard_queen or standard_twin; "
        "3-4 guests or guest mentions 'комфорт'/'comfort' → comfort; "
        "family with confirmed children → family. "
        "Pass multiple categories when the guest asks to see all rooms. "
        "Photos are sent directly to the guest — compose a natural reply referencing them."
    ),
    'transfer_to_manager': (
        "Call this tool to notify the hotel manager about a completed or escalated lead.\n\n"
        "Call when ANY of these happen:\n"
        "1. Guest has confirmed room + meal plan + provided contacts → booking complete\n"
        "2. Guest is a legal entity (юрлицо), requests invoice or contract\n"
        "3. Corporate event, conference, teambuilding, banquet request\n"
        "4. Sports camp or group training request\n"
        "5. Complaint, conflict, or refund request\n"
        "6. get_room_options returns {\"error\": \"transfer_to_manager\"} for groups > 10 → "
        "YOU MUST CALL THIS TOOL IMMEDIATELY. Do not just tell the guest you are transferring — "
        "actually call this tool first, then tell the guest.\n"
        "7. Guest asks a question you cannot answer from the knowledge base\n\n"
        "IMPORTANT: Whenever you say \"I will transfer you to the manager\" or \"передам менеджеру\" "
        "or any equivalent phrase — you MUST call this tool in the same turn. Never say those words "
        "without calling the tool. Saying the words without calling the tool is not a transfer.\n\n"
        "This tool sends a Telegram notification to the manager with a structured summary.\n"
        "Always call this tool before or immediately after telling the guest the transfer is happening — "
        "never ask the guest to wait."
    ),
    'get_room_options': (
        "Use for every automated room search, including families. "
        "Pass total guest_count plus adult_count and children_ages when children are present. "
        "Young children who stay free without a separate bed must not cause an unnecessary "
        "extra room or family-room recommendation."
    ),
    'get_family_room': (
        "Family-room self-service is disabled. Do not call this tool during normal selection. "
        "If the guest explicitly requests a family room, route the request to a manager; "
        "never present it as an automatically bookable option."
    ),
    'get_meal_plan_pricing': (
        "Look up meal plan prices for a specific room type. "
        "Call this after room selection AND whenever the guest asks ANY question about "
        "food, meals, питание, dining, or что включено в стоимость. "
        "This is the ONLY authoritative source for meal pricing — never answer food questions from memory. "
        "Returns total_price_per_night for each meal plan — this is the COMPLETE all-in nightly rate "
        "(room + meals combined). It is NOT an add-on fee. Do NOT subtract the room base price. "
        "Quote total_price_per_night directly as the new rate: 'с полупансионом — 8 800 сом/ночь'. "
        "Never do arithmetic with the room price. Never present a delta. Just quote total_price_per_night."
    ),
}

def wants_separate_room_options(message: str) -> bool:
    text = (message or '').lower()
    if not text:
        return False
    return any(
        phrase in text
        for phrase in (
            'все отдельно', 'всё отдельно', 'отдельно лежали',
            'отдельно спали', 'отдельные кровати', 'раздельные кровати',
            'по отдельности', 'отедльности', 'каждому отдельно',
            'каждый отдельно', 'не вся моя семья', 'вместо жены мой друг',
            'друг и только один ребенок', 'друг и только один ребёнок',
        )
    )

def detect_family_context(lead) -> bool:
    """Return family context from fields extracted semantically by the model."""
    if lead is None:
        return False
    return bool(
        (getattr(lead, 'children_ages', None) or [])
        or int(getattr(lead, 'infant_count', 0) or 0) > 0
    )


_ROOM_IMAGE_CATEGORIES = {'standard_queen', 'standard_twin', 'comfort', 'family'}
_HOTEL_IMAGE_CATEGORIES = {'cafeteria', 'pool', 'spa', 'exterior', 'lobby', 'conference'}


def execute_get_room_images(args: dict, lead=None) -> dict:
    """Fetch room photos by category and send them to the guest via their channel."""
    from apps.hotel_media.models import HotelMediaItem

    categories = args.get('categories') or args.get('room_type') or args.get('category') or []
    if isinstance(categories, str):
        categories = [categories]

    ROOM_CATEGORY_LABELS = {
        'standard_queen': 'Standard Queen',
        'standard_twin': 'Standard Twin',
        'comfort': 'Comfort',
        'family': 'Family',
        'cafeteria': 'Café & Restaurant',
        'pool': 'Pool',
        'spa': 'Spa',
        'exterior': 'Exterior',
        'lobby': 'Lobby',
        'conference': 'Conference Hall',
    }

    # Room categories filter by CATEGORY_ROOMS + room_category field.
    # Hotel facility categories filter by their own category value (no room_category).
    _ROOM_CATS = {'standard_queen', 'standard_twin', 'comfort', 'family', 'other'}
    _HOTEL_CAT_MAP = {
        'cafeteria': HotelMediaItem.CATEGORY_CAFETERIA,
        'pool': HotelMediaItem.CATEGORY_POOL,
        'spa': HotelMediaItem.CATEGORY_SPA,
        'conference': HotelMediaItem.CATEGORY_CONFERENCE,
        'exterior': HotelMediaItem.CATEGORY_EXTERIOR,
        'lobby': HotelMediaItem.CATEGORY_LOBBY,
    }

    results = []
    missing_categories = []
    duplicate_categories = []
    channel = 'unknown'
    sent = False

    _org = getattr(lead, 'organization', None) if lead else None

    for cat in categories:
        if cat in _ROOM_CATS:
            _filter = dict(
                category=HotelMediaItem.CATEGORY_ROOMS,
                room_category=cat,
                is_active=True,
            )
        elif cat in _HOTEL_CAT_MAP:
            _filter = dict(
                category=_HOTEL_CAT_MAP[cat],
                is_active=True,
            )
        else:
            missing_categories.append(cat)
            continue
        if _org is not None:
            _filter['organization'] = _org
        items = HotelMediaItem.objects.filter(**_filter).prefetch_related('photos').order_by('-ai_send_count')

        # Collect up to 3 photos: prefer album photos, fall back to item.file
        photos_to_send = []
        for item in items:
            album = list(item.photos.all())
            if album:
                for photo in album:
                    if len(photos_to_send) >= 3:
                        break
                    photos_to_send.append((item, photo))
            elif item.file and len(photos_to_send) < 3:
                class _FileProxy:
                    def __init__(self, f):
                        self.file = f
                        self.id = None
                photos_to_send.append((item, _FileProxy(item.file)))
            if len(photos_to_send) >= 3:
                break

        if not photos_to_send:
            missing_categories.append(cat)
            continue

        photo_meta = []
        media_items_sent = {}
        for item, photo in photos_to_send:
            photo_meta.append({
                'url': photo.file.url if photo.file else '',
                'caption': item.title,
            })
            media_items_sent[item.id] = item

        action_claim = None
        if lead is not None:
            from apps.leads.models import LeadActivity, OutboundActionClaim

            source = (lead.source or '').lower()
            channel = source or 'unknown'
            received_type = {
                'telegram': LeadActivity.TYPE_TELEGRAM_RECEIVED,
                'instagram': LeadActivity.TYPE_INSTAGRAM_RECEIVED,
                'whatsapp': LeadActivity.TYPE_WHATSAPP_RECEIVED,
            }.get(source)
            latest_inbound_id = (
                LeadActivity.objects.filter(lead=lead, activity_type=received_type)
                .order_by('-created_at', '-id')
                .values_list('id', flat=True)
                .first()
                if received_type else None
            )
            claim_key = f'room_images:{lead.id}:{source}:{cat}:{latest_inbound_id or "no-inbound"}'
            action_claim, claim_created = OutboundActionClaim.objects.get_or_create(
                idempotency_key=claim_key,
                defaults={
                    'lead': lead,
                    'organization': lead.organization,
                    'channel': source,
                    'action_type': 'room_images',
                    'metadata': {'category': cat, 'inbound_activity_id': latest_inbound_id},
                },
            )
            if not claim_created and action_claim.status == action_claim.STATUS_FAILED:
                claim_created = bool(
                    OutboundActionClaim.objects.filter(
                        pk=action_claim.pk,
                        status=action_claim.STATUS_FAILED,
                    ).update(status=action_claim.STATUS_PENDING)
                )
            if not claim_created:
                duplicate_categories.append(cat)
                results.append({
                    'category': cat,
                    'title': ROOM_CATEGORY_LABELS.get(cat, cat),
                    'description': photos_to_send[0][0].description if photos_to_send else '',
                    'photos_sent': 0,
                    'already_sent_for_message': True,
                    'photos': [],
                })
                logger.info(
                    'get_room_images: duplicate tool side effect suppressed for lead=%s category=%s inbound=%s',
                    lead.id,
                    cat,
                    latest_inbound_id,
                )
                continue

        sent_mids = []
        if lead is not None:
            source = (lead.source or '').lower()
            chat_id = getattr(lead, 'telegram_chat_id', None)

            if source == 'telegram' and chat_id:
                channel = 'telegram'
                try:
                    import tempfile
                    from apps.leads.telegram_service import TelegramService
                    from apps.hotel_media.utils import compress_image_for_telegram
                    from asgiref.sync import async_to_sync

                    _PHOTO_MAX_BYTES = 8 * 1024 * 1024
                    file_paths = []
                    temp_paths = []
                    for _, photo in photos_to_send:
                        if photo.file:
                            raw_path = os.path.join(settings.MEDIA_ROOT, photo.file.name)
                            if os.path.getsize(raw_path) > _PHOTO_MAX_BYTES:
                                with open(raw_path, 'rb') as fh:
                                    cf = compress_image_for_telegram(fh, filename=os.path.basename(raw_path))
                                with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tf:
                                    tf.write(cf.read())
                                    file_paths.append(tf.name)
                                    temp_paths.append(tf.name)
                            else:
                                file_paths.append(raw_path)

                    if file_paths:
                        svc = TelegramService()
                        caption = ROOM_CATEGORY_LABELS.get(cat, cat)
                        if len(file_paths) == 1:
                            result = async_to_sync(svc.send_photo)(chat_id, file_paths[0], caption=caption)
                        else:
                            result = async_to_sync(svc.send_media_group)(chat_id, file_paths, caption=caption)
                        sent = result is not None

                    for tp in temp_paths:
                        try:
                            os.remove(tp)
                        except OSError:
                            pass
                except Exception as e:
                    logger.error(f"get_room_images: Telegram send failed for cat={cat}: {e}", exc_info=True)
            elif source == 'instagram' and getattr(lead, 'instagram_user_id', None):
                channel = 'instagram'
                try:
                    _domain = os.environ.get('APP_DOMAIN') or os.environ.get('API_DOMAIN', '')
                    _domain = _domain.strip().rstrip('/')
                    if not _domain.startswith('http'):
                        _domain = f'https://{_domain}'
                    from apps.leads.instagram_service import instagram_service as _ig_svc
                    _any_sent = False
                    for _, photo in photos_to_send:
                        if photo.file:
                            abs_url = f"{_domain}{photo.file.url}"
                            result = _ig_svc.send_image_url(
                                lead.instagram_user_id,
                                abs_url,
                                org=_org,
                            )
                            if result:
                                _any_sent = True
                                mid = result.get('message_id')
                                if mid:
                                    sent_mids.append(mid)
                    sent = _any_sent
                except Exception as e:
                    logger.error(f"get_room_images: Instagram send failed for cat={cat}: {e}", exc_info=True)
            else:
                channel = source or 'unknown'
                logger.warning(f"get_room_images: channel '{source}' photo sending not supported")

            if sent:
                from apps.leads.models import LeadActivity
                _ACTIVITY_TYPE_MAP = {
                    'telegram': LeadActivity.TYPE_TELEGRAM_SENT,
                    'instagram': LeadActivity.TYPE_INSTAGRAM_SENT,
                    'whatsapp': LeadActivity.TYPE_WHATSAPP_SENT,
                }
                _activity_type = _ACTIVITY_TYPE_MAP.get(channel, LeadActivity.TYPE_TELEGRAM_SENT)
                for item in media_items_sent.values():
                    HotelMediaItem.objects.filter(pk=item.pk).update(
                        ai_send_count=item.ai_send_count + 1
                    )
                label = ROOM_CATEGORY_LABELS.get(cat, cat)
                try:
                    activity_kwargs = {
                        'lead': lead,
                        'organization': lead.organization,
                        'activity_type': _activity_type,
                        'description': f"AI sent {len(photos_to_send)} photo(s) of {label} rooms",
                        'metadata': {
                            'is_ai_generated': True,
                            'room_category': cat,
                            'photos_sent': len(photos_to_send),
                        }
                    }
                    if channel == 'instagram':
                        activity_kwargs['echo_origin'] = LeadActivity.ECHO_ORIGIN_CRM
                        activity_kwargs['metadata']['echo_origin'] = LeadActivity.ECHO_ORIGIN_CRM
                        if sent_mids:
                            activity_kwargs['metadata']['message_id'] = sent_mids[-1]
                            activity_kwargs['metadata']['all_message_ids'] = sent_mids
                    
                    LeadActivity.objects.create(**activity_kwargs)
                except Exception as e:
                    logger.error(f"get_room_images: activity log failed: {e}")
                if action_claim is not None:
                    action_claim.status = action_claim.STATUS_SENT
                    action_claim.metadata = {
                        **(action_claim.metadata or {}),
                        'photos_sent': len(photos_to_send),
                        'message_ids': sent_mids,
                    }
                    action_claim.save(update_fields=['status', 'metadata', 'updated_at'])
            elif action_claim is not None:
                action_claim.status = action_claim.STATUS_FAILED
                action_claim.save(update_fields=['status', 'updated_at'])

        first_item = photos_to_send[0][0] if photos_to_send else None
        results.append({
            'category': cat,
            'title': ROOM_CATEGORY_LABELS.get(cat, cat),
            'description': first_item.description if first_item else '',
            'photos_sent': len(photos_to_send),
            'photos': photo_meta,
        })

    response = {
        'channel': channel if results else 'unknown',
        'sent': sent if results else False,
        'results': results,
        'missing_categories': missing_categories,
        'duplicate_categories': duplicate_categories,
    }
    if duplicate_categories and not any(item.get('photos_sent') for item in results):
        sent = True
        response['sent'] = True
        response['already_sent_for_message'] = True
        response['_note'] = (
            'These photos were already sent for the latest guest message. '
            'Do not send them again and do not repeat the photo-introduction text.'
        )
    if results and not sent:
        response['_note'] = (
            'Photos could NOT be delivered to this guest — photo sending is unavailable on this channel. '
            'Do NOT tell the guest photos were sent. '
            'Instead say: photos are not available right now and offer to answer questions about the rooms.'
        )
    return response


def _remember_room_offer(lead, tool_name: str, response: dict, *, remember: bool = True) -> None:
    if not remember or lead is None or not isinstance(response, dict):
        return
    combinations = response.get('combinations') or []
    if not combinations:
        return

    snapshot = {
        'tool': tool_name,
        'guest_count': response.get('guest_count'),
        'checkin_date': response.get('checkin_date'),
        'checkout_date': response.get('checkout_date'),
        'total_nights': response.get('total_nights'),
        'combinations': combinations[:6],
        'created_at': datetime.now(tz=ZoneInfo('UTC')).isoformat(),
    }
    try:
        ctx = dict(lead.agent_context or {})
        ctx['last_room_offer'] = snapshot
        lead.agent_context = ctx
        lead.save(update_fields=['agent_context'])
    except Exception as exc:
        logger.warning(
            "Could not remember room offer for lead=%s: %s",
            getattr(lead, 'pk', None),
            exc,
        )


def _format_discovery_source_for_manager(lead, args: dict) -> str:
    source = (
        args.get('discovery_source')
        or getattr(lead, 'discovery_source', '')
        or ''
    )
    detail = (
        args.get('discovery_source_detail')
        or getattr(lead, 'discovery_source_detail', '')
        or ''
    )
    source = str(source or '').strip()
    detail = str(detail or '').strip()
    if not source and not detail:
        return ''

    label = source
    try:
        from apps.leads.services.discovery_sources import get_discovery_source_options

        org = _org_from_lead(lead)
        for option in get_discovery_source_options(org):
            if option['value'] == source:
                label = option['label']
                break
    except Exception:
        pass

    if detail and detail.lower() != label.lower():
        return f'{label} — {detail}' if label else detail
    return label or detail


def _note_is_discovery_source(notes: str, discovery_display: str) -> bool:
    text = (notes or '').strip().lower()
    if not text or not discovery_display:
        return False
    discovery_lower = discovery_display.lower()
    discovery_markers = ('узнал', 'узнала', 'узнали', 'откуда', 'источник', 'learned', 'heard')
    if not any(marker in text for marker in discovery_markers):
        return False
    source_tokens = {
        token
        for token in re.findall(r'[a-zA-Z0-9а-яА-ЯёЁөүңкһі]+', discovery_lower)
        if len(token) >= 3
    }
    return bool(source_tokens and any(token in text for token in source_tokens))


def _escape_html(value) -> str:
    return escape(str(value or ''), quote=True)


def _html_link(label: str, url: str) -> str:
    label = _escape_html(label)
    url = _escape_html(url)
    return f'<a href="{url}">{label}</a>' if url else label


def _normalize_whatsapp_phone(phone: str) -> str:
    digits = re.sub(r'\D', '', phone or '')
    if not digits:
        return ''
    if digits.startswith('00'):
        digits = digits[2:]
    if digits.startswith('0') and len(digits) == 10:
        return f'996{digits[1:]}'
    if len(digits) == 9:
        return f'996{digits}'
    return digits


def _format_money(value) -> str:
    if value in (None, ''):
        return ''
    try:
        amount = float(value)
        if amount.is_integer():
            return f'{int(amount):,}'.replace(',', ' ')
        return f'{amount:,.2f}'.replace(',', ' ')
    except (TypeError, ValueError):
        return str(value)


def _build_telegram_manager_notification_html(template_vars: dict, *, cfg, platform_lower: str) -> str:
    reason = template_vars.get('reason') or 'New request'
    business_name = template_vars.get('business_name') or 'Hotel'
    guest_name = template_vars.get('guest_name') or 'Guest'
    guest_phone = template_vars.get('guest_phone_raw') or ''
    guest_email = template_vars.get('guest_email') or ''
    notes = template_vars.get('notes') or ''

    contact_links = []
    if template_vars.get('whatsapp_link'):
        contact_links.append(_html_link('WhatsApp', template_vars['whatsapp_link']))
    if template_vars.get('instagram_link'):
        label = template_vars.get('instagram_handle_raw') or 'Instagram'
        contact_links.append(_html_link(label, template_vars['instagram_link']))
    if template_vars.get('telegram_link'):
        label = template_vars.get('telegram_handle_raw') or 'Telegram'
        contact_links.append(_html_link(label, template_vars['telegram_link']))
    if template_vars.get('crm_link'):
        contact_links.append(_html_link('CRM', template_vars['crm_link']))

    channel_label = {
        'telegram': 'Telegram',
        'instagram': 'Instagram',
        'whatsapp': 'WhatsApp',
    }.get(platform_lower, template_vars.get('platform_name') or '')

    lines = [
        f'<b>New booking request</b> · {_escape_html(business_name)}',
        f'<b>Reason:</b> {_escape_html(reason)}',
        '',
        f'<b>Guest</b>',
        f'Name: {_escape_html(guest_name)}',
    ]

    if guest_phone:
        phone_line = f'Phone: {_escape_html(guest_phone)}'
        if template_vars.get('whatsapp_link'):
            phone_line += f' · {_html_link("WhatsApp", template_vars["whatsapp_link"])}'
        lines.append(phone_line)
    if guest_email:
        lines.append(f'Email: {_escape_html(guest_email)}')
    if channel_label:
        channel_line = f'Channel: {_escape_html(channel_label)}'
        primary_link = ''
        if platform_lower == 'instagram':
            primary_link = template_vars.get('instagram_link') or ''
        elif platform_lower == 'telegram':
            primary_link = template_vars.get('telegram_link') or ''
        elif platform_lower == 'whatsapp':
            primary_link = template_vars.get('whatsapp_link') or ''
        actions = []
        if primary_link:
            actions.append(_html_link('Open chat', primary_link))
        if template_vars.get('crm_link'):
            actions.append(_html_link('CRM', template_vars['crm_link']))
        if actions:
            channel_line += ' · ' + ' · '.join(actions)
        lines.append(channel_line)
    if template_vars.get('discovery_source'):
        lines.append(f'Heard from: {_escape_html(template_vars["discovery_source"])}')

    booking_lines = []
    if template_vars.get('checkin_date') or template_vars.get('checkout_date'):
        booking_lines.append(
            f'Dates: {_escape_html(template_vars.get("checkin_date"))} -> {_escape_html(template_vars.get("checkout_date"))}'
        )
    if template_vars.get('nights'):
        booking_lines.append(f'Nights: {_escape_html(template_vars["nights"])}')
    if template_vars.get('guest_count'):
        booking_lines.append(f'Guests: {_escape_html(template_vars["guest_count"])}')
    if template_vars.get('room_description'):
        booking_lines.append(f'Room: {_escape_html(template_vars["room_description"])}')
    if template_vars.get('meal_plan'):
        booking_lines.append(f'Meal plan: {_escape_html(template_vars["meal_plan"])}')
    if template_vars.get('price_per_night'):
        booking_lines.append(f'Per night: {_escape_html(_format_money(template_vars["price_per_night"]))} KGS')
    if template_vars.get('total_price'):
        booking_lines.append(f'<b>Total: {_escape_html(_format_money(template_vars["total_price"]))} KGS</b>')

    if booking_lines:
        lines.extend(['', '<b>Booking</b>'])
        lines.extend(booking_lines)

    if notes:
        lines.extend(['', f'<b>Notes</b>\n{_escape_html(notes)}'])

    if contact_links:
        unique_links = list(dict.fromkeys(contact_links))
        lines.extend(['', '<b>Actions:</b> ' + ' · '.join(unique_links)])

    return '\n'.join(lines)


def _adjust_tree_group(parsed_lines: list, indices: list):
    if not indices:
        return
    for idx in indices[:-1]:
        line = parsed_lines[idx]['rendered']
        # Replace the first occurrence of ├ or └ with ├
        parsed_lines[idx]['rendered'] = re.sub(r'([├└])', '├', line, count=1)
    # The last one gets └
    last_idx = indices[-1]
    line = parsed_lines[last_idx]['rendered']
    parsed_lines[last_idx]['rendered'] = re.sub(r'([├└])', '└', line, count=1)


def _render_custom_template(template: str, template_vars: dict) -> str:
    # 1. Parse lines
    lines = template.splitlines()
    parsed_lines = []
    
    # Regex to find placeholders like {guest_name}
    placeholder_pattern = re.compile(r'\{([a-zA-Z0-9_]+)\}')
    
    for line in lines:
        stripped = line.strip()
        placeholders = placeholder_pattern.findall(line)
        is_tree = bool(re.search(r'^\s*[├└│─]', line))
        is_blank = not stripped
        # Header is a line ending with ':' and having no placeholders
        is_header = stripped.endswith(':') and not placeholders
        
        parsed_lines.append({
            'original': line,
            'placeholders': placeholders,
            'is_tree': is_tree,
            'is_blank': is_blank,
            'is_header': is_header,
            'status': 'pending',
            'rendered': line,
        })
        
    # 2. First pass: evaluate placeholders and mark status
    class _SafeDict(dict):
        def __missing__(self, key):
            return ''
            
    safe_vars = _SafeDict(template_vars)
    
    for item in parsed_lines:
        if item['is_blank']:
            item['status'] = 'blank'
            item['rendered'] = ''
        elif item['placeholders']:
            # Replace placeholders
            try:
                rendered_line = item['original'].format_map(safe_vars)
            except Exception:
                rendered_line = item['original']
            # Check if all placeholders evaluated to empty/blank values
            all_empty = True
            for ph in item['placeholders']:
                val = safe_vars[ph]
                if val and str(val).strip():
                    all_empty = False
                    break
            if all_empty:
                item['status'] = 'discarded'
            else:
                item['status'] = 'kept'
                item['rendered'] = rendered_line
        else:
            if item['is_header']:
                item['status'] = 'header'
            else:
                item['status'] = 'kept'
                
    # 3. Second pass: resolve headers based on subsequent non-blank lines
    # A header is discarded if there are no kept lines before the next header or end of document.
    for i, item in enumerate(parsed_lines):
        if item['status'] == 'header':
            has_kept_children = False
            for j in range(i + 1, len(parsed_lines)):
                next_item = parsed_lines[j]
                if next_item['status'] == 'header':
                    break
                if next_item['status'] == 'kept':
                    has_kept_children = True
                    break
            if not has_kept_children:
                item['status'] = 'discarded'
            else:
                item['status'] = 'kept'
                
    # 4. Third pass: adjust tree prefixes for kept tree lines
    # We find contiguous groups of kept tree lines.
    in_tree_group = False
    tree_group_indices = []
    
    for i, item in enumerate(parsed_lines):
        if item['status'] == 'kept' and item['is_tree']:
            if not in_tree_group:
                in_tree_group = True
                tree_group_indices = [i]
            else:
                tree_group_indices.append(i)
        else:
            if in_tree_group:
                # Process the completed tree group
                _adjust_tree_group(parsed_lines, tree_group_indices)
                in_tree_group = False
                tree_group_indices = []
                
    if in_tree_group:
        _adjust_tree_group(parsed_lines, tree_group_indices)
        
    # 5. Assemble final output
    final_lines = []
    for item in parsed_lines:
        if item['status'] == 'kept':
            final_lines.append(item['rendered'])
        elif item['status'] == 'blank':
            final_lines.append('')
            
    # Collapse multiple consecutive blank lines and strip ends
    result_lines = []
    for line in final_lines:
        if not line.strip():
            if result_lines and result_lines[-1] != '':
                result_lines.append('')
        else:
            result_lines.append(line)
            
    while result_lines and not result_lines[0].strip():
        result_lines.pop(0)
    while result_lines and not result_lines[-1].strip():
        result_lines.pop()
        
    return '\n'.join(result_lines)


def execute_transfer_to_manager(args: dict, lead=None) -> dict:
    """Send a structured manager notification via Telegram or WhatsApp."""
    try:
        from apps.flows.models import ManagerTransferConfig
    except Exception as e:
        logger.error(f"Could not import ManagerTransferConfig: {e}")
        return {'status': 'error', 'message': 'Получатель не настроен. Настройте Transfer в AI Flows.'}

    try:
        cfg = ManagerTransferConfig.get_config(org=_org_from_lead(lead))
    except Exception as e:
        logger.error(f"Could not load ManagerTransferConfig: {e}")
        return {'status': 'error', 'message': 'Получатель не настроен. Настройте Transfer в AI Flows.'}

    if not cfg.recipient_id:
        return {'status': 'error', 'message': 'Получатель не настроен. Настройте Transfer в AI Flows.'}

    reason = args.get('reason', 'escalation')
    logger.info(f"transfer_to_manager called: reason={reason}, recipient={cfg.recipient_id}")

    REASON_LABELS = {
        'booking_complete':  '✅ Бронирование завершено',
        'corporate_request': '🏢 Корпоративный запрос',
        'sports_camp':       '🏊 Спортивный сбор',
        'large_group':       '👥 Большая группа (10+)',
        'complaint':         '⚠️ Жалоба / конфликт',
        'refund':            '💸 Возврат / отмена',
        'unknown_question':  '❓ Вопрос вне базы знаний',
        'escalation':        '🔺 Эскалация менеджеру',
    }

    reason_label = REASON_LABELS.get(reason, reason)

    nights = None
    checkin = args.get('checkin_date')
    checkout = args.get('checkout_date')
    if checkin and checkout:
        try:
            delta = (date.fromisoformat(checkout) - date.fromisoformat(checkin)).days
            if delta > 0:
                nights = delta
        except (ValueError, TypeError):
            pass

    guest_name = args.get('guest_name', '')
    try:
        from apps.leads.services.stage_resolver import is_reliable_contact_person

        if not is_reliable_contact_person(lead, guest_name):
            guest_name = ''
    except Exception:
        pass
    guest_phone = args.get('guest_phone', '')
    guest_email = args.get('guest_email', '')
    platform = args.get('platform', '')
    discovery_source_display = _format_discovery_source_for_manager(lead, args)
    notes = args.get('notes', '') or ''
    if _note_is_discovery_source(notes, discovery_source_display):
        notes = ''

    transfer_signature = None
    if lead is not None and reason == 'booking_complete':
        transfer_signature = {
            'reason': reason,
            'guest_name': guest_name or '',
            'guest_phone': guest_phone or '',
            'checkin_date': checkin or '',
            'checkout_date': checkout or '',
            'guest_count': str(args.get('guest_count', '') or ''),
            'room_description': args.get('room_description', '') or '',
            'meal_plan': args.get('meal_plan', '') or '',
            'total_price': str(args.get('total_price', '') or ''),
        }
        try:
            previous_signature = (lead.agent_context or {}).get('last_booking_transfer_signature')
            if previous_signature == transfer_signature:
                logger.info(
                    "Skipping duplicate booking_complete transfer_to_manager for lead=%s",
                    getattr(lead, 'pk', None),
                )
                return {
                    'status': 'success',
                    'message': 'Менеджер уже уведомлён',
                    'notified': cfg.manager_name or 'менеджер',
                    'already_notified': True,
                }
        except Exception:
            pass

    if cfg.channel == ManagerTransferConfig.CHANNEL_TELEGRAM:
        contact_id = str(
            (lead.telegram_chat_id if lead and lead.telegram_chat_id else None)
            or args.get('telegram_chat_id', '')
        )
    else:
        contact_id = str(
            (lead.whatsapp_phone if lead and lead.whatsapp_phone else None)
            or (lead.phone if lead and lead.phone else None)
            or args.get('guest_phone', '')
        )

    # Resolve domain for CRM link
    _domain = os.environ.get('APP_DOMAIN') or os.environ.get('API_DOMAIN', '')
    _domain = _domain.strip().rstrip('/')
    if _domain and not _domain.startswith('http'):
        _domain = f'https://{_domain}'
    if not _domain:
        _domain = 'https://axon-kinetic.com'

    # Build direct messenger and CRM links
    platform_lower = (platform or '').lower()
    crm_link = ''
    if lead:
        crm_link = f"{_domain}/communications?leadId=%22{lead.id}%22&channel={platform_lower}"

    telegram_link = ''
    telegram_handle_val = ''
    if lead and lead.telegram_username:
        telegram_handle_val = f"@{lead.telegram_username}"
        telegram_link = f"https://t.me/{lead.telegram_username}"
    elif lead and lead.telegram_chat_id:
        telegram_handle_val = f"ID: {lead.telegram_chat_id}"
        telegram_link = f"tg://user?id={lead.telegram_chat_id}"

    instagram_link = ''
    instagram_handle_val = ''
    if lead and lead.instagram_username:
        instagram_handle_val = f"@{lead.instagram_username}"
        instagram_link = f"https://instagram.com/{lead.instagram_username}"

    whatsapp_link = ''
    if lead and lead.whatsapp_phone:
        clean_phone = re.sub(r'\D', '', lead.whatsapp_phone)
        whatsapp_link = f"https://wa.me/{clean_phone}"
    elif lead and lead.phone:
        clean_phone = re.sub(r'\D', '', lead.phone)
        whatsapp_link = f"https://wa.me/{clean_phone}"

    # Construct platform display name and clickable handles/phones
    is_html = (cfg.channel == 'telegram')

    def maybe_escape(val) -> str:
        s = str(val or '')
        return _escape_html(s) if is_html else s

    def format_link(label: str, url: str) -> str:
        if not url:
            return maybe_escape(label)
        if is_html:
            return f'<a href="{url}">{_escape_html(label)}</a>'
        return f"{label} ({url})"

    platform_name = platform.capitalize() if platform else ''
    links_list = []
    if platform_lower == 'telegram' and telegram_link:
        links_list.append(format_link('Чат', telegram_link))
    elif platform_lower == 'instagram' and instagram_link:
        links_list.append(format_link('Чат', instagram_link))
    elif platform_lower == 'whatsapp' and whatsapp_link:
        links_list.append(format_link('Чат', whatsapp_link))
        
    if crm_link:
        links_list.append(format_link('CRM', crm_link))
        
    if links_list:
        if is_html:
            platform_display = f"{_escape_html(platform_name)} · {' · '.join(links_list)}"
        else:
            platform_display = f"{platform_name} · {' · '.join(links_list)}"
    else:
        platform_display = maybe_escape(platform_name)

    if is_html:
        telegram_display = format_link(telegram_handle_val, telegram_link) if telegram_handle_val else ''
        instagram_display = format_link(instagram_handle_val, instagram_link) if instagram_handle_val else ''
        phone_display = format_link(guest_phone, whatsapp_link) if guest_phone else ''
    else:
        telegram_display = telegram_handle_val
        if telegram_handle_val and telegram_link:
            telegram_display = f"{telegram_handle_val} ({telegram_link})"

        instagram_display = instagram_handle_val
        if instagram_handle_val and instagram_link:
            instagram_display = f"{instagram_handle_val} ({instagram_link})"

        phone_display = guest_phone or ''
        if guest_phone and whatsapp_link:
            phone_display = f"{guest_phone} ({whatsapp_link})"

    org = _org_from_lead(lead)
    business_name = getattr(org, 'name', '') or 'Hotel'
    template_vars = {
        'business_name': maybe_escape(business_name),
        'reason': maybe_escape(reason_label),
        'guest_name': maybe_escape(guest_name),
        'guest_phone': phone_display,
        'guest_email': maybe_escape(guest_email),
        'platform': platform_display,
        'checkin_date': maybe_escape(checkin),
        'checkout_date': maybe_escape(checkout),
        'nights': maybe_escape(nights),
        'guest_count': maybe_escape(args.get('guest_count')),
        'room_description': maybe_escape(args.get('room_description')),
        'meal_plan': maybe_escape(args.get('meal_plan')),
        'price_per_night': maybe_escape(args.get('price_per_night')),
        'total_price': maybe_escape(args.get('total_price')),
        'notes': maybe_escape(notes),
        'discovery_source': maybe_escape(discovery_source_display),
        'discovery_source_detail': maybe_escape(
            args.get('discovery_source_detail')
            or getattr(lead, 'discovery_source_detail', '')
            or ''
        ),
        'contact_id': maybe_escape(contact_id),
        'telegram_handle': telegram_display,
        'instagram_handle': instagram_display,
        'crm_link': maybe_escape(crm_link),
        'telegram_link': maybe_escape(telegram_link),
        'instagram_link': maybe_escape(instagram_link),
        'whatsapp_link': maybe_escape(whatsapp_link),
    }

    def _format_tree_lines(items: list[tuple[str, str]]) -> list[str]:
        non_empty = [item for item in items if item[1] and str(item[1]).strip()]
        if not non_empty:
            return []
        formatted = []
        for i, (label, val) in enumerate(non_empty):
            prefix = '  └─ ' if i == len(non_empty) - 1 else '  ├─ '
            formatted.append(f"{prefix}{label}: {val}")
        return formatted

    if cfg.notification_template:
        template = _escape_html(cfg.notification_template) if is_html else cfg.notification_template
        message_text = _render_custom_template(template, template_vars)
    else:
        if is_html:
            lines = [
                f'🔔 <b>Новая заявка — {template_vars["business_name"]}</b>',
                f'━━━━━━━━━━━━━━━━━━━━',
                f'📌 <b>Причина:</b> {template_vars["reason"]}',
                '',
                f'👤 <b>Информация о госте:</b>',
            ]
            guest_items = [
                ('Имя', template_vars['guest_name']),
                ('Телефон', template_vars['guest_phone']),
                ('Email', template_vars['guest_email']),
                ('Источник', template_vars['platform']),
                ('Откуда узнал', template_vars['discovery_source']),
            ]
            if contact_id:
                label = 'Telegram ID' if platform_lower == 'telegram' else 'Телефон ID'
                guest_items.append((label, template_vars['contact_id']))
                
            lines.extend(_format_tree_lines(guest_items))

            booking_items = []
            if checkin:
                booking_items.append(('Заезд', template_vars['checkin_date']))
            if checkout:
                booking_items.append(('Выезд', template_vars['checkout_date']))
            if nights:
                booking_items.append(('Ночей', template_vars['nights']))
            if template_vars['guest_count']:
                booking_items.append(('Гостей', template_vars['guest_count']))
            if template_vars['room_description']:
                booking_items.append(('Номер', template_vars['room_description']))
            if template_vars['meal_plan']:
                booking_items.append(('Питание', template_vars['meal_plan']))
            if template_vars['price_per_night']:
                booking_items.append(('Цена/ночь', f"{template_vars['price_per_night']} сом"))
            if template_vars['total_price']:
                booking_items.append(('Итого', f"<b>{template_vars['total_price']} сом</b>"))

            formatted_booking = _format_tree_lines(booking_items)
            if formatted_booking:
                lines.append('')
                lines.append('🗓 <b>Детали проживания:</b>')
                lines.extend(formatted_booking)

            if template_vars['notes']:
                lines.append('')
                lines.append('📝 <b>Примечание:</b>')
                lines.append(f'<i>{template_vars["notes"]}</i>')
        else:
            lines = [
                f'🔔 *Новая заявка — {business_name}*',
                f'━━━━━━━━━━━━━━━━━━━━',
                f'📌 *Причина:* {reason_label}',
                '',
                f'👤 *Информация о госте:*',
            ]
            guest_items = [
                ('Имя', template_vars['guest_name']),
                ('Телефон', template_vars['guest_phone']),
                ('Email', template_vars['guest_email']),
                ('Источник', template_vars['platform']),
                ('Откуда узнал', template_vars['discovery_source']),
            ]
            if contact_id:
                label = 'Telegram ID' if platform_lower == 'telegram' else 'Телефон ID'
                guest_items.append((label, contact_id))
                
            lines.extend(_format_tree_lines(guest_items))

            booking_items = []
            if checkin:
                booking_items.append(('Заезд', checkin))
            if checkout:
                booking_items.append(('Выезд', checkout))
            if nights:
                booking_items.append(('Ночей', str(nights)))
            if template_vars['guest_count']:
                booking_items.append(('Гостей', template_vars['guest_count']))
            if template_vars['room_description']:
                booking_items.append(('Номер', template_vars['room_description']))
            if template_vars['meal_plan']:
                booking_items.append(('Питание', template_vars['meal_plan']))
            if template_vars['price_per_night']:
                booking_items.append(('Цена/ночь', f"{template_vars['price_per_night']} сом"))
            if template_vars['total_price']:
                booking_items.append(('Итого', f"*{template_vars['total_price']} сом*"))

            formatted_booking = _format_tree_lines(booking_items)
            if formatted_booking:
                lines.append('')
                lines.append('🗓 *Детали проживания:*')
                lines.extend(formatted_booking)

            if template_vars['notes']:
                lines.append('')
                lines.append('📝 *Примечание:*')
                lines.append(f'_{template_vars["notes"]}_')

        message_text = '\n'.join(lines)
    manager_name = cfg.manager_name or 'менеджер'

    try:
        if cfg.channel == 'telegram':
            from apps.leads.telegram_service import TelegramService
            from asgiref.sync import async_to_sync
            svc = TelegramService()
            result = async_to_sync(svc.send_message)(cfg.recipient_id, message_text, parse_mode='HTML')
            if result is None:
                raise RuntimeError('Telegram send returned None')
            logger.info(f"Telegram transfer result: message_id={getattr(result, 'message_id', result)}")
        else:
            from apps.leads.whatsapp_service import WhatsAppService
            svc = WhatsAppService()
            phone = cfg.recipient_id.lstrip('+')
            result = svc.send_message(phone, message_text)
            if result is None:
                raise RuntimeError('WhatsApp send returned None')
            logger.info(f"WhatsApp transfer result: {result}")

        logger.info(f"Manager notification sent via {cfg.channel} to {cfg.recipient_id}")
        if lead is not None:
            try:
                from django.utils import timezone
                update_fields = []
                
                if reason != 'booking_complete':
                    lead.ai_paused = True
                    lead.ai_paused_at = timezone.now()
                    lead.ai_paused_by = 'AI Handoff'
                    update_fields.extend(['ai_paused', 'ai_paused_at', 'ai_paused_by'])
                
                # Update CRM fields on lead for booking_complete
                if reason == 'booking_complete':
                    room_desc = args.get('room_description') or ''
                    if room_desc:
                        lead.room_type_preference = room_desc
                        update_fields.append('room_type_preference')
                    tot_price = args.get('total_price')
                    if tot_price is not None:
                        try:
                            lead.estimated_value = float(tot_price)
                            update_fields.append('estimated_value')
                        except (ValueError, TypeError):
                            pass

                if transfer_signature is not None:
                    ctx = dict(lead.agent_context or {})
                    ctx['last_booking_transfer_signature'] = transfer_signature
                    ctx['last_booking_transfer_notified_at'] = datetime.now(tz=ZoneInfo('UTC')).isoformat()
                    lead.agent_context = ctx
                    update_fields.append('agent_context')
                
                if update_fields:
                    lead.save(update_fields=update_fields)
            except Exception as save_err:
                logger.warning(
                    "Could not update lead status for handoff for lead=%s: %s",
                    getattr(lead, 'pk', None),
                    save_err,
                )
        return {'status': 'success', 'message': 'Менеджер уведомлён', 'notified': manager_name}

    except Exception as e:
        logger.error(f"Failed to send manager notification via {cfg.channel}: {e}", exc_info=True)
        return {'status': 'error', 'message': f'Не удалось отправить уведомление: {e}'}

def execute_pricing_tool(tool_name: str, args: dict, lead=None):
    """Execute a pricing tool call and return a JSON-serializable result."""
    try:
        args = dict(args or {})
        remember_offer = bool(args.pop('_remember_offer', True))
        if tool_name == 'get_room_images':
            return execute_get_room_images(args, lead)
        from apps.hotel_info.pricing_utils import generate_room_combinations, query_meal_plan_pricing
        from apps.hotel_info.models import RoomCombinationNote
        runtime_config = {}
        try:
            from django.db.models import Q
            from apps.flows.models import AITool
            org = _org_from_lead(lead)
            tool_qs = AITool.objects.filter(name=tool_name, is_enabled=True)
            if org is not None:
                tool_qs = tool_qs.filter(Q(organization=org) | Q(organization__isnull=True))
            else:
                tool_qs = tool_qs.filter(organization__isnull=True)
            tool_cfgs = sorted(
                tool_qs,
                key=lambda tool: (tool.organization_id is not None, tool.updated_at),
            )
            tool_cfg = tool_cfgs[-1] if tool_cfgs else None
            runtime_config = tool_cfg.runtime_config or {} if tool_cfg else {}
        except Exception:
            runtime_config = {}

        if tool_name == 'get_meal_plan_pricing':
            room_type = str(args.get('room_type') or '').strip()
            guest_count = args.get('guest_count')
            checkin_date = args.get('checkin_date')

            if not room_type:
                return {'error': 'room_type_required'}
            if guest_count is None:
                return {'error': 'guest_count_required'}

            try:
                guest_count = int(guest_count)
            except (TypeError, ValueError):
                return {'error': 'guest_count_invalid'}

            result = query_meal_plan_pricing(
                room_type=room_type,
                guest_count=guest_count,
                checkin_date=checkin_date,
            )
            if 'error' not in result:
                result['_note'] = (
                    'total_price_per_night is the COMPLETE all-in nightly rate '
                    '(room + meals combined). Quote it directly. Never subtract '
                    'the room base price and never present a delta.'
                )
            return result

        if tool_name == 'get_room_options':
            requested_guest_count = args.get('guest_count', 1)
            from apps.leads.services.guest_structure import effective_pricing_guest_count

            if lead is not None:
                structure_updates = {}
                if args.get('adult_count') is not None:
                    structure_updates['adult_count'] = args.get('adult_count')
                if isinstance(args.get('children_ages'), list):
                    structure_updates['children_ages'] = args.get('children_ages')
                if isinstance(args.get('one_room_required'), bool):
                    structure_updates['one_room_required'] = args.get('one_room_required')
                structure_updates['guest_count'] = requested_guest_count
                if structure_updates:
                    from apps.leads.services.guest_structure import apply_extracted_guest_structure

                    apply_extracted_guest_structure(lead, structure_updates)
            guest_count = effective_pricing_guest_count(lead, requested_guest_count) or 1
            checkin_date = args.get('checkin_date')
            checkout_date = args.get('checkout_date')
            one_room_required = bool(
                args.get('one_room_required')
                or args.get('single_room_required')
                or getattr(lead, 'one_room_required', False)
            )

            if checkin_date and _is_past_date(checkin_date):
                today_str = datetime.now(ZoneInfo('Asia/Bishkek')).date().isoformat()
                return {
                    'error': 'past_date',
                    'message': f'Дата заезда {checkin_date} не может быть в прошлом. Сегодня {today_str}. Вежливо сообщите гостю, что эта дата уже прошла, и попросите выбрать актуальные даты.',
                }

            max_self_service_guest_count = int(runtime_config.get('max_self_service_guest_count') or 10)

            if guest_count > max_self_service_guest_count:
                return {
                    'error': 'transfer_to_manager',
                    'message': f'Для групп более {max_self_service_guest_count} человек — передать менеджеру',
                    'max_self_service_guest_count': max_self_service_guest_count,
                }

            if not checkin_date or not checkout_date:
                return {
                    'error': 'dates_required',
                    'message': (
                        'Для проверки тарифа нужны обе точные даты: заезд и выезд. '
                        'Не называйте цену до получения обеих дат.'
                    ),
                }

            notes_map = {}
            try:
                for note_obj in RoomCombinationNote.objects.filter(guest_count=guest_count):
                    notes_map[note_obj.combination_index] = note_obj.note or ''
            except Exception:
                pass

            org = _org_from_lead(lead)
            all_groups, group, total_nights, stay_error = _validated_pricing_group(
                generate_room_combinations,
                guest_count=guest_count,
                checkin_date=checkin_date,
                checkout_date=checkout_date,
                org=org,
            )
            if stay_error:
                return {
                    **stay_error,
                    'guest_count': guest_count,
                    'checkin_date': checkin_date,
                    'checkout_date': checkout_date,
                    'combinations': [],
                }

            _MEAL_LABELS = {
                'with_breakfast': 'С завтраком',
                'half_board': 'Полупансион (завтрак + ужин)',
                'full_board': 'Полный пансион (завтрак + обед + ужин)',
            }

            logger.info(
                f"[get_room_options DEBUG] INPUT: guest_count={guest_count}, "
                f"checkin_date={checkin_date}, checkout_date={checkout_date}, "
                f"total_nights={total_nights}"
            )
            logger.info(
                f"[get_room_options DEBUG] group found: {len(group['combinations'])} combinations"
            )

            combinations = []
            family_alternatives = []
            for combo in group['combinations']:
                if not combo['available']:
                    continue
                if one_room_required and combo.get('room_count', 0) > 1:
                    continue
                prices = combo.get('prices') or {}
                standard_pn = prices.get('standard')

                logger.info(
                    f"[get_room_options DEBUG] combo rooms={combo['rooms']} "
                    f"raw prices dict={prices}"
                )

                meal_plans = {}
                for key, label in _MEAL_LABELS.items():
                    val = prices.get(key)
                    if val is not None:
                        plan = {'per_night': val, 'label': label}
                        if total_nights:
                            plan['total'] = val * total_nights
                        meal_plans[key] = plan

                logger.info(
                    f"[get_room_options DEBUG] combo rooms={combo['rooms']} "
                    f"meal_plans after primary build={meal_plans}"
                )

                if not meal_plans and combo['rooms']:
                    fallback = query_meal_plan_pricing(
                        room_type=combo['rooms'][0],
                        guest_count=guest_count,
                        checkin_date=checkin_date,
                    )
                    logger.info(
                        f"[get_room_options DEBUG] fallback query for rooms={combo['rooms']} "
                        f"returned: {fallback}"
                    )
                    for plan_item in (fallback.get('meal_plan_options') or []):
                        key = plan_item['meal_plan']
                        if key in _MEAL_LABELS:
                            entry_plan = {
                                'per_night': plan_item['total_price_per_night'],
                                'label': plan_item['name'],
                                'scope': 'primary_room_only',
                            }
                            if total_nights:
                                entry_plan['total'] = plan_item['total_price_per_night'] * total_nights
                            meal_plans[key] = entry_plan

                if combo['type'] == 'Семейный':
                    family_entry = {
                        'description': ' + '.join(combo['rooms']),
                        'room_count': combo['room_count'],
                        'is_multi_room': combo['room_count'] > 1,
                        'standard_price_per_night': standard_pn,
                        'meal_plans': meal_plans,
                        'note': notes_map.get(combo['index'], ''),
                        'room_type_key': combo['rooms'][0] if combo['rooms'] else '',
                    }
                    if standard_pn is not None and total_nights:
                        family_entry['standard_price_total'] = standard_pn * total_nights
                    if len(combo['rooms']) > 1:
                        family_entry['room_type_keys'] = combo['rooms']
                    family_alternatives.append(family_entry)
                    continue

                entry = {
                    'description': ' + '.join(combo['rooms']),
                    'room_count': combo['room_count'],
                    'is_multi_room': combo['room_count'] > 1,
                    'standard_price_per_night': standard_pn,
                    'meal_plans': meal_plans,
                    'note': notes_map.get(combo['index'], ''),
                    'room_type_key': combo['rooms'][0] if combo['rooms'] else '',
                }
                if standard_pn is not None and total_nights:
                    entry['standard_price_total'] = standard_pn * total_nights
                if len(combo['rooms']) > 1:
                    entry['room_type_keys'] = combo['rooms']
                combinations.append(entry)

            logger.info(
                f"[get_room_options] returning {len(combinations)} standard combinations to AI"
            )

            if not combinations:
                return {
                    'error': 'pricing_unavailable',
                    'guest_count': guest_count,
                    'checkin_date': checkin_date,
                    'checkout_date': checkout_date,
                    'combinations': [],
                    'message': (
                        'Актуальный тариф для выбранной даты не загружен. '
                        'Не называйте цену из памяти и не придумывайте доступность.'
                    ),
                }

            response = {
                'guest_count': guest_count,
                'total_party_size': getattr(lead, 'guest_count', None) or requested_guest_count,
                'adult_count': getattr(lead, 'adult_count', None),
                'children_ages': getattr(lead, 'children_ages', None) or [],
                'one_room_required': one_room_required,
                'combinations': combinations,
                '_note': (
                    'All prices pre-calculated — AI must NOT perform any arithmetic. '
                    'meal_plans.per_night is the COMBINED total for all rooms in this combination — quote it directly, never say "per room". '
                    'SEQUENCE (mandatory): 1) Present standard_price_per_night for all combinations. '
                    '2) After the guest picks a specific room, IMMEDIATELY present ALL meal_plan options '
                    'from that combination’s meal_plans (label + per_night). Ask the guest to choose. '
                    'If there is exactly ONE combination, present that room AND all meal_plan options in the SAME reply. '
                    'Do not ask "which option" and do not ask the guest what meal to add without listing the meal options. '
                    '3) ONLY after meal plan is confirmed, ask for contact details. '
                    'Do NOT skip meal plan step. Do NOT jump from room selection to contact details. '
                    'CRITICAL: Use ONLY the prices in this tool response. '
                    'NEVER use prices from example conversations, conversation history, or memory — those are outdated and incorrect. '
                    'For multi-room combinations (is_multi_room=true), mention that rooms will be adjacent if possible. '
                    'Show ONLY the combinations listed here — do NOT mention семейный or family rooms (those require a separate request). '
                    'If total_party_size is greater than guest_count because young children stay free without a separate bed, '
                    'say this clearly and recommend only options suitable for the paying adult occupancy. '
                    'A baby must not cause an unnecessary family or extra-room recommendation.'
                ),
            }

            if checkin_date:
                response['checkin_date'] = checkin_date
            if checkout_date:
                response['checkout_date'] = checkout_date
            if total_nights:
                response['total_nights'] = total_nights
            logger.info(
                f"[get_room_options DEBUG] FINAL RESPONSE JSON: "
                f"{json.dumps(response, ensure_ascii=False)}"
            )
            _remember_room_offer(lead, tool_name, response, remember=remember_offer)
            return response

        elif tool_name == 'get_family_room':
            return {
                'error': 'family_room_request_only',
                'message': (
                    'Семейный номер отключён для автоматической продажи. '
                    'Не предлагайте его и не называйте цену. Если гость прямо просит '
                    'семейный вариант, передайте запрос менеджеру; в обычном подборе '
                    'показывайте только доступные стандартные/комфорт варианты.'
                ),
            }
            guest_count = args.get('guest_count', 1)
            checkin_date = args.get('checkin_date')
            checkout_date = args.get('checkout_date')
            children_ages = [
                float(age)
                for age in (args.get('children_ages') or [])
                if isinstance(age, (int, float)) or str(age).replace('.', '', 1).isdigit()
            ]
            single_room_required = bool(args.get('single_room_required'))
            has_infant = any(age < 1 for age in children_ages)

            if checkin_date and _is_past_date(checkin_date):
                today_str = datetime.now(ZoneInfo('Asia/Bishkek')).date().isoformat()
                return {
                    'error': 'past_date',
                    'message': f'Дата заезда {checkin_date} не может быть в прошлом. Сегодня {today_str}. Вежливо сообщите гостю, что эта дата уже прошла, и попросите выбрать актуальные даты.',
                }

            max_self_service_guest_count = int(runtime_config.get('max_self_service_guest_count') or 10)

            if guest_count > max_self_service_guest_count:
                return {
                    'error': 'transfer_to_manager',
                    'message': f'Для групп более {max_self_service_guest_count} человек — передать менеджеру',
                    'max_self_service_guest_count': max_self_service_guest_count,
                }

            if not checkin_date or not checkout_date:
                return {
                    'error': 'dates_required',
                    'message': (
                        'Для проверки семейного размещения нужны обе точные даты: '
                        'заезд и выезд. Не называйте цену до получения обеих дат.'
                    ),
                }

            notes_map = {}
            try:
                for note_obj in RoomCombinationNote.objects.filter(guest_count=guest_count):
                    notes_map[note_obj.combination_index] = note_obj.note or ''
            except Exception:
                pass

            org = _org_from_lead(lead)
            all_groups, group, total_nights, stay_error = _validated_pricing_group(
                generate_room_combinations,
                guest_count=guest_count,
                checkin_date=checkin_date,
                checkout_date=checkout_date,
                org=org,
            )
            if stay_error:
                return {
                    **stay_error,
                    'guest_count': guest_count,
                    'checkin_date': checkin_date,
                    'checkout_date': checkout_date,
                    'combinations': [],
                }

            _MEAL_LABELS = {
                'with_breakfast': 'С завтраком',
                'half_board': 'Полупансион (завтрак + ужин)',
                'full_board': 'Полный пансион (завтрак + обед + ужин)',
            }

            combinations = []
            for combo in group['combinations']:
                if not combo['available']:
                    continue
                if single_room_required and combo['room_count'] > 1:
                    continue
                room_names = ' '.join(combo.get('rooms') or []).lower()
                is_family_combo = combo['type'] == 'Семейный'
                if has_infant:
                    # An infant does not need a separate family/two-room layout.
                    # Prefer compact one-room options and never upsell
                    # a family category merely because a baby was mentioned.
                    if combo['room_count'] != 1 or is_family_combo:
                        continue
                elif not is_family_combo:
                    continue
                prices = combo.get('prices') or {}
                standard_pn = prices.get('standard')

                meal_plans = {}
                for key, label in _MEAL_LABELS.items():
                    val = prices.get(key)
                    if val is not None:
                        plan = {'per_night': val, 'label': label}
                        if total_nights:
                            plan['total'] = val * total_nights
                        meal_plans[key] = plan

                if not meal_plans and combo['rooms']:
                    fallback = query_meal_plan_pricing(
                        room_type=combo['rooms'][0],
                        guest_count=guest_count,
                        checkin_date=checkin_date,
                    )
                    for plan_item in (fallback.get('meal_plan_options') or []):
                        key = plan_item['meal_plan']
                        if key in _MEAL_LABELS:
                            entry_plan = {
                                'per_night': plan_item['total_price_per_night'],
                                'label': plan_item['name'],
                                'scope': 'primary_room_only',
                            }
                            if total_nights:
                                entry_plan['total'] = plan_item['total_price_per_night'] * total_nights
                            meal_plans[key] = entry_plan

                entry = {
                    'description': ' + '.join(combo['rooms']),
                    'room_count': combo['room_count'],
                    'is_multi_room': combo['room_count'] > 1,
                    'standard_price_per_night': standard_pn,
                    'meal_plans': meal_plans,
                    'note': notes_map.get(combo['index'], ''),
                    'room_type_key': combo['rooms'][0] if combo['rooms'] else '',
                }
                if standard_pn is not None and total_nights:
                    entry['standard_price_total'] = standard_pn * total_nights
                if len(combo['rooms']) > 1:
                    entry['room_type_keys'] = combo['rooms']
                combinations.append(entry)

            if has_infant:
                combinations.sort(
                    key=lambda option: (
                        0 if 'комфорт' in option['description'].lower() else 1,
                        option.get('standard_price_per_night') or float('inf'),
                    )
                )
                combinations = combinations[:2]

            if not combinations:
                has_any_pricing = any(
                    combo.get('available')
                    for candidate_group in all_groups
                    for combo in candidate_group.get('combinations', [])
                )
                if not has_any_pricing:
                    return {
                        'error': 'pricing_unavailable',
                        'guest_count': guest_count,
                        'checkin_date': checkin_date,
                        'checkout_date': checkout_date,
                        'combinations': [],
                        'message': (
                            'Актуальный тариф для выбранной даты не загружен. '
                            'Не называйте цену из памяти.'
                        ),
                    }
                return {
                    'error': 'no_suitable_single_room' if single_room_required else 'no_family_option',
                    'guest_count': guest_count,
                    'combinations': [],
                    '_note': (
                        'No suitable one-room family option is configured. Do not offer multiple rooms.'
                        if single_room_required
                        else 'No family rooms available for this guest count. Use get_room_options for standard rooms.'
                    ),
                }

            response = {
                'guest_count': guest_count,
                'combinations': combinations,
                '_note': (
                    'All prices pre-calculated — AI must NOT perform any arithmetic. '
                    'meal_plans.per_night is the COMBINED total for all rooms — quote it directly. '
                    'SEQUENCE (mandatory): 1) Present standard_price_per_night for all combinations. '
                    '2) After the guest picks a specific room, IMMEDIATELY present ALL meal_plan options '
                    'from that combination’s meal_plans (label + per_night). Ask the guest to choose. '
                    'If there is exactly ONE combination, present that room AND all meal_plan options in the SAME reply. '
                    'Do not ask "which option" and do not ask the guest what meal to add without listing the meal options. '
                    '3) ONLY after meal plan is confirmed, ask for contact details. '
                    'Do NOT skip meal plan step. '
                    'CRITICAL: Use ONLY the prices in this tool response — never use prices from memory. '
                    'For multi-room combinations (is_multi_room=true), mention that rooms will be adjacent if possible.'
                ),
            }
            if checkin_date:
                response['checkin_date'] = checkin_date
            if checkout_date:
                response['checkout_date'] = checkout_date
            if total_nights:
                response['total_nights'] = total_nights
            response['children_ages'] = children_ages
            response['single_room_required'] = single_room_required
            logger.info(
                f"[get_family_room] returning {len(combinations)} family combinations to AI"
            )
            _remember_room_offer(lead, tool_name, response, remember=remember_offer)
            return response

        elif tool_name == 'transfer_to_manager':
            return execute_transfer_to_manager(args, lead=lead)

        else:
            return {'error': f'Unknown tool: {tool_name}'}
    except Exception as e:
        logger.error(f"Tool execution error ({tool_name}): {e}", exc_info=True)
        return {'error': str(e)}

def ensure_transfer_guest_message(response_text: str | None, args: dict, lead=None) -> str:
    """
    Make the guest-facing reply explicit after transfer_to_manager succeeds.
    """
    text = (response_text or '').strip()
    lower = text.lower()
    has_manager_followup = any(
        phrase in lower
        for phrase in (
            'менеджер свяжется', 'менеджер с вами свяжется', 'свяжется с вами',
            'передала менеджеру', 'передал менеджеру', 'передала ваш запрос',
            'передала запрос менеджеру', 'передал запрос менеджеру',
            'our manager will', 'manager will contact', 'will be in touch',
            'менеджер байланышат',
        )
    )
    if has_manager_followup:
        return text

    from apps.hotel_info.services.automation_templates import (
        detect_message_language,
        get_automation_message,
    )

    reason = (args or {}).get('reason', 'escalation')
    suffix = get_automation_message(
        'manager_handoff',
        organization=getattr(lead, 'organization', None),
        channel=(getattr(lead, 'source', '') or 'all').lower(),
        language=detect_message_language(text, getattr(lead, 'language', '')),
        variables={'reason': reason},
    )

    if not text:
        return suffix
    if not suffix:
        return text
    return f"{text}\n\n{suffix}"

def inject_pricing_calculation(lead_data: dict) -> str | None:
    """
    When guest_count + check_in_date + check_out_date are known, compute total stay total server-side
    and return pre-computed [PRICING CALCULATION] block.
    """
    from apps.hotel_info.pricing_utils import find_room_combinations

    guest_count = lead_data.get('guest_count')
    check_in = lead_data.get('check_in_date')
    check_out = lead_data.get('check_out_date')

    if not all([guest_count, check_in, check_out]):
        return None

    try:
        guest_count = int(guest_count)
        checkin = date.fromisoformat(str(check_in))
        checkout = date.fromisoformat(str(check_out))
        nights = (checkout - checkin).days
        if nights <= 0:
            return None
    except (ValueError, TypeError):
        return None

    tariff_totals: dict[str, int] = {}
    room_config_label = None

    for i in range(nights):
        night_date = checkin + timedelta(days=i)
        combos = find_room_combinations(
            total_guests=guest_count,
            checkin_date=str(night_date),
        )
        if not combos:
            return None
        combo = combos[0]
        if room_config_label is None:
            room_config_label = combo['description']
        for tariff, price in (combo.get('combined_prices_per_night_kgs') or {}).items():
            tariff_totals[tariff] = tariff_totals.get(tariff, 0) + price

    if not tariff_totals:
        return None

    tariff_labels = {
        'standard': 'Without meals',
        'with_breakfast': 'With breakfast',
        'half_board': 'Half-board (breakfast + lunch or dinner)',
        'full_board': 'Full board (breakfast + lunch + dinner)',
    }

    lines = [
        "[PRICING CALCULATION — PRE-COMPUTED, USE THESE EXACT NUMBERS]",
        f"Stay: {checkin.strftime('%d %b')} – {checkout.strftime('%d %b')} "
        f"({nights} {'night' if nights == 1 else 'nights'}), {guest_count} guests",
        f"Room configuration: {room_config_label}",
        "Total price for the entire stay (all rooms combined, all nights):",
    ]
    for tariff, total in tariff_totals.items():
        label = tariff_labels.get(tariff, tariff)
        lines.append(f"  {label}: {total:,} KGS".replace(',', '\u00a0'))
    lines.append(
        "CRITICAL: These totals are already calculated. "
        "Quote them exactly — do NOT re-calculate or estimate."
    )
    return "\n".join(lines)

def match_flow_connection(message: str, connections: list):
    """
    Pick the best connection for the incoming message.
    """
    cleaned_message = message.lower().strip(".,!? \t\n\r")
    default_conn = None

    for conn in connections:
        keywords = [k.strip().lower() for k in conn.condition_keywords.split(',') if k.strip()]
        if not keywords:
            default_conn = conn
            continue

        for kw in keywords:
            if kw.isdigit() and len(kw) == 1:
                if cleaned_message == kw:
                    return conn.target_card
            elif all(c.isalnum() or c.isspace() or c == '_' for c in kw):
                pattern = rf'\b{re.escape(kw)}\b'
                if re.search(pattern, cleaned_message):
                    return conn.target_card
            else:
                if kw in cleaned_message:
                    return conn.target_card

    if default_conn:
        return default_conn.target_card
    return None

def fill_placeholders(template: str, lead_data: dict, flow, ai_service_instance=None) -> str:
    """Fill template placeholders from lead data; compute pricing placeholders via AI."""
    lead_data = lead_data or {}

    contact_person = str(lead_data.get('contact_person') or '')
    replacements = {
        '{company_name}': str(lead_data.get('company_name') or ''),
        '{check_in_date}': str(lead_data.get('check_in_date') or ''),
        '{check_out_date}': str(lead_data.get('check_out_date') or ''),
        '{num_guests}': str(lead_data.get('guest_count') or ''),
    }

    result = template
    if contact_person:
        result = result.replace('{contact_person}', contact_person)
    else:
        # Remove ", {contact_person}" gracefully — avoids "Здравствуйте, ! 🌊" when name unknown.
        result = re.sub(r',\s*\{contact_person\}|\{contact_person\},?\s*', '', result)
    for key, value in replacements.items():
        result = result.replace(key, value)

    if '{room_suggestion}' in result or '{total_price}' in result:
        computed = compute_pricing_placeholders(lead_data, ai_service_instance)
        result = result.replace('{room_suggestion}', computed.get('room_suggestion', '[room to be confirmed]'))
        result = result.replace('{total_price}', computed.get('total_price', '[price to be confirmed]'))

    return result

def build_flow_card_instruction(card, lead_data: dict, flow, ai_service_instance=None, stage_resolution=None) -> str:
    """
    Build the system instruction for the active flow card.
    Keeps legacy message_template behavior, and appends structured stage policy
    only when managers configured those fields in the no-code flow editor.
    """
    template_text = fill_placeholders(card.message_template or '', lead_data, flow, ai_service_instance).strip()

    policy_parts = []
    goal = (getattr(card, 'goal', '') or '').strip()
    required_fields = getattr(card, 'required_fields', None) or []
    success_conditions = getattr(card, 'success_conditions', None) or {}
    allowed_tools = getattr(card, 'allowed_tools', None) or []
    response_policy = getattr(card, 'response_policy', None) or {}
    return_instruction = (getattr(card, 'return_to_funnel_instruction', '') or '').strip()

    if goal:
        policy_parts.append(f"Stage goal: {goal}")
    if required_fields:
        policy_parts.append(
            "Required fields to collect before progressing: "
            + ", ".join(str(field) for field in required_fields)
        )
    if success_conditions:
        policy_parts.append(
            "Success conditions: "
            + json.dumps(success_conditions, ensure_ascii=False, sort_keys=True)
        )
    if allowed_tools:
        policy_parts.append(
            "Allowed tools on this stage: "
            + ", ".join(str(tool) for tool in allowed_tools)
        )
    if response_policy:
        policy_parts.append(
            "Response policy: "
            + json.dumps(response_policy, ensure_ascii=False, sort_keys=True)
        )
    if return_instruction:
        policy_parts.append(f"Return-to-funnel instruction: {return_instruction}")
    if stage_resolution is not None:
        try:
            from apps.leads.services.stage_resolver import stage_resolution_instruction

            status_instruction = stage_resolution_instruction(stage_resolution)
            if status_instruction:
                policy_parts.append(status_instruction)
        except Exception:
            pass

    if not policy_parts:
        return template_text

    parts = [
        f"Current flow stage: {card.title}",
        *policy_parts,
    ]
    if template_text:
        parts.append(f"Stage message template:\n{template_text}")
    return "\n".join(parts)

def compute_pricing_placeholders(lead_data: dict, ai_service_instance=None) -> dict:
    """Use OpenAI/Gemini to compute room suggestion and total price from lead data."""
    if ai_service_instance is None or not ai_service_instance.is_configured():
        return {}
    try:
        from apps.hotel_info.pricing_utils import query_room_pricing
        guest_count = lead_data.get('guest_count')
        check_in = lead_data.get('check_in_date')
        check_out = lead_data.get('check_out_date')

        if not guest_count:
            return {'room_suggestion': '[room to be confirmed]', 'total_price': '[price to be confirmed]'}

        pricing = query_room_pricing(
            guest_count=int(guest_count),
            checkin_date=check_in,
            checkout_date=check_out,
        )
        if not pricing:
            return {'room_suggestion': '[room to be confirmed]', 'total_price': '[price to be confirmed]'}

        prompt = (
            f"Guest: {guest_count} people, check-in: {check_in or 'unknown'}, check-out: {check_out or 'unknown'}.\n"
            f"Available rooms: {json.dumps(pricing, ensure_ascii=False)}\n\n"
            "Return JSON with exactly two fields:\n"
            "- room_suggestion: short natural-language room recommendation (1-2 sentences)\n"
            "- total_price: computed total price as a string (e.g. '15,000 KGS per night')\n"
            "Be concise. Return only JSON."
        )
        kwargs = {
            'model': ai_service_instance._model,
            'messages': [{"role": "user", "content": prompt}],
            'temperature': 0.2,
            'response_format': {"type": "json_object"},
        }
        if getattr(ai_service_instance, 'provider', None) != 'gemini':
            kwargs['max_tokens'] = 150

        response = ai_service_instance.client.chat.completions.create(**kwargs)
        result = json.loads(response.choices[0].message.content)
        return {
            'room_suggestion': result.get('room_suggestion', '[room to be confirmed]'),
            'total_price': result.get('total_price', '[price to be confirmed]'),
        }
    except Exception as e:
        logger.error(f"Error computing pricing placeholders: {e}", exc_info=True)
        return {'room_suggestion': '[room to be confirmed]', 'total_price': '[price to be confirmed]'}

def get_flow_guided_response(message: str, lead, lead_data: dict, ai_service_instance=None) -> str | None:
    """
    If flow-guided mode is active and an active flow exists, advance the lead's
    flow state and return the next card's template.
    """
    try:
        from apps.flows.models import AIFlowMode, ConversationFlow, LeadFlowState
        from apps.leads.services.stage_resolver import sync_stage_state

        org = _org_from_lead(lead)
        mode_obj = AIFlowMode.get_mode(org=org)
        if not mode_obj or mode_obj.mode != AIFlowMode.MODE_FLOW_GUIDED:
            return None

        active_flow_qs = ConversationFlow.objects.filter(is_active=True)
        if org is not None:
            active_flow_qs = active_flow_qs.filter(organization=org)
        active_flow = active_flow_qs.prefetch_related('cards', 'connections').first()
        if not active_flow:
            return None

        state, created = LeadFlowState.objects.get_or_create(lead=lead)

        if created or state.flow_id != active_flow.id or state.current_card is None:
            entry_card = active_flow.cards.filter(card_type='entry').first()
            if not entry_card:
                return None
            state.flow = active_flow
            state.current_card = entry_card
            state.is_complete = False
            state.is_escalated = False
            state.collected_data = {}
            resolution = sync_stage_state(state, lead, lead_data, message)
            state.save()
            logger.info(f"Flow: starting lead {lead.pk} at entry card '{entry_card.title}'")
            effective_data = {**(lead_data or {}), **resolution.collected_data}
            return build_flow_card_instruction(entry_card, effective_data, active_flow, ai_service_instance, resolution)

        if state.is_complete or state.is_escalated:
            return None

        current_card = state.current_card
        current_resolution = sync_stage_state(state, lead, lead_data, message)
        if not current_resolution.is_complete:
            if current_resolution.changed:
                state.save(update_fields=['collected_data', 'updated_at'])
            logger.info(
                f"Flow: lead {lead.pk} remains at '{current_card.title}' "
                f"missing={current_resolution.missing_fields}"
            )
            effective_data = {**(lead_data or {}), **current_resolution.collected_data}
            return build_flow_card_instruction(current_card, effective_data, active_flow, ai_service_instance, current_resolution)

        outgoing = list(current_card.outgoing_connections.select_related('target_card').all())

        if not outgoing:
            state.is_complete = True
            state.save()
            return None

        next_card = match_flow_connection(message, outgoing)
        if next_card is None and current_resolution.required_fields:
            normal_targets = [
                conn.target_card
                for conn in outgoing
                if conn.target_card and conn.target_card.card_type != 'escalation'
            ]
            if len(normal_targets) == 1:
                next_card = normal_targets[0]
                logger.info(
                    "Flow: lead %s auto-advanced from completed stage '%s' to '%s' "
                    "without keyword match",
                    lead.pk,
                    current_card.title,
                    next_card.title,
                )
        if next_card is None:
            return None

        if next_card.card_type == 'escalation':
            state.is_escalated = True
        state.current_card = next_card
        next_resolution = sync_stage_state(state, lead, lead_data, message)
        state.save()

        logger.info(f"Flow: lead {lead.pk} advanced to '{next_card.title}' (type={next_card.card_type})")
        effective_data = {**(lead_data or {}), **next_resolution.collected_data}
        return build_flow_card_instruction(next_card, effective_data, active_flow, ai_service_instance, next_resolution)

    except Exception as e:
        logger.error(f"Flow-guided response error: {e}", exc_info=True)
        return None

MONTHS_RU = {
    'янв': 1, 'фев': 2, 'мар': 3, 'апр': 4, 'май': 5, 'мая': 5,
    'июн': 6, 'июл': 7, 'авг': 8, 'сен': 9, 'окт': 10, 'ноя': 11, 'дек': 12
}

def _extract_guest_count_from_text(text: str) -> int | None:
    if not text:
        return None
    text = text.lower()
    
    # Pattern 1: X rooms by Y people (e.g., "3 номера по 3 человека")
    rooms_pattern = re.search(r'(\d+)\s*(?:номер|комнат|коттедж|room)[а-яёs]*\s+(?:по|на|для)\s+(\d+)', text)
    if rooms_pattern:
        try:
            rooms = int(rooms_pattern.group(1))
            guests_per_room = int(rooms_pattern.group(2))
            return rooms * guests_per_room
        except ValueError:
            pass

    # Pattern 2: Sum up adults and children (e.g. "2 взрослых и 1 ребенок 7 лет")
    tokens = re.findall(r'(\d+)\s*([а-яёa-z]+)?', text)
    detailed_total = 0
    generic_total = None
    has_guest_context = False
    
    guest_words = {'взросл', 'взрослых', 'взрослый', 'ребен', 'ребенок', 'ребенка', 'дет', 'детей', 'дети', 'челов', 'человек', 'человека', 'гост', 'гостей', 'гость', 'чел', 'guest', 'guests', 'adult', 'adults', 'child', 'children'}
    detailed_guest_words = {'взросл', 'взрослых', 'взрослый', 'ребен', 'ребенок', 'ребенка', 'дет', 'детей', 'дети', 'adult', 'adults', 'child', 'children'}
    generic_guest_words = {'челов', 'человек', 'человека', 'гост', 'гостей', 'гость', 'чел', 'guest', 'guests'}
    ignore_words = {'лет', 'год', 'года', 'дн', 'дня', 'дней', 'день', 'ноч', 'ночи', 'ночей', 'night', 'nights', 'day', 'days', 'year', 'years', 'old', 'yo', 'м', 'минут', 'мин', 'час', 'часов'}
    
    for num_str, word in tokens:
        val = int(num_str)
        if word:
            is_ignored = False
            for ign in ignore_words:
                if word.startswith(ign):
                    is_ignored = True
                    break
            if is_ignored:
                continue
            
            is_detailed_guest = any(word.startswith(gw) for gw in detailed_guest_words)
            is_generic_guest = any(word.startswith(gw) for gw in generic_guest_words)
            if is_detailed_guest:
                detailed_total += val
                has_guest_context = True
            elif is_generic_guest:
                generic_total = val
                has_guest_context = True

    if has_guest_context:
        if detailed_total:
            return detailed_total
        return generic_total

    # Fallback checks:
    match_nas = re.search(r'(?:нас|будет|приедет|приедем|бронь\s+на)\s+(\d+)', text)
    if match_nas:
        return int(match_nas.group(1))
        
    return None

def _parse_dates_from_text(text: str, today: date) -> list[date]:
    if not text:
        return []
    text = text.lower()
    matches = []
    
    # 1. Relative dates
    for m in re.finditer(r'\b\w*завтра\w*\b', text):
        word = m.group(0)
        if 'завтра' in word:
            if word.startswith('по'):
                matches.append((m.start(), today + timedelta(days=2)))
            else:
                matches.append((m.start(), today + timedelta(days=1)))
    for m in re.finditer(r'\bсегодня\b', text):
        matches.append((m.start(), today))

    # Weekdays in natural phrases such as "с завтра до понедельника".
    # Always resolve to the next occurrence. If a previous date in the same
    # phrase is equal to or later than it, move the weekday to the next week so
    # check-out remains after check-in.
    weekday_patterns = {
        0: r'понедельник(?:а|у|ом|е)?',
        1: r'вторник(?:а|у|ом|е)?',
        2: r'сред(?:а|ы|у|ой|е)',
        3: r'четверг(?:а|у|ом|е)?',
        4: r'пятниц(?:а|ы|у|ей|е)',
        5: r'суббот(?:а|ы|у|ой|е)',
        6: r'воскресень(?:е|я|ю|ем)|воскресени(?:е|я|ю|ем)',
    }
    weekday_regex = re.compile(
        r'\b(?:до|по|в|на)?\s*('
        + '|'.join(f'(?P<wd{weekday}>{pattern})' for weekday, pattern in weekday_patterns.items())
        + r')\b'
    )
    for m in weekday_regex.finditer(text):
        target_weekday = next(
            weekday for weekday in weekday_patterns if m.group(f'wd{weekday}') is not None
        )
        days_ahead = (target_weekday - today.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        dt = today + timedelta(days=days_ahead)
        preceding_dates = [matched_date for pos, matched_date in matches if pos < m.start()]
        if preceding_dates:
            previous_date = preceding_dates[-1]
            while dt <= previous_date:
                dt += timedelta(days=7)
        matches.append((m.start(), dt))
        
    # 2. Absolute dates like "2 июня" or "2июня"
    for m in re.finditer(r'(\d{1,2})\s*(янв|фев|мар|апр|май|мая|июн|июл|авг|сен|окт|ноя|дек)[а-я]*', text):
        day = int(m.group(1))
        month_prefix = m.group(2)
        month = MONTHS_RU.get(month_prefix)
        if month:
            try:
                dt = date(today.year, month, day)
                matches.append((m.start(), dt))
            except ValueError:
                pass

    # 2b. Day only with an explicit current-month phrase:
    # "5го числа этого месяца", "с 5 числа в этом месяце".
    if re.search(r'(?:этого|текущего|в\s+этом)\s+месяц', text):
        for m in re.finditer(r'(?:с\s+)?(\d{1,2})\s*(?:-?\s*(?:го|ого|е|числа))', text):
            day = int(m.group(1))
            try:
                dt = date(today.year, today.month, day)
                if dt < today:
                    # If a guest says "this month" but the day already passed,
                    # treat it as next month rather than silently pricing the past.
                    next_month = today.month + 1
                    year = today.year
                    if next_month > 12:
                        next_month = 1
                        year += 1
                    dt = date(year, next_month, day)
                matches.append((m.start(), dt))
            except ValueError:
                pass
                
    # 3. Digital dates like "02.06"
    for m in re.finditer(r'\b(\d{1,2})\.(\d{1,2})(?:\.(\d{2,4}))?\b', text):
        day = int(m.group(1))
        month = int(m.group(2))
        year = today.year
        if m.group(3):
            y_str = m.group(3)
            if len(y_str) == 2:
                year = 2000 + int(y_str)
            else:
                year = int(y_str)
        try:
            dt = date(year, month, day)
            matches.append((m.start(), dt))
        except ValueError:
            pass

    matches.sort(key=lambda x: x[0])
    seen = set()
    result = []
    for pos, dt in matches:
        if dt not in seen:
            seen.add(dt)
            result.append(dt)
    return result


def _extract_nights_from_text(text: str) -> int | None:
    if not text:
        return None
    text = text.lower()
    match = re.search(r'\b(?:на\s+)?(\d{1,2})\s*(?:ноч(?:ь|и|ей)|night|nights)\b', text)
    if not match:
        return None
    try:
        nights = int(match.group(1))
    except ValueError:
        return None
    if 1 <= nights <= 60:
        return nights
    return None


def _known_booking_data_from_state(lead, lead_data: dict | None = None) -> dict:
    data = dict(lead_data or {})
    if lead is not None:
        if getattr(lead, 'guest_count', None) and not data.get('guest_count'):
            data['guest_count'] = lead.guest_count
        if getattr(lead, 'check_in_date', None) and not data.get('check_in_date'):
            data['check_in_date'] = lead.check_in_date.isoformat()
        if getattr(lead, 'check_out_date', None) and not data.get('check_out_date'):
            data['check_out_date'] = lead.check_out_date.isoformat()
        try:
            collected = lead.flow_state.collected_data or {}
        except Exception:
            collected = {}
        if isinstance(collected, dict):
            for key, value in collected.items():
                if value not in (None, '', [], {}, ()):
                    data.setdefault(key, value)
    return data


def _infer_relative_booking_dates(
    message: str,
    conversation_history: list | None = None,
    today: date | None = None,
) -> tuple[str | None, str | None]:
    if today is None:
        today = datetime.now(ZoneInfo('Asia/Bishkek')).date()
        
    dates = _parse_dates_from_text(message, today)
    
    if len(dates) < 2 and conversation_history:
        for turn in reversed(conversation_history):
            if turn.get('role') == 'user':
                hist_dates = _parse_dates_from_text(turn.get('content', ''), today)
                for d in hist_dates:
                    if d not in dates:
                        dates.append(d)
                if len(dates) >= 2:
                    break
                    
    checkin = dates[0].isoformat() if len(dates) > 0 else None
    checkout = dates[1].isoformat() if len(dates) > 1 else None
    nights = _extract_nights_from_text(message)
    if checkin and not checkout and nights:
        checkout = (date.fromisoformat(checkin) + timedelta(days=nights)).isoformat()
    return checkin, checkout

def normalize_booking_tool_args(
    tool_name: str,
    tool_args: dict,
    message: str,
    conversation_history: list | None = None,
    lead_data: dict | None = None,
    lead=None,
) -> dict:
    if not tool_args:
        tool_args = {}
    if not lead_data:
        lead_data = {}
    lead_data = _known_booking_data_from_state(lead, lead_data)
        
    extracted_guests = _extract_guest_count_from_text(message)
    if extracted_guests:
        tool_args['guest_count'] = extracted_guests
    elif lead_data.get('guest_count') and not tool_args.get('guest_count'):
        tool_args['guest_count'] = lead_data.get('guest_count')

    if tool_name == 'get_room_images':
        categories = (
            tool_args.get('categories')
            or tool_args.get('category')
            or tool_args.get('room_type')
            or []
        )
        if isinstance(categories, str):
            categories = [categories]
        allowed_categories = _ROOM_IMAGE_CATEGORIES | _HOTEL_IMAGE_CATEGORIES
        normalized_categories = []
        for category in categories:
            category_text = str(category or '').strip().lower()
            if category_text in allowed_categories:
                normalized_categories.append(category_text)
        if normalized_categories:
            tool_args['categories'] = list(dict.fromkeys(normalized_categories))
        tool_args.pop('room_type', None)
        tool_args.pop('category', None)
        return tool_args
        
    if tool_name in ('get_room_options', 'get_family_room'):
        today = datetime.now(ZoneInfo('Asia/Bishkek')).date()
        known_checkin = lead_data.get('check_in_date') or tool_args.get('checkin_date')
        known_checkout = lead_data.get('check_out_date') or tool_args.get('checkout_date')
        nights = _extract_nights_from_text(message)
        
        parsed_dates = _parse_dates_from_text(message, today)
        if not parsed_dates and conversation_history:
            for turn in reversed(conversation_history):
                if turn.get('role') == 'user':
                    parsed_dates = _parse_dates_from_text(turn.get('content', ''), today)
                    if parsed_dates:
                        break
        
        if parsed_dates:
            if len(parsed_dates) >= 2:
                tool_args['checkin_date'] = parsed_dates[0].isoformat()
                tool_args['checkout_date'] = parsed_dates[1].isoformat()
            elif len(parsed_dates) == 1:
                single_date_str = parsed_dates[0].isoformat()
                if nights:
                    tool_args['checkin_date'] = single_date_str
                    tool_args['checkout_date'] = (parsed_dates[0] + timedelta(days=nights)).isoformat()
                elif known_checkin:
                    tool_args['checkin_date'] = known_checkin
                    tool_args['checkout_date'] = single_date_str
                else:
                    tool_args['checkin_date'] = single_date_str
        else:
            if known_checkin and 'checkin_date' not in tool_args:
                tool_args['checkin_date'] = known_checkin
            if known_checkout and 'checkout_date' not in tool_args:
                tool_args['checkout_date'] = known_checkout

        if tool_args.get('checkin_date') and nights and not tool_args.get('checkout_date'):
            try:
                ci = date.fromisoformat(str(tool_args['checkin_date']))
                tool_args['checkout_date'] = (ci + timedelta(days=nights)).isoformat()
            except (TypeError, ValueError):
                pass

        # Guard against model guesses that point to a past month when the user's
        # text has an explicit current-month phrase.
        if re.search(r'(?:этого|текущего|в\s+этом)\s+месяц', (message or '').lower()):
            explicit_dates = _parse_dates_from_text(message, today)
            if explicit_dates:
                tool_args['checkin_date'] = explicit_dates[0].isoformat()
                if nights:
                    tool_args['checkout_date'] = (explicit_dates[0] + timedelta(days=nights)).isoformat()

    return tool_args
