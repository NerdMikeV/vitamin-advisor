import { useEffect, useMemo, useState } from 'react'
import { getEntities, getDisclaimer, getResearch, postPlan, postCheck } from './api'

const DSHEA = 'This statement has not been evaluated by the Food and Drug Administration. This product is not intended to diagnose, treat, cure, or prevent any disease.'
const FLAG_FOOTER = 'Informational safety alert, not a directive to change any medication. Discuss with a licensed pharmacist or physician.'

const GOALS = [
  { id: 'energy', label: 'Energy' },
  { id: 'sleep', label: 'Better sleep' },
  { id: 'heart', label: 'Heart health' },
  { id: 'joint', label: 'Joint support' },
  { id: 'immunity', label: 'Immunity' },
]

const PROFILE_FLAGS = [
  { id: 'pregnant', label: 'Pregnant' },
  { id: 'breastfeeding', label: 'Breastfeeding' },
  { id: 'hypertension', label: 'High blood pressure' },
  { id: 'renal_impaired', label: 'Kidney disease' },
  { id: 'hepatic_impaired', label: 'Liver disease' },
  { id: 'epilepsy', label: 'Epilepsy / seizure history' },
  { id: 'long_qt', label: 'Long QT / cardiac arrhythmia' },
  { id: 'pre_surgery', label: 'Surgery in next 2 weeks' },
]

// Lifestyle toggles. surveyField/surveyValue feed /plan gate rules; profile sets
// an engine modifier flag; entity adds a representative agent to a /check stack.
const LIFESTYLE = [
  { id: 'smoking', label: 'Smoke / vape', surveyField: 'smoking_status', surveyValue: 'current_smoker', profile: 'smoker', entity: 'nicotine' },
  { id: 'cbd', label: 'Use CBD', surveyField: 'uses_cbd', surveyValue: 'yes', entity: 'cbd' },
  { id: 'cannabis', label: 'Use cannabis (THC)', surveyField: 'uses_cannabis', surveyValue: 'yes', entity: 'thc-cannabis' },
  { id: 'glp1', label: 'On a GLP-1 (Ozempic / Mounjaro)', surveyField: 'uses_glp1', surveyValue: 'yes', entity: 'semaglutide' },
  { id: 'bloodwork', label: 'Bloodwork coming up', surveyField: 'upcoming_bloodwork', surveyValue: 'yes', profile: 'upcoming_bloodwork' },
]

const SEVERITY_LABEL = {
  contraindicated: 'Do not combine',
  major: 'Major risk',
  moderate: 'Moderate',
  minor: 'Minor',
  'timing-only': 'Timing fix',
}

// Live-demo presets — the three acceptance scenarios.
const SCENARIOS = [
  {
    name: 'Heart stack on warfarin',
    mode: 'checker',
    agents: [
      { entity_id: 'warfarin', source: 'med' },
      { entity_id: 'fish_oil', dose: 2000, dose_unit: 'mg', source: 'plan' },
      { entity_id: 'vitamin_e', dose: 400, dose_unit: 'IU', source: 'plan' },
      { entity_id: 'ginkgo', source: 'plan' },
      { entity_id: 'garlic', source: 'plan' },
      { entity_id: 'coq10', source: 'plan' },
    ],
    profile: {},
  },
  {
    name: 'Stimulant pre-workout cart',
    mode: 'checker',
    agents: [
      { entity_id: 'preworkout', dose: 300, dose_unit: 'mg', source: 'cart' },
      { entity_id: 'caffeine', dose: 200, dose_unit: 'mg', source: 'cart' },
      { entity_id: 'synephrine', source: 'cart' },
      { entity_id: 'yohimbine', source: 'cart' },
    ],
    profile: { hypertension: true },
  },
  {
    name: 'Metformin + energy goal',
    mode: 'advisor',
    survey: {
      goals: ['energy'],
      meds: [{ entity_id: 'metformin', dose: 1500, dose_unit: 'mg' }],
      profile: {},
    },
  },
]

