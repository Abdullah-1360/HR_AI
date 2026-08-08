// app/candidates/[id]/page.tsx
"use client";

import React, { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { Candidate } from "@/lib/types";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { ArrowLeft, User, Mail, Calendar, FileText, Briefcase, GraduationCap, Award, ExternalLink } from "lucide-react";

export default function CandidateProfilePage() {
  const params = useParams();
  const router = useRouter();
  const id = params?.id as string;

  const [candidate, setCandidate] = useState<Candidate | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    const loadProfile = async () => {
      try {
        setLoading(true);
        const data = await api.candidates.get(id);
        setCandidate(data);
      } catch (err) {
        console.error("Candidate profile load error:", err);
      } finally {
        setLoading(false);
      }
    };
    loadProfile();
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

  if (!candidate) {
    return (
      <div className="text-center py-16 bg-white/5 border border-white/5 rounded-2xl text-slate-500">
        Candidate profile not found.
      </div>
    );
  }

  const resume = (candidate.parsed_resume || {}) as any;

  return (
    <div className="space-y-8">
      {/* Back button */}
      <div>
        <button
          onClick={() => router.back()}
          className="flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-300 transition uppercase tracking-wider"
        >
          <ArrowLeft size={14} /> Back to Candidates
        </button>
      </div>

      {/* Hero Header */}
      <div className="relative overflow-hidden rounded-2xl border border-white/5 bg-gradient-card p-6 md:p-8">
        <div className="absolute top-0 right-0 w-96 h-96 bg-cyan-600/5 rounded-full blur-3xl" />
        <div className="relative z-10 flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
          <div className="flex gap-5 items-center">
            <div className="w-14 h-14 rounded-full bg-gradient-primary flex items-center justify-center font-bold text-white shadow-glow-violet-sm text-xl shrink-0">
              {candidate.name?.charAt(0) || "U"}
            </div>
            <div>
              <h1 className="text-2xl font-extrabold text-slate-100 tracking-tight">{candidate.name || "Unnamed"}</h1>
              <div className="flex flex-wrap gap-4 items-center text-xs text-slate-400 mt-2 font-mono">
                <div className="flex items-center gap-1">
                  <Mail size={14} className="text-slate-500" />
                  <span>{candidate.email || "No email listed"}</span>
                </div>
                <div className="flex items-center gap-1">
                  <Calendar size={14} className="text-slate-500" />
                  <span>Ingested: {new Date(candidate.created_at).toLocaleDateString()}</span>
                </div>
              </div>
            </div>
          </div>
          <div className="flex gap-2">
            {candidate.resume_url && (
              <a
                href={candidate.resume_url.replace("minio://", "http://localhost:9000/")}
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-white/5 hover:bg-white/10 font-semibold text-sm transition text-slate-300 border border-white/5"
              >
                <FileText size={16} />
                View Raw Resume
                <ExternalLink size={12} />
              </a>
            )}
          </div>
        </div>
      </div>

      {/* Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Column: Work experience and summary */}
        <div className="lg:col-span-2 space-y-8">
          {/* Summary */}
          {resume.summary && (
            <Card>
              <h3 className="text-md font-bold text-slate-200 mb-4 font-mono text-xs uppercase tracking-wider text-slate-500">
                AI Summary Profile
              </h3>
              <p className="text-slate-300 text-sm leading-relaxed">{resume.summary}</p>
            </Card>
          )}

          {/* Work History Timeline */}
          <Card>
            <h3 className="text-md font-bold text-slate-200 mb-6 font-mono text-xs uppercase tracking-wider text-slate-500">
              Work History
            </h3>

            {!resume.work_history || resume.work_history.length === 0 ? (
              <p className="text-slate-500 text-sm">No work history listed.</p>
            ) : (
              <div className="space-y-8 relative pl-6 border-l border-white/5">
                {resume.work_history.map((work: any, idx: number) => (
                  <div key={idx} className="relative group">
                    {/* Timeline bullet indicator */}
                    <div className="absolute -left-[31px] top-1 w-3.5 h-3.5 rounded-full bg-bg-surface border-2 border-violet-500 group-hover:bg-violet-500 transition-colors" />

                    <div className="space-y-2">
                      <div className="flex justify-between items-start gap-4">
                        <div>
                          <h4 className="font-bold text-slate-200 text-sm">{work.role}</h4>
                          <span className="text-xs text-slate-400 font-medium">{work.company}</span>
                        </div>
                        <Badge variant="slate" className="font-mono text-[10px]">
                          {work.duration}
                        </Badge>
                      </div>

                      {work.highlights && work.highlights.length > 0 && (
                        <ul className="list-disc pl-4 text-xs text-slate-400 space-y-1 mt-2">
                          {work.highlights.map((h: string, hidx: number) => (
                            <li key={hidx}>{h}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>

        {/* Right Column: Skills, Education, Projects */}
        <div className="space-y-8">
          {/* Skills Grid */}
          <Card>
            <h3 className="text-md font-bold text-slate-200 mb-4 font-mono text-xs uppercase tracking-wider text-slate-500">
              Skills Overview
            </h3>
            <div className="flex flex-wrap gap-2">
              {candidate.skills?.map((skill: string) => (
                <Badge key={skill} variant="cyan">
                  {skill}
                </Badge>
              )) || <span className="text-slate-500 text-xs">None listed</span>}
            </div>
            <div className="mt-4 pt-4 border-t border-white/5 flex justify-between text-xs text-slate-500 font-mono">
              <span>Total Estimated Experience:</span>
              <span className="text-slate-300 font-bold">{candidate.experience_years || 0} years</span>
            </div>
          </Card>

          {/* Education */}
          <Card>
            <h3 className="text-md font-bold text-slate-200 mb-4 font-mono text-xs uppercase tracking-wider text-slate-500">
              Education
            </h3>
            {!resume.education || resume.education.length === 0 ? (
              <p className="text-slate-500 text-sm">No education history listed.</p>
            ) : (
              <div className="space-y-4">
                {resume.education.map((edu: any, idx: number) => (
                  <div key={idx} className="flex gap-3 items-start">
                    <GraduationCap size={16} className="text-slate-500 shrink-0 mt-0.5" />
                    <div>
                      <h4 className="font-semibold text-slate-200 text-xs">{edu.degree}</h4>
                      <p className="text-[11px] text-slate-500 mt-0.5">
                        {edu.institution} {edu.year ? `(${edu.year})` : ""}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>

          {/* Projects & Certifications */}
          <Card>
            <h3 className="text-md font-bold text-slate-200 mb-4 font-mono text-xs uppercase tracking-wider text-slate-500">
              Projects & Certs
            </h3>

            {resume.projects && resume.projects.length > 0 && (
              <div className="space-y-2 mb-4">
                <h4 className="text-[10px] font-bold uppercase tracking-widest text-slate-500">Projects</h4>
                <ul className="list-disc pl-4 text-xs text-slate-400 space-y-1">
                  {resume.projects.map((p: string) => (
                    <li key={p}>{p}</li>
                  ))}
                </ul>
              </div>
            )}

            {resume.certifications && resume.certifications.length > 0 && (
              <div className="space-y-2 pt-3 border-t border-white/5">
                <h4 className="text-[10px] font-bold uppercase tracking-widest text-slate-500">Certifications</h4>
                <div className="flex flex-wrap gap-1.5">
                  {resume.certifications.map((c: string) => (
                    <Badge key={c} variant="slate" className="text-[10px] py-0 px-2">
                      {c}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
