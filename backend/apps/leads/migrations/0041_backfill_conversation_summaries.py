"""
One-time data migration: generate AI conversation summaries for all leads
that have message activities but no notes yet.

Requires OpenAI to be configured (CAYU_OPENAI_API_KEY or OPENAI_API_KEY).
Skips gracefully if AI is not available or a lead has no message history.
"""
import logging
from django.db import migrations

logger = logging.getLogger(__name__)

_MESSAGING_TYPES = frozenset([
    'telegram_received', 'telegram_sent',
    'instagram_received', 'instagram_sent',
    'whatsapp_received', 'whatsapp_sent',
    'ringcentral_sms_received', 'ringcentral_sms_sent',
])

_ACTIVITY_LABELS = {
    'telegram_received': ('Guest',),
    'instagram_received': ('Guest',),
    'whatsapp_received': ('Guest',),
    'ringcentral_sms_received': ('Guest',),
    'telegram_sent': ('Агент',),
    'instagram_sent': ('Агент',),
    'whatsapp_sent': ('Агент',),
    'ringcentral_sms_sent': ('Агент',),
}


def backfill_conversation_summaries(apps, schema_editor):
    import os
    try:
        from openai import OpenAI
    except ImportError:
        logger.warning("openai not installed — skipping conversation summary backfill")
        return

    api_key = os.environ.get('CAYU_OPENAI_API_KEY') or os.environ.get('OPENAI_API_KEY')
    if not api_key:
        logger.warning("No OpenAI API key found — skipping conversation summary backfill")
        return

    client = OpenAI(api_key=api_key)
    Lead = apps.get_model('leads', 'Lead')
    LeadActivity = apps.get_model('leads', 'LeadActivity')

    system_prompt = (
        "You are a hotel CRM assistant. Given a conversation between a guest and a hotel agent, "
        "write a single factual 10-15 word summary of the current booking inquiry. "
        "Focus on: room type, dates, guest count, meal plan, current conversation stage. "
        "Match the language the guest is using (Russian, Kyrgyz, or English). "
        "Return ONLY the summary — no quotes, no punctuation at the end, no extra text."
    )

    updated = 0
    skipped_no_messages = 0
    skipped_error = 0

    # Only process leads with message activities (don't care about existing notes —
    # backfill overwrites since we can't detect manual edits in a migration)
    leads_with_messages = Lead.objects.filter(
        activities__activity_type__in=list(_MESSAGING_TYPES)
    ).distinct()

    for lead in leads_with_messages.iterator():
        message_activities = list(
            LeadActivity.objects.filter(
                lead=lead,
                activity_type__in=list(_MESSAGING_TYPES),
            ).order_by('created_at')[:60]
        )
        if not message_activities:
            skipped_no_messages += 1
            continue

        lines = []
        for activity in message_activities:
            text = ''
            if activity.metadata and isinstance(activity.metadata, dict):
                text = activity.metadata.get('text', '') or activity.metadata.get('message', '')
            if not text:
                text = activity.description or ''
            if not text:
                continue
            role = _ACTIVITY_LABELS.get(activity.activity_type, ('Агент',))[0]
            lines.append(f"{role}: {text[:200]}")

        if not lines:
            skipped_no_messages += 1
            continue

        conversation = '\n'.join(lines)
        try:
            response = client.chat.completions.create(
                model='gpt-4o-mini',
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': conversation},
                ],
                max_tokens=60,
                temperature=0.2,
                timeout=15,
            )
            summary = response.choices[0].message.content.strip().strip('"\'')
            if summary:
                Lead.objects.filter(id=lead.id).update(notes=summary)
                updated += 1
        except Exception as e:
            logger.warning(f"Failed to generate summary for lead {lead.id}: {e}")
            skipped_error += 1

    print(
        f"  Conversation summary backfill: {updated} updated, "
        f"{skipped_no_messages} skipped (no messages), "
        f"{skipped_error} skipped (API error)"
    )


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0040_backfill_last_contacted'),
    ]

    operations = [
        migrations.RunPython(backfill_conversation_summaries, migrations.RunPython.noop),
    ]
