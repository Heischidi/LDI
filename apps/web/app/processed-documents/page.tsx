"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Download, Eye, FileCheck2, Pencil, Trash2, X } from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { useAuth } from "@/hooks/use-auth";
import { downloadAuthorizedFile, ldiApi } from "@/lib/api-client";
import { statusColorClasses } from "@/lib/utils";

export default function ProcessedDocumentsPage() {
  const { hasRole } = useAuth();
  const qc = useQueryClient();
  const canDelete = hasRole("SUPER_ADMIN", "ADMIN", "OFFICER");

  const [approvedOnly, setApprovedOnly] = useState(false);
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);
  const [editingDoc, setEditingDoc] = useState<{
    id: string;
    original_filename: string;
    generated_filename?: string | null;
    predicted_type_code?: string | null;
  } | null>(null);
  const [editTypeCode, setEditTypeCode] = useState("");
  const [editCustomFilename, setEditCustomFilename] = useState("");
  const [editApplicantName, setEditApplicantName] = useState("");
  const [editDocNumber, setEditDocNumber] = useState("");
  const [editIssuer, setEditIssuer] = useState("");
  const [editNotes, setEditNotes] = useState("");

  const { data: docs = [], isLoading } = useQuery({
    queryKey: ["processed-documents", approvedOnly],
    queryFn: () => ldiApi.listProcessedDocuments(approvedOnly ? "?approved_only=true" : ""),
  });

  const { data: docTypes = [] } = useQuery({
    queryKey: ["document-types"],
    queryFn: ldiApi.listDocumentTypes,
  });

  const refreshDocs = () => {
    qc.invalidateQueries({ queryKey: ["processed-documents"] });
    qc.invalidateQueries({ queryKey: ["applicant"] });
    qc.invalidateQueries({ queryKey: ["dashboard-metrics"] });
  };

  const editDocMutation = useMutation({
    mutationFn: () => {
      if (!editingDoc) throw new Error("No document selected.");
      return ldiApi.correctClassification(editingDoc.id, {
        action: editTypeCode && editTypeCode !== editingDoc.predicted_type_code ? "CHANGE_TYPE" : "CORRECT_METADATA",
        document_type_code: editTypeCode || undefined,
        custom_filename: editCustomFilename.trim() || undefined,
        extracted_applicant_name: editApplicantName.trim() || undefined,
        document_number: editDocNumber.trim() || undefined,
        issuing_authority: editIssuer.trim() || undefined,
        notes: editNotes.trim() || "Edited in Processed Documents repository",
      });
    },
    onSuccess: () => {
      setEditingDoc(null);
      refreshDocs();
    },
  });

  const openEditModal = async (d: {
    id: string;
    original_filename: string;
    generated_filename?: string | null;
    predicted_type_code?: string | null;
  }) => {
    setEditingDoc(d);
    setEditTypeCode(d.predicted_type_code || "ADDITIONAL_DOCUMENT");
    setEditCustomFilename(d.generated_filename || d.original_filename);
    setEditApplicantName("");
    setEditDocNumber("");
    setEditIssuer("");
    setEditNotes("");
  };

  const deleteMutation = useMutation({
    mutationFn: ldiApi.deleteDocument,
    onSuccess: (_res, docId) => {
      setSelectedDocIds((prev) => prev.filter((id) => id !== docId));
      refreshDocs();
    },
  });

  const batchDeleteMutation = useMutation({
    mutationFn: ldiApi.batchDeleteDocuments,
    onSuccess: () => {
      setSelectedDocIds([]);
      refreshDocs();
    },
  });

  const visibleIds = docs.map((d) => d.id);
  const allSelected = visibleIds.length > 0 && visibleIds.every((id) => selectedDocIds.includes(id));

  return (
    <AppShell
      title="Processed Documents Repository"
      subtitle="Traceability mapping between immutable original filenames and standardized export folder paths."
      actions={
        <div className="flex flex-wrap items-center gap-2">
          {canDelete && selectedDocIds.length > 0 && (
            <button
              type="button"
              onClick={() => batchDeleteMutation.mutate(selectedDocIds)}
              disabled={batchDeleteMutation.isPending}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-red-600 text-white text-xs font-medium hover:bg-red-700 disabled:opacity-60"
            >
              <Trash2 className="h-3.5 w-3.5" />
              {batchDeleteMutation.isPending
                ? "Deleting..."
                : `Delete Selected (${selectedDocIds.length})`}
            </button>
          )}
          <label className="inline-flex items-center gap-2 text-xs font-medium text-slate-700 bg-white border border-slate-200 px-3 py-2 rounded-lg cursor-pointer">
            <input
              type="checkbox"
              checked={approvedOnly}
              onChange={(e) => setApprovedOnly(e.target.checked)}
              className="rounded border-slate-300"
            />
            Approved for Export Only
          </label>
        </div>
      }
    >
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 uppercase">
              <tr>
                {canDelete && (
                  <th className="px-4 py-3 w-10">
                    <input
                      type="checkbox"
                      aria-label="Select All Documents"
                      checked={allSelected}
                      onChange={() => setSelectedDocIds(allSelected ? [] : visibleIds)}
                      className="rounded border-slate-300"
                    />
                  </th>
                )}
                <th className="px-4 py-3">Applicant</th>
                <th className="px-4 py-3">Original Filename</th>
                <th className="px-4 py-3">Standardised Filename</th>
                <th className="px-4 py-3">Document Type</th>
                <th className="px-4 py-3">Confidence</th>
                <th className="px-4 py-3">Export Ready</th>
                <th className="px-4 py-3 text-right">Applicant File</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {isLoading && (
                <tr>
                  <td colSpan={canDelete ? 8 : 7} className="px-4 py-10 text-center text-slate-400">
                    Loading processed documents...
                  </td>
                </tr>
              )}
              {!isLoading && docs.length === 0 && (
                <tr>
                  <td colSpan={canDelete ? 8 : 7} className="px-4 py-12 text-center text-slate-500">
                    <FileCheck2 className="h-8 w-8 mx-auto text-slate-300 mb-2" />
                    No processed documents recorded yet.
                  </td>
                </tr>
              )}
              {docs.map((d) => (
                <tr key={d.id} className="hover:bg-slate-50/70">
                  {canDelete && (
                    <td className="px-4 py-3">
                      <input
                        type="checkbox"
                        aria-label={`Select ${d.original_filename}`}
                        checked={selectedDocIds.includes(d.id)}
                        onChange={() =>
                          setSelectedDocIds((prev) =>
                            prev.includes(d.id) ? prev.filter((id) => id !== d.id) : [...prev, d.id]
                          )
                        }
                        className="rounded border-slate-300"
                      />
                    </td>
                  )}
                  <td className="px-4 py-3">
                    <div className="font-semibold text-navy">{d.applicant_name}</div>
                    <div className="font-mono text-[11px] text-slate-500">
                      {d.application_reference}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-slate-700">{d.original_filename}</td>
                  <td className="px-4 py-3 font-mono text-brand font-medium">
                    {d.is_excluded ? (
                      <span className="text-slate-400 line-through">Excluded</span>
                    ) : (
                      d.generated_filename || "Pending naming"
                    )}
                  </td>
                  <td className="px-4 py-3">{d.predicted_type_code || "—"}</td>
                  <td className="px-4 py-3">
                    {d.confidence !== null && d.confidence !== undefined ? (
                      <span
                        className={`px-2 py-0.5 rounded-full border font-medium ${statusColorClasses(
                          d.confidence_tier || ""
                        )}`}
                      >
                        {Math.round(d.confidence * 100)}%
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {d.is_approved_for_export ? (
                      <span className="inline-flex items-center gap-1 text-emerald-700 font-medium">
                        <CheckCircle2 className="h-3.5 w-3.5" /> Yes
                      </span>
                    ) : (
                      <span className="text-slate-400">No</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right space-x-2 whitespace-nowrap">
                    <button
                      type="button"
                      onClick={() =>
                        downloadAuthorizedFile(
                          `/api/documents/${d.id}/preview?download=true`,
                          d.generated_filename || d.original_filename
                        )
                      }
                      className="inline-flex items-center gap-1 px-2.5 py-1 rounded border border-brand/30 text-brand hover:bg-emerald-50"
                    >
                      <Download className="h-3 w-3" />
                      Download
                    </button>
                    <Link
                      href={`/applicants/${d.applicant_id}`}
                      className="inline-flex items-center gap-1 px-2.5 py-1 rounded border border-slate-200 text-navy hover:bg-navy-50"
                    >
                      <Eye className="h-3 w-3" />
                      View
                    </Link>
                    {canDelete && (
                      <button
                        type="button"
                        onClick={() => openEditModal(d)}
                        className="inline-flex items-center gap-1 px-2.5 py-1 rounded border border-slate-200 text-navy hover:bg-slate-100"
                      >
                        <Pencil className="h-3 w-3" />
                        Edit
                      </button>
                    )}
                    {canDelete && (
                      <button
                        type="button"
                        onClick={() => deleteMutation.mutate(d.id)}
                        title="Delete Document"
                        className="inline-flex items-center gap-1 px-2 py-1 rounded border border-red-200 bg-red-50 text-red-700 hover:bg-red-100"
                      >
                        <Trash2 className="h-3 w-3" />
                        Delete
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {editingDoc && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-2xl w-full max-w-lg overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-navy">Edit Processed Document</h3>
                <p className="text-[11px] text-slate-500 mt-0.5">{editingDoc.original_filename}</p>
              </div>
              <button
                type="button"
                onClick={() => setEditingDoc(null)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                editDocMutation.mutate();
              }}
              className="p-5 space-y-3 text-xs"
            >
              <div>
                <label className="block font-medium text-slate-700 mb-1">Document Type</label>
                <select
                  value={editTypeCode}
                  onChange={(e) => setEditTypeCode(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 bg-white"
                >
                  {docTypes.map((dt) => (
                    <option key={dt.id} value={dt.code}>
                      {dt.name} ({dt.code})
                    </option>
                  ))}
                  <option value="ADDITIONAL_DOCUMENT">Additional Document (ADDITIONAL_DOCUMENT)</option>
                  <option value="UNKNOWN">Unknown / Unclassified (UNKNOWN)</option>
                </select>
              </div>
              <div>
                <label className="block font-medium text-slate-700 mb-1">
                  Standardized Export Filename
                </label>
                <input
                  value={editCustomFilename}
                  onChange={(e) => setEditCustomFilename(e.target.value)}
                  placeholder="01_International_Passport.pdf"
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 font-mono"
                />
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium text-slate-700 mb-1">
                    Extracted Applicant Name
                  </label>
                  <input
                    value={editApplicantName}
                    onChange={(e) => setEditApplicantName(e.target.value)}
                    placeholder="Optional update"
                    className="w-full px-3 py-2 rounded-lg border border-slate-300"
                  />
                </div>
                <div>
                  <label className="block font-medium text-slate-700 mb-1">Document Number</label>
                  <input
                    value={editDocNumber}
                    onChange={(e) => setEditDocNumber(e.target.value)}
                    placeholder="Optional update"
                    className="w-full px-3 py-2 rounded-lg border border-slate-300"
                  />
                </div>
              </div>
              <div>
                <label className="block font-medium text-slate-700 mb-1">Issuing Authority</label>
                <input
                  value={editIssuer}
                  onChange={(e) => setEditIssuer(e.target.value)}
                  placeholder="Optional update"
                  className="w-full px-3 py-2 rounded-lg border border-slate-300"
                />
              </div>
              <div>
                <label className="block font-medium text-slate-700 mb-1">Audit / Review Notes</label>
                <input
                  value={editNotes}
                  onChange={(e) => setEditNotes(e.target.value)}
                  placeholder="Reason for edit..."
                  className="w-full px-3 py-2 rounded-lg border border-slate-300"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2 border-t border-slate-200">
                <button
                  type="button"
                  onClick={() => setEditingDoc(null)}
                  className="px-3.5 py-2 rounded-lg border border-slate-300 text-slate-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={editDocMutation.isPending}
                  className="px-4 py-2 rounded-lg bg-brand text-white font-medium hover:bg-brand-light disabled:opacity-60"
                >
                  {editDocMutation.isPending ? "Saving..." : "Save Changes"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </AppShell>
  );
}
