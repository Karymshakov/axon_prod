"""
Management command: seed the pre-built "Hotel Individual Booking" starter flow.
Safe to run multiple times — skips creation if a flow with that name already exists.
"""
from django.core.management.base import BaseCommand
from apps.flows.models import ConversationFlow, FlowCard, FlowConnection


CARDS = [
    {
        'key': 'welcome',
        'card_type': 'entry',
        'title': 'Welcome & Greeting',
        'message_template': (
            'Hello {contact_person}! 👋 Welcome to our hotel. '
            'I saw your inquiry and I\'m happy to help you plan your stay. '
            'Could you tell me your preferred check-in and check-out dates?'
        ),
        'position_x': 100,
        'position_y': 50,
    },
    {
        'key': 'collect_dates',
        'card_type': 'normal',
        'title': 'Collect Dates & Guests',
        'message_template': (
            'Great! And how many guests will be staying? '
            'Also, do you have any room preferences or special requirements?'
        ),
        'position_x': 100,
        'position_y': 250,
    },
    {
        'key': 'suggest_room',
        'card_type': 'normal',
        'title': 'Room Suggestion',
        'message_template': (
            'Based on {num_guests} guests from {check_in_date} to {check_out_date}, '
            'I recommend: {room_suggestion}\n\n'
            'The total cost would be approximately {total_price}. '
            'Does this sound good to you?'
        ),
        'position_x': 100,
        'position_y': 450,
    },
    {
        'key': 'confirm_booking',
        'card_type': 'normal',
        'title': 'Confirm Booking',
        'message_template': (
            'Wonderful! To finalize your reservation, I\'ll need a few more details:\n'
            '• Full name on the booking\n'
            '• Contact phone number\n'
            '• Any special requests (early check-in, dietary needs, etc.)\n\n'
            'Once I have these, I can send you a formal booking confirmation.'
        ),
        'position_x': 100,
        'position_y': 650,
    },
    {
        'key': 'send_confirmation',
        'card_type': 'normal',
        'title': 'Send Confirmation',
        'message_template': (
            'Perfect, {contact_person}! Your booking is confirmed. 🎉\n\n'
            'Check-in: {check_in_date}\n'
            'Check-out: {check_out_date}\n'
            'Room: {room_suggestion}\n'
            'Total: {total_price}\n\n'
            'We\'ll send a detailed confirmation to your email. '
            'Is there anything else I can help you with?'
        ),
        'position_x': 100,
        'position_y': 850,
    },
    {
        'key': 'alternative_dates',
        'card_type': 'normal',
        'title': 'Offer Alternative Dates',
        'message_template': (
            'I understand those dates might not work perfectly. '
            'We have great availability in nearby dates — '
            'would you like me to check alternatives? '
            'Just let me know your flexible date range.'
        ),
        'position_x': 450,
        'position_y': 450,
    },
    {
        'key': 'special_offers',
        'card_type': 'normal',
        'title': 'Share Special Offers',
        'message_template': (
            'We actually have some great special offers right now! '
            'I can share our current promotions and packages. '
            'Would you like me to send you our special rates for {check_in_date}?'
        ),
        'position_x': 450,
        'position_y': 650,
    },
    {
        'key': 'closing_no_booking',
        'card_type': 'normal',
        'title': 'Friendly Close',
        'message_template': (
            'No problem at all, {contact_person}! '
            'Whenever you\'re ready to book, feel free to reach out — '
            'I\'ll be happy to assist. Have a wonderful day! 😊'
        ),
        'position_x': 450,
        'position_y': 850,
    },
    {
        'key': 'escalation',
        'card_type': 'escalation',
        'title': 'Escalate to Staff',
        'message_template': (
            'I\'d like to connect you with one of our senior team members '
            'who can better assist with your specific needs. '
            'Please hold on for just a moment — someone will be with you shortly.'
        ),
        'position_x': 800,
        'position_y': 450,
    },
]

CONNECTIONS = [
    # Main path
    {'source': 'welcome', 'target': 'collect_dates', 'label': '', 'keywords': ''},
    {'source': 'collect_dates', 'target': 'suggest_room', 'label': 'Dates provided', 'keywords': 'january,february,march,april,may,june,july,august,september,october,november,december'},
    {'source': 'suggest_room', 'target': 'confirm_booking', 'label': 'Interested', 'keywords': 'yes,great,perfect,sounds good,confirm,ok,interested,book'},
    {'source': 'confirm_booking', 'target': 'send_confirmation', 'label': 'Details provided', 'keywords': ''},
    # Alternative path
    {'source': 'suggest_room', 'target': 'alternative_dates', 'label': 'Needs other dates', 'keywords': 'no,different,other,change,not available,alternative'},
    {'source': 'alternative_dates', 'target': 'special_offers', 'label': '', 'keywords': ''},
    {'source': 'special_offers', 'target': 'closing_no_booking', 'label': 'Not interested', 'keywords': 'no thanks,not now,later,maybe later'},
    # Escalation
    {'source': 'suggest_room', 'target': 'escalation', 'label': 'Needs human', 'keywords': 'human,person,staff,manager,call,speak,talk,complaint'},
]


class Command(BaseCommand):
    help = 'Seed the pre-built Hotel Individual Booking starter flow'

    def handle(self, *args, **options):
        if ConversationFlow.objects.filter(name='Hotel Individual Booking').exists():
            self.stdout.write(self.style.WARNING('Starter flow already exists — skipping.'))
            return

        flow = ConversationFlow.objects.create(
            name='Hotel Individual Booking',
            description='Guides a lead from first contact through room selection and booking confirmation.',
            is_active=False,
        )
        self.stdout.write(f'Created flow: {flow.name} (id={flow.id})')

        card_map = {}
        for card_data in CARDS:
            key = card_data.pop('key')
            card = FlowCard.objects.create(flow=flow, **card_data)
            card_map[key] = card
            self.stdout.write(f'  + Card: {card.title}')

        for conn_data in CONNECTIONS:
            source = card_map[conn_data['source']]
            target = card_map[conn_data['target']]
            FlowConnection.objects.create(
                flow=flow,
                source_card=source,
                target_card=target,
                condition_label=conn_data['label'],
                condition_keywords=conn_data['keywords'],
            )
            self.stdout.write(f'  → {source.title} → {target.title}')

        self.stdout.write(self.style.SUCCESS(
            f'\nStarter flow seeded successfully! {len(CARDS)} cards, {len(CONNECTIONS)} connections.'
        ))
