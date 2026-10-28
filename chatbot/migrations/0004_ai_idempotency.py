from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("chatbot", "0003_ai_usage_settlement")]

    operations = [
        migrations.AddField(
            model_name="aiusageevent",
            name="idempotency_key",
            field=models.CharField(blank=True, max_length=128, null=True),
        ),
        migrations.AddConstraint(
            model_name="aiusageevent",
            constraint=models.UniqueConstraint(
                fields=("initiated_by", "candidate", "operation", "idempotency_key"),
                name="unique_ai_request_idempotency_key",
            ),
        ),
    ]
