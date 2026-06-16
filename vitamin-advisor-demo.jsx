import React, { useState, useMemo, useRef } from "react";
import {
  Zap, Moon, Shield, Bone, Sparkles, Brain, Leaf, Heart,
  Pill, Wine, Sun, Salad, ArrowRight, ArrowLeft, AlertTriangle,
  Clock, CheckCircle2, Activity, Search, Loader2, FlaskConical, X
} from "lucide-react";

// ----------------------------- DATA -----------------------------

const GOALS = [
  { id: "energy", label: "Energy", icon: Zap },
  { id: "sleep", label: "Sleep", icon: Moon },
  { id: "immunity", label: "Immunity", icon: Shield },
  { id: "joint", label: "Joint & Mobility", icon: Bone },
  { id: "beauty", label: "Skin · Hair · Nails", icon: Sparkles },
  { id: "stress", label: "Stress & Mood", icon: Brain },
  { id: "digestion", label: "Digestion", icon: Leaf },
  { id: "heart", label: "Heart Health", icon: Heart },
];

const MEDS = [
  { id: "warfarin", label: "Warfarin / blood thinner" },
  { id: "levo", label: "Levothyroxine (thyroid)" },
  { id: "ssri", label: "SSRI antidepressant" },
  { id: "bp", label: "Blood pressure (ACE / ARB)" },
  { id: "statin", label: "Statin (cholesterol)" },
  { id: "metformin", label: "Metformin (diabetes)" },
  { id: "bc", label: "Birth control" },
];

const DIETS = [
  { id: "omni", label: "Omnivore" },
  { id: "veg", label: "Vegetarian" },
  { id: "vegan", label: "Vegan" },
];

// supplement catalog
const SUPP = {
  bcomplex:   { name: "B-Complex",           cat: "Foundational" },
  d3:         { name: "Vitamin D3 + K2",     cat: "Foundational" },
  b12:        { name: "Vitamin B12",         cat: "Foundational" },
  iron:       { name: "Iron + Vitamin C",    cat: "Foundational" },
  mag:        { name: "Magnesium Glycinate", cat: "Foundational" },
  vitc:       { name: "Vitamin C",           cat: "Immunity" },
  zinc:       { name: "Zinc",                cat: "Immunity" },
  omega:      { name: "Omega-3 Fish Oil",    cat: "Heart & Joint" },
  algal:      { name: "Algal Omega-3",       cat: "Heart & Joint" },
  coq10:      { name: "CoQ10",               cat: "Heart & Joint" },
  glucos:     { name: "Glucosamine",         cat: "Joint" },
  collagen:   { name: "Collagen Peptides",   cat: "Beauty" },
  biotin:     { name: "Biotin",              cat: "Beauty" },
  melatonin:  { name: "Melatonin",           cat: "Sleep" },
  ashwa:      { name: "Ashwagandha",         cat: "Mood" },
  probiotic:  { name: "Probiotic",           cat: "Digestion" },
};

// goal -> supplement ids
const GOAL_MAP = {
  energy:    ["bcomplex", "coq10"],
  sleep:     ["mag", "melatonin"],
  immunity:  ["vitc", "zinc", "d3"],
  joint:     ["omega", "glucos", "collagen"],
  beauty:    ["collagen", "biotin", "vitc"],
  stress:    ["mag", "ashwa", "bcomplex"],
  digestion: ["probiotic", "mag"],
  heart:     ["omega", "coq10", "mag"],
};

// ------------------------- RECOMMENDATION -------------------------

