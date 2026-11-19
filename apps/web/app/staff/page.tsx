"use client";

import React, { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, Shield, UserCheck, UserPlus, UserX } from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { useAuth } from "@/hooks/use-auth";
import { ldiApi } from "@/lib/api-client";
import { formatDateTime } from "@/lib/utils";

export default function StaffManagementPage() {
  const { hasRole } = useAuth();
  const qc = useQueryClient();
  const isSuperAdmin = hasRole("SUPER_ADMIN");

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [roleName, setRoleName] = useState("OFFICER");
  const [editingPasswordUserId, setEditingPasswordUserId] = useState<string | null>(null);
  const [newPassword, setNewPassword] = useState("");
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const { data: users = [] } = useQuery({
    queryKey: ["staff-users"],
    queryFn: ldiApi.listUsers,
  });

  const { data: auditData } = useQuery({
    queryKey: ["audit-logs"],
    queryFn: () => ldiApi.listAuditLogs("?page_size=25"),
  });

  const createUserMutation = useMutation({
    mutationFn: ldiApi.createUser,
    onSuccess: (created) => {
      setEmail("");
      setPassword("");
      setFirstName("");
      setLastName("");
      setErrorMsg(null);
      setStatusMsg(`Created staff account for ${created.email}.`);
      qc.invalidateQueries({ queryKey: ["staff-users"] });
      qc.invalidateQueries({ queryKey: ["audit-logs"] });
    },
    onError: (err) => setErrorMsg(err instanceof Error ? err.message : "Failed to create user"),
  });

  const toggleActiveMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      ldiApi.updateUser(id, { is_active }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["staff-users"] });
      qc.invalidateQueries({ queryKey: ["audit-logs"] });
    },
  });

  const updatePasswordMutation = useMutation({
    mutationFn: ({ id, password: pwd }: { id: string; password: string }) =>
      ldiApi.updateUser(id, { password: pwd }),
    onSuccess: (updated) => {
      setEditingPasswordUserId(null);
      setNewPassword("");
      setErrorMsg(null);
      setStatusMsg(`Password updated for ${updated.email}.`);
      qc.invalidateQueries({ queryKey: ["staff-users"] });
      qc.invalidateQueries({ queryKey: ["audit-logs"] });
    },
    onError: (err) => setErrorMsg(err instanceof Error ? err.message : "Failed to update password"),
  });

  return (
    <AppShell
      title="Staff Management & Security Audit Trail"
      subtitle="Administer role-based access accounts and inspect immutable security audit logs."
    >
      <div className="space-y-6">
        {isSuperAdmin && (
          <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
            <h3 className="text-sm font-semibold text-navy mb-3 flex items-center gap-2">
              <UserPlus className="h-4 w-4 text-brand" />
              Create Staff Account
            </h3>
            {errorMsg && (
              <div className="mb-3 rounded-lg bg-red-50 border border-red-200 px-3 py-2 text-xs text-red-700">
                {errorMsg}
              </div>
            )}
            <div className="grid grid-cols-1 sm:grid-cols-6 gap-2.5">
              <input
                placeholder="First Name"
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                className="px-3 py-2 text-xs rounded-lg border border-slate-300"
              />
              <input
                placeholder="Last Name"
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                className="px-3 py-2 text-xs rounded-lg border border-slate-300"
              />
              <input
                type="email"
                placeholder="staff@leaders.edu"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="px-3 py-2 text-xs rounded-lg border border-slate-300"
              />
              <input
                type="password"
                placeholder="Password (min 8 chars)"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="px-3 py-2 text-xs rounded-lg border border-slate-300"
              />
              <select
                value={roleName}
                onChange={(e) => setRoleName(e.target.value)}
                className="px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white"
              >
                <option value="OFFICER">Document Processing Officer</option>
                <option value="ADMIN">Administrator</option>
                <option value="VIEWER">Viewer / Supervisor</option>
                <option value="SUPER_ADMIN">Super Administrator</option>
              </select>
              <button
                onClick={() =>
                  createUserMutation.mutate({
                    email,
                    password,
                    first_name: firstName,
                    last_name: lastName,
                    role_name: roleName,
                  })
                }
                disabled={!email || !password || !firstName || !lastName}
                className="px-4 py-2 rounded-lg bg-brand text-white text-xs font-medium hover:bg-brand-light disabled:opacity-50"
              >
                Create Staff
              </button>
            </div>
          </div>
        )}

        {/* Staff Directory */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between gap-3">
            <h3 className="text-sm font-semibold text-navy">Staff Directory ({users.length})</h3>
            {statusMsg && (
              <span className="rounded-lg bg-emerald-50 border border-emerald-200 px-3 py-1 text-xs text-emerald-700 font-medium">
                {statusMsg}
              </span>
            )}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 uppercase">
                <tr>
                  <th className="px-4 py-2.5">Name</th>
                  <th className="px-4 py-2.5">Email</th>
                  <th className="px-4 py-2.5">Role</th>
                  <th className="px-4 py-2.5">Status</th>
                  <th className="px-4 py-2.5">Last Login</th>
                  {isSuperAdmin && <th className="px-4 py-2.5 text-right">Account Control</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {users.map((u) => (
                  <tr key={u.id}>
                    <td className="px-4 py-3 font-medium text-slate-900">
                      {u.first_name} {u.last_name}
                    </td>
                    <td className="px-4 py-3 text-slate-600">{u.email}</td>
                    <td className="px-4 py-3">
                      <span className="px-2 py-0.5 rounded bg-navy-50 text-navy font-medium">
                        {u.role}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`px-2 py-0.5 rounded-full font-medium ${
                          u.is_active
                            ? "bg-emerald-50 text-emerald-700"
                            : "bg-red-50 text-red-700"
                        }`}
                      >
                        {u.is_active ? "Active" : "Deactivated"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-500">{formatDateTime(u.last_login_at)}</td>
                    {isSuperAdmin && (
                      <td className="px-4 py-3 text-right">
                        {editingPasswordUserId === u.id ? (
                          <div className="inline-flex items-center justify-end gap-1.5">
                            <input
                              type="password"
                              placeholder="New password (8+ chars)"
                              value={newPassword}
                              onChange={(e) => setNewPassword(e.target.value)}
                              className="px-2.5 py-1 text-xs rounded border border-slate-300 w-44"
                            />
                            <button
                              type="button"
                              onClick={() =>
                                updatePasswordMutation.mutate({ id: u.id, password: newPassword })
                              }
                              disabled={newPassword.length < 8 || updatePasswordMutation.isPending}
                              className="px-2.5 py-1 rounded bg-brand text-white text-xs font-medium hover:bg-brand-light disabled:opacity-50"
                            >
                              {updatePasswordMutation.isPending ? "Saving..." : "Save"}
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                setEditingPasswordUserId(null);
                                setNewPassword("");
                              }}
                              className="px-2 py-1 rounded border border-slate-200 text-slate-600 hover:bg-slate-50 text-xs"
                            >
                              Cancel
                            </button>
                          </div>
                        ) : (
                          <div className="inline-flex items-center justify-end gap-2">
                            <button
                              type="button"
                              onClick={() => {
                                setEditingPasswordUserId(u.id);
                                setNewPassword("");
                                setStatusMsg(null);
                                setErrorMsg(null);
                              }}
                              className="inline-flex items-center gap-1 px-2.5 py-1 rounded border border-slate-200 text-navy hover:bg-slate-50 text-xs"
                            >
                              <KeyRound className="h-3.5 w-3.5" /> Change Password
                            </button>
                            <button
                              type="button"
                              onClick={() =>
                                toggleActiveMutation.mutate({ id: u.id, is_active: !u.is_active })
                              }
                              className={`inline-flex items-center gap-1 px-2.5 py-1 rounded border text-xs ${
                                u.is_active
                                  ? "border-red-200 text-red-700 hover:bg-red-50"
                                  : "border-emerald-200 text-emerald-700 hover:bg-emerald-50"
                              }`}
                            >
                              {u.is_active ? (
                                <>
                                  <UserX className="h-3.5 w-3.5" /> Deactivate
                                </>
                              ) : (
                                <>
                                  <UserCheck className="h-3.5 w-3.5" /> Activate
                                </>
                              )}
                            </button>
                          </div>
                        )}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Immutable Audit Logs */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-200 flex items-center gap-2">
            <Shield className="h-4 w-4 text-navy" />
            <h3 className="text-sm font-semibold text-navy">
              Immutable Audit Log Trail ({auditData?.total ?? 0} total events)
            </h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 uppercase">
                <tr>
                  <th className="px-4 py-2.5">Timestamp</th>
                  <th className="px-4 py-2.5">Actor</th>
                  <th className="px-4 py-2.5">Action</th>
                  <th className="px-4 py-2.5">Entity</th>
                  <th className="px-4 py-2.5">Sanitized Metadata</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {auditData?.items.map((log) => (
                  <tr key={log.id}>
                    <td className="px-4 py-2.5 text-slate-500 whitespace-nowrap">
                      {formatDateTime(log.created_at)}
                    </td>
                    <td className="px-4 py-2.5">
                      <span className="font-medium text-slate-800">{log.actor_email || "System"}</span>
                      {log.actor_role && (
                        <span className="ml-1.5 text-[10px] text-slate-400">({log.actor_role})</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 font-mono text-[11px] font-semibold text-navy">
                      {log.action}
                    </td>
                    <td className="px-4 py-2.5 text-slate-600">{log.entity_type}</td>
                    <td className="px-4 py-2.5 font-mono text-[11px] text-slate-500 max-w-md truncate">
                      {JSON.stringify(log.metadata_json)}
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
