"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Download, Eye, FileCheck2 } from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { downloadAuthorizedFile, ldiApi } from "@/lib/api-client";
import { statusColorClasses } from "@/lib/utils";

export default function ProcessedDocumentsPage() {
  const [approvedOnly, setApprovedOnly] = useState(false);

  const { data: docs = [], isLoading } = useQuery({
    queryKey: ["processed-documents", approvedOnly],
    queryFn: () => ldiApi.listProcessedDocuments(approvedOnly ? "?approved_only=true" : ""),
  });

  return (
    <AppShell
      title="Processed Documents Repository"
      subtitle="Traceability mapping between immutable original filenames and standardized export folder paths."
      actions={
        <label className="inline-flex items-center gap-2 text-xs font-medium text-slate-700 bg-white border border-slate-200 px-3 py-2 rounded-lg cursor-pointer">
          <input
            type="checkbox"
            checked={approvedOnly}
            onChange={(e) => setApprovedOnly(e.target.checked)}
            className="rounded border-slate-300"
          />
          Approved for Export Only
        </label>
      }
    >
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 uppercase">
              <tr>
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
                  <td colSpan={7} className="px-4 py-10 text-center text-slate-400">
                    Loading processed documents...
                  </td>
                </tr>
              )}
              {!isLoading && docs.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-slate-500">
                    <FileCheck2 className="h-8 w-8 mx-auto text-slate-300 mb-2" />
                    No processed documents recorded yet.
                  </td>
                </tr>
              )}
              {docs.map((d) => (
                <tr key={d.id} className="hover:bg-slate-50/70">
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
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </AppShell>
  );
}
