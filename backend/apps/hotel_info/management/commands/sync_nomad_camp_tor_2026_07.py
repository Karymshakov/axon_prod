import json
from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.hotel_info.models import Playbook, RoomPricing
from apps.leads.models import AIConfig
from apps.organizations.models import Organization

ORG_SLUG = 'nomad-camp'

# --- Room pricing -----------------------------------------------------------
# New model: breakfast is always included in the base rate (no more "no meal"
# tier). standartny_tarif == s_zavtrakom == base rate. polupansion/polny_pansion
# add 1300 som per guest per extra meal (lunch / lunch+dinner).
ROOM_PRICING_UPDATES = [
    # (kategoria_nomera, kolichestvo_chelovek, base, half_board, full_board)
    ('стандарт одноместный', 1, 5600, 6900, 8200),
    ('стандарт двухместный', 2, 8200, 10800, 13400),
    ('комфорт одноместный', 1, 8500, 9800, 11100),
    ('комфорт двухместный', 2, 11000, 13600, 16200),
    ('семейный два номера', 4, 16000, 21200, 26400),
]
ROOM_PRICING_NEW_VALID_TO = date(2026, 10, 1)
ROOM_PRICING_DELETE = ('семейный один номер', 2)

# --- Playbook content updates -------------------------------------------------
PLAYBOOK_UPDATES = {
    1: {
        'expected_name': 'Цены, тарифы и что входит',
        'block_updates': {
            'rr6vq8enzne': (
                'Политика отмены',
                '1. Бесплатная отмена: не позднее чем за 72 часа (3 суток) до заезда\n'
                '2. Поздняя отмена (менее чем за 48 часов до заезда): удерживается '
                'стоимость одних суток проживания по тарифу забронированной категории '
                'номера\n'
                'AI-ассистент не должен обсуждать исключения из этого правила.'
            ),
            'hjzmzm0dtd7': (
                'Тарифы проживания (питание)',
                '#Завтрак уже включён в стоимость проживания в любом тарифе — это '
                'базовое условие, не апгрейд.\n'
                '#Дополнительно можно докупить:\n'
                '- Обед (12:00–14:00) — 1300 сом с человека\n'
                '- Ужин (18:00–20:00) — 1300 сом с человека\n'
                '#Если гость хочет и обед, и ужин — это аналог полного пансиона '
                '(завтрак + обед + ужин).\n'
                '#Время питания:\n'
                '- Завтрак: 08:00 – 10:00\n'
                '- Обед: 12:00 – 14:00\n'
                '- Ужин: 18:00 – 20:00\n\n'
                'AI-ассистент никогда не предлагает тариф "без завтрака" — завтрак '
                'включён в проживание всегда, гость выбирает только нужны ли ему ещё '
                'обед и/или ужин.'
            ),
        },
    },
    5: {
        'expected_name': 'Номера (что продаем)',
        'block_updates': {
            'y8npm9nxkv': (
                'Типы номеров и вместимость',
                'Стандарт Квин — 1 двуспальная кровать, 2 человека. Всего: 15 номеров.\n'
                'Стандарт Твин — 2 раздельные кровати, 2 человека. Всего: 95 номеров.\n'
                'Комфорт — просторный номер, двуспальная кровать + диван в отдельной '
                'комнате + мини-кухня. 2 человека. Всего: 5 номеров.\n'
                'Семейный — 2 смежных номера (Квин + Твин), соединены дверью. До 4 '
                'человек. Всего: 5 номеров.\n\n'
                'Итого: 120 номеров.\n\n'
                '⚠️ Семейный номер упоминай ТОЛЬКО если гость сам спросил про такой тип '
                'номера или явно описал сценарий проживания вчетвером вместе '
                '(например: «а есть у вас семейный номер», «хотим заселиться вчетвером '
                'все вместе»). Не предлагай его самостоятельно в обычном подборе '
                'вариантов.'
            ),
            'lqg8o30tpq': (
                'Доп. место и детские кроватки',
                'Раскладушка — 1500 сом/сутки.\n'
                'Детский манеж — 500 сом/сутки.\n'
                'Предлагай эти варианты, если гостю нужно доп. место для ребёнка — не '
                'предлагай Семейный номер вместо этого (Семейный — только по прямому '
                'запросу, см. блок «Типы номеров и вместимость»).'
            ),
            'zxe0yochl4f': (
                'Что нельзя обещать',
                '— Конкретный номер или этаж\n'
                '— Гарантированный вид на озеро или горы\n'
                '— Тихий номер'
            ),
        },
    },
    6: {
        'expected_name': 'Правила проживания и отмены',
        'block_updates': {
            'y14av4k8xtk': (
                'Отмена и no-show',
                'Бесплатная отмена: не позднее чем за 72 часа (3 суток) до заезда.\n'
                'Отмена менее чем за 48 часов до заезда: удерживается стоимость одних '
                'суток проживания по тарифу забронированной категории номера.\n\n'
                'No-show (не приехали без предупреждения): бронь сгорает, оплата брони '
                'не возвращается.\n'
                'Перенос даты возможен — только при предварительной договорённости до '
                'истечения срока отмены.\n\n'
                'Нестандартные ситуации решаются индивидуально — передай запрос '
                'менеджеру.'
            ),
            'rui0q14s0i': (
                'Дети, животные, курение',
                'ДЕТИ:\n'
                'До 6 лет включительно — проживание бесплатно (без отдельного места).\n'
                'Доп. место: раскладушка — 1500 сом/сутки, детский манеж — 500 '
                'сом/сутки.\n\n'
                'ЖИВОТНЫЕ:\n'
                'Разрешены животные до 10 кг.\n'
                'Доплата: 800 сомов за проживание.\n'
                'Нельзя: в зоны питания (F&B), нарушать покой гостей.\n'
                'Специальных условий (миски, корм, пелёнки) нет — всё своё.\n\n'
                'КУРЕНИЕ:\n'
                'Запрещено: в номерах, на балконах, в коридорах, игровых комнатах и '
                'общих зонах.\n'
                'Разрешено: только в специальной зоне у входа в отель.'
            ),
        },
    },
    7: {
        'expected_name': 'Питание и Nomad Cafe',
        'block_updates': {
            '6213s0e5v36': (
                'Nomad Cafe',
                'Завтрак включён в стоимость проживания и подаётся комплексно '
                '(08:00–10:00).\n'
                'Обед (12:00–14:00) и ужин (18:00–20:00) можно докупить отдельно — '
                '1300 сом с человека за приём пищи.\n'
                'Кафе к заказу (a la carte) пока не работает — только комплексное '
                'питание по расписанию. Предупреждайте ресепшн заранее, если хотите '
                'докупить обед и/или ужин.'
            ),
            'separate_meal_price_policy': (
                'Цены на отдельное питание',
                'Обед и ужин — фиксированная цена 1300 сом с человека за приём пищи, '
                'независимо от типа номера. Называй эту цену прямо, не нужно '
                'перенаправлять вопрос менеджеру.'
            ),
        },
    },
    8: {
        'expected_name': 'Спорт-блок, бассейн и развлечения',
        'new_instructions': (
            'Отвечай по блокам ниже — бассейн и спорт-блок полностью работают, '
            'называй точные цены и часы работы. Спортивные сборы и командные пакеты '
            '— только через отдел продаж, не называй условия и цены самостоятельно.'
        ),
        'block_updates': {
            '35qeb73213n': (
                'PlayStation',
                'PlayStation 5 — 2 приставки, по 2 геймпада на каждую (итого 4 '
                'геймпада).\n'
                'Игры: UFC, Mortal Kombat, FIFA.\n'
                'Цена: 200 сом/час.'
            ),
        },
        'block_inserts': [
            (
                'sportblock_general_2026_07',
                'Спортивный блок и бассейн',
                'Бассейн: 25 м, 6 дорожек, крытый, 25°C.\n'
                'Строго в шапочках, очках, плавательных купальниках/плавках.\n'
                'Также в спорт-блоке: тренажёрный зал с кардио-зоной, зона силовых '
                'тренировок, зона татами (единоборства), парилка.\n'
                'Часы работы спорт-блока и бассейна: 07:00 – 23:00.\n'
                'Лимит по времени посещения — по выбранному абонементу (см. цены '
                'ниже).'
            ),
            (
                'sportblock_pricing_2026_07',
                'Цены на спорт-блок',
                'Для гостей отеля / для внешних гостей:\n'
                '1 день — 800 / 1000 сом\n'
                '3 дня — 1600 / 2000 сом\n'
                '7 дней — 3000 / 3800 сом\n'
                '12 посещений в месяц (3 раза в неделю) — 6400 / 8000 сом\n'
                '30 дней — 8000 / 10000 сом\n'
                '90 дней — 21600 / 27000 сом\n'
                'Дневной абонемент (12:00 – 14:00) — 7200 / 9000 сом\n'
                'Секции выходного дня (8 посещений в месяц) — 4500 / 5600 сом\n'
                'Детская секция плавания (12 занятий в месяц) — 4000 / 4000 сом'
            ),
            (
                'padel_football_2026_07',
                'Падел-корт и футбольное поле',
                'Падел-корт — 2000 сом/час.\n'
                'Футбольное поле — 800 сом/час.'
            ),
        ],
    },
    9: {
        'expected_name': 'Банкетный зал и конференц-залы',
        'block_updates': {
            'i8bzcgsenbi': (
                'Залы и вместимость',
                'Банкетный зал — 250 чел., 400 кв.м.\n'
                'Можно использовать как конференц-зал.\n'
                'Расстановку столов можно менять под формат мероприятия.\n\n'
                'Малый конференц-зал — 20 чел., 36 кв.м.\n'
                'Расстановку столов также можно менять.'
            ),
            'jgun9m6xw9k': (
                'Стоимость аренды',
                'Конференц-зал (малый, 20 чел.):\n'
                '- Целый день (24 ч) — 15 000 сом\n'
                '- Полдня (9 ч) — 8 000 сом\n'
                '- Почасово — 1 500 сом/час\n\n'
                'Банкетный/ивент-зал (250 чел.):\n'
                '- Целый день (24 ч) — 50 000 сом\n'
                '- 9 часов — 30 000 сом\n'
                '- Почасово — 6 000 сом/час\n\n'
                'Дополнительно к аренде зала:\n'
                '- Аренда аппаратуры (звук, проектор и т.д.) — 6 000 сом за '
                'мероприятие\n'
                '- Аренда колонки JBL с микрофоном — 1 000 сом за мероприятие\n\n'
                'Минимальное количество гостей на банкет: от 10 человек.\n'
                'Банкетное меню — уточняй у менеджера (есть PDF с пакетами).'
            ),
            '9p5rlqc0lmt': (
                'Условия бронирования залов',
                'Предоплата: 20% от суммы — для подтверждения брони.\n'
                'Подтверждение: не позднее чем за 3 дня до мероприятия.\n\n'
                'Отмена/перенос:\n'
                '- До 10 дней — предоплата возвращается полностью\n'
                '- За 3–10 дней — удерживается 50% предоплаты\n'
                '- Менее 3 дней — удерживается 100% предоплаты'
            ),
        },
    },
    10: {
        'expected_name': 'Как сейчас приходят заявки и как вы их обрабатываете',
        'block_updates': {
            'imijmyp314o': (
                'Шаблон подтверждения после сбора данных',
                'Отлично, принял вашу заявку! Передаю менеджеру — он оформит бронь и '
                'пришлёт вам ваучер.\n\n'
                'Напоминаем:\n'
                '👶 Дети до 6 лет — бесплатно (без отдельного спального места)\n'
                '👦 От 6 лет и старше — по полной стоимости\n'
                '✅ Бесплатная парковка\n'
                '✅ Wi-Fi на всей территории\n'
                '🏊 Бассейн, тренажёрный зал и спорт-блок — доступны\n'
                '🍴 Столовая на территории\n'
                '🏝 Пляж — в 5 минутах пешком\n\n'
                'Спасибо, что выбрали Nomad Camp! 🙏'
            ),
        },
    },
    12: {
        'expected_name': 'Спектр услуг',
        'block_updates': {
            'yc5ep8icxxj': (
                'Activity-зоны',
                '— Детская игровая комната — бесплатно, открывается по запросу\n'
                '— Компьютерная комната (CS 2, CS 1.6, Minecraft, PUBG) — 150 '
                'сом/час\n'
                '— Комната PlayStation 5 — 200 сом/час\n'
                '— Recovery-зона — скоро открытие\n'
                '— Коворкинг — скоро открытие'
            ),
            'tjylw3enb6m': (
                'Залы и мероприятия',
                '— Банкетный зал: тренинги, тимбилдинги, форумы, корпоративы, '
                'свадьбы, частные мероприятия\n'
                '— Малый конференц-зал: до 20 человек, с ТВ\n'
                '— Кофе-брейки: доступны под заказ\n'
                '— Помощь в организации мероприятий любого формата (для юр. лиц)'
            ),
        },
        'block_inserts': [
            (
                'extra_services_2026_07',
                'Дополнительные услуги',
                '— Костёр (средний) — 5000 сом\n'
                '— Костёр (большой) — 7000 сом\n'
                '— Услуги прачечной (полный пакет) — 500 сом\n'
                '— Услуги прачечной (половина пакета) — 300 сом\n'
                '— Утеря ключ-карты (штраф) — 300 сом'
            ),
        ],
    },
}

