from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0060_aiconfig_channel_ai_pause_fields'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='lead',
                    name='custom_fields',
                    field=models.JSONField(blank=True, default=dict),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="""
                    DO $$ 
                    BEGIN 
                      IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='leads_lead' AND column_name='custom_fields') THEN 
                        ALTER TABLE leads_lead ADD COLUMN custom_fields jsonb NOT NULL DEFAULT '{}'::jsonb; 
                      ELSE
                        ALTER TABLE leads_lead ALTER COLUMN custom_fields SET DEFAULT '{}';
                      END IF; 
                    END $$;
                    """,
                    reverse_sql="ALTER TABLE leads_lead DROP COLUMN IF EXISTS custom_fields;",
                ),
            ],
        ),
    ]
