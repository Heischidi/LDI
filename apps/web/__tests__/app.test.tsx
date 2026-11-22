import React from "react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/dashboard",
  useParams: () => ({ id: "app-1" }),
  useSearchParams: () => new URLSearchParams(""),
}));

// Mock auth hook
const mockLogin = vi.fn();
vi.mock("@/hooks/use-auth", () => ({
  useAuth: () => ({
    user: {
      id: "u1",
      email: "officer@leaders.edu",
      first_name: "Tunde",
      last_name: "Adeyemi",
      role: "OFFICER",
      permissions: [],
      is_active: true,
      created_at: "2026-01-01T00:00:00Z",
    },
    loading: false,
    login: mockLogin,
    logout: vi.fn(),
    hasRole: (...roles: string[]) => roles.includes("OFFICER"),
  }),
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

import LoginPage from "@/app/login/page";
import ApplicantsPage from "@/app/applicants/page";
import ProcessingPage from "@/app/processing/page";
import ApplicantDetailPage from "@/app/applicants/[id]/page";
import RequirementsManagerPage from "@/app/requirements/page";
import { ldiApi } from "@/lib/api-client";

function renderWithQuery(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("Leaders Document Intelligence Frontend Workflows", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders login form and validates submission", async () => {
    renderWithQuery(<LoginPage />);
    expect(screen.getByText("Staff Sign In")).toBeInTheDocument();
    expect(screen.queryByText(/superadmin@leaders\.edu/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Seeded Staff Accounts/i)).not.toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText(/Enter your username or staff email/i), {
      target: { value: "officer@leaders.edu" },
    });
    fireEvent.change(screen.getByPlaceholderText("••••••••••••"), {
      target: { value: "LeadersOfficer!2026" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Sign In to Workspace/i }));
    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith("officer@leaders.edu", "LeadersOfficer!2026");
    });
  });

  it("renders applicants list and New Applicant modal with dynamic checklist", async () => {
    vi.spyOn(ldiApi, "listApplicants").mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 20,
    });
    vi.spyOn(ldiApi, "listDestinations").mockResolvedValue([
      { id: "d1", name: "United Kingdom", code: "GB", is_active: true },
    ]);
    vi.spyOn(ldiApi, "listPurposes").mockResolvedValue([
      { id: "p1", name: "Study", code: "STUDY", is_active: true },
    ]);
    vi.spyOn(ldiApi, "listCategories").mockResolvedValue([
      { id: "c1", name: "Student Visa", code: "STUDENT_VISA", is_archived: false },
    ]);

    renderWithQuery(<ApplicantsPage />);
    const newBtn = await screen.findByRole("button", { name: /New Applicant/i });
    fireEvent.click(newBtn);
    expect(screen.getByText("New Applicant Record")).toBeInTheDocument();
  });

  it("renders bulk upload workflow and processing trigger", async () => {
    vi.spyOn(ldiApi, "listApplicants").mockResolvedValue({
      items: [
        {
          id: "app-1",
          application_reference: "LDI-2026-0001",
          first_name: "John",
          last_name: "Doe",
          full_name: "John Doe",
          email: "john@example.com",
          phone_number: "+234800",
          nationality: "Nigerian",
          applicant_type: "STANDARD",
          destination: { id: "d1", name: "United Kingdom", code: "GB", is_active: true },
          purpose: { id: "p1", name: "Study", code: "STUDY", is_active: true },
          category: { id: "c1", name: "Student Visa", code: "STUDENT_VISA", is_archived: false },
          status: "DRAFT",
          is_archived: false,
          document_count: 0,
          missing_required_count: 9,
          pending_review_count: 0,
          created_at: "2026-11-15T10:00:00Z",
          updated_at: "2026-11-15T10:00:00Z",
        },
      ],
      total: 1,
      page: 1,
      page_size: 100,
    });
    vi.spyOn(ldiApi, "listBatches").mockResolvedValue([]);

    renderWithQuery(<ProcessingPage />);
    expect(await screen.findByText(/Start AI Processing/i)).toBeInTheDocument();
  });

  it("renders applicant classification review and export workflow", async () => {
    vi.spyOn(ldiApi, "getApplicant").mockResolvedValue({
      id: "app-1",
      application_reference: "LDI-2026-0001",
      first_name: "John",
      last_name: "Doe",
      full_name: "John Doe",
      email: "john@example.com",
      phone_number: "+234800",
      nationality: "Nigerian",
      applicant_type: "STANDARD",
      destination: { id: "d1", name: "United Kingdom", code: "GB", is_active: true },
      purpose: { id: "p1", name: "Study", code: "STUDY", is_active: true },
      category: { id: "c1", name: "Student Visa", code: "STUDENT_VISA", is_archived: false },
      status: "AWAITING_REVIEW",
      is_archived: false,
      document_count: 1,
      missing_required_count: 1,
      pending_review_count: 1,
      eligibility_context: {},
      created_at: "2026-11-15T10:00:00Z",
      updated_at: "2026-11-15T10:00:00Z",
      checklist: [
        {
          id: "chk1",
          document_requirement_id: "r1",
          document_type_id: "dt1",
          document_type_code: "INTERNATIONAL_PASSPORT",
          document_type_name: "International Passport",
          requirement_level: "REQUIRED",
          display_order: 1,
          status: "FOUND",
          verification_stage: "QUALITY_CHECKED",
          quality_issues: [],
        },
      ],
      documents: [
        {
          id: "doc1",
          batch_id: "b1",
          original_filename: "IMG_0012.pdf",
          file_extension: "pdf",
          detected_mime_type: "application/pdf",
          file_size_bytes: 1024,
          sha256_hash: "abc",
          ingestion_type: "SEARCHABLE_PDF",
          page_count: 1,
          processing_status: "AWAITING_REVIEW",
          is_excluded: false,
          is_duplicate: false,
          is_approved_for_export: false,
          preview_url: "/api/documents/doc1/preview",
          proposed_filename: "01_International_Passport.pdf",
          classification: {
            id: "cls1",
            predicted_type_code: "INTERNATIONAL_PASSPORT",
            confidence: 0.96,
            confidence_tier: "HIGH",
            has_name_mismatch: false,
            is_expired: false,
            is_readable: true,
            possible_issues: [],
            classification_reason: "Matched passport fields",
            status: "AUTO_PREPARED",
          },
        },
      ],
      batches: [],
      exports: [],
    });
    vi.spyOn(ldiApi, "listDocumentTypes").mockResolvedValue([
      {
        id: "dt1",
        code: "INTERNATIONAL_PASSPORT",
        name: "International Passport",
        category: "IDENTITY",
        default_order: 1,
        has_expiry: true,
        aliases: [],
      },
    ]);

    renderWithQuery(<ApplicantDetailPage />);
    expect(await screen.findByText("IMG_0012.pdf")).toBeInTheDocument();
    expect(screen.getByText("01_International_Passport.pdf")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Download Organised Folder/i })).toBeInTheDocument();
  });

  it("renders configurable requirements manager", async () => {
    vi.spyOn(ldiApi, "listRequirements").mockResolvedValue([
      {
        id: "rs1",
        name: "United Kingdom - Study (Student Visa)",
        destination_id: "d1",
        destination_name: "United Kingdom",
        purpose_id: "p1",
        purpose_name: "Study",
        category_id: "c1",
        category_name: "Student Visa",
        applicant_type: "STANDARD",
        naming_convention: "{document_order}_{document_type}.{extension}",
        folder_template: "LEADERS_EDU_TOUR_DOCUMENTS/{DESTINATION}/{PURPOSE}/{APPLICANT_NAME}_{APPLICATION_REFERENCE}",
        is_active: true,
        active_version: {
          id: "v1",
          version_number: 1,
          items: [],
        },
        versions_summary: [],
      },
    ]);
    vi.spyOn(ldiApi, "listDocumentTypes").mockResolvedValue([]);
    vi.spyOn(ldiApi, "listDestinations").mockResolvedValue([]);
    vi.spyOn(ldiApi, "listPurposes").mockResolvedValue([]);
    vi.spyOn(ldiApi, "listCategories").mockResolvedValue([]);

    renderWithQuery(<RequirementsManagerPage />);
    expect(
      await screen.findByRole("heading", { name: "United Kingdom - Study (Student Visa)" })
    ).toBeInTheDocument();
  });
});
