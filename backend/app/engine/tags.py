"""Agent -> mechanism tag expansion (Layer 0 of the engine).

A tag with a dose_threshold only applies when the agent's dose meets it.
If the agent's dose is unknown and the tag has a threshold, we apply the tag
conservatively (safety-first) and mark it dose_assumed so the UI can say
"assuming a typical/unknown dose".
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class MechTag:
    tag: str
    role: str          # substrate|inhibitor|inducer|effector|depletes|susceptible
    dose_assumed: bool = False


@dataclass
class Agent:
    entity_id: str
    dose: float | None = None
    dose_unit: str | None = None
    source: str = "user"            # plan | user | cart
    entity_type: str = "supplement"
    canonical_name: str = ""
    tags: set = field(default_factory=set)   # set[MechTag]

    @property
    def is_rx(self) -> bool:
        return self.entity_type in ("drug", "drug_class")

    def has_tag(self, tag: str, role: str | None = None) -> bool:
        return any(t.tag == tag and (role is None or t.role == role) for t in self.tags)


def expand(agents: list[dict], conn) -> list[Agent]:
    """Resolve raw agent dicts against the entity + entity_mechanism tables."""
    expanded = []
    for raw in agents:
        eid = raw["entity_id"]
        row = conn.execute("SELECT * FROM entity WHERE entity_id = ?", (eid,)).fetchone()
        if row is None:
            # Unknown entity: keep it visible (UI shows "not in dataset") but carry no tags.
            expanded.append(Agent(entity_id=eid, dose=raw.get("dose"),
                                  dose_unit=raw.get("dose_unit"),
                                  source=raw.get("source", "user"),
                                  entity_type="unknown", canonical_name=eid))
            continue
        agent = Agent(entity_id=eid, dose=raw.get("dose"), dose_unit=raw.get("dose_unit"),
                      source=raw.get("source", "user"),
                      entity_type=row["entity_type"], canonical_name=row["canonical_name"])
        for m in conn.execute("SELECT * FROM entity_mechanism WHERE entity_id = ?", (eid,)):
            threshold = m["dose_threshold"]
            if threshold is None:
                agent.tags.add(MechTag(m["tag"], m["role"]))
            elif agent.dose is None:
                agent.tags.add(MechTag(m["tag"], m["role"], dose_assumed=True))
            elif agent.dose >= threshold:
                agent.tags.add(MechTag(m["tag"], m["role"]))
            # dose below threshold -> tag does not apply
        expanded.append(agent)
    return expanded
