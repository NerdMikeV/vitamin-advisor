"""Phase 7 guardrails gate.

Enforces the won't-do list against every user-facing string the backend can
emit: no uncited interaction content, no prescription directives, no disease
treatment/cure claims, no diagnosis language.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import connect
from app.engine.evaluator import ESCALATION_FOOTER, evaluate
from data.load_seed import load

# Phrases that would violate the won't-do list if they appeared in any output
# string. Directives about *prescription medications* and disease claims.
FORBIDDEN = [
    "stop taking your",
    "discontinue your",
    "stop your medication",
    "change your dose",
    "increase your dose",
    "reduce your dose",
    "lower your dose",
    "skip your",
    "will cure",
    "cures ",
    "treats your",
    "will treat",
    "prevents disease",
    "you have ",          # diagnosis language ("you have a deficiency/condition")
    "you are deficient",
]


@pytest.fixture(scope="module")
def conn(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("db") / "guard.db"
    load(db_path)
    c = connect(db_path)
    yield c
    c.close()


def _all_output_strings(conn):
    out = []
    for table, cols in (
        ("interaction_pair", ["mechanism", "management_text"]),
        ("additive_rule", ["management_text"]),
        ("conditional_modifier", ["message_text"]),
        ("survey_rule", ["rationale"]),
    ):
        for row in conn.execute(f"SELECT * FROM {table}"):
            for col in cols:
                if row[col]:
                    out.append((table, row[0], col, row[col]))
    return out


def test_no_prescription_directives_or_disease_claims(conn):
    violations = []
    for table, rid, col, text in _all_output_strings(conn):
        low = text.lower()
        for phrase in FORBIDDEN:
            if phrase in low:
                violations.append((table, rid, col, phrase))
    assert not violations, f"forbidden phrases in output strings: {violations}"


def test_every_safety_row_is_cited(conn):
    for table, key in (("interaction_pair", "rule_id"),
                       ("additive_rule", "agg_id"),
                       ("conditional_modifier", "mod_id")):
        uncited = conn.execute(
            f"SELECT {key} FROM {table} WHERE source_ref IS NULL OR source_ref = ''").fetchall()
        assert not uncited, f"{table} rows without source_ref: {[r[0] for r in uncited]}"


def test_every_emitted_finding_carries_citation_and_disclaimer(conn):
    report = evaluate([
        {"entity_id": "warfarin"}, {"entity_id": "ginkgo"},
        {"entity_id": "iron", "dose": 18, "dose_unit": "mg"}, {"entity_id": "coffee"},
    ], {"pregnant": True}, conn)
    findings = report["safety_findings"] + report["timing_findings"]
    assert findings
    for f in findings:
        assert f["source_ref"], f"finding {f['rule_id']} missing citation"
        assert f["disclaimer"] == ESCALATION_FOOTER
    assert "not a directive to change any medication" in report["disclaimer"]


def test_contraindicated_cannot_be_overridden(conn):
    """The API surface has no parameter that downgrades a finding's severity —
    severity comes only from cited rules + profile escalation."""
    report = evaluate([{"entity_id": "ssri"}, {"entity_id": "5htp"}], {}, conn)
    severities = [f["severity"] for f in report["safety_findings"]]
    assert "contraindicated" in severities
    assert report["escalate"] is True
