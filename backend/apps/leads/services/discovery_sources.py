from __future__ import annotations

import re
from typing import Any


LEAD_DISCOVERY_SOURCES_KEY = 'lead_discovery_sources'


DEFAULT_DISCOVERY_SOURCE_OPTIONS = [
    {'value': 'friends', 'label': 'Друзья / рекомендация'},
    {'value': 'ads', 'label': 'Реклама'},
    {'value': 'instagram', 'label': 'Instagram'},
    {'value': 'google', 'label': 'Google / поиск'},
    {'value': 'website', 'label': 'Сайт'},
    {'value': 'partner', 'label': 'Партнер'},
    {'value': 'repeat_guest', 'label': 'Уже был гостем'},
    {'value': 'other', 'label': 'Другое'},
]


_DISCOVERY_ALIASES = {
    'friends': 'friends',
    'friend': 'friends',
    'referral': 'friends',
    'recommendation': 'friends',
    'rekomendaciya': 'friends',
    'druzya': 'friends',
    'ot druzey': 'friends',
    'sarafannoe radio': 'friends',
    'друзья': 'friends',
    'от друзей': 'friends',
    'рекомендация': 'friends',
    'сарафанное радио': 'friends',
    'ads': 'ads',
    'ad': 'ads',
    'advertisement': 'ads',
    'reklama': 'ads',
    'iz reklamy': 'ads',
    'реклама': 'ads',
    'из рекламы': 'ads',
    'instagram': 'instagram',
    'insta': 'instagram',
    'inst': 'instagram',
    'инстаграм': 'instagram',
    'инста': 'instagram',
    'google': 'google',
    'search': 'google',
    'poisk': 'google',
    'поиск': 'google',
    'сайт': 'website',
    'sait': 'website',
    'website': 'website',
    'site': 'website',
    'partner': 'partner',
    'партнер': 'partner',
    'партнёр': 'partner',
    'partnerstvo': 'partner',
    'repeat_guest': 'repeat_guest',
    'already_visited': 'repeat_guest',
    'uzhe byli': 'repeat_guest',
    'byli u vas': 'repeat_guest',
    'уже были': 'repeat_guest',
    'были у вас': 'repeat_guest',
    'other': 'other',
    'drugoe': 'other',
    'другое': 'other',
}


_TRANSLIT_MAP = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'h', 'ц': 'c', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    'ү': 'u', 'ө': 'o', 'ң': 'n',
}

_STOPWORDS = {
    'na', 'v', 'vo', 'ot', 'iz', 's', 'so', 'u', 'po', 'pro', 'pri', 'dlya',
    'the', 'from', 'at', 'in', 'on', 'about',
    'на', 'в', 'во', 'от', 'из', 'с', 'со', 'у', 'по', 'про', 'при', 'для',
}


def _as_record(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _canonical_text(value: Any) -> str:
    text = str(value or '').strip().lower()
    text = ''.join(_TRANSLIT_MAP.get(char, char) for char in text)
    return re.sub(r'[^a-z0-9а-яёүөң]+', ' ', text).strip()


def _tokens(value: Any) -> set[str]:
    return {
        token
        for token in _canonical_text(value).split()
        if len(token) >= 3 and token not in _STOPWORDS
    }


def _normalize_option(option: Any) -> dict[str, str] | None:
    record = _as_record(option)
    value = str(record.get('value') or '').strip()[:50]
    label = str(record.get('label') or '').strip()
    if not value or not label:
        return None
    return {'value': value, 'label': label}


def get_discovery_source_options(organization: Any = None) -> list[dict[str, str]]:
    settings = _as_record(getattr(organization, 'org_settings', None))
    raw_options = settings.get(LEAD_DISCOVERY_SOURCES_KEY)
    if not isinstance(raw_options, list):
        return list(DEFAULT_DISCOVERY_SOURCE_OPTIONS)

    options = [
        option
        for option in (_normalize_option(raw_option) for raw_option in raw_options)
        if option is not None
    ]
    return options or list(DEFAULT_DISCOVERY_SOURCE_OPTIONS)


def build_discovery_sources_prompt_block(organization: Any = None) -> str:
    options = get_discovery_source_options(organization)
    lines = '\n'.join(
        f'- "{option["value"]}": {option["label"]}'
        for option in options
    )
    return f"""Available discovery_source values for this organization:
{lines}

Return discovery_source ONLY as one exact value from this list.
Match by meaning, not only exact wording. Example: if the list contains "partner_nomad_sport": "Партнер Nomad Sport" and the guest says "на забеге Nomad Sport говорили про вас", return "partner_nomad_sport".
If the guest explicitly answers but none of the configured values match, return "other" when it exists; otherwise omit discovery_source and keep the detail in discovery_source_detail."""


def normalize_discovery_source(value: Any, organization: Any = None) -> str:
    text = str(value or '').strip()
    if not text:
        return ''

    options = get_discovery_source_options(organization)
    allowed_values = {option['value'] for option in options}
    direct_lookup: dict[str, str] = {}
    for option in options:
        direct_lookup[option['value'].lower()] = option['value']
        direct_lookup[option['label'].lower()] = option['value']
        direct_lookup[_canonical_text(option['value'])] = option['value']
        direct_lookup[_canonical_text(option['label'])] = option['value']

    lowered = text.lower()
    canonical = _canonical_text(text)
    if lowered in direct_lookup:
        return direct_lookup[lowered]
    if canonical in direct_lookup:
        return direct_lookup[canonical]

    alias_value = _DISCOVERY_ALIASES.get(lowered) or _DISCOVERY_ALIASES.get(canonical)
    if alias_value and alias_value in allowed_values:
        return alias_value

    input_tokens = _tokens(text)
    best_value = ''
    best_score = 0.0
    for option in options:
        candidate = f'{option["value"]} {option["label"]}'
        candidate_tokens = _tokens(candidate)
        if not candidate_tokens or not input_tokens:
            continue

        joined_input = f' {canonical} '
        joined_candidate = f' {_canonical_text(candidate)} '
        if joined_candidate.strip() and joined_candidate.strip() in joined_input:
            return option['value']

        common = input_tokens & candidate_tokens
        if not common:
            continue
        score = len(common) / max(1, min(len(input_tokens), len(candidate_tokens)))
        if score > best_score:
            best_score = score
            best_value = option['value']

    if best_value and best_score >= 0.6:
        return best_value

    return 'other' if 'other' in allowed_values else ''
