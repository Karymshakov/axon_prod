import logging


logger = logging.getLogger(__name__)


def apply_extracted_guest_structure(lead, extracted_data: dict) -> list[str]:
    """Persist structured party data without collapsing adults and children."""
    updated_fields: list[str] = []

    def _small_int(key, minimum=0, maximum=100):
        value = extracted_data.get(key)
        if value is None or isinstance(value, bool):
            return None
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None
        return parsed if minimum <= parsed <= maximum else None

    adult_count = _small_int('adult_count', 1, 50)
    if adult_count is not None and lead.adult_count != adult_count:
        lead.adult_count = adult_count
        updated_fields.append('adult_count')

    ages = extracted_data.get('children_ages')
    if isinstance(ages, list):
        normalized_ages = []
        for age in ages:
            try:
                parsed_age = round(float(age), 2)
            except (TypeError, ValueError):
                continue
            if 0 <= parsed_age < 18:
                normalized_ages.append(parsed_age)
        if normalized_ages != (lead.children_ages or []):
            lead.children_ages = normalized_ages
            updated_fields.append('children_ages')
        inferred_infants = sum(1 for age in normalized_ages if age < 1)
        if lead.infant_count != inferred_infants:
            lead.infant_count = inferred_infants
            updated_fields.append('infant_count')
    else:
        infant_count = _small_int('infant_count', 0, 20)
        if infant_count is not None and lead.infant_count != infant_count:
            lead.infant_count = infant_count
            updated_fields.append('infant_count')

    one_room_required = extracted_data.get('one_room_required')
    if isinstance(one_room_required, bool) and lead.one_room_required != one_room_required:
        lead.one_room_required = one_room_required
        updated_fields.append('one_room_required')

    guest_count = _small_int('guest_count', 1, 100)
    if guest_count is None and adult_count is not None and isinstance(ages, list):
        guest_count = adult_count + len(lead.children_ages or [])
    if guest_count is not None and lead.guest_count != guest_count:
        lead.guest_count = guest_count
        updated_fields.append('guest_count')

    if updated_fields:
        lead.save(update_fields=list(dict.fromkeys(updated_fields)))
    return list(dict.fromkeys(updated_fields))


def effective_pricing_guest_count(lead, requested_count: int | None = None) -> int | None:
    """Return paid occupancy according to configured child policy."""
    if lead is None:
        return requested_count
    adult_count = getattr(lead, 'adult_count', None)
    ages = getattr(lead, 'children_ages', None) or []
    if not adult_count or not ages:
        return requested_count or adult_count

    free_max_age = 6.0
    try:
        from apps.hotel_info.models import BookingRules

        rules = BookingRules.objects.filter(organization=lead.organization).first()
        if rules:
            free_max_age = float(rules.child_free_max_age)
    except Exception as exc:
        logger.warning('Could not load booking rules for lead %s: %s', lead.id, exc)

    paid_children = sum(1 for age in ages if float(age) > free_max_age)
    return max(1, int(adult_count) + paid_children)
