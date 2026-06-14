from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0064_lead_channel_and_discovery_source'),
    ]

    operations = [
        migrations.AlterField(
            model_name='leadgoal',
            name='goal_type',
            field=models.CharField(
                choices=[
                    ('collect_email', 'Collect Email'),
                    ('collect_phone', 'Collect Phone'),
                    ('collect_guest_name', 'Collect Guest Name'),
                    ('collect_discovery_source', 'Collect Discovery Source'),
                    ('schedule_call', 'Schedule Call'),
                    ('schedule_meeting', 'Schedule Meeting'),
                    ('send_proposal', 'Send Proposal'),
                    ('send_info', 'Send Information'),
                    ('handle_objection', 'Handle Objection'),
                    ('close_deal', 'Close Deal'),
                    ('qualify_lead', 'Qualify Lead'),
                    ('get_decision_maker', 'Get Decision Maker'),
                ],
                max_length=30,
            ),
        ),
    ]
