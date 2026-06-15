import os
import base64
import logging

from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view
from rest_framework.response import Response

logger = logging.getLogger(__name__)

SUPPORTED_MIME_TYPES = {
    'image/png', 'image/jpeg', 'image/jpg', 'image/webp',
    'application/pdf',
}

FILE_EXTRACTION_PROMPT = """Extract all information from this file and return it in clean, well-formatted text.

Rules:
- Tables (pricing, menus, schedules): convert to clean markdown table format with all columns
- Key-value pairs and lists: use bullet points
- Plain text: reproduce accurately
- Do not add any commentary, preamble, or explanation — return ONLY the extracted content

The result will be used directly by an AI assistant to answer customer questions, so be precise and complete."""
from .models import (
    HotelProfile, HotelProfileLink, HotelPolicy, HotelFAQ, HandoverContact,
    Playbook, RoomPricing, RoomCombinationNote,
)
from .serializers import (
    HotelProfileSerializer, HotelProfileLinkSerializer,
    HotelPolicySerializer, HotelFAQSerializer, HandoverContactSerializer,
    PlaybookSerializer, RoomPricingSerializer, RoomCombinationNoteSerializer,
)
from apps.organizations.mixins import OrganizationQuerysetMixin


def _get_org(request):
    user = request.user
    if getattr(user, 'is_superadmin', False):
        return None
    org = getattr(user, 'current_organization', None)
    if org is None:
        from rest_framework.exceptions import PermissionDenied
        raise PermissionDenied('No active organization. Please select an organization.')
    return org


