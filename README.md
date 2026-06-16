# Vitamin Advisor — Vitamin Shoppe POC

Supplement personalization + combinatorial interaction-safety engine. See `CLAUDE.md` for the build contract.

## Run it

**Backend** (port 8001 — 8000 is used by another local project):

```sh
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # first time
.venv/bin/python -m data.load_seed                                   # build app.db from seed_data.json
export ANTHROPIC_API_KEY=sk-ant-...                                  # for the /research endpoint (optional — degrades gracefully)
.venv/bin/uvicorn app.main:app --port 8001
```

**Frontend** (port 5174):

```sh
cd frontend
npm install        # first time
npm run dev
```

Open http://localhost:5174 — the three demo-scenario buttons at the top preload the acceptance scenarios.

## Tests

```sh
cd backend && .venv/bin/python -m pytest tests/ -v
```

20 tests: Layer-1 unit tests, the three scenario acceptance tests, Layer-2 extras (renal triple-whammy, rx-anchor), recommendation gates, and the Phase-7 guardrails audit (citation enforcement + forbidden-phrase scan).

## API

| Endpoint | What |
|---|---|
| `POST /plan` | survey → recommended stack + gated items + safety report (one round-trip) |
| `POST /check` | stack + meds + profile → findings (3-layer engine) |
| `GET /research/{entity}` | Claude + web_search cited 2-sentence research summary |
| `GET /entities` | searchable catalog |
| `GET /health`, `GET /disclaimer` | plumbing |
