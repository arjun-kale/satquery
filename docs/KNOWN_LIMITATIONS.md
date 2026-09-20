# Known limitations

- Phase 0 contains no ingestion, geospatial processing, model execution, jobs
  API, or execution trace implementation beyond the foundational state machine.
- The UI health indicator is intentionally the only frontend feature.
- Model mode defaults to `mock`; no GPU or Modal dependency is needed for Phase 0.
- Vercel, Cloudflare Tunnel, and Modal are prototype-only routes and do not
  support a sovereign/no-foreign-inference deployment claim.
- Existing remote-sensing models are not SatCore. The team must complete the
  documented Phase 2 LoRA adaptation experiment before claiming M1 compliance.
