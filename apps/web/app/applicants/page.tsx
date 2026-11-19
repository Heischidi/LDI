"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Eye, Plus, Search, Trash2, X } from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { useAuth } from "@/hooks/use-auth";
import { ldiApi } from "@/lib/api-client";
import { formatDateTime, statusColorClasses } from "@/lib/utils";

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

  const { data: destinations = [] } = useQuery({
    queryKey: ["destinations"],
    queryFn: ldiApi.listDestinations,
  });
  const { data: purposes = [] } = useQuery({
    queryKey: ["purposes"],
    queryFn: ldiApi.listPurposes,
  });
  const { data: categories = [] } = useQuery({
    queryKey: ["categories"],
    queryFn: () => ldiApi.listCategories(),
  });

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

  const archiveMutation = useMutation({
    mutationFn: ldiApi.archiveApplicant,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["applicants"] }),
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
        hasRole("SUPER_ADMIN", "ADMIN", "OFFICER") ? (
          <button
            onClick={() => setShowNewModal(true)}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-brand text-white text-sm font-medium hover:bg-brand-light"
          >
            <Plus className="h-4 w-4" />
            New Applicant
          </button>
        ) : null
      }
    >
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
                  <td colSpan={7} className="px-4 py-10 text-center text-slate-400">
                    Loading applicants...
                  </td>
                </tr>
              )}
              {!isLoading && (data?.items.length ?? 0) === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-slate-500">
                    No applicants found. Click <strong>New Applicant</strong> to create one.
                  </td>
                </tr>
              )}
              {data?.items.map((app) => (
                <tr key={app.id} className="hover:bg-slate-50/70">
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
                  <td className="px-4 py-3 text-right space-x-2">
                    <Link
                      href={`/applicants/${app.id}`}
                      className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-slate-200 text-xs font-medium text-navy hover:bg-navy-50"
                    >
                      <Eye className="h-3.5 w-3.5" />
                      Open
                    </Link>
                    {hasRole("SUPER_ADMIN", "ADMIN") && (
                      <button
                        onClick={() => archiveMutation.mutate(app.id)}
                        title="Archive Applicant"
                        className="inline-flex items-center p-1.5 rounded-lg text-slate-400 hover:text-red-600 hover:bg-red-50"
                      >
                        <Trash2 className="h-4 w-4" />
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

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Destination *</label>
                  <select
                    required
                    value={destId}
                    onChange={(e) => setDestId(e.target.value)}
                    className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 bg-white"
                  >
                    <option value="">Select country...</option>
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
                    <option value="">Select purpose...</option>
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
                    <option value="">Select category...</option>
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
    </AppShell>
  );
}
