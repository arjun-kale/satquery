"use client";

import { useState, useEffect } from "react";
import { Play, Loader2, AlertCircle, CheckCircle2, ChevronRight, XCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface OrchestrationPanelProps {
  imageIds: string[];
  jobId: string | null;
  setJobId: (id: string | null) => void;
  trace: any;
  setTrace: (t: any) => void;
}

export function OrchestrationPanel({ imageIds, jobId, setJobId, trace, setTrace }: OrchestrationPanelProps) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setError(null);
    setTrace(null);
    setStatus("STARTING");

    try {
      const res = await fetch("http://localhost:8000/api/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image_ids: imageIds, query }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to create job");
      setJobId(data.id);
    } catch (err: any) {
      setError(err.message);
      setStatus(null);
    }
  };

  useEffect(() => {
    if (!jobId) return;
    
    let interval: NodeJS.Timeout;
    const poll = async () => {
      try {
        const res = await fetch(`http://localhost:8000/api/jobs/${jobId}/trace`);
        const data = await res.json();
        
        setStatus(data.status);
        setTrace(data.trace);
        
        if (data.failure_reason) {
          setError(data.failure_reason);
        }

        if (["COMPLETED", "FAILED", "REJECTED"].includes(data.status)) {
          clearInterval(interval);
        }
      } catch (err) {
        console.error("Polling error:", err);
      }
    };

    interval = setInterval(poll, 1000);
    poll(); // initial call
    return () => clearInterval(interval);
  }, [jobId]);

  const getStatusIcon = (stepStatus: string) => {
    switch (stepStatus) {
      case "COMPLETED": return <CheckCircle2 className="w-4 h-4 text-primary" />;
      case "FAILED": return <XCircle className="w-4 h-4 text-destructive" />;
      case "RUNNING": return <Loader2 className="w-4 h-4 text-secondary animate-spin" />;
      default: return <ChevronRight className="w-4 h-4 text-muted-foreground" />;
    }
  };

  return (
    <div className="flex flex-col gap-4 mt-8">
      <Card className="border-border bg-card">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-mono text-muted-foreground uppercase tracking-wider">Execute Query</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="flex gap-2">
            <Input 
              value={query} 
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. calculate water index for this region"
              className="font-mono bg-input rounded-none"
              disabled={["ROUTING", "EXECUTING"].includes(status || "")}
            />
            <Button 
              type="submit" 
              className="rounded-none bg-primary text-primary-foreground hover:bg-primary/90"
              disabled={!query.trim() || ["ROUTING", "EXECUTING"].includes(status || "")}
            >
              <Play className="w-4 h-4 mr-2" />
              RUN
            </Button>
          </form>
        </CardContent>
      </Card>

      {status && (
        <Card className="border-border bg-card">
          <CardHeader className="pb-3 border-b border-border">
            <div className="flex justify-between items-center">
              <CardTitle className="text-sm font-mono text-muted-foreground uppercase tracking-wider">
                Execution Trace
              </CardTitle>
              <span className={`text-xs font-mono px-2 py-1 border ${
                status === 'COMPLETED' ? 'text-primary border-primary' : 
                status === 'FAILED' || status === 'REJECTED' ? 'text-destructive border-destructive' : 
                'text-secondary border-secondary'
              }`}>
                {status}
              </span>
            </div>
          </CardHeader>
          <CardContent className="pt-4 p-0">
            {error && status === 'REJECTED' && (
              <div className="p-4 bg-destructive/10 text-destructive text-sm font-mono flex items-start gap-2">
                <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
                <span>{error}</span>
              </div>
            )}
            
            {trace && trace.steps && (
              <div className="flex flex-col">
                {trace.steps.map((step: any, idx: number) => (
                  <div key={idx} className="flex items-center gap-3 p-3 border-b border-border/50 hover:bg-muted/30 transition-colors">
                    {getStatusIcon(step.status)}
                    <span className="font-mono text-sm flex-1">{step.tool_name}</span>
                    <span className="font-mono text-xs text-muted-foreground">
                      {step.latency_ms ? `${(step.latency_ms / 1000).toFixed(2)}s` : '-'}
                    </span>
                  </div>
                ))}
              </div>
            )}
            {error && status === 'FAILED' && (
              <div className="p-4 border-t border-destructive/30 text-destructive text-sm font-mono">
                Error: {error}
              </div>
            )}
            
            {status === 'COMPLETED' && jobId && (
              <div className="p-4 border-t border-border/50">
                <Button 
                  onClick={() => window.open(`http://localhost:8000/api/jobs/${jobId}/report`, '_blank')}
                  variant="outline"
                  className="w-full font-mono text-sm"
                >
                  Download Report
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
