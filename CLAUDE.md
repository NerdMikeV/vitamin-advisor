# CLAUDE.md — Vitamin Advisor (Vitamin Shoppe POC)

## What we're building
A consumer-facing supplement personalization + interaction-safety app. A short health quiz builds a personalized supplement plan, then an engine checks that plan against the user's medications, other supplements, and lifestyle, flagging dangerous combinations and absorption/timing fixes. There's also an AI layer that surfaces the latest research on any supplement.

This is a proof of concept to win The Vitamin Shoppe's attention, not a shipping consumer product. The bar is: a VS exec clicks through it and leans forward. It will be built here in Claude Code, then demoed live.

## The one thing that matters
The differentiator is the combinatorial interaction engine — it catches risks that no consumer app catches because it reasons about mechanism classes, not just pairwise lookups (e.g., "fine with med A, fine with med B, dangerous on both"). Everything else is table stakes. Build the engine right; the rest is plumbing.

## Non-negotiable principles
1. NO SYNTHETIC DATA. Every interaction assertion must trace to a real cited source (`source_ref` field). Never invent an interaction or a citation. If a rule isn't sourced, it doesn't ship.
2. Information, not directives. The app never tells anyone to start/stop/change a prescription. It surfaces information and routes to a pharmacist. (See Guardrails.)
3. Incremental + tested. Each phase below has a test gate. Don't advance a phase until its tests pass. The three demo scenarios are hard acceptance tests.
4. Dose-dependence is first-class. Many interactions only fire above a dose threshold. A flag must respect `dose_threshold` before firing.
5. Distinguish true contraindication from timing fix. "Don't take together" and "take 4 hours apart" are different fields and different UX. Never collapse them.

## Tech stack
- Backend: Python + FastAPI, SQLite (POC — no Postgres). pydantic models.
- Frontend: React + Vite. Reuse the existing demo artifact (`vitamin-advisor-demo.jsx`) as the starting UI — it already has the quiz, results, interaction report, and AI panels. Wire it to the real backend.
- AI layer: Anthropic API (Claude) using the existing API key, with the web_search tool for the "latest research" feature. Usage-based, not a subscription.
- No paid data APIs. Interaction data is the hand-curated, cited seed set (`seed_data.json`). Production NatMed licensing is explicitly out of scope and is VS's line item later.

## Repo structure
```
vitamin-advisor/
  CLAUDE.md
  backend/
    app/
      main.py                 # FastAPI app + CORS
      db.py                   # SQLite connect + init_db()
      schema.sql              # DDL
      models.py               # pydantic request/response models
      engine/
        tags.py               # agent -> mechanism tag expansion
        evaluator.py          # the 3-layer interaction engine
        recommend.py          # survey answers -> supplement plan
      routers/
        plan.py               # POST /plan  (survey -> recommended stack)
        interactions.py       # POST /check (stack + meds + profile -> findings)
        research.py           # GET  /research/{entity}  (Claude + web_search)
    data/
      seed_data.json          # cited seed dataset (provided)
      load_seed.py            # loads seed_data.json -> app.db
    tests/
      test_engine.py          # 3 scenario acceptance tests + unit tests
    app.db                    # generated; gitignored
  frontend/                   # React + Vite app
```

## The interaction engine (engine/evaluator.py) — evaluation order
Input: `active_agents` = [{entity_id, dose, dose_unit, source}] (plan supplements + user-entered meds), plus `profile` flags (pregnant, renal_impaired, etc.).

