import logging

from apps.hotel_info.models import AutomationMessageTemplate


logger = logging.getLogger(__name__)

DEFAULT_AUTOMATION_MESSAGES = {
    'telegram_start': {
        'ru': 'Здравствуйте! 🌊 Рады приветствовать вас в Nomad Camp. Чем могу помочь?',
        'ky': 'Саламатсызбы! 🌊 Nomad Camp мейманканасына кош келиңиз. Сизге кандай жардам бере алам?',
        'en': 'Hello! 🌊 Welcome to Nomad Camp. How can I help?',
    },
    'story_mention_ack': {
        'ru': 'Спасибо, что отметили нас в сторис! 🌊 Нам очень приятно.',
        'ky': 'Бизди сториске белгилегениңиз үчүн рахмат! 🌊 Бизге абдан жагымдуу болду.',
        'en': 'Thank you for mentioning us in your story! 🌊 We really appreciate it.',
    },
    'story_courtesy_close': {
        'ru': 'И вам спасибо! Будем рады видеть вас снова 🌊',
        'ky': 'Сизге да рахмат! Дагы жолугушканга кубанычтабыз 🌊',
        'en': 'Thank you too! We will be happy to welcome you again 🌊',
    },
    'pricing_unavailable': {
        'ru': 'На эти даты тариф нужно подтвердить вручную. Запрос уже передан менеджеру; он уточнит стоимость.',
        'ky': 'Бул күндөргө тарифти кол менен ырастоо керек. Сурам менеджерге өткөрүлдү; ал бааны тактайт.',
        'en': 'The rate for these dates needs manual confirmation. The request has been sent to a manager for verification.',
    },
    'pricing_check_required': {
        'ru': 'Сейчас система не подтвердила тариф. Данные вашего запроса сохранены; могу передать проверку менеджеру.',
        'ky': 'Азыр система тарифти ырастаган жок. Сурамыңыздын маалыматы сакталды; текшерүүнү менеджерге өткөрүп бере алам.',
        'en': 'The system could not verify the rate just now. Your request details are saved; I can ask a manager to check it.',
    },
    'manager_handoff': {
        'ru': 'Запрос передан менеджеру. Он проверит детали и ответит вам.',
        'ky': 'Сурам менеджерге өткөрүлдү. Ал маалыматты текшерип, сизге жооп берет.',
        'en': 'The request has been sent to a manager. They will review the details and reply.',
    },
    'media_unavailable': {
        'ru': 'Сейчас фото не загрузились. Могу пока подробно рассказать о номере или передать запрос менеджеру.',
        'ky': 'Азыр сүрөттөр жүктөлбөй калды. Азырынча номер тууралуу айтып берейин же менеджерге өткөрүп берейин.',
        'en': 'The photos did not load just now. I can describe the room or pass the request to a manager.',
    },
}


def ensure_default_automation_templates(organization) -> None:
    """Materialize editable defaults for organizations created after the data migration."""
    if organization is None:
        return
    channel_by_event = {
        'telegram_start': 'telegram',
        'story_mention_ack': 'instagram',
        'story_courtesy_close': 'instagram',
    }
    for event_key, translations in DEFAULT_AUTOMATION_MESSAGES.items():
        channel = channel_by_event.get(event_key, 'all')
        for language, text in translations.items():
            AutomationMessageTemplate.objects.get_or_create(
                organization=organization,
                event_key=event_key,
                language=language,
                channel=channel,
                defaults={'text': text, 'is_active': True},
            )


def normalize_language(value: str | None, default: str = 'ru') -> str:
    language = str(value or '').lower().replace('_', '-').split('-', 1)[0]
    if language in {'ru', 'ky', 'en'}:
        return language
    return default


def detect_message_language(text: str | None, configured: str | None = None) -> str:
    normalized = normalize_language(configured, default='')
    if normalized:
        return normalized
    value = str(text or '').lower()
    if any(char in value for char in 'ңөү'):
        return 'ky'
    if any('а' <= char <= 'я' or char == 'ё' for char in value):
        return 'ru'
    if any('a' <= char <= 'z' for char in value):
        return 'en'
    return 'ru'


class _SafeVariables(dict):
    def __missing__(self, key):
        return '{' + key + '}'


def get_automation_message(
    event_key: str,
    *,
    organization=None,
    channel: str = 'all',
    language: str = 'ru',
    variables: dict | None = None,
) -> str:
    """Resolve an active org template with channel/language fallbacks."""

    language = normalize_language(language)
    text = ''
    configured_for_event = False
    if organization is not None:
        try:
            all_candidates = AutomationMessageTemplate.objects.filter(
                organization=organization,
                event_key=event_key,
            )
            configured_for_event = all_candidates.exists()
            candidates = all_candidates.filter(is_active=True)
            for candidate_channel, candidate_language in (
                (channel, language),
                ('all', language),
                (channel, 'ru'),
                ('all', 'ru'),
            ):
                template = candidates.filter(
                    channel=candidate_channel,
                    language=candidate_language,
                ).first()
                if template and template.text.strip():
                    text = template.text.strip()
                    break
        except Exception as exc:
            logger.warning('Could not resolve automation template %s: %s', event_key, exc)

    if not text and not configured_for_event:
        defaults = DEFAULT_AUTOMATION_MESSAGES.get(event_key, {})
        text = defaults.get(language) or defaults.get('ru') or ''
    if variables and text:
        try:
            text = text.format_map(_SafeVariables(variables))
        except Exception:
            logger.warning('Could not interpolate automation template %s', event_key)
    return text
