"use client";

import React, { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  CheckCircle2,
  Play,
  RefreshCw,
  Trash2,
  UploadCloud,
} from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { ldiApi } from "@/lib/api-client";
import { formatBytes, formatDateTime, statusColorClasses } from "@/lib/utils";

function ProcessingPageContent() {
  const searchParams = useSearchParams();
  const initialApplicantId = searchParams.get("applicantId") || "";
  const qc = useQueryClient();

  const [selectedApplicantId, setSelectedApplicantId] = useState(initialApplicantId);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [activeBatchId, setActiveBatchId] = useState<string | null>(null);
  const [uploadResult, setUploadResult] = useState<{
    total_accepted: number;
    rejected: Array<{ filename: string; reason: string }>;
  } | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (initialApplicantId) setSelectedApplicantId(initialApplicantId);
  }, [initialApplicantId]);

  const { data: applicantsData } = useQuery({
    queryKey: ["applicants-dropdown"],
    queryFn: () => ldiApi.listApplicants("?page_size=100"),
  });

  const { data: batches = [] } = useQuery({
    queryKey: ["processing-batches"],
    queryFn: ldiApi.listBatches,
    refetchInterval: 4000,
  });

  const { data: activeBatch } = useQuery({
    queryKey: ["batch-status", activeBatchId],
    queryFn: () => ldiApi.getBatchStatus(activeBatchId!),
    enabled: Boolean(activeBatchId),
    refetchInterval: (q) => {
      const st = q.state.data?.status;
      return st && ["UPLOADED", "QUEUED", "PROCESSING"].includes(st) ? 1500 : false;
    },
  });

  const uploadAndStartMutation = useMutation({
    mutationFn: async () => {
      if (!selectedApplicantId) throw new Error("Please select an applicant first.");
      if (selectedFiles.length === 0) throw new Error("Please choose files or a ZIP archive.");
      const uploaded = await ldiApi.uploadDocuments(selectedApplicantId, selectedFiles);
      setUploadResult({ total_accepted: uploaded.total_accepted, rejected: uploaded.rejected });
      setActiveBatchId(uploaded.batch_id);
      await ldiApi.startBatchProcessing(uploaded.batch_id);
      return uploaded.batch_id;
    },
    onSuccess: () => {
      setErrorMsg(null);
      setSelectedFiles([]);
      qc.invalidateQueries({ queryKey: ["processing-batches"] });
    },
    onError: (err) => {
      setErrorMsg(err instanceof Error ? err.message : "Upload failed");
    },
  });

  const retryMutation = useMutation({
    mutationFn: ldiApi.retryBatch,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["batch-status", activeBatchId] }),
  });

  const handleFileChange = (filesList: FileList | null) => {
    if (!filesList) return;
    setSelectedFiles((prev) => [...prev, ...Array.from(filesList)]);
  };

  return (
    <AppShell
      title="Bulk Document Processing"
      subtitle="Upload unsorted PDFs, images, Word documents, or ZIP archives and monitor AI extraction & classification."
    >
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Upload & Trigger Panel */}
        <div className="lg:col-span-2 space-y-5">
          <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm space-y-4">
            <div>
              <label className="block text-xs font-semibold text-navy uppercase tracking-wide mb-1.5">
                1. Select Applicant Record
              </label>
              <select
                value={selectedApplicantId}
                onChange={(e) => setSelectedApplicantId(e.target.value)}
                className="w-full px-3 py-2.5 text-sm rounded-lg border border-slate-300 bg-white"
              >
                <option value="">Choose an applicant...</option>
                {applicantsData?.items.map((app) => (
                  <option key={app.id} value={app.id}>
                    {app.application_reference} — {app.full_name} ({app.destination.name} / {app.purpose.name})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-navy uppercase tracking-wide mb-1.5">
                2. Upload Documents or ZIP Archive
              </label>
              <label
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  e.preventDefault();
                  handleFileChange(e.dataTransfer.files);
                }}
                className="flex flex-col items-center justify-center border-2 border-dashed border-slate-300 rounded-xl p-8 bg-slate-50/70 hover:bg-slate-100/70 cursor-pointer transition-colors text-center"
              >
                <UploadCloud className="h-9 w-9 text-navy mb-2" />
                <span className="text-sm font-medium text-slate-800">
                  Drag &amp; drop files here, or click to browse
                </span>
                <span className="text-xs text-slate-500 mt-1">
                  Supports PDF, JPG, JPEG, PNG, TIFF, DOC, DOCX, and ZIP (filenames can be arbitrary)
                </span>
                <input
                  type="file"
                  multiple
                  accept=".pdf,.jpg,.jpeg,.png,.tif,.tiff,.doc,.docx,.zip"
                  onChange={(e) => handleFileChange(e.target.files)}
                  className="hidden"
                />
              </label>
            </div>

            {selectedFiles.length > 0 && (
              <div className="border border-slate-200 rounded-lg divide-y divide-slate-100 max-h-52 overflow-y-auto">
                {selectedFiles.map((file, idx) => (
                  <div
                    key={`${file.name}-${idx}`}
                    className="px-3 py-2 flex items-center justify-between text-xs"
                  >
                    <div className="truncate pr-3">
                      <span className="font-medium text-slate-800">{file.name}</span>
                      <span className="text-slate-400 ml-2">{formatBytes(file.size)}</span>
                    </div>
                    <button
                      onClick={() =>
                        setSelectedFiles((prev) => prev.filter((_, i) => i !== idx))
                      }
                      className="text-slate-400 hover:text-red-600"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            )}

            {errorMsg && (
              <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-xs text-red-700 flex items-center gap-2">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>{errorMsg}</span>
              </div>
            )}

            {uploadResult && uploadResult.rejected.length > 0 && (
              <div className="rounded-lg bg-amber-50 border border-amber-200 px-4 py-3 text-xs text-amber-800 space-y-1">
                <div className="font-semibold">
                  {uploadResult.rejected.length} file(s) rejected by security/MIME validation:
                </div>
                {uploadResult.rejected.map((r, i) => (
                  <div key={i}>
                    • {r.filename}: {r.reason}
                  </div>
                ))}
              </div>
            )}

            <div className="flex items-center justify-between pt-2">
              <span className="text-xs text-slate-500">
                {selectedFiles.length} file(s) staged for secure upload
              </span>
              <button
                onClick={() => uploadAndStartMutation.mutate()}
                disabled={uploadAndStartMutation.isPending || selectedFiles.length === 0 || !selectedApplicantId}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-brand text-white text-sm font-medium hover:bg-brand-light disabled:opacity-50"
              >
                <Play className="h-4 w-4" />
                {uploadAndStartMutation.isPending ? "Uploading & Queuing..." : "Start AI Processing"}
              </button>
            </div>
          </div>

          {/* Live Batch Monitor */}
          {activeBatch && (
            <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h3 className="text-sm font-semibold text-navy">
                    Active Batch Monitor ({activeBatch.processed_files}/{activeBatch.total_files} processed)
                  </h3>
                  <p className="text-xs text-slate-500">
                    Status:{" "}
                    <span className={`px-2 py-0.5 rounded-full border ${statusColorClasses(activeBatch.status)}`}>
                      {activeBatch.status}
                    </span>
                  </p>
                </div>
                <div className="flex gap-2">
                  {activeBatch.failed_files > 0 && (
                    <button
                      onClick={() => retryMutation.mutate(activeBatch.id)}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-amber-300 bg-amber-50 text-xs font-medium text-amber-800"
                    >
                      <RefreshCw className="h-3.5 w-3.5" />
                      Retry Failed
                    </button>
                  )}
                  <Link
                    href={`/applicants/${activeBatch.applicant_id}`}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-navy text-white text-xs font-medium hover:bg-navy-700"
                  >
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    Review &amp; Approve Folder
                  </Link>
                </div>
              </div>

              <div className="divide-y divide-slate-100 border border-slate-200 rounded-lg">
                {activeBatch.jobs.map((job) => (
                  <div key={job.id} className="px-4 py-2.5 flex items-center justify-between gap-4 text-xs">
                    <div className="min-w-0 flex-1">
                      <div className="font-medium text-slate-800 truncate">
                        {job.original_filename || job.uploaded_document_id}
                      </div>
                      {job.error_log && (
                        <div className="text-red-600 text-[11px] truncate">{job.error_log}</div>
                      )}
                    </div>
                    <div className="w-32 bg-slate-100 h-2 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-brand transition-all"
                        style={{ width: `${job.progress_percent}%` }}
                      />
                    </div>
                    <span
                      className={`px-2 py-0.5 rounded-full text-[11px] font-medium border ${statusColorClasses(job.status)}`}
                    >
                      {job.status}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Recent Processing Batches Sidebar */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm h-fit">
          <h3 className="text-sm font-semibold text-navy mb-3">Recent Processing Batches</h3>
          {batches.length === 0 ? (
            <p className="text-xs text-slate-400 py-6 text-center">No batches processed yet.</p>
          ) : (
            <div className="space-y-2.5">
              {batches.map((b) => (
                <button
                  key={b.id}
                  onClick={() => setActiveBatchId(b.id)}
                  className={`w-full text-left p-3 rounded-lg border transition-colors text-xs ${
                    activeBatchId === b.id
                      ? "border-navy bg-navy-50/40"
                      : "border-slate-200 hover:bg-slate-50"
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-semibold text-navy truncate">{b.applicant_name}</span>
                    <span
                      className={`px-2 py-0.5 rounded-full text-[10px] border ${statusColorClasses(b.status)}`}
                    >
                      {b.status}
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-500">
                    {b.application_reference} · {b.processed_files}/{b.total_files} files
                  </div>
                  <div className="text-[10px] text-slate-400 mt-1">{formatDateTime(b.created_at)}</div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </AppShell>
  );
}

export default function ProcessingPage() {
  return (
    <Suspense
      fallback={
        <AppShell title="Document Processing">
          <div className="bg-white border border-slate-200 rounded-xl p-8 text-center text-sm text-slate-500">
            Loading document processing workspace...
          </div>
        </AppShell>
      }
    >
      <ProcessingPageContent />
    </Suspense>
  );
}
