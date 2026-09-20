# ADR-001: Next.js frontend on Vercel

## Decision

Use Next.js App Router, TypeScript and Tailwind CSS. Deploy the prototype UI to
Vercel when a public demo link is useful.

## Context

The UI needs a zero-cost, presentable evidence workspace with Git-based preview
deployments. It must not host ML models or geospatial processing.

## Options considered

- Next.js on Vercel
- React + Vite on static hosting
- A Python-only Streamlit UI

## Chosen approach and trade-offs

Next.js is the team stack and gives the most direct Vercel deployment path.
Vercel is limited to UI code; a direct browser-to-backend upload boundary avoids
function-size and raster-processing limits. A local Next.js run remains the
offline/sensitive-demo fallback.

## Future migration path

The frontend calls FastAPI through one API base URL, so it can move to any static
or self-hosted environment without changing the backend contract.
