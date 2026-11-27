"use client";

import React, { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Cake,
  CalendarHeart,
  Mail,
  PauseCircle,
  Pencil,
  PlayCircle,
  Plus,
  RefreshCw,
  Save,
  Search,
  Send,
  Trash2,
} from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { ldiApi } from "@/lib/api-client";
import { formatDateTime } from "@/lib/utils";
import type { ClientBirthdayItem } from "@/types";

export default function ClientBirthdaysPage() {
  const qc = useQueryClient();

  const [applicantId, setApplicantId] = useState("");
  const [clientName, setClientName] = useState("");
  const [clientEmail, setClientEmail] = useState("");
  const [birthDate, setBirthDate] = useState("");
  const [customMessage, setCustomMessage] = useState("");
  const [sendIfToday, setSendIfToday] = useState(true);
  const [search, setSearch] = useState("");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editEmail, setEditEmail] = useState("");
  const [editBirthDate, setEditBirthDate] = useState("");
  const [editCustomMessage, setEditCustomMessage] = useState("");
  const [editActive, setEditActive] = useState(true);

  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const { data: applicantsData } = useQuery({
    queryKey: ["applicants-for-birthdays"],
    queryFn: () => ldiApi.listApplicants("?page_size=100"),
  });

  const { data: birthdays = [], isLoading } = useQuery({
    queryKey: ["client-birthdays"],
    queryFn: ldiApi.listBirthdays,
  });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["client-birthdays"] });
  };

  const handleApplicantPick = (pickedId: string) => {
    setApplicantId(pickedId);
    const app = applicantsData?.items.find((a) => a.id === pickedId);
    if (app) {
      setClientName(app.full_name);
      setClientEmail(app.email);
      if (app.date_of_birth) {
        setBirthDate(app.date_of_birth);
      }
    }
  };

  const createMutation = useMutation({
    mutationFn: () =>
      ldiApi.createBirthday({
        applicant_id: applicantId || null,
        client_name: clientName.trim(),
        client_email: clientEmail.trim(),
        birth_date: birthDate,
        custom_message: customMessage.trim() || null,
        is_active: true,
        send_if_today: sendIfToday,
      }),
    onSuccess: (created) => {
      setApplicantId("");
      setClientName("");
      setClientEmail("");
      setBirthDate("");
      setCustomMessage("");
      setErrorMsg(null);
      setStatusMsg(
        created.is_birthday_today && created.last_delivery_status
          ? `Added birthday automation for ${created.client_name} and dispatched today's wish (${created.last_delivery_status}).`
          : `Enrolled ${created.client_name} (${created.client_email}) for automated annual birthday emails.`
      );
      refresh();
    },
    onError: (err) =>
      setErrorMsg(err instanceof Error ? err.message : "Failed to save client birthday"),
  });

  const updateMutation = useMutation({
    mutationFn: () => {
      if (!editingId) throw new Error("No birthday record selected.");
      return ldiApi.updateBirthday(editingId, {
        client_name: editName.trim(),
        client_email: editEmail.trim(),
        birth_date: editBirthDate,
        custom_message: editCustomMessage.trim(),
        is_active: editActive,
      });
    },
    onSuccess: (updated) => {
      setEditingId(null);
      setErrorMsg(null);
      setStatusMsg(`Updated birthday record for ${updated.client_name}.`);
      refresh();
    },
    onError: (err) =>
      setErrorMsg(err instanceof Error ? err.message : "Failed to update birthday record"),
  });

  const toggleActiveMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      ldiApi.updateBirthday(id, { is_active }),
    onSuccess: (updated) => {
      setErrorMsg(null);
      setStatusMsg(
        updated.is_active
          ? `Resumed annual birthday emails for ${updated.client_name}.`
          : `Paused annual birthday emails for ${updated.client_name}.`
      );
      refresh();
    },
  });

  const sendNowMutation = useMutation({
    mutationFn: ldiApi.sendBirthdayNow,
    onSuccess: (updated) => {
      setErrorMsg(null);
      setStatusMsg(
        `Birthday email sent to ${updated.client_name} (${updated.client_email}) — ${updated.last_delivery_status} (${updated.last_delivery_provider}).`
      );
      refresh();
    },
    onError: (err) =>
      setErrorMsg(err instanceof Error ? err.message : "Failed to send birthday email"),
  });

  const processDueMutation = useMutation({
    mutationFn: ldiApi.processDueBirthdays,
    onSuccess: (res) => {
      setErrorMsg(null);
      setStatusMsg(
        res.processed_count > 0
          ? `Processed and sent ${res.processed_count} birthday wish(es) due today.`
          : "Checked all enrolled clients — no unsent birthdays due today."
      );
      refresh();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: ldiApi.deleteBirthday,
    onSuccess: (res, id) => {
      setSelectedIds((prev) => prev.filter((x) => x !== id));
      setErrorMsg(null);
      setStatusMsg(res.message);
      refresh();
    },
  });

  const batchDeleteMutation = useMutation({
    mutationFn: ldiApi.batchDeleteBirthdays,
    onSuccess: (res) => {
      setSelectedIds([]);
      setErrorMsg(null);
      setStatusMsg(res.message);
      refresh();
    },
  });

  const startEdit = (item: ClientBirthdayItem) => {
    setEditingId(item.id);
    setEditName(item.client_name);
    setEditEmail(item.client_email);
    setEditBirthDate(item.birth_date);
    setEditCustomMessage(item.custom_message || "");
    setEditActive(item.is_active);
  };

  const filtered = birthdays.filter((item) => {
    if (!search.trim()) return true;
    const term = search.trim().toLowerCase();
    return (
      item.client_name.toLowerCase().includes(term) ||
      item.client_email.toLowerCase().includes(term)
    );
  });

  const visibleIds = filtered.map((b) => b.id);
  const allSelected = visibleIds.length > 0 && visibleIds.every((id) => selectedIds.includes(id));

  const todayCount = birthdays.filter((b) => b.is_active && b.is_birthday_today).length;
  const upcoming30Count = birthdays.filter(
    (b) => b.is_active && b.days_until_birthday <= 30
  ).length;
  const totalSentCount = birthdays.reduce((acc, b) => acc + b.send_count, 0);

  return (
    <AppShell
      title="Automated Client Birthdays"
      subtitle="Enter client names, emails, and birthdates once — LDI sends warm Happy Birthday emails automatically every year."
      actions={
        <button
          type="button"
          onClick={() => processDueMutation.mutate()}
          disabled={processDueMutation.isPending}
          className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg border border-slate-300 bg-white text-xs font-medium text-navy hover:bg-slate-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${processDueMutation.isPending ? "animate-spin" : ""}`} />
          Check &amp; Send Due Today
        </button>
      }
    >
      <div className="space-y-6">
        {errorMsg && (
          <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-xs text-red-700">
            {errorMsg}
          </div>
        )}
        {statusMsg && (
          <div className="rounded-xl bg-emerald-50 border border-emerald-200 px-4 py-3 text-xs text-emerald-700 flex items-center justify-between gap-2">
            <span>{statusMsg}</span>
            <button type="button" onClick={() => setStatusMsg(null)} className="underline">
              Dismiss
            </button>
          </div>
        )}

        {/* Summary KPI Strip */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
            <div className="text-xs text-slate-500">Enrolled Clients</div>
            <div className="text-2xl font-semibold text-navy mt-1">{birthdays.length}</div>
          </div>
          <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
            <div className="text-xs text-slate-500">Birthdays Today</div>
            <div className="text-2xl font-semibold text-brand mt-1">{todayCount}</div>
          </div>
          <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
            <div className="text-xs text-slate-500">Upcoming (Next 30 Days)</div>
            <div className="text-2xl font-semibold text-amber-600 mt-1">{upcoming30Count}</div>
          </div>
          <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
            <div className="text-xs text-slate-500">Total Wishes Sent</div>
            <div className="text-2xl font-semibold text-slate-800 mt-1">{totalSentCount}</div>
          </div>
        </div>

        {/* Enroll New Client Birthday */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm space-y-4">
          <div className="flex items-center gap-2">
            <Cake className="h-4 w-4 text-brand" />
            <h2 className="text-sm font-semibold text-navy">Add Client for Annual Birthday Emails</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-12 gap-3">
            <div className="md:col-span-3">
              <label className="block text-xs font-medium text-slate-700 mb-1">
                Quick-Fill from Applicant (Optional)
              </label>
              <select
                value={applicantId}
                onChange={(e) => handleApplicantPick(e.target.value)}
                className="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white"
              >
                <option value="">Manual entry...</option>
                {applicantsData?.items.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.full_name} ({a.application_reference})
                  </option>
                ))}
              </select>
            </div>
            <div className="md:col-span-3">
              <label className="block text-xs font-medium text-slate-700 mb-1">Client Name *</label>
              <input
                value={clientName}
                onChange={(e) => setClientName(e.target.value)}
                placeholder="e.g. Chidinma Okafor"
                className="w-full px-3 py-2 text-xs rounded-lg border border-slate-300"
              />
            </div>
            <div className="md:col-span-3">
              <label className="block text-xs font-medium text-slate-700 mb-1">Client Email *</label>
              <input
                type="email"
                value={clientEmail}
                onChange={(e) => setClientEmail(e.target.value)}
                placeholder="client@example.com"
                className="w-full px-3 py-2 text-xs rounded-lg border border-slate-300"
              />
            </div>
            <div className="md:col-span-3">
              <label className="block text-xs font-medium text-slate-700 mb-1">Birthdate *</label>
              <input
                type="date"
                value={birthDate}
                onChange={(e) => setBirthDate(e.target.value)}
                className="w-full px-3 py-2 text-xs rounded-lg border border-slate-300"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-end">
            <div className="md:col-span-7">
              <label className="block text-xs font-medium text-slate-700 mb-1">
                Custom Birthday Message (Optional)
              </label>
              <input
                value={customMessage}
                onChange={(e) => setCustomMessage(e.target.value)}
                placeholder="Leave blank to use the warm Leaders Edu Tour Ltd birthday greeting..."
                className="w-full px-3 py-2 text-xs rounded-lg border border-slate-300"
              />
            </div>
            <label className="md:col-span-2 inline-flex items-center gap-2 text-xs text-slate-700 py-2 cursor-pointer">
              <input
                type="checkbox"
                checked={sendIfToday}
                onChange={(e) => setSendIfToday(e.target.checked)}
                className="rounded border-slate-300"
              />
              Send immediately if today
            </label>
            <button
              type="button"
              onClick={() => createMutation.mutate()}
              disabled={
                !clientName.trim() || !clientEmail.trim() || !birthDate || createMutation.isPending
              }
              className="md:col-span-3 inline-flex items-center justify-center gap-1.5 px-4 py-2 rounded-lg bg-brand text-white text-xs font-medium hover:bg-brand-light disabled:opacity-50"
            >
              <Plus className="h-3.5 w-3.5" />
              {createMutation.isPending ? "Saving..." : "Save Birthday Automation"}
            </button>
          </div>
        </div>

        {/* Enrolled Client Birthdays List */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-200 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              {filtered.length > 0 && (
                <input
                  type="checkbox"
                  aria-label="Select All Client Birthdays"
                  checked={allSelected}
                  onChange={() => setSelectedIds(allSelected ? [] : visibleIds)}
                  className="rounded border-slate-300"
                />
              )}
              <h3 className="text-sm font-semibold text-navy">
                Enrolled Client Birthdays ({filtered.length})
              </h3>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <div className="relative">
                <Search className="h-3.5 w-3.5 text-slate-400 absolute left-2.5 top-2.5" />
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search name or email..."
                  className="pl-8 pr-3 py-1.5 text-xs rounded-lg border border-slate-300 w-52"
                />
              </div>
              {selectedIds.length > 0 && (
                <button
                  type="button"
                  onClick={() => batchDeleteMutation.mutate(selectedIds)}
                  disabled={batchDeleteMutation.isPending}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-600 text-white text-xs font-medium hover:bg-red-700"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  Delete Selected ({selectedIds.length})
                </button>
              )}
            </div>
          </div>

          {isLoading ? (
            <div className="p-8 text-center text-xs text-slate-400">Loading client birthdays...</div>
          ) : filtered.length === 0 ? (
            <div className="p-10 text-center text-xs text-slate-500">
              No client birthdays enrolled yet. Add a client above to send Happy Birthday emails automatically every year.
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {filtered.map((item) => (
                <div
                  key={item.id}
                  className={`p-4 flex flex-wrap items-start justify-between gap-4 ${
                    !item.is_active ? "bg-slate-50/70 opacity-75" : ""
                  }`}
                >
                  {editingId === item.id ? (
                    <div className="w-full space-y-3 bg-slate-50 rounded-lg border border-slate-200 p-3.5">
                      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                        <div>
                          <label className="block text-[11px] font-medium text-slate-600 mb-1">
                            Client Name
                          </label>
                          <input
                            value={editName}
                            onChange={(e) => setEditName(e.target.value)}
                            className="w-full px-2.5 py-1.5 text-xs rounded border border-slate-300 bg-white"
                          />
                        </div>
                        <div>
                          <label className="block text-[11px] font-medium text-slate-600 mb-1">
                            Client Email
                          </label>
                          <input
                            type="email"
                            value={editEmail}
                            onChange={(e) => setEditEmail(e.target.value)}
                            className="w-full px-2.5 py-1.5 text-xs rounded border border-slate-300 bg-white"
                          />
                        </div>
                        <div>
                          <label className="block text-[11px] font-medium text-slate-600 mb-1">
                            Birthdate
                          </label>
                          <input
                            type="date"
                            value={editBirthDate}
                            onChange={(e) => setEditBirthDate(e.target.value)}
                            className="w-full px-2.5 py-1.5 text-xs rounded border border-slate-300 bg-white"
                          />
                        </div>
                        <label className="inline-flex items-center gap-2 text-xs text-slate-700 pt-5 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={editActive}
                            onChange={(e) => setEditActive(e.target.checked)}
                            className="rounded border-slate-300"
                          />
                          Automation Active
                        </label>
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <input
                          value={editCustomMessage}
                          onChange={(e) => setEditCustomMessage(e.target.value)}
                          placeholder="Custom birthday message (optional)..."
                          className="flex-1 min-w-[220px] px-2.5 py-1.5 text-xs rounded border border-slate-300 bg-white"
                        />
                        <button
                          type="button"
                          onClick={() => updateMutation.mutate()}
                          disabled={
                            !editName.trim() ||
                            !editEmail.trim() ||
                            !editBirthDate ||
                            updateMutation.isPending
                          }
                          className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-brand text-white text-xs font-medium hover:bg-brand-light disabled:opacity-50"
                        >
                          <Save className="h-3.5 w-3.5" />
                          {updateMutation.isPending ? "Saving..." : "Save"}
                        </button>
                        <button
                          type="button"
                          onClick={() => setEditingId(null)}
                          className="px-3 py-1.5 rounded-lg border border-slate-300 bg-white text-xs text-slate-700"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div className="flex items-start gap-3 min-w-0 flex-1">
                        <input
                          type="checkbox"
                          aria-label={`Select ${item.client_name}`}
                          checked={selectedIds.includes(item.id)}
                          onChange={() =>
                            setSelectedIds((prev) =>
                              prev.includes(item.id)
                                ? prev.filter((id) => id !== item.id)
                                : [...prev, item.id]
                            )
                          }
                          className="mt-1 rounded border-slate-300 shrink-0"
                        />
                        <div className="min-w-0 space-y-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="text-sm font-semibold text-navy">
                              {item.client_name}
                            </span>
                            {item.is_birthday_today && (
                              <span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-200 text-[10px] font-semibold">
                                Birthday Today
                              </span>
                            )}
                            <span
                              className={`px-2 py-0.5 rounded-full text-[10px] font-medium border ${
                                item.is_active
                                  ? "bg-amber-50 text-amber-800 border-amber-200"
                                  : "bg-slate-100 text-slate-600 border-slate-200"
                              }`}
                            >
                              {item.is_active
                                ? item.days_until_birthday === 0
                                  ? "Due Today"
                                  : `In ${item.days_until_birthday} day(s) · ${item.next_birthday_date}`
                                : "Paused"}
                            </span>
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 text-[10px] font-medium">
                              <Mail className="h-2.5 w-2.5" /> Sent {item.send_count}x
                            </span>
                          </div>
                          {item.custom_message && (
                            <p className="text-xs text-slate-600">{item.custom_message}</p>
                          )}
                          <div className="flex flex-wrap items-center gap-3 text-[11px] text-slate-500">
                            <span>
                              Email: <strong className="text-slate-700">{item.client_email}</strong>
                            </span>
                            <span className="inline-flex items-center gap-1">
                              <CalendarHeart className="h-3 w-3 text-brand" />
                              Birthdate: <strong className="text-slate-700">{item.birth_date}</strong>
                            </span>
                            {item.last_delivery_status && (
                              <span>
                                Last Status: <strong>{item.last_delivery_status}</strong> (
                                {item.last_delivery_provider})
                              </span>
                            )}
                            {item.last_sent_at && (
                              <span>Last Sent: {formatDateTime(item.last_sent_at)}</span>
                            )}
                          </div>
                          {item.last_delivery_detail && (
                            <div
                              className={`text-[11px] italic ${
                                item.last_delivery_status === "FAILED"
                                  ? "text-red-600"
                                  : "text-slate-500"
                              }`}
                            >
                              {item.last_delivery_detail}
                            </div>
                          )}
                        </div>
                      </div>

                      <div className="flex flex-wrap items-center gap-2 shrink-0">
                        <button
                          type="button"
                          onClick={() => sendNowMutation.mutate(item.id)}
                          disabled={sendNowMutation.isPending}
                          className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-slate-200 text-navy hover:bg-slate-50 text-xs font-medium"
                        >
                          <Send className="h-3.5 w-3.5" />
                          Send Now
                        </button>
                        <button
                          type="button"
                          onClick={() => startEdit(item)}
                          className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-slate-200 text-navy hover:bg-slate-50 text-xs font-medium"
                        >
                          <Pencil className="h-3.5 w-3.5" />
                          Edit
                        </button>
                        <button
                          type="button"
                          onClick={() =>
                            toggleActiveMutation.mutate({
                              id: item.id,
                              is_active: !item.is_active,
                            })
                          }
                          className={`inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border text-xs font-medium ${
                            item.is_active
                              ? "border-amber-200 bg-amber-50 text-amber-800 hover:bg-amber-100"
                              : "border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
                          }`}
                        >
                          {item.is_active ? (
                            <>
                              <PauseCircle className="h-3.5 w-3.5" /> Pause
                            </>
                          ) : (
                            <>
                              <PlayCircle className="h-3.5 w-3.5" /> Resume
                            </>
                          )}
                        </button>
                        <button
                          type="button"
                          onClick={() => deleteMutation.mutate(item.id)}
                          title="Delete Birthday"
                          className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-red-200 bg-red-50 text-red-700 hover:bg-red-100 text-xs font-medium"
                        >
                          <Trash2 className="h-3.5 w-3.5" /> Delete
                        </button>
                      </div>
                    </>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </AppShell>
  );
}