@api_view(['GET', 'PATCH'])
def hotel_profile(request):
    """Retrieve or partially update the org-scoped HotelProfile."""
    org = _get_org(request)
    profile = HotelProfile.get_profile(org=org)
    if request.method == 'GET':
        return Response(HotelProfileSerializer(profile).data)
    serializer = HotelProfileSerializer(profile, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(HotelProfileSerializer(profile).data)


class HotelProfileLinkViewSet(OrganizationQuerysetMixin, viewsets.ModelViewSet):
    queryset = HotelProfileLink.objects.all()
    serializer_class = HotelProfileLinkSerializer

    def get_queryset(self):
        user = self.request.user
        org = None if getattr(user, 'is_superadmin', False) else self._get_organization()
        profile = HotelProfile.get_profile(org=org)
        return HotelProfileLink.objects.filter(profile=profile)

    def perform_create(self, serializer):
        user = self.request.user
        org = None if getattr(user, 'is_superadmin', False) else self._get_organization()
        profile = HotelProfile.get_profile(org=org)
        max_order = HotelProfileLink.objects.filter(profile=profile).count()
        serializer.save(profile=profile, order=max_order)


class HotelPolicyViewSet(OrganizationQuerysetMixin, viewsets.ModelViewSet):
    queryset = HotelPolicy.objects.all()
    serializer_class = HotelPolicySerializer

    def perform_create(self, serializer):
        user = self.request.user
        org = None if getattr(user, 'is_superadmin', False) else self._get_organization()
        max_order = HotelPolicy.objects.filter(organization=org).count() if org else HotelPolicy.objects.count()
        serializer.save(organization=org, order=max_order)


class HotelFAQViewSet(OrganizationQuerysetMixin, viewsets.ModelViewSet):
    queryset = HotelFAQ.objects.all()
    serializer_class = HotelFAQSerializer

    def perform_create(self, serializer):
        user = self.request.user
        org = None if getattr(user, 'is_superadmin', False) else self._get_organization()
        max_order = HotelFAQ.objects.filter(organization=org).count() if org else HotelFAQ.objects.count()
        serializer.save(organization=org, order=max_order)


class HandoverContactViewSet(OrganizationQuerysetMixin, viewsets.ModelViewSet):
    queryset = HandoverContact.objects.all()
    serializer_class = HandoverContactSerializer

    def perform_create(self, serializer):
        user = self.request.user
        org = None if getattr(user, 'is_superadmin', False) else self._get_organization()
        max_order = HandoverContact.objects.filter(organization=org).count() if org else HandoverContact.objects.count()
        serializer.save(organization=org, order=max_order)


class PlaybookViewSet(OrganizationQuerysetMixin, viewsets.ModelViewSet):
    queryset = Playbook.objects.all()
    serializer_class = PlaybookSerializer

    def perform_create(self, serializer):
        user = self.request.user
        org = None if getattr(user, 'is_superadmin', False) else self._get_organization()
        max_order = Playbook.objects.filter(organization=org).count() if org else Playbook.objects.count()
        serializer.save(organization=org, order=max_order)

    @action(detail=True, methods=['post'], url_path='process-file')
    def process_file(self, request, pk=None):
        """Upload an image or PDF and extract its content using AI vision."""
        uploaded = request.FILES.get('file')
        if not uploaded:
            return Response({'error': 'No file provided.'}, status=status.HTTP_400_BAD_REQUEST)

        mime_type = uploaded.content_type
        if mime_type not in SUPPORTED_MIME_TYPES:
            return Response(
                {'error': f'Unsupported file type: {mime_type}. Supported: images (PNG, JPEG, WEBP) and PDF.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        file_bytes = uploaded.read()
        is_image = mime_type in {'image/png', 'image/jpeg', 'image/jpg', 'image/webp'}

        if is_image:
            extracted = self._extract_image_openai(file_bytes, mime_type)
        else:
            extracted = self._extract_pdf_gemini(file_bytes, mime_type)

        if extracted is None:
            return Response(
                {'error': 'Failed to process file. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response({'content': extracted.strip()})

    def _extract_image_openai(self, file_bytes: bytes, mime_type: str):
        """Extract text/tables from an image using AI vision."""
        try:
            from apps.leads.ai_service import ai_service
            if not ai_service.is_configured():
                logger.error('AI service not configured for image extraction')
                return None
            b64 = base64.b64encode(file_bytes).decode('utf-8')
            response = ai_service.client.chat.completions.create(
                model=ai_service._model,
                messages=[{
                    'role': 'user',
                    'content': [
                        {'type': 'image_url', 'image_url': {'url': f'data:{mime_type};base64,{b64}'}},
                        {'type': 'text', 'text': FILE_EXTRACTION_PROMPT},
                    ],
                }],
                max_tokens=2000,
            )
            return response.choices[0].message.content or ''
        except Exception as e:
            logger.error(f'AI image extraction error: {e}', exc_info=True)
            return None

    def _extract_pdf_gemini(self, file_bytes: bytes, mime_type: str):
        """Extract content from a PDF using Gemini native SDK (supports binary PDF parsing)."""
        try:
            from google import genai
            from google.genai import types
            api_key = os.environ.get('CAYU_GEMINI_API_KEY') or os.environ.get('GEMINI_API_KEY')
            if not api_key:
                logger.error('Gemini API key not configured for PDF extraction')
                return None
            # Use env var override, default to gemini-2.5-flash
            pdf_model = os.environ.get('GEMINI_PDF_MODEL', 'gemini-2.5-flash')
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=pdf_model,
                contents=types.Content(
                    role='user',
                    parts=[
                        types.Part.from_bytes(data=file_bytes, mime_type=mime_type),
                        types.Part.from_text(text=FILE_EXTRACTION_PROMPT),
                    ],
                ),
            )
            return response.text or ''
        except Exception as e:
            logger.error(f'Gemini PDF extraction error: {e}', exc_info=True)
            return None


# Expected Excel column headers (case-insensitive, stripped)
_EXCEL_COL_MAP = {
    # Room category
    'категория номера': 'kategoria_nomera',
    'категория': 'kategoria_nomera',
    'тип номера': 'kategoria_nomera',
    'номер': 'kategoria_nomera',
    'тип': 'kategoria_nomera',
    'наименование': 'kategoria_nomera',
    # Guest count
    'кол-во чел': 'kolichestvo_chelovek',
    'кол-во чел.': 'kolichestvo_chelovek',
    'кол. чел.': 'kolichestvo_chelovek',
    'кол-во': 'kolichestvo_chelovek',
    'кол.': 'kolichestvo_chelovek',
    'чел': 'kolichestvo_chelovek',
    'чел.': 'kolichestvo_chelovek',
    'человек': 'kolichestvo_chelovek',
    'гостей': 'kolichestvo_chelovek',
    'кол-во гостей': 'kolichestvo_chelovek',
    'количество': 'kolichestvo_chelovek',
    'количество человек': 'kolichestvo_chelovek',
    # Valid from
    'действительно с': 'deystvitelno_s',
    'действительно с этой даты': 'deystvitelno_s',
    'действ. с': 'deystvitelno_s',
    'действует с': 'deystvitelno_s',
    'дата начала': 'deystvitelno_s',
    'начало': 'deystvitelno_s',
    # Valid until
    'действительно до': 'deystvitelno_do',
    'действительно до этой даты': 'deystvitelno_do',
    'действ. до': 'deystvitelno_do',
    'действует до': 'deystvitelno_do',
    'дата окончания': 'deystvitelno_do',
    'окончание': 'deystvitelno_do',
    # Weekdays
    'дни недели': 'dni_nedeli',
    'какие дни недели': 'dni_nedeli',
    'дни': 'dni_nedeli',
    'день недели': 'dni_nedeli',
    # Rates
    'стандартный тариф': 'standartny_tarif',
    'стандарт': 'standartny_tarif',
    'стандартный': 'standartny_tarif',
    'без питания': 'standartny_tarif',
    'тариф': 'standartny_tarif',
    'цена': 'standartny_tarif',
    'с завтраком': 's_zavtrakom',
    'завтрак': 's_zavtrakom',
    'bb': 's_zavtrakom',
    'полупансион': 'polupansion',
    'полупансион (обед или ужин)': 'polupansion',
    'hb': 'polupansion',
    'полный пансион': 'polny_pansion',
    'полный пансион (3 раз питание)': 'polny_pansion',
    'полный пансион (3 раза в день)': 'polny_pansion',
    'полный': 'polny_pansion',
    'fb': 'polny_pansion',
}

_WEEKDAY_MAP = {
    'понедельник': 'Понедельник', 'пн': 'Понедельник',
    'вторник': 'Вторник', 'вт': 'Вторник',
    'среда': 'Среда', 'ср': 'Среда',
    'четверг': 'Четверг', 'чт': 'Четверг',
    'пятница': 'Пятница', 'пт': 'Пятница',
    'суббота': 'Суббота', 'сб': 'Суббота',
    'воскресенье': 'Воскресенье', 'вс': 'Воскресенье',
}


def _normalize_header(val) -> str:
    """Normalize an Excel header cell: strip quotes/whitespace, collapse spaces/newlines, lowercase."""
    if val is None:
        return ''
    s = str(val)
    s = s.replace('\n', ' ').replace('\r', ' ')  # flatten multi-line headers
    s = s.strip('"\'')                            # remove surrounding quotes
    s = ' '.join(s.split())                       # collapse multiple spaces to one
    return s.lower().strip()


def _parse_rows_from_html(file_bytes: bytes):
    """Fallback: parse rows from an HTML table saved as .xls."""
    from html.parser import HTMLParser

    class _TableParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.rows = []
            self._row = None
            self._cell = None

        def handle_starttag(self, tag, attrs):
            if tag == 'tr':
                self._row = []
            elif tag in ('td', 'th'):
                self._cell = ''

        def handle_endtag(self, tag):
            if tag in ('td', 'th') and self._row is not None:
                self._row.append(self._cell or '')
                self._cell = None
            elif tag == 'tr' and self._row is not None:
                self.rows.append(tuple(self._row))
                self._row = None

        def handle_data(self, data):
            if self._cell is not None:
                self._cell += data

    parser = _TableParser()
    try:
        parser.feed(file_bytes.decode('utf-8', errors='replace'))
    except Exception:
        return None
    # Return the largest table's rows (tables are separated by None sentinel via headers)
    return parser.rows if parser.rows else None


_RU_MONTHS = {
    'январь': 1, 'января': 1, 'янв': 1,
    'февраль': 2, 'февраля': 2, 'фев': 2,
    'март': 3, 'марта': 3, 'мар': 3,
    'апрель': 4, 'апреля': 4, 'апр': 4,
    'май': 5, 'мая': 5,
    'июнь': 6, 'июня': 6, 'июн': 6,
    'июль': 7, 'июля': 7, 'июл': 7,
    'август': 8, 'августа': 8, 'авг': 8,
    'сентябрь': 9, 'сентября': 9, 'сен': 9, 'сент': 9,
    'октябрь': 10, 'октября': 10, 'окт': 10,
    'ноябрь': 11, 'ноября': 11, 'ноя': 11,
    'декабрь': 12, 'декабря': 12, 'дек': 12,
}


def _parse_excel_date(val):
    """Convert an Excel cell value to ISO date string or None."""
    if val is None or val == '':
        return None
    import datetime
    if isinstance(val, (datetime.date, datetime.datetime)):
        return val.strftime('%Y-%m-%d')
    s = str(val).strip()
    if not s or s == '-' or s == '—':
        return None
    # Standard numeric formats
    for fmt in ('%d.%m.%Y', '%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y'):
        try:
            return datetime.datetime.strptime(s, fmt).strftime('%Y-%m-%d')
        except ValueError:
            pass
    # Russian month name: "Март 1, 2026" or "1 марта 2026" or "1 март 2026"
    import re as _re
    parts = _re.split(r'[\s,]+', s.strip())
    parts = [p.lower() for p in parts if p]
    month_num = None
    day_num = None
    year_num = None
    for p in parts:
        if p in _RU_MONTHS and month_num is None:
            month_num = _RU_MONTHS[p]
        elif p.isdigit():
            num = int(p)
            if 1900 <= num <= 2100 and year_num is None:
                year_num = num
            elif 1 <= num <= 31 and day_num is None:
                day_num = num
    if month_num and day_num and year_num:
        try:
            return datetime.date(year_num, month_num, day_num).strftime('%Y-%m-%d')
        except ValueError:
            pass
    return None


def _parse_decimal(val):
    """Convert cell value to decimal string or None."""
    if val is None or val == '':
        return None
    s = str(val).strip().replace(' ', '').replace('\u00a0', '').replace(',', '.')
    if not s or s == '-' or s == '—':
        return None
    try:
        return str(int(float(s)))
    except (ValueError, TypeError):
        return None


def _parse_days(val):
    """Convert comma/space-separated weekday string to canonical list."""
    if not val:
        return []
    parts = str(val).replace(';', ',').replace('/', ',').split(',')
    result = []
    for p in parts:
        key = p.strip().lower()
        if key in _WEEKDAY_MAP:
            canonical = _WEEKDAY_MAP[key]
            if canonical not in result:
                result.append(canonical)
    return result


def _format_playbook_content(content: str) -> str:
    """Render playbook content blocks for prompt preview."""
    import json as _json
    if not content or not content.strip():
        return ''
    try:
        blocks = _json.loads(content)
        if isinstance(blocks, list) and blocks:
            parts = []
            for block in blocks:
                title = (block.get('title') or '').strip()
                text = (block.get('content') or '').strip()
                if title and text:
                    parts.append(f"### {title}\n{text}")
                elif text:
                    parts.append(text)
            return '\n\n'.join(parts)
    except (ValueError, AttributeError):
        pass
    return content


@api_view(['GET'])
def prompt_preview(request):
    """Assemble and return the static AI system prompt sections as plain text."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    sections = []

    # ─── [PLAYBOOKS] ─────────────────────────────────────────────────
    # Scope preview to the requesting user's current organization
    _preview_org = getattr(getattr(request, 'user', None), 'current_organization', None)
    try:
        from django.utils import timezone as _tz
        from django.db.models import Q as _Q
        _now = _tz.now()
        pb_qs = Playbook.objects.filter(is_active=True).filter(
            _Q(expires_at__isnull=True) | _Q(expires_at__gt=_now)
        )
        if _preview_org is not None:
            pb_qs = pb_qs.filter(organization=_preview_org)
        playbooks = pb_qs.order_by('created_at')
        if playbooks.exists():
            pb_lines = ["[PLAYBOOKS]"]
            for pb in playbooks:
                pb_lines.append(f"\n--- {pb.name} ---")
                if pb.instructions:
                    pb_lines.append(pb.instructions)
                if pb.content:
                    pb_lines.append(_format_playbook_content(pb.content))
            sections.append("\n".join(pb_lines))
        else:
            sections.append("[PLAYBOOKS]\n(no active playbooks)")
    except Exception:
        sections.append("[PLAYBOOKS]\n(error loading)")

    # ─── [PRICING TABLE] ─────────────────────────────────────────────
    try:
        from .pricing_utils import query_room_pricing
        pricing_rows = query_room_pricing()
        if pricing_rows:
            pt_lines = [
                "[PRICING TABLE]",
                "All prices in KGS per night. Each tier is the TOTAL per-room price (room + meals included).",
                "guest_type: 'any' = standard/comfort rooms (suggest first); 'family' = family rooms (suggest only when kids confirmed).",
            ]
            for r in pricing_rows:
                tiers = ", ".join(f"{k}={v}" for k, v in (r.get('prices_per_night_kgs') or {}).items())
                valid = f" | valid {r['valid_from']}–{r['valid_to']}" if r.get('valid_from') and r.get('valid_to') else ""
                days = f" | days: {', '.join(r['weekdays'])}" if r.get('weekdays') else ""
                gtype = f" [guest_type={r.get('guest_type', 'any')}]"
                pt_lines.append(f"  {r['room_type']} (max {r['max_guests']} guests){gtype}{valid}{days}: {tiers}")
            sections.append("\n".join(pt_lines))
        else:
            sections.append("[PRICING TABLE]\n(no pricing data)")
    except Exception:
        sections.append("[PRICING TABLE]\n(error loading)")

    # ─── [FAMILY ROOM POLICY] ─────────────────────────────────────────
    sections.append(
        "[FAMILY ROOM POLICY]\n"
        "ROOM SUGGESTION PRIORITY:\n"
        "1. Always suggest rooms tagged guest_type='any' first (Standard → Comfort order).\n"
        "2. Rooms tagged guest_type='family' are the 3rd alternative at earliest — NEVER suggest them as the 1st or 2nd option.\n"
        "3. Family rooms are ONLY suggested when:\n"
        "   a) Guest explicitly mentions children / kids / ребёнок / дети / балдар (or similar in any language), OR\n"
        "   b) Context strongly implies a family with children, OR\n"
        "   c) No 'any' rooms can accommodate the group size at all.\n"
        "\n"
        "KID DETECTION:\n"
        "- Infer from context: if the guest mentions kids or children → treat as family context.\n"
        "- Ask if unclear: if guest count is 3–4+ people and no mention of children → ask 'Will there be children staying with you?' BEFORE suggesting a family room.\n"
        "- Never ask if the guest has already clearly indicated adult-only or business travel.\n"
        "\n"
        "CHILD POLICY:\n"
        "- One child under 6 is FREE and does NOT count toward guest count.\n"
        "- Two or more children under 6 → recommend a family room.\n"
        "\n"
        "TOOL RESPONSE NOTE:\n"
        "- The get_room_options tool returns combinations with type='Семейный' for family rooms.\n"
        "- Present Семейный options only after confirming kids are present.\n"
        "- Never show Основной / Альтернатива / Семейный labels to the guest — these are internal."
    )

    # ─── Runtime placeholders ─────────────────────────────────────────
    now = datetime.now(ZoneInfo('Asia/Bishkek'))
    sections.append(
        f"[LEAD CONTEXT]\n"
        f"Current date/time: {now.strftime('%A, %d %B %Y, %H:%M')} (Kyrgyzstan, UTC+6)\n"
        f"\u21b3 lead name, source, and booking details injected at runtime"
    )
    sections.append("[ACTIVITY HISTORY]\n\u21b3 full chronological activity log injected at runtime")
    sections.append("[CONVERSATION HISTORY]\n\u21b3 recent chat messages injected at runtime")

    divider = "\n\n" + ("\u2500" * 60) + "\n\n"
    prompt = divider.join(sections)
    return Response({"prompt": prompt})


class RoomPricingViewSet(OrganizationQuerysetMixin, viewsets.ModelViewSet):
    queryset = RoomPricing.objects.all()
    serializer_class = RoomPricingSerializer

    @action(detail=False, methods=['post'], url_path='upload-excel')
    def upload_excel(self, request):
        """
        Parse an uploaded .xlsx file and bulk-create RoomPricing rows.
        The first row must be a header row with Russian column names.
        Returns the number of rows created and a list of skipped rows with reasons.
        """
        uploaded = request.FILES.get('file')
        if not uploaded:
            return Response({'error': 'No file provided.'}, status=status.HTTP_400_BAD_REQUEST)

        filename = uploaded.name.lower()
        if not (filename.endswith('.xlsx') or filename.endswith('.xls')):
            return Response(
                {'error': 'Only .xlsx and .xls files are supported.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        file_bytes = uploaded.read()
        rows = None

        # Strategy 1: real xlsx/xls via openpyxl
        try:
            import openpyxl
            import io as _io
            wb = openpyxl.load_workbook(_io.BytesIO(file_bytes), data_only=True)
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))
        except Exception:
            pass

        # Strategy 2: HTML table saved as .xls (common enterprise export)
        if not rows:
            rows = _parse_rows_from_html(file_bytes)

        if not rows:
            return Response(
                {'error': 'Could not read the file. Please save it as .xlsx from Excel and try again.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(rows) < 2:
            return Response({'error': 'File has no data rows.'}, status=status.HTTP_400_BAD_REQUEST)

        # Find the header row — skip leading empty rows
        header_row_idx = None
        for i, row in enumerate(rows):
            if row and any(cell is not None for cell in row):
                header_row_idx = i
                break

        if header_row_idx is None:
            return Response({'error': 'File has no data rows.'}, status=status.HTTP_400_BAD_REQUEST)

        # Map header row to field names (normalize: collapse newlines/spaces, strip quotes)
        col_index = {}
        for idx, h in enumerate(rows[header_row_idx]):
            field = _EXCEL_COL_MAP.get(_normalize_header(h))
            if field and field not in col_index:
                col_index[field] = idx

        if 'kategoria_nomera' not in col_index:
            found_headers = [_normalize_header(h) for h in rows[header_row_idx] if h is not None]
            logger.warning(f'Room pricing upload: category column not found. Headers: {found_headers}')
            return Response(
                {'error': 'Column "Категория номера" not found. Found headers: ' + ', '.join(found_headers[:10])},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Detect optional "id" column — enables upsert mode instead of replace-all
        id_col_idx = None
        for idx, h in enumerate(rows[header_row_idx]):
            if _normalize_header(h) in ('id', '#', 'номер строки'):
                id_col_idx = idx
                break

        has_id_column = id_col_idx is not None
        user = self.request.user
        upload_org = None if getattr(user, 'is_superadmin', False) else self._get_organization()

        if not has_id_column:
            # No ID column → classic replace: delete all rows for this org first
            org_qs = RoomPricing.objects.filter(organization=upload_org) if upload_org else RoomPricing.objects.all()
            deleted_count, _ = org_qs.delete()
        else:
            deleted_count = 0

        created = []
        updated = []
        skipped = []
        excel_ids = set()

        # Track last seen values to handle merged cells (merged cells return None after first row)
        last_kategoria = ''
        last_deystvitelno_s = None
        last_deystvitelno_do = None
        last_dni_nedeli = None

        for row_num, row in enumerate(rows[header_row_idx + 1:], start=header_row_idx + 2):
            def cell(field, _row=row):
                idx = col_index.get(field)
                return _row[idx] if idx is not None and idx < len(_row) else None

            # Carry forward merged category cells
            raw_kategoria = str(cell('kategoria_nomera') or '').strip()
            if raw_kategoria and raw_kategoria != last_kategoria:
                # New category group — reset date/weekday carry-forwards
                last_kategoria = raw_kategoria
                last_deystvitelno_s = None
                last_deystvitelno_do = None
                last_dni_nedeli = None
            kategoria = last_kategoria

            if not kategoria:
                skipped.append({'row': row_num, 'reason': 'Empty room category'})
                continue

            # Skip rows that look like sub-headers or notes (no price and no guest count)
            kol_raw = cell('kolichestvo_chelovek')
            price_raw = (
                cell('standartny_tarif') or cell('s_zavtrakom') or
                cell('polupansion') or cell('polny_pansion')
            )
            if kol_raw is None and price_raw is None:
                skipped.append({'row': row_num, 'reason': 'No guest count or price data'})
                continue

            try:
                kolichestvo = int(float(str(kol_raw).strip())) if kol_raw not in (None, '') else 1
            except (ValueError, TypeError):
                kolichestvo = 1

            # Carry forward merged date/weekday cells
            s_raw = cell('deystvitelno_s')
            do_raw = cell('deystvitelno_do')
            dni_raw = cell('dni_nedeli')

            if s_raw is not None and s_raw != '':
                last_deystvitelno_s = _parse_excel_date(s_raw)
            if do_raw is not None and do_raw != '':
                last_deystvitelno_do = _parse_excel_date(do_raw)
            if dni_raw is not None and dni_raw != '':
                last_dni_nedeli = _parse_days(dni_raw)

            pricing_fields = dict(
                kategoria_nomera=kategoria,
                kolichestvo_chelovek=max(1, kolichestvo),
                deystvitelno_s=last_deystvitelno_s,
                deystvitelno_do=last_deystvitelno_do,
                dni_nedeli=last_dni_nedeli if last_dni_nedeli is not None else [],
                standartny_tarif=_parse_decimal(cell('standartny_tarif')),
                s_zavtrakom=_parse_decimal(cell('s_zavtrakom')),
                polupansion=_parse_decimal(cell('polupansion')),
                polny_pansion=_parse_decimal(cell('polny_pansion')),
            )

            # Upsert by ID if id column is present
            row_id = None
            if has_id_column and id_col_idx < len(row):
                id_raw = row[id_col_idx]
                try:
                    row_id = int(float(str(id_raw).strip())) if id_raw not in (None, '') else None
                except (ValueError, TypeError):
                    row_id = None

            if row_id:
                try:
                    instance = RoomPricing.objects.get(id=row_id)
                    for k, v in pricing_fields.items():
                        setattr(instance, k, v)
                    instance.save()
                    updated.append(row_id)
                    excel_ids.add(row_id)
                except RoomPricing.DoesNotExist:
                    pricing = RoomPricing(**pricing_fields, organization=upload_org)
                    pricing.save()
                    created.append(pricing.id)
                    excel_ids.add(pricing.id)
            else:
                pricing = RoomPricing(**pricing_fields, organization=upload_org)
                pricing.save()
                created.append(pricing.id)
                if has_id_column:
                    excel_ids.add(pricing.id)

        # In upsert mode: delete rows not referenced by the Excel (org-scoped)
        if has_id_column and excel_ids:
            qs = RoomPricing.objects.exclude(id__in=excel_ids)
            if upload_org:
                qs = qs.filter(organization=upload_org)
            deleted_count, _ = qs.delete()

        return Response({
            'deleted': deleted_count,
            'created': len(created),
            'updated': len(updated),
            'skipped': len(skipped),
            'skipped_details': skipped,
        })


@api_view(['GET'])
def room_combinations(request):
    """
    Return pre-calculated room combinations for all guest counts 1–10.
    Optional ?guest_count=N filters to a single guest count.
    Uses today's date in Bishkek timezone to determine active rates.
    """
    from .pricing_utils import generate_room_combinations, calculate_combination_prices, _build_room_lookup

    org = _get_org(request)
    guest_count_param = request.query_params.get('guest_count')
    data = generate_room_combinations(org=org)

    # Attach notes and stored type overrides from DB; mark auto-generated rows
    # Note: RoomCombinationNote has no organization field — notes are shared globally
    notes_qs = RoomCombinationNote.objects.filter(is_custom=False)
    hidden_keys = {(n.guest_count, n.combination_index) for n in notes_qs if n.is_hidden}
    notes_map = {
        (n.guest_count, n.combination_index): {'note': n.note, 'type': n.combination_type}
        for n in notes_qs
    }
    for gc_entry in data:
        gc_entry['combinations'] = [c for c in gc_entry['combinations']
                                    if (gc_entry['guest_count'], c['index']) not in hidden_keys]
        for combo in gc_entry['combinations']:
            stored = notes_map.get((gc_entry['guest_count'], combo['index']), {})
            combo['note'] = stored.get('note', '')
            if stored.get('type'):
                combo['type'] = stored['type']
            combo['is_custom'] = False
            combo['id'] = None

    # Append custom combinations with live-calculated prices
    # Note: RoomCombinationNote has no organization field — notes are shared globally
    custom_qs = RoomCombinationNote.objects.filter(is_custom=True)
    if custom_qs.exists():
        lookup = _build_room_lookup()
        custom_by_gc: dict = {}
        for c in custom_qs:
            prices_data = calculate_combination_prices(c.rooms or [], room_lookup=lookup)
            custom_by_gc.setdefault(c.guest_count, []).append({
                'id': c.id,
                'index': c.combination_index,
                'rooms': c.rooms or [],
                'room_count': len(c.rooms or []),
                'type': c.combination_type or 'Альтернатива',
                'available': prices_data is not None,
                'prices': prices_data,
                'note': c.note,
                'is_custom': True,
            })
        for gc_entry in data:
            gc_entry['combinations'].extend(custom_by_gc.get(gc_entry['guest_count'], []))

    if guest_count_param is not None:
        try:
            gc = int(guest_count_param)
        except ValueError:
            return Response({'error': 'guest_count must be an integer'}, status=status.HTTP_400_BAD_REQUEST)
        if gc > 10:
            return Response(
                {'error': 'transfer_to_manager', 'message': 'Для групп более 10 человек — передать менеджеру'},
                status=status.HTTP_200_OK,
            )
        data = [entry for entry in data if entry['guest_count'] == gc]

    return Response({'results': data})


@api_view(['GET'])
def room_combination_room_types(request):
    """Return list of unique room type names from RoomPricing."""
    from .models import RoomPricing
    org = _get_org(request)
    qs = RoomPricing.objects.all()
    if org:
        qs = qs.filter(organization=org)
    types = list(qs.values_list('kategoria_nomera', flat=True).distinct().order_by('kategoria_nomera'))
    return Response({'results': types})


@api_view(['POST'])
def create_custom_combination(request):
    """Create a custom room combination for a guest count group."""
    from .pricing_utils import COMBINATIONS_MAP, calculate_combination_prices, _build_room_lookup
    from django.db import models as django_models

    org = _get_org(request)
    guest_count = request.data.get('guest_count')
    rooms = request.data.get('rooms', [])
    combination_type = request.data.get('combination_type', 'Альтернатива')
    note = request.data.get('note', '')

    if not isinstance(guest_count, int) or not (1 <= guest_count <= 10):
        return Response({'error': 'guest_count must be an integer 1–10'}, status=status.HTTP_400_BAD_REQUEST)
    if not rooms or not isinstance(rooms, list):
        return Response({'error': 'rooms must be a non-empty list'}, status=status.HTTP_400_BAD_REQUEST)
    if combination_type not in ('Основной', 'Альтернатива', 'Семейный'):
        return Response({'error': 'combination_type must be Основной, Альтернатива, or Семейный'}, status=status.HTTP_400_BAD_REQUEST)

    # Assign next available combination_index for this guest_count
    auto_count = len(COMBINATIONS_MAP.get(guest_count, []))
    base_qs = RoomCombinationNote.objects.filter(guest_count=guest_count)
    if org:
        base_qs = base_qs.filter(organization=org)
    agg = base_qs.aggregate(max_idx=django_models.Max('combination_index'))
    new_idx = max(auto_count, (agg['max_idx'] or 0) + 1)

    # If new row is Основной, demote all existing Основной rows in the group
    if combination_type == 'Основной':
        demote_qs = RoomCombinationNote.objects.filter(guest_count=guest_count, combination_type='Основной')
        if org:
            demote_qs = demote_qs.filter(organization=org)
        demote_qs.update(combination_type='Альтернатива')

    obj = RoomCombinationNote.objects.create(
        organization=org,
        guest_count=guest_count,
        combination_index=new_idx,
        rooms=rooms,
        combination_type=combination_type,
        note=note,
        is_custom=True,
    )

    lookup = _build_room_lookup(org=org)
    prices_data = calculate_combination_prices(rooms, room_lookup=lookup)

    return Response({
        'id': obj.id,
        'index': obj.combination_index,
        'rooms': obj.rooms,
        'room_count': len(obj.rooms),
        'type': obj.combination_type,
        'available': prices_data is not None,
        'prices': prices_data,
        'note': obj.note,
        'is_custom': True,
    }, status=status.HTTP_201_CREATED)


@api_view(['DELETE'])
def delete_custom_combination(request, pk):
    """Delete a custom combination by its primary key."""
    org = _get_org(request)
    qs = RoomCombinationNote.objects.filter(pk=pk, is_custom=True)
    if org:
        qs = qs.filter(organization=org)
    try:
        obj = qs.get()
    except RoomCombinationNote.DoesNotExist:
        return Response({'error': 'Custom combination not found'}, status=status.HTTP_404_NOT_FOUND)
    obj.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['DELETE'])
def hide_auto_combination(request, guest_count, combination_index):
    """Hide an auto-generated combination so it no longer appears in the API."""
    if not (1 <= guest_count <= 10):
        return Response({'error': 'guest_count must be 1–10'}, status=status.HTTP_400_BAD_REQUEST)
    org = _get_org(request)
    obj, _ = RoomCombinationNote.objects.get_or_create(
        organization=org,
        guest_count=guest_count,
        combination_index=combination_index,
        defaults={'is_custom': False},
    )
    obj.is_hidden = True
    obj.save(update_fields=['is_hidden'])
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['PUT', 'PATCH'])
def room_combination_note(request, guest_count, combination_index):
    """Save or update a custom note or type for a combination row."""
    if not (1 <= guest_count <= 10):
        return Response({'error': 'guest_count must be 1–10'}, status=status.HTTP_400_BAD_REQUEST)
    org = _get_org(request)

    if request.method == 'PATCH':
        combo_type = request.data.get('combination_type')
        if combo_type not in ('Основной', 'Альтернатива', 'Семейный'):
            return Response({'error': 'combination_type must be Основной, Альтернатива, or Семейный'}, status=status.HTTP_400_BAD_REQUEST)

        obj, _ = RoomCombinationNote.objects.update_or_create(
            organization=org,
            guest_count=guest_count,
            combination_index=combination_index,
            defaults={'combination_type': combo_type},
        )
        if combo_type == 'Основной':
            from .pricing_utils import COMBINATIONS_MAP
            group_size = len(COMBINATIONS_MAP.get(guest_count, []))
            for idx in range(group_size):
                if idx != combination_index:
                    existing = RoomCombinationNote.objects.filter(
                        organization=org, guest_count=guest_count, combination_index=idx
                    ).first()
                    if existing is None or existing.combination_type != 'Семейный':
                        RoomCombinationNote.objects.update_or_create(
                            organization=org,
                            guest_count=guest_count,
                            combination_index=idx,
                            defaults={'combination_type': 'Альтернатива'},
                        )
        return Response(RoomCombinationNoteSerializer(obj).data)

    # PUT — update note text
    note_text = request.data.get('note', '')
    obj, _ = RoomCombinationNote.objects.update_or_create(
        organization=org,
        guest_count=guest_count,
        combination_index=combination_index,
        defaults={'note': note_text},
    )
    return Response(RoomCombinationNoteSerializer(obj).data)
