import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("chatbot", "0008_message_evidence_fact_ids")]

    operations = [
        migrations.AlterField(
            model_name="aiusageevent",
            name="operation",
            field=models.CharField(
                choices=[
                    ("candidate_chat", "Candidate chat"),
                    ("knowledge_extraction", "Knowledge extraction"),
                ],
                max_length=32,
            ),
        ),
        migrations.CreateModel(
            name="CandidateExtractionRun",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("source_sha256", models.CharField(max_length=64)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("running", "Running"),
                            ("succeeded", "Succeeded"),
                            ("failed", "Failed"),
                        ],
                        default="running",
                        max_length=16,
                    ),
                ),
                ("attempts", models.PositiveSmallIntegerField(default=1)),
                ("started_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("proposed_count", models.PositiveSmallIntegerField(default=0)),
                ("error_code", models.CharField(blank=True, max_length=64)),
                (
                    "document",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="extraction_run",
                        to="chatbot.candidatedocument",
                    ),
                ),
                (
                    "last_usage_event",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="chatbot.aiusageevent",
                    ),
                ),
            ],
        ),
    ]
