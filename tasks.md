context:
  product_goal: "Dental franchise case-sharing site (1 HQ + 3 branches) for treatment plan collaboration."
  tenants: ["HQ", "Branch A", "Branch B", "Branch C"]
  roles: ["HQ_ADMIN","BRANCH_ADMIN","DENTIST","ASSISTANT","FRONT_DESK","READ_ONLY","EXTERNAL_GUEST"]
  compliance: ["PHI minimal exposure", "audit logs", "encrypted at rest/in transit"]
  stack:
    backend: "Django 5 + DRF"
    db: "Postgres"
    cache_tasks: "Redis + Celery"
    storage: "S3-compatible (presigned uploads)"
    deploy: "Docker/Compose (dev), Nginx, CI/CD"
  conventions:
    repo_layout:
      - backend/  # Django project
      - infra/    # docker, nginx, terraform (later)
      - docs/
      - ops/
    coding:
      style: "black + isort + flake8"
      commits: "conventional commits"
    testing:
      framework: "pytest + pytest-django + factory_boy"
      coverage_min: 80

epics:
  - id: E0
    title: "Bootstrap & Governance"
    tasks:
      - id: T0.1
        title: "Initialize repo & Django project"
        instructions: >
          Create Django project `core` and app `accounts`, configure Postgres/Redis,
          add settings split (base/dev/prod), install DRF, Celery, storages.
        inputs: []
        outputs:
          - repo with backend project
          - requirements files (prod/dev)
          - settings modules with env variables
        acceptance:
          - "manage.py check passes"
          - "pytest runs (even if empty)"
          - "docker-compose up works for dev"
      - id: T0.2
        title: "CI pipeline"
        instructions: "GitHub Actions: lint, test, build; cache deps; collect coverage."
        inputs: []
        outputs: [".github/workflows/ci.yml"]
        acceptance: ["CI green on push/PR", "coverage report artifact"]
      - id: T0.3
        title: "Base security headers & TLS assumptions"
        instructions: "Add Django SecurityMiddleware, SECURE_* flags; document TLS termination at Nginx."
        outputs: ["docs/security.md"]
        acceptance: ["SecurityMiddleware enabled", "HSTS in prod settings"]

  - id: E1
    title: "Organizations & RBAC"
    tasks:
      - id: T1.1
        title: "Models: Organization & User profile"
        instructions: >
          Create Organization {id, name, type: HQ|BRANCH, address?}.
          Extend user via OneToOne Profile {role, org_id, professional_type}.
        outputs: ["models.py", "migrations"]
        acceptance: ["makemigrations/migrate succeed", "admin list display org/role"]
      - id: T1.2
        title: "RBAC scaffolding"
        instructions: >
          Implement Groups/Permissions for roles. Add a `ScopeQuerySet` mixin that
          restricts default queryset to user.org unless HQ role.
        outputs: ["accounts/permissions.py", "common/queryset.py"]
        acceptance: ["Unit tests for HQ vs Branch visibility"]
        depends_on: ["T1.1"]
      - id: T1.3
        title: "Auth"
        instructions: "Email/username login with django-allauth or django built-ins;"
        outputs: ["login pages/api""]
       
  - id: E2
    title: "Patients & Cases"
    tasks:
      - id: T2.1
        title: "Models: Patient, Case, Tags"
        instructions: >
          Patient {mrn, name, dob, contact, consent_flags(JSON), org_owner}.
          Case {patient, created_by, owning_org, status, diagnosis, chief_complaint, tags M2M}.
          Tag {name, slug, scope: global|org}.
        outputs: ["models.py", "admin registrations"]
        acceptance: ["CRUD in admin", "unique constraints validated"]
        depends_on: ["T1.1"]
      - id: T2.2
        title: "API: Patient & Case CRUD + search"
        instructions: >
          DRF viewsets with pagination, filtering (patient name/MRN, status, tag, branch),
          scoped by org via `ScopeQuerySet`. Include serializers with minimal PHI.
        outputs: ["serializers.py", "views.py", "urls.py"]
        acceptance:
          - "HQ sees all; Branch sees own"
          - "Search by name/MRN works"
          - "Permissions unit tests"
        depends_on: ["T2.1","T1.2"]

  - id: E3
    title: "Treatment Plans (versioned)"
    tasks:
      - id: T3.1
        title: "Models: TreatmentPlan + Versioning"
        instructions: >
          TreatmentPlan {case, author, version, content(JSON), status:draft|approved|archived,
          approved_by?, approved_at?}. Version auto-increments per case.
        outputs: ["models.py", "signals for version increment"]
        acceptance: ["Version increments on create", "approved_* set on approve"]
        depends_on: ["T2.1"]
      - id: T3.2
        title: "API: Create/Edit/Compare/Approve plan"
        instructions: >
          Endpoints: create draft, update draft, compare(v1,v2) returns diff,
          approve(lock). PDF export endpoint.
        outputs: ["views.py", "serializers.py", "pdf export util"]
        acceptance:
          - "Dentist can create/edit draft"
          - "Approve locks edits (except HQ/Branch admin override)"
          - "PDF downloads with metadata footer"
        depends_on: ["T3.1","T1.2"]

  - id: E4
    title: "Files, Imaging & De-identification"
    tasks:
      - id: T4.1
        title: "Model: CaseFile"
        instructions: >
          CaseFile {case, uploaded_by, file, file_type: photo|xray|cbct|pdf,
          meta(JSON), is_deidentified:bool, derivatives(JSON)}.
        outputs: ["models.py"]
        acceptance: ["upload in admin works"]
        depends_on: ["T2.1"]
      - id: T4.2
        title: "Presigned S3 uploads + validation"
        instructions: >
          Backend endpoint to create presigned PUT URLs; limit mime/size; virus scan hook (stub).
        outputs: ["views.py", "storages config", "settings for S3"]
        acceptance: ["Client can PUT to S3 and register CaseFile record"]
        depends_on: ["T4.1"]
      - id: T4.3
        title: "Thumbnails/derivatives via Celery"
        instructions: >
          Celery task generates thumbnails (jpg/png) and stores in S3, updates CaseFile.derivatives.
        outputs: ["tasks.py", "image utils"]
        acceptance: ["Task idempotent; retries on failure; unit tests"]
        depends_on: ["T4.2"]
      - id: T4.4
        title: "Simple image viewer & annotations (server-side)"
        instructions: >
          API for basic annotations (arrows/notes). Store overlay JSON linked to CaseFile.
        outputs: ["annotation models/api"]
        acceptance: ["Create/read/update/delete annotations with audit trail"]
        depends_on: ["T4.1"]

  - id: E5
    title: "Case Sharing & Collaboration"
    tasks:
      - id: T5.1
        title: "SharePolicy & cross-branch feed"
        instructions: >
          SharePolicy {case, scope: branch|cross_branch|deidentified}.
          Cross-branch list obeys policy and de-identification flag.
        outputs: ["models.py","filters"]
        acceptance: ["Non-owning branches see only allowed data; PHI stripped when required"]
        depends_on: ["T2.1","T4.1"]
      - id: T5.2
        title: "@mentions, comments, timeline"
        instructions: >
          Comment {case, author, body, visibility: private|team|org}.
          Timeline aggregates plan versions, files, comments, approvals.
        outputs: ["models/api", "timeline endpoint"]
        acceptance: ["Email/in-app notification on mention", "visibility enforced"]
        depends_on: ["T2.1"]

  - id: E6
    title: "Notifications"
    tasks:
      - id: T6.1
        title: "Email adapter + templates"
        instructions: "Use Django email backend; env-configurable; templated messages."
        outputs: ["notifications/email.py", "templates/emails/*"]
        acceptance: ["Local dev: console backend; prod-ready settings"]
      - id: T6.2
        title: "Event-based notifications"
        instructions: >
          Signals: on mention, assignment, plan approval.
          Queue via Celery; dedupe by event key within 60s.
        outputs: ["notifications/events.py", "celery tasks"]
        acceptance: ["Unit tests verify one notification per event burst"]
        depends_on: ["T5.2","T3.2"]

  - id: E7
    title: "Admin & HQ Dashboards"
    tasks:
      - id: T7.1
        title: "User management & bulk invite"
        instructions: "Admin endpoints for CRUD users, reset MFA, force password reset; CSV invite."
        outputs: ["admin views", "management commands"]
        acceptance: ["HQ can manage all; Branch admin limited to own org"]
        depends_on: ["T1.1","T1.3"]
      - id: T7.2
        title: "Metrics APIs"
        instructions: >
          Endpoints for: cases per branch, approval time, files volume.
          Use annotated queries; return for charting.
        outputs: ["reports api"]
        acceptance: ["Aggregation unit tests; HQ-only permission"]
        depends_on: ["T2.2","T3.2"]

  - id: E8
    title: "Audit & Compliance"
    tasks:
      - id: T8.1
        title: "AuditEvent model + middleware"
        instructions: >
          AuditEvent {actor, verb, object_type, object_id, org_context, ip, ts, extra}.
          Record on read/write of PHI, downloads, permission changes.
        outputs: ["middleware/audit.py", "signals"]
        acceptance: ["Events written; sampling for reads configurable"]
      - id: T8.2
        title: "Exportable audit report"
        instructions: "HQ endpoint to export CSV by date range and event types."
        outputs: ["reports/audit_export.py"]
        acceptance: ["CSV matches filters; pagination for large exports"]
        depends_on: ["T8.1"]

  - id: E9
    title: "Non-Functional: Perf, Obs, Backups"
    tasks:
      - id: T9.1
        title: "Caching & select_related/prefetch"
        instructions: "Add queryset optimization helpers; cache heavy aggregations."
        outputs: ["common/dbutils.py"]
        acceptance: ["Queries under N targets in tests"]
      - id: T9.2
        title: "Logging & error tracking"
        instructions: "Structlog or Python logging JSON; integrate Sentry; mask PHI."
        outputs: ["settings logging config", "docs/logging.md"]
        acceptance: ["Sensitive fields redacted in test logs"]
      - id: T9.3
        title: "Backup/restore playbook"
        instructions: "pg_dump/restore scripts, S3 lifecycle rules; test restore in dev."
        outputs: ["ops/backup.sh", "ops/restore.sh", "docs/dr.md"]
        acceptance: ["Restore test passes with sample data"]

  - id: E10
    title: "Release Hardening"
    tasks:
      - id: T10.1
        title: "Permission fuzz tests"
        instructions: "Property-based tests to attempt cross-branch access and escalation."
        outputs: ["tests/security/test_rbac_fuzz.py"]
        acceptance: ["All attempts blocked; coverage > 80%"]
        depends_on: ["T1.2","T2.2","T3.2","T5.1"]
      - id: T10.2
        title: "UAT seed data & guides"
        instructions: "Management command to seed HQ+3 branches, sample patients/cases/files."
        outputs: ["manage.py seed_demo"]
        acceptance: ["Demo can be spun up with one command"]
