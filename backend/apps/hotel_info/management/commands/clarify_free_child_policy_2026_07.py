import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.hotel_info.models import Playbook
from apps.organizations.models import Organization

ORG_SLUG = 'nomad-camp'

# Closes a real loophole: a large number of free (<=6y) children could hide
# behind the adult count and always get quoted a single room, no matter how
# many bodies actually need to sleep somewhere. Sales confirmed: if children
# end up needing a separate room, that room is a normal paid room regardless
# of their age. Code enforces this (see guest_structure.py); these playbook
# edits make the AI explain the rule instead of silently under-quoting.
PLAYBOOK_UPDATES = {
    1: {
        'expected_name': 'Цены, тарифы и что входит',
        'block_updates': {
            '4ofgddwb62t': (
                'Скидки',
                '1. Дети до 6 лет размещаются бесплатно — но только пока вся семья '
                'помещается в одном номере вместе со взрослыми, без отдельного '
                'номера. Если из-за количества гостей (включая детей до 6 лет) '
                'требуется дополнительный номер — этот номер оплачивается по '
                'обычному тарифу своей категории, независимо от возраста тех, кто '
                'в нём поселится. Если свободных детей много (например, 3 и более) '
                'и семья явно не помещается в один номер — сообщи об этом гостю и '
                'озвучь стоимость дополнительного номера отдельно, не занижай '
                'цену.\n'
                '2. Спортивные группы: При заезде спортивных групп проживание '
                'тренера предоставляется бесплатно.'
            ),
        },
    },
    6: {
        'expected_name': 'Правила проживания и отмены',
        'block_updates': {
            'rui0q14s0i': (
                'Дети, животные, курение',
                'ДЕТИ:\n'
                'До 6 лет включительно — проживание бесплатно, но только пока они '
                'помещаются в одном номере с родителями (без отдельного номера).\n'
                'Доп. спальное место в том же номере: раскладушка — 1500 сом/сутки, '
                'детский манеж — 500 сом/сутки.\n'
                'Если количество гостей (включая детей до 6 лет) требует '
                'ОТДЕЛЬНОГО номера — этот номер оплачивается по обычному тарифу, '
                'независимо от возраста тех, кто в нём будет жить. Бесплатное '
                'размещение не распространяется на дополнительный номер.\n\n'
                'ЖИВОТНЫЕ:\n'
                'Разрешены животные до 10 кг.\n'
                'Доплата: 800 сомов за проживание.\n'
                'Нельзя: в зоны питания (F&B), нарушать покой гостей.\n'
                'Специальных условий (миски, корм, пелёнки) нет — всё своё.\n\n'
                'КУРЕНИЕ:\n'
                'Запрещено: в номерах, на балконах, в коридорах, игровых комнатах '
                'и общих зонах.\n'
                'Разрешено: только в специальной зоне у входа в отель.'
            ),
        },
    },
}


class Command(BaseCommand):
    help = (
        'Clarify the free-under-6-children policy: free only while sharing a '
        'room with parents; an extra room needed to fit everyone is a normal '
        'paid room regardless of the occupants\' ages.'
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
                for block_id, (title, new_content) in spec['block_updates'].items():
                    block = by_id.get(block_id)
                    if block is None:
                        raise CommandError(f'Expected block id={block_id!r} not found in playbook {pk}')
                    if block.get('content') != new_content:
                        changed.append(block_id)
                        block['title'] = title
                        block['content'] = new_content

                self.stdout.write(f'Playbook #{pk} {pb.name}: {len(changed)} block(s) changed: {changed}')
                pb.content = json.dumps(blocks, ensure_ascii=False)
                if not dry_run:
                    pb.save(update_fields=['content', 'updated_at'])

            if dry_run:
                self.stdout.write(self.style.WARNING('DRY RUN — rolling back.'))
                transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS('Done.' if not dry_run else 'Dry run complete.'))
