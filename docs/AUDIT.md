# Repository Audit

This audit summarizes the implementation after Phases A-D. Statuses describe
observable code, not roadmap intent; the Phase 0 section below preserves the
original findings for historical context.

| Area | Status | Evidence and gap |
|---|---|---|
| RBAC | Partial | A central role-permission matrix and object checks scope complainants to their own cases and officials to their bureau. An official who can access a case can review its related-case summary; officials from either involved bureau can decide the link. Unrelated users cannot. Admins retain global access. Denial tests cover complaint reads/actions, files, notifications, reports, analytics, and admin routes, but not every route/role pair. |
| Audit log | Partial | Database triggers block updates and deletes in SQLite and PostgreSQL. Entries are SHA-256 hash-chained and admins can verify the chain from the API/UI. Existing rows are chained on the first startup that adds the hash columns. The implementation is not an external/WORM audit store, and SQLite multi-process chain writes are not coordinated by a database-wide lock. |
| SLA escalation | Partial | An in-process APScheduler job marks overdue cases through the case state machine, writes a timeline event and chained audit entry, and notifies admins. It is not persistent/distributed. |
| AI correlation | Done | Suggestions combine configurable TF-IDF and sentence-embedding cosine scores. Multilingual model selection is supported; model/version-keyed embeddings are cached. If the configured model cannot load or inference fails, the affected score falls back to TF-IDF and a warning is logged. |
| Notifications | Partial | In-app notifications and SMTP email are implemented. Email failures are logged and swallowed, and delivery is not queued or retried. |
| Human validation | Partial | Officials can confirm or reject suggestions, with decision records, timeline events, notifications, and explicit case groups for confirmed links. There is no decision-based threshold calibration. |
| Routing rules | Partial | Rule-based bureau selection, a default bureau, least-loaded assignment, and admin rule creation/deletion exist. There is no rule-update endpoint or model-based triage. |
| Information-request flow | Done | Officials can request information; only the case owner can respond. State changes, timeline events, audit entries, and notifications are recorded. |
| Determination, closure, and feedback | Done | Accepted/rejected determinations are required to close a case. Closure metadata, read-only checks, notifications, and post-closure feedback are implemented. |
| Health and metrics | Partial | `/health` checks the database, and `/metrics` returns aggregate values as JSON. There is no separate `/ready` endpoint or Prometheus text exposition. |
| Case state machine | Done | A transition policy rejects illegal transitions with HTTP 409, requires Accepted/Rejected before closure, and records each transition in the timeline and audit chain. Tests cover allowed/forbidden transitions and the information-request and closure workflows. |
| Layered architecture | Partial | Routers delegate database operations and workflows to services/repositories, including authentication, analytics, notifications, reports, intake, case workflow, and admin configuration. Some services still query SQLAlchemy directly, so the repository boundary is not universal. |
| Database migrations | Done | Alembic has a generated baseline for current metadata, and the backend upgrades before seeding. The initial migration also creates newly modelled tables on databases previously bootstrapped with `create_all`; no tables or data are dropped. |
| Hybrid similarity and explainability | Done | Related-case links store a weighted hybrid score, configurable bucket, shared keywords, and shared metadata. Officials who can access the source case see the related-case summary and reasons; officials from either linked bureau can decide the suggestion. Admins can update bucket thresholds through the API and UI, with audit entries. |
| Evaluation quality | Partial | `ml/dataset.csv` contains 84 synthetic labelled pairs, including Hindi, Hindi-English, and Hinglish. The multilingual model loaded and `ml/evaluate.py` measured TF-IDF, sentence-embedding, and hybrid precision/recall/F1 and confusion matrices. The in-sample hybrid result is F1 0.9143 with 0.65 TF-IDF / 0.35 embedding weights; this small synthetic set is not independent or production validation. |
| Security hardening | Partial | Access tokens are short-lived PyJWT tokens; refresh tokens rotate and are revoked server-side through an httpOnly SameSite cookie. Upload validation and case-scoped downloads, the role matrix/object checks, production secret guard, security headers, CORS configuration, and hash-chain verification are implemented. Login lockout and per-IP rate limiting use Redis; development falls back to process-local memory, while production returns 503 when shared state is unavailable. Route/role coverage is not exhaustive. |
| Scalability | Partial | Dashboard aggregates use a configurable 1-60 second Redis TTL cache, with a process-local fallback in development. A 100-user, 5,000-case, two-worker Locust run is recorded in `docs/PERFORMANCE.md`; Redis was unavailable for that run, and seven connection-aborted requests were observed. It is a localhost SQLite smoke test, not production capacity evidence. Other lists remain offset-paginated or unbounded, and correlation/SLA work remains in-process. |
| UI and accessibility | Partial | Shared loading/empty/error primitives, role-aware navigation, accessible notification controls, and a reusable case timeline are implemented. Five real screenshots from the running app are checked in under `docs/screenshots/`. The Playwright E2E covers the requested complaint-to-closure path, but keyboard/screen-reader behavior and all role workflows are not covered. |
| CI and end-to-end coverage | Partial | GitHub Actions runs pytest, pip-audit, frontend lint/build, npm audit, and a Playwright Chromium workflow for complaint filing, routing, cross-bureau matching, notification, and closure. The E2E passed locally; the GitHub-hosted workflow has not been run in this session. There is no coverage threshold. |

