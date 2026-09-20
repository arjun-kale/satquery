# SatQuery AI

Zero-budget remote-sensing analysis MVP for **SIH 2026 — PS 26167**.
Local FastAPI + SQLite backend · Next.js evidence UI · deterministic EO tools.

---

## Quick start

Requirements: **Python 3.11+** and **Node.js 20+**

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

```bash
curl http://localhost:8000/health
# {"status":"ok","database":"ok","model_mode":"mock"}
```

### Frontend

```bash
cd frontend
cp .env.local.example .env.local
npm install
npm run dev
```

Open `http://localhost:3000` — top-right shows `BACKEND ONLINE / MOCK`.

### Tests

```bash
cd backend
source .venv/bin/activate
pytest -v
```

### Build checks

```bash
cd frontend
npm run lint && npm run build
```

---

## Phases

| Phase | Status | Scope |
|---|---|---|
| 0 — Scaffold | ✅ Complete | FastAPI `/health`, SQLite job state machine, Next.js landing page |
| 1 — Ingestion & EO tools | 🔧 In progress | GeoTIFF ingest, NDVI/MNDWI/NDBI, geodesy, SAR calibration, guardrail |
| 2 — RS model adapters | ⏳ Pending | GeoChat, ChangeFormer, MockAdapter, M1 LoRA adaptation gate |
| 3 — Router & executor | ⏳ Pending | Embedding-template router, typed DAG executor, trace |
| 4 — Evidence UI | ⏳ Pending | Upload, metadata, query, viewer, trace panel, DAG timeline |
| 5 — Modal inference | ⏳ Pending | Optional GPU inference via Modal |
| 6 — Evaluation & handoff | ⏳ Pending | Benchmarks, KNOWN_LIMITATIONS, final docs |

---

## Demo modes

| Mode | When to use |
|---|---|
| **Local** | Judging demo — run Next.js + FastAPI on the team laptop |
| **Remote public-sample** | UI on Vercel, backend via temporary Cloudflare Tunnel — public imagery only |

See [`docs/RUNBOOK.md`](docs/RUNBOOK.md) for exact commands.

---

## Docs

| File | Purpose |
|---|---|
| [`docs/execution_plan.md`](docs/execution_plan.md) | Phased implementation plan, ADRs, API contract |
| [`docs/SIH_2026_SatQuery_AI_Master_Build_Plan.md`](docs/SIH_2026_SatQuery_AI_Master_Build_Plan.md) | Master build plan |
| [`docs/research_ps26167.md`](docs/research_ps26167.md) | Problem statement research notes |
| [`docs/RUNBOOK.md`](docs/RUNBOOK.md) | Demo runbook |
| [`docs/OPEN_ITEMS.md`](docs/OPEN_ITEMS.md) | Unresolved decisions and known gaps |
| [`docs/KNOWN_LIMITATIONS.md`](docs/KNOWN_LIMITATIONS.md) | Honest limitations for the demo |

---

## Constraints

- No model weights, datasets, uploads, or secrets committed to git.
- No raw multispectral/SAR arrays cross the VLM adapter boundary.
- No OpenAI / Gemini / Claude API — open models only.
- Vercel hosts UI only; never routes raster bytes or model calls.
