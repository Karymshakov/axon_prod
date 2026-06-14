"""
Server-side room pricing query utilities.
Used by the AI service to look up exact pricing data via tool calls
instead of dumping the full table into the system prompt.
"""
from datetime import date

_RU_WEEKDAY_MAP = {
    'понедельник': 0,
    'вторник': 1,
    'среда': 2,
    'четверг': 3,
    'пятница': 4,
    'суббота': 5,
    'воскресенье': 6,
}


def _parse_date(val):
    if isinstance(val, date):
        return val
    if isinstance(val, str) and val:
        try:
            return date.fromisoformat(val)
        except ValueError:
            return None
    return None


def query_room_pricing(guest_count=None, checkin_date=None, checkout_date=None, org=None):
    """
    Return pricing rows matching the given parameters.

    Args:
        guest_count: Filter by exact kolichestvo_chelovek. Omit to return all.
        checkin_date: ISO date string or date. Filters by season range and day-of-week.
        checkout_date: Not used for filtering; included for context.

    Returns:
        List of dicts with room_type, max_guests, validity, weekdays, prices_per_night_kgs.
    """
    from apps.hotel_info.models import RoomPricing

    checkin = _parse_date(checkin_date)
    rows = RoomPricing.objects.all()
    if org is not None:
        rows = rows.filter(organization=org)
    if guest_count is not None:
        rows = rows.filter(kolichestvo_chelovek=guest_count)

    result = []
    for row in rows:
        # Season date filter
        if checkin and row.deystvitelno_s and row.deystvitelno_do:
            if not (row.deystvitelno_s <= checkin <= row.deystvitelno_do):
                continue

        # Day-of-week filter
        if checkin and row.dni_nedeli:
            weekday = checkin.weekday()  # 0=Mon … 6=Sun
            allowed = set()
            for d in row.dni_nedeli:
                key = d.lower().rstrip(',').strip()
                if key in _RU_WEEKDAY_MAP:
                    allowed.add(_RU_WEEKDAY_MAP[key])
            if allowed and weekday not in allowed:
                continue

        entry = {
            'room_type': row.kategoria_nomera,
            'max_guests': int(row.kolichestvo_chelovek) if row.kolichestvo_chelovek is not None else None,
            'guest_type': row.guest_type or 'any',
            'valid_from': row.deystvitelno_s.strftime('%d.%m.%Y') if row.deystvitelno_s else None,
            'valid_to': row.deystvitelno_do.strftime('%d.%m.%Y') if row.deystvitelno_do else None,
            'weekdays': row.dni_nedeli or [],
            'prices_per_night_kgs': {},
        }
        if row.standartny_tarif is not None:
            entry['prices_per_night_kgs']['standard'] = int(row.standartny_tarif)
        if row.s_zavtrakom is not None:
            entry['prices_per_night_kgs']['with_breakfast'] = int(row.s_zavtrakom)
        if row.polupansion is not None:
            entry['prices_per_night_kgs']['half_board'] = int(row.polupansion)
        if row.polny_pansion is not None:
            entry['prices_per_night_kgs']['full_board'] = int(row.polny_pansion)

        result.append(entry)

    return result


