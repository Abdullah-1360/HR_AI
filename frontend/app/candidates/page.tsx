// app/candidates/page.tsx
"use client";

import React, { useEffect, useState, useRef } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { Candidate } from "@/lib/types";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Upload, Users, Search, ArrowRight, X, FileText, Loader2, CheckCircle } from "lucide-react";

export default function CandidatesPage() {
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  // Upload state
  const [dragActive, setDragActive] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<{ success: boolean; msg: string } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadCandidates = async () => {
    try {
      setLoading(true);
      const data = await api.candidates.list();
      setCandidates(data.items || []);
    } catch (err) {
      console.error("Failed to load candidates:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCandidates();
  }, []);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      await handleUploadFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      await handleUploadFile(e.target.files[0]);
    }
  };

  const handleUploadFile = async (file: File) => {
    if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
      setUploadStatus({ success: false, msg: "Only PDF files are supported" });
      return;
    }

    try {
      setUploading(true);
      setUploadStatus(null);
      const res = await api.candidates.upload(file);
      setUploadStatus({ success: true, msg: `Ingested profile for: ${res.name || "Unknown"}` });
      await loadCandidates();
    } catch (err: any) {
      setUploadStatus({
        success: false,
        msg: err.response?.data?.detail || err.message || "Failed to upload resume",
      });
    } finally {
      setUploading(false);
    }
  };

  const filteredCandidates = candidates.filter(
    (c) =>
      c.name?.toLowerCase().includes(search.toLowerCase()) ||
      c.skills?.some((s) => s.toLowerCase().includes(search.toLowerCase()))
  );

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-extrabold text-slate-100 tracking-tight">Candidates Database</h1>
        <p className="text-sm text-slate-400 mt-1">Ingest, view, and analyze candidate resumes using the AI pipeline.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left column: upload resume */}
        <div className="space-y-6">
          <Card>
            <h3 className="text-md font-bold text-slate-200 mb-4 font-mono text-xs uppercase tracking-wider text-slate-500">
              Ingest Candidate Resume
            </h3>

            {/* Drag & drop zone */}
            <div
              className={`upload-zone rounded-xl p-8 text-center flex flex-col items-center justify-center cursor-pointer transition relative min-h-[220px] ${
                dragActive ? "drag-active border-violet-500 bg-violet-500/5" : ""
              }`}
              onDragEnter={handleDrag}
              onDragOver={handleDrag}
              onDragLeave={handleDrag}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
            >
              <input
                ref={fileInputRef}
                type="file"
                className="hidden"
                accept=".pdf"
                onChange={handleFileChange}
              />

              {uploading ? (
                <div className="space-y-3 flex flex-col items-center">
                  <Loader2 size={36} className="text-violet-500 animate-spin" />
                  <h4 className="font-semibold text-sm text-slate-300">Extracting & Parsing...</h4>
                  <p className="text-xs text-slate-500">Running AI resume parsing agent</p>
                </div>
              ) : (
                <div className="space-y-3 flex flex-col items-center">
                  <Upload size={32} className="text-slate-500" />
                  <h4 className="font-semibold text-sm text-slate-300">Drag & drop PDF here</h4>
                  <p className="text-xs text-slate-500">or click to browse your files</p>
                </div>
              )}
            </div>

            {/* Upload message alerts */}
            {uploadStatus && (
              <div
                className={`mt-4 p-4 rounded-xl flex items-start gap-3 border text-xs ${
                  uploadStatus.success
                    ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-400"
                    : "bg-red-500/10 border-red-500/20 text-red-400"
                }`}
              >
                {uploadStatus.success ? (
                  <CheckCircle size={16} className="shrink-0 mt-0.5" />
                ) : (
                  <X size={16} className="shrink-0 mt-0.5 cursor-pointer" onClick={() => setUploadStatus(null)} />
                )}
                <span>{uploadStatus.msg}</span>
              </div>
            )}
          </Card>
        </div>

        {/* Right column: listing */}
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <div className="flex justify-between items-center gap-4 mb-6">
              <div className="relative max-w-sm flex-1">
                <span className="absolute inset-y-0 left-0 pl-3 flex items-center text-slate-500">
                  <Search size={16} />
                </span>
                <input
                  type="text"
                  placeholder="Search candidates by name or skill..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="input-base pl-9 py-1.5 text-xs"
                />
              </div>
            </div>

            {loading ? (
              <div className="space-y-4">
                <div className="h-10 skeleton rounded-lg" />
                <div className="h-10 skeleton rounded-lg" />
                <div className="h-10 skeleton rounded-lg" />
              </div>
            ) : filteredCandidates.length === 0 ? (
              <div className="text-center py-16 text-slate-500 text-sm">
                No candidates found.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Candidate Name</th>
                      <th>Experience</th>
                      <th>Skills Overview</th>
                      <th aria-label="Actions"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredCandidates.map((c) => (
                      <tr key={c.id}>
                        <td>
                          <div>
                            <div className="font-semibold text-slate-200">{c.name || "Unnamed"}</div>
                            <div className="text-xs text-slate-500 font-mono mt-0.5">{c.email || "No email"}</div>
                          </div>
                        </td>
                        <td className="font-mono text-xs">{c.experience_years || 0} yrs</td>
                        <td>
                          <div className="flex flex-wrap gap-1.5 max-w-xs">
                            {c.skills?.slice(0, 3).map((s) => (
                              <Badge key={s} variant="cyan" className="text-[10px] py-0 px-1.5">
                                {s}
                              </Badge>
                            ))}
                            {c.skills && c.skills.length > 3 && (
                              <Badge variant="slate" className="text-[10px] py-0 px-1.5">
                                +{c.skills.length - 3}
                              </Badge>
                            )}
                          </div>
                        </td>
                        <td>
                          <Link
                            href={`/candidates/${c.id}`}
                            className="p-1.5 hover:bg-white/5 rounded-lg text-slate-500 hover:text-slate-300 block transition text-center"
                          >
                            <ArrowRight size={16} />
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
