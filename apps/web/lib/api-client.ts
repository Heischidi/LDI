import type {
  ApplicantDetail,
  ApplicantSummary,
  ApplicationCategory,
  DashboardMetrics,
  Destination,
  DocumentRecord,
  DocumentType,
  RequirementSet,
  TokenResponse,
  TravelPurpose,
  UserSummary,
} from "@/types";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://localhost:8000";

const TOKEN_KEY = "ldi_access_token";
const REFRESH_KEY = "ldi_refresh_token";
const USER_KEY = "ldi_user";

export function getStoredTokens() {
  if (typeof window === "undefined") return { access: null, refresh: null };
  return {
    access: window.localStorage.getItem(TOKEN_KEY),
    refresh: window.localStorage.getItem(REFRESH_KEY),
  };
}

export function setStoredSession(data: TokenResponse) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(TOKEN_KEY, data.access_token);
  window.localStorage.setItem(REFRESH_KEY, data.refresh_token);
  window.localStorage.setItem(USER_KEY, JSON.stringify(data.user));
}

export function clearStoredSession() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(REFRESH_KEY);
  window.localStorage.removeItem(USER_KEY);
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
  retry = true
): Promise<T> {
  const { access, refresh } = getStoredTokens();
  const headers = new Headers(options.headers || {});
  if (access) {
    headers.set("Authorization", `Bearer ${access}`);
  }
  if (!(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (res.status === 401 && retry && refresh) {
    const refreshRes = await fetch(`${API_BASE_URL}/api/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refresh }),
    });
    if (refreshRes.ok) {
      const tokenData: TokenResponse = await refreshRes.json();
      setStoredSession(tokenData);
      return apiRequest<T>(path, options, false);
    }
    clearStoredSession();
  }

  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const errBody = await res.json();
      detail =
        typeof errBody.detail === "string"
          ? errBody.detail
          : errBody.detail?.message || JSON.stringify(errBody.detail || errBody);
    } catch {
      // ignore json parse error
    }
    throw new Error(detail);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export async function downloadAuthorizedFile(path: string, fallbackName: string) {
  const { access } = getStoredTokens();
  const res = await fetch(`${API_BASE_URL}${path}`, {
    headers: access ? { Authorization: `Bearer ${access}` } : {},
  });
  if (!res.ok) {
    throw new Error(`Download failed (${res.status})`);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = fallbackName;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export const ldiApi = {
  login: (email: string, password: string) =>
    apiRequest<TokenResponse>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  logout: () => apiRequest<{ message: string }>("/api/auth/logout", { method: "POST" }),
  me: () => apiRequest<UserSummary>("/api/auth/me"),
  requestPasswordReset: (email: string) =>
    apiRequest<{ message: string }>("/api/auth/password-reset/request", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),

  getDashboardMetrics: () => apiRequest<DashboardMetrics>("/api/dashboard/metrics"),

  listDestinations: () => apiRequest<Destination[]>("/api/reference/destinations"),
  listPurposes: () => apiRequest<TravelPurpose[]>("/api/reference/purposes"),
  listCategories: (params = "") =>
    apiRequest<ApplicationCategory[]>(`/api/reference/categories${params}`),
  createCategory: (payload: Record<string, unknown>) =>
    apiRequest<ApplicationCategory>("/api/reference/categories", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  listApplicants: (query = "") =>
    apiRequest<{ items: ApplicantSummary[]; total: number; page: number; page_size: number }>(
      `/api/applicants${query}`
    ),
  createApplicant: (payload: Record<string, unknown>) =>
    apiRequest<ApplicantDetail>("/api/applicants", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getApplicant: (id: string) => apiRequest<ApplicantDetail>(`/api/applicants/${id}`),
  archiveApplicant: (id: string) =>
    apiRequest<{ message: string }>(`/api/applicants/${id}`, { method: "DELETE" }),

  listRequirements: () => apiRequest<RequirementSet[]>("/api/requirements"),
  matchRequirementSet: (destinationId: string, purposeId: string, categoryId: string) =>
    apiRequest<RequirementSet | null>(
      `/api/requirements/match?destination_id=${destinationId}&purpose_id=${purposeId}&category_id=${categoryId}`
    ),
  createRequirementSet: (payload: Record<string, unknown>) =>
    apiRequest<RequirementSet>("/api/requirements", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateRequirementSet: (id: string, payload: Record<string, unknown>) =>
    apiRequest<RequirementSet>(`/api/requirements/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  listDocumentTypes: () => apiRequest<DocumentType[]>("/api/requirements/document-types"),
  createDocumentType: (payload: Record<string, unknown>) =>
    apiRequest<DocumentType>("/api/requirements/document-types", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  uploadDocuments: (applicantId: string, files: File[]) => {
    const fd = new FormData();
    fd.append("applicant_id", applicantId);
    files.forEach((f) => fd.append("files", f));
    return apiRequest<{
      batch_id: string;
      applicant_id: string;
      total_accepted: number;
      rejected: Array<{ filename: string; reason: string }>;
      documents: DocumentRecord[];
    }>("/api/documents/upload", { method: "POST", body: fd });
  },
  startBatchProcessing: (batchId: string) =>
    apiRequest<{ batch_id: string; task_id: string; status: string }>(
      "/api/processing/batches",
      { method: "POST", body: JSON.stringify({ batch_id: batchId }) }
    ),
  listBatches: () =>
    apiRequest<
      Array<{
        id: string;
        applicant_id: string;
        applicant_name: string;
        application_reference: string;
        status: string;
        total_files: number;
        processed_files: number;
        failed_files: number;
        created_at: string;
      }>
    >("/api/processing/batches"),
  getBatchStatus: (batchId: string) =>
    apiRequest<{
      id: string;
      applicant_id: string;
      status: string;
      total_files: number;
      processed_files: number;
      failed_files: number;
      jobs: Array<{
        id: string;
        uploaded_document_id: string;
        original_filename: string;
        status: string;
        progress_percent: number;
        error_log?: string | null;
      }>;
      documents: DocumentRecord[];
    }>(`/api/processing/batches/${batchId}/status`),
  retryBatch: (batchId: string) =>
    apiRequest<{ batch_id: string; retried_jobs: number }>(
      `/api/processing/batches/${batchId}/retry`,
      { method: "POST" }
    ),

  listProcessedDocuments: (query = "") =>
    apiRequest<
      Array<{
        id: string;
        applicant_id: string;
        applicant_name: string;
        application_reference: string;
        original_filename: string;
        generated_filename?: string | null;
        relative_folder_path?: string | null;
        is_approved_for_export: boolean;
        predicted_type_code?: string | null;
        confidence?: number | null;
        confidence_tier?: string | null;
        classification_status?: string | null;
        is_duplicate: boolean;
        is_excluded: boolean;
        preview_url: string;
      }>
    >(`/api/documents${query}`),

  correctClassification: (documentId: string, payload: Record<string, unknown>) =>
    apiRequest<DocumentRecord>(`/api/documents/${documentId}/classification`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  approveDocument: (documentId: string) =>
    apiRequest<DocumentRecord>(`/api/documents/${documentId}/approve`, { method: "POST" }),
  reprocessDocument: (documentId: string) =>
    apiRequest<DocumentRecord>(`/api/documents/${documentId}/reprocess`, { method: "POST" }),
  bulkApprove: (applicantId: string, minConfidence = 0.9) =>
    apiRequest<{ approved_count: number; approved_document_ids: string[] }>(
      "/api/documents/bulk-approve",
      {
        method: "POST",
        body: JSON.stringify({ applicant_id: applicantId, min_confidence: minConfidence }),
      }
    ),

  generateExport: (applicantId: string) =>
    apiRequest<{
      export_id: string;
      folder_root: string;
      approved_doc_count: number;
      missing_doc_count: number;
      download_url: string;
    }>(`/api/applicants/${applicantId}/export`, { method: "POST" }),

  getReportSummary: (query = "") =>
    apiRequest<{
      total_applicants_processed: number;
      total_documents_classified: number;
      average_processing_seconds: number;
      ai_correction_rate_percent: number;
      processing_failure_rate_percent: number;
      common_destinations: Array<{ name: string; count: number }>;
      common_application_types: Array<{ name: string; count: number }>;
      most_frequently_missing_documents: Array<{ document_type: string; count: number }>;
      officer_processing_statistics: Array<{
        officer_name: string;
        email: string;
        uploads_count: number;
      }>;
    }>(`/api/reports/summary${query}`),

  listUsers: () => apiRequest<UserSummary[]>("/api/users"),
  createUser: (payload: Record<string, unknown>) =>
    apiRequest<UserSummary>("/api/users", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateUser: (id: string, payload: Record<string, unknown>) =>
    apiRequest<UserSummary>(`/api/users/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  listAuditLogs: (query = "") =>
    apiRequest<{
      items: Array<{
        id: string;
        actor_email?: string | null;
        actor_role?: string | null;
        action: string;
        entity_type: string;
        entity_id?: string | null;
        ip_address?: string | null;
        metadata_json: Record<string, unknown>;
        created_at: string;
      }>;
      total: number;
    }>(`/api/audit-logs${query}`),

  listSettings: () =>
    apiRequest<
      Array<{
        id: string;
        key: string;
        value_json: Record<string, unknown>;
        category: string;
        description?: string | null;
        updated_at: string;
      }>
    >("/api/settings"),
  updateSetting: (key: string, value_json: Record<string, unknown>) =>
    apiRequest(`/api/settings/${key}`, {
      method: "PATCH",
      body: JSON.stringify({ value_json }),
    }),
};
