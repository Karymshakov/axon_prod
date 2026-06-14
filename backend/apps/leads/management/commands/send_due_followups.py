"""
Management command: send all due AI follow-ups immediately.

Use this in development (without Celery running):
    python manage.py send_due_followups

In production, Celery beat handles this every 30 minutes automatically.
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Send all due AI-scheduled follow-ups (development shortcut for Celery beat)'

    def handle(self, *args, **options):
        from apps.leads.agent_service import agent_service
        self.stdout.write('Checking for due follow-ups...')
        results = agent_service.run_agent_check()
        self.stdout.write(self.style.SUCCESS(
            f'Done — processed={results["processed"]} '
            f'messaged={results["messaged"]} '
            f'skipped={results["skipped"]} '
            f'errors={results["errors"]}'
        ))
        if results.get('disabled'):
            self.stdout.write(self.style.WARNING(
                'Proactive outreach is disabled in AI Config. '
                'Enable it in Settings → AI Configuration → Proactive Outreach.'
            ))
        if results.get('ai_not_configured'):
            self.stdout.write(self.style.ERROR(
                'AI service not configured. Check GEMINI_API_KEY or OPENAI_API_KEY in .env'
            ))
