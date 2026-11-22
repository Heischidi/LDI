"use client";

import React, { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Save, Send, ShieldAlert } from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { useAuth } from "@/hooks/use-auth";
import { ldiApi } from "@/lib/api-client";

export default function SettingsPage() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const { data: settings = [], isLoading } = useQuery({
    queryKey: ["system-settings"],
    queryFn: ldiApi.listSettings,
  });

  const [aiProvider, setAiProvider] = useState("LOCAL_DETERMINISTIC");
  const [allowExternalAi, setAllowExternalAi] = useState(false);
  const [ocrProvider, setOcrProvider] = useState("TESSERACT");
  const [retentionDays, setRetentionDays] = useState(365);
  const [emailProvider, setEmailProvider] = useState("AUTO");
  const [smtpHost, setSmtpHost] = useState("");
  const [smtpPort, setSmtpPort] = useState(587);
  const [smtpUsername, setSmtpUsername] = useState("");
  const [smtpPassword, setSmtpPassword] = useState("");
  const [smtpFromEmail, setSmtpFromEmail] = useState("notifications@leaders.edu");
  const [smtpFromName, setSmtpFromName] = useState("Leaders Edu Tour Ltd");
  const [resendApiKey, setResendApiKey] = useState("");
  const [brevoApiKey, setBrevoApiKey] = useState("");
  const [testEmail, setTestEmail] = useState("");
  const [testResult, setTestResult] = useState<{
    delivery_status: string;
    delivery_provider: string;
    delivery_detail: string;
  } | null>(null);
  const [savedBanner, setSavedBanner] = useState<string | null>(null);

  useEffect(() => {
    if (user?.email && !testEmail) {
      setTestEmail(user.email);
    }
  }, [user?.email, testEmail]);

  useEffect(() => {
    const ai = settings.find((s) => s.key === "ai.provider")?.value_json;
    if (ai) {
      setAiProvider(String(ai.provider || "LOCAL_DETERMINISTIC"));
      setAllowExternalAi(Boolean(ai.allow_external_ai));
    }
    const ocr = settings.find((s) => s.key === "ocr.provider")?.value_json;
    if (ocr) setOcrProvider(String(ocr.provider || "TESSERACT"));
    const sec = settings.find((s) => s.key === "security.upload_limits")?.value_json;
    if (sec && sec.retention_days) setRetentionDays(Number(sec.retention_days));
    const notif = settings.find((s) => s.key === "notifications.email")?.value_json;
    if (notif) {
      setEmailProvider(String(notif.provider || "AUTO"));
      setSmtpHost(String(notif.smtp_host || ""));
      setSmtpPort(Number(notif.smtp_port || 587));
      setSmtpUsername(String(notif.smtp_username || ""));
      setSmtpPassword(String(notif.smtp_password || ""));
      setSmtpFromEmail(String(notif.from_email || "notifications@leaders.edu"));
      setSmtpFromName(String(notif.from_name || "Leaders Edu Tour Ltd"));
      setResendApiKey(String(notif.resend_api_key || ""));
      setBrevoApiKey(String(notif.brevo_api_key || ""));
    }
  }, [settings]);

  const persistEmailSettings = () =>
    ldiApi.updateSetting("notifications.email", {
      provider: emailProvider,
      smtp_host: smtpHost,
      smtp_port: smtpPort,
      smtp_username: smtpUsername,
      smtp_password: smtpPassword,
      smtp_use_tls: smtpPort !== 465,
      from_email: smtpFromEmail,
      from_name: smtpFromName,
      resend_api_key: resendApiKey,
      brevo_api_key: brevoApiKey,
    });

  const saveMutation = useMutation({
    mutationFn: async () => {
      await ldiApi.updateSetting("ai.provider", {
        provider: aiProvider,
        allow_external_ai: allowExternalAi,
        redact_pii: true,
      });
      await ldiApi.updateSetting("ocr.provider", { provider: ocrProvider });
      await ldiApi.updateSetting("security.upload_limits", {
        max_file_mb: 25,
        max_batch_files: 50,
        retention_days: retentionDays,
      });
      await persistEmailSettings();
    },
    onSuccess: () => {
      setSavedBanner("System configuration saved and recorded in audit log.");
      qc.invalidateQueries({ queryKey: ["system-settings"] });
    },
  });

  const testEmailMutation = useMutation({
    mutationFn: async () => {
      await persistEmailSettings();
      return ldiApi.sendTestEmail(testEmail.trim());
    },
    onSuccess: (res) => {
      setTestResult(res);
      qc.invalidateQueries({ queryKey: ["system-settings"] });
    },
  });

  return (
    <AppShell
      title="System Settings"
      subtitle="Configure interchangeable AI & OCR providers, privacy safeguards, and data retention policies."
    >
      {savedBanner && (
        <div className="mb-4 rounded-xl bg-emerald-50 border border-emerald-200 px-4 py-3 text-sm text-emerald-800">
          {savedBanner}
        </div>
      )}

      {isLoading ? (
        <div className="h-48 rounded-xl bg-white border border-slate-200 animate-pulse" />
      ) : (
        <div className="max-w-3xl space-y-6">
          <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm space-y-4">
            <h2 className="text-sm font-semibold text-navy">AI Provider &amp; Privacy Governance</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">
                  Active AI Classification Provider
                </label>
                <select
                  value={aiProvider}
                  onChange={(e) => setAiProvider(e.target.value)}
                  className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 bg-white"
                >
                  <option value="LOCAL_DETERMINISTIC">Local Deterministic Analyzer (Zero External Transfer)</option>
                  <option value="GEMINI">Google Gemini API</option>
                  <option value="OPENAI">OpenAI API</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">
                  Active OCR Provider
                </label>
                <select
                  value={ocrProvider}
                  onChange={(e) => setOcrProvider(e.target.value)}
                  className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 bg-white"
                >
                  <option value="TESSERACT">Local Tesseract OCR (with Visual Fallback)</option>
                  <option value="GOOGLE_DOC_AI">Google Document AI</option>
                  <option value="AZURE_DOC_INTELLIGENCE">Azure Document Intelligence</option>
                </select>
              </div>
            </div>

            <label className="flex items-start gap-3 p-3.5 rounded-lg bg-slate-50 border border-slate-200 cursor-pointer">
              <input
                type="checkbox"
                checked={allowExternalAi}
                onChange={(e) => setAllowExternalAi(e.target.checked)}
                className="mt-1"
              />
              <div className="text-xs">
                <div className="font-semibold text-navy">
                  Allow External Cloud AI API Calls (with automatic PII redaction)
                </div>
                <p className="text-slate-500 mt-0.5">
                  When disabled, all classification stays strictly within the private server perimeter to satisfy NDPA / GDPR strict residency requirements.
                </p>
              </div>
            </label>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm space-y-4">
            <h2 className="text-sm font-semibold text-navy">
              Client &amp; CEO Email Reminders (Real-Time Delivery)
            </h2>
            <p className="text-xs text-slate-500">
              Render&apos;s free hosting blocks outbound SMTP ports (25/465/587). Use{" "}
              <strong>Brevo HTTP API</strong> (300 free emails/day over HTTPS — works with any Gmail
              sender) or <strong>Resend API</strong> so CEO reminders and live client updates arrive
              immediately.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">
                  Delivery Mode
                </label>
                <select
                  value={emailProvider}
                  onChange={(e) => setEmailProvider(e.target.value)}
                  className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 bg-white"
                >
                  <option value="AUTO">Auto (Brevo → Resend → SMTP → Outbox)</option>
                  <option value="BREVO">Brevo HTTP API (Recommended — Works with Gmail)</option>
                  <option value="RESEND">Resend HTTP API (Custom Domain)</option>
                  <option value="SMTP">SMTP Server (Paid Host / Local Only)</option>
                  <option value="OUTBOX">Outbox Audit Only</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">
                  Sender Name
                </label>
                <input
                  value={smtpFromName}
                  onChange={(e) => setSmtpFromName(e.target.value)}
                  className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">
                  Sender Email
                </label>
                <input
                  type="email"
                  value={smtpFromEmail}
                  onChange={(e) => setSmtpFromEmail(e.target.value)}
                  className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">
                  Brevo API Key (Recommended for Render Free + Gmail)
                </label>
                <input
                  type="password"
                  value={brevoApiKey}
                  onChange={(e) => setBrevoApiKey(e.target.value)}
                  placeholder="xkeysib-..."
                  className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">
                  Resend API Key (Optional Alternative)
                </label>
                <input
                  type="password"
                  value={resendApiKey}
                  onChange={(e) => setResendApiKey(e.target.value)}
                  placeholder="re_..."
                  className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 pt-2 border-t border-slate-100">
              <div className="sm:col-span-2">
                <label className="block text-xs font-medium text-slate-700 mb-1">
                  SMTP Host (Paid Host / Local Only)
                </label>
                <input
                  value={smtpHost}
                  onChange={(e) => setSmtpHost(e.target.value)}
                  placeholder="smtp.gmail.com"
                  className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">
                  SMTP Port
                </label>
                <input
                  type="number"
                  value={smtpPort}
                  onChange={(e) => setSmtpPort(Number(e.target.value))}
                  className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">
                  SMTP Username
                </label>
                <input
                  value={smtpUsername}
                  onChange={(e) => setSmtpUsername(e.target.value)}
                  className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300"
                />
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">
                SMTP Password / App Password (Optional if using Brevo or Resend)
              </label>
              <input
                type="password"
                value={smtpPassword}
                onChange={(e) => setSmtpPassword(e.target.value)}
                placeholder="Optional if using Brevo / Resend"
                className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300"
              />
            </div>

            <div className="pt-3 border-t border-slate-200 space-y-2">
              <div className="text-xs font-semibold text-navy">Test Live Email Delivery</div>
              <div className="flex flex-wrap items-center gap-2">
                <input
                  type="email"
                  value={testEmail}
                  onChange={(e) => setTestEmail(e.target.value)}
                  placeholder="recipient@gmail.com"
                  className="flex-1 min-w-[220px] px-3 py-2 text-sm rounded-lg border border-slate-300"
                />
                <button
                  type="button"
                  onClick={() => testEmailMutation.mutate()}
                  disabled={!testEmail.trim() || testEmailMutation.isPending}
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-navy text-white text-xs font-medium hover:bg-navy-700 disabled:opacity-50"
                >
                  <Send className="h-3.5 w-3.5" />
                  {testEmailMutation.isPending ? "Sending Test..." : "Save & Send Test Email"}
                </button>
              </div>
              {testResult && (
                <div
                  className={`rounded-lg border px-3 py-2 text-xs ${
                    testResult.delivery_status.startsWith("SENT")
                      ? "bg-emerald-50 border-emerald-200 text-emerald-800"
                      : testResult.delivery_status === "FAILED"
                      ? "bg-red-50 border-red-200 text-red-700"
                      : "bg-amber-50 border-amber-200 text-amber-800"
                  }`}
                >
                  <strong>
                    {testResult.delivery_status} ({testResult.delivery_provider}):
                  </strong>{" "}
                  {testResult.delivery_detail}
                </div>
              )}
            </div>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm space-y-4">
            <h2 className="text-sm font-semibold text-navy">Retention &amp; Compliance</h2>
            <div className="flex items-center gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">
                  Document Retention Period (Days)
                </label>
                <input
                  type="number"
                  min={30}
                  max={3650}
                  value={retentionDays}
                  onChange={(e) => setRetentionDays(Number(e.target.value))}
                  className="w-40 px-3 py-2 text-sm rounded-lg border border-slate-300"
                />
              </div>
            </div>
            <div className="flex items-start gap-2 text-xs text-slate-500 bg-amber-50/70 border border-amber-200 rounded-lg p-3">
              <ShieldAlert className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
              <span>
                API credentials (GEMINI_API_KEY, OPENAI_API_KEY, S3_SECRET_ACCESS_KEY) are managed via server environment variables and never exposed to client browsers.
              </span>
            </div>
          </div>

          <button
            onClick={() => saveMutation.mutate()}
            disabled={saveMutation.isPending}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-brand text-white text-sm font-medium hover:bg-brand-light"
          >
            <Save className="h-4 w-4" />
            {saveMutation.isPending ? "Saving..." : "Save Configuration"}
          </button>
        </div>
      )}
    </AppShell>
  );
}
