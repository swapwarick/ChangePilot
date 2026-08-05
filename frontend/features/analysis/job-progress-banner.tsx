"use client";

import { useEffect, useState } from "react";
import { Loader2, CheckCircle2, AlertCircle, Cpu } from "lucide-react";
import { AnalysisJobStatus } from "@/types/api";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

interface JobProgressBannerProps {
  jobId: string;
  onJobComplete: (analysisId: string) => void;
}

export function JobProgressBanner({ jobId, onJobComplete }: JobProgressBannerProps) {
  const [job, setJob] = useState<AnalysisJobStatus | null>(null);

  useEffect(() => {
    let interval: any = null;

    const pollJob = async () => {
      try {
        const res = await fetch(`${API_BASE}/jobs/${jobId}`);
        if (res.ok) {
          const data: AnalysisJobStatus = await res.json();
          setJob(data);
          if (data.status === "COMPLETED" && data.analysis_id) {
            clearInterval(interval);
            onJobComplete(data.analysis_id);
          } else if (data.status === "FAILED") {
            clearInterval(interval);
          }
        }
      } catch (err) {}
    };

    pollJob();
    interval = setInterval(pollJob, 2000);

    return () => clearInterval(interval);
  }, [jobId, onJobComplete]);

  if (!job) return null;

  const isFailed = job.status === "FAILED";
  const isCompleted = job.status === "COMPLETED";

  return (
    <div className={`mb-6 rounded-lg border p-4 transition-all ${
      isFailed ? "border-destructive/40 bg-destructive/10" : isCompleted ? "border-emerald-500/40 bg-emerald-500/10" : "border-primary/40 bg-primary/10"
    }`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          {isFailed ? (
            <AlertCircle className="size-5 text-destructive" />
          ) : isCompleted ? (
            <CheckCircle2 className="size-5 text-emerald-500" />
          ) : (
            <Cpu className="size-5 text-primary animate-pulse" />
          )}
          <div>
            <div className="text-sm font-semibold flex items-center gap-2">
              <span>Async Worker Job ({job.status})</span>
              {!isCompleted && !isFailed && <Loader2 className="size-3 animate-spin text-primary" />}
            </div>
            <div className="text-xs text-muted-foreground">{job.step}</div>
          </div>
        </div>

        <div className="text-right">
          <div className="text-sm font-bold">{job.progress}%</div>
          <div className="w-32 h-1.5 bg-muted rounded-full overflow-hidden mt-1">
            <div
              className={`h-full transition-all duration-500 ${isFailed ? "bg-destructive" : isCompleted ? "bg-emerald-500" : "bg-primary"}`}
              style={{ width: `${job.progress}%` }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
