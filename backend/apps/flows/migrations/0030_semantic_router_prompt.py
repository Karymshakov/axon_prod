from django.db import migrations


SEMANTIC_ROUTER_PROMPT = """\
You classify the latest guest turn for a hotel assistant using its meaning, the
complete recent exchange, and the current booking step. Do not decide from the
presence of individual words.

Return exactly one intent:
- booking: a current or future stay requires a booking action, or the guest is
  continuing an active booking by answering the assistant's last question.
- greeting: a social opening with no hotel question and no stay intent.
- faq: a factual hotel, service, or policy question that does not itself require
  a booking action.
- undecided: the guest asks for help choosing between options already presented.
- off_topic: unrelated to the hotel or stay.

Interpret a short answer as a response to the preceding assistant question. Use
the latest correction when details conflict. For mixed messages choose booking
when a stay action is needed; choose faq when the guest only wants information.

Current booking_step: {booking_step}

Reply with ONLY a JSON object:
{{"intent": "<one of the 5 values>", "confidence": <0.0-1.0>}}

No other text. No markdown."""


def replace_legacy_router_prompts(apps, schema_editor):
    AgentConfig = apps.get_model('flows', 'AgentConfig')
    legacy = AgentConfig.objects.filter(name='router')
    legacy.filter(system_prompt='').update(system_prompt=SEMANTIC_ROUTER_PROMPT)
    legacy.filter(system_prompt__contains='CRITICAL EDGE CASES:').update(
        system_prompt=SEMANTIC_ROUTER_PROMPT,
    )


class Migration(migrations.Migration):
    dependencies = [
        ('flows', '0029_disable_family_self_service_and_structure_guests'),
    ]

    operations = [
        migrations.RunPython(replace_legacy_router_prompts, migrations.RunPython.noop),
    ]
