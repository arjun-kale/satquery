# Deployment

Live since 2026-09-25.

| Part | Where | Notes |
|---|---|---|
| Frontend | **https://satcore.vercel.app** (Vercel project `satcore`, scope `arjunkale-7`) | Next.js. `NEXT_PUBLIC_API_BASE_URL` = the Railway URL (baked in at build time) |
| Backend | **https://satquery-api-production-7842.up.railway.app** (Railway project `satquery`, service `satquery-api`) | Dockerfile in `backend/`; volume `/data` (uploads, SQLite, weights, samples) |
| VLM (GeoChat-7B + M2 LoRA) | Hugging Face private repo `arjun-kale/satquery-vlm` → **Inference Endpoint (not created yet, see below)** | Custom handler `hf_endpoint/handler.py` (same loading/prompts as `modal_worker/infer.py`) |
| ChangeFormer V6 (DSIFN) | Private repo `arjun-kale/satquery-changeformer` | Downloaded by the backend on first start; runs on CPU |
| Sample scenes | Private dataset `arjun-kale/satquery-samples` | Downloaded by the backend on first start |

## Backend variables (Railway → satquery-api)

| Variable | Value |
|---|---|
| `SATQUERY_MODEL_MODE` | `hf` |
| `SATQUERY_HF_ENDPOINT_URL` | the Inference Endpoint URL (**set once the endpoint exists**) |
| `SATQUERY_HF_TOKEN` | a Hugging Face token that can read the private repos and call the endpoint |
| `SATQUERY_HF_CHANGEFORMER_REPO` | `arjun-kale/satquery-changeformer` |
| `SATQUERY_HF_SAMPLES_REPO` | `arjun-kale/satquery-samples` |
| `SATQUERY_CORS_ORIGINS` | `https://satcore.vercel.app` |

Set a variable without echoing it: `printf '%s' "$VALUE" | railway variables --service satquery-api --set-from-stdin NAME`.

## Remaining step: create the GPU endpoint

Hugging Face needs a payment method before it will create an Inference Endpoint
(https://huggingface.co/settings/billing). Then:

```bash
hf endpoints deploy satquery-vlm \
  --repo arjun-kale/satquery-vlm --task custom --framework pytorch \
  --accelerator gpu --vendor aws --region us-east-1 \
  --instance-type nvidia-l4 --instance-size x1 \
  --min-replica 0 --max-replica 1 --scale-to-zero-timeout 15 \
  --type authenticated
hf endpoints describe satquery-vlm          # wait for "running", copy the URL
printf '%s' "<endpoint url>" | railway variables --service satquery-api --set-from-stdin SATQUERY_HF_ENDPOINT_URL
```

- **Cost:** an L4 is $0.80/hour while awake. It scales to zero after 15 idle minutes and then costs
  nothing. The first request after idle waits while it wakes (a few minutes). The backend waits up to
  `SATQUERY_HF_WAIT_S` (600 s) and the UI shows the measured wake time on the step.
- **First test:** ask one "Describe this scene" question on the city sample, then check the step
  shows `SatQuery VLM · base weights` and a confidence. If the endpoint fails to start, read its logs
  in the HF UI: the handler pins `transformers==4.51.3`, `peft==0.15.2` and `bitsandbytes==0.45.5`,
  which must match the endpoint image's torch/CUDA.
- **Demo window:** `hf endpoints update satquery-vlm --min-replica 1` keeps it warm ($0.80/h). Set it
  back to 0 afterwards.

## Redeploying

- **Backend:** `cd backend && railway up --service satquery-api --detach`. `.railwayignore` keeps
  `.venv` and `data/` out; without it the upload is ~300 MB and Railway rejects it (413).
- **Frontend:** `cd frontend && vercel deploy --prod --yes`.
  - If the deployment shows **BLOCKED**, the git commit author isn't linked to the Vercel account.
    The fix is to add `kalearjun2368@gmail.com` to the Vercel account (Account Settings → Emails)
    or connect GitHub.
  - Until then, deploy from a copy without `.git`:
    `tar --exclude=node_modules --exclude=.next --exclude='.env*' -cf - . | tar -xf - -C /tmp/satcore && (cd /tmp/satcore && vercel deploy --prod --yes)`
  - `vercel.json` pins the framework to Next.js. Without it the project was created as "Other" and
    the build failed looking for `public/`.
- **VLM weights:** `HF_TOKEN=… modal run modal_worker/publish_hf.py --repo-id arjun-kale/satquery-vlm`
  copies from the Modal volume in Modal's datacenter. Endpoint handler changes can also go up
  directly: `hf upload arjun-kale/satquery-vlm hf_endpoint/ .`
- **Assets:** `cd backend && HF_TOKEN=… .venv/bin/python scripts/publish_assets_hf.py --user arjun-kale`
