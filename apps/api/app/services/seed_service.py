"""Idempotent database seeder for initial roles, permissions, users, checklists, and settings."""

from datetime import datetime, timezone
import secrets

from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from app.core.security import compute_base_username, hash_password
from app.models.entities import (
    Applicant,
    ApplicationCategory,
    Destination,
    DocumentAlias,
    DocumentRequirement,
    DocumentType,
    Permission,
    RequirementSet,
    RequirementVersion,
    Role,
    SystemSetting,
    TravelPurpose,
    User,
)

DEFAULT_PERMISSIONS = [
    ("applicants:read", "applicants", "View applicant records"),
    ("applicants:write", "applicants", "Create and update applicant records"),
    ("applicants:delete", "applicants", "Archive or delete applicant records"),
    ("documents:upload", "documents", "Upload and process document batches"),
    ("documents:review", "documents", "Review and override AI classifications"),
    ("documents:approve", "documents", "Approve processed documents and folders"),
    ("exports:download", "exports", "Generate and download organised ZIP packages and reports"),
    ("requirements:read", "requirements", "View document requirement checklists"),
    ("requirements:write", "requirements", "Create and modify document requirement checklists"),
    ("reports:read", "reports", "View and export analytics reports"),
    ("users:manage", "staff", "Manage staff accounts and role assignments"),
    ("audit:read", "audit", "Inspect immutable security audit logs"),
    ("settings:manage", "settings", "Configure AI providers, naming conventions, and security settings"),
]

ROLE_DEFINITIONS = {
    "CEO": (
        "Chief Executive Officer (CEO)",
        "Complete executive and Super Admin platform access plus twice-daily personal email reminders.",
        [p[0] for p in DEFAULT_PERMISSIONS],
    ),
    "SUPER_ADMIN": (
        "Super Administrator",
        "Complete platform access across staff, requirements, AI providers, applicants, and audit logs.",
        [p[0] for p in DEFAULT_PERMISSIONS],
    ),
    "ADMIN": (
        "Administrator",
        "Manage applicants, document requirements, document processing, and reporting.",
        [
            "applicants:read",
            "applicants:write",
            "applicants:delete",
            "documents:upload",
            "documents:review",
            "documents:approve",
            "exports:download",
            "requirements:read",
            "requirements:write",
            "reports:read",
        ],
    ),
    "OFFICER": (
        "Document Processing Officer",
        "Create applicants, upload document batches, review/override AI classifications, approve and export folders.",
        [
            "applicants:read",
            "applicants:write",
            "documents:upload",
            "documents:review",
            "documents:approve",
            "exports:download",
            "requirements:read",
            "reports:read",
        ],
    ),
    "VIEWER": (
        "Viewer / Supervisor",
        "Read-only visibility into applicants, processing results, and reports.",
        [
            "applicants:read",
            "requirements:read",
            "reports:read",
        ],
    ),
}

DEFAULT_DESTINATIONS = [
    ("Canada", "CA", "North America"),
    ("United States", "US", "North America"),
    ("United Kingdom", "GB", "Europe"),
    ("Malta", "MT", "Europe"),
    ("France", "FR", "Europe"),
    ("Germany", "DE", "Europe"),
    ("Ireland", "IE", "Europe"),
    ("Netherlands", "NL", "Europe"),
    ("Spain", "ES", "Europe"),
    ("Australia", "AU", "Oceania"),
]

DEFAULT_PURPOSES = [
    ("Study", "STUDY", "Academic study, university admissions, and student visas"),
    ("Tourism", "TOURISM", "Short-stay leisure and tourist travel"),
    ("Business", "BUSINESS", "Corporate conferences, meetings, and business travel"),
    ("Work", "WORK", "Skilled employment and work permit applications"),
    ("Family Visit", "FAMILY_VISIT", "Visiting family members or dependants abroad"),
    ("Immigration", "IMMIGRATION", "Permanent residency or long-term settlement pathways"),
    ("Other", "OTHER", "Specialised or bespoke travel categories"),
]

