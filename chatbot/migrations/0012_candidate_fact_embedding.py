import django.db.models.deletion
from django.db import migrations, models
from pgvector.django import VectorExtension, VectorField


class Migration(migrations.Migration):
    dependencies = [("chatbot", "0011_candidate_public_fact_fts")]

    operations = [
        VectorExtension(),
        migrations.AlterField(
            model_name="aiusageevent",
            name="operation",
            field=models.CharField(
                choices=[
                    ("candidate_chat", "Candidate chat"),
                    ("knowledge_extraction", "Knowledge extraction"),
                    ("embedding_index", "Embedding index"),
                    ("embedding_query", "Embedding query"),
                ],
                max_length=32,
            ),
        ),
        migrations.CreateModel(
            name="CandidateFactEmbedding",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name="ID"
                    ),
                ),
                ("embedding_model", models.CharField(max_length=127)),
                ("content_sha256", models.CharField(max_length=64)),
                ("vector", VectorField(dimensions=256)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "fact",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="semantic_embedding",
                        to="chatbot.candidatefact",
                    ),
                ),
            ],
        ),
    ]
