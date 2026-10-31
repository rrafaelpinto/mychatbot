from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("chatbot", "0010_candidate_fact_review_event")]

    operations = [
        migrations.AddIndex(
            model_name="candidatefact",
            index=GinIndex(
                SearchVector("content", config="english"),
                name="candidate_public_fact_fts",
                condition=models.Q(
                    verification_status="verified", is_public=True
                ),
            ),
        ),
    ]
