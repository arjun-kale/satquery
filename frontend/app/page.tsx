"use client";

import dynamic from "next/dynamic";

// The workspace is entirely client state (uploads, polling, pan/zoom); render it client-side only.
const Workspace = dynamic(() => import("@/components/workspace/workspace").then((m) => m.Workspace), {
  ssr: false,
  loading: () => <div className="h-dvh bg-base" />,
});

export default function Home() {
  return <Workspace />;
}
