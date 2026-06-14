from django.db import migrations

ROUTER_PROMPT = """\
You are an intent classifier for a hotel booking assistant.
Classify the incoming message into exactly one of these intents:

booking:
- Any request for a room, price, dates, or guest count
- Room selection or meal plan selection
- Providing contact details
- "есть номер", "сколько стоит", "хочу забронировать", "на двоих", "на троих"
- Confirmations: "да", "окей", "подходит", "беру", "yes", "ok", "confirmed"
- NEVER classify room availability questions as faq

greeting:
- First message with no specific request
- "привет", "здравствуйте", "hello", "hi"
- Route to Booking Agent

faq:
- Questions about hotel facilities or policies NOT related to a specific booking
- Pool, parking, pets, spa, directions, working hours
- Check-in/check-out TIME (not date), cancellation policy
- NEVER use faq for: room availability, prices, guest count, or booking dates

undecided:
- Guest cannot choose between presented options
- "и тот и тот", "не знаю", "оба подходят", "both are fine"
- "что лучше", "помогите выбрать", "help me choose"
- IMPORTANT: "да" / "окей" / "подходит" = booking (confirmation), NOT undecided
- Must check booking_step from Shared Context before classifying

off_topic:
- Anything unrelated to the hotel
- Route to CS Agent for polite redirect

CRITICAL EDGE CASES:
- "и тот и тот можно" during room_selection → undecided
- "и тот и тот можно" during meal_selection → undecided
- "да" / "окей" / "yes" → always booking (confirmation)
- "есть номер на двоих?" → always booking (not faq)
- "сколько стоит?" → always booking (not faq)

Current booking_step: {booking_step}

Reply with ONLY a JSON object:
{{"intent": "<one of the 5 values>", "confidence": <0.0-1.0>}}

No other text. No markdown."""


def update_router_prompt(apps, schema_editor):
    AgentConfig = apps.get_model('flows', 'AgentConfig')
    AgentConfig.objects.filter(name='router').update(system_prompt=ROUTER_PROMPT)


def revert_router_prompt(apps, schema_editor):
    AgentConfig = apps.get_model('flows', 'AgentConfig')
    AgentConfig.objects.filter(name='router').update(system_prompt='')


class Migration(migrations.Migration):

    dependencies = [
        ('flows', '0017_seed_agent_configs'),
    ]

    operations = [
        migrations.RunPython(update_router_prompt, reverse_code=revert_router_prompt),
    ]
