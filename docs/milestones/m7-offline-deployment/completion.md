# Milestone 7 Completion Evidence - Offline Deployment and Shop Pilot

**Implementation status:** Complete on 2026-08-07  
**Milestone acceptance:** Pending required shop-host verification and supervised pilot  
**Planning:** `docs/milestones/m7-offline-deployment/feature-spec.md`, `docs/milestones/m7-offline-deployment/technical-design.md`, `docs/milestones/m7-offline-deployment/development-tasks.md`

## Implemented

- Linux multi-stage Docker image with exact Python/Node family images, locally compiled Tailwind,
  collected WhiteNoise assets, non-root runtime, and exact Gunicorn 26.0.0.
- Docker Tailwind stage includes every configured template/app/JavaScript scan source before CSS
  compilation, preventing production images from losing utility classes.
- Dockerfile avoids an unnecessary external syntax-frontend lookup, allowing repeat release builds
  to use the locally cached pinned base images while the internet is disconnected.
- Versioned Compose web image, healthy-PostgreSQL dependency, application/database health checks,
  loopback-only default bindings, persistent database/log boundaries, and restart policies.
- Public safe health response with database readiness and selected application version.
- Checked offline release package containing image tar, SHA-256 manifest, Compose runtime,
  PostgreSQL initialization, deployment scripts, and operator/shop runbooks.
- Initial install, start, stop, status, update, backup, scheduled-task, restore, and rollback scripts.
- Verified PostgreSQL custom-format backups with atomic copy, seven-day safe retention, optional
  external copy, and operational logging.
- Explicit destructive recovery confirmation, prior-image/pre-update-dump rollback, and no normal
  volume deletion path.
- Future private-LAN instructions that expose only the app port, not PostgreSQL.
- Required real-host/shop pilot checklist covering every milestone exit criterion.

## Automated evidence

All results were run from the Windows development host against PostgreSQL 16.14 in Docker.

- `python manage.py test --noinput`: **347 tests passed** in 397.245 seconds.
- `node --test static/js/*.test.js`: **14 tests passed**.
- `ruff check .`: passed.
- `ruff format --check .`: **176 files formatted**.
- `python manage.py makemigrations --check --dry-run`: no changes detected.
- `python manage.py check`: no issues.
- `python -m pip check`: no broken requirements.
- `npm run css:build`: Tailwind 4.3.3 build passed.
- PowerShell parser: every `deploy/*.ps1` and `deploy/*.psm1` file parsed without errors.
- `docker compose config --quiet`: passed.
- Production image: built successfully with Python 3.13.14, Gunicorn 26.0.0, local static assets,
  and user `pos`.
- Production runtime: Gunicorn booted two gthread workers and `/health/` returned
  `{"status":"ok","version":"m7-test"}` while connected to the Docker PostgreSQL service.
- Packaged-CSS regression: the corrected image contained the complete 47,212-byte stylesheet and
  required login utilities including `max-w-md`, `rounded-2xl`, and the responsive `sm:py-14` rule.
- Real backup: `Backup-Database.ps1` produced and validated a non-empty PostgreSQL custom-format
  dump under ignored `var/backups`; no live database reset occurred.
- Release smoke package: image tar, schema-1 manifest, matching SHA-256, runtime bundle, and zip were
  created and re-read successfully. Test artifacts remain ignored under `releases/`.

The first full test attempt was interrupted by its time limit and left only the disposable
`test_pos_codex` database. That exact test database was removed; the live `pos_codex` database and
volume were not reset. The complete rerun then passed and removed its test database normally.

## Post-completion Compose identity correction

A test update using a non-default Compose project revealed that copying runtime `compose.yaml`
could replace a locally customized top-level name and make Docker attempt to start another database
project on the same port. No migration or database replacement occurred. Public-release preparation
corrects this by resolving the project name from persistent `COMPOSE_PROJECT_NAME`, documenting the
invariant, and testing the release contract. Existing default-name installations remain compatible;
non-default installations retain their project name in `.env`.

Correction verification on 2026-08-14: alternate/default Compose configuration parsing passed,
all 5 focused deployment contract tests passed, all 348 Django tests passed in 381.914 seconds, and
the JavaScript, Ruff, migration-drift, dependency, Tailwind, static-collection, and diff checks
passed.

## Required manual release checks

These checks cannot be truthfully completed by automated tests and must be performed by the user on
the actual shop host. Use the detailed result sheet in `deploy/PILOT_CHECKLIST.md`.

1. Install with a production `.env`, enable Docker Desktop start-on-sign-in, restart Windows, sign
   in, and confirm the POS becomes available without manually starting containers.
2. Install and immediately run the Windows daily-backup task; confirm a new dump and SUCCESS log.
3. Disconnect internet and manually exercise login, Products & Stock, POS, Orders, returns, voids,
   Reports, Audit, and local styling/assets.
4. Restore a new verified dump into an isolated clean test installation; verify health, login,
   latest order, sample stock, report totals, and inventory reconciliation.
5. Perform the physical USB scanner, quick-create, signed-change, cashier-handoff, two-client
   concurrency, negative-stock, linked-return, void, and reconciliation scenarios.
6. Complete the supervised live pilot, reconcile physical cash and selected stock, document every
   difference, and obtain owner approval with no unexplained discrepancy.

Milestone 7—and therefore the MVP—must remain **pending user verification** until all six groups pass.
