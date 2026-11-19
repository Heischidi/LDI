"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Download, FileSpreadsheet, FileText } from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { downloadAuthorizedFile, ldiApi } from "@/lib/api-client";

export default function ReportsPage() {
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  const queryParams = new URLSearchParams({
    ...(startDate ? { start_date: startDate } : {}),
    ...(endDate ? { end_date: endDate } : {}),
  }).toString();

  const { data, isLoading } = useQuery({
    queryKey: ["reports-summary", queryParams],
    queryFn: () => ldiApi.getReportSummary(queryParams ? `?${queryParams}` : ""),
  });

  return (
    <AppShell
      title="Reports & Analytics"
      subtitle="Operational throughput, AI classification accuracy, missing document trends, and officer productivity."
      actions={
        <>
          <button
            onClick={() =>
              downloadAuthorizedFile(
                `/api/reports/export/csv${queryParams ? `?${queryParams}` : ""}`,
                "ldi_analytics_report.csv"
              )
            }
            className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg border border-slate-300 bg-white text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            <FileSpreadsheet className="h-4 w-4" />
            Export CSV
          </button>
          <button
            onClick={() =>
              downloadAuthorizedFile(
                `/api/reports/export/pdf${queryParams ? `?${queryParams}` : ""}`,
                "ldi_analytics_report.pdf"
              )
            }
            className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg bg-navy text-white text-sm font-medium hover:bg-navy-700"
          >
            <FileText className="h-4 w-4" />
            Export PDF
          </button>
        </>
      }
    >
      {/* Date Filter */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 mb-6 flex flex-wrap items-center gap-4 shadow-sm text-sm">
        <div className="flex items-center gap-2">
          <label className="text-xs font-medium text-slate-600">From:</label>
          <input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="px-3 py-1.5 rounded-lg border border-slate-300 text-xs"
          />
        </div>
        <div className="flex items-center gap-2">
          <label className="text-xs font-medium text-slate-600">To:</label>
          <input
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            className="px-3 py-1.5 rounded-lg border border-slate-300 text-xs"
          />
        </div>
        {(startDate || endDate) && (
          <button
            onClick={() => {
              setStartDate("");
              setEndDate("");
            }}
            className="text-xs text-brand font-medium hover:underline"
          >
            Clear Filter
          </button>
        )}
      </div>

      {isLoading || !data ? (
        <div className="h-48 rounded-xl bg-white border border-slate-200 animate-pulse" />
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
            {[
              { label: "Applicants Processed", val: data.total_applicants_processed },
              { label: "Documents Classified", val: data.total_documents_classified },
              { label: "Avg. Processing Time", val: `${data.average_processing_seconds}s` },
              { label: "AI Correction Rate", val: `${data.ai_correction_rate_percent}%` },
              { label: "Failure Rate", val: `${data.processing_failure_rate_percent}%` },
            ].map((m) => (
              <div key={m.label} className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
                <div className="text-xs text-slate-500">{m.label}</div>
                <div className="text-2xl font-bold text-navy mt-2 tabular-nums">{m.val}</div>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
            <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
              <h3 className="text-sm font-semibold text-navy mb-3">Common Destinations</h3>
              <div className="space-y-2 text-xs">
                {data.common_destinations.map((d) => (
                  <div key={d.name} className="flex justify-between py-1.5 border-b border-slate-100">
                    <span>{d.name}</span>
                    <strong className="text-navy">{d.count}</strong>
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
              <h3 className="text-sm font-semibold text-navy mb-3">Most Missing Documents</h3>
              <div className="space-y-2 text-xs">
                {data.most_frequently_missing_documents.map((m) => (
                  <div
                    key={m.document_type}
                    className="flex justify-between py-1.5 border-b border-slate-100"
                  >
                    <span>{m.document_type}</span>
                    <strong className="text-amber-700">{m.count}</strong>
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
              <h3 className="text-sm font-semibold text-navy mb-3">Officer Upload Statistics</h3>
              <div className="space-y-2 text-xs">
                {data.officer_processing_statistics.map((o) => (
                  <div key={o.email} className="flex justify-between py-1.5 border-b border-slate-100">
                    <span>{o.officer_name}</span>
                    <strong className="text-brand">{o.uploads_count} docs</strong>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}
