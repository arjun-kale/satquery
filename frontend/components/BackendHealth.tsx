"use client";

import { useEffect, useState } from "react";

type Health = { status: "ok"; database: "ok"; model_mode: "mock" | "local" | "modal" };

export function BackendHealth() {
  const [state, setState] = useState<"checking" | "online" | "offline">("checking");
  const [modelMode, setModelMode] = useState<Health["model_mode"] | null>(null);

  useEffect(() => {
    const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
    const controller = new AbortController();

    fetch(`${baseUrl}/health`, { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error("Backend health check failed");
        return (await response.json()) as Health;
      })
      .then((health) => {
        setModelMode(health.model_mode);
        setState("online");
      })
      .catch(() => setState("offline"));

    return () => controller.abort();
  }, []);

  const label = state === "online"
    ? `BACKEND ONLINE / ${modelMode?.toUpperCase()}`
    : state === "offline"
      ? "BACKEND OFFLINE"
      : "CHECKING BACKEND";

  return <span className={`status ${state}`}><span aria-hidden="true" />{label}</span>;
}
