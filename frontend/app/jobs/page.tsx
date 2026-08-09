// app/jobs/page.tsx
"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { Job } from "@/lib/types";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Briefcase, Plus, Search, Calendar, MapPin, X, Loader2, Mic } from "lucide-react";
import { AudioScreeningModal } from "@/components/screening/AudioScreeningModal";

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [screeningJob, setScreeningJob] = useState<{ id: string; title: string } | null>(null);

  // Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [rawDescription, setRawDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadJobs = async () => {
    try {
      setLoading(true);
      const data = await api.jobs.list();
      setJobs(data.items || []);
    } catch (err) {
      console.error("Failed to load jobs:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadJobs();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title || !rawDescription) return;

    try {
      setSubmitting(true);
      setError(null);
      await api.jobs.create(title, rawDescription);
      // Clean up & reload
      setTitle("");
      setRawDescription("");
      setIsModalOpen(false);
      await loadJobs();
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || "Failed to create job");
    } finally {
      setSubmitting(false);
    }
  };

  const filteredJobs = jobs.filter(
    (job) =>
      job.title.toLowerCase().includes(search.toLowerCase()) ||
      job.description.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-8">
      {/* Header section */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-100 tracking-tight">Active Jobs</h1>
          <p className="text-sm text-slate-400 mt-1">Manage, analyze, and run candidate matching against job postings.</p>
        </div>
        <button
          onClick={() => setIsModalOpen(true)}
          className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-primary hover:opacity-90 font-semibold text-sm transition shadow-glow-violet-sm"
        >
          <Plus size={16} />
          Create Job Posting
        </button>
      </div>

      {/* Search Filter */}
      <div className="relative max-w-md">
        <span className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-500">
          <Search size={18} />
        </span>
        <input
          type="text"
          placeholder="Search job postings..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="input-base pl-10"
        />
      </div>

      {/* Grid */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <div className="h-44 w-full skeleton rounded-2xl" />
          <div className="h-44 w-full skeleton rounded-2xl" />
          <div className="h-44 w-full skeleton rounded-2xl" />
        </div>
      ) : filteredJobs.length === 0 ? (
        <div className="text-center py-16 bg-white/5 border border-white/5 rounded-2xl text-slate-500 text-sm">
          No job postings found matching your search.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredJobs.map((job) => (
            <Card key={job.id} hoverable>
              <div className="block h-full flex flex-col justify-between">
                <div>
                  <div className="flex justify-between items-start gap-4">
                    <Link href={`/jobs/${job.id}`}>
                      <h3 className="font-bold text-slate-200 hover:text-violet-400 transition">
                        {job.title}
                      </h3>
                    </Link>
                    <div className="p-2 bg-white/5 rounded-lg text-slate-500">
                      <Briefcase size={16} />
                    </div>
                  </div>

                  <div className="flex flex-wrap gap-2 mt-4">
                    <Badge variant="violet">
                      {job.parsed_requirements?.seniority || "mid"}
                    </Badge>
                    <Badge variant="slate">
                      {job.parsed_requirements?.location || "Remote"}
                    </Badge>
                    {job.parsed_requirements?.salary_range && (
                      <Badge variant="emerald">
                        {job.parsed_requirements.salary_range}
                      </Badge>
                    )}
                  </div>
                </div>

                <div className="mt-4 pt-3 border-t border-white/5">
                  <button
                    onClick={() => setScreeningJob({ id: job.id, title: job.title })}
                    className="w-full py-2 bg-violet-600/20 hover:bg-violet-600/30 border border-violet-500/30 text-violet-300 font-bold text-xs rounded-xl flex items-center justify-center gap-2 transition shadow-glow-violet-sm"
                  >
                    <Mic size={14} />
                    AI Voice Pre-Screening
                  </button>

                  <div className="mt-3 flex justify-between items-center text-[11px] text-slate-500 font-mono">
                    <div className="flex items-center gap-1">
                      <Calendar size={12} />
                      <span>{new Date(job.created_at).toLocaleDateString()}</span>
                    </div>
                    <span>ID: {job.id.substring(0, 8)}...</span>
                  </div>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Audio Screening Modal */}
      {screeningJob && (
        <AudioScreeningModal
          jobId={screeningJob.id}
          jobTitle={screeningJob.title}
          isOpen={!!screeningJob}
          onClose={() => setScreeningJob(null)}
        />
      )}


      {/* Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm animate-fade-in p-4">
          <div className="bg-bg-surface border border-white/10 rounded-2xl w-full max-w-xl max-h-[90vh] flex flex-col overflow-hidden shadow-2xl">
            {/* Header */}
            <div className="p-6 border-b border-white/5 flex justify-between items-center">
              <div>
                <h3 className="text-lg font-bold text-slate-100">Post a Job</h3>
                <p className="text-xs text-slate-500 mt-0.5">Undergoes automatic LLM analysis upon creation.</p>
              </div>
              <button
                onClick={() => setIsModalOpen(false)}
                className="p-1.5 hover:bg-white/5 rounded-lg text-slate-400 hover:text-slate-200 transition"
              >
                <X size={18} />
              </button>
            </div>

            {/* Form */}
            <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-6 space-y-5">
              {error && (
                <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-400 text-xs rounded-xl">
                  {error}
                </div>
              )}

              <div className="space-y-1.5">
                <label className="text-xs font-bold uppercase tracking-wider text-slate-500 font-mono">
                  Job Title
                </label>
                <input
                  type="text"
                  placeholder="e.g. Senior Machine Learning Engineer"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="input-base"
                  required
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-bold uppercase tracking-wider text-slate-500 font-mono">
                  Raw Description
                </label>
                <textarea
                  placeholder="Paste description including requirements, responsibilities, salary, etc..."
                  value={rawDescription}
                  onChange={(e) => setRawDescription(e.target.value)}
                  className="input-base h-60"
                  required
                />
              </div>

              {/* Actions */}
              <div className="pt-2 flex justify-end gap-3 border-t border-white/5">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-slate-300 text-sm font-semibold transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="flex items-center gap-2 px-5 py-2 rounded-xl bg-gradient-primary hover:opacity-90 font-semibold text-sm text-white transition shadow-glow-violet-sm disabled:opacity-50"
                >
                  {submitting ? (
                    <>
                      <Loader2 size={16} className="animate-spin" />
                      Analyzing...
                    </>
                  ) : (
                    "Create & Analyze"
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
