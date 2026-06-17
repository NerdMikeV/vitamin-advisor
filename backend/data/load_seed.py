"""Load seed_data.json (+ optional expansion_data.json) into app.db.

Run from backend/: python -m data.load_seed

Merge semantics (when expansion_data.json is present):
  * Mechanism-tag vocabulary = seed mechanism_tags + expansion new_mechanism_tags.
    Every tag used by any entity/rule must be in the vocab or it is reported as
    inert (unknown) — a tag the engine carries but no vocabulary entry documents.
  * Entities: foreign-key ids are normalised via id_aliases; an expansion entity
    whose (aliased) id already exists EXTENDS the existing row (union of aka + tags)
    rather than duplicating it. Stub entities and aka_extensions are applied too.
  * interaction_pairs: deduped by rule_id AND by logical pair
    (unordered {agent_a, agent_b} + interaction_type) so the same pair is not
    flagged twice under two rule_ids.
  * additive_rules: deduped by mechanism_class — the existing seed rule wins
    (its escalation thresholds are covered by the acceptance tests); expansion
    duplicates are skipped, new mechanism classes are added.
  * conditional_modifiers: condition strings normalised via condition_map,
    severity_delta coerced from "+1"/"0" to int, deduped by (condition, mechanism).
  * survey_rules: appended; target_entity may be a comma list and may reference
    mechanism classes / pseudo-targets, which are validated but not treated as
    entity FKs.

FK validation runs before insert; unresolved references are collected and printed,
and (for interaction_pairs) the offending row is skipped rather than crashing.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import init_db, DB_PATH

DATA_DIR = Path(__file__).resolve().parent
SEED_PATH = DATA_DIR / "seed_data.json"
EXPANSION_PATH = DATA_DIR / "expansion_data.json"
GOAL_PATH = DATA_DIR / "goal_expansion.json"

# Non-entity tokens that survey_rule.target_entity may legitimately reference
# (handled as advisory gates, not entity foreign keys).
PSEUDO_TARGETS = {"oral_medications"}


def _merge_entity(dst: dict, src: dict) -> None:
    """Union src's aka + tags into an existing entity dict dst (in place)."""
    aka = list(dst.get("aka") or [])
    for a in src.get("aka", []):
        if a not in aka:
            aka.append(a)
    dst["aka"] = aka
    have = {(t["tag"], t["role"]) for t in dst.get("tags", [])}
    tags = list(dst.get("tags", []))
    for t in src.get("tags", []):
        if (t["tag"], t["role"]) not in have:
            tags.append(t)
            have.add((t["tag"], t["role"]))
    dst["tags"] = tags


def _coerce_delta(v):
    if v is None or isinstance(v, int):
        return v
    return int(str(v).replace("+", "").strip() or 0)


