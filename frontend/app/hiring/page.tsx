// app/hiring/page.tsx
"use client";

import React from "react";
import Link from "next/link";
import { Card } from "@/components/ui/Card";
import { GitFork, FileText, Zap, ChevronRight } from "lucide-react";

export default function HiringHubPage() {
  const tools = [
    {
      href: "/hiring/match",
      title: "Evaluate Match Fit",
      desc: "Perform semantic pgvector retrieval followed by detailed LLM scoring across skills, experience, and education.",
      icon: GitFork,
      color: "text-violet-400 bg-violet-500/10 border-violet-500/20",
    },
    {
      href: "/hiring/interview",
      title: "Generate Interview Kit",
      desc: "Compile detailed technical, behavioral, and scenario interview questions with custom evaluation rubrics.",
      icon: FileText,
      color: "text-cyan-400 bg-cyan-500/10 border-cyan-500/20",
    },
    {
      href: "/hiring/pipeline",
      title: "Run Supervisor Pipeline",
      desc: "Trigger the multi-agent LangGraph supervisor. Runs job analysis, candidate retrieval, matching, and interview generation in one flow.",
      icon: Zap,
      color: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
    },
  ];

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-extrabold text-slate-100 tracking-tight">Hiring Command Hub</h1>
        <p className="text-sm text-slate-400 mt-1">Execute automated workflows, matching algorithms, and candidate evaluation kits.</p>
      </div>

      {/* Tools grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
        {tools.map((t) => {
          const Icon = t.icon;
          return (
            <Card key={t.title} hoverable className="flex flex-col justify-between min-h-[250px]">
              <div className="space-y-4">
                <div className={`w-12 h-12 rounded-xl border flex items-center justify-center ${t.color}`}>
                  <Icon size={24} />
                </div>
                <div className="space-y-1.5">
                  <h3 className="text-base font-bold text-slate-200">{t.title}</h3>
                  <p className="text-xs text-slate-400 leading-relaxed">{t.desc}</p>
                </div>
              </div>
              <div className="pt-6 border-t border-white/5">
                <Link
                  href={t.href}
                  className="flex items-center gap-1.5 text-xs font-bold text-violet-400 hover:text-violet-300 transition group"
                >
                  Configure & Execute
                  <ChevronRight size={14} className="group-hover:translate-x-0.5 transition-transform" />
                </Link>
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