DEFAULT_DOCUMENT_TYPES = [
    ("INTERNATIONAL_PASSPORT", "International Passport", "IDENTITY", 1, True, 180, "International_Passport", ["Travel Passport", "Passport Bio Page", "Passport Data Page", "Nigerian Passport"]),
    ("ADMISSION_LETTER", "Letter of Acceptance (LOA) / Admission Letter", "ACADEMIC", 2, False, None, "Admission_Letter", ["Offer Letter", "CAS Letter", "Unconditional Offer", "University Admission Letter", "Letter of Acceptance", "LOA", "DLI Acceptance Letter"]),
    ("ACADEMIC_TRANSCRIPT", "Academic / Degree Transcript", "ACADEMIC", 3, False, None, "Academic_Transcript", ["Student Transcript", "Official Transcript", "Transcript of Records", "Degree Transcript"]),
    ("ACADEMIC_CERTIFICATES", "Academic / Degree Certificates", "ACADEMIC", 4, False, None, "Academic_Certificates", ["Degree Certificate", "Diploma Certificate", "Graduation Certificate", "BSc Certificate"]),
    ("BANK_STATEMENT", "Bank Statement (+ Certificate)", "FINANCIAL", 5, True, 28, "Bank_Statement", ["Statement of Account", "Account Statement", "Financial Statement", "Six Months Personal Bank Statement", "Bank Reference Certificate"]),
    ("BIRTH_CERTIFICATE", "Birth Certificate", "IDENTITY", 6, False, None, "Birth_Certificate", ["Certificate of Birth", "NPC Birth Certificate"]),
    ("STATEMENT_OF_PURPOSE", "Statement of Purpose (SOP)", "SUPPORTING", 7, False, None, "Statement_of_Purpose", ["Personal Statement", "Motivation Letter", "SOP"]),
    ("ENGLISH_PROFICIENCY", "Proof of English Proficiency", "ACADEMIC", 8, True, 90, "Proof_of_English_Proficiency", ["IELTS Result", "TOEFL Score Report", "PTE Academic", "IELTS TRF"]),
    ("PASSPORT_PHOTOGRAPH", "Passport Photograph (White Background)", "IDENTITY", 9, False, None, "Passport_Photograph", ["Biometric Photo", "Passport Photo"]),
    ("SPONSORSHIP_LETTER", "Sponsorship Letter", "FINANCIAL", 10, False, None, "Sponsorship_Letter", ["Financial Sponsor Letter", "Affidavit of Support"]),
    ("MEDICAL_CERTIFICATE", "Medical / TB Certificate", "HEALTH", 11, True, 90, "Medical_Certificate", ["TB Test Certificate", "IOM TB Clearance"]),
    ("EMPLOYMENT_LETTER", "Employment Verification Letter", "EMPLOYMENT", 12, False, None, "Employment_Letter", ["Employer Letter", "Work Reference Letter"]),
    ("POLICE_CLEARANCE", "Police Clearance Certificate", "BACKGROUND", 13, True, 90, "Police_Clearance", ["Criminal Record Check", "Character Certificate"]),
    ("TRAVEL_ITINERARY", "Travel Itinerary", "TRAVEL", 14, False, None, "Travel_Itinerary", ["Flight Reservation", "Flight Booking"]),
    ("HOTEL_BOOKING", "Accommodation / Hotel Booking", "TRAVEL", 15, False, None, "Hotel_Booking", ["Hotel Reservation", "Tenancy Agreement"]),
    ("CURRICULUM_VITAE", "Curriculum Vitae (CV)", "ACADEMIC", 16, False, None, "Curriculum_Vitae", ["CV", "Resume", "Academic CV"]),
    ("WAEC_NECO_CERTIFICATE", "WAEC / NECO Certificate", "ACADEMIC", 17, False, None, "WAEC_NECO_Certificate", ["WAEC Certificate", "NECO Certificate", "SSCE Certificate", "WASSCE Certificate"]),
    ("WAEC_NECO_SCRATCH_CARD", "WAEC / NECO Scratch Card", "ACADEMIC", 18, False, None, "WAEC_NECO_Scratch_Card", ["WAEC Scratch Card", "NECO Scratch Card", "Result Checker PIN"]),
    ("ACADEMIC_REFERENCE_LETTER", "Academic Reference Letter", "ACADEMIC", 19, False, None, "Academic_Reference_Letter", ["Reference Letter", "Academic Recommendation Letter"]),
    ("NIN_SLIP", "NIN Slip", "IDENTITY", 20, False, None, "NIN_Slip", ["National Identification Number Slip", "NIMC Slip"]),
    ("TRAINING_CERTIFICATES", "Training and Professional Certificates", "ACADEMIC", 21, False, None, "Training_Professional_Certificates", ["Professional Certificate", "Training Certificate"]),
    ("PARENTS_CONSENT_LETTER", "Parents' Consent Letter", "SUPPORTING", 22, False, None, "Parents_Consent_Letter", ["Parental Consent Letter", "Parent Consent"]),
    ("PROMOTION_LETTER", "Promotion Letter(s)", "EMPLOYMENT", 23, False, None, "Promotion_Letter", ["Letter of Promotion"]),
    ("EMPLOYER_INTRODUCTION_LETTER", "Letter of Introduction from Employer", "EMPLOYMENT", 24, False, None, "Employer_Introduction_Letter", ["Employer Introduction Letter"]),
    ("STUDY_LEAVE_LETTER", "Study Leave / Letter of Exemption to Study", "EMPLOYMENT", 25, False, None, "Study_Leave_Letter", ["Study Leave Approval", "Letter of Exemption to Study"]),
    ("WORK_ID_CARD", "Work ID Card", "EMPLOYMENT", 26, False, None, "Work_ID_Card", ["Staff ID Card", "Employee ID Card"]),
    ("PAYSLIPS", "Six (6) Months' Payslips", "EMPLOYMENT", 27, False, None, "Six_Months_Payslips", ["Salary Payslips", "Monthly Payslips"]),
    ("BUSINESS_REGISTRATION", "Business Registration Documents", "FINANCIAL", 28, False, None, "Business_Registration_Documents", ["CAC Certificate", "Certificate of Incorporation", "Business Name Registration"]),
    ("BUSINESS_BANK_STATEMENT", "Business Bank Statement", "FINANCIAL", 29, True, 28, "Business_Bank_Statement", ["Corporate Bank Statement", "Company Bank Statement"]),
    ("TAX_CLEARANCE_CERTIFICATE", "Tax Clearance Certificate", "FINANCIAL", 30, True, 90, "Tax_Clearance_Certificate", ["FIRS Tax Clearance", "TCC"]),
    ("LAND_DOCUMENTS", "Land Documents", "ASSETS", 31, False, None, "Land_Documents", ["Land Purchase Agreement", "Land Allocation"]),
    ("CERTIFICATE_OF_OCCUPANCY", "Certificate of Occupancy (C of O)", "ASSETS", 32, False, None, "Certificate_of_Occupancy", ["C of O", "Statutory Right of Occupancy"]),
    ("SURVEY_PLAN", "Survey Plan", "ASSETS", 33, False, None, "Survey_Plan", ["Registered Survey Plan"]),
    ("DEED_OF_ASSIGNMENT", "Deed of Assignment", "ASSETS", 34, False, None, "Deed_of_Assignment", ["Deed of Conveyance"]),
    ("PROPERTY_VALUATION_REPORT", "Property Valuation Report", "ASSETS", 35, False, None, "Property_Valuation_Report", ["Estate Valuation Report"]),
    ("OTHER_ASSET_DOCUMENTS", "Other Investment or Asset Documents", "ASSETS", 36, False, None, "Other_Asset_Documents", ["Investment Certificate", "Share Certificate"]),
    ("NOTARY_FEE_RECEIPT", "Lawyer's Notary Fee Receipt (₦100,000)", "FEES", 37, False, None, "Lawyers_Notary_Fee_Receipt", ["Notary Fee Receipt", "Lawyer Notary Fee"]),
    ("ADDITIONAL_DOCUMENT", "Additional Supporting Document", "GENERAL", 90, False, None, "Additional_Document", ["Supplementary Document"]),
    ("UNKNOWN", "Unclassified / Unknown Document", "GENERAL", 99, False, None, "Unknown_Document", []),
]


