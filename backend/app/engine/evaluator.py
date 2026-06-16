"""The 3-layer combinatorial interaction engine.

Layer 1: pairwise rules (interaction_pair), dose-threshold aware.
Layer 2: additive mechanism-class aggregation (additive_rule) — the differentiator.
Layer 3: conditional profile modifiers (conditional_modifier), attached or standalone.

Every finding carries source_name + source_ref. No finding is ever emitted
without a citation — uncited rows are rejected at load time.
"""
import json
from dataclasses import dataclass, field
from itertools import combinations

from .tags import Agent, expand

SEVERITY = ["timing-only", "minor", "moderate", "major", "contraindicated"]

# Entities whose dose counts toward total caffeine load (seed-note convention:
# preworkout dose is entered as its caffeine content in mg).
CAFFEINE_SOURCES = {"caffeine", "preworkout", "coffee", "green_tea_extract", "guarana"}
CAFFEINE_DAILY_LIMIT_MG = 400  # FDA consumer guidance, cited via the stimulant additive rule

ESCALATION_FOOTER = ("Informational safety alert, not a directive to change any medication. "
                     "Discuss with a licensed pharmacist or physician.")


@dataclass
class Finding:
    rule_id: str
    layer: int                      # 1 | 2 | 3
    agents: list                    # entity_ids involved
    interaction_type: str
    severity: str
    mechanism: str
    source_name: str
    source_ref: str
    is_true_contraindication: bool = False
    spacing_hours: int | None = None
    evidence_grade: str | None = None
    evidence_type: str | None = None
    management_text: str | None = None
    dose_assumed: bool = False      # fired on an assumed (unknown) dose
    modifier_notes: list = field(default_factory=list)   # [{message, source_name, source_ref}]
    extras: dict = field(default_factory=dict)           # e.g. total_caffeine_mg

    def severity_rank(self) -> int:
        return SEVERITY.index(self.severity)

    def bump(self, delta: int):
        self.severity = SEVERITY[min(self.severity_rank() + delta, len(SEVERITY) - 1)]

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id, "layer": self.layer, "agents": self.agents,
            "interaction_type": self.interaction_type, "severity": self.severity,
            "mechanism": self.mechanism,
            "is_true_contraindication": self.is_true_contraindication,
            "spacing_hours": self.spacing_hours,
            "evidence_grade": self.evidence_grade, "evidence_type": self.evidence_type,
            "source_name": self.source_name, "source_ref": self.source_ref,
            "management_text": self.management_text,
            "dose_assumed": self.dose_assumed,
            "modifier_notes": self.modifier_notes, "extras": self.extras,
            "disclaimer": ESCALATION_FOOTER,
        }


def _pair_dose_ok(rule, agent_for_a: Agent, agent_for_b: Agent) -> tuple[bool, bool]:
    """Check a pair rule's dose thresholds. Returns (fires, dose_assumed)."""
    assumed = False
    for threshold, agent in ((rule["dose_threshold_a"], agent_for_a),
                             (rule["dose_threshold_b"], agent_for_b)):
        if threshold is None:
            continue
        if agent.dose is None:
            assumed = True          # unknown dose: fire conservatively, flag assumption
        elif agent.dose < threshold:
            return False, False
    return True, assumed


def _finding_from_pair(rule, agents: list[str], dose_assumed: bool) -> Finding:
    return Finding(
        rule_id=rule["rule_id"], layer=1, agents=agents,
        interaction_type=rule["interaction_type"], severity=rule["severity"],
        mechanism=rule["mechanism"] or "",
        is_true_contraindication=bool(rule["is_true_contraindication"]),
        spacing_hours=rule["spacing_hours"],
        evidence_grade=rule["evidence_grade"], evidence_type=rule["evidence_type"],
        source_name=rule["source_name"], source_ref=rule["source_ref"],
        management_text=rule["management_text"], dose_assumed=dose_assumed)


def _layer1_pairwise(agents: list[Agent], conn) -> list[Finding]:
    findings = []
    by_id = {a.entity_id: a for a in agents}

    for a, b in combinations(agents, 2):
        rows = conn.execute(
            """SELECT * FROM interaction_pair
               WHERE (agent_a = ? AND agent_b = ?) OR (agent_a = ? AND agent_b = ?)""",
            (a.entity_id, b.entity_id, b.entity_id, a.entity_id)).fetchall()
        for rule in rows:
            agent_for_a = by_id[rule["agent_a"]]
            agent_for_b = by_id[rule["agent_b"]]
            fires, assumed = _pair_dose_ok(rule, agent_for_a, agent_for_b)
            if fires:
                findings.append(_finding_from_pair(rule, [rule["agent_a"], rule["agent_b"]], assumed))

    # Self-pair rules (agent_a == agent_b) are single-agent dose warnings, e.g. zinc >40mg.
    for agent in agents:
        for rule in conn.execute(
                "SELECT * FROM interaction_pair WHERE agent_a = ? AND agent_b = ?",
                (agent.entity_id, agent.entity_id)):
            fires, assumed = _pair_dose_ok(rule, agent, agent)
            if fires:
                findings.append(_finding_from_pair(rule, [agent.entity_id], assumed))
    return findings


