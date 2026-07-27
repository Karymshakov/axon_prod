<!--
  ФАЙЛ: _lead_extractor.md
  ИСПОЛЬЗУЕТСЯ: extract_lead_data() в ai_service.py
  ЧТО ДЕЛАЕТ AI: Читает переписку и извлекает структурированные данные о брони/госте.
  ПЛЕЙСХОЛДЕРЫ: {today}, {tomorrow}, {day_after_tomorrow} подставляются автоматически.
  ИЗМЕНЯТЬ: Можно менять описания полей, добавлять примеры, корректировать правила парсинга дат.
  НЕ МЕНЯТЬ: Названия полей в JSON (company_name, contact_person, phone и т.д.) — они привязаны к базе данных.
  НЕ МЕНЯТЬ: Список допустимых значений meal_plan (none/breakfast/lunch/dinner/half_board_bl/half_board_bd/full_board).
  НЕ УДАЛЯТЬ: Блок "IMPORTANT RULES" — он предотвращает заполнение пустых полей заглушками.
-->

Today's date: {today} (Kyrgyzstan time, UTC+6). Tomorrow is {tomorrow}.

Extract the following information about the CUSTOMER from the conversation:
- company_name (the CUSTOMER's company, NOT the company they are contacting)
- contact_person (the CUSTOMER's name)
- phone (the CUSTOMER's phone number)
- email (the CUSTOMER's email address)
- problem_description (a brief summary of the customer's need or request — what they are looking for, in their own words)
- preferred_contact_time (the best time or day the customer mentions for a call or meeting, e.g. "Tomorrow at 4pm", "Weekday mornings")
- check_in_date (the guest's intended check-in date in YYYY-MM-DD format; parse natural language relative to TODAY ({today}): "завтра"/"tomorrow"/"на завтра" = {tomorrow}; "послезавтра"/"day after tomorrow" = {day_after_tomorrow}; "сегодня"/"today" = {today}; "15 июля" = that date in the current year)
- check_out_date (the guest's intended check-out date in YYYY-MM-DD format; same parsing rules as check_in_date; DURATION INFERENCE: if the guest states a duration like "только один день", "одну ночь", "один день", "two nights", "3 дня", "три ночи", etc., compute check_out_date = check_in_date + N days where N is the number of nights/days mentioned — e.g. "только один день"/"одну ночь" → check_out = check_in + 1 day, "два дня"/"две ночи" → check_out = check_in + 2 days; apply this ONLY when check_in_date is determinable from the conversation)
- guest_count (total people including adults and children)
- adult_count (number of adults, only when clear from context)
- children_ages (JSON array with each child's age in years; decimals for infants)
- infant_count (number of children under one year)
- one_room_required (true only when the guest explicitly requires one room)
- room_type_preference (preferred room type mentioned, e.g. "Deluxe Balcony", "семейный номер", "стандарт", "люкс")
- meal_plan (meal plan preference — return ONLY one of these exact values: "none", "breakfast", "lunch", "dinner", "half_board_bl", "half_board_bd", "full_board"; map guest's words like "завтрак" → "breakfast", "завтрак и обед" → "half_board_bl", "завтрак и ужин" → "half_board_bd", "всё включено" → "full_board")
{exclusion_instruction}

LANGUAGE NOTE: The conversation may be in Russian, Kyrgyz, English, or a mix of these. Extract information regardless of the language used. Return text field values in the exact language the customer used (except meal_plan and dates which must follow the exact formats above).

IMPORTANT RULES:
1. Only extract information that the CUSTOMER (role: "user") explicitly provides about THEMSELVES
2. Do NOT extract company names mentioned by the assistant/bot — those are OUR company
3. Review ALL messages to gather complete information
4. If a field is mentioned multiple times, use the MOST RECENT value from the customer
5. CRITICAL: Do NOT include placeholder values! If information is not provided, OMIT the field entirely.
   - Never use: "не указано", "Не указано", "not specified", "not provided", "N/A", "n/a", "unknown", "Unknown", "-", "none", "None", "null", "белгисиз", "жок", "айтылган жок", or any similar placeholder
   - Only include REAL data that the customer actually provided
6. If the customer gives only day numbers/range without a month (for example "с 1 по 7") and no month is clear from nearby customer messages, OMIT check_in_date/check_out_date. Never assume January.

Return JSON with keys: company_name, contact_person, phone, email, problem_description, preferred_contact_time, check_in_date, check_out_date, guest_count, adult_count, children_ages, infant_count, one_room_required, room_type_preference, meal_plan.
OMIT any field where no REAL customer-provided information is found. Empty or placeholder values are NOT acceptable.

Example format:
{
  "contact_person": "Алия",
  "phone": "+996700123456",
  "check_in_date": "2026-07-15",
  "check_out_date": "2026-07-20",
  "guest_count": 3,
  "adult_count": 2,
  "children_ages": [0.17],
  "infant_count": 1,
  "one_room_required": true,
  "room_type_preference": "стандарт с балконом",
  "meal_plan": "half_board_bd",
  "problem_description": "Хотим отдохнуть на Иссык-Куле всей семьёй",
  "preferred_contact_time": "вечером после 18:00"
}
