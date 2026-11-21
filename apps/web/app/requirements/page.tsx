"use client";

import React, { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Globe2, Plus, Save, Tag, Trash2 } from "lucide-react";
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
  const [countryFilter, setCountryFilter] = useState<string>("");
  const [newNaming, setNewNaming] = useState("");
  const [newDocName, setNewDocName] = useState("");
  const [newDocCode, setNewDocCode] = useState("");
  const [newDocAliases, setNewDocAliases] = useState("");
  const [activePanel, setActivePanel] = useState<"none" | "newSet" | "newCountry" | "newCategory">("none");

  const [setName, setSetName] = useState("");
  const [setDest, setSetDest] = useState("");
  const [setPurpose, setSetPurpose] = useState("");
  const [setCategory, setSetCategory] = useState("");

  const [countryName, setCountryName] = useState("");
  const [countryCode, setCountryCode] = useState("");
  const [countryRegion, setCountryRegion] = useState("Europe");

  const [catName, setCatName] = useState("");
  const [catCode, setCatCode] = useState("");
  const [catPurpose, setCatPurpose] = useState("");

  const [addDocTypeId, setAddDocTypeId] = useState("");
  const [addDocLevel, setAddDocLevel] = useState<"REQUIRED" | "OPTIONAL" | "CONDITIONAL">("REQUIRED");
  const [addMinValidity, setAddMinValidity] = useState("");
  const [addInstructions, setAddInstructions] = useState("");
  const [bannerMsg, setBannerMsg] = useState<string | null>(null);
  const [selectedSetIds, setSelectedSetIds] = useState<string[]>([]);
  const [selectedRuleIds, setSelectedRuleIds] = useState<string[]>([]);
  const [selectedTypeIds, setSelectedTypeIds] = useState<string[]>([]);

  const filteredSets = countryFilter
    ? reqSets.filter((rs) => rs.destination_id === countryFilter)
    : reqSets;
  const activeSet =
    filteredSets.find((s) => s.id === selectedSetId) || filteredSets[0] || reqSets[0];

  const updateSetMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Record<string, unknown> }) =>
      ldiApi.updateRequirementSet(id, payload),
    onSuccess: () => {
      setSelectedRuleIds([]);
      setBannerMsg("Checklist updated and new immutable version snapshot saved.");
      qc.invalidateQueries({ queryKey: ["requirement-sets"] });
    },
  });

  const deleteSetMutation = useMutation({
    mutationFn: ldiApi.deleteRequirementSet,
    onSuccess: (res, id) => {
      setSelectedSetIds((prev) => prev.filter((x) => x !== id));
      if (selectedSetId === id) setSelectedSetId(null);
      setBannerMsg(res.message);
      qc.invalidateQueries({ queryKey: ["requirement-sets"] });
    },
  });

  const batchDeleteSetsMutation = useMutation({
    mutationFn: ldiApi.batchDeleteRequirementSets,
    onSuccess: (res) => {
      setSelectedSetIds([]);
      if (selectedSetId && res.deleted_ids.includes(selectedSetId)) setSelectedSetId(null);
      setBannerMsg(res.message);
      qc.invalidateQueries({ queryKey: ["requirement-sets"] });
    },
  });

  const deleteTypeMutation = useMutation({
    mutationFn: ldiApi.deleteDocumentType,
    onSuccess: (res, id) => {
      setSelectedTypeIds((prev) => prev.filter((x) => x !== id));
      setBannerMsg(res.message);
      qc.invalidateQueries({ queryKey: ["document-types"] });
      qc.invalidateQueries({ queryKey: ["requirement-sets"] });
    },
  });

  const batchDeleteTypesMutation = useMutation({
    mutationFn: ldiApi.batchDeleteDocumentTypes,
    onSuccess: (res) => {
      setSelectedTypeIds([]);
      setBannerMsg(res.message);
      qc.invalidateQueries({ queryKey: ["document-types"] });
      qc.invalidateQueries({ queryKey: ["requirement-sets"] });
    },
  });

  const createTypeMutation = useMutation({
    mutationFn: ldiApi.createDocumentType,
    onSuccess: () => {
      setNewDocName("");
      setNewDocCode("");
      setNewDocAliases("");
      setBannerMsg("Canonical document type created.");
      qc.invalidateQueries({ queryKey: ["document-types"] });
    },
  });

  const createSetMutation = useMutation({
    mutationFn: ldiApi.createRequirementSet,
    onSuccess: (created) => {
      setActivePanel("none");
      setSetName("");
      setSelectedSetId(created.id);
      setBannerMsg(`Created checklist: ${created.name}`);
      qc.invalidateQueries({ queryKey: ["requirement-sets"] });
    },
  });

  const createDestMutation = useMutation({
    mutationFn: ldiApi.createDestination,
    onSuccess: (created) => {
      setActivePanel("none");
      setCountryName("");
      setCountryCode("");
      setBannerMsg(`Added destination country: ${created.name} (${created.code})`);
      qc.invalidateQueries({ queryKey: ["destinations"] });
    },
  });

  const createCategoryMutation = useMutation({
    mutationFn: ldiApi.createCategory,
    onSuccess: (created) => {
      setActivePanel("none");
      setCatName("");
      setCatCode("");
      setBannerMsg(`Added visa type category: ${created.name}`);
      qc.invalidateQueries({ queryKey: ["categories"] });
    },
  });

  const mapExistingItems = () =>
    (activeSet?.active_version?.items || []).map((i) => ({
      document_type_id: i.document_type_id,
      requirement_level: i.requirement_level,
      display_order: i.display_order,
      condition_explanation: i.condition_explanation,
      min_validity_days: i.min_validity_days,
      custom_instructions: i.custom_instructions,
    }));

  const addItemToActiveSet = (
    docTypeId: string,
    level: "REQUIRED" | "OPTIONAL" | "CONDITIONAL",
    minValidityDays?: number | null,
    instructions?: string | null
  ) => {
    if (!activeSet?.active_version) return;
    const existingItems = mapExistingItems();
    existingItems.push({
      document_type_id: docTypeId,
      requirement_level: level,
      display_order: existingItems.length + 1,
      condition_explanation: level === "CONDITIONAL" ? instructions || "Conditional eligibility requirement" : null,
      min_validity_days: minValidityDays || null,
      custom_instructions: instructions || null,
    });
    updateSetMutation.mutate({
      id: activeSet.id,
      payload: {
        change_notes: "Added requirement rule via Requirements Manager",
        items: existingItems,
      },
    });
    setAddDocTypeId("");
    setAddMinValidity("");
    setAddInstructions("");
  };

  const changeItemLevel = (index: number, nextLevel: "REQUIRED" | "OPTIONAL" | "CONDITIONAL") => {
    if (!activeSet?.active_version) return;
    const updated = mapExistingItems().map((item, idx) =>
      idx === index
        ? {
            ...item,
            requirement_level: nextLevel,
            condition_explanation:
              nextLevel === "CONDITIONAL"
                ? item.condition_explanation || "Conditional eligibility requirement"
                : null,
          }
        : item
    );
    updateSetMutation.mutate({
      id: activeSet.id,
      payload: { change_notes: `Changed rule level to ${nextLevel}`, items: updated },
    });
  };

  const removeSelectedRules = () => {
    if (!activeSet?.active_version || selectedRuleIds.length === 0) return;
    const remaining = (activeSet.active_version.items || [])
      .filter((i) => !selectedRuleIds.includes(i.id))
      .map((i, idx) => ({
        document_type_id: i.document_type_id,
        requirement_level: i.requirement_level,
        display_order: idx + 1,
        condition_expression: null,
        condition_explanation: i.condition_explanation,
        min_validity_days: i.min_validity_days,
        custom_instructions: i.custom_instructions,
      }));
    if (remaining.length === 0) {
      setBannerMsg("A checklist must keep at least 1 rule (or delete the checklist itself).");
      return;
    }
    updateSetMutation.mutate({
      id: activeSet.id,
      payload: {
        change_notes: `Batch removed ${selectedRuleIds.length} requirement rule(s)`,
        items: remaining,
      },
    });
  };

  const removeItemFromActiveSet = (index: number) => {
    if (!activeSet?.active_version) return;
    const remaining = mapExistingItems()
      .filter((_, idx) => idx !== index)
      .map((item, idx) => ({ ...item, display_order: idx + 1 }));
    if (remaining.length === 0) return;
    updateSetMutation.mutate({
      id: activeSet.id,
      payload: { change_notes: "Removed requirement rule from checklist", items: remaining },
    });
  };

  const visibleSetIds = filteredSets.map((s) => s.id);
  const allSetsSelected =
    visibleSetIds.length > 0 && visibleSetIds.every((id) => selectedSetIds.includes(id));
  const activeItems = activeSet?.active_version?.items || [];
  const activeRuleIds = activeItems.map((i) => i.id);
  const allRulesSelected =
    activeRuleIds.length > 0 && activeRuleIds.every((id) => selectedRuleIds.includes(id));
  const allTypeIds = docTypes.map((dt) => dt.id);
  const allTypesSelected =
    allTypeIds.length > 0 && allTypeIds.every((id) => selectedTypeIds.includes(id));

  return (
    <AppShell
      title="Requirements Manager"
      subtitle="Configure per-country destination checklists, visa types, conditional rules, document aliases, and naming conventions without modifying historical records."
      actions={
        canEdit ? (
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => setActivePanel(activePanel === "newCountry" ? "none" : "newCountry")}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-slate-300 bg-white text-slate-700 text-xs font-medium hover:bg-slate-50"
            >
              <Globe2 className="h-3.5 w-3.5" />
              Add Country
            </button>
            <button
              onClick={() => setActivePanel(activePanel === "newCategory" ? "none" : "newCategory")}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-slate-300 bg-white text-slate-700 text-xs font-medium hover:bg-slate-50"
            >
              <Plus className="h-3.5 w-3.5" />
              Add Visa Type
            </button>
            <button
              onClick={() => setActivePanel(activePanel === "newSet" ? "none" : "newSet")}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-brand text-white text-sm font-medium hover:bg-brand-light"
            >
              <Plus className="h-4 w-4" />
              New Requirement Set
            </button>
          </div>
        ) : null
      }
    >
      {bannerMsg && (
        <div className="mb-4 rounded-xl bg-emerald-50 border border-emerald-200 px-4 py-3 text-xs text-emerald-800 flex items-center justify-between">
          <span>{bannerMsg}</span>
          <button onClick={() => setBannerMsg(null)} className="underline">
            Dismiss
          </button>
        </div>
      )}

      {activePanel === "newCountry" && canEdit && (
        <div className="bg-white rounded-xl border border-slate-200 p-5 mb-6 shadow-sm">
          <h3 className="text-sm font-semibold text-navy mb-3">Add Destination Country</h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-3">
            <input
              placeholder="Country Name (e.g. Italy)"
              value={countryName}
              onChange={(e) => setCountryName(e.target.value)}
              className="px-3 py-2 text-sm rounded-lg border border-slate-300"
            />
            <input
              placeholder="ISO Code (e.g. IT)"
              value={countryCode}
              onChange={(e) => setCountryCode(e.target.value.toUpperCase())}
              maxLength={10}
              className="px-3 py-2 text-sm rounded-lg border border-slate-300 font-mono"
            />
            <input
              placeholder="Region (e.g. Europe)"
              value={countryRegion}
              onChange={(e) => setCountryRegion(e.target.value)}
              className="px-3 py-2 text-sm rounded-lg border border-slate-300"
            />
          </div>
          <button
            onClick={() =>
              createDestMutation.mutate({
                name: countryName,
                code: countryCode,
                region: countryRegion,
              })
            }
            disabled={!countryName || !countryCode}
            className="px-4 py-2 rounded-lg bg-navy text-white text-xs font-medium disabled:opacity-50"
          >
            Save Country
          </button>
        </div>
      )}

      {activePanel === "newCategory" && canEdit && (
        <div className="bg-white rounded-xl border border-slate-200 p-5 mb-6 shadow-sm">
          <h3 className="text-sm font-semibold text-navy mb-3">Add Visa / Application Category</h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-3">
            <input
              placeholder="Visa Type Name (e.g. Work Permit / Au Pair)"
              value={catName}
              onChange={(e) => setCatName(e.target.value)}
              className="px-3 py-2 text-sm rounded-lg border border-slate-300"
            />
            <input
              placeholder="CODE (e.g. WORK_PERMIT)"
              value={catCode}
              onChange={(e) => setCatCode(e.target.value.toUpperCase().replace(/\s+/g, "_"))}
              className="px-3 py-2 text-sm rounded-lg border border-slate-300 font-mono"
            />
            <select
              value={catPurpose}
              onChange={(e) => setCatPurpose(e.target.value)}
              className="px-3 py-2 text-sm rounded-lg border border-slate-300 bg-white"
            >
              <option value="">Default Purpose (Optional)...</option>
              {purposes.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>
          <button
            onClick={() =>
              createCategoryMutation.mutate({
                name: catName,
                code: catCode,
                purpose_id: catPurpose || undefined,
              })
            }
            disabled={!catName || !catCode}
            className="px-4 py-2 rounded-lg bg-navy text-white text-xs font-medium disabled:opacity-50"
          >
            Save Visa Type
          </button>
        </div>
      )}

      {activePanel === "newSet" && canEdit && (
        <div className="bg-white rounded-xl border border-slate-200 p-5 mb-6 shadow-sm">
          <h3 className="text-sm font-semibold text-navy mb-3">Create Requirement Set</h3>
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 mb-3">
            <input
              placeholder="Checklist Name (e.g. Germany Study Visa)"
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
              <option value="">Visa Type / Category...</option>
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
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Configured Checklists ({filteredSets.length})
            </h3>
            <div className="flex items-center gap-2">
              {canEdit && filteredSets.length > 0 && (
                <label className="inline-flex items-center gap-1 text-[11px] text-slate-600 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={allSetsSelected}
                    onChange={() => setSelectedSetIds(allSetsSelected ? [] : visibleSetIds)}
                    className="rounded border-slate-300"
                  />
                  All
                </label>
              )}
              {canEdit && selectedSetIds.length > 0 && (
                <button
                  type="button"
                  onClick={() => batchDeleteSetsMutation.mutate(selectedSetIds)}
                  disabled={batchDeleteSetsMutation.isPending}
                  className="inline-flex items-center gap-1 px-2 py-1 rounded bg-red-600 text-white text-[11px] font-medium hover:bg-red-700"
                >
                  <Trash2 className="h-3 w-3" />
                  Delete ({selectedSetIds.length})
                </button>
              )}
              <select
                value={countryFilter}
                onChange={(e) => setCountryFilter(e.target.value)}
                className="px-2.5 py-1 text-xs rounded-lg border border-slate-300 bg-white"
              >
                <option value="">All Countries ({reqSets.length})</option>
                {destinations.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
          {isLoading ? (
            <div className="h-32 rounded-xl bg-white border border-slate-200 animate-pulse" />
          ) : (
            <div className="space-y-2.5 max-h-[680px] overflow-y-auto pr-1">
              {filteredSets.map((rs) => (
                <div
                  key={rs.id}
                  className={`p-4 rounded-xl border transition-all flex items-start gap-2.5 ${
                    activeSet?.id === rs.id
                      ? "bg-white border-navy ring-2 ring-navy/10 shadow-sm"
                      : "bg-white border-slate-200 hover:border-slate-300"
                  }`}
                >
                  {canEdit && (
                    <input
                      type="checkbox"
                      aria-label={`Select checklist ${rs.name}`}
                      checked={selectedSetIds.includes(rs.id)}
                      onChange={() =>
                        setSelectedSetIds((prev) =>
                          prev.includes(rs.id) ? prev.filter((id) => id !== rs.id) : [...prev, rs.id]
                        )
                      }
                      className="mt-1 rounded border-slate-300 shrink-0"
                    />
                  )}
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedSetId(rs.id);
                      setSelectedRuleIds([]);
                      setNewNaming(rs.naming_convention);
                    }}
                    className="flex-1 text-left min-w-0"
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
                  {canEdit && (
                    <button
                      type="button"
                      onClick={() => deleteSetMutation.mutate(rs.id)}
                      title="Delete Checklist"
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
                <div className="flex items-center gap-2">
                  {canEdit && selectedRuleIds.length > 0 && (
                    <button
                      type="button"
                      onClick={removeSelectedRules}
                      disabled={
                        updateSetMutation.isPending ||
                        activeItems.length - selectedRuleIds.length < 1
                      }
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-600 text-white text-xs font-medium hover:bg-red-700 disabled:opacity-50"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                      Delete Selected Rules ({selectedRuleIds.length})
                    </button>
                  )}
                  {canEdit && (
                    <button
                      type="button"
                      onClick={() => deleteSetMutation.mutate(activeSet.id)}
                      disabled={deleteSetMutation.isPending}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-red-200 bg-red-50 text-red-700 text-xs font-medium hover:bg-red-100"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                      Delete Checklist
                    </button>
                  )}
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
                      {canEdit && (
                        <th className="px-3 py-2 w-8">
                          <input
                            type="checkbox"
                            aria-label="Select All Checklist Rules"
                            checked={allRulesSelected}
                            onChange={() =>
                              setSelectedRuleIds(allRulesSelected ? [] : activeRuleIds)
                            }
                            className="rounded border-slate-300"
                          />
                        </th>
                      )}
                      <th className="px-3 py-2">Order</th>
                      <th className="px-3 py-2">Document Type</th>
                      <th className="px-3 py-2">Requirement</th>
                      <th className="px-3 py-2">Min Validity</th>
                      <th className="px-3 py-2">Instructions / Condition</th>
                      {canEdit && <th className="px-3 py-2 text-right">Remove</th>}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {activeItems.map((item, idx) => (
                      <tr key={item.id}>
                        {canEdit && (
                          <td className="px-3 py-2">
                            <input
                              type="checkbox"
                              aria-label={`Select ${item.document_type_name}`}
                              checked={selectedRuleIds.includes(item.id)}
                              onChange={() =>
                                setSelectedRuleIds((prev) =>
                                  prev.includes(item.id)
                                    ? prev.filter((id) => id !== item.id)
                                    : [...prev, item.id]
                                )
                              }
                              className="rounded border-slate-300"
                            />
                          </td>
                        )}
                        <td className="px-3 py-2 font-mono text-slate-500">{item.display_order}</td>
                        <td className="px-3 py-2 font-medium text-slate-900">
                          {item.document_type_name}
                        </td>
                        <td className="px-3 py-2">
                          {canEdit ? (
                            <select
                              value={item.requirement_level}
                              onChange={(e) =>
                                changeItemLevel(
                                  idx,
                                  e.target.value as "REQUIRED" | "OPTIONAL" | "CONDITIONAL"
                                )
                              }
                              className="px-2 py-1 rounded border border-slate-200 bg-white text-xs font-medium text-slate-700"
                            >
                              <option value="REQUIRED">REQUIRED</option>
                              <option value="CONDITIONAL">CONDITIONAL</option>
                              <option value="OPTIONAL">OPTIONAL</option>
                            </select>
                          ) : (
                            <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-700 font-medium">
                              {item.requirement_level}
                            </span>
                          )}
                        </td>
                        <td className="px-3 py-2 text-slate-600">
                          {item.min_validity_days ? `${item.min_validity_days} days` : "—"}
                        </td>
                        <td className="px-3 py-2 text-slate-500">
                          {item.condition_explanation || item.custom_instructions || "—"}
                        </td>
                        {canEdit && (
                          <td className="px-3 py-2 text-right">
                            <button
                              type="button"
                              onClick={() => removeItemFromActiveSet(idx)}
                              disabled={activeItems.length <= 1}
                              title="Remove from checklist"
                              className="p-1 rounded text-red-600 hover:bg-red-50 disabled:opacity-30"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </button>
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {canEdit && (
                <div className="pt-3 border-t border-slate-200 bg-slate-50/70 p-3.5 rounded-lg space-y-2 text-xs">
                  <div className="text-slate-700 font-semibold">
                    Add Document Rule to Checklist (creates new version)
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-6 gap-2">
                    <select
                      value={addDocTypeId}
                      onChange={(e) => setAddDocTypeId(e.target.value)}
                      className="sm:col-span-2 px-2.5 py-1.5 rounded border border-slate-300 bg-white"
                    >
                      <option value="">Select Document Type...</option>
                      {docTypes.map((dt) => (
                        <option key={dt.id} value={dt.id}>
                          {dt.name}
                        </option>
                      ))}
                    </select>
                    <select
                      value={addDocLevel}
                      onChange={(e) =>
                        setAddDocLevel(e.target.value as "REQUIRED" | "OPTIONAL" | "CONDITIONAL")
                      }
                      className="px-2.5 py-1.5 rounded border border-slate-300 bg-white"
                    >
                      <option value="REQUIRED">REQUIRED</option>
                      <option value="CONDITIONAL">CONDITIONAL</option>
                      <option value="OPTIONAL">OPTIONAL</option>
                    </select>
                    <input
                      type="number"
                      min={1}
                      placeholder="Min days (opt)"
                      value={addMinValidity}
                      onChange={(e) => setAddMinValidity(e.target.value)}
                      className="px-2.5 py-1.5 rounded border border-slate-300 bg-white"
                    />
                    <input
                      placeholder="Custom notes / condition"
                      value={addInstructions}
                      onChange={(e) => setAddInstructions(e.target.value)}
                      className="px-2.5 py-1.5 rounded border border-slate-300 bg-white"
                    />
                    <button
                      type="button"
                      disabled={!addDocTypeId || updateSetMutation.isPending}
                      onClick={() =>
                        addItemToActiveSet(
                          addDocTypeId,
                          addDocLevel,
                          addMinValidity ? Number(addMinValidity) : null,
                          addInstructions || null
                        )
                      }
                      className="px-3 py-1.5 rounded bg-navy text-white font-medium hover:bg-navy-700 disabled:opacity-40"
                    >
                      + Add Rule
                    </button>
                  </div>
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
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-sm font-semibold text-navy">
                Canonical Document Types &amp; Aliases ({docTypes.length})
              </h3>
              {canEdit && docTypes.length > 0 && (
                <div className="flex items-center gap-2.5">
                  <label className="inline-flex items-center gap-1 text-xs text-slate-600 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={allTypesSelected}
                      onChange={() => setSelectedTypeIds(allTypesSelected ? [] : allTypeIds)}
                      className="rounded border-slate-300"
                    />
                    Select All
                  </label>
                  {selectedTypeIds.length > 0 && (
                    <button
                      type="button"
                      onClick={() => batchDeleteTypesMutation.mutate(selectedTypeIds)}
                      disabled={batchDeleteTypesMutation.isPending}
                      className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-red-600 text-white text-xs font-medium hover:bg-red-700"
                    >
                      <Trash2 className="h-3 w-3" />
                      Delete Selected ({selectedTypeIds.length})
                    </button>
                  )}
                </div>
              )}
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-h-64 overflow-y-auto pr-1">
              {docTypes.map((dt) => (
                <div
                  key={dt.id}
                  className="p-3 rounded-lg border border-slate-200 bg-slate-50/50 text-xs flex items-start justify-between gap-2"
                >
                  <div className="flex items-start gap-2 min-w-0 flex-1">
                    {canEdit && (
                      <input
                        type="checkbox"
                        aria-label={`Select ${dt.name}`}
                        checked={selectedTypeIds.includes(dt.id)}
                        onChange={() =>
                          setSelectedTypeIds((prev) =>
                            prev.includes(dt.id)
                              ? prev.filter((id) => id !== dt.id)
                              : [...prev, dt.id]
                          )
                        }
                        className="mt-0.5 rounded border-slate-300 shrink-0"
                      />
                    )}
                    <div className="min-w-0">
                      <div className="font-semibold text-navy truncate">{dt.name}</div>
                      <div className="font-mono text-[10px] text-slate-400 truncate">{dt.code}</div>
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
                  </div>
                  {canEdit && (
                    <button
                      type="button"
                      onClick={() => deleteTypeMutation.mutate(dt.id)}
                      title="Delete Document Type"
                      className="p-1 rounded border border-red-200 bg-red-50 text-red-700 hover:bg-red-100 shrink-0"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
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
