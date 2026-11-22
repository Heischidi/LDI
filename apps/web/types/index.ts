export type UserRole = "CEO" | "SUPER_ADMIN" | "ADMIN" | "OFFICER" | "VIEWER";

export interface UserSummary {
  id: string;
  username?: string | null;
  email: string;
  first_name: string;
  last_name: string;
  phone_number?: string | null;
  role: UserRole;
  permissions: string[];
  is_active: boolean;
  last_login_at?: string | null;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: UserSummary;
}

export interface Destination {
  id: string;
  name: string;
  code: string;
  region?: string | null;
  is_active: boolean;
}

export interface TravelPurpose {
  id: string;
  name: string;
  code: string;
  description?: string | null;
  is_active: boolean;
}

export interface ApplicationCategory {
  id: string;
  name: string;
  code: string;
  destination_id?: string | null;
  purpose_id?: string | null;
  description?: string | null;
  is_archived: boolean;
}

export interface ChecklistItem {
  id: string;
  document_requirement_id: string;
  document_type_id: string;
  document_type_code: string;
  document_type_name: string;
  requirement_level: "REQUIRED" | "OPTIONAL" | "CONDITIONAL";
  display_order: number;
  status: string;
  verification_stage: string;
  matched_document_id?: string | null;
  matched_filename?: string | null;
  generated_filename?: string | null;
  condition_explanation?: string | null;
  custom_instructions?: string | null;
  quality_issues: string[];
}

export interface ClassificationInfo {
  id: string;
  predicted_type_code: string;
  document_type_id?: string | null;
  document_type_name?: string | null;
  confidence: number;
  confidence_tier: "HIGH" | "MEDIUM" | "LOW";
  extracted_applicant_name?: string | null;
  has_name_mismatch: boolean;
  document_number?: string | null;
  issuing_authority?: string | null;
  issue_date?: string | null;
  expiry_date?: string | null;
  is_expired: boolean;
  is_readable: boolean;
  possible_issues: string[];
  classification_reason: string;
  status: string;
}

export interface DocumentRecord {
  id: string;
  batch_id: string;
  applicant_id?: string;
  original_filename: string;
  source_archive_name?: string | null;
  file_extension: string;
  detected_mime_type: string;
  file_size_bytes: number;
  sha256_hash: string;
  ingestion_type: string;
  page_count: number;
  processing_status: string;
  is_excluded: boolean;
  is_duplicate: boolean;
  duplicate_of_id?: string | null;
  duplicate_reason?: string | null;
  error_message?: string | null;
  extracted_text_preview?: string;
  extraction_method?: string | null;
  proposed_filename?: string | null;
  is_approved_for_export: boolean;
  preview_url: string;
  classification?: ClassificationInfo | null;
}

export interface ApplicantSummary {
  id: string;
  application_reference: string;
  first_name: string;
  middle_name?: string | null;
  last_name: string;
  full_name: string;
  email: string;
  phone_number: string;
  date_of_birth?: string | null;
  nationality: string;
  applicant_type: string;
  destination: Destination;
  purpose: TravelPurpose;
  category: ApplicationCategory;
  assigned_officer?: {
    id: string;
    first_name: string;
    last_name: string;
    email: string;
  } | null;
  requirement_version_id?: string | null;
  status: string;
  is_archived: boolean;
  document_count: number;
  missing_required_count: number;
  pending_review_count: number;
  created_at: string;
  updated_at: string;
}

export interface StageMilestoneOption {
  code: string;
  label: string;
  applicant_status: string;
  default_subject: string;
  default_message: string;
}

export interface StageUpdateItem {
  id: string;
  applicant_id: string;
  track: string;
  stage_code: string;
  stage_label: string;
  subject: string;
  message_body: string;
  recipient_email: string;
  delivery_status: string;
  delivery_provider: string;
  delivery_detail?: string | null;
  sent_by_name?: string | null;
  created_at: string;
}

