import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.hotel_info.models import Playbook
from apps.organizations.models import Organization

ORG_SLUG = 'nomad-camp'

# Follow-up pass fixing gaps missed in the first TOR sync: early check-in /
# late check-out numbers reconciled to the price list, children's documents,
# vegetarian/kids menu note, and the coffee-break menu/price.
PLAYBOOK_UPDATES = {
    6: {
        'expected_name': 'Правила проживания и отмены',
        'block_updates': {
            '1dlmeumlb82': (
                'Заезд и выезд',
                'Заезд: с 14:00\n'
                'Выезд: до 12:00\n\n'
                'Ранний заезд (за доплату):\n'
                '- с 6:00 до 14:00 дня заезда — 50% стоимости ночи\n'
                '- до 6:00 — 100% стоимости ночи\n\n'
                'Поздний выезд (за доплату):\n'
                '- продление проживания до 18:00 текущего дня — 50% стоимости ночи\n'
                '- после 18:00 — 100% стоимости ночи\n\n'
                'Ранний/поздний — по запросу, не гарантирован. Уточнять у менеджера.'
            ),
            'wcsws8y713': (
                'Депозит и документы',
                'Депозит при заселении: не требуется.\n'
                'Документы: паспорт — для всех взрослых гостей.\n'
                'Если ребёнка сопровождают не родители — дополнительно нужны '
                'свидетельство о рождении ребёнка и расписка от законных '
                'представителей (родителей).'
            ),
        },
    },
    7: {
        'expected_name': 'Питание и Nomad Cafe',
        'block_inserts': [
            (
                'children_veg_menu_2026_07',
                'Детское и вегетарианское меню',
                'Специального детского меню нет — детям можно предложить блюда из '
                'общего меню / со стойки.\n'
                'Для вегетарианцев кухня может приготовить отдельно, либо гость может '
                'набрать подходящие блюда из предложенного на стойке.'
            ),
        ],
    },
    9: {
        'expected_name': 'Банкетный зал и конференц-залы',
        'block_inserts': [
            (
                'coffee_break_menu_2026_07',
                'Кофе-брейк: меню и цена',
                'Кофе-брейк — 615 сом с человека.\n'
                'В пакет входит:\n'
                '- Пекарский сет (самсы с курицей, кекс)\n'
                '- Минисеты (минибургеры и минисэндвичи)\n'
                '- Фрешсет (фрукты и овощи на шпажках)\n'
                '- Напитки (чай, кофе, сахар, молоко)'
            ),
        ],
    },
}


class Command(BaseCommand):
    help = (
        'Second-pass fixes for gaps found after the first Nomad Camp TOR sync: '
        'reconcile early check-in / late check-out numbers to the price list, '
        'add children\'s document requirements, vegetarian/kids menu note, and '
        'the coffee-break menu/price.'
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
            for pk, spec in PLAYBOOK_UPDATES.items():
                pb = Playbook.objects.get(organization=org, pk=pk)
                if pb.name != spec['expected_name']:
                    raise CommandError(
                        f'Playbook pk={pk} name mismatch: expected {spec["expected_name"]!r}, got {pb.name!r}'
                    )
                blocks = json.loads(pb.content or '[]')
                by_id = {b['id']: b for b in blocks}
                changed = []

                for block_id, (title, new_content) in spec.get('block_updates', {}).items():
                    block = by_id.get(block_id)
                    if block is None:
                        raise CommandError(f'Expected block id={block_id!r} not found in playbook {pk}')
                    if block.get('content') != new_content:
                        changed.append(block_id)
                        block['title'] = title
                        block['content'] = new_content

                for new_id, new_title, new_content in spec.get('block_inserts', []):
                    if not any(b['id'] == new_id for b in blocks):
                        blocks.append({'id': new_id, 'title': new_title, 'content': new_content})
                        changed.append(new_id)

                self.stdout.write(f'Playbook #{pk} {pb.name}: {len(changed)} block(s) changed: {changed}')
                pb.content = json.dumps(blocks, ensure_ascii=False)
                if not dry_run:
                    pb.save(update_fields=['content', 'updated_at'])

            if dry_run:
                self.stdout.write(self.style.WARNING('DRY RUN — rolling back.'))
                transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS('Done.' if not dry_run else 'Dry run complete.'))
