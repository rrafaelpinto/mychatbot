import json
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction

from chatbot.models import CandidateFact, CandidateProfile
from chatbot.services.ai import NoVerifiedFacts, ask_candidate

SYNTHETIC_MANIFEST = (
    Path(__file__).parent / "fixtures" / "synthetic_candidate_facts.json"
)


def import_facts(candidate, manifest=SYNTHETIC_MANIFEST, *, dry_run=False):
    output = StringIO()
    call_command(
        "import_candidate_facts",
        candidate=candidate.slug,
        file=str(manifest),
        dry_run=dry_run,
        stdout=output,
    )
    return output.getvalue()


def write_manifest(tmp_path, facts):
    path = tmp_path / "facts.json"
    path.write_text(json.dumps({"version": 1, "facts": facts}), encoding="utf-8")
    return path


@pytest.mark.django_db
def test_import_creates_private_pending_facts_and_is_idempotent(published_candidate):
    assert "5 new" in import_facts(published_candidate)
    facts = CandidateFact.objects.filter(candidate=published_candidate)
    assert facts.count() == 5
    assert all(
        f.verification_status == CandidateFact.VerificationStatus.PENDING for f in facts
    )
    assert all(not f.is_public for f in facts)
    assert all(f.import_key for f in facts)
    assert "5 unchanged" in import_facts(published_candidate)
    assert facts.count() == 5


@pytest.mark.django_db
def test_dry_run_validates_without_writing(published_candidate):
    assert "Dry run: 5 new" in import_facts(published_candidate, dry_run=True)
    assert not CandidateFact.objects.filter(candidate=published_candidate).exists()


@pytest.mark.django_db
def test_import_preserves_review_and_rejects_changed_content(
    published_candidate, tmp_path
):
    import_facts(published_candidate)
    fact = CandidateFact.objects.get(
        candidate=published_candidate, import_key="summary-backend"
    )
    fact.verification_status = CandidateFact.VerificationStatus.VERIFIED
    fact.is_public = True
    fact.full_clean()
    fact.save()

    assert "5 unchanged" in import_facts(published_candidate)
    fact.refresh_from_db()
    assert fact.is_public

    changed = [
        {
            "key": "summary-backend",
            "type": "summary",
            "content": "Changed professional claim.",
        }
    ]
    with pytest.raises(CommandError, match="different existing data"):
        import_facts(published_candidate, write_manifest(tmp_path, changed))
    fact.refresh_from_db()
    assert fact.content != "Changed professional claim."
    assert fact.is_public


@pytest.mark.django_db
def test_conflict_rolls_back_entire_import(published_candidate, tmp_path):
    import_facts(published_candidate)
    manifest = write_manifest(
        tmp_path,
        [
            {"key": "new-item", "type": "skill", "content": "Example skill."},
            {
                "key": "summary-backend",
                "type": "summary",
                "content": "Different claim.",
            },
        ],
    )
    with pytest.raises(CommandError, match="different existing data"):
        import_facts(published_candidate, manifest)
    assert not CandidateFact.objects.filter(import_key="new-item").exists()


@pytest.mark.django_db
def test_import_key_is_scoped_to_candidate(published_candidate, other_user):
    other = CandidateProfile.objects.create(user=other_user, name="Other Candidate")
    import_facts(published_candidate)
    import_facts(other)
    assert CandidateFact.objects.filter(import_key="summary-backend").count() == 2


@pytest.mark.django_db
@pytest.mark.parametrize(
    "payload",
    [
        {"version": 2, "facts": []},
        {
            "version": 1,
            "facts": [
                {
                    "key": "foo",
                    "type": "skill",
                    "content": "x",
                    "verification_status": "verified",
                }
            ],
        },
        {
            "version": 1,
            "facts": [
                {"key": "foo", "type": "skill", "content": "x", "is_public": True}
            ],
        },
        {
            "version": 1,
            "facts": [
                {"key": "foo", "type": "skill", "content": "x"},
                {"key": "foo", "type": "skill", "content": "y"},
            ],
        },
        {"version": 1, "facts": [{"key": "foo", "type": "unknown", "content": "x"}]},
        {"version": 1, "facts": [{"key": "../foo", "type": "skill", "content": "x"}]},
        {"version": 1, "facts": [{"key": "foo", "type": "skill", "content": "  "}]},
    ],
)
def test_invalid_manifest_fails_closed(published_candidate, tmp_path, payload):
    path = tmp_path / "facts.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(CommandError):
        import_facts(published_candidate, path)
    assert not CandidateFact.objects.exists()


@pytest.mark.django_db
def test_missing_candidate_is_rejected(tmp_path):
    manifest = write_manifest(
        tmp_path, [{"key": "skill", "type": "skill", "content": "An example."}]
    )
    with pytest.raises(CommandError, match="does not exist"):
        call_command(
            "import_candidate_facts", candidate="no-such-candidate", file=str(manifest)
        )


@pytest.mark.django_db
def test_private_verified_fact_never_reaches_provider(published_candidate, recruiter):
    CandidateFact.objects.create(
        candidate=published_candidate,
        fact_type=CandidateFact.FactType.SKILL,
        content="Private professional detail",
        verification_status=CandidateFact.VerificationStatus.VERIFIED,
    )
    with patch("chatbot.services.ai.invoke_candidate_chat") as provider:
        with pytest.raises(NoVerifiedFacts):
            ask_candidate(
                candidate=published_candidate,
                initiated_by=recruiter,
                question="What are your skills?",
            )
    provider.assert_not_called()


@pytest.mark.django_db
def test_public_fact_must_be_verified(published_candidate):
    fact = CandidateFact(
        candidate=published_candidate,
        fact_type=CandidateFact.FactType.SKILL,
        content="Unreviewed",
        is_public=True,
    )
    with pytest.raises(ValidationError, match="Only verified"):
        fact.full_clean()
    with pytest.raises(IntegrityError), transaction.atomic():
        CandidateFact.objects.create(
            candidate=published_candidate,
            fact_type=CandidateFact.FactType.SKILL,
            content="Unreviewed",
            is_public=True,
        )
