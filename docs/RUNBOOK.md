# SatQuery MVP Runbook

## Phase 0 local demo mode

Use this mode for judging when the UI and backend run on the same laptop. It is
the default and does not require a tunnel.

1. Start FastAPI on port 8000.
2. Start Next.js on port 3000 with `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`.
3. Confirm the UI status reads `BACKEND ONLINE / MOCK`.

## Remote public-sample mode

Only use public sample imagery. Start the backend locally and expose port 8000
through a short-lived Cloudflare Tunnel. Set the deployed Vercel project's
`NEXT_PUBLIC_API_BASE_URL` to that HTTPS tunnel URL and add the Vercel origin to
`SATQUERY_CORS_ORIGINS`.

Do not use a Vercel deployment, tunnel, or Modal with restricted imagery or
sensitive coordinates. The final system cannot claim sovereign hosting in this
mode.

## Diagnosing a failed request

Future API errors include a `request_id`. Search backend logs by that ID, then
inspect the job's state transition and tool-step trace. Phase 0 only exposes
`/health`; ingestion and execution arrive in later phases.
