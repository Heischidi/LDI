"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowLeft,
  BellRing,
  Check,
  CheckCheck,
  Download,
  Eye,
  FileText,
  FolderArchive,
  Mail,
  RefreshCw,
  Send,
  Trash2,
  UploadCloud,
  XCircle,
} from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { useAuth } from "@/hooks/use-auth";
import { API_BASE_URL, downloadAuthorizedFile, getStoredTokens, ldiApi } from "@/lib/api-client";
import { formatBytes, formatDateTime, statusColorClasses } from "@/lib/utils";
import type { DocumentRecord } from "@/types";

export default function ApplicantDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { hasRole } = useAuth();
  const canDelete = hasRole("SUPER_ADMIN", "ADMIN", "OFFICER");
  const applicantId = params.id;
  const qc = useQueryClient();

  const [previewDoc, setPreviewDoc] = useState<DocumentRecord | null>(null);
  const [statusBanner, setStatusBanner] = useState<string | null>(null);
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);
  const [selectedExportIds, setSelectedExportIds] = useState<string[]>([]);
  const [track, setTrack] = useState<string>("DOCUMENT_REMINDER");
  const [stageCode, setStageCode] = useState<string>("MISSING_DOCUMENTS_REMINDER");
  const [emailSubject, setEmailSubject] = useState<string>("");
  const [emailBody, setEmailBody] = useState<string>("");
  const [includeMissing, setIncludeMissing] = useState<boolean>(true);
  const [updateStatusFlag, setUpdateStatusFlag] = useState<boolean>(true);

  const { data: applicant, isLoading } = useQuery({
    queryKey: ["applicant", applicantId],
    queryFn: () => ldiApi.getApplicant(applicantId),
    refetchInterval: (q) =>
      q.state.data?.batches?.some((b) => ["QUEUED", "PROCESSING"].includes(b.status))
        ? 2500
        : false,
  });

  const { data: stageCatalog } = useQuery({
    queryKey: ["stage-catalog"],
    queryFn: ldiApi.getStageCatalog,
  });

  const { data: docTypes = [] } = useQuery({
    queryKey: ["document-types"],
    queryFn: ldiApi.listDocumentTypes,
  });

  useEffect(() => {
    if (!stageCatalog || !applicant) return;
    const options = stageCatalog[track] || [];
    const activeOpt = options.find((o) => o.code === stageCode) || options[0];
    if (!activeOpt) return;
    if (activeOpt.code !== stageCode) setStageCode(activeOpt.code);
    const fillVars = (raw: string) =>
      raw
        .replaceAll("{applicant_name}", applicant.full_name)
        .replaceAll("{application_reference}", applicant.application_reference)
        .replaceAll("{destination}", applicant.destination.name)
        .replaceAll("{purpose}", applicant.purpose.name)
        .replaceAll("{category}", applicant.category.name)
        .replaceAll("{stage_label}", activeOpt.label);
    setEmailSubject(fillVars(activeOpt.default_subject));
    setEmailBody(fillVars(activeOpt.default_message));
    setIncludeMissing(
      track === "DOCUMENT_REMINDER" && activeOpt.code === "MISSING_DOCUMENTS_REMINDER"
    );
  }, [stageCatalog, track, stageCode, applicant]);

  const sendStageMutation = useMutation({
    mutationFn: () =>
      ldiApi.sendStageUpdate(applicantId, {
        track,
        stage_code: stageCode,
        subject: emailSubject || undefined,
        message_body: emailBody || undefined,
        include_missing_checklist: includeMissing,
        update_applicant_status: updateStatusFlag,
      }),
    onSuccess: (res) => {
      setStatusBanner(
        `Client notified at ${res.recipient_email} (${res.stage_label} · ${res.delivery_status}).`
      );
      refreshAll();
    },
  });

  const refreshAll = () => {
    qc.invalidateQueries({ queryKey: ["applicant", applicantId] });
    qc.invalidateQueries({ queryKey: ["processed-documents"] });
    qc.invalidateQueries({ queryKey: ["processing-batches"] });
    qc.invalidateQueries({ queryKey: ["applicants"] });
    qc.invalidateQueries({ queryKey: ["dashboard-metrics"] });
  };

  const correctMutation = useMutation({
    mutationFn: ({ docId, payload }: { docId: string; payload: Record<string, unknown> }) =>
      ldiApi.correctClassification(docId, payload),
    onSuccess: refreshAll,
  });

  const approveMutation = useMutation({
    mutationFn: ldiApi.approveDocument,
    onSuccess: refreshAll,
  });

  const reprocessMutation = useMutation({
    mutationFn: ldiApi.reprocessDocument,
    onSuccess: refreshAll,
  });

  const bulkApproveMutation = useMutation({
    mutationFn: () => ldiApi.bulkApprove(applicantId, 0.9),
    onSuccess: (res) => {
      setStatusBanner(`Bulk approved ${res.approved_count} high-confidence documents.`);
      refreshAll();
    },
  });

  const deleteApplicantMutation = useMutation({
    mutationFn: () => ldiApi.archiveApplicant(applicantId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["applicants"] });
      qc.invalidateQueries({ queryKey: ["dashboard-metrics"] });
      router.push("/applicants");
    },
  });

  const deleteDocMutation = useMutation({
    mutationFn: ldiApi.deleteDocument,
    onSuccess: (res, docId) => {
      setSelectedDocIds((prev) => prev.filter((id) => id !== docId));
      if (previewDoc?.id === docId) setPreviewDoc(null);
      setStatusBanner(res.message);
      refreshAll();
    },
  });

  const batchDeleteDocsMutation = useMutation({
    mutationFn: ldiApi.batchDeleteDocuments,
    onSuccess: (res) => {
      setSelectedDocIds([]);
      setPreviewDoc(null);
      setStatusBanner(res.message);
      refreshAll();
    },
  });

  const deleteExportMutation = useMutation({
    mutationFn: ldiApi.deleteExport,
    onSuccess: (res, id) => {
      setSelectedExportIds((prev) => prev.filter((x) => x !== id));
      setStatusBanner(res.message);
      refreshAll();
    },
  });

  const batchDeleteExportsMutation = useMutation({
    mutationFn: ldiApi.batchDeleteExports,
    onSuccess: (res) => {
      setSelectedExportIds([]);
      setStatusBanner(res.message);
      refreshAll();
    },
  });

  const exportMutation = useMutation({
    mutationFn: () => ldiApi.generateExport(applicantId),
    onSuccess: async (res) => {
      setStatusBanner(`Organised ZIP built (${res.approved_doc_count} approved documents). Downloading...`);
      refreshAll();
      await downloadAuthorizedFile(
        res.download_url,
        `${applicant?.application_reference || applicantId}_ORGANISED_DOCUMENTS.zip`
      );
    },
  });

  const token = getStoredTokens().access;
  const allDocIds = (applicant?.documents || []).map((d) => d.id);
  const allDocsSelected = allDocIds.length > 0 && allDocIds.every((id) => selectedDocIds.includes(id));
  const allExportIds = (applicant?.exports || []).map((e) => e.id);
  const allExportsSelected =
    allExportIds.length > 0 && allExportIds.every((id) => selectedExportIds.includes(id));

  return (
    <AppShell
      title={applicant ? `${applicant.full_name} — ${applicant.application_reference}` : "Applicant Workspace"}
      subtitle={
        applicant
          ? `${applicant.destination.name} · ${applicant.purpose.name} · ${applicant.category.name}`
          : "Loading applicant record..."
      }
      actions={
        applicant ? (
          <>
            <Link
              href={`/processing?applicantId=${applicant.id}`}
              className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg border border-slate-300 bg-white text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              <UploadCloud className="h-4 w-4" />
              Upload Documents
            </Link>
            <button
              onClick={() => bulkApproveMutation.mutate()}
              disabled={bulkApproveMutation.isPending}
              className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg bg-navy text-white text-sm font-medium hover:bg-navy-700 disabled:opacity-60"
            >
              <CheckCheck className="h-4 w-4" />
              Bulk Approve High-Confidence
            </button>
            <button
              onClick={() =>
                downloadAuthorizedFile(
                  `/api/applicants/${applicant.id}/report`,
                  `PROCESSING_REPORT_${applicant.application_reference}.pdf`
                )
              }
              className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg border border-slate-300 bg-white text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              <FileText className="h-4 w-4" />
              PDF Report
            </button>
            <button
              onClick={() => exportMutation.mutate()}
              disabled={exportMutation.isPending}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-brand text-white text-sm font-medium hover:bg-brand-light disabled:opacity-60"
            >
              <FolderArchive className="h-4 w-4" />
              {exportMutation.isPending ? "Packaging..." : "Download Organised Folder"}
            </button>
            {canDelete && (
              <button
                type="button"
                onClick={() => deleteApplicantMutation.mutate()}
                disabled={deleteApplicantMutation.isPending}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg border border-red-200 bg-red-50 text-red-700 text-sm font-medium hover:bg-red-100 disabled:opacity-60"
              >
                <Trash2 className="h-4 w-4" />
                {deleteApplicantMutation.isPending ? "Deleting..." : "Delete Applicant"}
              </button>
            )}
          </>
        ) : null
      }
    >
      <div className="mb-4">
        <Link href="/applicants" className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-500 hover:text-navy">
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to Applicants
        </Link>
      </div>

      {statusBanner && (
        <div className="mb-4 rounded-xl bg-emerald-50 border border-emerald-200 px-4 py-3 text-sm text-emerald-800 flex items-center justify-between">
          <span>{statusBanner}</span>
          <button onClick={() => setStatusBanner(null)} className="text-xs underline">
            Dismiss
          </button>
        </div>
      )}

      {isLoading || !applicant ? (
        <div className="h-48 rounded-xl bg-white border border-slate-200 animate-pulse" />
      ) : (
        <div className="space-y-6">
          {/* Applicant Overview Card */}
          <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm grid grid-cols-2 md:grid-cols-5 gap-4 text-sm">
            <div>
              <div className="text-xs text-slate-500">Email</div>
              <div className="font-medium text-slate-900 truncate">{applicant.email}</div>
            </div>
            <div>
              <div className="text-xs text-slate-500">Phone</div>
              <div className="font-medium text-slate-900">{applicant.phone_number}</div>
            </div>
            <div>
              <div className="text-xs text-slate-500">Nationality</div>
              <div className="font-medium text-slate-900">{applicant.nationality}</div>
            </div>
            <div>
              <div className="text-xs text-slate-500">Passport (Masked)</div>
              <div className="font-mono text-xs font-semibold text-slate-800">
                {applicant.passport_number_masked || "Not provided"}
              </div>
            </div>
            <div>
              <div className="text-xs text-slate-500">Application Status</div>
              <span
                className={`inline-block mt-0.5 px-2.5 py-0.5 rounded-full text-xs font-medium border ${statusColorClasses(applicant.status)}`}
              >
                {applicant.status}
              </span>
            </div>
          </div>

          {/* Client Stage Updates & Real-Time Email Reminders */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-200 flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <BellRing className="h-4 w-4 text-brand" />
                <div>
                  <h2 className="text-sm font-semibold text-navy">
                    Client Stage Progression &amp; Real-Time Email Reminders
                  </h2>
                  <p className="text-xs text-slate-500">
                    Update admission, visa processing, or document milestones and notify{" "}
                    <span className="font-medium text-slate-700">{applicant.email}</span> immediately.
                  </p>
                </div>
              </div>
              {applicant.current_stage_label && (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-xs font-semibold text-emerald-800">
                  Current Milestone: {applicant.current_stage_label}
                </span>
              )}
            </div>

            <div className="p-5 grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="space-y-3">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-slate-700 mb-1">
                      Notification Track
                    </label>
                    <select
                      value={track}
                      onChange={(e) => {
                        const nextTrack = e.target.value;
                        setTrack(nextTrack);
                        const firstOpt = stageCatalog?.[nextTrack]?.[0];
                        if (firstOpt) setStageCode(firstOpt.code);
                      }}
                      className="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white"
                    >
                      <option value="DOCUMENT_REMINDER">Full Package &amp; Document Reminders</option>
                      <option value="ADMISSION">Admission Approval Milestones</option>
                      <option value="VISA_PROCESSING">Visa Processing Milestones</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-700 mb-1">
                      Stage Milestone
                    </label>
                    <select
                      value={stageCode}
                      onChange={(e) => setStageCode(e.target.value)}
                      className="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white"
                    >
                      {(stageCatalog?.[track] || []).map((opt) => (
                        <option key={opt.code} value={opt.code}>
                          {opt.label}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">
                    Email Subject
                  </label>
                  <input
                    value={emailSubject}
                    onChange={(e) => setEmailSubject(e.target.value)}
                    placeholder="Subject line sent to client..."
                    className="w-full px-3 py-2 text-xs rounded-lg border border-slate-300"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">
                    Message to Client
                  </label>
                  <textarea
                    rows={4}
                    value={emailBody}
                    onChange={(e) => setEmailBody(e.target.value)}
                    className="w-full px-3 py-2 text-xs rounded-lg border border-slate-300"
                  />
                </div>

                <div className="flex flex-wrap items-center gap-4 text-xs text-slate-700">
                  <label className="inline-flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={includeMissing}
                      onChange={(e) => setIncludeMissing(e.target.checked)}
                    />
                    Include outstanding missing checklist documents
                  </label>
                  <label className="inline-flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={updateStatusFlag}
                      onChange={(e) => setUpdateStatusFlag(e.target.checked)}
                    />
                    Update applicant status automatically
                  </label>
                </div>

                <button
                  type="button"
                  onClick={() => sendStageMutation.mutate()}
                  disabled={sendStageMutation.isPending || !emailSubject.trim()}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-brand text-white text-xs font-medium hover:bg-brand-light disabled:opacity-50"
                >
                  <Send className="h-3.5 w-3.5" />
                  {sendStageMutation.isPending
                    ? "Sending Update..."
                    : "Update Stage & Send Email Reminder"}
                </button>
              </div>

              <div className="border-t lg:border-t-0 lg:border-l border-slate-200 pt-4 lg:pt-0 lg:pl-6">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-3 flex items-center gap-1.5">
                  <Mail className="h-3.5 w-3.5" />
                  Client Notification &amp; Reminder History ({applicant.stage_updates?.length || 0})
                </h3>
                {!applicant.stage_updates || applicant.stage_updates.length === 0 ? (
                  <div className="rounded-lg bg-slate-50 border border-slate-200 p-4 text-xs text-slate-500">
                    No client email reminders have been dispatched yet. Select a stage on the left to notify the applicant in real time.
                  </div>
                ) : (
                  <div className="space-y-2.5 max-h-72 overflow-y-auto pr-1">
                    {applicant.stage_updates.map((upd) => (
                      <div
                        key={upd.id}
                        className="rounded-lg border border-slate-200 bg-slate-50/70 p-3 text-xs space-y-1"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-semibold text-navy">{upd.stage_label}</span>
                          <span
                            className={`px-2 py-0.5 rounded-full text-[10px] font-medium border ${
                              upd.delivery_status.startsWith("SENT")
                                ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                                : upd.delivery_status === "FAILED"
                                ? "bg-red-50 text-red-700 border-red-200"
                                : "bg-amber-50 text-amber-700 border-amber-200"
                            }`}
                          >
                            {upd.delivery_status} ({upd.delivery_provider})
                          </span>
                        </div>
                        <div className="text-slate-700 font-medium truncate">{upd.subject}</div>
                        <div className="text-[11px] text-slate-500">
                          To {upd.recipient_email} · By {upd.sent_by_name || "Officer"} ·{" "}
                          {formatDateTime(upd.created_at)}
                        </div>
                        {upd.delivery_detail && (
                          <div className="text-[11px] text-slate-500 italic">{upd.delivery_detail}</div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Configured Requirements Checklist */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between">
              <div>
                <h2 className="text-sm font-semibold text-navy">
                  Configured Requirements Checklist &amp; Completeness
                </h2>
                <p className="text-xs text-slate-500">
                  Distinguishes automatic detection, quality screening, manual review, and officer approval.
                </p>
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 uppercase">
                  <tr>
                    <th className="px-4 py-2.5">#</th>
                    <th className="px-4 py-2.5">Required Document</th>
                    <th className="px-4 py-2.5">Level</th>
                    <th className="px-4 py-2.5">Checklist Status</th>
                    <th className="px-4 py-2.5">Verification Stage</th>
                    <th className="px-4 py-2.5">Matched / Output Filename</th>
                    <th className="px-4 py-2.5">Notes / Warnings</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {applicant.checklist.map((item) => (
                    <tr key={item.id}>
                      <td className="px-4 py-2.5 font-mono text-slate-400">
                        {String(item.display_order).padStart(2, "0")}
                      </td>
                      <td className="px-4 py-2.5 font-medium text-slate-900">
                        {item.document_type_name}
                        {item.condition_explanation && (
                          <p className="text-[11px] text-slate-500 font-normal">
                            {item.condition_explanation}
                          </p>
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-slate-600">{item.requirement_level}</td>
                      <td className="px-4 py-2.5">
                        <span
                          className={`px-2 py-0.5 rounded-full font-medium border ${statusColorClasses(item.status)}`}
                        >
                          {item.status}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-slate-600">{item.verification_stage}</td>
                      <td className="px-4 py-2.5">
                        {item.generated_filename ? (
                          <span className="font-mono text-brand font-medium">
                            {item.generated_filename}
                          </span>
                        ) : (
                          <span className="text-slate-400">—</span>
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-amber-700">
                        {item.quality_issues.length > 0 ? item.quality_issues.join("; ") : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Classification Review Interface */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-200 flex flex-wrap items-center justify-between gap-2">
              <div>
                <h2 className="text-sm font-semibold text-navy">
                  Uploaded Documents &amp; AI Classification Review ({applicant.documents.length})
                </h2>
                <p className="text-xs text-slate-500">
                  Original files are preserved immutably. Override uncertain AI classifications or exclude irrelevant files before export.
                </p>
              </div>
              {canDelete && selectedDocIds.length > 0 && (
                <button
                  type="button"
                  onClick={() => batchDeleteDocsMutation.mutate(selectedDocIds)}
                  disabled={batchDeleteDocsMutation.isPending}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-600 text-white text-xs font-medium hover:bg-red-700 disabled:opacity-60"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  {batchDeleteDocsMutation.isPending
                    ? "Deleting..."
                    : `Delete Selected (${selectedDocIds.length})`}
                </button>
              )}
            </div>

            {applicant.documents.length === 0 ? (
              <div className="p-8 text-center text-sm text-slate-500">
                No documents uploaded yet. Click <strong>Upload Documents</strong> above to upload PDFs, images, Word docs, or ZIPs.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 uppercase">
                    <tr>
                      {canDelete && (
                        <th className="px-4 py-2.5 w-10">
                          <input
                            type="checkbox"
                            aria-label="Select All Uploaded Documents"
                            checked={allDocsSelected}
                            onChange={() => setSelectedDocIds(allDocsSelected ? [] : allDocIds)}
                            className="rounded border-slate-300"
                          />
                        </th>
                      )}
                      <th className="px-4 py-2.5">Original Filename</th>
                      <th className="px-4 py-2.5">AI Type (Editable)</th>
                      <th className="px-4 py-2.5">Confidence</th>
                      <th className="px-4 py-2.5">Extracted Metadata &amp; Issues</th>
                      <th className="px-4 py-2.5">Proposed Filename</th>
                      <th className="px-4 py-2.5">Review Status</th>
                      <th className="px-4 py-2.5 text-right">Officer Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {applicant.documents.map((doc) => {
                      const cls = doc.classification;
                      return (
                        <tr key={doc.id} className={doc.is_excluded ? "bg-slate-50 opacity-60" : ""}>
                          {canDelete && (
                            <td className="px-4 py-3">
                              <input
                                type="checkbox"
                                aria-label={`Select ${doc.original_filename}`}
                                checked={selectedDocIds.includes(doc.id)}
                                onChange={() =>
                                  setSelectedDocIds((prev) =>
                                    prev.includes(doc.id)
                                      ? prev.filter((id) => id !== doc.id)
                                      : [...prev, doc.id]
                                  )
                                }
                                className="rounded border-slate-300"
                              />
                            </td>
                          )}
                          <td className="px-4 py-3">
                            <div className="font-medium text-slate-900">{doc.original_filename}</div>
                            <div className="text-[11px] text-slate-500">
                              {formatBytes(doc.file_size_bytes)} · {doc.ingestion_type} · {doc.page_count}p
                            </div>
                            {doc.is_duplicate && (
                              <span className="inline-flex items-center gap-1 mt-1 px-1.5 py-0.5 rounded bg-amber-100 text-amber-800 text-[10px] font-medium">
                                <AlertTriangle className="h-3 w-3" /> Duplicate Flagged
                              </span>
                            )}
                          </td>
                          <td className="px-4 py-3">
                            {cls ? (
                              <select
                                value={cls.predicted_type_code}
                                onChange={(e) =>
                                  correctMutation.mutate({
                                    docId: doc.id,
                                    payload: {
                                      action: "CHANGE_TYPE",
                                      document_type_code: e.target.value,
                                      notes: "Officer reassigned classification type",
                                    },
                                  })
                                }
                                className="px-2 py-1.5 rounded border border-slate-300 bg-white text-xs font-medium max-w-[180px]"
                              >
                                {docTypes.map((dt) => (
                                  <option key={dt.id} value={dt.code}>
                                    {dt.name}
                                  </option>
                                ))}
                              </select>
                            ) : (
                              <span className="text-slate-400">{doc.processing_status}</span>
                            )}
                          </td>
                          <td className="px-4 py-3">
                            {cls ? (
                              <span
                                className={`px-2 py-0.5 rounded-full font-semibold border ${statusColorClasses(cls.confidence_tier)}`}
                              >
                                {Math.round(cls.confidence * 100)}% ({cls.confidence_tier})
                              </span>
                            ) : (
                              "—"
                            )}
                          </td>
                          <td className="px-4 py-3 max-w-[260px]">
                            {cls && (
                              <div className="space-y-0.5">
                                {cls.extracted_applicant_name && (
                                  <div>
                                    Name: <strong>{cls.extracted_applicant_name}</strong>
                                    {cls.has_name_mismatch && (
                                      <span className="ml-1 text-red-600 font-semibold">(Mismatch!)</span>
                                    )}
                                  </div>
                                )}
                                {cls.issuing_authority && (
                                  <div className="text-slate-500 truncate">
                                    Issuer: {cls.issuing_authority}
                                  </div>
                                )}
                                {cls.possible_issues.map((iss, idx) => (
                                  <div key={idx} className="text-amber-700 text-[11px]">
                                    • {iss}
                                  </div>
                                ))}
                              </div>
                            )}
                          </td>
                          <td className="px-4 py-3 font-mono text-[11px] text-navy">
                            {doc.is_excluded ? (
                              <span className="line-through text-slate-400">Excluded</span>
                            ) : (
                              doc.proposed_filename || "—"
                            )}
                          </td>
                          <td className="px-4 py-3">
                            <span
                              className={`px-2 py-0.5 rounded-full font-medium border ${statusColorClasses(
                                doc.is_excluded ? "EXCLUDED" : cls?.status || doc.processing_status
                              )}`}
                            >
                              {doc.is_excluded ? "EXCLUDED" : cls?.status || doc.processing_status}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-right space-x-1 whitespace-nowrap">
                            <button
                              onClick={() => setPreviewDoc(doc)}
                              title="Preview Document"
                              className="p-1.5 rounded border border-slate-200 text-slate-600 hover:bg-slate-100"
                            >
                              <Eye className="h-3.5 w-3.5" />
                            </button>
                            <button
                              onClick={() =>
                                downloadAuthorizedFile(
                                  `/api/documents/${doc.id}/preview?download=true`,
                                  doc.proposed_filename || doc.original_filename
                                )
                              }
                              title={`Download as ${doc.proposed_filename || doc.original_filename}`}
                              className="p-1.5 rounded border border-slate-200 text-navy hover:bg-slate-100"
                            >
                              <Download className="h-3.5 w-3.5" />
                            </button>
                            {!doc.is_excluded && (
                              <button
                                onClick={() => approveMutation.mutate(doc.id)}
                                title="Approve for Export"
                                className="p-1.5 rounded border border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
                              >
                                <Check className="h-3.5 w-3.5" />
                              </button>
                            )}
                            <button
                              onClick={() => reprocessMutation.mutate(doc.id)}
                              title="Reprocess Document"
                              className="p-1.5 rounded border border-slate-200 text-slate-600 hover:bg-slate-100"
                            >
                              <RefreshCw className="h-3.5 w-3.5" />
                            </button>
                            <button
                              onClick={() =>
                                correctMutation.mutate({
                                  docId: doc.id,
                                  payload: {
                                    action: doc.is_excluded ? "INCLUDE" : "EXCLUDE",
                                    notes: doc.is_excluded ? "Re-included by officer" : "Excluded by officer",
                                  },
                                })
                              }
                              title={doc.is_excluded ? "Restore to Package" : "Exclude from Package"}
                              className="p-1.5 rounded border border-amber-200 bg-amber-50 text-amber-700 hover:bg-amber-100"
                            >
                              <XCircle className="h-3.5 w-3.5" />
                            </button>
                            {canDelete && (
                              <button
                                type="button"
                                onClick={() => deleteDocMutation.mutate(doc.id)}
                                title="Delete Document"
                                className="p-1.5 rounded border border-red-200 bg-red-50 text-red-700 hover:bg-red-100"
                              >
                                <Trash2 className="h-3.5 w-3.5" />
                              </button>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Export History */}
          {applicant.exports.length > 0 && (
            <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
              <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
                <h3 className="text-sm font-semibold text-navy">
                  Generated Document Packages ({applicant.exports.length})
                </h3>
                {canDelete && (
                  <div className="flex items-center gap-2.5">
                    <label className="inline-flex items-center gap-1 text-xs text-slate-600 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={allExportsSelected}
                        onChange={() =>
                          setSelectedExportIds(allExportsSelected ? [] : allExportIds)
                        }
                        className="rounded border-slate-300"
                      />
                      Select All
                    </label>
                    {selectedExportIds.length > 0 && (
                      <button
                        type="button"
                        onClick={() => batchDeleteExportsMutation.mutate(selectedExportIds)}
                        disabled={batchDeleteExportsMutation.isPending}
                        className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-red-600 text-white text-xs font-medium hover:bg-red-700"
                      >
                        <Trash2 className="h-3 w-3" />
                        Delete Selected ({selectedExportIds.length})
                      </button>
                    )}
                  </div>
                )}
              </div>
              <div className="space-y-2">
                {applicant.exports.map((exp) => (
                  <div
                    key={exp.id}
                    className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-lg bg-slate-50 border border-slate-200 text-xs"
                  >
                    <div className="flex items-center gap-2.5 min-w-0 flex-1">
                      {canDelete && (
                        <input
                          type="checkbox"
                          aria-label={`Select export ${exp.folder_root}`}
                          checked={selectedExportIds.includes(exp.id)}
                          onChange={() =>
                            setSelectedExportIds((prev) =>
                              prev.includes(exp.id)
                                ? prev.filter((id) => id !== exp.id)
                                : [...prev, exp.id]
                            )
                          }
                          className="rounded border-slate-300 shrink-0"
                        />
                      )}
                      <div className="min-w-0">
                        <div className="font-mono font-semibold text-navy truncate">{exp.folder_root}</div>
                        <div className="text-slate-500">
                          {exp.approved_doc_count} approved docs · {exp.missing_doc_count} missing items
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() =>
                          downloadAuthorizedFile(
                            exp.download_url,
                            `${applicant.application_reference}_ORGANISED_DOCUMENTS.zip`
                          )
                        }
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-brand text-white font-medium hover:bg-brand-light"
                      >
                        <Download className="h-3.5 w-3.5" />
                        Download ZIP
                      </button>
                      {canDelete && (
                        <button
                          type="button"
                          onClick={() => deleteExportMutation.mutate(exp.id)}
                          title="Delete Export Package"
                          className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-red-200 bg-red-50 text-red-700 font-medium hover:bg-red-100"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                          Delete
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Document Preview Modal */}
      {previewDoc && (
        <div className="fixed inset-0 z-50 bg-slate-950/60 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-4xl w-full h-[85vh] flex flex-col overflow-hidden shadow-2xl">
            <div className="px-5 py-3 border-b border-slate-200 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-navy">
                  {previewDoc.proposed_filename || previewDoc.original_filename}
                </h3>
                <p className="text-xs text-slate-500">
                  Original: {previewDoc.original_filename} · {previewDoc.detected_mime_type} ·{" "}
                  {previewDoc.extraction_method || "Raw Preview"}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() =>
                    downloadAuthorizedFile(
                      `/api/documents/${previewDoc.id}/preview?download=true`,
                      previewDoc.proposed_filename || previewDoc.original_filename
                    )
                  }
                  className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg bg-brand text-white text-xs font-medium hover:bg-brand-light"
                >
                  <Download className="h-3.5 w-3.5" />
                  Download Renamed
                </button>
                {canDelete && (
                  <button
                    type="button"
                    onClick={() => deleteDocMutation.mutate(previewDoc.id)}
                    disabled={deleteDocMutation.isPending}
                    className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg border border-red-200 bg-red-50 text-red-700 text-xs font-medium hover:bg-red-100"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                    Delete
                  </button>
                )}
                <button
                  onClick={() => setPreviewDoc(null)}
                  className="px-3 py-1 rounded-lg border border-slate-300 text-xs font-medium"
                >
                  Close
                </button>
              </div>
            </div>
            <div className="flex-1 grid md:grid-cols-3 min-h-0">
              <div className="md:col-span-2 bg-slate-100 h-full">
                <iframe
                  src={`${API_BASE_URL}${previewDoc.preview_url}?token=${encodeURIComponent(token || "")}`}
                  className="w-full h-full border-0"
                  title="Document Preview"
                />
              </div>
              <div className="p-4 border-l border-slate-200 overflow-y-auto space-y-3 text-xs">
                <div>
                  <div className="font-semibold text-navy mb-1">AI Reasoning</div>
                  <p className="text-slate-600">
                    {previewDoc.classification?.classification_reason || "Not classified yet."}
                  </p>
                </div>
                <div>
                  <div className="font-semibold text-navy mb-1">Extracted Text Preview</div>
                  <pre className="whitespace-pre-wrap bg-slate-50 p-2.5 rounded-lg border border-slate-200 text-[11px] text-slate-700">
                    {previewDoc.extracted_text_preview || "No text extracted."}
                  </pre>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}
