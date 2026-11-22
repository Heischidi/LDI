"use client";

import React, { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2,
  Copy,
  Download,
  FilePlus2,
  Pencil,
  RefreshCw,
  Save,
  Sparkles,
  Trash2,
} from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { downloadAuthorizedFile, ldiApi } from "@/lib/api-client";
import { formatDateTime } from "@/lib/utils";
import type { StatementOfPurposeItem } from "@/types";

export default function SopGeneratorPage() {
  const qc = useQueryClient();

  const [activeSop, setActiveSop] = useState<StatementOfPurposeItem | null>(null);
  const [applicantId, setApplicantId] = useState("");
  const [candidateName, setCandidateName] = useState("");
  const [universityName, setUniversityName] = useState("");
  const [courseOrProgram, setCourseOrProgram] = useState("");
  const [degreeLevel, setDegreeLevel] = useState("Master's");
  const [entryTerm, setEntryTerm] = useState("Fall 2026 / September 2026");
  const [destinationCountry, setDestinationCountry] = useState("Canada");
  const [academicBackground, setAcademicBackground] = useState("");
  const [workExperience, setWorkExperience] = useState("");
  const [whyUniversity, setWhyUniversity] = useState("");
  const [careerGoals, setCareerGoals] = useState("");
  const [fundingAndTies, setFundingAndTies] = useState("");
  const [tone, setTone] = useState("ACADEMIC_PROFESSIONAL");
  const [wordCountTarget, setWordCountTarget] = useState(750);
  const [draftContent, setDraftContent] = useState("");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const { data: applicantsData } = useQuery({
    queryKey: ["applicants-for-sop"],
    queryFn: () => ldiApi.listApplicants("?page_size=100"),
  });

  const { data: sops = [], isLoading } = useQuery({
    queryKey: ["sops"],
    queryFn: ldiApi.listSops,
  });

  const loadIntoWorkspace = (item: StatementOfPurposeItem) => {
    setActiveSop(item);
    setApplicantId(item.applicant_id || "");
    setCandidateName(item.candidate_name);
    setUniversityName(item.university_name);
    setCourseOrProgram(item.course_or_program);
    setDegreeLevel(item.degree_level);
    setEntryTerm(item.entry_term);
    setDestinationCountry(item.destination_country);
    setAcademicBackground(item.academic_background || "");
    setWorkExperience(item.work_experience || "");
    setWhyUniversity(item.why_university || "");
    setCareerGoals(item.career_goals || "");
    setFundingAndTies(item.funding_and_ties || "");
    setTone(item.tone);
    setWordCountTarget(item.word_count_target);
    setDraftContent(item.generated_content);
  };

  const handleApplicantPick = (pickedId: string) => {
    setApplicantId(pickedId);
    const app = applicantsData?.items.find((a) => a.id === pickedId);
    if (app) {
      setCandidateName(app.full_name);
      setDestinationCountry(app.destination.name);
    }
  };

  const generateMutation = useMutation({
    mutationFn: () =>
      ldiApi.generateSop({
        applicant_id: applicantId || null,
        candidate_name: candidateName.trim(),
        university_name: universityName.trim(),
        course_or_program: courseOrProgram.trim(),
        degree_level: degreeLevel,
        entry_term: entryTerm.trim(),
        destination_country: destinationCountry.trim(),
        academic_background: academicBackground.trim() || null,
        work_experience: workExperience.trim() || null,
        why_university: whyUniversity.trim() || null,
        career_goals: careerGoals.trim() || null,
        funding_and_ties: fundingAndTies.trim() || null,
        tone,
        word_count_target: wordCountTarget,
      }),
    onSuccess: (created) => {
      setErrorMsg(null);
      loadIntoWorkspace(created);
      setStatusMsg(
        `Generated admission-ready SOP for ${created.candidate_name} (${created.ai_provider}).`
      );
      qc.invalidateQueries({ queryKey: ["sops"] });
    },
    onError: (err) => setErrorMsg(err instanceof Error ? err.message : "Failed to generate SOP"),
  });

  const updateMutation = useMutation({
    mutationFn: ({ regenerate }: { regenerate: boolean }) => {
      if (!activeSop) throw new Error("No active SOP selected.");
      return ldiApi.updateSop(activeSop.id, {
        candidate_name: candidateName.trim(),
        university_name: universityName.trim(),
        course_or_program: courseOrProgram.trim(),
        degree_level: degreeLevel,
        entry_term: entryTerm.trim(),
        destination_country: destinationCountry.trim(),
        academic_background: academicBackground.trim() || null,
        work_experience: workExperience.trim() || null,
        why_university: whyUniversity.trim() || null,
        career_goals: careerGoals.trim() || null,
        funding_and_ties: fundingAndTies.trim() || null,
        tone,
        word_count_target: wordCountTarget,
        generated_content: regenerate ? undefined : draftContent,
        regenerate,
      });
    },
    onSuccess: (updated, vars) => {
      setErrorMsg(null);
      loadIntoWorkspace(updated);
      setStatusMsg(
        vars.regenerate ? "Regenerated SOP with updated university & program details." : "Saved SOP edits."
      );
      qc.invalidateQueries({ queryKey: ["sops"] });
    },
    onError: (err) => setErrorMsg(err instanceof Error ? err.message : "Failed to update SOP"),
  });

  const attachMutation = useMutation({
    mutationFn: () => {
      if (!activeSop) throw new Error("Generate or select an SOP first.");
      return ldiApi.attachSopToApplicant(activeSop.id, applicantId || undefined);
    },
    onSuccess: (res) => {
      setErrorMsg(null);
      setStatusMsg(res.message);
      qc.invalidateQueries({ queryKey: ["applicant"] });
      qc.invalidateQueries({ queryKey: ["processed-documents"] });
      qc.invalidateQueries({ queryKey: ["applicants"] });
    },
    onError: (err) => setErrorMsg(err instanceof Error ? err.message : "Failed to attach SOP"),
  });

  const deleteMutation = useMutation({
    mutationFn: ldiApi.deleteSop,
    onSuccess: (res, id) => {
      setSelectedIds((prev) => prev.filter((x) => x !== id));
      if (activeSop?.id === id) {
        setActiveSop(null);
        setDraftContent("");
      }
      setStatusMsg(res.message);
      qc.invalidateQueries({ queryKey: ["sops"] });
    },
  });

  const batchDeleteMutation = useMutation({
    mutationFn: ldiApi.batchDeleteSops,
    onSuccess: (res) => {
      setSelectedIds([]);
      if (activeSop && res.deleted_ids.includes(activeSop.id)) {
        setActiveSop(null);
        setDraftContent("");
      }
      setStatusMsg(res.message);
      qc.invalidateQueries({ queryKey: ["sops"] });
    },
  });

  const wordCount = useMemo(
    () => (draftContent.trim() ? draftContent.trim().split(/\s+/).length : 0),
    [draftContent]
  );
  const allIds = sops.map((s) => s.id);
  const allSelected = allIds.length > 0 && allIds.every((id) => selectedIds.includes(id));

  return (
    <AppShell
      title="AI Statement of Purpose (SOP) Generator"
      subtitle="Generate tailored, admission-ready Statements of Purpose by university, course/program, entry term, and destination country."
    >
      <div className="space-y-6">
        {errorMsg && (
          <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-xs text-red-700">
            {errorMsg}
          </div>
        )}
        {statusMsg && (
          <div className="rounded-xl bg-emerald-50 border border-emerald-200 px-4 py-3 text-xs text-emerald-700 flex items-center justify-between">
            <span>{statusMsg}</span>
            <button type="button" onClick={() => setStatusMsg(null)} className="underline">
              Dismiss
            </button>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Column: Intake & Program Details */}
          <div className="lg:col-span-5 bg-white rounded-xl border border-slate-200 p-5 shadow-sm space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-navy flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-brand" />
                Candidate &amp; Admission Details
              </h2>
              {activeSop && (
                <button
                  type="button"
                  onClick={() => {
                    setActiveSop(null);
                    setDraftContent("");
                  }}
                  className="text-xs text-brand hover:underline font-medium"
                >
                  + New SOP
                </button>
              )}
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">
                Link Existing Applicant Record (Optional)
              </label>
              <select
                value={applicantId}
                onChange={(e) => handleApplicantPick(e.target.value)}
                className="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white"
              >
                <option value="">Standalone SOP (not linked to applicant yet)</option>
                {applicantsData?.items.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.application_reference} — {a.full_name} ({a.destination.name})
                  </option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Candidate Name *</label>
                <input
                  value={candidateName}
                  onChange={(e) => setCandidateName(e.target.value)}
                  placeholder="John Doe"
                  className="w-full px-3 py-2 text-xs rounded-lg border border-slate-300"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Destination Country *</label>
                <input
                  value={destinationCountry}
                  onChange={(e) => setDestinationCountry(e.target.value)}
                  placeholder="Canada, United Kingdom, USA..."
                  className="w-full px-3 py-2 text-xs rounded-lg border border-slate-300"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">Target University / School *</label>
              <input
                value={universityName}
                onChange={(e) => setUniversityName(e.target.value)}
                placeholder="e.g. University of Toronto"
                className="w-full px-3 py-2 text-xs rounded-lg border border-slate-300"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Course / Program *</label>
                <input
                  value={courseOrProgram}
                  onChange={(e) => setCourseOrProgram(e.target.value)}
                  placeholder="e.g. MSc Data Science"
                  className="w-full px-3 py-2 text-xs rounded-lg border border-slate-300"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Degree Level</label>
                <select
                  value={degreeLevel}
                  onChange={(e) => setDegreeLevel(e.target.value)}
                  className="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white"
                >
                  <option value="Bachelor's">Bachelor&apos;s</option>
                  <option value="Master's">Master&apos;s</option>
                  <option value="MBA">MBA</option>
                  <option value="Postgraduate Diploma">Postgraduate Diploma</option>
                  <option value="PhD">PhD / Doctorate</option>
                  <option value="Diploma / Certificate">Diploma / Certificate</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Entry Term *</label>
                <input
                  value={entryTerm}
                  onChange={(e) => setEntryTerm(e.target.value)}
                  placeholder="September 2026"
                  className="w-full px-2.5 py-2 text-xs rounded-lg border border-slate-300"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Tone</label>
                <select
                  value={tone}
                  onChange={(e) => setTone(e.target.value)}
                  className="w-full px-2.5 py-2 text-xs rounded-lg border border-slate-300 bg-white"
                >
                  <option value="ACADEMIC_PROFESSIONAL">Academic</option>
                  <option value="CONCISE_VISA_FOCUSED">Visa-Focused</option>
                  <option value="RESEARCH_INTENSIVE">Research</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Target Words</label>
                <select
                  value={wordCountTarget}
                  onChange={(e) => setWordCountTarget(Number(e.target.value))}
                  className="w-full px-2.5 py-2 text-xs rounded-lg border border-slate-300 bg-white"
                >
                  <option value={500}>~500 words</option>
                  <option value={750}>~750 words</option>
                  <option value={1000}>~1000 words</option>
                  <option value={1200}>~1200 words</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">Academic Background</label>
              <textarea
                rows={2}
                value={academicBackground}
                onChange={(e) => setAcademicBackground(e.target.value)}
                placeholder="BSc Computer Science (Second Class Upper), thesis or key coursework..."
                className="w-full px-3 py-2 text-xs rounded-lg border border-slate-300"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">Work / Project Experience</label>
              <textarea
                rows={2}
                value={workExperience}
                onChange={(e) => setWorkExperience(e.target.value)}
                placeholder="3 years as Analyst at ..., led analytics migration..."
                className="w-full px-3 py-2 text-xs rounded-lg border border-slate-300"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">Why This University &amp; Country</label>
              <textarea
                rows={2}
                value={whyUniversity}
                onChange={(e) => setWhyUniversity(e.target.value)}
                placeholder="Specific modules, labs, co-op options, global recognition..."
                className="w-full px-3 py-2 text-xs rounded-lg border border-slate-300"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">Post-Study Career Goals</label>
              <textarea
                rows={2}
                value={careerGoals}
                onChange={(e) => setCareerGoals(e.target.value)}
                placeholder="Target role and contribution in home country..."
                className="w-full px-3 py-2 text-xs rounded-lg border border-slate-300"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">Funding &amp; Home Ties</label>
              <input
                value={fundingAndTies}
                onChange={(e) => setFundingAndTies(e.target.value)}
                placeholder="Sponsored by parent / self-funded savings + return ties..."
                className="w-full px-3 py-2 text-xs rounded-lg border border-slate-300"
              />
            </div>

            <button
              type="button"
              onClick={() => generateMutation.mutate()}
              disabled={
                generateMutation.isPending ||
                !candidateName.trim() ||
                !universityName.trim() ||
                !courseOrProgram.trim() ||
                !entryTerm.trim() ||
                !destinationCountry.trim()
              }
              className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-brand text-white text-xs font-semibold hover:bg-brand-light disabled:opacity-50"
            >
              <Sparkles className="h-4 w-4" />
              {generateMutation.isPending ? "Generating SOP..." : "Generate Statement of Purpose"}
            </button>
          </div>

          {/* Right Column: Live Editable SOP Output */}
          <div className="lg:col-span-7 bg-white rounded-xl border border-slate-200 p-5 shadow-sm flex flex-col space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 pb-3">
              <div>
                <h2 className="text-sm font-semibold text-navy">
                  {activeSop
                    ? `${activeSop.candidate_name} — ${activeSop.university_name}`
                    : "Generated SOP Editor"}
                </h2>
                <p className="text-[11px] text-slate-500">
                  {wordCount} words
                  {activeSop ? ` · Engine: ${activeSop.ai_provider}` : " · Fill candidate details on the left and click Generate"}
                </p>
              </div>
              {activeSop && (
                <div className="flex flex-wrap items-center gap-1.5">
                  <button
                    type="button"
                    onClick={() => updateMutation.mutate({ regenerate: false })}
                    disabled={updateMutation.isPending}
                    className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-navy text-white text-xs font-medium hover:bg-navy-700"
                  >
                    <Save className="h-3.5 w-3.5" />
                    Save Edits
                  </button>
                  <button
                    type="button"
                    onClick={() => updateMutation.mutate({ regenerate: true })}
                    disabled={updateMutation.isPending}
                    className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-slate-300 text-slate-700 text-xs font-medium hover:bg-slate-50"
                  >
                    <RefreshCw className="h-3.5 w-3.5" />
                    Regenerate
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      navigator.clipboard?.writeText(draftContent);
                      setStatusMsg("Copied SOP text to clipboard.");
                    }}
                    className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-slate-300 text-slate-700 text-xs font-medium hover:bg-slate-50"
                  >
                    <Copy className="h-3.5 w-3.5" />
                    Copy
                  </button>
                </div>
              )}
            </div>

            <textarea
              rows={20}
              value={draftContent}
              onChange={(e) => setDraftContent(e.target.value)}
              placeholder="Your generated Statement of Purpose will appear here. Staff can review, customize, save, export to PDF/Word, or attach directly to the applicant's checklist."
              className="flex-1 w-full p-4 text-xs leading-relaxed rounded-lg border border-slate-200 bg-slate-50/40 font-sans focus:outline-none focus:ring-2 focus:ring-navy/20"
            />

            {activeSop && (
              <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-slate-200">
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={() =>
                      downloadAuthorizedFile(
                        `/api/sop/${activeSop.id}/export?format=pdf`,
                        `${activeSop.candidate_name.replace(/\s+/g, "_")}_Statement_of_Purpose.pdf`
                      )
                    }
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-brand/30 bg-emerald-50 text-brand text-xs font-medium hover:bg-emerald-100"
                  >
                    <Download className="h-3.5 w-3.5" />
                    Download PDF
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      downloadAuthorizedFile(
                        `/api/sop/${activeSop.id}/export?format=docx`,
                        `${activeSop.candidate_name.replace(/\s+/g, "_")}_Statement_of_Purpose.docx`
                      )
                    }
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-300 bg-white text-navy text-xs font-medium hover:bg-slate-50"
                  >
                    <Download className="h-3.5 w-3.5" />
                    Download Word (.docx)
                  </button>
                </div>
                {(applicantId || activeSop.applicant_id) && (
                  <button
                    type="button"
                    onClick={() => attachMutation.mutate()}
                    disabled={attachMutation.isPending}
                    className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-brand text-white text-xs font-medium hover:bg-brand-light disabled:opacity-60"
                  >
                    <FilePlus2 className="h-3.5 w-3.5" />
                    {attachMutation.isPending ? "Attaching..." : "Attach PDF to Applicant Checklist"}
                  </button>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Saved SOPs Library */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-200 flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-sm font-semibold text-navy">
              Saved Statements of Purpose ({sops.length})
            </h3>
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
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 uppercase">
                <tr>
                  <th className="px-4 py-2.5 w-10">
                    <input
                      type="checkbox"
                      aria-label="Select All SOPs"
                      checked={allSelected}
                      onChange={() => setSelectedIds(allSelected ? [] : allIds)}
                      className="rounded border-slate-300"
                    />
                  </th>
                  <th className="px-4 py-2.5">Candidate</th>
                  <th className="px-4 py-2.5">University &amp; Country</th>
                  <th className="px-4 py-2.5">Course / Program</th>
                  <th className="px-4 py-2.5">Intake</th>
                  <th className="px-4 py-2.5">Updated</th>
                  <th className="px-4 py-2.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {isLoading && (
                  <tr>
                    <td colSpan={7} className="px-4 py-8 text-center text-slate-400">
                      Loading saved SOP drafts...
                    </td>
                  </tr>
                )}
                {!isLoading && sops.length === 0 && (
                  <tr>
                    <td colSpan={7} className="px-4 py-10 text-center text-slate-500">
                      No SOP drafts generated yet.
                    </td>
                  </tr>
                )}
                {sops.map((item) => (
                  <tr key={item.id} className="hover:bg-slate-50/70">
                    <td className="px-4 py-3">
                      <input
                        type="checkbox"
                        aria-label={`Select SOP for ${item.candidate_name}`}
                        checked={selectedIds.includes(item.id)}
                        onChange={() =>
                          setSelectedIds((prev) =>
                            prev.includes(item.id)
                              ? prev.filter((id) => id !== item.id)
                              : [...prev, item.id]
                          )
                        }
                        className="rounded border-slate-300"
                      />
                    </td>
                    <td className="px-4 py-3 font-medium text-navy">
                      {item.candidate_name}
                      {item.applicant_id && (
                        <CheckCircle2
                          className="h-3 w-3 text-emerald-600 inline ml-1"
                          aria-label="Linked to Applicant"
                        />
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <div className="text-slate-800">{item.university_name}</div>
                      <div className="text-[11px] text-slate-500">{item.destination_country}</div>
                    </td>
                    <td className="px-4 py-3">
                      {item.degree_level} in {item.course_or_program}
                    </td>
                    <td className="px-4 py-3 text-slate-600">{item.entry_term}</td>
                    <td className="px-4 py-3 text-slate-500">{formatDateTime(item.updated_at)}</td>
                    <td className="px-4 py-3 text-right space-x-1.5 whitespace-nowrap">
                      <button
                        type="button"
                        onClick={() => loadIntoWorkspace(item)}
                        className="inline-flex items-center gap-1 px-2.5 py-1 rounded border border-slate-200 text-navy hover:bg-navy-50"
                      >
                        <Pencil className="h-3 w-3" />
                        Edit
                      </button>
                      <button
                        type="button"
                        onClick={() =>
                          downloadAuthorizedFile(
                            `/api/sop/${item.id}/export?format=pdf`,
                            `${item.candidate_name.replace(/\s+/g, "_")}_Statement_of_Purpose.pdf`
                          )
                        }
                        className="inline-flex items-center gap-1 px-2 py-1 rounded border border-brand/30 text-brand hover:bg-emerald-50"
                      >
                        <Download className="h-3 w-3" />
                        PDF
                      </button>
                      <button
                        type="button"
                        onClick={() => deleteMutation.mutate(item.id)}
                        title="Delete SOP"
                        className="inline-flex items-center gap-1 px-2 py-1 rounded border border-red-200 bg-red-50 text-red-700 hover:bg-red-100"
                      >
                        <Trash2 className="h-3 w-3" />
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