def query_meal_plan_pricing(room_type, guest_count, checkin_date=None):
    """
    Return meal plan upgrade prices for a specific room type and guest count.

    Args:
        room_type: Exact room category string (e.g. 'Стандарт Queen').
        guest_count: Number of adults — used to find the matching pricing row.
        checkin_date: ISO date string or date for season/weekday filtering.

    Returns:
        Dict with 'room_type', 'guest_count', 'standard_price', and
        'meal_plan_options' list (each with name, price_per_night, extra_per_night).
        Returns {'error': ...} if no matching row found.
    """
    room_type_lower = room_type.lower().strip()
    rows = query_room_pricing(guest_count=guest_count, checkin_date=checkin_date)
    matches = [r for r in rows if r['room_type'].lower() == room_type_lower]
    if not matches:
        # Try without guest_count filter in case guest count doesn't match exactly
        all_rows = query_room_pricing(checkin_date=checkin_date)
        matches = [r for r in all_rows if r['room_type'].lower() == room_type_lower]
    if not matches:
        # Fuzzy fallback: find rows whose room_type contains all words in the query
        # e.g. "Семейный" matches "семейный два номера" and "семейный один номера"
        # Prefer the row with highest max_guests when multiple fuzzy matches exist
        query_words = room_type_lower.split()
        all_rows = query_room_pricing(checkin_date=checkin_date)
        fuzzy = [
            r for r in all_rows
            if all(w in r['room_type'].lower() for w in query_words)
        ]
        if fuzzy:
            matches = sorted(fuzzy, key=lambda r: r.get('max_guests') or 0, reverse=True)
    if not matches:
        return {'error': f'No pricing found for room type: {room_type}'}

    row = matches[0]
    prices = row.get('prices_per_night_kgs') or {}
    standard = prices.get('standard')

    meal_plan_names = {
        'with_breakfast': 'С завтраком',
        'half_board': 'Полупансион',
        'full_board': 'Полный пансион (завтрак + обед + ужин)',
    }
    options = []
    for key, label in meal_plan_names.items():
        if key in prices:
            options.append({
                'meal_plan': key,
                'name': label,
                'total_price_per_night': prices[key],
            })

    return {
        'room_type': room_type,
        'guest_count': guest_count,
        'meal_plan_options': options,
        '_note': 'total_price_per_night is the COMPLETE all-in nightly rate. Quote it directly.',
    }


COMBINATIONS_MAP = {
    1: [
        {"rooms": ["стандарт одноместный"]},
        {"rooms": ["комфорт одноместный"]},
    ],
    2: [
        {"rooms": ["стандарт двухместный"]},
        {"rooms": ["комфорт двухместный"]},
        {"rooms": ["семейный один номер"]},
    ],
    3: [
        {"rooms": ["стандарт одноместный", "стандарт двухместный"]},
        {"rooms": ["комфорт одноместный", "комфорт двухместный"]},
        {"rooms": ["семейный два номера"]},
    ],
    4: [
        {"rooms": ["стандарт двухместный", "стандарт двухместный"]},
        {"rooms": ["комфорт двухместный", "комфорт двухместный"]},
        {"rooms": ["семейный два номера"]},
    ],
    5: [
        {"rooms": ["стандарт двухместный", "стандарт двухместный", "стандарт одноместный"]},
        {"rooms": ["комфорт двухместный", "комфорт двухместный", "комфорт одноместный"]},
        {"rooms": ["семейный два номера", "стандарт одноместный"]},
    ],
    6: [
        {"rooms": ["стандарт двухместный", "стандарт двухместный", "стандарт двухместный"]},
        {"rooms": ["комфорт двухместный", "комфорт двухместный", "комфорт двухместный"]},
        {"rooms": ["семейный два номера", "стандарт двухместный"]},
    ],
    7: [
        {"rooms": ["стандарт двухместный", "стандарт двухместный", "стандарт двухместный", "стандарт одноместный"]},
        {"rooms": ["комфорт двухместный", "комфорт двухместный", "комфорт двухместный", "комфорт одноместный"]},
        {"rooms": ["семейный два номера", "стандарт двухместный", "стандарт одноместный"]},
    ],
    8: [
        {"rooms": ["стандарт двухместный", "стандарт двухместный", "стандарт двухместный", "стандарт двухместный"]},
        {"rooms": ["комфорт двухместный", "комфорт двухместный", "комфорт двухместный", "комфорт двухместный"]},
        {"rooms": ["семейный два номера", "семейный два номера"]},
    ],
    9: [
        {"rooms": ["стандарт двухместный", "стандарт двухместный", "стандарт двухместный", "стандарт двухместный", "стандарт одноместный"]},
        {"rooms": ["комфорт двухместный", "комфорт двухместный", "комфорт двухместный", "комфорт двухместный", "комфорт одноместный"]},
        {"rooms": ["семейный два номера", "семейный два номера", "стандарт одноместный"]},
    ],
    10: [
        {"rooms": ["стандарт двухместный", "стандарт двухместный", "стандарт двухместный", "стандарт двухместный", "стандарт двухместный"]},
        {"rooms": ["комфорт двухместный", "комфорт двухместный", "комфорт двухместный", "комфорт двухместный", "комфорт двухместный"]},
        {"rooms": ["семейный два номера", "семейный два номера", "стандарт двухместный"]},
    ],
}


