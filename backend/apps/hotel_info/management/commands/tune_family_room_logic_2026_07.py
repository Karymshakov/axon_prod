import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.hotel_info.models import Playbook
from apps.organizations.models import Organization

ORG_SLUG = 'nomad-camp'

PLAYBOOK_PK = 5
EXPECTED_NAME = 'Номера (что продаем)'

BLOCK_UPDATES = {
    'y8npm9nxkv': (
        'Типы номеров и вместимость',
        'Стандарт Квин — 1 двуспальная кровать, 2 человека. Всего: 15 номеров.\n'
        'Стандарт Твин — 2 раздельные кровати, 2 человека. Всего: 95 номеров.\n'
        'Комфорт — просторный номер, двуспальная кровать + диван в отдельной комнате + '
        'мини-кухня. 2 человека. Всего: 5 номеров.\n'
        'Семейный — 2 смежных номера (Квин + Твин), соединены дверью. До 4 человек. Всего: '
        '5 номеров.\n\n'
        'Итого: 120 номеров.\n\n'
        'Когда предлагать Семейный номер:\n'
        '— гость сам спросил про такой тип номера или явно сказал, что хочет жить вместе '
        'как одна группа из 3+ человек (например: «хотим заселиться вчетвером все '
        'вместе»);\n'
        '— в семье есть ребёнок примерно 7–17 лет — он обычно уже не может спать в одной '
        'кровати с родителями, но и отдельный номер для него — не лучший вариант; предложи '
        'Семейный номер как способ остаться вместе, назвав цену, и одновременно можно '
        'показать вариант с раздельными номерами — пусть гость выберет сам.\n\n'
        'Когда НЕ предлагать Семейный номер:\n'
        '— маленький ребёнок (примерно до 7 лет), который может остаться в комнате с '
        'родителями — тут нужна не Семейный номер, а доп. кровать/детский манеж (см. блок '
        '«Доп. место и детские кроватки»).'
    ),
    'lqg8o30tpq': (
        'Доп. место и детские кроватки',
        'Раскладушка — 1500 сом/сутки.\n'
        'Детский манеж — 500 сом/сутки.\n'
        'Подходит, когда ребёнку (примерно до 7 лет) нужно доп. место, но он может '
        'находиться в одной комнате с родителями.\n'
        'Для детей постарше (примерно 7–17 лет) или когда гости прямо хотят жить одной '
        'группой — смотри блок «Типы номеров и вместимость»: там уместнее Семейный номер.'
    ),
}


class Command(BaseCommand):
    help = (
        'Replace the overly rigid "only on literal request" family-room instructions in '
        'Playbook #5 with age-based / explicit-togetherness guidance, matching the '
        're-enabled get_family_room tool logic in booking_tools.py.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        try:
            org = Organization.objects.get(slug=ORG_SLUG)
        except Organization.DoesNotExist:
            raise CommandError(f'Organization with slug={ORG_SLUG!r} not found')

        with transaction.atomic():
            pb = Playbook.objects.get(organization=org, pk=PLAYBOOK_PK)
            if pb.name != EXPECTED_NAME:
                raise CommandError(f'Playbook pk={PLAYBOOK_PK} name mismatch: got {pb.name!r}')

            blocks = json.loads(pb.content or '[]')
            by_id = {b['id']: b for b in blocks}
            changed = []
            for block_id, (title, new_content) in BLOCK_UPDATES.items():
                block = by_id.get(block_id)
                if block is None:
                    raise CommandError(f'Expected block id={block_id!r} not found')
                if block.get('content') != new_content:
                    changed.append(block_id)
                    block['title'] = title
                    block['content'] = new_content

            self.stdout.write(f'Playbook #{PLAYBOOK_PK}: {len(changed)} block(s) changed: {changed}')
            pb.content = json.dumps(blocks, ensure_ascii=False)
            if not dry_run:
                pb.save(update_fields=['content', 'updated_at'])

            if dry_run:
                self.stdout.write(self.style.WARNING('DRY RUN — rolling back.'))
                transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS('Done.' if not dry_run else 'Dry run complete.'))
