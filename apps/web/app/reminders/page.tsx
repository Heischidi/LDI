"use client";

import React, { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BellRing, CheckCircle2, Clock, Mail, Pencil, Plus, RotateCcw, Save, Send, Trash2 } from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { useAuth } from "@/hooks/use-auth";
import { ldiApi } from "@/lib/api-client";
import { formatDateTime } from "@/lib/utils";
import type { PersonalReminderItem } from "@/types";

export default function RemindersPage() {
  const { user } = useAuth();
  const isCeo = user?.role === "CEO";
  const qc = useQueryClient();

  const [title, setTitle] = useState("");
  const [notes, setNotes] = useState("");
  const [recipientEmail, setRecipientEmail] = useState("");
  const [morningTime, setMorningTime] = useState("09:00");
  const [eveningTime, setEveningTime] = useState("17:00");
  const [sendImmediately, setSendImmediately] = useState(true);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editNotes, setEditNotes] = useState("");
  const [editEmail, setEditEmail] = useState("");
  const [editMorning, setEditMorning] = useState("09:00");
  const [editEvening, setEditEvening] = useState("17:00");
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (user?.email && !recipientEmail) {
      setRecipientEmail(user.email);
    }
  }, [user?.email, recipientEmail]);

  const { data: reminders = [], isLoading } = useQuery({
    queryKey: ["personal-reminders"],
    queryFn: ldiApi.listReminders,
    enabled: isCeo,
    refetchInterval: 60_000,
  });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["personal-reminders"] });
  };

  const createMutation = useMutation({
    mutationFn: () =>
      ldiApi.createReminder({
        title: title.trim(),
        notes: notes.trim() || undefined,
        recipient_email: recipientEmail.trim() || undefined,
        morning_time: morningTime,
        evening_time: eveningTime,
        send_immediately: sendImmediately,
      }),
    onSuccess: (created) => {
      setTitle("");
      setNotes("");
      setErrorMsg(null);
      setStatusMsg(
        `Reminder "${created.title}" active for ${created.recipient_email} (${created.morning_time} & ${created.evening_time} UTC).`
      );
      refresh();
    },
    onError: (err) => setErrorMsg(err instanceof Error ? err.message : "Failed to create reminder"),
  });

  const toggleDoneMutation = useMutation({
    mutationFn: ({ id, is_completed }: { id: string; is_completed: boolean }) =>
      ldiApi.updateReminder(id, { is_completed }),
    onSuccess: (updated) => {
      setErrorMsg(null);
      setStatusMsg(
        updated.is_completed
          ? `Marked "${updated.title}" completed — twice-daily emails stopped.`
          : `Reopened "${updated.title}" — twice-daily emails resumed.`
      );
      refresh();
    },
  });

  const updateReminderMutation = useMutation({
    mutationFn: () => {
      if (!editingId) throw new Error("No reminder selected.");
      return ldiApi.updateReminder(editingId, {
        title: editTitle.trim(),
        notes: editNotes.trim() || "",
        recipient_email: editEmail.trim(),
        morning_time: editMorning,
        evening_time: editEvening,
      });
    },
    onSuccess: (updated) => {
      setEditingId(null);
      setErrorMsg(null);
      setStatusMsg(`Updated reminder "${updated.title}".`);
      refresh();
    },
    onError: (err) => setErrorMsg(err instanceof Error ? err.message : "Failed to update reminder"),
  });

  const startEditReminder = (rem: PersonalReminderItem) => {
    setEditingId(rem.id);
    setEditTitle(rem.title);
    setEditNotes(rem.notes || "");
    setEditEmail(rem.recipient_email);
    setEditMorning(rem.morning_time);
    setEditEvening(rem.evening_time);
  };

  const sendNowMutation = useMutation({
    mutationFn: ldiApi.sendReminderNow,
    onSuccess: (updated) => {
      setErrorMsg(null);
      setStatusMsg(
        `Reminder email #${updated.send_count} dispatched to ${updated.recipient_email} (${updated.last_delivery_status}).`
      );
      refresh();
    },
    onError: (err) => setErrorMsg(err instanceof Error ? err.message : "Failed to dispatch reminder"),
  });

  const deleteMutation = useMutation({
    mutationFn: ldiApi.deleteReminder,
    onSuccess: (res, id) => {
      setSelectedIds((prev) => prev.filter((x) => x !== id));
      setErrorMsg(null);
      setStatusMsg(res.message);
      refresh();
    },
  });

  const batchDeleteMutation = useMutation({
    mutationFn: ldiApi.batchDeleteReminders,
    onSuccess: (res) => {
      setSelectedIds([]);
      setErrorMsg(null);
      setStatusMsg(res.message);
      refresh();
    },
  });

  const allIds = reminders.map((r) => r.id);
  const allSelected = allIds.length > 0 && allIds.every((id) => selectedIds.includes(id));

  if (!isCeo) {
    return (
      <AppShell
        title="CEO & Personal Action Reminders"
        subtitle="Executive action reminders exclusively available to the CEO account."
      >
        <div className="bg-white rounded-xl border border-slate-200 p-8 text-center text-sm text-slate-600 shadow-sm">
          Executive Access Only: CEO Reminders are exclusive to the CEO account.
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell
      title="CEO & Personal Action Reminders"
      subtitle="Set executive action reminders delivered automatically twice a day to your personal email until marked done."
    >
      <div className="space-y-6">
        {/* Create Twice-Daily Personal Reminder */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-sm font-semibold text-navy flex items-center gap-2">
              <BellRing className="h-4 w-4 text-brand" />
              Create Twice-Daily Personal Email Reminder
            </h2>
            <span className="text-xs text-slate-500 bg-slate-100 border border-slate-200 px-3 py-1 rounded-full">
              Sends 2x daily until marked done
            </span>
          </div>

          {errorMsg && (
            <div className="rounded-lg bg-red-50 border border-red-200 px-3 py-2 text-xs text-red-700">
              {errorMsg}
            </div>
          )}
          {statusMsg && (
            <div className="rounded-lg bg-emerald-50 border border-emerald-200 px-3 py-2 text-xs text-emerald-700">
              {statusMsg}
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-6 gap-3">
            <div className="md:col-span-2">
              <label className="block text-xs font-medium text-slate-700 mb-1">Task / Reminder Title *</label>
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Approve UK tuition transfer & sign LOA"
                className="w-full px-3 py-2 text-xs rounded-lg border border-slate-300"
              />
            </div>
            <div className="md:col-span-2">
              <label className="block text-xs font-medium text-slate-700 mb-1">Personal Email *</label>
              <input
                type="email"
                value={recipientEmail}
                onChange={(e) => setRecipientEmail(e.target.value)}
                placeholder="ceo.personal@gmail.com"
                className="w-full px-3 py-2 text-xs rounded-lg border border-slate-300"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">Morning Slot (UTC)</label>
              <input
                type="time"
                value={morningTime}
                onChange={(e) => setMorningTime(e.target.value)}
                className="w-full px-3 py-2 text-xs rounded-lg border border-slate-300"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">Evening Slot (UTC)</label>
              <input
                type="time"
                value={eveningTime}
                onChange={(e) => setEveningTime(e.target.value)}
                className="w-full px-3 py-2 text-xs rounded-lg border border-slate-300"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-6 gap-3 items-end">
            <div className="md:col-span-4">
              <label className="block text-xs font-medium text-slate-700 mb-1">Notes / Context (Optional)</label>
              <input
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Additional details included in each reminder email..."
                className="w-full px-3 py-2 text-xs rounded-lg border border-slate-300"
              />
            </div>
            <label className="inline-flex items-center gap-2 text-xs text-slate-700 py-2 cursor-pointer">
              <input
                type="checkbox"
                checked={sendImmediately}
                onChange={(e) => setSendImmediately(e.target.checked)}
                className="rounded border-slate-300"
              />
              Send initial email now
            </label>
            <button
              type="button"
              onClick={() => createMutation.mutate()}
              disabled={!title.trim() || !recipientEmail.trim() || createMutation.isPending}
              className="inline-flex items-center justify-center gap-1.5 px-4 py-2 rounded-lg bg-brand text-white text-xs font-medium hover:bg-brand-light disabled:opacity-50"
            >
              <Plus className="h-3.5 w-3.5" />
              {createMutation.isPending ? "Saving..." : "Set Reminder"}
            </button>
          </div>
        </div>

        {/* Reminders List */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-200 flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-3">
              {reminders.length > 0 && (
                <input
                  type="checkbox"
                  aria-label="Select All Reminders"
                  checked={allSelected}
                  onChange={() => setSelectedIds(allSelected ? [] : allIds)}
                  className="rounded border-slate-300"
                />
              )}
              <h3 className="text-sm font-semibold text-navy">
                My Personal Reminders ({reminders.length})
              </h3>
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

          {isLoading ? (
            <div className="p-8 text-center text-xs text-slate-400">Loading reminders...</div>
          ) : reminders.length === 0 ? (
            <div className="p-10 text-center text-xs text-slate-500">
              No personal reminders created yet. Add one above to receive emails twice a day until you mark it done.
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {reminders.map((rem) => (
                <div
                  key={rem.id}
                  className={`p-4 flex flex-wrap items-start justify-between gap-4 ${
                    rem.is_completed ? "bg-slate-50/70 opacity-75" : ""
                  }`}
                >
                  {editingId === rem.id ? (
                    <div className="w-full space-y-3 bg-slate-50 rounded-lg border border-slate-200 p-3.5">
                      <div className="grid grid-cols-1 md:grid-cols-6 gap-3">
                        <div className="md:col-span-2">
                          <label className="block text-[11px] font-medium text-slate-600 mb-1">
                            Reminder Title
                          </label>
                          <input
                            value={editTitle}
                            onChange={(e) => setEditTitle(e.target.value)}
                            className="w-full px-2.5 py-1.5 text-xs rounded border border-slate-300 bg-white"
                          />
                        </div>
                        <div className="md:col-span-2">
                          <label className="block text-[11px] font-medium text-slate-600 mb-1">
                            Personal Email
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
                            Morning (UTC)
                          </label>
                          <input
                            type="time"
                            value={editMorning}
                            onChange={(e) => setEditMorning(e.target.value)}
                            className="w-full px-2.5 py-1.5 text-xs rounded border border-slate-300 bg-white"
                          />
                        </div>
                        <div>
                          <label className="block text-[11px] font-medium text-slate-600 mb-1">
                            Evening (UTC)
                          </label>
                          <input
                            type="time"
                            value={editEvening}
                            onChange={(e) => setEditEvening(e.target.value)}
                            className="w-full px-2.5 py-1.5 text-xs rounded border border-slate-300 bg-white"
                          />
                        </div>
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <input
                          value={editNotes}
                          onChange={(e) => setEditNotes(e.target.value)}
                          placeholder="Notes / context..."
                          className="flex-1 min-w-[220px] px-2.5 py-1.5 text-xs rounded border border-slate-300 bg-white"
                        />
                        <button
                          type="button"
                          onClick={() => updateReminderMutation.mutate()}
                          disabled={!editTitle.trim() || !editEmail.trim() || updateReminderMutation.isPending}
                          className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-brand text-white text-xs font-medium hover:bg-brand-light disabled:opacity-50"
                        >
                          <Save className="h-3.5 w-3.5" />
                          {updateReminderMutation.isPending ? "Saving..." : "Save"}
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
                          aria-label={`Select ${rem.title}`}
                          checked={selectedIds.includes(rem.id)}
                          onChange={() =>
                            setSelectedIds((prev) =>
                              prev.includes(rem.id)
                                ? prev.filter((id) => id !== rem.id)
                                : [...prev, rem.id]
                            )
                          }
                          className="mt-1 rounded border-slate-300 shrink-0"
                        />
                        <div className="min-w-0 space-y-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <span
                              className={`text-sm font-semibold ${
                                rem.is_completed ? "line-through text-slate-500" : "text-navy"
                              }`}
                            >
                              {rem.title}
                            </span>
                            <span
                              className={`px-2 py-0.5 rounded-full text-[10px] font-medium border ${
                                rem.is_completed
                                  ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                                  : "bg-amber-50 text-amber-800 border-amber-200"
                              }`}
                            >
                              {rem.is_completed ? "Completed" : `Active · ${rem.morning_time} & ${rem.evening_time} UTC`}
                            </span>
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 text-[10px] font-medium">
                              <Mail className="h-2.5 w-2.5" /> Sent {rem.send_count}x
                            </span>
                          </div>
                          {rem.notes && <p className="text-xs text-slate-600">{rem.notes}</p>}
                          <div className="flex flex-wrap items-center gap-3 text-[11px] text-slate-500">
                            <span>To: <strong className="text-slate-700">{rem.recipient_email}</strong></span>
                            {rem.last_delivery_status && (
                              <span>
                                Last Status: <strong>{rem.last_delivery_status}</strong> ({rem.last_delivery_provider})
                              </span>
                            )}
                            {!rem.is_completed && rem.next_send_at && (
                              <span className="inline-flex items-center gap-1 text-navy">
                                <Clock className="h-3 w-3" /> Next Send: {formatDateTime(rem.next_send_at)}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>

                      <div className="flex flex-wrap items-center gap-2 shrink-0">
                        {!rem.is_completed && (
                          <button
                            type="button"
                            onClick={() => sendNowMutation.mutate(rem.id)}
                            disabled={sendNowMutation.isPending}
                            className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-slate-200 text-navy hover:bg-slate-50 text-xs font-medium"
                          >
                            <Send className="h-3.5 w-3.5" />
                            Send Now
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={() => startEditReminder(rem)}
                          className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-slate-200 text-navy hover:bg-slate-50 text-xs font-medium"
                        >
                          <Pencil className="h-3.5 w-3.5" />
                          Edit
                        </button>
                        <button
                          type="button"
                          onClick={() =>
                            toggleDoneMutation.mutate({ id: rem.id, is_completed: !rem.is_completed })
                          }
                          className={`inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border text-xs font-medium ${
                            rem.is_completed
                              ? "border-slate-300 bg-white text-slate-700 hover:bg-slate-50"
                              : "border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
                          }`}
                        >
                          {rem.is_completed ? (
                            <>
                              <RotateCcw className="h-3.5 w-3.5" /> Reopen
                            </>
                          ) : (
                            <>
                              <CheckCircle2 className="h-3.5 w-3.5" /> Mark Done
                            </>
                          )}
                        </button>
                        <button
                          type="button"
                          onClick={() => deleteMutation.mutate(rem.id)}
                          title="Delete Reminder"
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