def build_dataset() -> tuple[dict, dict]:
    """Return (dataset, report). dataset has the five merged lists + vocab."""
    seed = json.loads(SEED_PATH.read_text())
    exp = json.loads(EXPANSION_PATH.read_text()) if EXPANSION_PATH.exists() else {}

    # Fold the goal-expansion pack into the same merge/validate machinery: its
    # entities/pairs/survey rules ride the existing alias, dedup, and FK paths.
    if GOAL_PATH.exists():
        goal = json.loads(GOAL_PATH.read_text())
        exp.setdefault("entities", []).extend(goal.get("new_entities", []))
        exp.setdefault("interaction_pairs", []).extend(goal.get("new_interaction_pairs", []))
        exp.setdefault("survey_rules", []).extend(goal.get("new_survey_rules", []))

    report = {"unknown_tags": [], "unresolved_pair_fks": [], "deduped_pairs": [],
              "deduped_additive": [], "deduped_modifiers": [],
              "survey_target_issues": [], "aka_extension_misses": []}

    aliases = exp.get("id_aliases", {})
    condition_map = exp.get("condition_map", {})

    def canon(eid):
        return aliases.get(eid, eid)

    # --- 1. mechanism-tag vocabulary -----------------------------------------
    vocab = {t["tag"] for t in seed.get("mechanism_tags", [])}
    vocab |= {t["tag"] for t in exp.get("new_mechanism_tags", [])}

    # --- 2. entities (merge by canonical id) ---------------------------------
    entities: dict[str, dict] = {}
    order: list[str] = []
    for e in seed["entities"]:
        entities[e["entity_id"]] = json.loads(json.dumps(e))  # deep copy
        order.append(e["entity_id"])

    for e in list(exp.get("entities", [])) + list(exp.get("stub_entities", [])):
        cid = canon(e["entity_id"])
        e = {**e, "entity_id": cid}
        if cid in entities:
            _merge_entity(entities[cid], e)
        else:
            entities[cid] = e
            order.append(cid)

    for eid, akas in exp.get("aka_extensions", {}).items():
        if eid not in entities:
            report["aka_extension_misses"].append(eid)
            continue
        cur = list(entities[eid].get("aka") or [])
        for a in akas:
            if a not in cur:
                cur.append(a)
        entities[eid]["aka"] = cur

    entity_ids = set(entities)

    # tag-vocab validation
    for eid in order:
        for t in entities[eid].get("tags", []):
            if t["tag"] not in vocab:
                report["unknown_tags"].append((eid, t["tag"]))

    # --- 3. interaction_pairs (dedup by rule_id and by logical pair) ----------
    pairs = []
    seen_rule_ids = set()
    seen_logical = set()
    for p in seed["interaction_pairs"]:
        pairs.append(p)
        seen_rule_ids.add(p["rule_id"])
        seen_logical.add((frozenset((p["agent_a"], p["agent_b"])), p["interaction_type"]))

    for p in exp.get("interaction_pairs", []):
        p = {**p, "agent_a": canon(p["agent_a"]), "agent_b": canon(p["agent_b"])}
        if p["rule_id"] in seen_rule_ids:
            report["deduped_pairs"].append((p["rule_id"], "rule_id exists"))
            continue
        key = (frozenset((p["agent_a"], p["agent_b"])), p["interaction_type"])
        if key in seen_logical:
            report["deduped_pairs"].append((p["rule_id"], "logical pair exists"))
            continue
        missing = [a for a in (p["agent_a"], p["agent_b"]) if a not in entity_ids]
        if missing:
            report["unresolved_pair_fks"].append((p["rule_id"], missing))
            continue
        pairs.append(p)
        seen_rule_ids.add(p["rule_id"])
        seen_logical.add(key)

    # --- 4. additive_rules (dedup by class SET — seed wins) -------------------
    # Key on the unordered {mechanism_class, secondary_class} set so the seed's
    # anticoagulant+antiplatelet "bleeding" rule matches the expansion's
    # antiplatelet+anticoagulant one (same coverage, primary/secondary swapped).
    def class_set(a):
        return frozenset(c for c in (a["mechanism_class"], a.get("secondary_class")) if c)
    additive = list(seed["additive_rules"])
    seen_classes = {class_set(a) for a in additive}
    for a in exp.get("additive_rules", []):
        if class_set(a) in seen_classes:
            report["deduped_additive"].append((a["agg_id"], a["mechanism_class"]))
            continue
        additive.append(a)
        seen_classes.add(class_set(a))

    # --- 5. conditional_modifiers (normalise condition + delta, dedup) --------
    modifiers = list(seed["conditional_modifiers"])
    seen_mod = {(m["condition"], m["applies_to_mechanism"]) for m in modifiers}
    for m in exp.get("conditional_modifiers", []):
        cond = condition_map.get(m["condition"], m["condition"])
        m = {**m, "condition": cond, "severity_delta": _coerce_delta(m.get("severity_delta"))}
        key = (cond, m["applies_to_mechanism"])
        if key in seen_mod:
            report["deduped_modifiers"].append((m["mod_id"], key))
            continue
        modifiers.append(m)
        seen_mod.add(key)

    # --- 6. survey_rules (append; validate target tokens) --------------------
    survey = list(seed["survey_rules"])
    for s in exp.get("survey_rules", []):
        survey.append(s)
        for tok in (s.get("target_entity") or "").split(","):
            tok = canon(tok.strip())
            if not tok or tok in entity_ids or tok in vocab or tok in PSEUDO_TARGETS:
                continue
            report["survey_target_issues"].append((s["sr_id"], tok))

    # also validate seed survey targets (single entity ids)
    for s in seed["survey_rules"]:
        tok = s.get("target_entity")
        if tok and tok not in entity_ids and tok not in vocab and tok not in PSEUDO_TARGETS:
            report["survey_target_issues"].append((s["sr_id"], tok))

    dataset = {
        "vocab": sorted(vocab),
        "entities": [entities[eid] for eid in order],
        "interaction_pairs": pairs,
        "additive_rules": additive,
        "conditional_modifiers": modifiers,
        "survey_rules": survey,
    }
    return dataset, report