## Phase 0 findings

- The repository had no root `.gitignore`; tracked SQLite database files and
  generated Python bytecode were present.
- The worktree already had modifications to `drishti.db-wal` and
  `test_drishti.db` before this audit. They were not altered or restored.
- No evidence of real credentials was found in the inspected source or recent
  history. Development signing keys and database credentials are hard-coded
  examples and must not be used in a deployed environment.
- The README's former demo credentials did not match the seed data. The seed
  accounts use `@drishti.test` addresses and a shared prototype password.
- The login flow worked in the browser. The admin dashboard's analytics request
  returned HTTP 500 because SQLite returned a naive `sla_due_at` datetime that
  was compared to an aware UTC datetime.
- Backend tests passed (13 tests). Frontend lint and production build completed
  with warnings. See the accompanying Phase 0 report for the exact commands.

## Phase A implementation notes

- Phase A security changes are implemented and covered by focused tests.
- Audit hash-chain changes are compatible with existing databases through a
  startup backfill when the chain columns are first added; this startup schema
  adjustment is not a replacement for the pending Alembic migration work.
- Login attempt and lockout state was originally process-local; it now uses
  Redis with a development-only in-memory fallback.

## Phase B implementation notes

- Complaint lifecycle transitions now pass through a service-level state
  machine. Invalid moves return HTTP 409; accepted/rejected determinations are
  required before closure, and closed cases cannot be reassigned or annotated.
- Information requests, responses, determinations, reassignment, SLA overdue
  escalation, and confirmed case-link decisions record timeline/audit data
  through services. Confirmed link components are merged into case groups.
- Complaint list/detail reads use repositories with eager loading for case
  relationships; admin bureau workload counts use aggregate subqueries rather
  than per-bureau count queries.
- Docker and local startup instructions apply Alembic migrations before seeding.
- Phase B did not include durable/distributed scheduling, a full repository
  conversion for auth/analytics/notifications/reports, hybrid similarity, or
  performance testing. Hybrid similarity was implemented in Phase C; the
  remaining architecture and performance gaps are tracked above and in Phase D.

## Phase C implementation notes

- The correlation engine now combines lexical TF-IDF and sentence-embedding
  cosine similarity using environment-configurable weights. Hindi-capable
  multilingual embeddings are selected by default; `SIMILARITY_MULTILINGUAL_ENABLED`
  can select the English model instead. Embedding cache keys include the model
  name and an operator-controlled cache version.
- The engine logs a warning and uses TF-IDF when the model cannot load or an
  embedding cannot be computed. It does not write fabricated embedding scores.
- Admins can configure the High/Medium/Low boundaries. Stored case-link
  explanations include shared keywords and exact shared metadata, which the
  API only returns when the current user can view both cases.
- The evaluation script validates the labelled CSV and reports real TF-IDF,
  sentence-embedding, and hybrid metrics/confusion matrices. The multilingual
  model was loaded for the measured report; results remain exploratory and
  in-sample.
- At Phase C completion, load testing, dashboard caching, screenshot capture,
  and the remaining UI/CI work were outstanding; Phase D progress and limits
  are recorded below.

## Phase D implementation notes

- Analytics responses are cached for `DASHBOARD_CACHE_TTL_SECONDS` (default
  10; permitted range 1-60). Keys include the caller identity and query filters,
  and Redis stores the TTL entries across workers. Without Redis in
  development, the cache falls back to process-local memory; production
  requests fail explicitly if Redis is unavailable.
- `scripts/performance/seed_5000.py` refuses non-SQLite databases and requires
  an explicitly opted-in database filename containing `perf`. The Locust run
  exercises the dashboard and 50-row complaint list with two workers; measured
  results, observed failures, and the lack of Redis during the run are in
  `docs/PERFORMANCE.md`.
- The React UI now has reusable page-state/status components, role-specific
  mobile and desktop navigation, notification loading/error states, and a
  dedicated case timeline component. Five screenshots were captured from the
  running app using synthetic demo data. The Playwright E2E covers the requested
  complaint, routing, match explanation, notification, and closure workflow.
- The CI workflow is configured but has not been executed by GitHub Actions in
  this local session. Local backend tests, frontend lint/build, dependency
  audit, and Playwright E2E passed; oxlint reports existing warnings in
  unrelated frontend code.
