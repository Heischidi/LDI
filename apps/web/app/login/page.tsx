"use client";

import React, { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { FolderCog, Lock, Mail, ShieldCheck } from "lucide-react";
import { useAuth } from "@/hooks/use-auth";
import { ldiApi } from "@/lib/api-client";

const loginSchema = z.object({
  email: z.string().email("Enter a valid staff email address"),
  password: z.string().min(1, "Password is required"),
});

type LoginForm = z.infer<typeof loginSchema>;

export default function LoginPage() {
  const { login } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [resetEmail, setResetEmail] = useState("");
  const [resetStatus, setResetStatus] = useState<string | null>(null);
  const [showReset, setShowReset] = useState(false);

  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = async (data: LoginForm) => {
    setError(null);
    try {
      await login(data.email, data.password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed");
    }
  };

  const handleResetRequest = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await ldiApi.requestPasswordReset(resetEmail);
      setResetStatus(res.message);
    } catch (err) {
      setResetStatus(err instanceof Error ? err.message : "Unable to request reset");
    }
  };

  const fillDemo = (email: string, password: string) => {
    setValue("email", email);
    setValue("password", password);
  };

  return (
    <div className="min-h-screen bg-slate-100 flex flex-col items-center justify-center p-4 gap-4">
      <div className="w-full max-w-4xl grid md:grid-cols-5 bg-white rounded-2xl shadow-lg border border-slate-200 overflow-hidden">
        {/* Brand Panel */}
        <div className="md:col-span-2 bg-navy text-white p-8 flex flex-col justify-between">
          <div>
            <div className="inline-flex items-center gap-3 mb-6">
              <div className="h-10 w-10 rounded-xl bg-brand flex items-center justify-center">
                <FolderCog className="h-5 w-5 text-white" />
              </div>
              <div>
                <div className="font-semibold text-base tracking-tight">Leaders Edu Tour Ltd</div>
                <div className="text-xs text-emerald-300">Document Intelligence</div>
              </div>
            </div>
            <h2 className="text-2xl font-semibold leading-snug">
              Automated Client Document Classification &amp; Packaging
            </h2>
            <p className="text-sm text-slate-300 mt-3 leading-relaxed">
              Receive unstructured applicant uploads, extract text via OCR &amp; AI, detect
              missing checklist items, and export audit-ready client folders.
            </p>
          </div>

          <div className="mt-8 pt-6 border-t border-white/15 space-y-2 text-xs text-slate-300">
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-emerald-400 shrink-0" />
              <span>Private encrypted document vault &amp; RBAC</span>
            </div>
            <p className="text-[11px] text-slate-400">
              Internal administrative tool — Leaders Edu Tour Ltd. NDPA &amp; GDPR aligned. · Powered by{" "}
              <span className="font-semibold text-emerald-300">CHIDI AI</span>
            </p>
          </div>
        </div>

        {/* Auth Form */}
        <div className="md:col-span-3 p-8">
          <div className="mb-6">
            <h1 className="text-xl font-semibold text-navy">Staff Sign In</h1>
            <p className="text-sm text-slate-500 mt-1">
              Sign in with your authorised Leaders Edu Tour staff credentials.
            </p>
          </div>

          {error && (
            <div className="mb-4 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {!showReset ? (
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Staff Email
                </label>
                <div className="relative">
                  <Mail className="h-4 w-4 text-slate-400 absolute left-3 top-3" />
                  <input
                    type="email"
                    placeholder="officer@leaders.edu"
                    {...register("email")}
                    className="w-full pl-9 pr-3 py-2 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-navy/20 focus:border-navy"
                  />
                </div>
                {errors.email && (
                  <p className="text-xs text-red-600 mt-1">{errors.email.message}</p>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Password
                </label>
                <div className="relative">
                  <Lock className="h-4 w-4 text-slate-400 absolute left-3 top-3" />
                  <input
                    type="password"
                    placeholder="••••••••••••"
                    {...register("password")}
                    className="w-full pl-9 pr-3 py-2 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-navy/20 focus:border-navy"
                  />
                </div>
                {errors.password && (
                  <p className="text-xs text-red-600 mt-1">{errors.password.message}</p>
                )}
              </div>

              <div className="flex items-center justify-between text-xs">
                <button
                  type="button"
                  onClick={() => setShowReset(true)}
                  className="text-navy hover:underline font-medium"
                >
                  Forgot password?
                </button>
              </div>

              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full py-2.5 px-4 rounded-lg bg-navy text-white text-sm font-medium hover:bg-navy-700 disabled:opacity-60 transition-colors"
              >
                {isSubmitting ? "Signing in..." : "Sign In to Workspace"}
              </button>

              {/* Seeded Role Quick-Select for Internal Verification */}
              <div className="pt-4 border-t border-slate-200">
                <p className="text-xs font-medium text-slate-500 mb-2">
                  Seeded Staff Accounts (Local Dev / Testing):
                </p>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => fillDemo("officer@leaders.edu", "LeadersOfficer!2026")}
                    className="text-left px-3 py-2 rounded-lg border border-slate-200 hover:bg-slate-50 text-xs"
                  >
                    <div className="font-semibold text-navy">Processing Officer</div>
                    <div className="text-slate-500 truncate">officer@leaders.edu</div>
                  </button>
                  <button
                    type="button"
                    onClick={() => fillDemo("superadmin@leaders.edu", "LeadersAdmin!2026")}
                    className="text-left px-3 py-2 rounded-lg border border-slate-200 hover:bg-slate-50 text-xs"
                  >
                    <div className="font-semibold text-brand">Super Admin</div>
                    <div className="text-slate-500 truncate">superadmin@leaders.edu</div>
                  </button>
                </div>
              </div>
            </form>
          ) : (
            <form onSubmit={handleResetRequest} className="space-y-4">
              <p className="text-sm text-slate-600">
                Enter your staff email address to initiate a password reset token.
              </p>
              <input
                type="email"
                required
                value={resetEmail}
                onChange={(e) => setResetEmail(e.target.value)}
                placeholder="staff@leaders.edu"
                className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300"
              />
              {resetStatus && (
                <div className="rounded-lg bg-emerald-50 border border-emerald-200 px-3 py-2 text-xs text-emerald-800">
                  {resetStatus}
                </div>
              )}
              <div className="flex gap-2">
                <button
                  type="submit"
                  className="px-4 py-2 rounded-lg bg-navy text-white text-sm font-medium"
                >
                  Request Reset
                </button>
                <button
                  type="button"
                  onClick={() => setShowReset(false)}
                  className="px-4 py-2 rounded-lg border border-slate-300 text-sm text-slate-700"
                >
                  Back to Login
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
      <div className="flex items-center justify-center gap-2 text-xs text-slate-500">
        <span>Built by</span>
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full bg-navy text-emerald-300 font-semibold tracking-wider text-[11px]">
          CHIDI AI
        </span>
      </div>
    </div>
  );
}
