"use client";

import React, { useEffect, useState, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { Job, RankedCandidate } from "@/lib/types";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { ProgressRing } from "@/components/ui/ProgressRing";
import { GitFork, Search, Sliders, ChevronRight, Loader2, Play } from "lucide-react";

function MatchRunnerContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const initialJobId = searchParams?.get("job_id") || "";

  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedJobId, setSelectedJobId] = useState(initialJobId);
  const [topK, setTopK] = useState(10);

  const [loadingJobs, setLoadingJobs] = useState(true);
  const [running, setRunning] = useState(false);
  const [results, setResults] = useState<RankedCandidate[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadJobs = async () => {
      try {
        setLoadingJobs(true);
        const data = await api.jobs.list();
        setJobs(data.items || []);
        if (data.items?.length > 0 && !selectedJobId) {
          setSelectedJobId(data.items[0].id);
        }
      } catch (err) {
        console.error("Failed to load jobs list:", err);
      } finally {
        setLoadingJobs(false);
      }
    };
    loadJobs();
  }, [selectedJobId]);

  const handleRunMatch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedJobId) return;

    try {
      setRunning(true);
      setError(null);
      setResults([]);
      const data = await api.hiring.match(selectedJobId, topK);
      setResults(data.ranked_candidates || []);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || "Failed to execute match run");
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-extrabold text-slate-100 tracking-tight">Evaluate Candidate Match</h1>
        <p className="text-sm text-slate-400 mt-1">
          Perform vector-based similarity checks followed by LLM-based structured scoring.
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
              <form onSubmit={handleRunMatch} className="space-y-5">
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
                    <label>Top-K Candidates</label>
                    <span className="text-slate-300 font-mono text-[10px]">{topK} candidates</span>
                  </div>
                  <div className="flex items-center gap-4">
                    <input
                      type="range"
                      min="1"
                      max="50"
                      value={topK}
                      onChange={(e) => setTopK(parseInt(e.target.value))}
                      className="flex-1 accent-violet-500 cursor-pointer bg-white/5 h-1.5 rounded-lg appearance-none"
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={running || !selectedJobId}
                  className="w-full flex items-center justify-center gap-2 px-5 py-3 rounded-xl bg-gradient-primary hover:opacity-90 font-semibold text-sm text-white transition shadow-glow-violet-sm disabled:opacity-50"
                >
                  {running ? (
                    <>
                      <Loader2 size={16} className="animate-spin" />
                      Evaluating Candidate Fit...
                    </>
                  ) : (
                    <>
                      <Play size={16} />
                      Start Matching Run
                    </>
                  )}
                </button>
              </form>
            )}
          </Card>
        </div>

        {/* Right Column: Results Panel */}
        <div className="lg:col-span-2 space-y-6">
          <Card className="min-h-[400px]">
            <h3 className="text-md font-bold text-slate-200 mb-6 font-mono text-xs uppercase tracking-wider text-slate-500">
              Match Results
            </h3>

            {running ? (
              <div className="flex flex-col items-center justify-center h-64 text-center space-y-4">
                <Loader2 size={36} className="text-violet-500 animate-spin" />
                <div className="space-y-1">
                  <h4 className="font-semibold text-sm text-slate-300">Matching Pipeline Running</h4>
                  <p className="text-xs text-slate-500 max-w-xs leading-relaxed">
                    Querying pgvector search to fetch candidates, then calling the routing LLM to score fit...
                  </p>
                </div>
              </div>
            ) : results.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-64 text-center text-slate-500 text-sm space-y-2">
                <GitFork size={32} className="text-slate-600" />
                <p>Run matching to display evaluation candidates list.</p>
              </div>
            ) : (
              <div className="space-y-4">
                {results.map((r) => (
                  <div
                    key={r.candidate_id}
                    className="p-5 rounded-2xl bg-white/5 border border-white/5 flex flex-col md:flex-row justify-between items-start md:items-center gap-6 hover:border-white/10 transition group cursor-pointer"
                    onClick={() => router.push(`/candidates/${r.candidate_id}`)}
                  >
                    <div className="flex gap-4 items-start">
                      <ProgressRing score={r.overall_score} size={48} strokeWidth={4.5} />
                      <div>
                        <h4 className="font-bold text-slate-200 text-sm">{r.name || "Unnamed"}</h4>
                        <p className="text-xs text-slate-500 font-mono mt-0.5">{r.email}</p>
                        {r.strengths && r.strengths.length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-2.5">
                            {r.strengths.slice(0, 2).map((s) => (
                              <Badge key={s} variant="violet" className="text-[9px] py-0 px-2">
                                {s}
                              </Badge>
                            ))}
                            {r.missing_skills?.length > 0 && (
                              <Badge variant="red" className="text-[9px] py-0 px-2">
                                Gap: {r.missing_skills[0]}
                              </Badge>
                            )}
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center gap-4 self-stretch md:self-auto pt-4 md:pt-0 border-t border-white/5 md:border-0 justify-between">
                      <div className="text-right">
                        <div className="text-xs text-slate-400 font-mono">
                          Skills score: <span className="text-slate-200 font-bold">{r.skill_match_score}%</span>
                        </div>
                        <div className="text-xs text-slate-400 font-mono mt-0.5">
                          Experience score: <span className="text-slate-200 font-bold">{r.experience_score}%</span>
                        </div>
                      </div>
                      <ChevronRight size={16} className="text-slate-600 group-hover:text-slate-400 transition" />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}

export default function MatchRunnerPage() {
  return (
    <Suspense fallback={
      <div className="flex flex-col items-center justify-center h-64 text-center space-y-4">
        <Loader2 className="animate-spin text-violet-500" size={36} />
        <h4 className="font-semibold text-slate-300">Loading Matching Hub...</h4>
      </div>
    }>
      <MatchRunnerContent />
    </Suspense>
  );
}
