from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("chatbot", "0005_ai_price_snapshot"),
    ]

    operations = [
        migrations.AddField(
            model_name="candidatefact",
            name="is_public",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="candidatefact",
            name="import_key",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AddConstraint(
            model_name="candidatefact",
            constraint=models.UniqueConstraint(
                fields=("candidate", "import_key"),
                name="unique_candidate_fact_import_key",
            ),
        ),
        migrations.AddConstraint(
            model_name="candidatefact",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(is_public=False)
                    | models.Q(verification_status="verified")
                ),
                name="public_fact_must_be_verified",
            ),
        ),
    ]
