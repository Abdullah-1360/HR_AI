// components/layout/TopBar.tsx
"use client";

import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Activity, Database, HardDrive, Bot, ShieldCheck, Sparkles } from "lucide-react";
import { CopilotDrawer } from "@/components/copilot/CopilotDrawer";

interface HealthState {
  status: string;
  db: string;
  storage: string;
}

export const TopBar: React.FC = () => {
  const [health, setHealth] = useState<HealthState | null>(null);
  const [copilotOpen, setCopilotOpen] = useState(false);
  const [deiMode, setDeiMode] = useState(false);

  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const data = await api.health();
        setHealth(data);
      } catch (err) {
        setHealth({ status: "offline", db: "error", storage: "error" });
      }
    };
    fetchHealth();
    const interval = setInterval(fetchHealth, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <>
      <header className="h-16 bg-slate-950/80 backdrop-blur-md border-b border-white/10 flex items-center justify-between px-8 fixed top-0 right-0 left-64 z-10">
        <div className="flex items-center gap-4">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400 font-mono">
            Recruitment Operating System
          </h2>

          {/* DEI Blind Screening Toggle */}
          <button
            onClick={() => setDeiMode(!deiMode)}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-mono font-bold uppercase transition border ${
              deiMode
                ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/40 shadow-glow-violet-sm"
                : "bg-white/5 text-slate-400 border-white/10 hover:border-white/20"
            }`}
          >
            <ShieldCheck size={12} />
            DEI Blind Mode: {deiMode ? "ON" : "OFF"}
          </button>
        </div>

        <div className="flex items-center gap-6">
          {/* AI Copilot Trigger */}
          <button
            onClick={() => setCopilotOpen(true)}
            className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-violet-600/20 hover:bg-violet-600/30 border border-violet-500/30 text-violet-300 font-bold text-xs transition shadow-glow-violet-sm"
          >
            <Bot size={15} />
            Ask Copilot
          </button>

          {/* DB Health */}
          <div className="flex items-center gap-2 text-xs font-mono text-slate-400">
            <Database size={14} className={health?.db === "ok" ? "text-emerald-500 animate-pulse" : "text-red-500"} />
            <span>DB: {health ? (health.db === "ok" ? "Online" : "Offline") : "Connecting..."}</span>
          </div>

          {/* Object Storage Health */}
          <div className="flex items-center gap-2 text-xs font-mono text-slate-400">
            <HardDrive size={14} className={health?.storage === "ok" ? "text-emerald-500 animate-pulse" : "text-red-500"} />
            <span>Storage: {health ? (health.storage === "ok" ? "MinIO" : "Offline") : "Connecting..."}</span>
          </div>

          {/* Global Router Health */}
          <div className="flex items-center gap-2 text-xs font-mono">
            <Activity size={14} className={health?.status === "ok" ? "text-emerald-500 animate-pulse" : "text-amber-500 animate-ping"} />
            <span className={`px-2 py-0.5 rounded-full font-bold uppercase text-[9px] ${
              health?.status === "ok" 
                ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                : "bg-red-500/10 text-red-400 border border-red-500/20"
            }`}>
              {health ? health.status : "Checking"}
            </span>
          </div>
        </div>
      </header>

      {/* Floating Copilot Drawer */}
      <CopilotDrawer isOpen={copilotOpen} onClose={() => setCopilotOpen(false)} />
    </>
  );
};
export default TopBar;

