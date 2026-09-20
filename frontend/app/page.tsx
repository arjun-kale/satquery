import { BackendHealth } from "../components/BackendHealth";

export default function HomePage() {
  return (
    <main className="workspace">
      <header className="topbar">
        <div>
          <p className="eyebrow">SATQUERY AI / MVP</p>
          <h1>Remote-sensing evidence workspace</h1>
        </div>
        <BackendHealth />
      </header>

      <section className="empty-state" aria-labelledby="phase-zero-title">
        <p className="eyebrow">SYSTEM READY</p>
        <h2 id="phase-zero-title">Phase 0 foundation is online.</h2>
        <p>
          GeoTIFF ingestion, model execution, and evidence traces are introduced in the
          following phases. This screen only confirms the UI-to-backend foundation.
        </p>
      </section>
    </main>
  );
}