function Citation({ name, url }) {
  if (!url) return null
  const href = url.startsWith('http') ? url : null
  return (
    <span className="citation">
      Source:{' '}
      {href ? (
        <a href={href} target="_blank" rel="noreferrer">{name || url.replace(/^https?:\/\/(www\.)?/, '').split('/')[0]}</a>
      ) : (
        <span>{name ? `${name} — ` : ''}{url}</span>
      )}
    </span>
  )
}

function SeverityBadge({ severity }) {
  return <span className={`badge sev-${severity}`}>{SEVERITY_LABEL[severity] || severity}</span>
}

function Finding({ f, names }) {
  const agentNames = f.agents.map((a) => names[a] || a).join(' + ')
  return (
    <div className={`finding sevborder-${f.severity}`}>
      <div className="finding-head">
        <SeverityBadge severity={f.severity} />
        {f.layer === 2 && <span className="badge layer">Combination effect · {f.extras.count} agents</span>}
        {f.dose_assumed && <span className="badge assumed">dose assumed</span>}
        <strong>{agentNames}</strong>
      </div>
      {f.mechanism && <p className="mechanism">{f.mechanism}</p>}
      {f.spacing_hours && (
        <p className="spacing">⏱ Take at least <strong>{f.spacing_hours} hours apart</strong> — this is a scheduling fix, not a danger flag.</p>
      )}
      {f.extras?.total_caffeine_mg && (
        <p className={f.extras.caffeine_over_limit ? 'caffeine over' : 'caffeine'}>
          Total caffeine in this stack: <strong>{f.extras.total_caffeine_mg} mg</strong>
          {f.extras.caffeine_over_limit && ' — exceeds the 400 mg/day FDA guidance for healthy adults'}
        </p>
      )}
      {f.management_text && <p className="management">{f.management_text}</p>}
      {f.modifier_notes.map((n) => (
        <p key={n.mod_id} className="modifier">
          ▲ Because of your profile ({n.condition.replace('_', ' ')}): {n.message} <Citation name={n.source_name} url={n.source_ref} />
        </p>
      ))}
      <div className="finding-foot">
        <Citation name={f.source_name} url={f.source_ref} />
        {f.evidence_grade && <span className="grade">Evidence grade {f.evidence_grade}</span>}
      </div>
      <p className="flag-footer">{FLAG_FOOTER}</p>
    </div>
  )
}

function Report({ report, names }) {
  if (!report) return null
  const safety = report.safety_findings
  const timing = report.timing_findings
  return (
    <div className="report">
      {report.escalate && (
        <div className="escalate">
          <strong>Talk to a pharmacist before purchasing this combination.</strong>
          <p>This stack has flags that deserve a professional review. Bring your full medication list — most pharmacies do this consult for free.</p>
        </div>
      )}
      <h3>Safety findings {safety.length === 0 && <span className="ok">— none found in this dataset ✓</span>}</h3>
      {safety.map((f) => <Finding key={f.rule_id + f.agents.join()} f={f} names={names} />)}
      {timing.length > 0 && (
        <>
          <h3>Timing & absorption fixes <span className="muted">(keep everything — just schedule it right)</span></h3>
          {timing.map((f) => <Finding key={f.rule_id + f.agents.join()} f={f} names={names} />)}
        </>
      )}
    </div>
  )
}

function Advisories({ advisories }) {
  if (!advisories || advisories.length === 0) return null
  return (
    <div className="advisories">
      <h3>Lifestyle advisories</h3>
      {advisories.map((a) => (
        <div key={a.gating_flag} className="advisory">
          <strong>{a.trigger.replace(/_/g, ' ')}:</strong> {a.rationale} <Citation url={a.source_ref} />
        </div>
      ))}
    </div>
  )
}

function ResearchPanel({ entityId, names }) {
  const [state, setState] = useState({ loading: false, data: null })
  const load = async () => {
    setState({ loading: true, data: null })
    try {
      setState({ loading: false, data: await getResearch(entityId) })
    } catch {
      setState({ loading: false, data: { error: 'Research service unavailable.' } })
    }
  }
  return (
    <div className="research">
      {!state.data && (
        <button className="link-btn" onClick={load} disabled={state.loading}>
          {state.loading ? 'Searching the literature…' : `Latest research on ${names[entityId] || entityId} →`}
        </button>
      )}
      {state.data?.summary && (
        <div className="research-result">
          <p>{state.data.summary}</p>
          <p className="dshea">{state.data.disclaimer}</p>
        </div>
      )}
      {state.data?.error && <p className="muted">{state.data.error}</p>}
    </div>
  )
}