def generate_unique_username(
    db: Session,
    first_name: str,
    last_name: str,
    exclude_user_id: str | None = None,
) -> str:
    """Return unique username using lastname + first two letters of firstname (suffix if needed)."""
    base = compute_base_username(first_name, last_name)
    candidate = base
    suffix = 2
    while True:
        existing = db.scalar(select(User).where(User.username == candidate))
        if not existing or (exclude_user_id and existing.id == exclude_user_id):
            return candidate
        candidate = f"{base}{suffix}"
        suffix += 1


def _ensure_user_username_column(db: Session) -> None:
    """Safely add users.username column on existing databases if not yet migrated."""
    inspector = inspect(db.get_bind())
    if "users" not in inspector.get_table_names():
        return
    cols = {col["name"] for col in inspector.get_columns("users")}
    if "username" not in cols:
        db.execute(text("ALTER TABLE users ADD COLUMN username VARCHAR(100)"))
        db.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username ON users (username)"))
        db.commit()


def _ensure_applicant_tracking_token_column(db: Session) -> None:
    """Safely add applicants.tracking_token column on existing DBs and backfill existing applicants."""
    inspector = inspect(db.get_bind())
    if "applicants" not in inspector.get_table_names():
        return
    cols = {col["name"] for col in inspector.get_columns("applicants")}
    if "tracking_token" not in cols:
        db.execute(text("ALTER TABLE applicants ADD COLUMN tracking_token VARCHAR(80)"))
        db.execute(
            text("CREATE UNIQUE INDEX IF NOT EXISTS ix_applicants_tracking_token ON applicants (tracking_token)")
        )
        db.commit()

    missing_rows = db.scalars(select(Applicant).where(Applicant.tracking_token.is_(None))).all()
    if missing_rows:
        for app_row in missing_rows:
            app_row.tracking_token = secrets.token_urlsafe(24)
        db.commit()


