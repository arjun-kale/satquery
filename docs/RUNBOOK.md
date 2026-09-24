# SatQuery AI — Demo Runbook

## Judging / local demo (default)

Run everything on the team laptop. No internet required.

```bash
# Terminal 1 — backend
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend
npm run dev
```

Open `http://localhost:3000`. The top bar should show **SatQuery VLM on GPU** (real models). A **Mock models** tag means the backend was started with `SATQUERY_MODEL_MODE=mock` — never demo in that state.

Verify backend directly:
```bash
curl http://localhost:8000/health
# {"status":"ok","database":"ok","model_mode":"modal"}
```

---

## Remote public-sample demo (Vercel + Cloudflare Tunnel)

> ⚠️ Use **public imagery only**. Never send restricted coordinates or sensitive data through the tunnel.

```bash
# 1. Start backend locally
cd backend && uvicorn app.main:app --port 8000

# 2. Open a Cloudflare Tunnel
cloudflared tunnel --url http://localhost:8000
# Note the generated *.trycloudflare.com URL

# 3. Set NEXT_PUBLIC_API_BASE_URL in Vercel dashboard to the tunnel URL
# 4. Redeploy or trigger a Vercel rebuild
```

---

## Environment variables

| Variable | Where | Purpose |
|---|---|---|
| `SATQUERY_MODEL_MODE` | backend `.env` | `modal` (default, real models) / `mock` (dev only) / `local` |
| `SATQUERY_CORS_ORIGINS` | backend `.env` | Allowed frontend origins |
| `NEXT_PUBLIC_API_BASE_URL` | frontend `.env.local` | Backend base URL |

No model tokens or secrets belong in `NEXT_PUBLIC_*` variables.
