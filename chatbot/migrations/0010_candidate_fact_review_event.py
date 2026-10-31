import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("chatbot", "0009_knowledge_extraction"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CandidateFactReviewEvent",
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
                (
                    "action",
                    models.CharField(
                        choices=[
                            ("edited", "Edited"),
                            ("approved", "Approved"),
                            ("rejected", "Rejected"),
                            ("reopened", "Reopened"),
                            ("published", "Published"),
                            ("unpublished", "Unpublished"),
                        ],
                        max_length=16,
                    ),
                ),
                (
                    "previous_status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending review"),
                            ("verified", "Verified"),
                            ("rejected", "Rejected"),
                        ],
                        max_length=16,
                    ),
                ),
                (
                    "new_status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending review"),
                            ("verified", "Verified"),
                            ("rejected", "Rejected"),
                        ],
                        max_length=16,
                    ),
                ),
                ("previous_public", models.BooleanField()),
                ("new_public", models.BooleanField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "fact",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="review_events",
                        to="chatbot.candidatefact",
                    ),
                ),
                (
                    "reviewed_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="candidate_fact_reviews",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
    ]
