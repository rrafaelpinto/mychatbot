from django.conf import settings
from django.db import migrations


def backfill(apps, schema_editor):
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
    Account = apps.get_model("chatbot", "AccountAccess")
    Profile = apps.get_model("chatbot", "CandidateProfile")
    seen = set()
    candidates = set(Profile.objects.values_list("user_id", flat=True))
    for user in User.objects.order_by("pk").iterator():
        email = user.email.strip().lower() or None
        if email in seen:
            raise RuntimeError("Resolve duplicate account emails before migrating.")
        if email:
            seen.add(email)
        Account.objects.create(user_id=user.pk, email=email, role="candidate" if user.pk in candidates else "recruiter")


class Migration(migrations.Migration):
    dependencies = [("chatbot", "0013_emailchallenge_accountaccess")]
    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