def _layer2_additive(agents: list[Agent], conn) -> list[Finding]:
    findings = []
    for rule in conn.execute("SELECT * FROM additive_rule"):
        classes = {rule["mechanism_class"]}
        if rule["secondary_class"]:
            classes.add(rule["secondary_class"])

        contributors = [a for a in agents
                        if any(a.has_tag(c, role="effector") for c in classes)]
        if len(contributors) < rule["count_threshold"]:
            continue
        if rule["requires_rx_anchor"] and not any(a.is_rx for a in contributors):
            continue

        esc = json.loads(rule["escalation_map"])
        max_key = max(int(k) for k in esc)
        severity = esc[str(min(len(contributors), max_key))]
        dose_assumed = any(
            t.dose_assumed for a in contributors for t in a.tags if t.tag in classes)

        finding = Finding(
            rule_id=rule["agg_id"], layer=2,
            agents=[a.entity_id for a in contributors],
            interaction_type="pd-additive", severity=severity,
            mechanism=rule["mechanism_class"],
            is_true_contraindication=(severity == "contraindicated"),
            evidence_grade=rule["evidence_grade"],
            source_name=rule["source_name"], source_ref=rule["source_ref"],
            management_text=rule["management_text"], dose_assumed=dose_assumed,
            extras={"count": len(contributors),
                    "mechanism_classes": sorted(classes),
                    "rx_anchor": any(a.is_rx for a in contributors)})

        if rule["mechanism_class"] == "stimulant-sympathomimetic":
            total_caffeine = sum(a.dose or 0 for a in agents
                                 if a.entity_id in CAFFEINE_SOURCES and (a.dose_unit or "mg") == "mg")
            if total_caffeine > 0:
                finding.extras["total_caffeine_mg"] = total_caffeine
                finding.extras["caffeine_over_limit"] = total_caffeine > CAFFEINE_DAILY_LIMIT_MG
        findings.append(finding)
    return findings


def _modifier_matches_finding(mod, finding: Finding, agents_by_id: dict) -> bool:
    target = mod["applies_to_mechanism"]
    if target == finding.mechanism:
        return True
    if target in finding.agents:
        return True
    # Match a mechanism tag carried by any agent in the finding.
    return any(agents_by_id[eid].has_tag(target)
               for eid in finding.agents if eid in agents_by_id)


def _layer3_modifiers(agents: list[Agent], findings: list[Finding], profile: dict, conn) -> list[Finding]:
    agents_by_id = {a.entity_id: a for a in agents}
    standalone = []
    for mod in conn.execute("SELECT * FROM conditional_modifier"):
        if not profile.get(mod["condition"]):
            continue
        note = {"mod_id": mod["mod_id"], "condition": mod["condition"],
                "message": mod["message_text"],
                "source_name": mod["source_name"], "source_ref": mod["source_ref"]}

        matched_any = False
        for f in findings:
            if _modifier_matches_finding(mod, f, agents_by_id):
                matched_any = True
                if mod["hard_block"]:
                    f.severity = "contraindicated"
                    f.is_true_contraindication = True
                elif mod["severity_delta"]:
                    f.bump(mod["severity_delta"])
                f.modifier_notes.append(note)

        if matched_any:
            continue

        # Standalone fire: condition + matching agent present, no existing finding to attach to.
        target = mod["applies_to_mechanism"]
        hit_agents = [a.entity_id for a in agents
                      if a.entity_id == target or a.has_tag(target)]
        if hit_agents:
            if mod["hard_block"]:
                severity = "contraindicated"
            else:
                severity = SEVERITY[min(1 + (mod["severity_delta"] or 0), len(SEVERITY) - 1)]
            standalone.append(Finding(
                rule_id=mod["mod_id"], layer=3, agents=hit_agents,
                interaction_type="conditional-modifier", severity=severity,
                mechanism=target,
                is_true_contraindication=bool(mod["hard_block"]),
                source_name=mod["source_name"], source_ref=mod["source_ref"],
                management_text=mod["message_text"],
                modifier_notes=[dict(note)]))
    return standalone


def _resolve(findings: list[Finding]) -> list[Finding]:
    """Dedupe (same agents + mechanism -> keep highest severity), sort severity desc."""
    best: dict = {}
    for f in findings:
        key = (frozenset(f.agents), f.mechanism, f.interaction_type)
        if key not in best or f.severity_rank() > best[key].severity_rank():
            best[key] = f
    out = sorted(best.values(), key=lambda f: f.severity_rank(), reverse=True)
    for f in out:
        assert f.source_ref, f"finding {f.rule_id} has no source_ref"
    return out


def _escalate(findings: list[Finding], agents: list[Agent], profile: dict) -> bool:
    if any(f.severity in ("contraindicated", "major") for f in findings):
        return True
    if any(profile.get(c) for c in ("pregnant", "renal_impaired", "hepatic_impaired", "pre_surgery")):
        return True
    # >=3 agents sharing any pharmacodynamic effector class.
    class_counts: dict = {}
    for a in agents:
        for t in a.tags:
            if t.role == "effector":
                class_counts[t.tag] = class_counts.get(t.tag, 0) + 1
    return any(n >= 3 for n in class_counts.values())


def evaluate(active_agents: list[dict], profile: dict | None, conn) -> dict:
    """Run the full engine. active_agents: [{entity_id, dose, dose_unit, source}]."""
    profile = profile or {}
    agents = expand(active_agents, conn)

    findings = _layer1_pairwise(agents, conn)
    findings += _layer2_additive(agents, conn)
    findings += _layer3_modifiers(agents, findings, profile, conn)
    findings = _resolve(findings)

    safety = [f for f in findings if f.severity != "timing-only"]
    timing = [f for f in findings if f.severity == "timing-only"]

    return {
        "agents": [{"entity_id": a.entity_id, "canonical_name": a.canonical_name,
                    "entity_type": a.entity_type, "dose": a.dose, "dose_unit": a.dose_unit,
                    "source": a.source} for a in agents],
        "safety_findings": [f.to_dict() for f in safety],
        "timing_findings": [f.to_dict() for f in timing],
        "escalate": _escalate(findings, agents, profile),
        "disclaimer": ESCALATION_FOOTER,
    }
