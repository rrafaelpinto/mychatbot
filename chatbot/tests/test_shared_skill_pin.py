"""Verify the pinned shared UI review skill and local discovery bridge."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CANONICAL = ROOT / ".agents/skills/ui-ux-review/SKILL.md"
LOCK = ROOT / ".agents/skills.lock"
BRIDGE = ROOT / ".claude/skills/ui-ux-review/SKILL.md"


def test_ui_review_skill_matches_pinned_snapshot():
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    record = lock["skills"]["ui-ux-review"]
    assert lock["schema"] == 1
    assert record["source"] == "https://github.com/rrafaelpinto/skills"
    assert record["revision"] == "5367a48c43531697729ef374bfa79990d1d89a86"
    digest = hashlib.sha256()
    for file in sorted(p for p in CANONICAL.parent.rglob("*") if p.is_file()):
        digest.update(file.relative_to(CANONICAL.parent).as_posix().encode())
        digest.update(b"\0")
        digest.update(file.read_bytes())
        digest.update(b"\0")
    assert digest.hexdigest() == record["sha256"]


def test_claude_bridge_preserves_local_workflow():
    bridge = BRIDGE.read_text(encoding="utf-8")
    assert ".agents/skills/ui-ux-review/SKILL.md" in bridge
    assert "docs/engineering/UI_UX_WORKFLOW.md" in bridge
    workflow = (ROOT / "docs/engineering/UI_UX_WORKFLOW.md").read_text(
        encoding="utf-8"
    )
    assert "Candidate Agent answers remain first person" in workflow
    assert "npm --prefix frontend run test:e2e" in workflow