def load(db_path=DB_PATH) -> dict:
    data, report = build_dataset()
    conn = init_db(db_path)
    cur = conn.cursor()

    for table in ("entity_mechanism", "interaction_pair", "additive_rule",
                  "conditional_modifier", "survey_rule", "entity"):
        cur.execute(f"DELETE FROM {table}")

    counts = {}

    # entities -> entity_mechanism
    for e in data["entities"]:
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
    counts["entity"] = len(data["entities"])
    counts["entity_mechanism"] = cur.execute("SELECT COUNT(*) FROM entity_mechanism").fetchone()[0]

    for p in data["interaction_pairs"]:
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
    counts["interaction_pair"] = len(data["interaction_pairs"])

    for a in data["additive_rules"]:
        if not a.get("source_ref"):
            raise ValueError(f"additive_rule {a.get('agg_id')} has no source_ref — refusing to load")
        cur.execute(
            """INSERT INTO additive_rule (agg_id, mechanism_class, secondary_class, count_threshold,
                   requires_rx_anchor, escalation_map, evidence_grade, source_name, source_ref, management_text)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (a["agg_id"], a["mechanism_class"], a.get("secondary_class"), a["count_threshold"],
             int(bool(a.get("requires_rx_anchor"))), json.dumps(a["escalation_map"]),
             a.get("evidence_grade"), a.get("source_name"), a["source_ref"], a.get("management_text")))
    counts["additive_rule"] = len(data["additive_rules"])

    for m in data["conditional_modifiers"]:
        if not m.get("source_ref"):
            raise ValueError(f"conditional_modifier {m.get('mod_id')} has no source_ref — refusing to load")
        cur.execute(
            """INSERT INTO conditional_modifier (mod_id, condition, applies_to_mechanism,
                   severity_delta, hard_block, source_name, source_ref, message_text)
               VALUES (?,?,?,?,?,?,?,?)""",
            (m["mod_id"], m["condition"], m["applies_to_mechanism"],
             m.get("severity_delta"), int(bool(m.get("hard_block"))),
             m.get("source_name"), m["source_ref"], m.get("message_text")))
    counts["conditional_modifier"] = len(data["conditional_modifiers"])

    for s in data["survey_rules"]:
        cur.execute(
            """INSERT INTO survey_rule (sr_id, trigger_field, trigger_value, action,
                   target_entity, gating_flag, rationale, evidence_grade, source_ref)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (s["sr_id"], s["trigger_field"], s["trigger_value"], s["action"],
             s.get("target_entity"), s.get("gating_flag"),
             s.get("rationale"), s.get("evidence_grade"), s.get("source_ref")))
    counts["survey_rule"] = len(data["survey_rules"])

    conn.commit()
    conn.close()
    counts["_report"] = report
    counts["_vocab_size"] = len(data["vocab"])
    return counts


if __name__ == "__main__":
    counts = load()
    report = counts.pop("_report")
    vocab_size = counts.pop("_vocab_size")
    print(f"Loaded data into {DB_PATH}:")
    for table, n in counts.items():
        print(f"  {table}: {n} rows")
    print(f"  mechanism-tag vocab: {vocab_size} tags")
    print("\nFK / merge validation:")
    print(f"  unknown tags (inert): {report['unknown_tags'] or 'none'}")
    print(f"  unresolved pair FKs:  {report['unresolved_pair_fks'] or 'none'}")
    print(f"  aka-extension misses: {report['aka_extension_misses'] or 'none'}")
    print(f"  survey target non-entity tokens (informational):")
    if report["survey_target_issues"]:
        for sr, tok in report["survey_target_issues"]:
            print(f"      {sr}: '{tok}'")
    else:
        print("      none")
    print(f"  deduped interaction_pairs: {report['deduped_pairs'] or 'none'}")
    print(f"  deduped additive_rules:    {report['deduped_additive'] or 'none'}")
    print(f"  deduped modifiers:         {report['deduped_modifiers'] or 'none'}")
