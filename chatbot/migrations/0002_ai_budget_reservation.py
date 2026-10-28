# Generated for Phase 2 budget reservation.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("chatbot", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="aiusageevent",
            name="reserved_micro_usd",
            field=models.PositiveBigIntegerField(default=0),
        ),
        migrations.CreateModel(
            name="AIProjectBudget",
            fields=[
                (
                    "id",
                    models.PositiveSmallIntegerField(
                        default=1, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("daily_window", models.DateField()),
                ("monthly_window", models.DateField()),
                ("daily_reserved_micro_usd", models.PositiveBigIntegerField(default=0)),
                ("monthly_reserved_micro_usd", models.PositiveBigIntegerField(default=0)),
            ],
        ),
    ]
