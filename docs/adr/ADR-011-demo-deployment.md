# ADR-011: Laptop-first judging deployment

## Decision

Run FastAPI and SQLite on the team laptop. Use a temporary Cloudflare Tunnel only
for a remote public-sample demo; run Next.js locally for offline/sensitive demos.

## Context

A laptop behind a network boundary is not reachable by a Vercel UI without a
tunnel. Moving the backend to Modal would invalidate the selected local-state
model.

## Options considered

- Laptop backend + temporary tunnel
- Modal-hosted backend
- Paid always-on host

## Chosen approach and trade-offs

This resolves demo-day reachability without adding cost or persistent cloud
state. Public tunnel traffic must contain public sample imagery only.

## Future migration path

Use an approved static IP/hosting environment and durable storage when remote
production access becomes a requirement.
