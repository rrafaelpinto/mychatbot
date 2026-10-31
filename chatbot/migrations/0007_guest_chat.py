import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("chatbot", "0006_candidate_fact_import_visibility")]

    operations = [
        migrations.CreateModel(
            name="GuestOrigin",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("digest", models.CharField(max_length=64, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="GuestChatSession",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField()),
                ("in_flight_until", models.DateTimeField(blank=True, null=True)),
                ("candidate", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="guest_sessions", to="chatbot.candidateprofile")),
                ("origin", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="sessions", to="chatbot.guestorigin")),
                ("active_usage", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="chatbot.aiusageevent")),
            ],
        ),
        migrations.AlterField(
            model_name="conversation",
            name="recruiter",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="candidate_conversations", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="conversation",
            name="guest_session",
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="conversation", to="chatbot.guestchatsession"),
        ),
        migrations.AddConstraint(
            model_name="conversation",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(recruiter__isnull=False, guest_session__isnull=True)
                    | models.Q(recruiter__isnull=True, guest_session__isnull=False)
                ),
                name="conversation_exactly_one_identity",
            ),
        ),
        migrations.AlterField(
            model_name="aiusageevent",
            name="initiated_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="ai_usage_events", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="aiusageevent",
            name="guest_session",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="usage_events", to="chatbot.guestchatsession"),
        ),
        migrations.AddField(
            model_name="aiusageevent",
            name="guest_origin",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="usage_events", to="chatbot.guestorigin"),
        ),
        migrations.AddConstraint(
            model_name="aiusageevent",
            constraint=models.UniqueConstraint(fields=("guest_session", "candidate", "operation", "idempotency_key"), name="unique_guest_request_idempotency_key"),
        ),
        migrations.AddConstraint(
            model_name="aiusageevent",
            constraint=models.CheckConstraint(
                condition=(models.Q(initiated_by__isnull=True) | models.Q(guest_origin__isnull=True)),
                name="ai_usage_identity_not_mixed",
            ),
        ),
    ]
