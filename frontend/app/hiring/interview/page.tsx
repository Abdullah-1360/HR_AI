// app/hiring/interview/page.tsx
"use client";

import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Job, Candidate, InterviewResponse } from "@/lib/types";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { FileText, Loader2, Play, ChevronDown, ChevronUp, Copy, Check } from "lucide-react";

export default function InterviewGeneratorPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [selectedJobId, setSelectedJobId] = useState("");
  const [selectedCandidateId, setSelectedCandidateId] = useState("");

  const [loadingLists, setLoadingLists] = useState(true);
  const [running, setRunning] = useState(false);
  const [pack, setPack] = useState<InterviewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Accordion active state
  const [expandedIndex, setExpandedIndex] = useState<number | null>(0);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const loadLists = async () => {
      try {
        setLoadingLists(true);
        const [jobsData, candidatesData] = await Promise.all([
          api.jobs.list(),
          api.candidates.list(),
        ]);
        setJobs(jobsData.items || []);
        setCandidates(candidatesData.items || []);
        if (jobsData.items?.length > 0) setSelectedJobId(jobsData.items[0].id);
        if (candidatesData.items?.length > 0) setSelectedCandidateId(candidatesData.items[0].id);
      } catch (err) {
        console.error("Failed to load interview generator selectors:", err);
      } finally {
        setLoadingLists(false);
      }
    };
    loadLists();
  }, []);

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedJobId || !selectedCandidateId) return;

    try {
      setRunning(true);
      setError(null);
      setPack(null);
      const data = await api.hiring.interview(selectedJobId, selectedCandidateId);
      setPack(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || "Failed to generate interview pack");
    } finally {
      setRunning(false);
    }
  };

  const copyToClipboard = () => {
    if (!pack) return;
    const text = JSON.stringify(pack, null, 2);
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Combine questions
  const allQuestions = pack
    ? [
        ...pack.technical_questions,
        ...pack.behavioral_questions,
        ...pack.scenario_questions,
        ...pack.system_design_questions,
      ]
    : [];

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-100 tracking-tight">Interview Kit Generator</h1>
          <p className="text-sm text-slate-400 mt-1">
            Generate customized technical, behavioral, and architectural rubrics for matching candidates.
          </p>
        </div>
        {pack && (
          <button
            onClick={copyToClipboard}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white/5 border border-white/5 hover:bg-white/10 text-xs font-semibold font-mono text-slate-300 transition"
          >
            {copied ? <Check size={14} className="text-emerald-500" /> : <Copy size={14} />}
            {copied ? "Copied" : "Copy JSON Data"}
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Configuration Column */}
        <div className="space-y-6">
          <Card>
            <h3 className="text-md font-bold text-slate-200 mb-6 font-mono text-xs uppercase tracking-wider text-slate-500">
              Run Configuration
            </h3>

            {loadingLists ? (
              <div className="h-44 skeleton rounded-xl" />
            ) : (
              <form onSubmit={handleGenerate} className="space-y-5">
                {error && (
                  <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-400 text-xs rounded-xl">
                    {error}
                  </div>
                )}

                <div className="space-y-1.5">
                  <label className="text-xs font-bold uppercase tracking-wider text-slate-500 font-mono">
                    Select Position
                  </label>
                  <select
                    value={selectedJobId}
                    onChange={(e) => setSelectedJobId(e.target.value)}
                    className="input-base"
                    required
                  >
                    {jobs.map((j) => (
                      <option key={j.id} value={j.id}>
                        {j.title}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-bold uppercase tracking-wider text-slate-500 font-mono">
                    Select Candidate
                  </label>
                  <select
                    value={selectedCandidateId}
                    onChange={(e) => setSelectedCandidateId(e.target.value)}
                    className="input-base"
                    required
                  >
                    {candidates.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name || "Unnamed"} ({c.email})
                      </option>
                    ))}
                  </select>
                </div>

                <button
                  type="submit"
                  disabled={running || !selectedJobId || !selectedCandidateId}
                  className="w-full flex items-center justify-center gap-2 px-5 py-3 rounded-xl bg-gradient-primary hover:opacity-90 font-semibold text-sm text-white transition shadow-glow-violet-sm disabled:opacity-50"
                >
                  {running ? (
                    <>
                      <Loader2 size={16} className="animate-spin" />
                      Compiling Questions...
                    </>
                  ) : (
                    <>
                      <Play size={16} />
                      Generate Interview Pack
                    </>
                  )}
                </button>
              </form>
            )}
          </Card>
        </div>

        {/* Results Column */}
        <div className="lg:col-span-2 space-y-6">
          <Card className="min-h-[450px]">
            <h3 className="text-md font-bold text-slate-200 mb-6 font-mono text-xs uppercase tracking-wider text-slate-500">
              Evaluation Kit
            </h3>

            {running ? (
              <div className="flex flex-col items-center justify-center h-64 text-center space-y-4">
                <Loader2 size={36} className="text-violet-500 animate-spin" />
                <div className="space-y-1">
                  <h4 className="font-semibold text-sm text-slate-300">Generating Questions & Rubrics</h4>
                  <p className="text-xs text-slate-500 max-w-xs leading-relaxed">
                    Analyzing target candidate highlights, skill gaps, and job expectations...
                  </p>
                </div>
              </div>
            ) : !pack ? (
              <div className="flex flex-col items-center justify-center h-64 text-center text-slate-500 text-sm space-y-2">
                <FileText size={32} className="text-slate-600" />
                <p>Submit targets to generate interactive questions accordions.</p>
              </div>
            ) : (
              <div className="space-y-6">
                {/* Meta Summary banner */}
                <div className="p-4 rounded-xl bg-white/5 border border-white/5 flex flex-wrap gap-6 text-xs text-slate-400 font-mono">
                  <div>
                    <span>Job Title:</span>
                    <span className="text-slate-200 font-bold ml-1">{pack.job_title}</span>
                  </div>
                  <div>
                    <span>Target Candidate:</span>
                    <span className="text-slate-200 font-bold ml-1">{pack.candidate_name || "Unnamed"}</span>
                  </div>
                  <div>
                    <span>Suggested Duration:</span>
                    <span className="text-slate-200 font-bold ml-1">{pack.recommended_interview_duration_mins} mins</span>
                  </div>
                </div>

                {/* Question Accordion block */}
                <div className="space-y-3">
                  {allQuestions.map((q, idx) => {
                    const isExpanded = expandedIndex === idx;

                    let difficultyColorClass = "emerald";
                    if (q.difficulty === "hard") {
                      difficultyColorClass = "red";
                    } else if (q.difficulty === "medium") {
                      difficultyColorClass = "amber";
                    }

                    return (
                      <div key={idx} className="space-y-2">
                        <button
                          onClick={() => setExpandedIndex(isExpanded ? null : idx)}
                          className="accordion-btn"
                        >
                          <div className="flex items-center gap-3">
                            <Badge variant={q.category === "technical" ? "violet" : q.category === "behavioral" ? "cyan" : "slate"}>
                              {q.category}
                            </Badge>
                            <span className="font-semibold">{q.question}</span>
                          </div>
                          {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                        </button>

                        {isExpanded && (
                          <div className="p-5 rounded-xl border border-white/5 bg-white/5 text-xs text-slate-300 space-y-4 animate-slide-up">
                            <div className="flex justify-between font-mono text-[10px] text-slate-500 border-b border-white/5 pb-2">
                              <span>DIFFICULTY LEVEL</span>
                              <span className={`text-${difficultyColorClass}-500 font-bold uppercase`}>
                                {q.difficulty}
                              </span>
                            </div>

                            <div className="space-y-1.5">
                              <h5 className="font-bold text-slate-200">Ideal Response Rubric</h5>
                              <p className="leading-relaxed">{q.what_good_looks_like}</p>
                            </div>

                            {q.follow_ups && q.follow_ups.length > 0 && (
                              <div className="space-y-1.5 pt-3 border-t border-white/5">
                                <h5 className="font-bold text-slate-200">Recommended Follow-Ups</h5>
                                <ul className="list-disc pl-4 space-y-1 leading-relaxed text-slate-400">
                                  {q.follow_ups.map((f, fidx) => (
                                    <li key={fidx}>{f}</li>
                                  ))}
                                </ul>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
