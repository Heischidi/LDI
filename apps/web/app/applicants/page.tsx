"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Eye, Pencil, Plus, Search, Send, Trash2, X } from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { useAuth } from "@/hooks/use-auth";
import { ldiApi } from "@/lib/api-client";
import { formatDateTime, statusColorClasses } from "@/lib/utils";
import type { ApplicantSummary } from "@/types";

export default function ApplicantsPage() {
  const { hasRole } = useAuth();
  const router = useRouter();
  const qc = useQueryClient();

  const [search, setSearch] = useState("");
  const [destinationFilter, setDestinationFilter] = useState("");
  const [purposeFilter, setPurposeFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [showNewModal, setShowNewModal] = useState(false);

  // Form state for New Applicant
  const [firstName, setFirstName] = useState("");
  const [middleName, setMiddleName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [nationality, setNationality] = useState("Nigerian");
  const [passportNo, setPassportNo] = useState("");
  const [destId, setDestId] = useState("");
  const [purposeId, setPurposeId] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const queryStr = new URLSearchParams({
    ...(search ? { search } : {}),
    ...(destinationFilter ? { destination_id: destinationFilter } : {}),
    ...(purposeFilter ? { purpose_id: purposeFilter } : {}),
    ...(statusFilter ? { status: statusFilter } : {}),
  }).toString();

  const { data, isLoading } = useQuery({
    queryKey: ["applicants", queryStr],
    queryFn: () => ldiApi.listApplicants(queryStr ? `?${queryStr}` : ""),
  });

  const {
    data: destinations = [],
    isLoading: destLoading,
    isError: destIsError,
    error: destError,
    refetch: refetchDestinations,
  } = useQuery({
    queryKey: ["destinations"],
    queryFn: ldiApi.listDestinations,
    retry: 3,
    retryDelay: (attempt) => Math.min(1500 * 2 ** attempt, 8000),
  });
  const {
    data: purposes = [],
    isLoading: purpLoading,
    isError: purpIsError,
    error: purpError,
    refetch: refetchPurposes,
  } = useQuery({
    queryKey: ["purposes"],
    queryFn: ldiApi.listPurposes,
    retry: 3,
    retryDelay: (attempt) => Math.min(1500 * 2 ** attempt, 8000),
  });
  const {
    data: categories = [],
    isLoading: catLoading,
    isError: catIsError,
    error: catError,
    refetch: refetchCategories,
  } = useQuery({
    queryKey: ["categories"],
    queryFn: () => ldiApi.listCategories(),
    retry: 3,
    retryDelay: (attempt) => Math.min(1500 * 2 ** attempt, 8000),
  });

  const refLoading = destLoading || purpLoading || catLoading;
  const refError = destIsError || purpIsError || catIsError;
  const refErrorMessage =
    (destError instanceof Error && destError.message) ||
    (purpError instanceof Error && purpError.message) ||
    (catError instanceof Error && catError.message) ||
    "";
  const isAuthError = /401|credential|token|unauthori/i.test(refErrorMessage);

  const reloadReferenceData = () => {
    void refetchDestinations();
    void refetchPurposes();
    void refetchCategories();
  };

  const openNewApplicantModal = () => {
    setShowNewModal(true);
    if (destinations.length === 0 || purposes.length === 0 || categories.length === 0) {
      reloadReferenceData();
    }
  };

  const referenceAlert =
    !refLoading &&
    (refError || destinations.length === 0 || purposes.length === 0 || categories.length === 0) ? (
      <div className="rounded-lg bg-amber-50 border border-amber-200 px-3.5 py-2.5 text-xs text-amber-900 flex flex-wrap items-center justify-between gap-2">
        <span>
          {isAuthError
            ? "Your session expired. Please sign in again to load countries, purposes, and visa categories."
            : "Countries, purposes, or categories did not finish loading (the API server may have been waking up)."}
        </span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={reloadReferenceData}
            className="px-2.5 py-1 rounded bg-navy text-white font-medium hover:bg-navy-700"
          >
            Reload Countries &amp; Categories
          </button>
          {isAuthError && (
            <Link
              href="/login"
              className="px-2.5 py-1 rounded border border-amber-400 bg-white text-amber-900 font-medium"
            >
              Sign In Again
            </Link>
          )}
        </div>
      </div>
    ) : null;

  const { data: matchedChecklist } = useQuery({
    queryKey: ["match-checklist", destId, purposeId, categoryId],
    queryFn: () => ldiApi.matchRequirementSet(destId, purposeId, categoryId),
    enabled: Boolean(destId && purposeId && categoryId),
  });

  const createMutation = useMutation({
    mutationFn: ldiApi.createApplicant,
    onSuccess: (created) => {
      qc.invalidateQueries({ queryKey: ["applicants"] });
      setShowNewModal(false);
      router.push(`/applicants/${created.id}`);
    },
    onError: (err) => {
      setFormError(err instanceof Error ? err.message : "Failed to create applicant");
    },
  });

  const [selectedIds, setSelectedIds] = useState<string[]>([]);

  const archiveMutation = useMutation({
    mutationFn: ldiApi.archiveApplicant,
    onSuccess: (_res, id) => {
      setSelectedIds((prev) => prev.filter((item) => item !== id));
      qc.invalidateQueries({ queryKey: ["applicants"] });
      qc.invalidateQueries({ queryKey: ["dashboard-metrics"] });
    },
  });

  const batchDeleteMutation = useMutation({
    mutationFn: (ids: string[]) => ldiApi.batchDeleteApplicants(ids),
    onSuccess: () => {
      setSelectedIds([]);
      qc.invalidateQueries({ queryKey: ["applicants"] });
      qc.invalidateQueries({ queryKey: ["dashboard-metrics"] });
    },
  });

  const visibleIds = (data?.items || []).map((a) => a.id);
  const allVisibleSelected = visibleIds.length > 0 && visibleIds.every((id) => selectedIds.includes(id));
  const toggleSelectAll = () => {
    setSelectedIds(allVisibleSelected ? [] : visibleIds);
  };
  const toggleSelectOne = (id: string) => {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  };
  const canDelete = hasRole("SUPER_ADMIN", "ADMIN", "OFFICER");

  const [editingApp, setEditingApp] = useState<ApplicantSummary | null>(null);
  const [editForm, setEditForm] = useState({
    first_name: "",
    middle_name: "",
    last_name: "",
    email: "",
    phone_number: "",
    nationality: "",
    passport_number: "",
    destination_id: "",
    purpose_id: "",
    category_id: "",
    status: "NEW",
  });
  const [editError, setEditError] = useState<string | null>(null);

  const openEditApplicant = (app: ApplicantSummary) => {
    setEditingApp(app);
    setEditError(null);
    if (destinations.length === 0 || purposes.length === 0 || categories.length === 0) {
      reloadReferenceData();
    }
    setEditForm({
      first_name: app.first_name,
      middle_name: app.middle_name || "",
      last_name: app.last_name,
      email: app.email,
      phone_number: app.phone_number,
      nationality: app.nationality,
      passport_number: "",
      destination_id: app.destination.id,
      purpose_id: app.purpose.id,
      category_id: app.category.id,
      status: app.status,
    });
  };

  const updateApplicantMutation = useMutation({
    mutationFn: () => {
      if (!editingApp) throw new Error("No applicant selected.");
      const payload: Record<string, unknown> = {
        first_name: editForm.first_name.trim(),
        middle_name: editForm.middle_name.trim() || null,
        last_name: editForm.last_name.trim(),
        email: editForm.email.trim(),
        phone_number: editForm.phone_number.trim(),
        nationality: editForm.nationality.trim(),
        destination_id: editForm.destination_id,
        purpose_id: editForm.purpose_id,
        category_id: editForm.category_id,
        status: editForm.status,
      };
      if (editForm.passport_number.trim()) {
        payload.passport_number = editForm.passport_number.trim();
      }
      return ldiApi.updateApplicant(editingApp.id, payload);
    },
    onSuccess: () => {
      setEditingApp(null);
      setEditError(null);
      qc.invalidateQueries({ queryKey: ["applicants"] });
      qc.invalidateQueries({ queryKey: ["dashboard-metrics"] });
    },
    onError: (err) => {
      setEditError(err instanceof Error ? err.message : "Failed to update applicant");
    },
  });

  const [updatingApp, setUpdatingApp] = useState<ApplicantSummary | null>(null);
  const [quickStep, setQuickStep] = useState("");
  const [quickNote, setQuickNote] = useState("");
  const [quickIncludeMissing, setQuickIncludeMissing] = useState(false);
  const [quickBanner, setQuickBanner] = useState<string | null>(null);

  const openQuickUpdate = (app: ApplicantSummary) => {
    setUpdatingApp(app);
    setQuickStep("");
    setQuickNote("");
    setQuickIncludeMissing(false);
  };

  const quickUpdateMutation = useMutation({
    mutationFn: () => {
      if (!updatingApp) throw new Error("No applicant selected.");
      const headline = quickStep.trim();
      return ldiApi.sendStageUpdate(updatingApp.id, {
        track: "LIVE_UPDATE",
        stage_code: "CUSTOM_UPDATE",
        stage_label: headline,
        subject: `Application Update: ${headline} — ${updatingApp.application_reference}`,
        message_body: quickNote.trim() || undefined,
        include_missing_checklist: quickIncludeMissing,
        update_applicant_status: true,
      });
    },
    onSuccess: (res) => {
      setUpdatingApp(null);
      setQuickStep("");
      setQuickNote("");
      setQuickBanner(
        `Live update "${res.stage_label}" emailed to ${res.recipient_email} (${res.delivery_status}).`
      );
      qc.invalidateQueries({ queryKey: ["applicants"] });
    },
  });

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    createMutation.mutate({
      first_name: firstName,
      middle_name: middleName || null,
      last_name: lastName,
      email,
      phone_number: phone,
      nationality,
      passport_number: passportNo || null,
      destination_id: destId,
      purpose_id: purposeId,
      category_id: categoryId,
    });
  };

  return (
    <AppShell
      title="Applicants"
      subtitle="Manage client records, assigned travel checklists, and document processing status."
      actions={
        <div className="flex flex-wrap items-center gap-2">
          {canDelete && selectedIds.length > 0 && (
            <button
              type="button"
              onClick={() => batchDeleteMutation.mutate(selectedIds)}
              disabled={batchDeleteMutation.isPending}
              className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg bg-red-600 text-white text-sm font-medium hover:bg-red-700 disabled:opacity-60"
            >
              <Trash2 className="h-4 w-4" />
              {batchDeleteMutation.isPending
                ? "Deleting..."
                : `Delete Selected (${selectedIds.length})`}
            </button>
          )}
          {canDelete && (
            <button
              onClick={openNewApplicantModal}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-brand text-white text-sm font-medium hover:bg-brand-light"
            >
              <Plus className="h-4 w-4" />
              New Applicant
            </button>
          )}
        </div>
      }
    >
      {quickBanner && (
        <div className="mb-4 rounded-xl bg-emerald-50 border border-emerald-200 px-4 py-3 text-xs text-emerald-800 flex items-center justify-between">
          <span>{quickBanner}</span>
          <button type="button" onClick={() => setQuickBanner(null)} className="underline">
            Dismiss
          </button>
        </div>
      )}

      {/* Filters Bar */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 mb-5 flex flex-wrap items-center gap-3 shadow-sm">
        <div className="relative flex-1 min-w-[220px]">
          <Search className="h-4 w-4 text-slate-400 absolute left-3 top-2.5" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by name, reference (LDI-...), or email..."
            className="w-full pl-9 pr-3 py-2 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-navy/20"
          />
        </div>
        <select
          value={destinationFilter}
          onChange={(e) => setDestinationFilter(e.target.value)}
          className="px-3 py-2 text-sm rounded-lg border border-slate-300 bg-white"
        >
          <option value="">All Destinations</option>
          {destinations.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </select>
        <select
          value={purposeFilter}
          onChange={(e) => setPurposeFilter(e.target.value)}
          className="px-3 py-2 text-sm rounded-lg border border-slate-300 bg-white"
        >
          <option value="">All Purposes</option>
          {purposes.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-3 py-2 text-sm rounded-lg border border-slate-300 bg-white"
        >
          <option value="">All Statuses</option>
          <option value="DRAFT">Draft</option>
          <option value="DOCUMENTS_UPLOADED">Documents Uploaded</option>
          <option value="AWAITING_REVIEW">Awaiting Review</option>
          <option value="APPROVED">Approved</option>
          <option value="COMPLETED">Completed</option>
        </select>
      </div>

      {/* Applicants Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-600 uppercase">
              <tr>
                {canDelete && (
                  <th className="px-4 py-3 w-10">
                    <input
                      type="checkbox"
                      aria-label="Select All Applicants"
                      checked={allVisibleSelected}
                      onChange={toggleSelectAll}
                      className="rounded border-slate-300"
                    />
                  </th>
                )}
                <th className="px-4 py-3">Reference</th>
                <th className="px-4 py-3">Applicant</th>
                <th className="px-4 py-3">Travel Profile</th>
                <th className="px-4 py-3">Documents / Missing</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Created</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {isLoading && (
                <tr>
                  <td colSpan={canDelete ? 8 : 7} className="px-4 py-10 text-center text-slate-400">
                    Loading applicants...
                  </td>
                </tr>
              )}
              {!isLoading && (data?.items.length ?? 0) === 0 && (
                <tr>
                  <td colSpan={canDelete ? 8 : 7} className="px-4 py-12 text-center text-slate-500">
                    No applicants found. Click <strong>New Applicant</strong> to create one.
                  </td>
                </tr>
              )}
              {data?.items.map((app) => (
                <tr key={app.id} className="hover:bg-slate-50/70">
                  {canDelete && (
                    <td className="px-4 py-3">
                      <input
                        type="checkbox"
                        aria-label={`Select ${app.full_name}`}
                        checked={selectedIds.includes(app.id)}
                        onChange={() => toggleSelectOne(app.id)}
                        className="rounded border-slate-300"
                      />
                    </td>
                  )}
                  <td className="px-4 py-3 font-mono text-xs font-semibold text-navy">
                    {app.application_reference}
                  </td>
                  <td className="px-4 py-3">
                    <div className="font-medium text-slate-900">{app.full_name}</div>
                    <div className="text-xs text-slate-500">{app.email}</div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="text-slate-800">{app.destination.name}</div>
                    <div className="text-xs text-slate-500">
                      {app.purpose.name} · {app.category.name}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-xs">
                    <span className="font-semibold text-slate-800">{app.document_count}</span> uploaded
                    {app.missing_required_count > 0 && (
                      <span className="ml-2 text-red-600 font-medium">
                        ({app.missing_required_count} missing)
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`px-2.5 py-0.5 rounded-full text-xs font-medium border ${statusColorClasses(app.status)}`}
                    >
                      {app.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-500">
                    {formatDateTime(app.created_at)}
                  </td>
                  <td className="px-4 py-3 text-right space-x-2 whitespace-nowrap">
                    <Link
                      href={`/applicants/${app.id}`}
                      className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-slate-200 text-xs font-medium text-navy hover:bg-navy-50"
                    >
                      <Eye className="h-3.5 w-3.5" />
                      Open
                    </Link>
                    {canDelete && (
                      <button
                        type="button"
                        onClick={() => openQuickUpdate(app)}
                        title="Send Live Client Email Update"
                        className="inline-flex items-center gap-1 px-2 py-1.5 rounded-lg border border-brand/30 bg-emerald-50 text-xs font-medium text-brand hover:bg-emerald-100"
                      >
                        <Send className="h-3.5 w-3.5" />
                        Update
                      </button>
                    )}
                    {canDelete && (
                      <button
                        type="button"
                        onClick={() => openEditApplicant(app)}
                        title="Edit Applicant"
                        className="inline-flex items-center gap-1 px-2 py-1.5 rounded-lg border border-slate-200 text-xs font-medium text-navy hover:bg-slate-100"
                      >
                        <Pencil className="h-3.5 w-3.5" />
                        Edit
                      </button>
                    )}
                    {canDelete && (
                      <button
                        type="button"
                        onClick={() => archiveMutation.mutate(app.id)}
                        title="Delete Applicant"
                        className="inline-flex items-center gap-1 px-2 py-1.5 rounded-lg border border-red-200 bg-red-50 text-xs font-medium text-red-700 hover:bg-red-100"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
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

      {/* New Applicant Modal */}
      {showNewModal && (
        <div className="fixed inset-0 z-50 bg-slate-950/50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl border border-slate-200 max-w-2xl w-full max-h-[90vh] overflow-y-auto shadow-xl">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-navy">New Applicant Record</h2>
                <p className="text-xs text-slate-500">
                  Select travel profile to load the configured document checklist automatically.
                </p>
              </div>
              <button
                onClick={() => setShowNewModal(false)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleCreate} className="p-6 space-y-4">
              {formError && (
                <div className="rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-700">
                  {formError}
                </div>
              )}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">First Name *</label>
                  <input
                    required
                    value={firstName}
                    onChange={(e) => setFirstName(e.target.value)}
                    placeholder="John"
                    className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Middle Name</label>
                  <input
                    value={middleName}
                    onChange={(e) => setMiddleName(e.target.value)}
                    className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Last Name *</label>
                  <input
                    required
                    value={lastName}
                    onChange={(e) => setLastName(e.target.value)}
                    placeholder="Doe"
                    className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Email *</label>
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="john.doe@example.com"
                    className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Phone Number *</label>
                  <input
                    required
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    placeholder="+2348011223344"
                    className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Nationality *</label>
                  <input
                    required
                    value={nationality}
                    onChange={(e) => setNationality(e.target.value)}
                    className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Passport Number</label>
                  <input
                    value={passportNo}
                    onChange={(e) => setPassportNo(e.target.value)}
                    placeholder="Optional (encrypted at rest)"
                    className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300"
                  />
                </div>
              </div>

              {referenceAlert}

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Destination *</label>
                  <select
                    required
                    value={destId}
                    onChange={(e) => setDestId(e.target.value)}
                    className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 bg-white"
                  >
                    <option value="">
                      {destLoading ? "Loading countries..." : "Select country..."}
                    </option>
                    {destinations.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Purpose *</label>
                  <select
                    required
                    value={purposeId}
                    onChange={(e) => setPurposeId(e.target.value)}
                    className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 bg-white"
                  >
                    <option value="">
                      {purpLoading ? "Loading purposes..." : "Select purpose..."}
                    </option>
                    {purposes.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Category *</label>
                  <select
                    required
                    value={categoryId}
                    onChange={(e) => setCategoryId(e.target.value)}
                    className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 bg-white"
                  >
                    <option value="">
                      {catLoading ? "Loading categories..." : "Select category..."}
                    </option>
                    {categories.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Dynamic Checklist Preview */}
              {matchedChecklist?.active_version && (
                <div className="rounded-xl bg-slate-50 border border-slate-200 p-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-semibold text-navy">
                      Matched Checklist: {matchedChecklist.name} (v
                      {matchedChecklist.active_version.version_number})
                    </span>
                    <span className="text-xs text-brand font-medium">
                      {matchedChecklist.active_version.items.length} documents configured
                    </span>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5 text-xs text-slate-700">
                    {matchedChecklist.active_version.items.map((item) => (
                      <div key={item.id} className="flex items-center gap-1.5">
                        <span className="font-mono text-[11px] text-slate-400">
                          {String(item.display_order).padStart(2, "0")}.
                        </span>
                        <span className="truncate">{item.document_type_name}</span>
                        <span className="text-[10px] px-1.5 rounded bg-white border border-slate-200 text-slate-500">
                          {item.requirement_level}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="flex justify-end gap-2 pt-3 border-t border-slate-200">
                <button
                  type="button"
                  onClick={() => setShowNewModal(false)}
                  className="px-4 py-2 rounded-lg border border-slate-300 text-sm text-slate-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createMutation.isPending}
                  className="px-4 py-2 rounded-lg bg-brand text-white text-sm font-medium hover:bg-brand-light disabled:opacity-60"
                >
                  {createMutation.isPending ? "Creating..." : "Create Applicant & Load Checklist"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {editingApp && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-navy">Edit Applicant Record</h2>
                <p className="text-xs text-slate-500">{editingApp.application_reference}</p>
              </div>
              <button
                type="button"
                onClick={() => setEditingApp(null)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                setEditError(null);
                updateApplicantMutation.mutate();
              }}
              className="p-6 space-y-4 text-sm"
            >
              {editError && (
                <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-xs text-red-700">
                  {editError}
                </div>
              )}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">First Name *</label>
                  <input
                    required
                    value={editForm.first_name}
                    onChange={(e) => setEditForm((f) => ({ ...f, first_name: e.target.value }))}
                    className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Middle Name</label>
                  <input
                    value={editForm.middle_name}
                    onChange={(e) => setEditForm((f) => ({ ...f, middle_name: e.target.value }))}
                    className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Last Name *</label>
                  <input
                    required
                    value={editForm.last_name}
                    onChange={(e) => setEditForm((f) => ({ ...f, last_name: e.target.value }))}
                    className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300"
                  />
                </div>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Email *</label>
                  <input
                    type="email"
                    required
                    value={editForm.email}
                    onChange={(e) => setEditForm((f) => ({ ...f, email: e.target.value }))}
                    className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Phone Number *</label>
                  <input
                    required
                    value={editForm.phone_number}
                    onChange={(e) => setEditForm((f) => ({ ...f, phone_number: e.target.value }))}
                    className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300"
                  />
                </div>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Nationality *</label>
                  <input
                    required
                    value={editForm.nationality}
                    onChange={(e) => setEditForm((f) => ({ ...f, nationality: e.target.value }))}
                    className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">
                    Update Passport No. (Optional)
                  </label>
                  <input
                    value={editForm.passport_number}
                    onChange={(e) => setEditForm((f) => ({ ...f, passport_number: e.target.value }))}
                    placeholder="Leave blank to keep existing"
                    className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Status</label>
                  <select
                    value={editForm.status}
                    onChange={(e) => setEditForm((f) => ({ ...f, status: e.target.value }))}
                    className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 bg-white"
                  >
                    <option value="NEW">NEW</option>
                    <option value="PROCESSING">PROCESSING</option>
                    <option value="IN_REVIEW">IN_REVIEW</option>
                    <option value="MISSING_DOCUMENTS">MISSING_DOCUMENTS</option>
                    <option value="READY_FOR_EXPORT">READY_FOR_EXPORT</option>
                    <option value="COMPLETED">COMPLETED</option>
                  </select>
                </div>
              </div>
              {referenceAlert}

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Destination *</label>
                  <select
                    required
                    value={editForm.destination_id}
                    onChange={(e) => setEditForm((f) => ({ ...f, destination_id: e.target.value }))}
                    className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 bg-white"
                  >
                    {destinations.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Purpose *</label>
                  <select
                    required
                    value={editForm.purpose_id}
                    onChange={(e) => setEditForm((f) => ({ ...f, purpose_id: e.target.value }))}
                    className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 bg-white"
                  >
                    {purposes.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Category *</label>
                  <select
                    required
                    value={editForm.category_id}
                    onChange={(e) => setEditForm((f) => ({ ...f, category_id: e.target.value }))}
                    className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 bg-white"
                  >
                    {categories.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="flex justify-end gap-2 pt-3 border-t border-slate-200">
                <button
                  type="button"
                  onClick={() => setEditingApp(null)}
                  className="px-4 py-2 rounded-lg border border-slate-300 text-sm text-slate-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={updateApplicantMutation.isPending}
                  className="px-4 py-2 rounded-lg bg-brand text-white text-sm font-medium hover:bg-brand-light disabled:opacity-60"
                >
                  {updateApplicantMutation.isPending ? "Saving..." : "Save Changes"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {updatingApp && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-2xl w-full max-w-lg overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-navy">Send Live Client Email Update</h3>
                <p className="text-[11px] text-slate-500 mt-0.5">
                  {updatingApp.full_name} ({updatingApp.application_reference}) · To: {updatingApp.email}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setUpdatingApp(null)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                quickUpdateMutation.mutate();
              }}
              className="p-5 space-y-3 text-xs"
            >
              <div>
                <label className="block font-medium text-slate-700 mb-1">
                  Process Step Completed *
                </label>
                <input
                  required
                  value={quickStep}
                  onChange={(e) => setQuickStep(e.target.value)}
                  placeholder="e.g. Visa documents collected"
                  className="w-full px-3 py-2 rounded-lg border border-slate-300"
                />
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {[
                    "Visa documents collected",
                    "Admission application submitted",
                    "Offer letter received",
                    "Visa application submitted",
                    "Biometrics completed",
                    "Passport ready for collection",
                  ].map((chip) => (
                    <button
                      key={chip}
                      type="button"
                      onClick={() => setQuickStep(chip)}
                      className="px-2 py-0.5 rounded-full bg-slate-100 hover:bg-emerald-50 hover:text-emerald-800 border border-slate-200 text-[11px] text-slate-700"
                    >
                      {chip}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block font-medium text-slate-700 mb-1">
                  Additional Note to Client (Optional)
                </label>
                <textarea
                  rows={3}
                  value={quickNote}
                  onChange={(e) => setQuickNote(e.target.value)}
                  placeholder="Leave blank to send an automatic confirmation email with their live tracker link..."
                  className="w-full px-3 py-2 rounded-lg border border-slate-300"
                />
              </div>

              <label className="inline-flex items-center gap-2 cursor-pointer text-slate-700">
                <input
                  type="checkbox"
                  checked={quickIncludeMissing}
                  onChange={(e) => setQuickIncludeMissing(e.target.checked)}
                />
                Include outstanding missing checklist documents
              </label>

              {updatingApp.tracking_token && (
                <div className="rounded-lg bg-slate-50 border border-slate-200 px-3 py-2 text-[11px] text-slate-500 truncate">
                  Tracker link automatically included in email:{" "}
                  <span className="font-mono text-navy">/track/{updatingApp.tracking_token}</span>
                </div>
              )}

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-200">
                <button
                  type="button"
                  onClick={() => setUpdatingApp(null)}
                  className="px-3.5 py-2 rounded-lg border border-slate-300 text-slate-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!quickStep.trim() || quickUpdateMutation.isPending}
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-brand text-white font-medium hover:bg-brand-light disabled:opacity-60"
                >
                  <Send className="h-3.5 w-3.5" />
                  {quickUpdateMutation.isPending ? "Sending..." : "Send Live Update"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </AppShell>
  );
}
