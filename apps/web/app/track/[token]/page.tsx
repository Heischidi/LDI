"use client";

import React from "react";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  CheckCircle2,
  Clock,
  FileCheck2,
  FolderCog,
  RefreshCw,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { ldiApi } from "@/lib/api-client";
import { formatDateTime, statusColorClasses } from "@/lib/utils";

function checklistBadgeClasses(status: string) {
  switch (status) {
    case "FOUND":
      return "bg-emerald-50 text-emerald-700 border-emerald-200";
    case "PENDING_REVIEW":
      return "bg-amber-50 text-amber-800 border-amber-200";
    case "MISSING":
    case "UNREADABLE":
    case "POTENTIALLY_INVALID":
      return "bg-red-50 text-red-700 border-red-200";
    default:
      return "bg-slate-100 text-slate-600 border-slate-200";
  }
}

export default function PublicClientTrackerPage() {
  const params = useParams<{ token: string }>();
  const token = params.token;

  const {
    data: tracker,
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ["public-tracking", token],
    queryFn: () => ldiApi.getPublicTracking(token),
    enabled: Boolean(token),
    refetchInterval: 30_000,
  });

  const completionPct =
    tracker && tracker.checklist_summary.total > 0
      ? Math.round((tracker.checklist_summary.completed / tracker.checklist_summary.total) * 100)
      : 0;

  return (
    <div className="min-h-screen bg-slate-100 flex flex-col">
      {/* Branded Header */}
      <header className="bg-navy text-white border-b border-navy-700">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 py-4 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-lg bg-brand flex items-center justify-center shrink-0">
              <FolderCog className="h-5 w-5 text-white" />
            </div>
            <div>
              <div className="font-semibold text-sm sm:text-base tracking-tight">
                Leaders Edu Tour Ltd
              </div>
              <div className="text-[11px] text-emerald-300">
                Live Client Application Status Tracker
              </div>
            </div>
          </div>

          <button
            type="button"
            onClick={() => refetch()}
            disabled={isFetching}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-xs font-medium text-white border border-white/15 disabled:opacity-60"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isFetching ? "animate-spin" : ""}`} />
            {isFetching ? "Refreshing..." : "Refresh Live Status"}
          </button>
        </div>
      </header>

      <main className="flex-1 max-w-5xl w-full mx-auto px-4 sm:px-6 py-6 space-y-6">
        {isLoading ? (
          <div className="bg-white rounded-2xl border border-slate-200 p-10 text-center text-sm text-slate-500 animate-pulse">
            Loading your live application progress...
          </div>
        ) : isError || !tracker ? (
          <div className="bg-white rounded-2xl border border-red-200 p-8 text-center space-y-2 shadow-sm">
            <h1 className="text-lg font-semibold text-navy">Application Tracker Not Found</h1>
            <p className="text-sm text-slate-600 max-w-md mx-auto">
              {error instanceof Error
                ? error.message
                : "This tracking link is invalid or the application has been archived."}
            </p>
            <p className="text-xs text-slate-400">
              Please contact your Leaders Edu Tour processing officer for an updated link.
            </p>
          </div>
        ) : (
          <>
            {/* Overview & Current Step Banner */}
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
              <div className="p-5 sm:p-6 border-b border-slate-200 flex flex-wrap items-start justify-between gap-4">
                <div className="space-y-1">
                  <div className="text-xs font-mono font-semibold text-brand">
                    REF: {tracker.application_reference}
                  </div>
                  <h1 className="text-xl sm:text-2xl font-semibold text-navy">
                    {tracker.applicant_name}
                  </h1>
                  <p className="text-xs sm:text-sm text-slate-600">
                    {tracker.destination_name} · {tracker.purpose_name} ({tracker.category_name})
                  </p>
                </div>

                <div className="flex flex-col sm:items-end gap-2">
                  <span
                    className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold border ${statusColorClasses(tracker.status)}`}
                  >
                    {tracker.status.replaceAll("_", " ")}
                  </span>
                  {tracker.assigned_officer_name && (
                    <span className="text-xs text-slate-500">
                      Processing Officer:{" "}
                      <strong className="text-slate-800">{tracker.assigned_officer_name}</strong>
                    </span>
                  )}
                  <span className="text-[11px] text-slate-400">
                    Last updated {formatDateTime(tracker.updated_at)}
                  </span>
                </div>
              </div>

              {tracker.current_stage_label && (
                <div className="px-5 sm:px-6 py-3.5 bg-emerald-50 border-b border-emerald-100 flex flex-wrap items-center gap-2.5">
                  <Sparkles className="h-4 w-4 text-brand shrink-0" />
                  <span className="text-xs font-medium text-emerald-900">Latest Step:</span>
                  <span className="text-sm font-semibold text-navy">
                    {tracker.current_stage_label}
                  </span>
                </div>
              )}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              {/* Live Officer Updates Timeline */}
              <div className="lg:col-span-7 bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
                <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Clock className="h-4 w-4 text-brand" />
                    <h2 className="text-sm font-semibold text-navy">
                      Live Application Updates ({tracker.updates.length})
                    </h2>
                  </div>
                  <span className="text-[11px] text-slate-400">Auto-refreshes every 30s</span>
                </div>

                {tracker.updates.length === 0 ? (
                  <div className="p-8 text-center text-xs text-slate-500">
                    Your file has been created and assigned to our processing team. Live step
                    updates will appear here as soon as your officer posts progress.
                  </div>
                ) : (
                  <div className="divide-y divide-slate-100">
                    {tracker.updates.map((upd, idx) => (
                      <div key={upd.id} className="p-5 space-y-2">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="flex items-center gap-2">
                            {idx === 0 ? (
                              <span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 text-[10px] font-semibold">
                                LATEST
                              </span>
                            ) : (
                              <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
                            )}
                            <h3 className="text-sm font-semibold text-navy">{upd.stage_label}</h3>
                          </div>
                          <span className="text-[11px] text-slate-400">
                            {formatDateTime(upd.created_at)}
                          </span>
                        </div>
                        <p className="text-xs sm:text-sm text-slate-700 whitespace-pre-line leading-relaxed">
                          {upd.message_body}
                        </p>
                        {upd.sent_by_name && (
                          <div className="text-[11px] text-slate-400">
                            Posted by {upd.sent_by_name}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Document Checklist Progress */}
              <div className="lg:col-span-5 bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden h-fit">
                <div className="px-5 py-4 border-b border-slate-200 space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <FileCheck2 className="h-4 w-4 text-navy" />
                      <h2 className="text-sm font-semibold text-navy">Checklist Progress</h2>
                    </div>
                    <span className="text-xs font-semibold text-brand">{completionPct}% Ready</span>
                  </div>
                  <div className="w-full h-2 rounded-full bg-slate-100 overflow-hidden">
                    <div
                      className="h-full bg-brand transition-all duration-300"
                      style={{ width: `${completionPct}%` }}
                    />
                  </div>
                  <div className="flex flex-wrap gap-3 text-[11px] text-slate-500">
                    <span>
                      Completed: <strong className="text-emerald-700">{tracker.checklist_summary.completed}</strong>
                    </span>
                    <span>
                      In Review: <strong className="text-amber-700">{tracker.checklist_summary.pending}</strong>
                    </span>
                    <span>
                      Outstanding: <strong className="text-red-700">{tracker.checklist_summary.missing}</strong>
                    </span>
                  </div>
                </div>

                <div className="divide-y divide-slate-100 max-h-[460px] overflow-y-auto">
                  {tracker.checklist_items.map((item) => (
                    <div
                      key={`${item.display_order}-${item.document_type_name}`}
                      className="px-4 py-2.5 flex items-center justify-between gap-2 text-xs"
                    >
                      <div className="min-w-0">
                        <div className="font-medium text-slate-800 truncate">
                          {String(item.display_order).padStart(2, "0")}. {item.document_type_name}
                        </div>
                        <div className="text-[10px] text-slate-400">{item.requirement_level}</div>
                      </div>
                      <span
                        className={`px-2 py-0.5 rounded-full text-[10px] font-medium border shrink-0 ${checklistBadgeClasses(item.status)}`}
                      >
                        {item.status.replaceAll("_", " ")}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </>
        )}
      </main>

      <footer className="bg-white border-t border-slate-200 py-4 px-4 text-center text-xs text-slate-500">
        <div className="max-w-5xl mx-auto flex flex-wrap items-center justify-between gap-2">
          <span className="inline-flex items-center gap-1.5">
            <ShieldCheck className="h-3.5 w-3.5 text-brand" />
            Private Read-Only Client Progress Tracker · Leaders Edu Tour Ltd
          </span>
          <span>
            Built by{" "}
            <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-navy text-emerald-300 font-semibold text-[10px]">
              CHIDI AI
            </span>
          </span>
        </div>
      </footer>
    </div>
  );
}
