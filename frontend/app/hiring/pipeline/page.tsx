// app/hiring/pipeline/page.tsx
"use client";

import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Job, PipelineResponse } from "@/lib/types";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { ProgressRing } from "@/components/ui/ProgressRing";
import { Zap, Loader2, Play, CheckCircle, Circle, ArrowRight } from "lucide-react";

export default function PipelineSupervisorPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedJobId, setSelectedJobId] = useState("");
  const [topK, setTopK] = useState(10);

  const [loadingJobs, setLoadingJobs] = useState(true);
  const [running, setRunning] = useState(false);
  const [activeStep, setActiveStep] = useState(0); // 0: idle, 1: Job Analysis, 2: Retrieval, 3: Scoring, 4: Interview, 5: Done
  const [result, setResult] = useState<PipelineResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadJobs = async () => {
      try {
        setLoadingJobs(true);
        const data = await api.jobs.list();
        setJobs(data.items || []);
        if (data.items?.length > 0) setSelectedJobId(data.items[0].id);
      } catch (err) {
        console.error("Pipeline load jobs error:", err);
      } finally {
        setLoadingJobs(false);
      }
    };
    loadJobs();
  }, []);

  const handleRunPipeline = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedJobId) return;

    try {
      setRunning(true);
      setError(null);
      setResult(null);

      // Simulated stepping to make execution stages transparent and visually outstanding
      setActiveStep(1);
      await new Promise((r) => setTimeout(r, 1500)); // Simulating Job Node
      setActiveStep(2);
      await new Promise((r) => setTimeout(r, 1500)); // Simulating Vector Retrieval Node

      setActiveStep(3);
      // Execute pipeline API call which triggers all nodes at backend
      const data = await api.hiring.pipeline(selectedJobId, topK);

      setActiveStep(4);
      await new Promise((r) => setTimeout(r, 1200)); // Simulating Interview generation node

      setResult(data);
      setActiveStep(5);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || "Failed to execute pipeline");
      setActiveStep(0);
    } finally {
      setRunning(false);
    }
  };

  const steps = [
    { label: "Job Analysis Node", desc: "Extracting JD semantic structure" },
    { label: "Vector Retrieval Node", desc: "pgvector ANN cosine distance check" },
    { label: "AI Match Evaluation", desc: "Concurrent multi-factor fit scoring" },
    { label: "Interview Generation", desc: "Tailoring technical evaluation packs" },
  ];

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-extrabold text-slate-100 tracking-tight">Supervisor Orchestrator</h1>
        <p className="text-sm text-slate-400 mt-1">
          Trigger the multi-agent LangGraph supervisor flow. Processes JDs, retrieves candidate vectors, matches, and generates kits.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Column: Config Panel */}
        <div className="space-y-6">
          <Card>
            <h3 className="text-md font-bold text-slate-200 mb-6 font-mono text-xs uppercase tracking-wider text-slate-500">
              Run Configuration
            </h3>

            {loadingJobs ? (
              <div className="h-40 skeleton rounded-xl" />
            ) : (
              <form onSubmit={handleRunPipeline} className="space-y-5">
                {error && (
                  <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-400 text-xs rounded-xl">
                    {error}
                  </div>
                )}

                <div className="space-y-1.5">
                  <label className="text-xs font-bold uppercase tracking-wider text-slate-500 font-mono">
                    Select Target Job Posting
                  </label>
                  <select
                    value={selectedJobId}
                    onChange={(e) => setSelectedJobId(e.target.value)}
                    className="input-base"
                    required
                    disabled={running}
                  >
                    {jobs.map((job) => (
                      <option key={job.id} value={job.id}>
                        {job.title}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="space-y-1.5">
                  <div className="flex justify-between items-center text-xs font-bold uppercase tracking-wider text-slate-500 font-mono">
                    <label>Candidate Sample Pool</label>
                    <span className="text-slate-300 font-mono text-[10px]">{topK} candidates</span>
                  </div>
                  <input
                    type="range"
                    min="5"
                    max="50"
                    value={topK}
                    onChange={(e) => setTopK(parseInt(e.target.value))}
                    className="w-full accent-violet-500 cursor-pointer bg-white/5 h-1.5 rounded-lg appearance-none"
                    disabled={running}
                  />
                </div>

                <button
                  type="submit"
                  disabled={running || !selectedJobId}
                  className="w-full flex items-center justify-center gap-2 px-5 py-3 rounded-xl bg-gradient-primary hover:opacity-90 font-semibold text-sm text-white transition shadow-glow-violet-sm disabled:opacity-50"
                >
                  {running ? (
                    <>
                      <Loader2 size={16} className="animate-spin" />
                      Executing Pipeline...
                    </>
                  ) : (
                    <>
                      <Zap size={16} />
                      Execute Orchestrator
                    </>
                  )}
                </button>
              </form>
            )}
          </Card>

          {/* Stepper Status widget */}
          {(running || activeStep > 0) && (
            <Card>
              <h3 className="text-md font-bold text-slate-200 mb-6 font-mono text-xs uppercase tracking-wider text-slate-500">
                Supervisor States
              </h3>

              <div className="space-y-6 relative pl-6">
                {steps.map((step, idx) => {
                  const stepNum = idx + 1;
                  const isDone = activeStep > stepNum;
                  const isActive = activeStep === stepNum;

                  return (
                    <div key={idx} className="relative flex items-start gap-4">
                      {/* Step Connector line */}
                      {idx < steps.length - 1 && <div className="step-connector" />}

                      {/* Step Bullet */}
                      <div className="absolute -left-[30px] top-0.5 shrink-0 z-10">
                        {isDone ? (
                          <CheckCircle size={18} className="text-emerald-500 bg-bg-surface rounded-full" />
                        ) : isActive ? (
                          <Loader2 size={18} className="text-violet-500 bg-bg-surface rounded-full animate-spin" />
                        ) : (
                          <Circle size={18} className="text-slate-700 bg-bg-surface rounded-full" />
                        )}
                      </div>

                      <div>
                        <h4 className={`font-semibold text-xs leading-none ${isActive ? "text-violet-400" : isDone ? "text-slate-300" : "text-slate-500"}`}>
                          {step.label}
                        </h4>
                        <p className={`text-[10px] mt-1 ${isActive ? "text-slate-300" : "text-slate-500"}`}>
                          {step.desc}
                        </p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </Card>
          )}
        </div>

        {/* Right Column: Execution Output */}
        <div className="lg:col-span-2 space-y-6">
          <Card className="min-h-[450px]">
            <h3 className="text-md font-bold text-slate-200 mb-6 font-mono text-xs uppercase tracking-wider text-slate-500">
              Pipeline Workspace
            </h3>

            {running && activeStep < 3 ? (
              <div className="flex flex-col items-center justify-center h-64 text-center space-y-4">
                <Loader2 size={36} className="text-violet-500 animate-spin" />
                <div className="space-y-1">
                  <h4 className="font-semibold text-sm text-slate-300">Supervisor Flow Active</h4>
                  <p className="text-xs text-slate-500 max-w-xs leading-relaxed">
                    Executing routing logic nodes. Graph: START → job_analysis → candidate_retrieval...
                  </p>
                </div>
              </div>
            ) : !result ? (
              <div className="flex flex-col items-center justify-center h-64 text-center text-slate-500 text-sm space-y-2">
                <Zap size={32} className="text-slate-600" />
                <p>Run pipeline supervisor to retrieve consolidated execution output.</p>
              </div>
            ) : (
              <div className="space-y-8 animate-fade-in">
                {/* Headline result */}
                <div className="flex justify-between items-center border-b border-white/5 pb-4">
                  <div>
                    <h4 className="font-bold text-slate-200 text-base">Pipeline Executed Successfully</h4>
                    <p className="text-xs text-slate-400 mt-0.5">Matched and generated rubrics for position: {result.job_title}</p>
                  </div>
                  <Badge variant="emerald">Orchestration Done</Badge>
                </div>

                {/* Ranked candidates grid */}
                <div className="space-y-4">
                  <h5 className="text-[10px] font-bold uppercase tracking-widest text-slate-500">Ranked Match Output</h5>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {result.ranked_candidates?.slice(0, 4).map((rc) => (
                      <div
                        key={rc.candidate_id}
                        className="p-4 rounded-xl bg-white/5 border border-white/5 flex gap-4 items-center hover:bg-white/10 transition"
                      >
                        <ProgressRing score={rc.overall_score} size={42} strokeWidth={3} />
                        <div>
                          <h6 className="font-semibold text-slate-200 text-xs">{rc.name || "Candidate"}</h6>
                          <p className="text-[10px] text-slate-500 font-mono mt-0.5">{rc.email}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Interview pack widget snippet */}
                {result.interview_pack && (
                  <div className="space-y-4 pt-6 border-t border-white/5">
                    <h5 className="text-[10px] font-bold uppercase tracking-widest text-slate-500">Interview pack sample</h5>
                    <div className="p-4 rounded-xl bg-white/5 border border-white/5 space-y-3">
                      <div>
                        <h6 className="font-semibold text-slate-200 text-xs">
                          {result.interview_pack.technical_questions?.[0]?.question || "Technical Screening Question"}
                        </h6>
                        <p className="text-[11px] text-slate-400 mt-1 leading-relaxed">
                          {result.interview_pack.technical_questions?.[0]?.what_good_looks_like}
                        </p>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
