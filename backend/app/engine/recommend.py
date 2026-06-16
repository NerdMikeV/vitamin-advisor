"""Survey answers -> personalized supplement plan, then one safety round-trip.

Applies survey_rule rows (recommend | gate), dedupes, and runs the resulting
plan + user meds through the interaction engine so plan and safety report come
back together.
"""
from .evaluator import evaluate

# Survey fields whose values are matched one-to-one against survey_rule triggers.
SCALAR_FIELDS = ("diet", "alcohol", "sun")


def _trigger_values(survey: dict) -> list[tuple[str, str]]:
    pairs = []
    for goal in survey.get("goals", []):
        pairs.append(("goal", goal))
    for field in SCALAR_FIELDS:
        if survey.get(field):
            pairs.append((field, survey[field]))
    for med in survey.get("meds", []):
        pairs.append(("med", med["entity_id"]))
    return pairs


def build_plan(survey: dict, conn) -> dict:
    """Returns {plan, gated, report}. survey: {goals, diet, alcohol, sun, meds, profile}."""
    recommended: dict = {}   # entity_id -> plan item
    gates: list = []         # gate rules triggered (applied after recommendations collected)

    for field, value in _trigger_values(survey):
        rows = conn.execute(
            "SELECT * FROM survey_rule WHERE trigger_field = ? AND trigger_value = ?",
            (field, value)).fetchall()
        for rule in rows:
            if rule["action"] == "recommend":
                eid = rule["target_entity"]
                entity = conn.execute("SELECT * FROM entity WHERE entity_id = ?", (eid,)).fetchone()
                if entity is None:
                    continue
                item = recommended.setdefault(eid, {
                    "entity_id": eid,
                    "canonical_name": entity["canonical_name"],
                    "dose": entity["dose_low"], "dose_unit": entity["dose_unit"],
                    "reasons": [],
                })
                item["reasons"].append({
                    "trigger": f"{field}={value}",
                    "rationale": rule["rationale"],
                    "evidence_grade": rule["evidence_grade"],
                    "source_ref": rule["source_ref"],
                })
            elif rule["action"] == "gate":
                gates.append(rule)

    # Gates: pull the target out of the auto-plan and surface it for pharmacist review.
    gated = []
    for rule in gates:
        eid = rule["target_entity"]
        if eid in recommended:
            item = recommended.pop(eid)
        else:
            entity = conn.execute("SELECT * FROM entity WHERE entity_id = ?", (eid,)).fetchone()
            if entity is None:
                continue
            item = {"entity_id": eid, "canonical_name": entity["canonical_name"], "reasons": []}
        gated.append({**item,
                      "gating_flag": rule["gating_flag"],
                      "gate_rationale": rule["rationale"],
                      "source_ref": rule["source_ref"]})

    plan = list(recommended.values())

    # One round-trip: plan + meds through the interaction engine.
    active = [{"entity_id": p["entity_id"], "dose": p["dose"],
               "dose_unit": p["dose_unit"], "source": "plan"} for p in plan]
    active += [{"entity_id": m["entity_id"], "dose": m.get("dose"),
                "dose_unit": m.get("dose_unit"), "source": "med"}
               for m in survey.get("meds", [])]
    report = evaluate(active, survey.get("profile"), conn)

    return {"plan": plan, "gated": gated, "report": report}
