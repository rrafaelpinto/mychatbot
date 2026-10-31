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

## LLM-assisted extraction (Phase 3)

Document text can be turned into **private, pending suggestions** using the
administrative `extract_candidate_facts` command. The operation is disabled by
default even in development. It requires an already processed document, an
explicitly selected candidate, `AI_ENABLED=true`,
`AI_KNOWLEDGE_EXTRACTION_ENABLED=true`, an OpenAI API key, and available
project budget.

```sh
uv run python manage.py extract_candidate_facts \\
  --candidate candidate-slug --document 123
```

This sends a bounded portion of private extracted text to the configured
OpenAI provider. It is not invoked automatically on upload, during public
chat, or when merely viewing the document. Text longer than the supported
input limit is rejected rather than silently truncated. Treat source
documents as potentially sensitive and only initiate extraction for
information the candidate is authorized to process externally.

The LangChain prompt and Pydantic parser propose structured facts. Each
suggestion must include an **exact source quotation**, verified by application
code. Proposed facts remain `pending` and `is_public=False`, linked to
the private document. Source quotations are private metadata, never exposed
by the public Candidate Agent.

Successful execution is idempotent per document, while failed attempts
are recoverable subject to quotas and budgets. The extraction workflow does
not decide whether the source claim is truthful or suitable for publication.
That decision belongs to a human reviewer. Use the private
`/candidate/facts/` interface to review proposals, edit claims, approve their
accuracy, and separately authorize public visibility. Editing an approved
claim revokes its verification and public visibility until it is reviewed again.
Only the candidate account owner can access this interface. The review record
stores decisions and timestamps, not copies of private documents or fact text.

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

Review the imported records through **Profile → Review professional facts**.
For every entry, inspect the source reference, correct the claim if necessary,
approve it as verified, and independently publish it only if disclosure is
appropriate. Rejected facts remain private. Changes to verified text
automatically revoke verification and publication until explicitly reapproved.
Only facts that are both verified and public reach the Candidate Agent.
Publishing the candidate profile is a separate administrative decision.

Do not publish facts containing private contact details, third-party personal
information, or confidential employer material. If a published fact must be
withdrawn, unset **Is public** immediately. Later ingestion and review workflows
will use the same authorization boundary.

Existing hand-entered facts have no import key and are not changed by imports.
Neither imported nor manually created facts become public automatically.