```
SEVERITY = [timing-only, minor, moderate, major, contraindicated]   # ordered for escalation

1. EXPAND: for each agent, load entity_mechanism rows -> set of (tag, role) it carries,
   honoring dose_threshold (a tag only applies if agent.dose >= its threshold).

2. LAYER 1 (pairwise): for each unordered pair (a, b) in active_agents:
     look up interaction_pair where {agent_a,agent_b} matches (either order).
     if found AND dose thresholds met -> emit Finding.

3. LAYER 2 (additive): for each additive_rule:
     count = # active agents carrying mechanism_class as an 'effector' role.
     if requires_rx_anchor: count only valid if >=1 of those agents is a prescription drug.
     if count >= count_threshold: sev = escalation_map[str(min(count, max key))]; emit Finding.

4. LAYER 3 (modifiers): for each conditional_modifier where profile[condition] is true:
     bump/hard-block matching findings; can also fire standalone.

5. RESOLVE: dedupe (same agents+mechanism -> keep highest severity).
   Partition: contraindications/cautions vs timing-only. Every finding MUST carry source_ref.

6. RETURN findings + escalate flag (any contraindicated/major, pregnancy,
   renal/hepatic disease, >=3 agents sharing a PD class, or pre_surgery).
```

Key detail: Layer 2 is what makes the demo. The warfarin/fish-oil/E/ginkgo stack and the caffeine/synephrine/yohimbine stack fire here, not in Layer 1.

## Build order (each phase has a gate — don't skip)
- Phase 0 — Scaffold. Gate: `load_seed.py` loads seed_data.json into app.db with row counts printed; `/health` returns 200.
- Phase 1 — Tags + Layer 1. Gate: iron+coffee (timing), calcium+levothyroxine (timing 4h), warfarin+ginkgo (major) unit tests pass.
- Phase 2 — Layer 2 + Layer 3 + ACCEPTANCE TESTS. Gate: the three scenario tests pass.
- Phase 3 — Recommendation. Gate: vegan yields B12/iron/algal-omega/D; metformin yields B12; alcohol yields B-complex.
- Phase 4 — API. Gate: curl each endpoint end-to-end.
- Phase 5 — Frontend. Gate: all three scenarios click through in the browser.
- Phase 6 — AI research. Gate: cited 2-sentence summary; fails gracefully on API error.
- Phase 7 — Guardrails pass. Gate: no efficacy/treatment claims in any output string.

## Acceptance tests (tests/test_engine.py — these define "done")
1. Warfarin heart stack. meds=[warfarin]; plan=[fish_oil@2000mg, vitamin_e@400IU, ginkgo, garlic, coq10]. Expect: Layer-2 anticoagulant/antiplatelet aggregation fires contraindicated; ginkgo+warfarin major present; coq10 retained.
2. Stimulant stack. cart=[preworkout caffeine@300mg, caffeine@200mg, synephrine, yohimbine]; profile.hypertension=true. Expect: stimulant count ≥3 -> contraindicated; total caffeine >400mg surfaced; hypertension modifier escalates.
3. Metformin + B12. meds=[metformin@1500mg]; goal=energy. Expect: nutrient-depletion rule -> recommend B12 with mechanism + citation; no false danger flags.

## Data sourcing rules
- Seed comes from free, citable sources only: NIH ODS fact sheets, NCCIH HerbList, FDA DailyMed/openFDA, RxNorm.
- Each interaction/additive/modifier row has a `source_ref`. Before any non-demo use, a human verifies each row against its live source.
- The LLM may summarize already-sourced content (research endpoint). It must never generate interaction assertions into the database.

## Guardrails (Phase 7)
- DSHEA disclaimer wherever a structure/function claim appears.
- Global footer: general-information / not-medical-advice / consult-your-pharmacist-or-physician language.
- Interaction flag footer: "Informational safety alert, not a directive to change any medication. Discuss with a licensed pharmacist or physician."
- Won't-do (enforce in code + copy): never advise changing a prescription dose; never tell a user to stop a prescribed med; never diagnose; never make disease treatment/cure claims; never override a contraindicated flag; never emit uncited interaction content.
- Escalation CTA shown whenever `escalate` is true.

## Explicitly OUT of scope for the POC
NatMed/paid licensing, real VS SKU mapping, biomarker/lab intake, user auth, payments, comprehensive coverage. The demo dataset is a curated illustrative set and is labeled as such in the UI footer.