function buildStack(a) {
  const reasons = {}; // id -> [reasons]
  const add = (id, why) => {
    if (!reasons[id]) reasons[id] = [];
    if (why && !reasons[id].includes(why)) reasons[id].push(why);
  };

  a.goals.forEach((g) => {
    (GOAL_MAP[g] || []).forEach((id) =>
      add(id, `Supports your ${GOALS.find((x) => x.id === g).label.toLowerCase()} goal`)
    );
  });

  // lifestyle-driven rules
  if (a.alcohol === "yes")
    add("bcomplex", "Regular alcohol depletes B-vitamins (B1, folate, B12)");
  if (a.sun === "no")
    add("d3", "Limited daily sun — most people fall short on vitamin D");

  // diet-driven rules
  if (a.diet === "vegan") {
    add("b12", "B12 is found almost only in animal foods");
    add("algal", "Plant-based EPA/DHA source");
    add("d3", "Harder to get D from a plant-based diet");
    add("iron", "Plant (non-heme) iron absorbs less efficiently");
  }
  if (a.diet === "veg") {
    add("b12", "Vegetarian diets often run low on B12");
    add("iron", "Plant iron absorbs less efficiently — pair with vitamin C");
  }

  // if vegan, swap fish oil -> algal
  if (a.diet === "vegan" && reasons.omega) {
    add("algal", reasons.omega[0]);
    delete reasons.omega;
  }

  // medication-aware additions
  if (a.meds.includes("metformin"))
    add("b12", "Long-term metformin is well known to deplete B12");
  if (a.meds.includes("statin"))
    add("coq10", "Statins lower the body's natural CoQ10");

  return reasons;
}

// --------------------------- INTERACTIONS ---------------------------
// types: danger | caution | timing | synergy
function analyze(ids, meds, a) {
  const f = [];
  const has = (id) => ids.includes(id);
  const med = (id) => meds.includes(id);
  const push = (type, title, detail, action) =>
    f.push({ type, title, detail, action });

  // ---- DANGER / CAUTION: med interactions ----
  if (med("warfarin") && (has("omega") || has("algal")))
    push("caution", "Omega-3 + Warfarin",
      "High-dose fish oil can add to warfarin's blood-thinning effect, raising bleeding risk.",
      "Keep doses moderate and have your clinician check your INR.");

  if (med("warfarin") && has("d3"))
    push("timing", "Vitamin K2 + Warfarin",
      "The K2 in this D3 blend works against warfarin if intake swings up and down.",
      "Choose a K2-free vitamin D, and keep vitamin K intake consistent.");

  if (med("levo") && (has("mag") || has("iron")))
    push("caution", "Minerals + Levothyroxine",
      "Magnesium, calcium, and iron bind to thyroid medication and block its absorption.",
      "Take levothyroxine on its own, then wait 4 hours before any minerals.");

  if (med("bp") && has("mag"))
    push("timing", "Magnesium + Blood-pressure meds",
      "Magnesium can gently lower blood pressure on top of your medication.",
      "Fine for most people — worth a heads-up to your doctor if you feel lightheaded.");

  // ---- SYNERGY: positive pairings (the attach-rate moments) ----
  if (med("statin") && has("coq10"))
    push("synergy", "CoQ10 + Statin — good pairing",
      "Statins deplete CoQ10, which is linked to the muscle aches some people get.",
      "This pairing replenishes what the statin lowers.");

  if (med("metformin") && has("b12"))
    push("synergy", "B12 + Metformin — smart add",
      "Metformin is a known cause of low B12 over time.",
      "Adding B12 gets ahead of a very common deficiency.");

  if (has("iron") && has("vitc"))
    push("synergy", "Iron + Vitamin C — absorption boost",
      "Vitamin C converts iron into a form your gut absorbs far better.",
      "Take them together for maximum benefit.");

  // ---- TIMING / ABSORPTION ----
  if (has("iron"))
    push("timing", "How to take Iron",
      "Coffee, tea, and calcium can cut iron absorption by more than half.",
      "Take with vitamin C or orange juice, and keep 2 hours away from coffee, tea, and dairy.");

  if (has("iron") && has("mag"))
    push("timing", "Iron + Magnesium spacing",
      "Iron and magnesium compete for the same uptake pathway.",
      "Split them — iron in the morning, magnesium in the evening.");

  if (has("d3") || has("coq10") || has("omega") || has("algal"))
    push("timing", "Take fat-soluble nutrients with food",
      "Vitamin D, CoQ10, and Omega-3 absorb best alongside dietary fat.",
      "Take with your largest meal of the day.");

  if (has("mag") || has("melatonin"))
    push("timing", "Best taken at night",
      "Magnesium glycinate and melatonin support relaxation and sleep onset.",
      "Move these to your evening routine.");

  if (has("zinc"))
    push("timing", "Zinc over the long run",
      "Sustained high-dose zinc can slowly deplete copper.",
      "Look for a formula with a touch of copper if taking daily for months.");

  // ---- lifestyle info ----
  if (a.alcohol === "yes")
    push("timing", "Alcohol & your B-vitamins",
      "Alcohol increases how fast B-vitamins are used up and excreted.",
      "The B-Complex in your plan helps offset this.");

  return f;
}

