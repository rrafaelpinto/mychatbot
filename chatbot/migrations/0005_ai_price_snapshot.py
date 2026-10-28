from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("chatbot", "0004_ai_idempotency")]

    operations = [
        migrations.AddField(
            model_name="aiusageevent",
            name="input_price_per_million",
            field=models.DecimalField(
                blank=True, decimal_places=6, max_digits=12, null=True
            ),
        ),
        migrations.AddField(
            model_name="aiusageevent",
            name="output_price_per_million",
            field=models.DecimalField(
                blank=True, decimal_places=6, max_digits=12, null=True
            ),
        ),
    ]
