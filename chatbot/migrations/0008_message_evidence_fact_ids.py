from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("chatbot", "0007_guest_chat")]

    operations = [
        migrations.AddField(
            model_name="message",
            name="evidence_fact_ids",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
