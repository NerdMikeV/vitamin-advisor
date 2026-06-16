"""Load seed_data.json into app.db. Run from backend/: python -m data.load_seed"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import init_db, DB_PATH

SEED_PATH = Path(__file__).resolve().parent / "seed_data.json"


def load(db_path=DB_PATH) -> dict:
    seed = json.loads(SEED_PATH.read_text())
    conn = init_db(db_path)
    cur = conn.cursor()

    # Idempotent reload: clear data tables first.
    for table in ("entity_mechanism", "interaction_pair", "additive_rule",
                  "conditional_modifier", "survey_rule", "entity"):
        cur.execute(f"DELETE FROM {table}")

    counts = {}

    for e in seed["entities"]:
        cur.execute(
            """INSERT INTO entity (entity_id, canonical_name, entity_type, aka, rxnorm_rxcui,
                                   category, dose_low, dose_high, dose_unit, forms, dose_source)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (e["entity_id"], e["canonical_name"], e["entity_type"],
             json.dumps(e.get("aka", [])), e.get("rxnorm_rxcui"), e.get("category"),
             e.get("dose_low"), e.get("dose_high"), e.get("dose_unit"),
             json.dumps(e.get("forms", [])), e.get("dose_source")))
        for t in e.get("tags", []):
            cur.execute(
                """INSERT INTO entity_mechanism (entity_id, tag, role, dose_threshold, dose_unit, note)
                   VALUES (?,?,?,?,?,?)""",
                (e["entity_id"], t["tag"], t["role"],
                 t.get("dose_threshold"), t.get("dose_unit"), t.get("note")))
    counts["entity"] = len(seed["entities"])
    counts["entity_mechanism"] = cur.execute("SELECT COUNT(*) FROM entity_mechanism").fetchone()[0]

    for p in seed["interaction_pairs"]:
        if not p.get("source_ref"):
            raise ValueError(f"interaction_pair {p.get('rule_id')} has no source_ref — refusing to load (no-synthetic-data rule)")
        cur.execute(
            """INSERT INTO interaction_pair (rule_id, agent_a, agent_b, interaction_type, severity,
                   mechanism, is_true_contraindication, spacing_hours,
                   dose_threshold_a, dose_threshold_b, dose_unit,
                   evidence_grade, evidence_type, source_name, source_ref, management_text)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (p["rule_id"], p["agent_a"], p["agent_b"], p["interaction_type"], p["severity"],
             p.get("mechanism"), int(bool(p.get("is_true_contraindication"))), p.get("spacing_hours"),
             p.get("dose_threshold_a"), p.get("dose_threshold_b"), p.get("dose_unit"),
             p.get("evidence_grade"), p.get("evidence_type"),
             p["source_name"], p["source_ref"], p.get("management_text")))
    counts["interaction_pair"] = len(seed["interaction_pairs"])

    for a in seed["additive_rules"]:
        if not a.get("source_ref"):
            raise ValueError(f"additive_rule {a.get('agg_id')} has no source_ref — refusing to load")
        cur.execute(
            """INSERT INTO additive_rule (agg_id, mechanism_class, secondary_class, count_threshold,
                   requires_rx_anchor, escalation_map, evidence_grade, source_name, source_ref, management_text)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (a["agg_id"], a["mechanism_class"], a.get("secondary_class"), a["count_threshold"],
             int(bool(a.get("requires_rx_anchor"))), json.dumps(a["escalation_map"]),
             a.get("evidence_grade"), a.get("source_name"), a["source_ref"], a.get("management_text")))
    counts["additive_rule"] = len(seed["additive_rules"])

    for m in seed["conditional_modifiers"]:
        if not m.get("source_ref"):
            raise ValueError(f"conditional_modifier {m.get('mod_id')} has no source_ref — refusing to load")
        cur.execute(
            """INSERT INTO conditional_modifier (mod_id, condition, applies_to_mechanism,
                   severity_delta, hard_block, source_name, source_ref, message_text)
               VALUES (?,?,?,?,?,?,?,?)""",
            (m["mod_id"], m["condition"], m["applies_to_mechanism"],
             m.get("severity_delta"), int(bool(m.get("hard_block"))),
             m.get("source_name"), m["source_ref"], m.get("message_text")))
    counts["conditional_modifier"] = len(seed["conditional_modifiers"])

    for s in seed["survey_rules"]:
        cur.execute(
            """INSERT INTO survey_rule (sr_id, trigger_field, trigger_value, action,
                   target_entity, gating_flag, rationale, evidence_grade, source_ref)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (s["sr_id"], s["trigger_field"], s["trigger_value"], s["action"],
             s.get("target_entity"), s.get("gating_flag"),
             s.get("rationale"), s.get("evidence_grade"), s.get("source_ref")))
    counts["survey_rule"] = len(seed["survey_rules"])

    conn.commit()
    conn.close()
    return counts


if __name__ == "__main__":
    counts = load()
    print(f"Loaded seed data into {DB_PATH}:")
    for table, n in counts.items():
        print(f"  {table}: {n} rows")
