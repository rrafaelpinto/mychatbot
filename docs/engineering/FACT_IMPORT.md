# Candidate Fact Import

Candidate facts are private until explicitly verified and approved for public use.
The public Candidate Agent only receives facts with both
`verification_status=verified` and `is_public=True`.

## Prepare a manifest

Create a JSON file **outside the repository**, for example under the ignored
`.local/` directory. Do not commit real resumes, extracted documents, contact
details, or unapproved professional claims.

A synthetic, non-personal example is provided in
`chatbot/tests/fixtures/synthetic_candidate_facts.json`.

The versioned format is:

```json
{
  "version": 1,
  "facts": [
    {
      "key": "project-example-01",
      "type": "project",
      "content": "Built a Django service that processes operational records.",
      "source_reference": "Owner-reviewed project notes"
    }
  ]
}
```

Allowed types are `summary`, `experience`, `education`, `skill`, `project`,
and `other`. Each key must be stable and unique within the candidate manifest.
The optional source reference is a descriptive provenance label, not a public
URL to a private document.

## Import and review

First create a candidate with the usual account flow. The import command
requires an existing candidate slug and never creates accounts or publishes a
profile.

```sh
uv run python manage.py import_candidate_facts \
  --candidate candidate-slug --file .local/candidate-facts.json --dry-run

uv run python manage.py import_candidate_facts \
  --candidate candidate-slug --file .local/candidate-facts.json
```

The command validates the entire manifest before writing, imports facts as
`pending` and private, and is safe to rerun with identical data. A changed
entry with an existing import key causes the transaction to roll back rather
than overwriting a reviewed fact. It does not send data to an AI provider.

Review the imported records in Django Admin under **Candidate facts**. Verify
each claim against its source, confirm that it is appropriate for public
disclosure, then set **Verification status = Verified** and **Is public = True**.
Both settings are required for the fact to reach the Candidate Agent.
Publication of the candidate profile is a separate administrative decision.

Do not publish facts containing private contact details, third-party personal
information, or confidential employer material. If a published fact must be
withdrawn, unset **Is public** immediately. Later ingestion and review workflows
will use the same authorization boundary.

Existing hand-entered facts have no import key and are not changed by imports.
Neither imported nor manually created facts become public automatically.
