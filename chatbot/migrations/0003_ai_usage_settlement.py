from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("chatbot", "0002_ai_budget_reservation")]

    operations = [
        migrations.AddField(
            model_name="aiusageevent",
            name="actual_micro_usd",
            field=models.PositiveBigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="aiusageevent",
            name="settled_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
