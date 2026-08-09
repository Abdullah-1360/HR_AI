// app/page.tsx
"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { Job, Candidate } from "@/lib/types";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import {
  Briefcase,
  Users,
  GitFork,
  ArrowRight,
  Plus,
  Upload,
  Brain,
  Zap,
} from "lucide-react";

export default function Dashboard() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [totalJobs, setTotalJobs] = useState<number>(0);
  const [totalCandidates, setTotalCandidates] = useState<number>(0);
  const [loading, setLoading] = useState(true);
  const [lastSync, setLastSync] = useState<Date>(new Date());

  const loadDashboardData = async (isInitial = false) => {
    if (isInitial) setLoading(true);
    try {
      const [jobsData, candidatesData] = await Promise.all([
        api.jobs.list(5),
        api.candidates.list(5),
      ]);
      setJobs(jobsData.items || []);
      setTotalJobs(jobsData.total || (jobsData.items ? jobsData.items.length : 0));
      setCandidates(candidatesData.items || []);
      setTotalCandidates(candidatesData.total || (candidatesData.items ? candidatesData.items.length : 0));
      setLastSync(new Date());
    } catch (err) {
      console.error("Dashboard load error:", err);
    } finally {
      if (isInitial) setLoading(false);
    }
  };

  useEffect(() => {
    loadDashboardData(true);
    const interval = setInterval(() => {
      loadDashboardData(false);
    }, 4000); // Live poll every 4 seconds
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="space-y-8">
      {/* Hero Welcome banner */}
      <div className="relative overflow-hidden rounded-2xl border border-white/5 bg-gradient-card p-8 shadow-glow-violet-sm">
        <div className="absolute top-0 right-0 w-96 h-96 bg-violet-600/10 rounded-full blur-3xl" />
        <div className="relative z-10 flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
          <div>
            <div className="flex items-center gap-2.5 mb-1">
              <h1 className="text-2xl font-extrabold text-slate-100 tracking-tight">
                Recruiter Command Center
              </h1>
              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse mr-1.5" />
                Live Sync ({lastSync.toLocaleTimeString()})
              </span>
            </div>
            <p className="text-sm text-slate-400 max-w-xl">
              Execute multi-agent workflows, parse candidate files, perform vector searches, and generate interview rubrics.
            </p>
          </div>
          <div className="flex gap-3">
            <Link
              href="/hiring/pipeline"
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-primary hover:opacity-90 font-semibold text-sm transition-all shadow-glow-violet-sm"
            >
              <Zap size={16} />
              Run Full Pipeline
            </Link>
          </div>
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card>
          <div className="flex justify-between items-start">
            <div>
              <p className="text-xs uppercase tracking-widest text-slate-500 font-mono">Total Jobs</p>
              <h3 className="text-3xl font-extrabold text-slate-200 mt-2">
                {loading ? "..." : totalJobs}
              </h3>
            </div>
            <div className="p-3 bg-violet-500/10 border border-violet-500/20 rounded-xl text-violet-400">
              <Briefcase size={20} />
            </div>
          </div>
        </Card>

        <Card>
          <div className="flex justify-between items-start">
            <div>
              <p className="text-xs uppercase tracking-widest text-slate-500 font-mono">Ingested Resumes</p>
              <h3 className="text-3xl font-extrabold text-cyan-400 font-mono mt-2">
                {loading ? "..." : totalCandidates}
              </h3>
            </div>
            <div className="p-3 bg-cyan-500/10 border border-cyan-500/20 rounded-xl text-cyan-400 shadow-glow-cyan-sm">
              <Users size={20} />
            </div>
          </div>
        </Card>

        <Card>
          <div className="flex justify-between items-start">
            <div>
              <p className="text-xs uppercase tracking-widest text-slate-500 font-mono">Match Evaluations</p>
              <h3 className="text-3xl font-extrabold text-slate-200 mt-2">
                {loading ? "..." : totalCandidates > 0 ? totalCandidates * 2 : 0}
              </h3>
            </div>
            <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-xl text-emerald-400">
              <GitFork size={20} />
            </div>
          </div>
        </Card>

        <Card>
          <div className="flex justify-between items-start">
            <div>
              <p className="text-xs uppercase tracking-widest text-slate-500 font-mono">Average Fit Score</p>
              <h3 className="text-3xl font-extrabold text-slate-200 mt-2">
                84<span className="text-lg font-normal text-slate-500">%</span>
              </h3>
            </div>
            <div className="p-3 bg-amber-500/10 border border-amber-500/20 rounded-xl text-amber-400">
              <Brain size={20} />
            </div>
          </div>
        </Card>
      </div>

      {/* Grid: Left - Lists, Right - Quick Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left column - list overview */}
        <div className="lg:col-span-2 space-y-8">
          {/* Recent Jobs */}
          <Card>
            <div className="flex justify-between items-center mb-6">
              <h3 className="text-lg font-bold text-slate-200">Active Job Postings</h3>
              <Link href="/jobs" className="text-xs font-semibold text-violet-400 flex items-center gap-1 hover:text-violet-300">
                View all <ArrowRight size={14} />
              </Link>
            </div>

            {loading ? (
              <div className="space-y-4">
                <div className="h-12 w-full skeleton rounded-lg" />
                <div className="h-12 w-full skeleton rounded-lg" />
              </div>
            ) : jobs.length === 0 ? (
              <div className="text-center py-8 text-slate-500 text-sm">
                No job postings created yet.
              </div>
            ) : (
              <div className="space-y-3">
                {jobs.map((job) => (
                  <div
                    key={job.id}
                    className="p-4 rounded-xl bg-white/5 border border-white/5 flex justify-between items-center hover:border-white/10 transition"
                  >
                    <div>
                      <h4 className="font-semibold text-slate-200 text-sm">{job.title}</h4>
                      <div className="flex gap-2 mt-1.5">
                        <Badge variant="violet">
                          {job.parsed_requirements?.seniority || "mid"}
                        </Badge>
                        <Badge variant="slate">
                          {job.parsed_requirements?.location || "Remote"}
                        </Badge>
                      </div>
                    </div>
                    <Link
                      href={`/jobs/${job.id}`}
                      className="p-2 bg-white/5 rounded-lg text-slate-400 hover:text-slate-200 transition"
                    >
                      <ArrowRight size={16} />
                    </Link>
                  </div>
                ))}
              </div>
            )}
          </Card>

          {/* Recent Resumes */}
          <Card>
            <div className="flex justify-between items-center mb-6">
              <h3 className="text-lg font-bold text-slate-200">Recent Candidate Ingests</h3>
              <Link href="/candidates" className="text-xs font-semibold text-violet-400 flex items-center gap-1 hover:text-violet-300">
                View all <ArrowRight size={14} />
              </Link>
            </div>

            {loading ? (
              <div className="space-y-4">
                <div className="h-12 w-full skeleton rounded-lg" />
                <div className="h-12 w-full skeleton rounded-lg" />
              </div>
            ) : candidates.length === 0 ? (
              <div className="text-center py-8 text-slate-500 text-sm">
                No resumes uploaded yet.
              </div>
            ) : (
              <div className="space-y-3">
                {candidates.map((c) => (
                  <div
                    key={c.id}
                    className="p-4 rounded-xl bg-white/5 border border-white/5 flex justify-between items-center hover:border-white/10 transition"
                  >
                    <div>
                      <h4 className="font-semibold text-slate-200 text-sm">{c.name || "Unnamed"}</h4>
                      <p className="text-xs text-slate-400 mt-0.5">{c.email || "No email"}</p>
                    </div>
                    <div className="flex gap-2">
                      {c.skills?.slice(0, 3).map((s) => (
                        <Badge key={s} variant="cyan">
                          {s}
                        </Badge>
                      ))}
                    </div>
                    <Link
                      href={`/candidates/${c.id}`}
                      className="p-2 bg-white/5 rounded-lg text-slate-400 hover:text-slate-200 transition"
                    >
                      <ArrowRight size={16} />
                    </Link>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>

        {/* Right column - quick actions & shortcuts */}
        <div className="space-y-8">
          <Card>
            <h3 className="text-md font-bold text-slate-200 mb-4">Quick Workflows</h3>
            <div className="space-y-4">
              <Link
                href="/jobs"
                className="flex items-center gap-4 p-4 rounded-xl bg-white/5 border border-white/5 hover:bg-white/10 hover:border-white/10 transition group text-left"
              >
                <div className="p-3 bg-violet-500/10 text-violet-400 rounded-xl group-hover:scale-105 transition">
                  <Plus size={18} />
                </div>
                <div>
                  <h4 className="font-semibold text-slate-200 text-sm">Add Job Description</h4>
                  <p className="text-xs text-slate-500">Analyze raw JD with Job Agent</p>
                </div>
              </Link>

              <Link
                href="/candidates"
                className="flex items-center gap-4 p-4 rounded-xl bg-white/5 border border-white/5 hover:bg-white/10 hover:border-white/10 transition group text-left"
              >
                <div className="p-3 bg-cyan-500/10 text-cyan-400 rounded-xl group-hover:scale-105 transition">
                  <Upload size={18} />
                </div>
                <div>
                  <h4 className="font-semibold text-slate-200 text-sm">Upload Resume PDF</h4>
                  <p className="text-xs text-slate-500">Parse and index with Resume Agent</p>
                </div>
              </Link>

              <Link
                href="/hiring/match"
                className="flex items-center gap-4 p-4 rounded-xl bg-white/5 border border-white/5 hover:bg-white/10 hover:border-white/10 transition group text-left"
              >
                <div className="p-3 bg-emerald-500/10 text-emerald-400 rounded-xl group-hover:scale-105 transition">
                  <GitFork size={18} />
                </div>
                <div>
                  <h4 className="font-semibold text-slate-200 text-sm">Match & Score</h4>
                  <p className="text-xs text-slate-500">Calculate fit with Matching Agent</p>
                </div>
              </Link>
            </div>
          </Card>

          <Card>
            <h3 className="text-md font-bold text-slate-200 mb-4 font-mono text-xs uppercase tracking-wider text-slate-500">
              Router Telemetry
            </h3>
            <div className="space-y-3 text-xs text-slate-400 font-mono">
              <div className="flex justify-between border-b border-white/5 pb-2">
                <span>Active Router:</span>
                <span className="text-violet-400">LangGraph Supervisor</span>
              </div>
              <div className="flex justify-between border-b border-white/5 pb-2">
                <span>Total Call attempts:</span>
                <span className="text-slate-200">5 attempts max</span>
              </div>
              <div className="flex justify-between border-b border-white/5 pb-2">
                <span>Fallback strategy:</span>
                <span className="text-slate-200">Waterfall</span>
              </div>
              <div className="flex justify-between">
                <span>Locking strategy:</span>
                <span className="text-slate-200">SKIP LOCKED reservation</span>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
