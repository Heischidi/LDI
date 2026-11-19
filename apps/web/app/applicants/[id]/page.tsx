"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowLeft,
  Check,
  CheckCheck,
  Download,
  Eye,
  FileText,
  FolderArchive,
  RefreshCw,
  UploadCloud,
  XCircle,
} from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { API_BASE_URL, downloadAuthorizedFile, getStoredTokens, ldiApi } from "@/lib/api-client";
import { formatBytes, statusColorClasses } from "@/lib/utils";
import type { DocumentRecord } from "@/types";

export default function ApplicantDetailPage() {
  const params = useParams<{ id: string }>();
  const applicantId = params.id;
  const qc = useQueryClient();

  const [previewDoc, setPreviewDoc] = useState<DocumentRecord | null>(null);
  const [statusBanner, setStatusBanner] = useState<string | null>(null);

  const { data: applicant, isLoading } = useQuery({
    queryKey: ["applicant", applicantId],
    queryFn: () => ldiApi.getApplicant(applicantId),
    refetchInterval: (q) =>
      q.state.data?.batches?.some((b) => ["QUEUED", "PROCESSING"].includes(b.status))
        ? 2500
        : false,
  });

  const { data: docTypes = [] } = useQuery({
    queryKey: ["document-types"],
    queryFn: ldiApi.listDocumentTypes,
  });

  const refreshAll = () => {
    qc.invalidateQueries({ queryKey: ["applicant", applicantId] });
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
            <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between">
              <div>
                <h2 className="text-sm font-semibold text-navy">
                  Uploaded Documents &amp; AI Classification Review ({applicant.documents.length})
                </h2>
                <p className="text-xs text-slate-500">
                  Original files are preserved immutably. Override uncertain AI classifications or exclude irrelevant files before export.
                </p>
              </div>
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
                              className="p-1.5 rounded border border-red-200 bg-red-50 text-red-700 hover:bg-red-100"
                            >
                              <XCircle className="h-3.5 w-3.5" />
                            </button>
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
              <h3 className="text-sm font-semibold text-navy mb-3">Generated Document Packages</h3>
              <div className="space-y-2">
                {applicant.exports.map((exp) => (
                  <div
                    key={exp.id}
                    className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-lg bg-slate-50 border border-slate-200 text-xs"
                  >
                    <div>
                      <div className="font-mono font-semibold text-navy">{exp.folder_root}</div>
                      <div className="text-slate-500">
                        {exp.approved_doc_count} approved docs · {exp.missing_doc_count} missing items
                      </div>
                    </div>
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
                <h3 className="text-sm font-semibold text-navy">{previewDoc.original_filename}</h3>
                <p className="text-xs text-slate-500">
                  {previewDoc.detected_mime_type} · {previewDoc.extraction_method || "Raw Preview"}
                </p>
              </div>
              <button
                onClick={() => setPreviewDoc(null)}
                className="px-3 py-1 rounded-lg border border-slate-300 text-xs font-medium"
              >
                Close
              </button>
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
