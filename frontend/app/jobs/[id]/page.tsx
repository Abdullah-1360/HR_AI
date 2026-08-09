// app/jobs/[id]/page.tsx
"use client";

import React, { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { Job, RankedCandidate } from "@/lib/types";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { ProgressRing } from "@/components/ui/ProgressRing";
import {
  Briefcase,
  MapPin,
  DollarSign,
  Calendar,
  Layers,
  ArrowLeft,
  ChevronRight,
  GitFork,
  Brain,
  AlertTriangle,
} from "lucide-react";

export default function JobDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params?.id as string;

  const [job, setJob] = useState<Job | null>(null);
  const [matches, setMatches] = useState<RankedCandidate[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    const loadDetail = async () => {
      try {
        setLoading(true);
        const [jobData, matchesData] = await Promise.all([
          api.jobs.get(id),
          api.hiring.getMatches(id),
        ]);
        setJob(jobData);
        setMatches(matchesData.ranked_candidates || []);
      } catch (err) {
        console.error("Job details load error:", err);
      } finally {
        setLoading(false);
      }
    };
    loadDetail();
  }, [id]);

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-32 skeleton rounded-2xl" />
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 h-96 skeleton rounded-2xl" />
          <div className="h-96 skeleton rounded-2xl" />
        </div>
      </div>
    );
  }

  if (!job) {
    return (
      <div className="text-center py-16 bg-white/5 border border-white/5 rounded-2xl text-slate-500">
        Job posting not found.
      </div>
    );
  }

  const requirements = (job.parsed_requirements || {}) as any;

  return (
    <div className="space-y-8">
      {/* Back link */}
      <div>
        <button
          onClick={() => router.back()}
          className="flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-300 transition uppercase tracking-wider"
        >
          <ArrowLeft size={14} /> Back to Jobs
        </button>
      </div>

      {/* Hero header */}
      <div className="relative overflow-hidden rounded-2xl border border-white/5 bg-gradient-card p-6 md:p-8">
        <div className="absolute top-0 right-0 w-96 h-96 bg-violet-600/5 rounded-full blur-3xl" />
        <div className="relative z-10 flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
          <div>
            <h1 className="text-2xl font-extrabold text-slate-100 tracking-tight">{job.title}</h1>
            <div className="flex flex-wrap gap-4 items-center text-xs text-slate-400 mt-2 font-mono">
              <div className="flex items-center gap-1">
                <MapPin size={14} className="text-slate-500" />
                <span>{requirements.location || "Remote"}</span>
              </div>
              <div className="flex items-center gap-1">
                <DollarSign size={14} className="text-slate-500" />
                <span>{requirements.salary_range || "Not specified"}</span>
              </div>
              <div className="flex items-center gap-1">
                <Calendar size={14} className="text-slate-500" />
                <span>{new Date(job.created_at).toLocaleDateString()}</span>
              </div>
            </div>
          </div>
          <div>
            <button
              onClick={() => router.push(`/hiring/match?job_id=${job.id}`)}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-primary hover:opacity-90 font-semibold text-sm transition shadow-glow-violet-sm"
            >
              <GitFork size={16} />
              Run Matching Evaluation
            </button>
          </div>
        </div>
      </div>

      {/* Columns */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left column - details & descriptions */}
        <div className="lg:col-span-2 space-y-8">
          {/* Job Requirements */}
          <Card>
            <h3 className="text-md font-bold text-slate-200 mb-6 font-mono text-xs uppercase tracking-wider text-slate-500">
              Parsed Requirements (AI Analyzed)
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
              <div>
                <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-3">Required Skills</h4>
                <div className="flex flex-wrap gap-2">
                  {requirements.required_skills?.map((skill: string) => (
                    <Badge key={skill} variant="violet">
                      {skill}
                    </Badge>
                  )) || <span className="text-slate-600 text-xs">None listed</span>}
                </div>
              </div>

              <div>
                <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-3">Preferred Skills</h4>
                <div className="flex flex-wrap gap-2">
                  {requirements.preferred_skills?.map((skill: string) => (
                    <Badge key={skill} variant="cyan">
                      {skill}
                    </Badge>
                  )) || <span className="text-slate-600 text-xs">None listed</span>}
                </div>
              </div>
            </div>

            <div className="mt-8 grid grid-cols-2 sm:grid-cols-3 gap-6 pt-6 border-t border-white/5">
              <div>
                <h5 className="text-[10px] uppercase font-bold tracking-widest text-slate-500">Seniority</h5>
                <p className="text-sm font-semibold text-slate-300 mt-1 capitalize">
                  {requirements.seniority || "mid"}
                </p>
              </div>
              <div>
                <h5 className="text-[10px] uppercase font-bold tracking-widest text-slate-500">Min Experience</h5>
                <p className="text-sm font-semibold text-slate-300 mt-1">
                  {requirements.experience_years_min || 0} years
                </p>
              </div>
              <div>
                <h5 className="text-[10px] uppercase font-bold tracking-widest text-slate-500">Work Auth</h5>
                <p className="text-sm font-semibold text-slate-300 mt-1">
                  {requirements.work_authorization || "Any"}
                </p>
              </div>
            </div>
          </Card>

          {/* Raw description */}
          <Card>
            <h3 className="text-md font-bold text-slate-200 mb-6 font-mono text-xs uppercase tracking-wider text-slate-500">
              Raw Description
            </h3>
            <p className="text-slate-300 text-sm whitespace-pre-wrap leading-relaxed">
              {job.description}
            </p>
          </Card>
        </div>

        {/* Right column - matches list overview */}
        <div className="space-y-8">
          <Card>
            <h3 className="text-md font-bold text-slate-200 mb-6 font-mono text-xs uppercase tracking-wider text-slate-500">
              Matched Candidates
            </h3>

            {matches.length === 0 ? (
              <div className="text-center py-8 text-slate-500 text-sm space-y-3">
                <p>No matches generated for this job posting.</p>
                <button
                  onClick={() => router.push(`/hiring/match?job_id=${job.id}`)}
                  className="text-xs font-bold text-violet-400 hover:text-violet-300 inline-flex items-center gap-1"
                >
                  Evaluate candidate match now <ChevronRight size={14} />
                </button>
              </div>
            ) : (
              <div className="space-y-4">
                {matches.map((c) => (
                  <div
                    key={c.candidate_id}
                    className="p-4 rounded-xl bg-white/5 border border-white/5 flex gap-4 items-center justify-between hover:bg-white/10 transition group cursor-pointer"
                    onClick={() => router.push(`/candidates/${c.candidate_id}`)}
                  >
                    <div className="flex gap-4 items-center">
                      <ProgressRing score={c.overall_score} size={42} strokeWidth={3} />
                      <div>
                        <h4 className="font-semibold text-slate-200 text-sm">{c.name || "Unnamed"}</h4>
                        <p className="text-xs text-slate-500 font-mono mt-0.5">{c.email || "No email"}</p>
                      </div>
                    </div>
                    <ChevronRight size={16} className="text-slate-600 group-hover:text-slate-400 transition" />
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
