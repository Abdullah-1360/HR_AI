// components/layout/Sidebar.tsx
"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Briefcase, Users, GitFork, Shield, Cpu } from "lucide-react";

export const Sidebar: React.FC = () => {
  const pathname = usePathname();

  const links = [
    { href: "/", label: "Dashboard", icon: LayoutDashboard },
    { href: "/jobs", label: "Jobs", icon: Briefcase },
    { href: "/candidates", label: "Candidates", icon: Users },
    { href: "/hiring", label: "Hiring Hub", icon: GitFork },
    { href: "/router", label: "Router Intelligence", icon: Cpu },
  ];

  return (
    <aside className="w-64 bg-bg-surface border-r border-border-subtle flex flex-col justify-between h-screen fixed left-0 top-0 z-20">
      <div className="flex flex-col">
        {/* Brand */}
        <div className="p-6 border-b border-border-subtle flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-primary flex items-center justify-center font-bold text-white shadow-glow-violet-sm">
            H
          </div>
          <div>
            <h1 className="text-sm font-bold text-slate-100 tracking-tight">HR AI Platform</h1>
            <span className="text-[10px] text-slate-500 font-mono">v0.1.0 (Router OS)</span>
          </div>
        </div>

        {/* Links */}
        <nav className="p-4 space-y-1">
          {links.map((link) => {
            const Icon = link.icon;
            const active =
              link.href === "/"
                ? pathname === "/"
                : pathname?.startsWith(link.href);

            return (
              <Link
                key={link.href}
                href={link.href}
                className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all duration-200 ${
                  active
                    ? "bg-gradient-primary text-white shadow-glow-violet-sm"
                    : "text-slate-400 hover:text-slate-200 hover:bg-white/5"
                }`}
              >
                <Icon size={18} />
                {link.label}
              </Link>
            );
          })}
        </nav>
      </div>

      {/* Footer info */}
      <div className="p-6 border-t border-border-subtle text-[11px] text-slate-600 font-mono space-y-1">
        <div className="flex items-center gap-1.5">
          <Shield size={12} className="text-violet-500" />
          <span>Secured with RBAC</span>
        </div>
        <p>© 2026 HR AI. Router Graph.</p>
      </div>
    </aside>
  );
};
export default Sidebar;