def _bishkek_today():
    from datetime import datetime
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        from backports.zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo('Asia/Bishkek')).date()


def _build_room_lookup(target_date=None, org=None):
    """Build normalised room name → pricing row dict for the given date."""
    if target_date is None:
        target_date = _bishkek_today()
    else:
        target_date = _parse_date(target_date) or _bishkek_today()

    all_rows = query_room_pricing(checkin_date=target_date, org=org)
    room_lookup: dict = {}
    for row in all_rows:
        key = row['room_type'].lower().strip()
        existing = room_lookup.get(key)
        if existing is None:
            room_lookup[key] = row
        else:
            has_date = row.get('valid_from') is not None
            existing_has_date = existing.get('valid_from') is not None
            if has_date and not existing_has_date:
                room_lookup[key] = row
    return room_lookup


def _lookup_room(room_lookup: dict, room_name: str):
    """Look up a room by name; falls back to word-based fuzzy match."""
    key = room_name.lower().strip()
    row = room_lookup.get(key)
    if row:
        return row
    words = key.split()
    for rk, rv in room_lookup.items():
        if all(w in rk for w in words):
            return rv
    return None


def calculate_combination_prices(rooms, target_date=None, room_lookup=None):
    """
    Sum prices for a list of room type strings.

    Returns a dict {standard, with_breakfast, half_board, full_board} where
    each value is the summed total or None if that tariff is missing from any
    room. Returns None if any room has no pricing row at all.
    Pass a pre-built room_lookup to avoid repeated DB queries.
    """
    if room_lookup is None:
        room_lookup = _build_room_lookup(target_date)

    tariff_sums: dict = {'standard': 0, 'with_breakfast': 0, 'half_board': 0, 'full_board': 0}
    missing_tariffs: set = set()

    for room_name in rooms:
        row = _lookup_room(room_lookup, room_name)
        if row is None:
            return None
        prices = row.get('prices_per_night_kgs') or {}
        for tariff in ('standard', 'with_breakfast', 'half_board', 'full_board'):
            val = prices.get(tariff)
            if val is None:
                missing_tariffs.add(tariff)
            else:
                tariff_sums[tariff] += val

    return {
        t: (None if t in missing_tariffs else tariff_sums[t])
        for t in ('standard', 'with_breakfast', 'half_board', 'full_board')
    }


def _is_family_combo(rooms: list, room_lookup: dict) -> bool:
    """Return True if any room in the combo is a family room (by name or guest_type tag)."""
    for room_name in rooms:
        if 'семейн' in room_name.lower():
            return True
        row = _lookup_room(room_lookup, room_name)
        if row and row.get('guest_type') == 'family':
            return True
    return False


