"""Regression tests for the five headline expansion interactions + brand search.

These protect the hosted demo: each is a primary-sourced interaction an exec is
likely to surface by typing a common brand name. They run against the merged
seed+expansion dataset (the conn fixture loads via data.load_seed.load).
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import connect
from app.engine.evaluator import evaluate
from data.load_seed import load


@pytest.fixture(scope="module")
def conn(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("db") / "expansion.db"
    load(db_path)
    c = connect(db_path)
    yield c
    c.close()


def safety(conn, agents, profile=None):
    return evaluate(agents, profile, conn)["safety_findings"]


def rule_ids(findings):
    return {f["rule_id"] for f in findings}


def sev_of(findings, rule_id):
    return next(f["severity"] for f in findings if f["rule_id"] == rule_id)


# ---------------------------------------------------------------- headline interactions

def test_zoloft_st_johns_wort_serotonin_major(conn):
    """Zoloft (sertraline) + St. John's Wort -> serotonin syndrome, major."""
    findings = safety(conn, [{"entity_id": "sertraline"}, {"entity_id": "st_johns_wort"}])
    assert "ssri_sjw" in rule_ids(findings)
    assert sev_of(findings, "ssri_sjw") == "major"
    # The serotonergic additive rule also fires at >=2 serotonergic agents.
    assert sev_of(findings, "additive_serotonin") == "major"
    assert all(f["source_ref"] for f in findings)


def test_adderall_preworkout_stimulant_stack(conn):
    """Adderall (amphetamine) + caffeinated pre-workout -> stimulant stack."""
    findings = safety(conn, [{"entity_id": "amphetamine"},
                             {"entity_id": "preworkout", "dose": 300, "dose_unit": "mg"}])
    f = next(x for x in findings if x["rule_id"] == "additive_stimulant")
    assert f["severity"] in ("major", "contraindicated")
    assert f["layer"] == 2
    assert f["extras"]["count"] >= 2


def test_cbd_warfarin_major(conn):
    """CBD + warfarin (Coumadin) -> CYP2C9/3A4 inhibition raises INR, major."""
    findings = safety(conn, [{"entity_id": "cbd"}, {"entity_id": "warfarin"}])
    assert "cbd_warfarin" in rule_ids(findings)
    assert sev_of(findings, "cbd_warfarin") == "major"


def test_red_yeast_rice_atorvastatin_duplicate_statin_major(conn):
    """Red yeast rice + atorvastatin (Lipitor) -> duplicate HMG-CoA inhibition, major."""
    findings = safety(conn, [{"entity_id": "red-yeast-rice"}, {"entity_id": "atorvastatin"}])
    assert "ryr_statin" in rule_ids(findings)
    assert sev_of(findings, "ryr_statin") == "major"


def test_oxycodone_alprazolam_cns_depressant_major(conn):
    """Oxycodone (OxyContin) + alprazolam (Xanax) -> CNS depression, major (FDA boxed warning)."""
    findings = safety(conn, [{"entity_id": "oxycodone"}, {"entity_id": "alprazolam"}])
    assert "opioid_benzo" in rule_ids(findings)
    assert sev_of(findings, "opioid_benzo") == "major"
    # CNS-depressant additive rule also fires at >=2 agents.
    assert sev_of(findings, "cns_depressant_stack") == "major"


def test_all_headline_escalate(conn):
    for agents in ([{"entity_id": "sertraline"}, {"entity_id": "st_johns_wort"}],
                   [{"entity_id": "cbd"}, {"entity_id": "warfarin"}],
                   [{"entity_id": "oxycodone"}, {"entity_id": "alprazolam"}]):
        assert evaluate(agents, {}, conn)["escalate"] is True


# ---------------------------------------------------------------- brand-name resolution

@pytest.mark.parametrize("brand,expected", [
    ("Coumadin", "warfarin"),
    ("Ozempic", "semaglutide"),
    ("Xanax", "alprazolam"),
    ("Lipitor", "atorvastatin"),
])
def test_brand_name_resolves_via_aka(conn, brand, expected):
    rows = conn.execute("SELECT entity_id, canonical_name, aka FROM entity").fetchall()
    q = brand.lower()
    hits = [r["entity_id"] for r in rows
            if q in r["canonical_name"].lower()
            or any(q in a.lower() for a in json.loads(r["aka"] or "[]"))]
    assert expected in hits