function PlanCard({ item, names, gated }) {
  return (
    <div className={`plan-card ${gated ? 'gated' : ''}`}>
      <div className="plan-head">
        <strong>{item.canonical_name}</strong>
        {item.dose != null && <span className="dose">{item.dose} {item.dose_unit}</span>}
        {gated && <span className="badge sev-major">Needs pharmacist review</span>}
      </div>
      {gated && <p className="mechanism">{item.gate_rationale}</p>}
      {(item.reasons || []).map((r, i) => (
        <p key={i} className="reason">
          {r.rationale} <Citation url={r.source_ref} /> {r.evidence_grade && <span className="grade">Grade {r.evidence_grade}</span>}
        </p>
      ))}
      {gated && <Citation url={item.source_ref} />}
      <p className="dshea">{DSHEA}</p>
      <ResearchPanel entityId={item.entity_id} names={names} />
    </div>
  )
}

function AgentPicker({ entities, onAdd }) {
  const [query, setQuery] = useState('')
  const [dose, setDose] = useState('')
  const matches = useMemo(() => {
    if (!query) return []
    const q = query.toLowerCase()
    return entities
      .filter((e) => e.canonical_name.toLowerCase().includes(q) || e.entity_id.includes(q) || (e.aka || []).some((a) => a.toLowerCase().includes(q)))
      .slice(0, 6)
  }, [query, entities])
  return (
    <div className="picker">
      <div className="picker-row">
        <input placeholder="Search supplements & medications…" value={query} onChange={(e) => setQuery(e.target.value)} />
        <input className="dose-input" placeholder="dose (optional)" value={dose} onChange={(e) => setDose(e.target.value)} />
      </div>
      {matches.length > 0 && (
        <ul className="matches">
          {matches.map((e) => (
            <li key={e.entity_id}>
              <button
                onClick={() => {
                  onAdd({
                    entity_id: e.entity_id,
                    dose: dose ? parseFloat(dose) : null,
                    dose_unit: dose ? e.dose_unit || 'mg' : null,
                    source: e.entity_type === 'supplement' ? 'cart' : 'med',
                  })
                  setQuery('')
                  setDose('')
                }}
              >
                {e.canonical_name} <span className="muted">({e.entity_type.replace('_', ' ')})</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default function App() {
  const [entities, setEntities] = useState([])
  const [footer, setFooter] = useState('')
  const [mode, setMode] = useState('advisor') // advisor | checker
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  // Advisor (quiz) state
  const [goals, setGoals] = useState([])
  const [diet, setDiet] = useState('omnivore')
  const [alcohol, setAlcohol] = useState('none')
  const [sun, setSun] = useState('moderate')
  const [meds, setMeds] = useState([])
  const [profile, setProfile] = useState({})
  const [lifestyle, setLifestyle] = useState({})   // {smoking, cbd, cannabis, glp1, bloodwork}
  const [planResult, setPlanResult] = useState(null)

  // Checker state
  const [stack, setStack] = useState([])
  const [checkProfile, setCheckProfile] = useState({})
  const [checkResult, setCheckResult] = useState(null)

  // Translate lifestyle toggles into survey gate fields + engine profile flags.
  const lifestyleSurvey = (ls) => {
    const out = {}
    for (const item of LIFESTYLE) if (ls[item.id] && item.surveyField) out[item.surveyField] = item.surveyValue
    return out
  }
  const lifestyleProfile = (ls) => {
    const out = {}
    for (const item of LIFESTYLE) if (ls[item.id] && item.profile) out[item.profile] = true
    return out
  }

  const names = useMemo(() => Object.fromEntries(entities.map((e) => [e.entity_id, e.canonical_name])), [entities])

  useEffect(() => {
    getEntities().then(setEntities).catch(() => setError('Backend not reachable — start it with: uvicorn app.main:app --port 8001'))
    getDisclaimer().then((d) => setFooter(d.footer)).catch(() => {})
  }, [])

  const runPlan = async () => {
    setBusy(true); setError(null)
    try {
      const survey = { goals, diet, alcohol, sun, meds,
                       ...lifestyleSurvey(lifestyle),
                       profile: { ...profile, ...lifestyleProfile(lifestyle) } }
      setPlanResult(await postPlan(survey))
    } catch (e) { setError(String(e)) } finally { setBusy(false) }
  }

  const runCheck = async (agents = stack, prof = checkProfile) => {
    setBusy(true); setError(null)
    try {
      setCheckResult(await postCheck(agents, prof))
    } catch (e) { setError(String(e)) } finally { setBusy(false) }
  }

  const loadScenario = async (s) => {
    setMode(s.mode)
    setPlanResult(null); setCheckResult(null)
    if (s.mode === 'checker') {
      setStack(s.agents)
      setCheckProfile(s.profile)
      await runCheck(s.agents, s.profile)
    } else {
      setGoals(s.survey.goals)
      setMeds(s.survey.meds)
      setProfile(s.survey.profile)
      setBusy(true)
      try { setPlanResult(await postPlan(s.survey)) } finally { setBusy(false) }
    }
  }

  const toggle = (list, setList, id) => setList(list.includes(id) ? list.filter((x) => x !== id) : [...list, id])

  return (
    <div className="app">
      <header>
        <h1>Vitamin&nbsp;Advisor</h1>
        <p className="tagline">Personalized supplement plans, checked against your medications — including the combination risks single-pair checkers miss.</p>
        <div className="scenarios">
          <span className="muted">Demo scenarios:</span>
          {SCENARIOS.map((s) => (
            <button key={s.name} className="scenario-btn" onClick={() => loadScenario(s)}>{s.name}</button>
          ))}
        </div>
        <nav>
          <button className={mode === 'advisor' ? 'active' : ''} onClick={() => setMode('advisor')}>Build my plan</button>
          <button className={mode === 'checker' ? 'active' : ''} onClick={() => setMode('checker')}>Check my stack</button>
        </nav>
      </header>

      {error && <div className="error">{error}</div>}

      {mode === 'advisor' && (
        <section>
          <div className="quiz">
            <h2>1 · What are you optimizing for?</h2>
            <div className="chips">
              {GOALS.map((g) => (
                <button key={g.id} className={`chip ${goals.includes(g.id) ? 'on' : ''}`} onClick={() => toggle(goals, setGoals, g.id)}>{g.label}</button>
              ))}
            </div>
            <h2>2 · Lifestyle</h2>
            <div className="selects">
              <label>Diet
                <select value={diet} onChange={(e) => setDiet(e.target.value)}>
                  <option value="omnivore">Omnivore</option>
                  <option value="vegetarian">Vegetarian</option>
                  <option value="vegan">Vegan</option>
                </select>
              </label>
              <label>Alcohol
                <select value={alcohol} onChange={(e) => setAlcohol(e.target.value)}>
                  <option value="none">Rarely / never</option>
                  <option value="occasional">Occasional</option>
                  <option value="regular">Regular</option>
                </select>
              </label>
              <label>Sun exposure
                <select value={sun} onChange={(e) => setSun(e.target.value)}>
                  <option value="low">Low</option>
                  <option value="moderate">Moderate</option>
                  <option value="high">High</option>
                </select>
              </label>
            </div>
            <h2>3 · Medications you take</h2>
            <AgentPicker entities={entities.filter((e) => e.entity_type !== 'food')} onAdd={(a) => setMeds([...meds, a])} />
            <div className="chips">
              {meds.map((m, i) => (
                <button key={i} className="chip on" onClick={() => setMeds(meds.filter((_, j) => j !== i))}>
                  {names[m.entity_id] || m.entity_id}{m.dose ? ` ${m.dose}${m.dose_unit}` : ''} ✕
                </button>
              ))}
            </div>
            <h2>4 · Lifestyle &amp; products you use</h2>
            <div className="chips">
              {LIFESTYLE.map((l) => (
                <button key={l.id} className={`chip ${lifestyle[l.id] ? 'on' : ''}`} onClick={() => setLifestyle({ ...lifestyle, [l.id]: !lifestyle[l.id] })}>{l.label}</button>
              ))}
            </div>
            <h2>5 · Anything that applies?</h2>
            <div className="chips">
              {PROFILE_FLAGS.map((p) => (
                <button key={p.id} className={`chip ${profile[p.id] ? 'on' : ''}`} onClick={() => setProfile({ ...profile, [p.id]: !profile[p.id] })}>{p.label}</button>
              ))}
            </div>
            <button className="primary" onClick={runPlan} disabled={busy}>{busy ? 'Building…' : 'Build my plan'}</button>
          </div>

          {planResult && (
            <div className="results">
              <h2>Your plan</h2>
              {planResult.plan.length === 0 && <p className="muted">No specific recommendations from this survey — tell us more above.</p>}
              <div className="plan-grid">
                {planResult.plan.map((p) => <PlanCard key={p.entity_id} item={p} names={names} />)}
                {planResult.gated.map((g) => <PlanCard key={g.entity_id} item={g} names={names} gated />)}
              </div>
              <Advisories advisories={planResult.advisories} />
              <Report report={planResult.report} names={names} />
            </div>
          )}
        </section>
      )}

      {mode === 'checker' && (
        <section>
          <div className="quiz">
            <h2>What's in your stack?</h2>
            <p className="muted">Add the supplements you take or plan to buy, plus your medications.</p>
            <AgentPicker entities={entities} onAdd={(a) => setStack([...stack, a])} />
            <div className="chips">
              {stack.map((m, i) => (
                <button key={i} className="chip on" onClick={() => setStack(stack.filter((_, j) => j !== i))}>
                  {names[m.entity_id] || m.entity_id}{m.dose ? ` ${m.dose}${m.dose_unit || 'mg'}` : ''} ✕
                </button>
              ))}
            </div>
            <h2>Lifestyle &amp; products you use</h2>
            <p className="muted">Quick-adds the relevant agent and sets your profile.</p>
            <div className="chips">
              {LIFESTYLE.map((l) => {
                const on = lifestyle[l.id]
                return (
                  <button key={l.id} className={`chip ${on ? 'on' : ''}`} onClick={() => {
                    const next = { ...lifestyle, [l.id]: !on }
                    setLifestyle(next)
                    if (l.entity) {
                      setStack((cur) => on
                        ? cur.filter((s) => s.entity_id !== l.entity)
                        : (cur.some((s) => s.entity_id === l.entity) ? cur : [...cur, { entity_id: l.entity, source: 'cart' }]))
                    }
                    if (l.profile) setCheckProfile((cur) => ({ ...cur, [l.profile]: !on }))
                  }}>{l.label}</button>
                )
              })}
            </div>
            <h2>Health profile</h2>
            <div className="chips">
              {PROFILE_FLAGS.map((p) => (
                <button key={p.id} className={`chip ${checkProfile[p.id] ? 'on' : ''}`} onClick={() => setCheckProfile({ ...checkProfile, [p.id]: !checkProfile[p.id] })}>{p.label}</button>
              ))}
            </div>
            <button className="primary" onClick={() => runCheck()} disabled={busy || stack.length === 0}>
              {busy ? 'Checking…' : `Check ${stack.length} item${stack.length === 1 ? '' : 's'}`}
            </button>
          </div>
          {checkResult && (
            <div className="results">
              <Report report={checkResult} names={names} />
              <div className="plan-grid">
                {stack.filter((s) => entities.find((e) => e.entity_id === s.entity_id)?.entity_type === 'supplement').map((s) => (
                  <div className="plan-card" key={s.entity_id}>
                    <div className="plan-head"><strong>{names[s.entity_id]}</strong></div>
                    <ResearchPanel entityId={s.entity_id} names={names} />
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>
      )}

      <footer>
        <p>{footer}</p>
        <p>Interaction data: curated, cited demo dataset (NIH ODS, NCCIH, FDA, peer-reviewed literature) — illustrative, not comprehensive. Every flag links to its source.</p>
      </footer>
    </div>
  )
}
