"use client";

import { useState } from "react";
import { UploadPanel, MetadataPanel, ImageMetadata } from "@/components/upload-panel";
import { OrchestrationPanel } from "@/components/orchestration-panel";
import dynamic from 'next/dynamic';

const EvidenceViewer = dynamic(
  () => import('@/components/evidence-viewer').then((mod) => mod.EvidenceViewer),
  { ssr: false }
);

export default function Home() {
  const [imageIds, setImageIds] = useState<string[]>([]);
  const [metadatas, setMetadatas] = useState<ImageMetadata[]>([]);
  const [jobId, setJobId] = useState<string | null>(null);
  const [trace, setTrace] = useState<any>(null);

  const handleUploadSuccess = (id: string, meta: ImageMetadata) => {
    setImageIds(prev => [...prev, id]);
    setMetadatas(prev => [...prev, meta]);
    setJobId(null);
    setTrace(null);
  };

  const handleClear = () => {
    setImageIds([]);
    setMetadatas([]);
    setJobId(null);
    setTrace(null);
  };

  return (
    <div className="workspace">
      <header className="topbar mb-8">
        <div>
          <h1 className="text-primary font-mono tracking-tight">SATQUERY<span className="text-foreground">.AI</span></h1>
          <p className="eyebrow mt-1">Autonomous Remote-Sensing Analysis</p>
        </div>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Column: Upload, Metadata, Orchestration */}
        <div className="lg:col-span-4 flex flex-col">
          {imageIds.length === 0 ? (
            <UploadPanel onUploadSuccess={handleUploadSuccess} label="Image A (Before)" />
          ) : (
            <>
              <div className="flex justify-between items-center mb-2">
                <span className="text-xs font-mono text-muted-foreground uppercase">Active Source</span>
                <button 
                  onClick={handleClear}
                  className="text-xs font-mono text-destructive hover:underline"
                >
                  Clear All
                </button>
              </div>
              {metadatas.map((meta, i) => (
                <div key={i} className="mb-4">
                  <MetadataPanel metadata={meta} label={i === 0 ? "Image A (Before)" : "Image B (After)"} />
                </div>
              ))}
              {imageIds.length === 1 && (
                <div className="mb-4">
                   <UploadPanel onUploadSuccess={handleUploadSuccess} label="Image B (After) (Optional for Change Detection)" />
                </div>
              )}
              <OrchestrationPanel imageIds={imageIds} jobId={jobId} setJobId={setJobId} trace={trace} setTrace={setTrace} />
            </>
          )}
        </div>

        {/* Right Column: Evidence Viewer (Map) */}
        <div className="lg:col-span-8">
          <EvidenceViewer metadata={metadatas[0] || null} jobId={jobId} trace={trace} />
        </div>
      </div>
    </div>
  );
}
