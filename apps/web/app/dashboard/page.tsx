"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  BellRing,
  CheckCircle2,
  Clock,
  FileCheck2,
  FileWarning,
  Plus,
  Trash2,
  UploadCloud,
  Users,
  XCircle,
} from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { useAuth } from "@/hooks/use-auth";
import { ldiApi } from "@/lib/api-client";
import { formatDateTime, statusColorClasses } from "@/lib/utils";

function HorizontalBarChart({
  title,
  items,
  colorClass = "bg-navy",
}: {
  title: string;
  items: Array<{ label: string; value: number }>;
  colorClass?: string;
}) {
  const maxVal = Math.max(...items.map((i) => i.value), 1);
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
      <h3 className="text-sm font-semibold text-navy mb-4">{title}</h3>
      {items.length === 0 ? (
        <p className="text-xs text-slate-400 py-6 text-center">No database records recorded yet.</p>
      ) : (
        <div className="space-y-3">
          {items.map((item) => (
            <div key={item.label} className="space-y-1">
              <div className="flex justify-between text-xs font-medium text-slate-700">
                <span className="truncate pr-2">{item.label}</span>
                <span className="tabular-nums text-slate-900 font-semibold">{item.value}</span>
              </div>
              <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
                <div
                  className={`h-full rounded-full ${colorClass}`}
                  style={{ width: `${Math.max(4, (item.value / maxVal) * 100)}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function DashboardPage() {
  const { hasRole, user } = useAuth();
  const qc = useQueryClient();
  const canDelete = hasRole("SUPER_ADMIN", "ADMIN", "OFFICER");
  const isExecutive = hasRole("CEO", "SUPER_ADMIN");
  const [selectedAppIds, setSelectedAppIds] = useState<string[]>([]);
  const [quickReminderTitle, setQuickReminderTitle] = useState("");
  const [quickReminderEmail, setQuickReminderEmail] = useState("");

  const { data, isLoading, error } = useQuery({
    queryKey: ["dashboard-metrics"],
    queryFn: ldiApi.getDashboardMetrics,
    refetchInterval: 15_000,
  });

  const { data: myReminders = [] } = useQuery({
    queryKey: ["personal-reminders"],
    queryFn: ldiApi.listReminders,
    enabled: isExecutive,
  });

  const quickReminderMutation = useMutation({
    mutationFn: () =>
      ldiApi.createReminder({
        title: quickReminderTitle.trim(),
        recipient_email: quickReminderEmail.trim() || user?.email,
        send_immediately: true,
      }),
    onSuccess: () => {
      setQuickReminderTitle("");
      qc.invalidateQueries({ queryKey: ["personal-reminders"] });
    },
  });

  const markReminderDoneMutation = useMutation({
    mutationFn: (id: string) => ldiApi.updateReminder(id, { is_completed: true }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["personal-reminders"] }),
  });

  const deleteReminderMutation = useMutation({
    mutationFn: ldiApi.deleteReminder,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["personal-reminders"] }),
  });

  const deleteAppMutation = useMutation({
    mutationFn: ldiApi.archiveApplicant,
    onSuccess: (_res, id) => {
      setSelectedAppIds((prev) => prev.filter((x) => x !== id));
      qc.invalidateQueries({ queryKey: ["dashboard-metrics"] });
      qc.invalidateQueries({ queryKey: ["applicants"] });
    },
  });

  const batchDeleteAppsMutation = useMutation({
    mutationFn: ldiApi.batchDeleteApplicants,
    onSuccess: () => {
      setSelectedAppIds([]);
      qc.invalidateQueries({ queryKey: ["dashboard-metrics"] });
      qc.invalidateQueries({ queryKey: ["applicants"] });
    },
  });

  const recentAppIds = (data?.recent_applicants || []).map((a) => a.id);
  const allRecentSelected =
    recentAppIds.length > 0 && recentAppIds.every((id) => selectedAppIds.includes(id));

  const kpis = data
    ? [
        { label: "Total Applicants", value: data.total_applicants, icon: Users, tone: "text-navy bg-navy-50" },
        { label: "Documents Processed", value: data.total_documents_processed, icon: FileCheck2, tone: "text-brand bg-brand-muted" },
        { label: "Currently Processing", value: data.applications_processing, icon: Clock, tone: "text-amber-700 bg-amber-50" },
        { label: "Completed Batches", value: data.completed_batches, icon: CheckCircle2, tone: "text-emerald-700 bg-emerald-50" },
        { label: "Missing Documents", value: data.applications_with_missing_docs, icon: FileWarning, tone: "text-amber-700 bg-amber-50" },
        { label: "Awaiting Review", value: data.documents_awaiting_review, icon: AlertTriangle, tone: "text-amber-700 bg-amber-50" },
        { label: "Failed Jobs", value: data.failed_processing_jobs, icon: XCircle, tone: "text-red-700 bg-red-50" },
      ]
    : [];

  return (
    <AppShell
      title="Operations Dashboard"
      subtitle="Live database metrics across applicant document intake, AI classification, and compliance checks."
      actions={
        <>
          <Link
            href="/processing"
            className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg border border-slate-300 bg-white text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            <UploadCloud className="h-4 w-4" />
            Bulk Upload
          </Link>
          <Link
            href="/applicants?new=1"
            className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg bg-brand text-white text-sm font-medium hover:bg-brand-light"
          >
            <Plus className="h-4 w-4" />
            New Applicant
          </Link>
        </>
      }
    >
      {isLoading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-24 rounded-xl bg-white border border-slate-200 animate-pulse" />
          ))}
        </div>
      )}

      {error && (
        <div className="rounded-xl bg-red-50 border border-red-200 p-4 text-sm text-red-700">
          Failed to load dashboard metrics: {error instanceof Error ? error.message : "Unknown error"}
        </div>
      )}

      {data && (
        <div className="space-y-6">
          {/* KPI Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-7 gap-4">
            {kpis.map((kpi) => {
              const Icon = kpi.icon;
              return (
                <div
                  key={kpi.label}
                  className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm flex flex-col justify-between"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-slate-500">{kpi.label}</span>
                    <span className={`p-1.5 rounded-lg ${kpi.tone}`}>
                      <Icon className="h-4 w-4" />
                    </span>
                  </div>
                  <div className="text-2xl font-bold text-navy mt-3 tabular-nums">{kpi.value}</div>
                </div>
              );
            })}
          </div>

          {/* Visual Charts Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
            <HorizontalBarChart
              title="Applicants by Destination"
              items={data.applicants_by_destination.map((d) => ({ label: d.name, value: d.count }))}
              colorClass="bg-navy"
            />
            <HorizontalBarChart
              title="Applicants by Travel Purpose"
              items={data.applicants_by_purpose.map((p) => ({ label: p.name, value: p.count }))}
              colorClass="bg-brand"
            />
            <HorizontalBarChart
              title="Most Frequently Missing Documents"
              items={data.missing_document_stats.map((m) => ({
                label: m.document_type,
                value: m.missing_count,
              }))}
              colorClass="bg-amber-600"
            />
          </div>

          {/* Documents Processed Over Time + Completion Rate */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
            <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-navy">Documents Processed Over Time</h3>
                <span className="text-xs text-slate-500">
                  Batch Completion Rate:{" "}
                  <strong className="text-brand">{data.completion_rate_percent}%</strong>
                </span>
              </div>
              {data.documents_over_time.length === 0 ? (
                <p className="text-xs text-slate-400 py-8 text-center">
                  Upload and process documents to populate daily throughput history.
                </p>
              ) : (
                <div className="flex items-end gap-2 h-36 pt-4">
                  {data.documents_over_time.map((pt) => {
                    const max = Math.max(...data.documents_over_time.map((x) => x.count), 1);
                    const pct = Math.max(12, Math.round((pt.count / max) * 100));
                    return (
                      <div key={pt.date} className="flex-1 flex flex-col items-center gap-1 min-w-0">
                        <span className="text-[11px] font-semibold text-navy tabular-nums">
                          {pt.count}
                        </span>
                        <div className="w-full max-w-[38px] bg-slate-100 rounded-t-md h-24 flex items-end overflow-hidden">
                          <div
                            className="w-full bg-brand rounded-t-md transition-all"
                            style={{ height: `${pct}%` }}
                          />
                        </div>
                        <span className="text-[10px] text-slate-500 truncate w-full text-center">
                          {pt.date.slice(5)}
                        </span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
              <h3 className="text-sm font-semibold text-navy mb-4">Officer Activity</h3>
              {data.officer_activity.length === 0 ? (
                <p className="text-xs text-slate-400 py-8 text-center">No assigned applicants yet.</p>
              ) : (
                <div className="space-y-3">
                  {data.officer_activity.map((off) => (
                    <div
                      key={off.email}
                      className="flex items-center justify-between py-2 border-b border-slate-100 last:border-0"
                    >
                      <div className="min-w-0">
                        <p className="text-xs font-semibold text-slate-800 truncate">{off.name}</p>
                        <p className="text-[11px] text-slate-500 truncate">{off.email}</p>
                      </div>
                      <span className="px-2.5 py-1 rounded-full bg-navy-50 text-navy text-xs font-semibold tabular-nums">
                        {off.assigned_applicants} files
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* CEO & Executive Twice-Daily Personal Email Reminders */}
          {isExecutive && (
            <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <BellRing className="h-4 w-4 text-brand" />
                  <h3 className="text-sm font-semibold text-navy">
                    CEO &amp; Executive Personal Email Reminders (Twice Daily Until Done)
                  </h3>
                </div>
                <Link href="/reminders" className="text-xs font-medium text-brand hover:underline">
                  Manage Schedule &amp; All Reminders
                </Link>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-6 gap-2.5">
                <input
                  value={quickReminderTitle}
                  onChange={(e) => setQuickReminderTitle(e.target.value)}
                  placeholder="Task to be reminded about twice daily..."
                  className="md:col-span-3 px-3 py-2 text-xs rounded-lg border border-slate-300"
                />
                <input
                  type="email"
                  value={quickReminderEmail}
                  onChange={(e) => setQuickReminderEmail(e.target.value)}
                  placeholder={user?.email || "Personal email (optional)"}
                  className="md:col-span-2 px-3 py-2 text-xs rounded-lg border border-slate-300"
                />
                <button
                  type="button"
                  onClick={() => quickReminderMutation.mutate()}
                  disabled={!quickReminderTitle.trim() || quickReminderMutation.isPending}
                  className="inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-brand text-white text-xs font-medium hover:bg-brand-light disabled:opacity-50"
                >
                  <Plus className="h-3.5 w-3.5" />
                  {quickReminderMutation.isPending ? "Saving..." : "Set Reminder"}
                </button>
              </div>
              {myReminders.filter((r) => !r.is_completed).length > 0 && (
                <div className="divide-y divide-slate-100 border border-slate-200 rounded-lg">
                  {myReminders
                    .filter((r) => !r.is_completed)
                    .slice(0, 4)
                    .map((rem) => (
                      <div
                        key={rem.id}
                        className="px-3 py-2 flex flex-wrap items-center justify-between gap-2 text-xs"
                      >
                        <div className="min-w-0">
                          <span className="font-semibold text-navy">{rem.title}</span>
                          <span className="text-slate-500 ml-2">
                            ({rem.recipient_email} · Sent {rem.send_count}x)
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={() => markReminderDoneMutation.mutate(rem.id)}
                            className="inline-flex items-center gap-1 px-2 py-1 rounded border border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 text-[11px] font-medium"
                          >
                            <CheckCircle2 className="h-3 w-3" /> Mark Done
                          </button>
                          <button
                            type="button"
                            onClick={() => deleteReminderMutation.mutate(rem.id)}
                            title="Delete Reminder"
                            className="p-1 rounded border border-red-200 bg-red-50 text-red-700 hover:bg-red-100"
                          >
                            <Trash2 className="h-3 w-3" />
                          </button>
                        </div>
                      </div>
                    ))}
                </div>
              )}
            </div>
          )}

          {/* Recent Applicants & Recent Activity */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
              <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
                <h3 className="text-sm font-semibold text-navy">Recent Applicants</h3>
                <div className="flex items-center gap-2.5">
                  {canDelete && recentAppIds.length > 0 && (
                    <label className="inline-flex items-center gap-1 text-xs text-slate-600 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={allRecentSelected}
                        onChange={() =>
                          setSelectedAppIds(allRecentSelected ? [] : recentAppIds)
                        }
                        className="rounded border-slate-300"
                      />
                      All
                    </label>
                  )}
                  {canDelete && selectedAppIds.length > 0 && (
                    <button
                      type="button"
                      onClick={() => batchDeleteAppsMutation.mutate(selectedAppIds)}
                      disabled={batchDeleteAppsMutation.isPending}
                      className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-red-600 text-white text-xs font-medium hover:bg-red-700"
                    >
                      <Trash2 className="h-3 w-3" />
                      Delete ({selectedAppIds.length})
                    </button>
                  )}
                  <Link href="/applicants" className="text-xs font-medium text-brand hover:underline">
                    View All
                  </Link>
                </div>
              </div>
              {data.recent_applicants.length === 0 ? (
                <p className="text-xs text-slate-400 py-6 text-center">No applicants created yet.</p>
              ) : (
                <div className="divide-y divide-slate-100">
                  {data.recent_applicants.map((app) => (
                    <div
                      key={app.id}
                      className="py-2.5 flex items-center justify-between gap-2 hover:bg-slate-50 rounded-lg px-2 -mx-2"
                    >
                      {canDelete && (
                        <input
                          type="checkbox"
                          aria-label={`Select ${app.full_name}`}
                          checked={selectedAppIds.includes(app.id)}
                          onChange={() =>
                            setSelectedAppIds((prev) =>
                              prev.includes(app.id)
                                ? prev.filter((id) => id !== app.id)
                                : [...prev, app.id]
                            )
                          }
                          className="rounded border-slate-300 shrink-0"
                        />
                      )}
                      <Link href={`/applicants/${app.id}`} className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-slate-900 truncate">{app.full_name}</p>
                        <p className="text-xs text-slate-500 truncate">
                          {app.application_reference} · {app.destination} ({app.purpose})
                        </p>
                      </Link>
                      <span
                        className={`px-2 py-0.5 rounded-full text-[11px] font-medium border shrink-0 ${statusColorClasses(app.status)}`}
                      >
                        {app.status}
                      </span>
                      {canDelete && (
                        <button
                          type="button"
                          onClick={() => deleteAppMutation.mutate(app.id)}
                          title="Delete Applicant"
                          className="p-1.5 rounded border border-red-200 bg-red-50 text-red-700 hover:bg-red-100 shrink-0"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
              <h3 className="text-sm font-semibold text-navy mb-4">Recent Processing Activity</h3>
              {data.recent_activity.length === 0 ? (
                <p className="text-xs text-slate-400 py-6 text-center">No audit events recorded yet.</p>
              ) : (
                <div className="divide-y divide-slate-100">
                  {data.recent_activity.map((act) => (
                    <div key={act.id} className="py-2.5 flex items-center justify-between text-xs">
                      <div>
                        <span className="font-semibold text-slate-800">{act.action}</span>
                        <span className="text-slate-500 ml-1.5">({act.entity_type})</span>
                        <p className="text-[11px] text-slate-500">{act.actor_email}</p>
                      </div>
                      <span className="text-[11px] text-slate-400">
                        {formatDateTime(act.created_at)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}