def generate_room_combinations(target_date=None, org=None):
    """
    Generate the pre-calculated room combinations table for a given date.

    Uses COMBINATIONS_MAP to define which room types to combine for each
    guest count (1–10). Looks up current pricing from RoomPricing for
    today (Bishkek time) or the provided date.

    4-slot priority structure per guest count:
      1. Основной  — cheapest "any"-tagged combo
      2. Альтернатива — second "any"-tagged combo
      3. Альтернатива — third "any"-tagged combo
      4. Семейный  — first "family"-tagged combo (only if one exists)

    Returns a list of guest-count dicts, each with 'guest_count' and
    'combinations' list. Each combination has:
      - index, rooms (list of names), room_count, type, available, prices
    Prices is a dict {standard, with_breakfast, half_board, full_board}
    where each value is the summed total across all rooms, or None if
    that tariff is missing from any room in the combination.
    """
    if target_date is None:
        target_date = _bishkek_today()
    else:
        target_date = _parse_date(target_date) or _bishkek_today()

    room_lookup = _build_room_lookup(target_date, org=org)

    result = []
    for guest_count in range(1, 11):
        combos = COMBINATIONS_MAP.get(guest_count, [])

        any_entries = []
        family_entries = []

        for idx, combo in enumerate(combos):
            rooms = combo['rooms']
            prices_out = calculate_combination_prices(rooms, room_lookup=room_lookup)
            available = prices_out is not None

            entry = {
                'index': idx,
                'rooms': rooms,
                'room_count': len(rooms),
                'available': available,
                'prices': prices_out,
            }

            if _is_family_combo(rooms, room_lookup):
                family_entries.append(entry)
            else:
                any_entries.append(entry)

        # Among "any" combos: cheapest available → Основной, rest → Альтернатива (up to 3 total)
        combo_results = []
        available_any = [
            (i, c) for i, c in enumerate(any_entries)
            if c['available'] and c.get('prices') and c['prices'].get('standard') is not None
        ]
        cheapest_any_idx = (
            min(available_any, key=lambda x: x[1]['prices']['standard'])[0]
            if available_any else 0
        )
        for i, combo in enumerate(any_entries[:3]):
            combo['type'] = 'Основной' if i == cheapest_any_idx else 'Альтернатива'
            combo_results.append(combo)

        # Add the first family combo as Семейный slot (omit if none exist)
        if family_entries:
            family_entries[0]['type'] = 'Семейный'
            combo_results.append(family_entries[0])

        result.append({
            'guest_count': guest_count,
            'combinations': combo_results,
        })

    return result


def find_room_combinations(total_guests, checkin_date=None, checkout_date=None):
    """
    Find viable room combinations for a group of adults.

    Args:
        total_guests: Number of adults needing accommodation.
        checkin_date: ISO date string — used to filter by season/weekday.
        checkout_date: ISO date string (for context).

    Returns:
        List of combination dicts, each with 'description' and 'rooms' list.
    """
    checkin = _parse_date(checkin_date)
    all_rows = query_room_pricing(checkin_date=checkin)

    # Deduplicate: keep the highest-capacity row per room_type so that
    # a room type with rows for 1 and 2 persons is represented by
    # the 2-person row when building combinations.
    seen = {}
    for row in all_rows:
        rt = row['room_type']
        if rt not in seen or (row['max_guests'] or 0) > (seen[rt]['max_guests'] or 0):
            seen[rt] = row

    room_types = list(seen.values())
    combinations = []

    def _combined_prices(rooms):
        """Sum prices_per_night_kgs across all rooms in the combination."""
        totals = {}
        for room in rooms:
            for tariff, price in (room.get('prices_per_night_kgs') or {}).items():
                totals[tariff] = totals.get(tariff, 0) + price
        return totals

    # Single-room options that fit the whole group
    for rt in room_types:
        if (rt['max_guests'] or 0) >= total_guests:
            combinations.append({
                'description': f"1 × {rt['room_type']} (fits up to {rt['max_guests']} guests)",
                'rooms': [rt],
                'combined_prices_per_night_kgs': rt.get('prices_per_night_kgs', {}),
                'capacity': rt['max_guests'],
            })

    # Two-room combinations — only when no single room can fit the whole group
    if combinations:
        return combinations

    # No single room fits — fall back to two-room combinations
    n = len(room_types)
    for i in range(n):
        for j in range(i, n):
            rt1 = room_types[i]
            rt2 = room_types[j]
            cap = (rt1['max_guests'] or 0) + (rt2['max_guests'] or 0)
            if cap >= total_guests:
                if i == j:
                    label = f"2 × {rt1['room_type']} ({rt1['max_guests']} guests each)"
                else:
                    label = (
                        f"1 × {rt1['room_type']} ({rt1['max_guests']} guests) "
                        f"+ 1 × {rt2['room_type']} ({rt2['max_guests']} guests)"
                    )
                rooms = [rt1, rt2]
                combinations.append({
                    'description': label,
                    'rooms': rooms,
                    'combined_prices_per_night_kgs': _combined_prices(rooms),
                    'capacity': cap,
                })

    return combinations