// ----------------------------- STYLES -----------------------------

const FONTS = `
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600;9..144,700&family=Hanken+Grotesk:wght@400;500;600;700&display=swap');
`;

const C = {
  cream: "#FBF7EF",
  paper: "#FFFFFF",
  ink: "#1C1A14",
  muted: "#6E685A",
  line: "#E8E0CE",
  amber: "#E3A008",
  amberDeep: "#B07400",
  danger: "#B23A2E",
  dangerBg: "#FBEDEB",
  caution: "#C07A00",
  cautionBg: "#FBF2DD",
  timing: "#3B6B78",
  timingBg: "#EAF2F3",
  synergy: "#3D7A55",
  synergyBg: "#EAF3EC",
};

const SEV = {
  danger:  { c: C.danger,  bg: C.dangerBg,  icon: AlertTriangle, label: "Heads up" },
  caution: { c: C.caution, bg: C.cautionBg, icon: AlertTriangle, label: "Worth knowing" },
  timing:  { c: C.timing,  bg: C.timingBg,  icon: Clock,         label: "Take it right" },
  synergy: { c: C.synergy, bg: C.synergyBg, icon: CheckCircle2,  label: "Smart pairing" },
};

// ----------------------------- APP -----------------------------

export default function App() {
  const [step, setStep] = useState("intro");
  const [ans, setAns] = useState({
    goals: [], meds: [], alcohol: null, sun: null, diet: null,
  });

  const stack = useMemo(() => (step === "results" ? buildStack(ans) : {}), [step, ans]);
  const stackIds = Object.keys(stack);
  const findings = useMemo(
    () => (step === "results" ? analyze(stackIds, ans.meds, ans) : []),
    [step, stackIds.join(","), ans]
  );

  const toggle = (key, val) =>
    setAns((s) => {
      const arr = s[key];
      return { ...s, [key]: arr.includes(val) ? arr.filter((x) => x !== val) : [...arr, val] };
    });
  const set = (key, val) => setAns((s) => ({ ...s, [key]: val }));

  const canBuild =
    ans.goals.length > 0 && ans.alcohol && ans.sun && ans.diet;

  return (
    <div style={{ background: C.cream, color: C.ink, minHeight: "100vh", fontFamily: "'Hanken Grotesk', sans-serif" }}>
      <style>{FONTS}{CSS}</style>

      {/* header */}
      <header style={{ borderBottom: `1px solid ${C.line}`, background: C.cream }}>
        <div className="wrap" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "18px 0" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ width: 30, height: 30, borderRadius: 8, background: C.ink, display: "grid", placeItems: "center" }}>
              <FlaskConical size={17} color={C.amber} />
            </div>
            <div style={{ fontFamily: "'Fraunces', serif", fontWeight: 600, fontSize: 19, letterSpacing: "-0.01em" }}>
              StackWise
            </div>
          </div>
          <div style={{ fontSize: 12, color: C.muted, fontWeight: 600, letterSpacing: "0.04em", textTransform: "uppercase" }}>
            Concept · built for The Vitamin Shoppe
          </div>
        </div>
      </header>

      {step === "intro" && <Intro onStart={() => setStep("quiz")} />}
      {step === "quiz" && (
        <Quiz ans={ans} toggle={toggle} set={set} canBuild={canBuild}
          onBack={() => setStep("intro")} onBuild={() => setStep("results")} />
      )}
      {step === "results" && (
        <Results stack={stack} findings={findings} ans={ans}
          onRestart={() => { setAns({ goals: [], meds: [], alcohol: null, sun: null, diet: null }); setStep("quiz"); }} />
      )}

      <footer style={{ borderTop: `1px solid ${C.line}`, marginTop: 60 }}>
        <div className="wrap" style={{ padding: "24px 0", fontSize: 12.5, color: C.muted, lineHeight: 1.6 }}>
          Demonstration concept only — not medical advice. Interaction logic shown here is a curated
          illustrative rule set; a production build would sit on a licensed clinical database (e.g. NatMed)
          with pharmacist review.
        </div>
      </footer>
    </div>
  );
}