def seed_initial_data(db: Session) -> None:
    """Populate initial RBAC roles, staff accounts, reference data, and requirement checklists."""
    _ensure_user_username_column(db)
    _ensure_applicant_tracking_token_column(db)

    # 1. Permissions & Roles
    perm_map: dict[str, Permission] = {}
    for code, module, desc in DEFAULT_PERMISSIONS:
        perm = db.scalar(select(Permission).where(Permission.code == code))
        if not perm:
            perm = Permission(code=code, module=module, description=desc)
            db.add(perm)
            db.flush()
        perm_map[code] = perm

    role_map: dict[str, Role] = {}
    for role_code, (display_name, desc, perm_codes) in ROLE_DEFINITIONS.items():
        role = db.scalar(select(Role).where(Role.name == role_code))
        if not role:
            role = Role(
                name=role_code,
                display_name=display_name,
                description=desc,
                is_system=True,
                permissions=[perm_map[c] for c in perm_codes if c in perm_map],
            )
            db.add(role)
            db.flush()
        role_map[role_code] = role

    # 2. Default Staff Users (for enterprise onboarding & automated verification)
    default_users = [
        ("superadmin@leaders.edu", "LeadersAdmin!2026", "Superadmin", "", "SUPER_ADMIN"),
        ("admin@leaders.edu", "LeadersAdmin!2026", "Chinedu", "Balogun", "ADMIN"),
        ("officer@leaders.edu", "LeadersOfficer!2026", "Tunde", "Adeyemi", "OFFICER"),
        ("viewer@leaders.edu", "LeadersViewer!2026", "Grace", "Mensah", "VIEWER"),
    ]
    for email, pw, fname, lname, role_name in default_users:
        existing = db.scalar(select(User).where(User.email == email))
        if not existing:
            uname = generate_unique_username(db, fname, lname)
            db.add(
                User(
                    username=uname,
                    email=email,
                    hashed_password=hash_password(pw),
                    first_name=fname,
                    last_name=lname,
                    role_id=role_map[role_name].id,
                    is_active=True,
                )
            )
            db.flush()
        else:
            if email == "superadmin@leaders.edu" and (
                existing.first_name == "Adaeze" or existing.first_name != "Superadmin" or existing.last_name != ""
            ):
                existing.first_name = "Superadmin"
                existing.last_name = ""
                existing.username = "superadmin"
            elif not existing.username:
                existing.username = generate_unique_username(
                    db, existing.first_name, existing.last_name, exclude_user_id=existing.id
                )
    # Backfill usernames on any legacy staff rows
    for staff_user in db.scalars(select(User).where(User.username.is_(None))).all():
        staff_user.username = generate_unique_username(
            db, staff_user.first_name, staff_user.last_name, exclude_user_id=staff_user.id
        )
    db.flush()

    # 3. Destinations
    dest_map: dict[str, Destination] = {}
    for name, code, region in DEFAULT_DESTINATIONS:
        dest = db.scalar(select(Destination).where(Destination.code == code))
        if not dest:
            dest = Destination(name=name, code=code, region=region, is_active=True)
            db.add(dest)
            db.flush()
        dest_map[code] = dest

    # 4. Travel Purposes
    purpose_map: dict[str, TravelPurpose] = {}
    for name, code, desc in DEFAULT_PURPOSES:
        purpose = db.scalar(select(TravelPurpose).where(TravelPurpose.code == code))
        if not purpose:
            purpose = TravelPurpose(name=name, code=code, description=desc, is_active=True)
            db.add(purpose)
            db.flush()
        purpose_map[code] = purpose

    # 5. Application Categories (reusable across all active destination countries)
    categories_seed = [
        ("Student Visa", "STUDENT_VISA", None, "STUDY", "University / College Student Visa Package"),
        ("Postgraduate Study Visa", "POSTGRAD_STUDY_VISA", None, "STUDY", "Postgraduate university study application"),
        ("Study Permit", "STUDY_PERMIT", None, "STUDY", "Canadian / National Study Permit document package"),
        ("Standard Visitor Visa", "STANDARD_VISITOR", None, "TOURISM", "Short-stay tourist visitor application"),
        ("Schengen Tourist / Visitor Visa", "SCHENGEN_VISITOR_VISA", None, "TOURISM", "Schengen short-stay tourist / visitor visa package"),
        ("Business Visitor Visa", "BUSINESS_VISITOR", None, "BUSINESS", "Business conference & corporate visit"),
        ("Skilled Worker Visa", "SKILLED_WORKER", None, "WORK", "Sponsored skilled employment visa"),
        ("Family Visit Visa", "FAMILY_VISIT_VISA", None, "FAMILY_VISIT", "Family visit & dependent travel"),
    ]
    cat_map: dict[str, ApplicationCategory] = {}
    for name, code, dest_code, purp_code, desc in categories_seed:
        cat = db.scalar(select(ApplicationCategory).where(ApplicationCategory.code == code))
        if not cat:
            cat = ApplicationCategory(
                name=name,
                code=code,
                destination_id=dest_map[dest_code].id if dest_code else None,
                purpose_id=purpose_map[purp_code].id if purp_code else None,
                description=desc,
                is_archived=False,
            )
            db.add(cat)
            db.flush()
        else:
            cat.destination_id = dest_map[dest_code].id if dest_code else None
        cat_map[code] = cat

    # 6. Document Types & Aliases
    doc_type_map: dict[str, DocumentType] = {}
    for code, name, cat_name, order, has_exp, min_val, prefix, aliases in DEFAULT_DOCUMENT_TYPES:
        dt = db.scalar(select(DocumentType).where(DocumentType.code == code))
        if not dt:
            dt = DocumentType(
                code=code,
                name=name,
                category=cat_name,
                default_order=order,
                has_expiry=has_exp,
                min_validity_days=min_val,
                naming_prefix=prefix,
                description=f"Canonical document type for {name}",
                is_active=True,
            )
            db.add(dt)
            db.flush()
        else:
            dt.name = name
            dt.category = cat_name
            dt.default_order = order
            dt.has_expiry = has_exp
            dt.min_validity_days = min_val
            dt.naming_prefix = prefix

        existing_aliases = {
            a.alias_name
            for a in db.scalars(
                select(DocumentAlias).where(DocumentAlias.document_type_id == dt.id)
            ).all()
        }
        for alias_name in aliases:
            if alias_name not in existing_aliases:
                db.add(DocumentAlias(document_type_id=dt.id, alias_name=alias_name, is_active=True))
                existing_aliases.add(alias_name)
        doc_type_map[code] = dt
    db.flush()

    # 7. Configurable Requirement Sets (Sample checklists - clearly illustrative administrative configurations)
    super_admin = db.scalar(select(User).where(User.email == "superadmin@leaders.edu"))

    # 7a. United Kingdom + Study + Student Visa (illustrative checklist from specification)
    uk_study_set = db.scalar(
        select(RequirementSet).where(
            RequirementSet.destination_id == dest_map["GB"].id,
            RequirementSet.purpose_id == purpose_map["STUDY"].id,
            RequirementSet.category_id == cat_map["STUDENT_VISA"].id,
        )
    )
    if not uk_study_set:
        uk_study_set = RequirementSet(
            name="United Kingdom - Study (Student Visa)",
            destination_id=dest_map["GB"].id,
            purpose_id=purpose_map["STUDY"].id,
            category_id=cat_map["STUDENT_VISA"].id,
            applicant_type="STANDARD",
            naming_convention="{document_order}_{document_type}.{extension}",
            folder_template="LEADERS_EDU_TOUR_DOCUMENTS/{DESTINATION}/{PURPOSE}/{APPLICANT_NAME}_{APPLICATION_REFERENCE}",
            is_active=True,
        )
        db.add(uk_study_set)
        db.flush()

        v1 = RequirementVersion(
            requirement_set_id=uk_study_set.id,
            version_number=1,
            effective_from=datetime.now(timezone.utc),
            change_notes="Initial configurable checklist for UK Student Visa administrative processing.",
            created_by_id=super_admin.id if super_admin else None,
        )
        db.add(v1)
        db.flush()
        uk_study_set.active_version_id = v1.id

        uk_items = [
            ("INTERNATIONAL_PASSPORT", "REQUIRED", 1, None, None, 180, "Bio-data page must be clear and valid for at least 6 months."),
            ("ADMISSION_LETTER", "REQUIRED", 2, None, None, None, "Official unconditional offer or CAS confirmation from UK institution."),
            ("ACADEMIC_TRANSCRIPT", "REQUIRED", 3, None, None, None, "Complete academic transcripts with institutional stamp/signature."),
            ("ACADEMIC_CERTIFICATES", "REQUIRED", 4, None, None, None, "Degree or secondary graduation certificate."),
            ("BANK_STATEMENT", "REQUIRED", 5, None, None, 28, "Recent bank statement showing maintenance funds."),
            ("BIRTH_CERTIFICATE", "REQUIRED", 6, None, None, None, "Official birth registration certificate."),
            ("STATEMENT_OF_PURPOSE", "REQUIRED", 7, None, None, None, "Personal statement explaining course choice and career objectives."),
            ("ENGLISH_PROFICIENCY", "REQUIRED", 8, None, None, None, "IELTS, TOEFL, PTE, or institutional English waiver."),
            ("PASSPORT_PHOTOGRAPH", "REQUIRED", 9, None, None, None, "Recent colour biometric passport photograph."),
            (
                "SPONSORSHIP_LETTER",
                "CONDITIONAL",
                10,
                {"field": "is_sponsored", "op": "==", "value": True},
                "Required if tuition or living expenses are funded by a parent or third-party sponsor.",
                None,
                "Include sponsor's signed commitment letter alongside financial evidence.",
            ),
            ("MEDICAL_CERTIFICATE", "OPTIONAL", 11, None, None, 180, "TB clearance certificate where applicable to country of residence."),
        ]
        for code, level, order, cond_expr, cond_exp, min_val, instr in uk_items:
            db.add(
                DocumentRequirement(
                    requirement_version_id=v1.id,
                    document_type_id=doc_type_map[code].id,
                    requirement_level=level,
                    display_order=order,
                    condition_expression=cond_expr,
                    condition_explanation=cond_exp,
                    alternative_doc_type_ids=[],
                    allow_multiple_versions=True,
                    min_validity_days=min_val,
                    custom_instructions=instr,
                )
            )

    # 7b. Canada + Study + Study Permit (Full Sections A-E Checklist)
    ca_study_set = db.scalar(
        select(RequirementSet).where(
            RequirementSet.destination_id == dest_map["CA"].id,
            RequirementSet.purpose_id == purpose_map["STUDY"].id,
            RequirementSet.category_id == cat_map["STUDY_PERMIT"].id,
        )
    )
    if not ca_study_set:
        ca_study_set = RequirementSet(
            name="Canada Study Visa – Document Checklist",
            destination_id=dest_map["CA"].id,
            purpose_id=purpose_map["STUDY"].id,
            category_id=cat_map["STUDY_PERMIT"].id,
            applicant_type="STANDARD",
            naming_convention="{document_order}_{document_type}.{extension}",
            folder_template="LEADERS_EDU_TOUR_DOCUMENTS/{DESTINATION}/{PURPOSE}/{APPLICANT_NAME}_{APPLICATION_REFERENCE}",
            is_active=True,
        )
        db.add(ca_study_set)
        db.flush()

    existing_ca_versions = db.scalars(
        select(RequirementVersion)
        .where(RequirementVersion.requirement_set_id == ca_study_set.id)
        .order_by(RequirementVersion.version_number.desc())
    ).all()
    active_ca_ver = next(
        (v for v in existing_ca_versions if v.id == ca_study_set.active_version_id),
        existing_ca_versions[0] if existing_ca_versions else None,
    )
    existing_ca_item_count = (
        len(
            db.scalars(
                select(DocumentRequirement).where(
                    DocumentRequirement.requirement_version_id == active_ca_ver.id
                )
            ).all()
        )
        if active_ca_ver
        else 0
    )

    if existing_ca_item_count < 30:
        next_ver_num = (existing_ca_versions[0].version_number + 1) if existing_ca_versions else 1
        ca_study_set.name = "Canada Study Visa – Document Checklist"
        ca_ver = RequirementVersion(
            requirement_set_id=ca_study_set.id,
            version_number=next_ver_num,
            effective_from=datetime.now(timezone.utc),
            change_notes="Full Canada Study Visa – Document Checklist (Sections A–E: Personal, Employment, Financial, Assets, and Fees).",
            created_by_id=super_admin.id if super_admin else None,
        )
        db.add(ca_ver)
        db.flush()
        ca_study_set.active_version_id = ca_ver.id

        ca_study_items = [
            # Section A: Student's Personal Documents
            ("INTERNATIONAL_PASSPORT", "REQUIRED", 1, None, None, 180, "[Section A · Personal] Valid international passport bio-data page."),
            ("ADMISSION_LETTER", "REQUIRED", 2, None, None, None, "[Section A · Personal] Official Letter of Acceptance (LOA) from Designated Learning Institution."),
            ("BIRTH_CERTIFICATE", "REQUIRED", 3, None, None, None, "[Section A · Personal] Official Birth Certificate / NPC Certificate of Birth."),
            ("CURRICULUM_VITAE", "REQUIRED", 4, None, None, None, "[Section A · Personal] Up-to-date Curriculum Vitae (CV)."),
            ("ACADEMIC_CERTIFICATES", "REQUIRED", 5, None, None, None, "[Section A · Personal] University/College Degree Certificate or Statement of Result."),
            ("ACADEMIC_TRANSCRIPT", "REQUIRED", 6, None, None, None, "[Section A · Personal] Official Degree Academic Transcript."),
            ("WAEC_NECO_CERTIFICATE", "REQUIRED", 7, None, None, None, "[Section A · Personal] WAEC / NECO Senior Secondary School Certificate."),
            ("WAEC_NECO_SCRATCH_CARD", "REQUIRED", 8, None, None, None, "[Section A · Personal] WAEC / NECO Scratch Card / Result Checker PIN."),
            ("ACADEMIC_REFERENCE_LETTER", "REQUIRED", 9, None, None, None, "[Section A · Personal] Signed Academic Reference Letter from lecturer/institution."),
            ("PASSPORT_PHOTOGRAPH", "REQUIRED", 10, None, None, None, "[Section A · Personal] Recent Passport Photograph on a clean white background."),
            ("NIN_SLIP", "REQUIRED", 11, None, None, None, "[Section A · Personal] National Identification Number (NIN) Slip."),
            ("POLICE_CLEARANCE", "REQUIRED", 12, None, None, 90, "[Section A · Personal] Valid Police Clearance / Character Certificate."),
            ("TRAINING_CERTIFICATES", "OPTIONAL", 13, None, None, None, "[Section A · Personal] Training and Professional Certificates (where applicable)."),
            ("STATEMENT_OF_PURPOSE", "REQUIRED", 14, None, None, None, "[Section A · Personal] Statement of Purpose (SOP) — to be written/reviewed by Leaders Edu Tour Ltd."),
            ("PARENTS_CONSENT_LETTER", "CONDITIONAL", 15, {"field": "requires_parent_consent", "op": "==", "value": True}, "Required where applicant is a minor or supported by parental consent.", None, "[Section A · Personal] Signed Parents' Consent Letter (where applicable)."),
            # Section B: Student's Employment Documents
            ("EMPLOYMENT_LETTER", "CONDITIONAL", 16, {"field": "is_employed", "op": "==", "value": True}, "Required if applicant is currently or previously employed.", None, "[Section B · Employment] Official Employment Letter stating role and start date."),
            ("PROMOTION_LETTER", "OPTIONAL", 17, None, None, None, "[Section B · Employment] Promotion Letter(s) (where applicable)."),
            ("EMPLOYER_INTRODUCTION_LETTER", "CONDITIONAL", 18, {"field": "is_employed", "op": "==", "value": True}, "Required when employed to confirm official status with employer.", None, "[Section B · Employment] Letter of Introduction from Employer."),
            ("STUDY_LEAVE_LETTER", "CONDITIONAL", 19, {"field": "is_employed", "op": "==", "value": True}, "Required if taking study leave or exemption from employment/NYSC.", None, "[Section B · Employment] Study Leave / Letter of Exemption to Study (where applicable)."),
            ("WORK_ID_CARD", "CONDITIONAL", 20, {"field": "is_employed", "op": "==", "value": True}, "Required for currently employed applicants.", None, "[Section B · Employment] Valid Staff / Work ID Card."),
            ("PAYSLIPS", "CONDITIONAL", 21, {"field": "is_employed", "op": "==", "value": True}, "Required for salaried/employed applicants.", None, "[Section B · Employment] Six (6) Months' Payslips."),
            # Section C: Financial Documents (Sponsor and Yours)
            ("BANK_STATEMENT", "REQUIRED", 22, None, None, 28, "[Section C · Financial] Six (6) Months' Personal Bank Statement + Reference Certificate."),
            ("SPONSORSHIP_LETTER", "CONDITIONAL", 23, {"field": "is_sponsored", "op": "==", "value": True}, "Required if tuition or living expenses are funded by a sponsor.", None, "[Section C · Financial] Sponsor Commitment Letter / Affidavit of Support & sponsor bank statement."),
            ("BUSINESS_REGISTRATION", "CONDITIONAL", 24, {"field": "is_self_employed", "op": "==", "value": True}, "Required if applicant or sponsor is self-employed / business owner.", None, "[Section C · Financial] Business Registration Documents / CAC Certificate (if self-employed)."),
            ("BUSINESS_BANK_STATEMENT", "CONDITIONAL", 25, {"field": "is_self_employed", "op": "==", "value": True}, "Required if self-employed or funding through a company account.", 28, "[Section C · Financial] Six (6) Months' Business Bank Statement (if applicable)."),
            ("TAX_CLEARANCE_CERTIFICATE", "CONDITIONAL", 26, {"field": "is_self_employed", "op": "==", "value": True}, "Required where business or personal tax filings apply.", 90, "[Section C · Financial] Tax Clearance Certificate (where applicable)."),
            # Section D: Asset Documents (where applicable)
            ("LAND_DOCUMENTS", "OPTIONAL", 27, None, None, None, "[Section D · Assets] Land Documents (where applicable)."),
            ("CERTIFICATE_OF_OCCUPANCY", "OPTIONAL", 28, None, None, None, "[Section D · Assets] Certificate of Occupancy (C of O) (where applicable)."),
            ("SURVEY_PLAN", "OPTIONAL", 29, None, None, None, "[Section D · Assets] Registered Survey Plan (where applicable)."),
            ("DEED_OF_ASSIGNMENT", "OPTIONAL", 30, None, None, None, "[Section D · Assets] Deed of Assignment (where applicable)."),
            ("PROPERTY_VALUATION_REPORT", "OPTIONAL", 31, None, None, None, "[Section D · Assets] Property Valuation Report (where applicable)."),
            ("OTHER_ASSET_DOCUMENTS", "OPTIONAL", 32, None, None, None, "[Section D · Assets] Other Investment or Asset Documents (where applicable)."),
            # Section E: Visa & Professional Fees
            ("NOTARY_FEE_RECEIPT", "REQUIRED", 33, None, None, None, "[Section E · Visa & Professional Fees] Lawyer's Notary Fee – N100,000 payment confirmation."),
        ]

        for code, level, order, cond_expr, cond_exp, min_val, instr in ca_study_items:
            db.add(
                DocumentRequirement(
                    requirement_version_id=ca_ver.id,
                    document_type_id=doc_type_map[code].id,
                    requirement_level=level,
                    display_order=order,
                    condition_expression=cond_expr,
                    condition_explanation=cond_exp,
                    alternative_doc_type_ids=[],
                    allow_multiple_versions=True,
                    min_validity_days=min_val,
                    custom_instructions=instr,
                )
            )

    # 7c. UK Tourism Standard Visitor
    uk_tour_set = db.scalar(
        select(RequirementSet).where(
            RequirementSet.destination_id == dest_map["GB"].id,
            RequirementSet.purpose_id == purpose_map["TOURISM"].id,
            RequirementSet.category_id == cat_map["STANDARD_VISITOR"].id,
        )
    )
    if not uk_tour_set:
        uk_tour_set = RequirementSet(
            name="United Kingdom - Tourism (Standard Visitor)",
            destination_id=dest_map["GB"].id,
            purpose_id=purpose_map["TOURISM"].id,
            category_id=cat_map["STANDARD_VISITOR"].id,
            applicant_type="STANDARD",
            naming_convention="{document_order}_{document_type}.{extension}",
            folder_template="LEADERS_EDU_TOUR_DOCUMENTS/{DESTINATION}/{PURPOSE}/{APPLICANT_NAME}_{APPLICATION_REFERENCE}",
            is_active=True,
        )
        db.add(uk_tour_set)
        db.flush()
        v1 = RequirementVersion(
            requirement_set_id=uk_tour_set.id,
            version_number=1,
            change_notes="Initial configurable checklist for UK Standard Visitor.",
            created_by_id=super_admin.id if super_admin else None,
        )
        db.add(v1)
        db.flush()
        uk_tour_set.active_version_id = v1.id
        for idx, (code, level) in enumerate(
            [
                ("INTERNATIONAL_PASSPORT", "REQUIRED"),
                ("BANK_STATEMENT", "REQUIRED"),
                ("EMPLOYMENT_LETTER", "REQUIRED"),
                ("TRAVEL_ITINERARY", "REQUIRED"),
                ("HOTEL_BOOKING", "REQUIRED"),
            ],
            start=1,
        ):
            db.add(
                DocumentRequirement(
                    requirement_version_id=v1.id,
                    document_type_id=doc_type_map[code].id,
                    requirement_level=level,
                    display_order=idx,
                    allow_multiple_versions=True,
                )
            )

    # 7d. Baseline Study & Visitor Checklists Across Active Countries (US, MT, FR, DE, IE, NL, ES, CA Tourism)
    default_study_items = [
        ("INTERNATIONAL_PASSPORT", "REQUIRED"),
        ("ADMISSION_LETTER", "REQUIRED"),
        ("ACADEMIC_TRANSCRIPT", "REQUIRED"),
        ("ACADEMIC_CERTIFICATES", "REQUIRED"),
        ("BANK_STATEMENT", "REQUIRED"),
        ("BIRTH_CERTIFICATE", "REQUIRED"),
        ("STATEMENT_OF_PURPOSE", "REQUIRED"),
        ("ENGLISH_PROFICIENCY", "OPTIONAL"),
        ("PASSPORT_PHOTOGRAPH", "REQUIRED"),
        ("POLICE_CLEARANCE", "OPTIONAL"),
    ]
    default_visitor_items = [
        ("INTERNATIONAL_PASSPORT", "REQUIRED"),
        ("BANK_STATEMENT", "REQUIRED"),
        ("EMPLOYMENT_LETTER", "REQUIRED"),
        ("TRAVEL_ITINERARY", "REQUIRED"),
        ("HOTEL_BOOKING", "REQUIRED"),
        ("PASSPORT_PHOTOGRAPH", "REQUIRED"),
    ]

    baseline_sets = [
        ("United States - Study (Student Visa F-1)", "US", "STUDY", "STUDENT_VISA", default_study_items),
        ("United States - Tourism (Standard Visitor B1/B2)", "US", "TOURISM", "STANDARD_VISITOR", default_visitor_items),
        ("Canada - Tourism (Standard Visitor Visa)", "CA", "TOURISM", "STANDARD_VISITOR", default_visitor_items),
        ("Malta - Study (Student Visa)", "MT", "STUDY", "STUDENT_VISA", default_study_items),
        ("Malta - Tourism (Schengen Visitor Visa)", "MT", "TOURISM", "SCHENGEN_VISITOR_VISA", default_visitor_items),
        ("France - Study (Student Visa)", "FR", "STUDY", "STUDENT_VISA", default_study_items),
        ("France - Tourism (Schengen Visitor Visa)", "FR", "TOURISM", "SCHENGEN_VISITOR_VISA", default_visitor_items),
        ("Germany - Study (Student Visa)", "DE", "STUDY", "STUDENT_VISA", default_study_items),
        ("Germany - Tourism (Schengen Visitor Visa)", "DE", "TOURISM", "SCHENGEN_VISITOR_VISA", default_visitor_items),
        ("Ireland - Study (Student Visa)", "IE", "STUDY", "STUDENT_VISA", default_study_items),
        ("Ireland - Tourism (Standard Visitor Visa)", "IE", "TOURISM", "STANDARD_VISITOR", default_visitor_items),
        ("Netherlands - Study (Student Visa)", "NL", "STUDY", "STUDENT_VISA", default_study_items),
        ("Netherlands - Tourism (Schengen Visitor Visa)", "NL", "TOURISM", "SCHENGEN_VISITOR_VISA", default_visitor_items),
        ("Spain - Study (Student Visa)", "ES", "STUDY", "STUDENT_VISA", default_study_items),
        ("Spain - Tourism (Schengen Visitor Visa)", "ES", "TOURISM", "SCHENGEN_VISITOR_VISA", default_visitor_items),
    ]

    for set_title, d_code, p_code, c_code, base_items in baseline_sets:
        existing_set = db.scalar(
            select(RequirementSet).where(
                RequirementSet.destination_id == dest_map[d_code].id,
                RequirementSet.purpose_id == purpose_map[p_code].id,
                RequirementSet.category_id == cat_map[c_code].id,
            )
        )
        if existing_set:
            continue
        req_set = RequirementSet(
            name=set_title,
            destination_id=dest_map[d_code].id,
            purpose_id=purpose_map[p_code].id,
            category_id=cat_map[c_code].id,
            applicant_type="STANDARD",
            naming_convention="{document_order}_{document_type}.{extension}",
            folder_template="LEADERS_EDU_TOUR_DOCUMENTS/{DESTINATION}/{PURPOSE}/{APPLICANT_NAME}_{APPLICATION_REFERENCE}",
            is_active=True,
        )
        db.add(req_set)
        db.flush()
        ver = RequirementVersion(
            requirement_set_id=req_set.id,
            version_number=1,
            effective_from=datetime.now(timezone.utc),
            change_notes=f"Initial configurable baseline checklist for {set_title}.",
            created_by_id=super_admin.id if super_admin else None,
        )
        db.add(ver)
        db.flush()
        req_set.active_version_id = ver.id
        for order_idx, (doc_code, req_level) in enumerate(base_items, start=1):
            db.add(
                DocumentRequirement(
                    requirement_version_id=ver.id,
                    document_type_id=doc_type_map[doc_code].id,
                    requirement_level=req_level,
                    display_order=order_idx,
                    allow_multiple_versions=True,
                )
            )

    # 8. Default System Settings
    default_settings = [
        ("ai.provider", {"provider": "LOCAL_DETERMINISTIC", "allow_external_ai": False, "redact_pii": True}, "AI", "Active AI document classification provider and external privacy guard"),
        ("ocr.provider", {"provider": "TESSERACT"}, "OCR", "Active OCR engine for scanned PDFs and images"),
        ("naming.default_convention", {"template": "{document_order}_{document_type}.{extension}", "alternative": "{applicant_name}_{document_type}_{date}.{extension}"}, "NAMING", "Default automatic filename generation convention"),
        ("storage.folder_template", {"template": "LEADERS_EDU_TOUR_DOCUMENTS/{DESTINATION}/{PURPOSE}/{APPLICANT_NAME}_{APPLICATION_REFERENCE}"}, "STORAGE", "Default organized applicant folder hierarchy"),
        ("security.upload_limits", {"max_file_mb": 25, "max_batch_files": 50, "retention_days": 365}, "SECURITY", "Upload limits and NDPA/GDPR data retention policy"),
    ]
    for key, val, cat, desc in default_settings:
        if not db.scalar(select(SystemSetting).where(SystemSetting.key == key)):
            db.add(SystemSetting(key=key, value_json=val, category=cat, description=desc))

    db.commit()