export interface ApplicantDetail extends ApplicantSummary {
  passport_number_masked?: string | null;
  current_stage_code?: string | null;
  current_stage_label?: string | null;
  eligibility_context: Record<string, unknown>;
  checklist: ChecklistItem[];
  documents: DocumentRecord[];
  batches: Array<{
    id: string;
    status: string;
    total_files: number;
    processed_files: number;
    failed_files: number;
    created_at: string;
    completed_at?: string | null;
  }>;
  exports: Array<{
    id: string;
    folder_root: string;
    approved_doc_count: number;
    missing_doc_count: number;
    download_url: string;
    created_at: string;
  }>;
  stage_updates?: StageUpdateItem[];
}

export interface DocumentType {
  id: string;
  code: string;
  name: string;
  category: string;
  default_order: number;
  has_expiry: boolean;
  min_validity_days?: number | null;
  naming_prefix?: string | null;
  aliases: Array<{ id: string; alias_name: string; is_active: boolean }>;
}

export interface RequirementSet {
  id: string;
  name: string;
  destination_id: string;
  destination_name: string;
  purpose_id: string;
  purpose_name: string;
  category_id: string;
  category_name: string;
  applicant_type: string;
  naming_convention: string;
  folder_template: string;
  is_active: boolean;
  active_version_id?: string | null;
  active_version?: {
    id: string;
    version_number: number;
    change_notes?: string | null;
    items: Array<{
      id: string;
      document_type_id: string;
      document_type_code: string;
      document_type_name: string;
      requirement_level: "REQUIRED" | "OPTIONAL" | "CONDITIONAL";
      display_order: number;
      condition_explanation?: string | null;
      min_validity_days?: number | null;
      custom_instructions?: string | null;
    }>;
  } | null;
  versions_summary: Array<{
    id: string;
    version_number: number;
    effective_from: string;
    change_notes?: string | null;
    item_count: number;
  }>;
}

export interface DashboardMetrics {
  total_applicants: number;
  total_documents_processed: number;
  applications_processing: number;
  completed_batches: number;
  applications_with_missing_docs: number;
  documents_awaiting_review: number;
  failed_processing_jobs: number;
  completion_rate_percent: number;
  documents_over_time: Array<{ date: string; count: number }>;
  applicants_by_destination: Array<{ name: string; count: number }>;
  applicants_by_purpose: Array<{ name: string; count: number }>;
  missing_document_stats: Array<{ document_type: string; missing_count: number }>;
  recent_applicants: Array<{
    id: string;
    application_reference: string;
    full_name: string;
    destination: string;
    purpose: string;
    status: string;
    created_at: string;
  }>;
  recent_activity: Array<{
    id: string;
    action: string;
    entity_type: string;
    actor_email: string;
    created_at: string;
  }>;
  officer_activity: Array<{
    name: string;
    email: string;
    assigned_applicants: number;
  }>;
}

export interface PersonalReminderItem {
  id: string;
  user_id: string;
  title: string;
  notes?: string | null;
  recipient_email: string;
  times_per_day: number;
  morning_time: string;
  evening_time: string;
  is_completed: boolean;
  completed_at?: string | null;
  send_count: number;
  last_sent_at?: string | null;
  next_send_at?: string | null;
  last_delivery_status?: string | null;
  last_delivery_provider?: string | null;
  last_delivery_detail?: string | null;
  created_at: string;
  updated_at: string;
}

export interface StatementOfPurposeItem {
  id: string;
  applicant_id?: string | null;
  created_by_id?: string | null;
  candidate_name: string;
  university_name: string;
  course_or_program: string;
  degree_level: string;
  entry_term: string;
  destination_country: string;
  academic_background?: string | null;
  work_experience?: string | null;
  career_goals?: string | null;
  why_university?: string | null;
  funding_and_ties?: string | null;
  tone: string;
  word_count_target: number;
  generated_content: string;
  ai_provider: string;
  ai_model: string;
  created_at: string;
  updated_at: string;
}
