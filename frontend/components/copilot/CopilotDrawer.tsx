// components/copilot/CopilotDrawer.tsx
"use client";

import React, { useState } from "react";
import { Bot, Send, X, Sparkles, UserCheck, FileText, ExternalLink, Briefcase } from "lucide-react";

interface CandidateContext {
  id: string;
  name?: string;
  skills?: string[];
  experience_years?: number;
}

interface Message {
  id: string;
  sender: "user" | "copilot";
  text: string;
  candidates?: CandidateContext[];
  timestamp: string;
}

const formatInline = (text: string) => {
  const parts = text.split(/(\*\*.*?\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return (
        <strong key={i} className="font-bold text-slate-100">
          {part.slice(2, -2)}
        </strong>
      );
    }
    return part;
  });
};

const FormattedMarkdown: React.FC<{ content: string }> = ({ content }) => {
  const lines = content.split("\n");
  return (
    <div className="space-y-1.5 leading-relaxed text-slate-200">
      {lines.map((line, idx) => {
        const trimmed = line.trim();
        if (!trimmed) return <div key={idx} className="h-1" />;

        // Header ###
        if (trimmed.startsWith("###")) {
          const headerText = trimmed.replace(/^###\s*/, "");
          return (
            <h4 key={idx} className="font-bold text-xs text-violet-300 border-b border-violet-500/20 pb-1 mt-3 mb-1.5 flex items-center gap-1.5">
              {formatInline(headerText)}
            </h4>
          );
        }
        // Header ##
        if (trimmed.startsWith("##")) {
          const headerText = trimmed.replace(/^##\s*/, "");
          return (
            <h3 key={idx} className="font-extrabold text-xs text-cyan-300 mt-3 mb-1">
              {formatInline(headerText)}
            </h3>
          );
        }
        // Bullet list item
        if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
          const bulletText = trimmed.replace(/^[-*]\s*/, "");
          return (
            <div key={idx} className="flex items-start gap-2 pl-2 my-0.5">
              <span className="text-violet-400 mt-1 text-[8px]">•</span>
              <span className="flex-1 text-slate-300">{formatInline(bulletText)}</span>
            </div>
          );
        }

        return <p key={idx}>{formatInline(line)}</p>;
      })}
    </div>
  );
};

export const CopilotDrawer: React.FC<{ isOpen: boolean; onClose: () => void }> = ({
  isOpen,
  onClose,
}) => {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      sender: "copilot",
      text: "Hello! I am your AI Recruiter Copilot. Ask me anything about candidate profiles, skill gap analyses, or team fit recommendations.",
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    },
  ]);

  if (!isOpen) return null;

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || loading) return;

    const userMsg: Message = {
      id: Date.now().toString(),
      sender: "user",
      text: query,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, userMsg]);
    const currentQuery = query;
    setQuery("");
    setLoading(true);

    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:3006"}/api/v1/copilot/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: currentQuery }),
      });
      const data = await res.json();

      const copilotMsg: Message = {
        id: (Date.now() + 1).toString(),
        sender: "copilot",
        text: data.answer || "Analyzed candidates successfully.",
        candidates: data.retrieved_candidates || [],
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };
      setMessages((prev) => [...prev, copilotMsg]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          sender: "copilot",
          text: "Sorry, I encountered an error querying the talent database. Please verify your connection.",
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-y-0 right-0 z-50 w-full sm:w-[500px] bg-slate-950/95 backdrop-blur-2xl border-l border-violet-500/20 shadow-2xl flex flex-col transition-all duration-300">
      {/* Header */}
      <div className="p-4 border-b border-white/10 flex justify-between items-center bg-gradient-to-r from-violet-900/30 via-slate-900/50 to-slate-950">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-violet-600/20 border border-violet-500/30 rounded-xl text-violet-400 shadow-glow-violet-sm">
            <Bot size={20} />
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-100 flex items-center gap-1.5">
              Recruiter AI Copilot
              <span className="px-2 py-0.5 text-[9px] font-mono uppercase bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 rounded-full font-bold">
                Online
              </span>
            </h3>
            <p className="text-xs text-slate-400">Conversational RAG Talent Intelligence</p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="p-2 text-slate-400 hover:text-slate-100 rounded-lg hover:bg-white/10 transition"
        >
          <X size={18} />
        </button>
      </div>

      {/* Message Chat Body */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((m) => (
          <div
            key={m.id}
            className={`flex flex-col ${m.sender === "user" ? "items-end" : "items-start"}`}
          >
            <div
              className={`max-w-[92%] p-4 rounded-2xl text-xs leading-relaxed ${
                m.sender === "user"
                  ? "bg-violet-600 text-white rounded-br-none shadow-glow-violet-sm font-medium"
                  : "bg-slate-900/90 border border-white/10 text-slate-200 rounded-bl-none shadow-xl"
              }`}
            >
              {m.sender === "copilot" && (
                <div className="flex items-center gap-1 text-[10px] uppercase font-mono tracking-wider text-violet-400 mb-2 font-bold border-b border-violet-500/20 pb-1">
                  <Sparkles size={12} /> AI Talent Analysis
                </div>
              )}

              {/* Render formatted markdown for AI messages, plain text for user */}
              {m.sender === "copilot" ? (
                <FormattedMarkdown content={m.text} />
              ) : (
                <p className="whitespace-pre-wrap">{m.text}</p>
              )}

              {/* Clickable Candidate CV cards at end of message */}
              {m.candidates && m.candidates.length > 0 && (
                <div className="mt-4 space-y-2 pt-3 border-t border-white/10">
                  <p className="text-[10px] font-mono uppercase tracking-wider text-violet-400 font-bold flex items-center gap-1">
                    <UserCheck size={13} /> Retrieved Candidates (Click to View CV):
                  </p>
                  <div className="space-y-2">
                    {m.candidates.slice(0, 4).map((c) => {
                      const displayName =
                        c.name && c.name !== "Not provided" && c.name !== "null" && c.name !== "Unknown"
                          ? c.name
                          : `Candidate ${c.id.slice(0, 8)}`;
                      return (
                        <div
                          key={c.id}
                          className="p-3 rounded-xl bg-slate-950/80 hover:bg-slate-800 border border-violet-500/20 hover:border-violet-500/50 transition cursor-pointer flex flex-col sm:flex-row sm:items-center justify-between gap-2 shadow-lg group"
                          onClick={() => window.open(`/candidates/${c.id}`, "_blank")}
                        >
                          <div className="space-y-1">
                            <div className="flex items-center gap-2">
                              <span className="font-bold text-slate-100 group-hover:text-violet-300 transition text-xs">
                                {displayName}
                              </span>
                              <span className="px-1.5 py-0.5 text-[9px] font-mono bg-violet-500/20 text-violet-300 rounded border border-violet-500/30 font-semibold">
                                {c.experience_years || 0} yrs exp
                              </span>
                            </div>
                            <div className="flex flex-wrap gap-1">
                              {c.skills?.slice(0, 3).map((s) => (
                                <span key={s} className="px-1.5 py-0.5 rounded bg-white/5 text-slate-400 text-[9px] font-mono">
                                  {s}
                                </span>
                              ))}
                            </div>
                          </div>

                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              window.open(`/candidates/${c.id}`, "_blank");
                            }}
                            className="px-3 py-1.5 bg-violet-600 hover:bg-violet-500 text-white font-bold text-[10px] rounded-lg flex items-center justify-center gap-1.5 transition shadow-glow-violet-sm shrink-0"
                          >
                            <FileText size={12} />
                            View CV
                            <ExternalLink size={11} />
                          </button>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
            <span className="text-[9px] font-mono text-slate-500 mt-1 px-1">{m.timestamp}</span>
          </div>
        ))}

        {loading && (
          <div className="flex items-center gap-2 p-3 bg-slate-900/80 border border-white/10 rounded-2xl text-slate-400 text-xs w-fit">
            <Sparkles size={14} className="animate-spin text-violet-400" />
            <span>Copilot is searching talent pool & synthesizing response...</span>
          </div>
        )}
      </div>

      {/* Input bar */}
      <form onSubmit={handleSend} className="p-4 border-t border-white/10 bg-slate-950/80 flex gap-2">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ask Copilot (e.g. 'Show senior Python engineers')..."
          className="flex-1 bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-violet-500/50 transition font-sans"
        />
        <button
          type="submit"
          disabled={loading || !query.trim()}
          className="px-4 py-2.5 bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white font-semibold text-xs rounded-xl flex items-center gap-2 transition shadow-glow-violet-sm"
        >
          <Send size={14} />
        </button>
      </form>
    </div>
  );
};