// ----------------------------- INTRO -----------------------------

function Intro({ onStart }) {
  return (
    <div className="wrap" style={{ padding: "70px 0 40px" }}>
      <div className="rise" style={{ maxWidth: 720 }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: C.amberDeep, letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 18 }}>
          The advisor in your pocket
        </div>
        <h1 style={{ fontFamily: "'Fraunces', serif", fontWeight: 600, fontSize: 52, lineHeight: 1.04, letterSpacing: "-0.02em", margin: 0 }}>
          Know exactly what to take —<br />and what <em style={{ fontStyle: "italic", color: C.amberDeep }}>not</em> to take together.
        </h1>
        <p style={{ fontSize: 18, color: C.muted, lineHeight: 1.55, marginTop: 22, maxWidth: 580 }}>
          A 60-second profile builds a personalized supplement plan, then checks every item against
          your medications, your other supplements, and how your body actually absorbs them.
        </p>
        <button className="btn-primary rise-2" onClick={onStart} style={{ marginTop: 30 }}>
          Build my plan <ArrowRight size={18} />
        </button>

        <div className="rise-3" style={{ display: "flex", gap: 30, marginTop: 54, flexWrap: "wrap" }}>
          {[
            { n: "Personalized", d: "Recommendations from goals, diet & lifestyle" },
            { n: "Interaction-aware", d: "Flags supplement ↔ medication conflicts" },
            { n: "Absorption-smart", d: "Tells you how & when to take each one" },
          ].map((x) => (
            <div key={x.n} style={{ maxWidth: 200 }}>
              <div style={{ fontFamily: "'Fraunces', serif", fontWeight: 600, fontSize: 17 }}>{x.n}</div>
              <div style={{ fontSize: 13.5, color: C.muted, marginTop: 4, lineHeight: 1.45 }}>{x.d}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ----------------------------- QUIZ -----------------------------

function Quiz({ ans, toggle, set, canBuild, onBack, onBuild }) {
  return (
    <div className="wrap" style={{ padding: "44px 0 20px", maxWidth: 760 }}>
      <button className="link" onClick={onBack}><ArrowLeft size={15} /> Back</button>

      <Section n="01" title="What are your health goals?" hint="Pick all that apply">
        <div className="chips">
          {GOALS.map((g) => {
            const on = ans.goals.includes(g.id);
            const Icon = g.icon;
            return (
              <button key={g.id} className={`chip ${on ? "on" : ""}`} onClick={() => toggle("goals", g.id)}>
                <Icon size={16} /> {g.label}
              </button>
            );
          })}
        </div>
      </Section>

      <Section n="02" title="Are you taking any medications?" hint="This is how we catch conflicts — pick any that apply">
        <div className="chips">
          {MEDS.map((m) => {
            const on = ans.meds.includes(m.id);
            return (
              <button key={m.id} className={`chip ${on ? "on" : ""}`} onClick={() => toggle("meds", m.id)}>
                <Pill size={15} /> {m.label}
              </button>
            );
          })}
        </div>
      </Section>

      <Section n="03" title="Do you drink alcohol regularly?" icon={Wine}>
        <Toggle value={ans.alcohol} onChange={(v) => set("alcohol", v)}
          options={[["yes", "Yes"], ["no", "No / rarely"]]} />
      </Section>

      <Section n="04" title="Are you in direct sunlight 15+ min on most days?" icon={Sun}>
        <Toggle value={ans.sun} onChange={(v) => set("sun", v)}
          options={[["yes", "Yes"], ["no", "Not really"]]} />
      </Section>

      <Section n="05" title="How do you eat?" icon={Salad}>
        <Toggle value={ans.diet} onChange={(v) => set("diet", v)}
          options={DIETS.map((d) => [d.id, d.label])} />
      </Section>

      <div style={{ marginTop: 36, display: "flex", alignItems: "center", gap: 16 }}>
        <button className="btn-primary" disabled={!canBuild} onClick={onBuild}
          style={{ opacity: canBuild ? 1 : 0.4, cursor: canBuild ? "pointer" : "not-allowed" }}>
          See my plan <ArrowRight size={18} />
        </button>
        {!canBuild && <span style={{ fontSize: 13, color: C.muted }}>Answer the goals + last three to continue</span>}
      </div>
    </div>
  );
}

function Section({ n, title, hint, icon: Icon, children }) {
  return (
    <div style={{ marginTop: 38 }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
        <span style={{ fontFamily: "'Fraunces', serif", color: C.amberDeep, fontSize: 14, fontWeight: 600 }}>{n}</span>
        <h2 style={{ fontFamily: "'Fraunces', serif", fontWeight: 600, fontSize: 23, margin: 0, letterSpacing: "-0.01em", display: "flex", alignItems: "center", gap: 9 }}>
          {Icon && <Icon size={20} color={C.muted} />}{title}
        </h2>
      </div>
      {hint && <div style={{ fontSize: 13.5, color: C.muted, marginTop: 5, marginLeft: 26 }}>{hint}</div>}
      <div style={{ marginTop: 16, marginLeft: 26 }}>{children}</div>
    </div>
  );
}

function Toggle({ value, onChange, options }) {
  return (
    <div className="chips">
      {options.map(([v, label]) => (
        <button key={v} className={`chip ${value === v ? "on" : ""}`} onClick={() => onChange(v)}>
          {label}
        </button>
      ))}
    </div>
  );
}

// ----------------------------- RESULTS -----------------------------

function Results({ stack, findings, ans, onRestart }) {
  const ids = Object.keys(stack);
  const grouped = {};
  ids.forEach((id) => {
    const cat = SUPP[id].cat;
    (grouped[cat] = grouped[cat] || []).push(id);
  });

  const order = ["danger", "caution", "synergy", "timing"];
  const sortedFindings = [...findings].sort((a, b) => order.indexOf(a.type) - order.indexOf(b.type));
  const flags = findings.filter((f) => f.type === "danger" || f.type === "caution").length;

  return (
    <div className="wrap" style={{ padding: "44px 0 20px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", flexWrap: "wrap", gap: 12 }}>
        <div>
          <div style={{ fontSize: 13, fontWeight: 700, color: C.amberDeep, letterSpacing: "0.06em", textTransform: "uppercase" }}>
            Your plan
          </div>
          <h1 style={{ fontFamily: "'Fraunces', serif", fontWeight: 600, fontSize: 38, margin: "6px 0 0", letterSpacing: "-0.02em" }}>
            {ids.length} supplements, checked & optimized
          </h1>
        </div>
        <button className="link" onClick={onRestart}><ArrowLeft size={15} /> Start over</button>
      </div>

      {/* stack grid */}
      <div style={{ marginTop: 30, display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(230px, 1fr))", gap: 14 }}>
        {ids.map((id, i) => (
          <div key={id} className="card rise" style={{ animationDelay: `${i * 50}ms` }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div style={{ fontFamily: "'Fraunces', serif", fontWeight: 600, fontSize: 17 }}>{SUPP[id].name}</div>
              <span className="tag">{SUPP[id].cat}</span>
            </div>
            <ul style={{ margin: "10px 0 0", padding: 0, listStyle: "none" }}>
              {stack[id].map((r, j) => (
                <li key={j} style={{ fontSize: 13, color: C.muted, lineHeight: 1.45, display: "flex", gap: 7, marginTop: 5 }}>
                  <span style={{ color: C.amber, marginTop: 1 }}>•</span> {r}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      {/* the differentiator */}
      <div style={{ marginTop: 50, display: "flex", alignItems: "center", gap: 12 }}>
        <Activity size={22} color={C.ink} />
        <h2 style={{ fontFamily: "'Fraunces', serif", fontWeight: 600, fontSize: 27, margin: 0, letterSpacing: "-0.01em" }}>
          Interaction & optimization report
        </h2>
      </div>
      <p style={{ fontSize: 14.5, color: C.muted, marginTop: 6, maxWidth: 620 }}>
        {flags > 0
          ? `We found ${flags} thing${flags > 1 ? "s" : ""} to be aware of, plus timing tips to get more from every dose.`
          : "No conflicts found. Here's how to get the most out of your plan."}
      </p>

      <div style={{ marginTop: 18, display: "flex", flexDirection: "column", gap: 11 }}>
        {sortedFindings.map((f, i) => {
          const s = SEV[f.type];
          const Icon = s.icon;
          return (
            <div key={i} className="finding rise" style={{ animationDelay: `${i * 40}ms`, borderLeft: `3px solid ${s.c}` }}>
              <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
                <div style={{ width: 26, height: 26, borderRadius: 7, background: s.bg, display: "grid", placeItems: "center", flexShrink: 0 }}>
                  <Icon size={15} color={s.c} />
                </div>
                <div style={{ fontWeight: 700, fontSize: 15 }}>{f.title}</div>
                <span style={{ marginLeft: "auto", fontSize: 11, fontWeight: 700, color: s.c, background: s.bg, padding: "3px 9px", borderRadius: 20, letterSpacing: "0.03em", textTransform: "uppercase" }}>
                  {s.label}
                </span>
              </div>
              <div style={{ fontSize: 14, color: C.ink, lineHeight: 1.5, marginTop: 9 }}>{f.detail}</div>
              <div style={{ fontSize: 13.5, color: s.c, fontWeight: 600, lineHeight: 1.45, marginTop: 7, display: "flex", gap: 7 }}>
                <ArrowRight size={15} style={{ flexShrink: 0, marginTop: 2 }} /> {f.action}
              </div>
            </div>
          );
        })}
      </div>

      {/* AI layers */}
      <AIAdvisor />
      <ResearchScanner stackIds={ids} />
    </div>
  );
}

// ----------------------- AI: combo checker -----------------------

function AIAdvisor() {
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);
  const [res, setRes] = useState(null);
  const [err, setErr] = useState(null);

  const ask = async () => {
    if (!q.trim()) return;
    setLoading(true); setErr(null); setRes(null);
    try {
      const r = await fetch("https://api.anthropic.com/v1/messages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model: "claude-sonnet-4-20250514",
          max_tokens: 1000,
          messages: [{
            role: "user",
            content: `A consumer is asking about taking these together: "${q}". Assess any interaction or absorption issue. Respond ONLY with raw JSON, no markdown, in this exact shape: {"severity":"none|low|moderate|high","summary":"one plain-language sentence","recommendation":"one practical sentence"}`
          }],
        }),
      });
      const data = await r.json();
      const text = data.content.filter((b) => b.type === "text").map((b) => b.text).join("").replace(/```json|```/g, "").trim();
      setRes(JSON.parse(text));
    } catch (e) {
      setErr("Couldn't reach the advisor just now. Try again in a moment.");
    } finally {
      setLoading(false);
    }
  };

  const sevColor = { none: C.synergy, low: C.timing, moderate: C.caution, high: C.danger };

  return (
    <div className="panel" style={{ marginTop: 48 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
        <Search size={18} color={C.amberDeep} />
        <div style={{ fontFamily: "'Fraunces', serif", fontWeight: 600, fontSize: 19 }}>Ask the advisor</div>
        <span className="live">AI · live</span>
      </div>
      <div style={{ fontSize: 13.5, color: C.muted, marginTop: 5 }}>
        Check anything not in your plan. Try “ibuprofen and fish oil” or “St. John's Wort and birth control.”
      </div>
      <div style={{ display: "flex", gap: 8, marginTop: 14 }}>
        <input className="input" value={q} placeholder="e.g. magnesium and my blood pressure pill"
          onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && ask()} />
        <button className="btn-primary" onClick={ask} disabled={loading} style={{ flexShrink: 0 }}>
          {loading ? <Loader2 size={17} className="spin" /> : "Check"}
        </button>
      </div>

      {err && <div style={{ marginTop: 12, fontSize: 13.5, color: C.danger }}>{err}</div>}
      {res && (
        <div className="rise" style={{ marginTop: 14, padding: 16, borderRadius: 12, background: C.cream, border: `1px solid ${C.line}` }}>
          <span style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.04em", color: sevColor[res.severity] || C.muted, background: C.paper, border: `1px solid ${C.line}`, padding: "3px 10px", borderRadius: 20 }}>
            {res.severity} concern
          </span>
          <div style={{ fontSize: 14.5, lineHeight: 1.5, marginTop: 11 }}>{res.summary}</div>
          <div style={{ fontSize: 13.5, color: C.amberDeep, fontWeight: 600, marginTop: 8, display: "flex", gap: 7 }}>
            <ArrowRight size={15} style={{ flexShrink: 0, marginTop: 2 }} /> {res.recommendation}
          </div>
        </div>
      )}
    </div>
  );
}

// -------------------- AI: latest research scan --------------------

function ResearchScanner({ stackIds }) {
  const [active, setActive] = useState(null);
  const [loading, setLoading] = useState(false);
  const [out, setOut] = useState(null);
  const [err, setErr] = useState(null);

  const names = stackIds.map((id) => SUPP[id].name);
  const pick = (name) => name.replace(/\s*\+.*/, "").replace(/ Peptides| Glycinate| Fish Oil/i, "").trim();

  const scan = async (name) => {
    setActive(name); setLoading(true); setOut(null); setErr(null);
    try {
      const r = await fetch("https://api.anthropic.com/v1/messages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model: "claude-sonnet-4-20250514",
          max_tokens: 1000,
          messages: [{
            role: "user",
            content: `Search for the most recent research or news on the supplement "${pick(name)}". Then give me a 2-sentence plain-language summary of what's newest, for a curious consumer. Be specific about findings if you can.`
          }],
          tools: [{ type: "web_search_20250305", name: "web_search" }],
        }),
      });
      const data = await r.json();
      const text = data.content.filter((b) => b.type === "text").map((b) => b.text).join(" ").trim();
      setOut(text || "No fresh summary available right now.");
    } catch (e) {
      setErr("Research scan unavailable just now.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="panel" style={{ marginTop: 20 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
        <FlaskConical size={18} color={C.amberDeep} />
        <div style={{ fontFamily: "'Fraunces', serif", fontWeight: 600, fontSize: 19 }}>What's new in research</div>
        <span className="live">AI · live web</span>
      </div>
      <div style={{ fontSize: 13.5, color: C.muted, marginTop: 5 }}>
        The science moves. Tap any item in your plan to pull the latest.
      </div>
      <div className="chips" style={{ marginTop: 14 }}>
        {[...new Set(names)].map((n) => (
          <button key={n} className={`chip ${active === n ? "on" : ""}`} onClick={() => scan(n)}>
            {pick(n)}
          </button>
        ))}
      </div>
      {loading && (
        <div style={{ marginTop: 14, fontSize: 13.5, color: C.muted, display: "flex", alignItems: "center", gap: 8 }}>
          <Loader2 size={15} className="spin" /> Scanning recent literature for {pick(active)}…
        </div>
      )}
      {err && <div style={{ marginTop: 12, fontSize: 13.5, color: C.danger }}>{err}</div>}
      {out && !loading && (
        <div className="rise" style={{ marginTop: 14, padding: 16, borderRadius: 12, background: C.cream, border: `1px solid ${C.line}`, fontSize: 14.5, lineHeight: 1.55 }}>
          {out}
        </div>
      )}
    </div>
  );
}

// ----------------------------- CSS -----------------------------

const CSS = `
.wrap { max-width: 940px; margin: 0 auto; padding-left: 24px; padding-right: 24px; }
.btn-primary {
  background: ${C.ink}; color: ${C.cream}; border: none; border-radius: 999px;
  padding: 13px 24px; font-size: 15px; font-weight: 600; font-family: inherit;
  display: inline-flex; align-items: center; gap: 9px; cursor: pointer; transition: transform .15s, background .2s;
}
.btn-primary:hover:not(:disabled) { transform: translateY(-1px); background: #2c2920; }
.link {
  background: none; border: none; color: ${C.muted}; font-family: inherit; font-size: 14px;
  font-weight: 600; cursor: pointer; display: inline-flex; align-items: center; gap: 6px; padding: 4px 0;
}
.link:hover { color: ${C.ink}; }
.chips { display: flex; flex-wrap: wrap; gap: 9px; }
.chip {
  background: ${C.paper}; border: 1.5px solid ${C.line}; border-radius: 999px;
  padding: 9px 16px; font-size: 14px; font-weight: 500; font-family: inherit; color: ${C.ink};
  cursor: pointer; display: inline-flex; align-items: center; gap: 7px; transition: all .15s;
}
.chip:hover { border-color: ${C.amber}; }
.chip.on { background: ${C.ink}; color: ${C.cream}; border-color: ${C.ink}; }
.card {
  background: ${C.paper}; border: 1px solid ${C.line}; border-radius: 14px; padding: 16px;
}
.tag {
  font-size: 10.5px; font-weight: 700; text-transform: uppercase; letter-spacing: .04em;
  color: ${C.amberDeep}; background: ${C.cautionBg}; padding: 3px 8px; border-radius: 6px;
}
.finding {
  background: ${C.paper}; border: 1px solid ${C.line}; border-radius: 12px; padding: 15px 17px;
}
.panel {
  background: ${C.paper}; border: 1px solid ${C.line}; border-radius: 16px; padding: 22px 22px 24px;
}
.live {
  font-size: 10.5px; font-weight: 700; text-transform: uppercase; letter-spacing: .05em;
  color: ${C.synergy}; background: ${C.synergyBg}; padding: 3px 9px; border-radius: 20px; margin-left: 2px;
}
.input {
  flex: 1; background: ${C.cream}; border: 1.5px solid ${C.line}; border-radius: 999px;
  padding: 12px 18px; font-size: 14.5px; font-family: inherit; color: ${C.ink}; outline: none; transition: border .15s;
}
.input:focus { border-color: ${C.amber}; }
.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.rise { animation: rise .5s cubic-bezier(.2,.7,.2,1) both; }
.rise-2 { animation: rise .5s cubic-bezier(.2,.7,.2,1) .08s both; }
.rise-3 { animation: rise .5s cubic-bezier(.2,.7,.2,1) .16s both; }
@keyframes rise { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: translateY(0); } }
h1 em { font-style: italic; }
`;
