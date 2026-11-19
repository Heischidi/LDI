"use client";

import React, { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Save, Tag } from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { useAuth } from "@/hooks/use-auth";
import { ldiApi } from "@/lib/api-client";

export default function RequirementsManagerPage() {
  const { hasRole } = useAuth();
  const qc = useQueryClient();
  const canEdit = hasRole("SUPER_ADMIN", "ADMIN");

  const { data: reqSets = [], isLoading } = useQuery({
    queryKey: ["requirement-sets"],
    queryFn: ldiApi.listRequirements,
  });
  const { data: docTypes = [] } = useQuery({
    queryKey: ["document-types"],
    queryFn: ldiApi.listDocumentTypes,
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

  const [selectedSetId, setSelectedSetId] = useState<string | null>(null);
  const [newNaming, setNewNaming] = useState("");
  const [newDocName, setNewDocName] = useState("");
  const [newDocCode, setNewDocCode] = useState("");
  const [newDocAliases, setNewDocAliases] = useState("");
  const [showNewSet, setShowNewSet] = useState(false);

  const [setName, setSetName] = useState("");
  const [setDest, setSetDest] = useState("");
  const [setPurpose, setSetPurpose] = useState("");
  const [setCategory, setSetCategory] = useState("");

  const activeSet = reqSets.find((s) => s.id === selectedSetId) || reqSets[0];

  const updateSetMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Record<string, unknown> }) =>
      ldiApi.updateRequirementSet(id, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["requirement-sets"] }),
  });

  const createTypeMutation = useMutation({
    mutationFn: ldiApi.createDocumentType,
    onSuccess: () => {
      setNewDocName("");
      setNewDocCode("");
      setNewDocAliases("");
      qc.invalidateQueries({ queryKey: ["document-types"] });
    },
  });

  const createSetMutation = useMutation({
    mutationFn: ldiApi.createRequirementSet,
    onSuccess: (created) => {
      setShowNewSet(false);
      setSelectedSetId(created.id);
      qc.invalidateQueries({ queryKey: ["requirement-sets"] });
    },
  });

  const addItemToActiveSet = (docTypeId: string, level: "REQUIRED" | "OPTIONAL" | "CONDITIONAL") => {
    if (!activeSet?.active_version) return;
    const existingItems = activeSet.active_version.items.map((i) => ({
      document_type_id: i.document_type_id,
      requirement_level: i.requirement_level,
      display_order: i.display_order,
      condition_explanation: i.condition_explanation,
      min_validity_days: i.min_validity_days,
      custom_instructions: i.custom_instructions,
    }));
    existingItems.push({
      document_type_id: docTypeId,
      requirement_level: level,
      display_order: existingItems.length + 1,
      condition_explanation: level === "CONDITIONAL" ? "Conditional eligibility requirement" : null,
      min_validity_days: null,
      custom_instructions: null,
    });
    updateSetMutation.mutate({
      id: activeSet.id,
      payload: {
        change_notes: `Added requirement item (creates new version)`,
        items: existingItems,
      },
    });
  };

  return (
    <AppShell
      title="Requirements Manager"
      subtitle="Configure destination/purpose checklists, conditional rules, document aliases, and naming conventions without modifying historical records."
      actions={
        canEdit ? (
          <button
            onClick={() => setShowNewSet(!showNewSet)}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-brand text-white text-sm font-medium hover:bg-brand-light"
          >
            <Plus className="h-4 w-4" />
            New Requirement Set
          </button>
        ) : null
      }
    >
      {showNewSet && canEdit && (
        <div className="bg-white rounded-xl border border-slate-200 p-5 mb-6 shadow-sm">
          <h3 className="text-sm font-semibold text-navy mb-3">Create Requirement Set</h3>
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 mb-3">
            <input
              placeholder="Checklist Name (e.g. Germany Study)"
              value={setName}
              onChange={(e) => setSetName(e.target.value)}
              className="px-3 py-2 text-sm rounded-lg border border-slate-300"
            />
            <select
              value={setDest}
              onChange={(e) => setSetDest(e.target.value)}
              className="px-3 py-2 text-sm rounded-lg border border-slate-300 bg-white"
            >
              <option value="">Destination...</option>
              {destinations.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
            <select
              value={setPurpose}
              onChange={(e) => setSetPurpose(e.target.value)}
              className="px-3 py-2 text-sm rounded-lg border border-slate-300 bg-white"
            >
              <option value="">Purpose...</option>
              {purposes.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
            <select
              value={setCategory}
              onChange={(e) => setSetCategory(e.target.value)}
              className="px-3 py-2 text-sm rounded-lg border border-slate-300 bg-white"
            >
              <option value="">Category...</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
          <button
            onClick={() =>
              createSetMutation.mutate({
                name: setName,
                destination_id: setDest,
                purpose_id: setPurpose,
                category_id: setCategory,
                items: docTypes[0]
                  ? [{ document_type_id: docTypes[0].id, requirement_level: "REQUIRED", display_order: 1 }]
                  : [],
              })
            }
            disabled={!setName || !setDest || !setPurpose || !setCategory}
            className="px-4 py-2 rounded-lg bg-navy text-white text-xs font-medium disabled:opacity-50"
          >
            Save Requirement Set
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Requirement Sets List */}
        <div className="space-y-3">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Configured Checklists ({reqSets.length})
          </h3>
          {isLoading ? (
            <div className="h-32 rounded-xl bg-white border border-slate-200 animate-pulse" />
          ) : (
            reqSets.map((rs) => (
              <button
                key={rs.id}
                onClick={() => {
                  setSelectedSetId(rs.id);
                  setNewNaming(rs.naming_convention);
                }}
                className={`w-full text-left p-4 rounded-xl border transition-all ${
                  activeSet?.id === rs.id
                    ? "bg-white border-navy ring-2 ring-navy/10 shadow-sm"
                    : "bg-white border-slate-200 hover:border-slate-300"
                }`}
              >
                <div className="font-semibold text-sm text-navy">{rs.name}</div>
                <div className="text-xs text-slate-500 mt-1">
                  {rs.destination_name} · {rs.purpose_name} · {rs.category_name}
                </div>
                <div className="text-[11px] text-brand font-medium mt-2">
                  Active Version v{rs.active_version?.version_number || 1} ·{" "}
                  {rs.active_version?.items.length || 0} rules
                </div>
              </button>
            ))
          )}
        </div>

        {/* Active Requirement Set Editor + Document Types/Aliases */}
        <div className="lg:col-span-2 space-y-6">
          {activeSet && (
            <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm space-y-4">
              <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-200 pb-4">
                <div>
                  <h2 className="text-base font-semibold text-navy">{activeSet.name}</h2>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Version {activeSet.active_version?.version_number} · Folder template:{" "}
                    <code className="text-[11px] bg-slate-100 px-1.5 py-0.5 rounded">
                      {activeSet.folder_template}
                    </code>
                  </p>
                </div>
              </div>

              {/* Naming Convention Config */}
              <div className="flex flex-wrap items-end gap-3 bg-slate-50 p-3.5 rounded-lg border border-slate-200">
                <div className="flex-1 min-w-[240px]">
                  <label className="block text-xs font-medium text-slate-700 mb-1">
                    Document Naming Convention
                  </label>
                  <select
                    disabled={!canEdit}
                    value={newNaming || activeSet.naming_convention}
                    onChange={(e) => setNewNaming(e.target.value)}
                    className="w-full px-3 py-1.5 text-xs rounded border border-slate-300 bg-white font-mono"
                  >
                    <option value="{document_order}_{document_type}.{extension}">
                      {"{document_order}_{document_type}.{extension}"} (Default: 01_International_Passport.pdf)
                    </option>
                    <option value="{applicant_name}_{document_type}_{date}.{extension}">
                      {"{applicant_name}_{document_type}_{date}.{extension}"} (John_Doe_International_Passport_2026.pdf)
                    </option>
                  </select>
                </div>
                {canEdit && (
                  <button
                    onClick={() =>
                      updateSetMutation.mutate({
                        id: activeSet.id,
                        payload: { naming_convention: newNaming || activeSet.naming_convention },
                      })
                    }
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-navy text-white text-xs font-medium"
                  >
                    <Save className="h-3.5 w-3.5" />
                    Save Convention
                  </button>
                )}
              </div>

              {/* Checklist Rules Table */}
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 uppercase">
                    <tr>
                      <th className="px-3 py-2">Order</th>
                      <th className="px-3 py-2">Document Type</th>
                      <th className="px-3 py-2">Requirement</th>
                      <th className="px-3 py-2">Min Validity</th>
                      <th className="px-3 py-2">Instructions / Condition</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {activeSet.active_version?.items.map((item) => (
                      <tr key={item.id}>
                        <td className="px-3 py-2 font-mono text-slate-500">{item.display_order}</td>
                        <td className="px-3 py-2 font-medium text-slate-900">
                          {item.document_type_name}
                        </td>
                        <td className="px-3 py-2">
                          <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-700 font-medium">
                            {item.requirement_level}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-slate-600">
                          {item.min_validity_days ? `${item.min_validity_days} days` : "—"}
                        </td>
                        <td className="px-3 py-2 text-slate-500">
                          {item.condition_explanation || item.custom_instructions || "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {canEdit && (
                <div className="pt-3 border-t border-slate-200 flex flex-wrap items-center gap-2 text-xs">
                  <span className="text-slate-600 font-medium">Quick-append rule (creates new version):</span>
                  <select
                    onChange={(e) => {
                      if (e.target.value) {
                        addItemToActiveSet(e.target.value, "REQUIRED");
                        e.target.value = "";
                      }
                    }}
                    className="px-2.5 py-1.5 rounded border border-slate-300 bg-white"
                  >
                    <option value="">+ Add Required Document...</option>
                    {docTypes.map((dt) => (
                      <option key={dt.id} value={dt.id}>
                        {dt.name}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {/* Version History */}
              <div className="pt-3 border-t border-slate-200">
                <h4 className="text-xs font-semibold text-navy mb-2">Version History (Immutable Snapshots)</h4>
                <div className="space-y-1 text-xs text-slate-600">
                  {activeSet.versions_summary.map((v) => (
                    <div key={v.id} className="flex justify-between py-1">
                      <span>
                        <strong>v{v.version_number}</strong> — {v.change_notes || "Update"} ({v.item_count} items)
                      </span>
                      <span className="text-slate-400">
                        {new Date(v.effective_from).toLocaleDateString()}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Canonical Document Types & Aliases */}
          <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm space-y-4">
            <h3 className="text-sm font-semibold text-navy">
              Canonical Document Types &amp; Aliases ({docTypes.length})
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-h-64 overflow-y-auto pr-1">
              {docTypes.map((dt) => (
                <div key={dt.id} className="p-3 rounded-lg border border-slate-200 bg-slate-50/50 text-xs">
                  <div className="font-semibold text-navy">{dt.name}</div>
                  <div className="font-mono text-[10px] text-slate-400">{dt.code}</div>
                  {dt.aliases.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-2">
                      {dt.aliases.map((al) => (
                        <span
                          key={al.id}
                          className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-white border border-slate-200 text-[10px] text-slate-600"
                        >
                          <Tag className="h-2.5 w-2.5" />
                          {al.alias_name}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>

            {canEdit && (
              <div className="pt-3 border-t border-slate-200 grid grid-cols-1 sm:grid-cols-4 gap-2">
                <input
                  placeholder="Document Name"
                  value={newDocName}
                  onChange={(e) => setNewDocName(e.target.value)}
                  className="px-2.5 py-1.5 text-xs rounded border border-slate-300"
                />
                <input
                  placeholder="CODE (e.g. TAX_CLEARANCE)"
                  value={newDocCode}
                  onChange={(e) => setNewDocCode(e.target.value)}
                  className="px-2.5 py-1.5 text-xs rounded border border-slate-300 font-mono"
                />
                <input
                  placeholder="Aliases (comma-separated)"
                  value={newDocAliases}
                  onChange={(e) => setNewDocAliases(e.target.value)}
                  className="px-2.5 py-1.5 text-xs rounded border border-slate-300"
                />
                <button
                  onClick={() =>
                    createTypeMutation.mutate({
                      name: newDocName,
                      code: newDocCode,
                      aliases: newDocAliases
                        .split(",")
                        .map((s) => s.trim())
                        .filter(Boolean),
                    })
                  }
                  disabled={!newDocName || !newDocCode}
                  className="px-3 py-1.5 rounded bg-brand text-white text-xs font-medium disabled:opacity-50"
                >
                  Add Document Type
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