PLAYBOOK_DELETE = ('Мивида', 16)
PLAYBOOK_EXPIRE = ('Nomad Run Camp', 15, date(2026, 4, 20))

COMPANY_PROFILE_LINK_OLD = (
    '- LINK: Alway send this 2GIS link along with address - https://go.2gis.com/zQ3MW'
)
COMPANY_PROFILE_LINK_NEW = (
    '- LINK: Alway send this 2GIS link along with address - https://go.2gis.com/sm9b6\n'
    '- Google Maps: https://maps.app.goo.gl/rJeAqoArKKrJ7L2E8\n'
    '- Yandex Maps: https://yandex.com/maps/-/CPaAbBnO'
)


def _apply_block_updates(blocks, block_updates):
    changed = []
    by_id = {b['id']: b for b in blocks}
    for block_id, (title, new_content) in block_updates.items():
        block = by_id.get(block_id)
        if block is None:
            raise CommandError(f'Expected block id={block_id!r} not found (playbook content drifted?)')
        if block.get('content') != new_content or block.get('title') != title:
            changed.append((block_id, block.get('title'), title))
            block['title'] = title
            block['content'] = new_content
    return changed


class Command(BaseCommand):
    help = (
        'One-off sync of Nomad Camp room pricing / playbooks / company profile '
        'to match the July 2026 client TOR + price list. See '
        'C:\\Users\\user\\.claude\\plans\\parsed-discovering-mist.md for the full spec.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Print changes without saving')

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        try:
            org = Organization.objects.get(slug=ORG_SLUG)
        except Organization.DoesNotExist:
            raise CommandError(f'Organization with slug={ORG_SLUG!r} not found')
        except Organization.MultipleObjectsReturned:
            raise CommandError(f'Multiple organizations with slug={ORG_SLUG!r} — aborting')

        self.stdout.write(self.style.NOTICE(f'Target organization: {org.name} (id={org.id})'))

        with transaction.atomic():
            self._sync_room_pricing(org, dry_run)
            self._sync_playbooks(org, dry_run)
            self._sync_company_profile(org, dry_run)

            if dry_run:
                self.stdout.write(self.style.WARNING('DRY RUN — rolling back transaction, nothing saved.'))
                transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS('Done.' if not dry_run else 'Dry run complete.'))

    def _sync_room_pricing(self, org, dry_run):
        self.stdout.write(self.style.NOTICE('\n== RoomPricing =='))
        for kategoria, kolvo, base, half, full in ROOM_PRICING_UPDATES:
            row = RoomPricing.objects.filter(
                organization=org,
                kategoria_nomera__iexact=kategoria,
                kolichestvo_chelovek=kolvo,
            ).first()
            if row is None:
                raise CommandError(f'RoomPricing row not found: {kategoria!r} x{kolvo}')
            before = (row.standartny_tarif, row.s_zavtrakom, row.polupansion, row.polny_pansion, row.deystvitelno_do)
            after = (base, base, half, full, ROOM_PRICING_NEW_VALID_TO)
            self.stdout.write(f'  id={row.id} {kategoria} x{kolvo}: {before} -> {after}')
            row.standartny_tarif = base
            row.s_zavtrakom = base
            row.polupansion = half
            row.polny_pansion = full
            row.deystvitelno_do = ROOM_PRICING_NEW_VALID_TO
            if not dry_run:
                row.save(update_fields=[
                    'standartny_tarif', 's_zavtrakom', 'polupansion', 'polny_pansion',
                    'deystvitelno_do', 'updated_at',
                ])

        del_kategoria, del_kolvo = ROOM_PRICING_DELETE
        del_row = RoomPricing.objects.filter(
            organization=org,
            kategoria_nomera__iexact=del_kategoria,
            kolichestvo_chelovek=del_kolvo,
        ).first()
        if del_row is None:
            self.stdout.write(self.style.WARNING(f'  (already absent) {del_kategoria} x{del_kolvo}'))
        else:
            self.stdout.write(f'  DELETE id={del_row.id} {del_kategoria} x{del_kolvo}')
            if not dry_run:
                del_row.delete()

    def _sync_playbooks(self, org, dry_run):
        self.stdout.write(self.style.NOTICE('\n== Playbooks =='))
        for pk, spec in PLAYBOOK_UPDATES.items():
            try:
                pb = Playbook.objects.get(organization=org, pk=pk)
            except Playbook.DoesNotExist:
                raise CommandError(f'Playbook pk={pk} not found for {org}')
            if pb.name != spec['expected_name']:
                raise CommandError(
                    f'Playbook pk={pk} name mismatch: expected {spec["expected_name"]!r}, got {pb.name!r}'
                )
            blocks = json.loads(pb.content or '[]')
            changed = _apply_block_updates(blocks, spec.get('block_updates', {}))
            for new_id, new_title, new_content in spec.get('block_inserts', []):
                if not any(b['id'] == new_id for b in blocks):
                    blocks.append({'id': new_id, 'title': new_title, 'content': new_content})
                    changed.append((new_id, None, new_title))

            new_instructions = spec.get('new_instructions')
            instructions_changed = new_instructions is not None and new_instructions != pb.instructions

            if changed or instructions_changed:
                self.stdout.write(f'  #{pk} {pb.name}: {len(changed)} block(s) changed'
                                   + (', instructions updated' if instructions_changed else ''))
                for block_id, old_title, new_title in changed:
                    self.stdout.write(f'    - {block_id}: {old_title!r} -> {new_title!r}')
                pb.content = json.dumps(blocks, ensure_ascii=False)
                if instructions_changed:
                    pb.instructions = new_instructions
                if not dry_run:
                    pb.save(update_fields=['content', 'instructions', 'updated_at'])
            else:
                self.stdout.write(f'  #{pk} {pb.name}: no changes')

        del_name, del_pk = PLAYBOOK_DELETE
        try:
            pb = Playbook.objects.get(organization=org, pk=del_pk)
        except Playbook.DoesNotExist:
            self.stdout.write(self.style.WARNING(f'  (already absent) playbook #{del_pk} {del_name!r}'))
        else:
            if pb.name != del_name:
                raise CommandError(f'Playbook pk={del_pk} name mismatch: expected {del_name!r}, got {pb.name!r}')
            self.stdout.write(f'  DELETE #{del_pk} {del_name!r}')
            if not dry_run:
                pb.delete()

        expire_name, expire_pk, expire_date = PLAYBOOK_EXPIRE
        try:
            pb = Playbook.objects.get(organization=org, pk=expire_pk)
        except Playbook.DoesNotExist:
            raise CommandError(f'Playbook pk={expire_pk} ({expire_name!r}) not found')
        if pb.name != expire_name:
            raise CommandError(f'Playbook pk={expire_pk} name mismatch: expected {expire_name!r}, got {pb.name!r}')
        expires_at = timezone.make_aware(
            timezone.datetime(expire_date.year, expire_date.month, expire_date.day)
        )
        self.stdout.write(f'  #{expire_pk} {expire_name}: expires_at -> {expires_at.isoformat()}')
        pb.expires_at = expires_at
        if not dry_run:
            pb.save(update_fields=['expires_at', 'updated_at'])

    def _sync_company_profile(self, org, dry_run):
        self.stdout.write(self.style.NOTICE('\n== AIConfig.company_profile =='))
        cfg = AIConfig.objects.filter(organization=org).first()
        if cfg is None:
            raise CommandError('AIConfig not found for organization')
        if COMPANY_PROFILE_LINK_OLD not in (cfg.company_profile or ''):
            if COMPANY_PROFILE_LINK_NEW in (cfg.company_profile or ''):
                self.stdout.write('  links already up to date')
                return
            raise CommandError('Expected 2GIS link line not found in company_profile — content drifted, aborting')
        self.stdout.write('  replacing 2GIS link line, adding Google/Yandex map links')
        cfg.company_profile = cfg.company_profile.replace(COMPANY_PROFILE_LINK_OLD, COMPANY_PROFILE_LINK_NEW)
        if not dry_run:
            cfg.save(update_fields=['company_profile'])
