import json
import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from chatbot.models import CandidateFact, CandidateProfile

MAX_FILE_BYTES = 1_000_000
MAX_FACTS = 100
MAX_CONTENT_LENGTH = 4_000
KEY_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}$")


def read_manifest(path: str) -> list[dict[str, str]]:
    try:
        file = Path(path)
        if file.stat().st_size > MAX_FILE_BYTES:
            raise CommandError("Fact manifest exceeds the size limit.")
        payload = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise CommandError("Cannot read a valid UTF-8 JSON fact manifest.") from exc

    if (
        not isinstance(payload, dict)
        or set(payload) != {"version", "facts"}
        or type(payload["version"]) is not int
        or payload["version"] != 1
        or not isinstance(payload["facts"], list)
        or not 1 <= len(payload["facts"]) <= MAX_FACTS
    ):
        raise CommandError("Invalid fact manifest format or version.")

    facts = []
    keys = set()
    for index, item in enumerate(payload["facts"], start=1):
        if (
            not isinstance(item, dict)
            or not {"key", "type", "content"} <= set(item)
            or set(item) - {"key", "type", "content", "source_reference"}
        ):
            raise CommandError(f"Invalid fields in fact #{index}.")

        key = item["key"]
        fact_type = item["type"]
        content = item["content"]
        source_reference = item.get("source_reference", "")

        if not isinstance(key, str) or not KEY_PATTERN.fullmatch(key):
            raise CommandError(f"Invalid key in fact #{index}.")
        if key in keys:
            raise CommandError(f"Duplicate import key in fact #{index}.")
        if fact_type not in CandidateFact.FactType.values:
            raise CommandError(f"Invalid type in fact #{index}.")
        if (
            not isinstance(content, str)
            or not content.strip()
            or len(content) > MAX_CONTENT_LENGTH
        ):
            raise CommandError(f"Invalid content in fact #{index}.")
        if not isinstance(source_reference, str) or len(source_reference) > 255:
            raise CommandError(f"Invalid source reference in fact #{index}.")

        keys.add(key)
        facts.append(
            {
                "import_key": key,
                "fact_type": fact_type,
                "content": content.strip(),
                "source_reference": source_reference.strip(),
            }
        )
    return facts


class Command(BaseCommand):
    """Import private, pending candidate facts without overwriting reviewed facts."""

    help = "Import candidate facts as pending and private; never auto-verify or publish."

    def add_arguments(self, parser):
        parser.add_argument("--candidate", required=True, help="Existing candidate slug")
        parser.add_argument("--file", required=True, help="Private JSON manifest path")
        parser.add_argument("--dry-run", action="store_true", help="Validate without writing")

    def handle(self, *args, **options):
        facts = read_manifest(options["file"])
        dry_run = options["dry_run"]
        with transaction.atomic():
            try:
                candidate = CandidateProfile.objects.select_for_update().get(
                    slug=options["candidate"]
                )
            except CandidateProfile.DoesNotExist as exc:
                raise CommandError("Candidate does not exist.") from exc

            existing = {
                fact.import_key: fact
                for fact in CandidateFact.objects.filter(
                    candidate=candidate,
                    import_key__in=[item["import_key"] for item in facts],
                )
            }
            created = 0
            unchanged = 0
            for item in facts:
                current = existing.get(item["import_key"])
                if current is not None:
                    if any(
                        getattr(current, field) != value for field, value in item.items()
                    ):
                        raise CommandError(
                            f"Import key '{item['import_key']}' has different existing data."
                        )
                    unchanged += 1
                    continue

                fact = CandidateFact(candidate=candidate, **item)
                fact.full_clean()
                if not dry_run:
                    fact.save()
                created += 1

        self.stdout.write(
            f"{'Dry run: ' if dry_run else ''}{created} new, {unchanged} unchanged; "
            "imported facts remain pending and private."
        )
