"""Unit tests (Phase 1) + the three demo-scenario acceptance tests (Phase 2/3).

These define "done" for the engine.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import connect
from app.engine.evaluator import evaluate
from data.load_seed import load


@pytest.fixture(scope="session")
def conn(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("db") / "test.db"
    load(db_path)
    c = connect(db_path)
    yield c
    c.close()


def check(conn, agents, profile=None):
    return evaluate(agents, profile, conn)


def all_findings(report):
    return report["safety_findings"] + report["timing_findings"]


def by_rule(report, rule_id):
    return [f for f in all_findings(report) if f["rule_id"] == rule_id]


# ---------------------------------------------------------------- Phase 1: Layer 1 pairwise

def test_iron_coffee_timing(conn):
    report = check(conn, [{"entity_id": "iron", "dose": 18, "dose_unit": "mg"},
                          {"entity_id": "coffee"}])
    hits = by_rule(report, "iron_coffee")
    assert len(hits) == 1
    f = hits[0]
    assert f["severity"] == "timing-only"
    assert f["spacing_hours"] == 2
    assert not f["is_true_contraindication"]
    assert f["source_ref"].startswith("http")
    assert not report["safety_findings"]      # timing fix, never a danger flag


def test_calcium_levothyroxine_timing_4h(conn):
    report = check(conn, [{"entity_id": "calcium", "dose": 600, "dose_unit": "mg"},
                          {"entity_id": "levothyroxine"}])
    hits = by_rule(report, "calcium_levo")
    assert len(hits) == 1
    assert hits[0]["severity"] == "timing-only"
    assert hits[0]["spacing_hours"] == 4


def test_warfarin_ginkgo_major(conn):
    report = check(conn, [{"entity_id": "warfarin"}, {"entity_id": "ginkgo"}])
    hits = by_rule(report, "warfarin_ginkgo")
    assert len(hits) == 1
    assert hits[0]["severity"] == "major"
    assert hits[0]["source_ref"]
    assert report["escalate"] is True


def test_dose_threshold_respected(conn):
    # Fish oil below its 2000 mg antiplatelet threshold: pairwise rule must NOT fire.
    low = check(conn, [{"entity_id": "warfarin"}, {"entity_id": "fish_oil", "dose": 1000, "dose_unit": "mg"}])
    assert not by_rule(low, "warfarin_fishoil")
    high = check(conn, [{"entity_id": "warfarin"}, {"entity_id": "fish_oil", "dose": 2000, "dose_unit": "mg"}])
    assert by_rule(high, "warfarin_fishoil")


def test_unknown_dose_fires_conservatively(conn):
    report = check(conn, [{"entity_id": "warfarin"}, {"entity_id": "fish_oil"}])
    hits = by_rule(report, "warfarin_fishoil")
    assert len(hits) == 1
    assert hits[0]["dose_assumed"] is True


# ---------------------------------------------------------------- Phase 2: acceptance scenarios

def test_scenario_1_warfarin_heart_stack(conn):
    """Warfarin + fish oil 2g + vitamin E 400IU + ginkgo + garlic + coq10."""
    report = check(conn, [
        {"entity_id": "warfarin", "source": "med"},
        {"entity_id": "fish_oil", "dose": 2000, "dose_unit": "mg", "source": "plan"},
        {"entity_id": "vitamin_e", "dose": 400, "dose_unit": "IU", "source": "plan"},
        {"entity_id": "ginkgo", "source": "plan"},
        {"entity_id": "garlic", "source": "plan"},
        {"entity_id": "coq10", "source": "plan"},
    ])
    # Layer 2 bleeding aggregation fires contraindicated (rx anchor + >=2 supplement bleeders).
    agg = by_rule(report, "additive_bleeding")
    assert len(agg) == 1
    f = agg[0]
    assert f["severity"] == "contraindicated"
    assert f["layer"] == 2
    assert f["extras"]["rx_anchor"] is True
    assert set(f["agents"]) == {"warfarin", "fish_oil", "vitamin_e", "ginkgo", "garlic"}
    # Individual ginkgo+warfarin major still present.
    assert by_rule(report, "warfarin_ginkgo")[0]["severity"] == "major"
    # CoQ10 carries no bleeding flag — appears in no safety finding.
    assert all("coq10" not in sf["agents"] for sf in report["safety_findings"])
    assert report["escalate"] is True
    assert all(sf["source_ref"] for sf in all_findings(report))


def test_scenario_2_stimulant_stack(conn):
    """Preworkout 300mg caffeine + caffeine 200mg + synephrine + yohimbine, hypertensive user."""
    report = check(conn, [
        {"entity_id": "preworkout", "dose": 300, "dose_unit": "mg", "source": "cart"},
        {"entity_id": "caffeine", "dose": 200, "dose_unit": "mg", "source": "cart"},
        {"entity_id": "synephrine", "source": "cart"},
        {"entity_id": "yohimbine", "source": "cart"},
    ], profile={"hypertension": True})
    agg = by_rule(report, "additive_stimulant")
    assert len(agg) == 1
    f = agg[0]
    assert f["severity"] == "contraindicated"
    assert f["extras"]["count"] >= 3
    # Total caffeine surfaced and over the 400 mg guidance line.
    assert f["extras"]["total_caffeine_mg"] == 500
    assert f["extras"]["caffeine_over_limit"] is True
    # Hypertension modifier attached.
    assert any(n["condition"] == "hypertension" for n in f["modifier_notes"])
    assert report["escalate"] is True


def test_scenario_2_hypertension_escalates_below_cap(conn):
    """With only 2 stimulants (severity major), hypertension bumps to contraindicated."""
    base = check(conn, [{"entity_id": "caffeine", "dose": 200, "dose_unit": "mg"},
                        {"entity_id": "synephrine"}])
    assert by_rule(base, "additive_stimulant")[0]["severity"] == "major"
    hyper = check(conn, [{"entity_id": "caffeine", "dose": 200, "dose_unit": "mg"},
                         {"entity_id": "synephrine"}], profile={"hypertension": True})
    assert by_rule(hyper, "additive_stimulant")[0]["severity"] == "contraindicated"


def test_scenario_3_metformin_b12_no_false_flags(conn):
    """Metformin + recommended B12: depletion-driven recommendation, zero danger flags."""
    report = check(conn, [
        {"entity_id": "metformin", "dose": 1500, "dose_unit": "mg", "source": "med"},
        {"entity_id": "b12", "source": "plan"},
    ])
    assert report["safety_findings"] == []
    assert report["escalate"] is False


# ---------------------------------------------------------------- Layer 2 extras

def test_triple_whammy_renal(conn):
    """ACE inhibitor + diuretic + NSAID: no dangerous pair, dangerous trio."""
    report = check(conn, [{"entity_id": "ace_inhibitor"}, {"entity_id": "diuretic"},
                          {"entity_id": "nsaid"}])
    agg = by_rule(report, "additive_nephrotoxic")
    assert len(agg) == 1
    assert agg[0]["severity"] == "major"
    # Adding a nephrotoxic supplement escalates to contraindicated.
    report4 = check(conn, [{"entity_id": "ace_inhibitor"}, {"entity_id": "diuretic"},
                           {"entity_id": "nsaid"}, {"entity_id": "creatine"}])
    assert by_rule(report4, "additive_nephrotoxic")[0]["severity"] == "contraindicated"


def test_rx_anchor_required_for_bleeding(conn):
    """Two supplement bleeders without a prescription anticoagulant: no Layer-2 fire."""
    report = check(conn, [{"entity_id": "ginkgo"}, {"entity_id": "garlic"}])
    assert not by_rule(report, "additive_bleeding")


def test_pregnancy_vitamin_a_standalone_hard_block(conn):
    report = check(conn, [{"entity_id": "vitamin_a"}], profile={"pregnant": True})
    hits = by_rule(report, "pregnancy_vitamin_a")
    assert len(hits) == 1
    assert hits[0]["severity"] == "contraindicated"
    assert report["escalate"] is True


# ---------------------------------------------------------------- Phase 3: recommendation

from app.engine.recommend import build_plan


def plan_ids(result):
    return {p["entity_id"] for p in result["plan"]}


def test_vegan_profile_plan(conn):
    result = build_plan({"diet": "vegan", "sun": "low", "goals": []}, conn)
    assert {"b12", "iron", "algal_oil", "vitamin_d"} <= plan_ids(result)
    # Every recommendation carries a cited reason.
    assert all(r["source_ref"] for p in result["plan"] for r in p["reasons"])


def test_metformin_yields_b12(conn):
    result = build_plan({"goals": ["energy"],
                         "meds": [{"entity_id": "metformin", "dose": 1500, "dose_unit": "mg"}]}, conn)
    assert "b12" in plan_ids(result)
    b12 = next(p for p in result["plan"] if p["entity_id"] == "b12")
    assert any("metformin" in r["trigger"] for r in b12["reasons"])
    assert all(r["source_ref"] for r in b12["reasons"])
    # No false danger flags in the bundled safety report.
    assert result["report"]["safety_findings"] == []


def test_alcohol_yields_bcomplex(conn):
    result = build_plan({"alcohol": "regular", "goals": []}, conn)
    assert "b_complex" in plan_ids(result)


def test_warfarin_gates_fish_oil(conn):
    result = build_plan({"goals": ["heart"],
                         "meds": [{"entity_id": "warfarin"}]}, conn)
    assert "fish_oil" not in plan_ids(result)
    gated = [g for g in result["gated"] if g["entity_id"] == "fish_oil"]
    assert len(gated) == 1
    assert gated[0]["gating_flag"] == "bleeding_risk"
