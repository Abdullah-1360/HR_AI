"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  Activity,
  Cpu,
  Layers,
  Zap,
  Server,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  RefreshCw,
  Clock,
  Database,
  ArrowRight,
  TrendingUp,
  BarChart2,
  Flame,
  ShieldAlert,
  Search,
  Filter,
} from "lucide-react";
import { api } from "@/lib/api";
import type {
  RouterOverviewResponse,
  RouterProvider,
  RouterModel,
  RouterRequestLog,
  RouterTierWaterfall,
} from "@/lib/types";

export default function RouterIntelligencePage() {
  const [overview, setOverview] = useState<RouterOverviewResponse | null>(null);
  const [providers, setProviders] = useState<RouterProvider[]>([]);
  const [models, setModels] = useState<RouterModel[]>([]);
  const [requests, setRequests] = useState<RouterRequestLog[]>([]);
  const [waterfall, setWaterfall] = useState<RouterTierWaterfall[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastRefreshed, setLastRefreshed] = useState<Date>(new Date());
  const [activeTab, setActiveTab] = useState<"models" | "providers" | "stream" | "waterfall">("models");
  const [searchFilter, setSearchFilter] = useState("");
  const [tierFilter, setTierFilter] = useState<string>("ALL");

  const fetchData = useCallback(async (isInitial = false) => {
    if (isInitial) setLoading(true);
    else setRefreshing(true);

    try {
      const [ovRes, provRes, modRes, reqRes, wfRes] = await Promise.all([
        api.router.getOverview().catch(() => null),
        api.router.getProviders().catch(() => []),
        api.router.getModels().catch(() => []),
        api.router.getRequests(50).catch(() => ({ items: [], total: 0 })),
        api.router.getTierWaterfall().catch(() => []),
      ]);

      if (ovRes) setOverview(ovRes);
      setProviders(provRes);
      setModels(modRes);
      setRequests(reqRes.items || []);
      setWaterfall(wfRes);
      setLastRefreshed(new Date());
    } catch (err) {
      console.error("Router stats fetch error:", err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchData(true);
    const interval = setInterval(() => {
      fetchData(false);
    }, 5000);
    return () => clearInterval(interval);
  }, [fetchData]);

  // Filtered models
  const filteredModels = models.filter((m) => {
    const matchesSearch =
      m.model_name.toLowerCase().includes(searchFilter.toLowerCase()) ||
      m.provider.display_name.toLowerCase().includes(searchFilter.toLowerCase()) ||
      m.tier.toLowerCase().includes(searchFilter.toLowerCase());
    const matchesTier = tierFilter === "ALL" || m.tier === tierFilter;
    return matchesSearch && matchesTier;
  });

  const getTierColor = (tier: string) => {
    switch (tier) {
      case "PRIMARY_FREE":
        return "text-emerald-400 bg-emerald-500/10 border-emerald-500/30";
      case "SECONDARY_FREE":
        return "text-cyan-400 bg-cyan-500/10 border-cyan-500/30";
      case "LIMITED_FREE":
        return "text-amber-400 bg-amber-500/10 border-amber-500/30";
      case "PAID":
        return "text-violet-400 bg-violet-500/10 border-violet-500/30";
      case "LOCAL":
        return "text-slate-400 bg-slate-500/10 border-slate-500/30";
      default:
        return "text-slate-300 bg-slate-500/10 border-slate-500/30";
    }
  };

  const ov = overview?.overview;

  return (
    <div className="space-y-8 pb-16">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-border-subtle pb-6">
        <div>
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-violet-500/10 border border-violet-500/30 text-violet-400 shadow-glow-violet-sm">
              <Cpu size={24} />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-slate-100 tracking-tight flex items-center gap-2">
                Router Intelligence & Telemetry
                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse mr-1.5" />
                  Live (5s Poll)
                </span>
              </h1>
              <p className="text-sm text-slate-400 mt-0.5">
                Real-time multi-provider routing state, quota windows, tier waterfall, and token analytics
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="text-xs font-mono text-slate-500 flex items-center gap-1.5 bg-bg-surface px-3 py-1.5 rounded-lg border border-border-subtle">
            <Clock size={12} className="text-slate-400" />
            Updated {lastRefreshed.toLocaleTimeString()}
          </div>
          <button
            onClick={() => fetchData(false)}
            disabled={refreshing}
            className="flex items-center gap-2 px-3.5 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-slate-300 hover:text-white border border-border-subtle text-xs font-medium transition-all"
          >
            <RefreshCw size={13} className={refreshing ? "animate-spin text-violet-400" : ""} />
            Sync Now
          </button>
        </div>
      </div>

      {/* KPI Overview Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-6 gap-4">
        <div className="bg-bg-surface/80 border border-border-subtle rounded-2xl p-4 backdrop-blur shadow-card hover:border-violet-500/40 transition-all">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium mb-2">
            <span>Total Requests</span>
            <Activity size={14} className="text-violet-400" />
          </div>
          <div className="text-2xl font-bold text-slate-100 font-mono">
            {loading ? "..." : (ov?.total_requests ?? 0).toLocaleString()}
          </div>
          <div className="text-[11px] text-slate-500 mt-1 flex items-center gap-1">
            <span className="text-emerald-400 font-medium">
              {ov?.success_count ?? 0}
            </span> ok · <span className="text-rose-400">{ov?.failure_count ?? 0}</span> failed
          </div>
        </div>

        <div className="bg-bg-surface/80 border border-border-subtle rounded-2xl p-4 backdrop-blur shadow-card hover:border-cyan-500/40 transition-all">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium mb-2">
            <span>Tokens Consumed</span>
            <Flame size={14} className="text-cyan-400" />
          </div>
          <div className="text-2xl font-bold text-cyan-400 font-mono">
            {loading ? "..." : (ov?.total_tokens ?? 0).toLocaleString()}
          </div>
          <div className="text-[11px] text-slate-500 mt-1">
            In: {(ov?.prompt_tokens ?? 0).toLocaleString()} · Out: {(ov?.completion_tokens ?? 0).toLocaleString()}
          </div>
        </div>

        <div className="bg-bg-surface/80 border border-border-subtle rounded-2xl p-4 backdrop-blur shadow-card hover:border-emerald-500/40 transition-all">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium mb-2">
            <span>Success Rate</span>
            <CheckCircle2 size={14} className="text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-emerald-400 font-mono">
            {loading ? "..." : `${ov?.success_rate ?? 100}%`}
          </div>
          <div className="text-[11px] text-slate-500 mt-1">
            Across all router tiers
          </div>
        </div>

        <div className="bg-bg-surface/80 border border-border-subtle rounded-2xl p-4 backdrop-blur shadow-card hover:border-amber-500/40 transition-all">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium mb-2">
            <span>Avg Latency</span>
            <Zap size={14} className="text-amber-400" />
          </div>
          <div className="text-2xl font-bold text-amber-400 font-mono">
            {loading ? "..." : `${ov?.avg_latency_ms ?? 0}ms`}
          </div>
          <div className="text-[11px] text-slate-500 mt-1">
            Rolling execution time
          </div>
        </div>

        <div className="bg-bg-surface/80 border border-border-subtle rounded-2xl p-4 backdrop-blur shadow-card hover:border-violet-500/40 transition-all">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium mb-2">
            <span>Active Providers</span>
            <Server size={14} className="text-violet-400" />
          </div>
          <div className="text-2xl font-bold text-slate-100 font-mono">
            {loading ? "..." : `${ov?.active_providers ?? 0}/${ov?.total_providers ?? 0}`}
          </div>
          <div className="text-[11px] text-slate-500 mt-1">
            Gemini, Groq, Mistral, etc.
          </div>
        </div>

        <div className="bg-bg-surface/80 border border-border-subtle rounded-2xl p-4 backdrop-blur shadow-card hover:border-cyan-500/40 transition-all">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium mb-2">
            <span>Healthy Models</span>
            <Layers size={14} className="text-cyan-400" />
          </div>
          <div className="text-2xl font-bold text-slate-100 font-mono">
            {loading ? "..." : `${ov?.healthy_models ?? 0}/${ov?.total_models ?? 0}`}
          </div>
          <div className="text-[11px] text-slate-500 mt-1">
            Auto-failover enabled
          </div>
        </div>
      </div>

      {/* Tier Waterfall Bar & Provider Distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Tier Waterfall Distribution */}
        <div className="lg:col-span-2 bg-bg-surface/80 border border-border-subtle rounded-2xl p-6 backdrop-blur shadow-card">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-base font-bold text-slate-100 flex items-center gap-2">
                <Layers size={18} className="text-violet-400" />
                Tier Waterfall Execution Flow
              </h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Dynamic routing priority: Requests cascade from top free tier down to paid fallbacks
              </p>
            </div>
            <span className="text-xs font-mono px-2.5 py-1 rounded-md bg-white/5 text-slate-300 border border-border-subtle">
              Priority Cascade
            </span>
          </div>

          <div className="space-y-3 mt-4">
            {waterfall.map((w, idx) => {
              const totalReqs = ov?.total_requests || 1;
              const pct = totalReqs > 0 ? Math.round((w.request_count / totalReqs) * 100) : 0;
              return (
                <div
                  key={w.tier}
                  className="p-3.5 rounded-xl bg-bg-card/60 border border-border-subtle hover:border-violet-500/30 transition-all"
                >
                  <div className="flex items-center justify-between text-xs mb-2">
                    <div className="flex items-center gap-2">
                      <span className="w-5 h-5 rounded-full bg-white/5 border border-border-subtle flex items-center justify-center font-mono text-[10px] text-slate-400">
                        {idx + 1}
                      </span>
                      <span className={`px-2 py-0.5 rounded font-mono font-bold text-[11px] border ${getTierColor(w.tier)}`}>
                        {w.tier}
                      </span>
                      <span className="text-slate-400 hidden sm:inline text-[11px]">
                        {w.description}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 font-mono">
                      <span className="text-slate-200 font-bold">{w.request_count} reqs</span>
                      <span className="text-slate-500">({pct}%)</span>
                      <span className="text-cyan-400">{w.total_tokens.toLocaleString()} tok</span>
                      <span className="text-amber-400">{w.avg_latency_ms}ms</span>
                    </div>
                  </div>

                  {/* Progress bar */}
                  <div className="w-full h-2 bg-black/40 rounded-full overflow-hidden flex">
                    <div
                      className="bg-gradient-to-r from-violet-500 to-cyan-400 h-full rounded-full transition-all duration-500"
                      style={{ width: `${Math.max(pct, 2)}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Tokens by Provider Card */}
        <div className="bg-bg-surface/80 border border-border-subtle rounded-2xl p-6 backdrop-blur shadow-card flex flex-col justify-between">
          <div>
            <h2 className="text-base font-bold text-slate-100 flex items-center gap-2 mb-1">
              <BarChart2 size={18} className="text-cyan-400" />
              Token Consumption by Provider
            </h2>
            <p className="text-xs text-slate-400 mb-4">
              Real-time token distribution across active LLM backends
            </p>

            <div className="space-y-3">
              {(overview?.by_provider || []).slice(0, 6).map((p) => {
                const totalTok = ov?.total_tokens || 1;
                const pct = totalTok > 0 ? Math.round((p.tokens / totalTok) * 100) : 0;
                return (
                  <div key={p.provider_key} className="space-y-1">
                    <div className="flex justify-between text-xs font-mono">
                      <span className="text-slate-300 font-medium capitalize">{p.provider_name}</span>
                      <span className="text-slate-400">
                        {p.tokens.toLocaleString()} <span className="text-slate-600">({pct}%)</span>
                      </span>
                    </div>
                    <div className="w-full h-1.5 bg-black/40 rounded-full overflow-hidden">
                      <div
                        className="bg-cyan-400 h-full rounded-full transition-all duration-500"
                        style={{ width: `${Math.max(pct, 1)}%` }}
                      />
                    </div>
                  </div>
                );
              })}
              {(!overview?.by_provider || overview.by_provider.length === 0) && (
                <div className="text-xs text-slate-500 py-6 text-center">
                  No requests logged yet. Upload resumes to see live token telemetry.
                </div>
              )}
            </div>
          </div>

          <div className="pt-4 border-t border-border-subtle mt-4 text-[11px] text-slate-500 flex items-center justify-between">
            <span>Automatic quota preservation</span>
            <span className="text-emerald-400 flex items-center gap-1">
              <CheckCircle2 size={12} /> Active
            </span>
          </div>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="flex items-center justify-between gap-4 border-b border-border-subtle">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setActiveTab("models")}
            className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-all ${
              activeTab === "models"
                ? "border-violet-500 text-violet-400 font-semibold"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <Cpu size={16} />
            Models & Quotas ({models.length})
          </button>
          <button
            onClick={() => setActiveTab("providers")}
            className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-all ${
              activeTab === "providers"
                ? "border-violet-500 text-violet-400 font-semibold"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <Server size={16} />
            Providers ({providers.length})
          </button>
          <button
            onClick={() => setActiveTab("stream")}
            className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-all ${
              activeTab === "stream"
                ? "border-violet-500 text-violet-400 font-semibold"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <Activity size={16} />
            Live Request Stream ({requests.length})
          </button>
        </div>

        {activeTab === "models" && (
          <div className="flex items-center gap-2 pb-2">
            <div className="relative">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
              <input
                type="text"
                placeholder="Search models..."
                value={searchFilter}
                onChange={(e) => setSearchFilter(e.target.value)}
                className="pl-8 pr-3 py-1.5 rounded-lg bg-bg-surface border border-border-subtle text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-violet-500 w-40 sm:w-56"
              />
            </div>
            <select
              value={tierFilter}
              onChange={(e) => setTierFilter(e.target.value)}
              className="bg-bg-surface border border-border-subtle text-xs text-slate-300 rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-violet-500 font-mono"
            >
              <option value="ALL">All Tiers</option>
              <option value="PRIMARY_FREE">PRIMARY_FREE</option>
              <option value="SECONDARY_FREE">SECONDARY_FREE</option>
              <option value="LIMITED_FREE">LIMITED_FREE</option>
              <option value="PAID">PAID</option>
              <option value="LOCAL">LOCAL</option>
            </select>
          </div>
        )}
      </div>

      {/* Tab 1: Models & Quota Table */}
      {activeTab === "models" && (
        <div className="bg-bg-surface/80 border border-border-subtle rounded-2xl overflow-hidden backdrop-blur shadow-card">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-black/30 border-b border-border-subtle text-slate-400 font-mono uppercase text-[10px]">
                <tr>
                  <th className="py-3.5 px-4">Model & Provider</th>
                  <th className="py-3.5 px-4">Tier</th>
                  <th className="py-3.5 px-4">Health / Latency</th>
                  <th className="py-3.5 px-4">Scores</th>
                  <th className="py-3.5 px-4">Quota Utilization</th>
                  <th className="py-3.5 px-4">Capabilities</th>
                  <th className="py-3.5 px-4">Last Selected</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-subtle">
                {filteredModels.map((m) => {
                  const quota = m.quotas[0];
                  return (
                    <tr key={m.id} className="hover:bg-white/[0.02] transition-colors">
                      <td className="py-3.5 px-4">
                        <div className="font-semibold text-slate-100 text-sm flex items-center gap-1.5">
                          <span
                            className={`w-2 h-2 rounded-full ${
                              m.health.healthy ? "bg-emerald-400 shadow-glow-emerald" : "bg-rose-400"
                            }`}
                          />
                          {m.display_name || m.model_name}
                        </div>
                        <div className="text-[11px] text-slate-400 font-mono capitalize mt-0.5">
                          {m.provider.display_name} ·{" "}
                          <span className="text-slate-500">{m.context_window ? `${m.context_window / 1000}k ctx` : "default ctx"}</span>
                        </div>
                      </td>

                      <td className="py-3.5 px-4">
                        <span className={`px-2 py-0.5 rounded font-mono font-bold text-[10px] border ${getTierColor(m.tier)}`}>
                          {m.tier}
                        </span>
                      </td>

                      <td className="py-3.5 px-4 font-mono">
                        <div className="text-slate-200">
                          {m.health.avg_latency_ms ? `${m.health.avg_latency_ms}ms` : "—"}
                        </div>
                        <div className="text-[10px] text-slate-500">
                          err: {m.health.error_rate}%
                        </div>
                      </td>

                      <td className="py-3.5 px-4 font-mono">
                        <div className="flex items-center gap-1.5">
                          <span className="text-violet-400 font-bold">{m.scores.overall}</span>
                          <span className="text-[10px] text-slate-500">
                            (spd: {m.scores.speed} · qly: {m.scores.quality})
                          </span>
                        </div>
                      </td>

                      <td className="py-3.5 px-4 min-w-[200px]">
                        {quota ? (
                          <div className="space-y-1">
                            <div className="flex justify-between text-[11px] font-mono">
                              <span className="text-slate-400">
                                {quota.type}/{quota.window}
                              </span>
                              <span className="text-slate-200 font-semibold">
                                {quota.used.toLocaleString()} / {quota.limit.toLocaleString()}
                              </span>
                            </div>
                            <div className="w-full h-1.5 bg-black/40 rounded-full overflow-hidden">
                              <div
                                className={`h-full rounded-full transition-all duration-300 ${
                                  quota.usage_percentage > 80
                                    ? "bg-rose-400"
                                    : quota.usage_percentage > 50
                                    ? "bg-amber-400"
                                    : "bg-emerald-400"
                                }`}
                                style={{ width: `${Math.max(quota.usage_percentage, 2)}%` }}
                              />
                            </div>
                          </div>
                        ) : (
                          <span className="text-slate-500 font-mono text-[11px]">No active quota limit</span>
                        )}
                      </td>

                      <td className="py-3.5 px-4">
                        <div className="flex items-center gap-1">
                          {m.capabilities.tools && (
                            <span className="px-1.5 py-0.5 rounded bg-violet-500/10 text-violet-400 border border-violet-500/20 text-[10px] font-mono">
                              tools
                            </span>
                          )}
                          {m.capabilities.vision && (
                            <span className="px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 text-[10px] font-mono">
                              vision
                            </span>
                          )}
                          {m.capabilities.coding && (
                            <span className="px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-[10px] font-mono">
                              code
                            </span>
                          )}
                          {!m.capabilities.tools && !m.capabilities.vision && !m.capabilities.coding && (
                            <span className="text-slate-600 text-[10px] font-mono">chat</span>
                          )}
                        </div>
                      </td>

                      <td className="py-3.5 px-4 font-mono text-[11px] text-slate-400">
                        {m.last_selected_at
                          ? new Date(m.last_selected_at).toLocaleTimeString()
                          : "Never"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 2: Providers Grid */}
      {activeTab === "providers" && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {providers.map((p) => (
            <div
              key={p.id}
              className="bg-bg-surface/80 border border-border-subtle rounded-2xl p-5 backdrop-blur shadow-card hover:border-violet-500/40 transition-all flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2.5">
                    <div className="w-9 h-9 rounded-xl bg-violet-500/10 border border-violet-500/30 flex items-center justify-center font-bold text-violet-400 font-mono uppercase">
                      {p.name.slice(0, 2)}
                    </div>
                    <div>
                      <h3 className="font-bold text-slate-100 text-sm capitalize">{p.display_name || p.name}</h3>
                      <span className="text-[11px] text-slate-500 font-mono">{p.provider_type}</span>
                    </div>
                  </div>

                  <span
                    className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-mono font-medium border ${
                      p.metrics.healthy
                        ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                        : "bg-rose-500/10 text-rose-400 border-rose-500/30"
                    }`}
                  >
                    <span
                      className={`w-1.5 h-1.5 rounded-full mr-1.5 ${
                        p.metrics.healthy ? "bg-emerald-400" : "bg-rose-400"
                      }`}
                    />
                    {p.metrics.healthy ? "Healthy" : "Degraded"}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-3 p-3 rounded-xl bg-bg-card/60 border border-border-subtle my-3 font-mono text-xs">
                  <div>
                    <div className="text-[10px] text-slate-500">ACTIVE MODELS</div>
                    <div className="font-bold text-slate-200 mt-0.5">
                      {p.metrics.active_models}/{p.metrics.total_models}
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] text-slate-500">AVG LATENCY</div>
                    <div className="font-bold text-amber-400 mt-0.5">
                      {p.metrics.avg_latency_ms}ms
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] text-slate-500">TOKENS USED</div>
                    <div className="font-bold text-cyan-400 mt-0.5">
                      {p.metrics.tokens_consumed.toLocaleString()}
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] text-slate-500">TOTAL REQUESTS</div>
                    <div className="font-bold text-slate-200 mt-0.5">
                      {p.metrics.total_requests}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-1.5 mt-2">
                  {p.capabilities.streaming && (
                    <span className="px-1.5 py-0.5 rounded bg-white/5 border border-border-subtle text-[10px] font-mono text-slate-400">
                      streaming
                    </span>
                  )}
                  {p.capabilities.tools && (
                    <span className="px-1.5 py-0.5 rounded bg-white/5 border border-border-subtle text-[10px] font-mono text-slate-400">
                      tools
                    </span>
                  )}
                  {p.capabilities.images && (
                    <span className="px-1.5 py-0.5 rounded bg-white/5 border border-border-subtle text-[10px] font-mono text-slate-400">
                      images
                    </span>
                  )}
                  {p.capabilities.reasoning && (
                    <span className="px-1.5 py-0.5 rounded bg-white/5 border border-border-subtle text-[10px] font-mono text-slate-400">
                      reasoning
                    </span>
                  )}
                </div>
              </div>

              <div className="pt-3 border-t border-border-subtle mt-4 text-[11px] text-slate-500 flex justify-between font-mono">
                <span>Priority: #{p.priority}</span>
                <span className={`font-bold ${getTierColor(p.tier)} px-1.5 py-0.2 rounded border`}>
                  {p.tier}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Tab 3: Live Request Stream */}
      {activeTab === "stream" && (
        <div className="bg-bg-surface/80 border border-border-subtle rounded-2xl overflow-hidden backdrop-blur shadow-card">
          <div className="p-4 border-b border-border-subtle flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Activity size={16} className="text-violet-400" />
              <h3 className="font-bold text-slate-100 text-sm">Telemetry Request Log (Last 50)</h3>
            </div>
            <span className="text-xs font-mono text-slate-500">Live PostgreSQL Stream</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-black/30 border-b border-border-subtle text-slate-400 font-mono uppercase text-[10px]">
                <tr>
                  <th className="py-3 px-4">Timestamp</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Provider & Model</th>
                  <th className="py-3 px-4">Tier</th>
                  <th className="py-3 px-4">Tokens (In / Out)</th>
                  <th className="py-3 px-4">Latency</th>
                  <th className="py-3 px-4">Attempts</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-subtle font-mono">
                {requests.map((r) => (
                  <tr key={r.id} className="hover:bg-white/[0.02] transition-colors">
                    <td className="py-3 px-4 text-slate-400 text-[11px]">
                      {r.created_at ? new Date(r.created_at).toLocaleTimeString() : "—"}
                    </td>

                    <td className="py-3 px-4">
                      {r.status === "success" ? (
                        <span className="inline-flex items-center gap-1 text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 px-2 py-0.5 rounded text-[10px] font-bold">
                          <CheckCircle2 size={10} /> 200 OK
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-rose-400 bg-rose-500/10 border border-rose-500/30 px-2 py-0.5 rounded text-[10px] font-bold">
                          <XCircle size={10} /> {r.error_message ? r.error_message.slice(0, 20) : "Failed"}
                        </span>
                      )}
                    </td>

                    <td className="py-3 px-4">
                      <div className="font-semibold text-slate-200 capitalize">
                        {r.provider_display_name || r.provider_name}
                      </div>
                      <div className="text-[10px] text-slate-500">{r.model_display_name || r.model_name}</div>
                    </td>

                    <td className="py-3 px-4">
                      <span className={`px-1.5 py-0.5 rounded text-[10px] border ${getTierColor(r.tier)}`}>
                        {r.tier}
                      </span>
                    </td>

                    <td className="py-3 px-4 text-slate-300">
                      <span className="text-cyan-400 font-bold">{(r.total_tokens || 0).toLocaleString()}</span>
                      <span className="text-slate-500 text-[10px] ml-1">
                        ({r.prompt_tokens || 0} / {r.completion_tokens || 0})
                      </span>
                    </td>

                    <td className="py-3 px-4">
                      <span className="text-amber-400 font-bold">{r.latency_ms ? `${r.latency_ms}ms` : "—"}</span>
                    </td>

                    <td className="py-3 px-4 text-slate-400">
                      #{r.attempt}
                    </td>
                  </tr>
                ))}

                {requests.length === 0 && (
                  <tr>
                    <td colSpan={7} className="py-8 text-center text-slate-500 text-xs">
                      No requests recorded yet. Upload resumes or use the Copilot to see live telemetry.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
