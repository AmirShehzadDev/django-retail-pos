# Milestone 7 Development Tasks - Offline Deployment and Shop Pilot

**Status:** Implemented; planning review passed  
**Inputs:** `docs/milestones/m7-offline-deployment/feature-spec.md`, `docs/milestones/m7-offline-deployment/technical-design.md`

## Task 1 - Reconcile deployment decisions

- Update project technical design from host Waitress to Linux-container Gunicorn.
- Document versioned Docker packages and persistent configuration/data boundaries.
- Acceptance: no active production guidance selects Waitress; MVP/milestone scope is unchanged.

## Task 2 - Build the production application image

- Add `.dockerignore`, multi-stage `Dockerfile`, and Gunicorn configuration.
- Replace Waitress with exact-pinned Gunicorn 26.0.0.
- Compile Tailwind, collect static files, and run as non-root.
- Acceptance: image builds, has production assets, starts Gunicorn, and contains no `.env`/backup.

## Task 3 - Complete production Compose topology

- Add versioned `web` service, health dependency/check, loopback binding, log mount, and restart.
- Preserve the existing PostgreSQL volume/init behavior and loopback-only maintenance port.
- Add deployment environment examples.
- Acceptance: `docker compose config` passes and web waits for healthy DB.

## Task 4 - Add database-aware health/version behavior

- Add application version setting and DB readiness check to `/health/`.
- Return HTTP 503 safely on DB failure.
- Add focused tests.
- Acceptance: status/version and unavailable paths pass without leaking configuration.

## Task 5 - Implement shared deployment safety helpers

- Add PowerShell module for root/config resolution, native command checks, version validation,
  `.env` key updates, state, locking, container discovery, and health polling.
- Acceptance: scripts support paths with spaces, do not print secrets, and parse successfully.

## Task 6 - Implement start, stop, status, and initial install

- Add idempotent lifecycle/status scripts and release-based initial installer.
- Apply migrations once before web startup; never on normal container restart.
- Acceptance: clean install selects version, migrates, starts healthy services, and records state.

## Task 7 - Implement verified backups and scheduling

- Add custom-format dump, validation, atomic host copy, seven-day safe pruning, logging, optional
  external copy, and scheduled-task installer.
- Acceptance: failures return non-zero; retention can only target matching files inside validated
  backup directory; scheduler command is absolute and quoted.

## Task 8 - Implement restore and rollback

- Add dump validation, explicit data-replacement confirmation, scoped DB recreate/restore, migration,
  health verification, and prior-image rollback wrapper.
- Acceptance: no destructive operation occurs without explicit flag; no volume-delete command exists.

## Task 9 - Implement release build and update

- Add release manifest/checksum/image export/zip builder and update installer.
- Require verified pre-update backup and preserve prior version/recovery details.
- Acceptance: shop update installs no online dependency, preserves `.env`/volume, and provides exact
  recovery instruction on failure.

## Task 10 - Add automated deployment contract tests

- Test health behavior and important Docker/script safety contracts.
- Parse all PowerShell files, validate Compose, build production image, and run checks/tests.
- Acceptance: focused and full automated suites pass; image health can be observed with PostgreSQL.

## Task 11 - Write deployment and shop operations documentation

- Write install/update/rollback/backup/restore/log/troubleshooting runbook.
- Write owner/admin/cashier daily instructions and future private-LAN procedure.
- Replace root Waitress instructions with Docker/Gunicorn workflow.
- Acceptance: a developer can update remotely and a shop owner can check daily health/backup without
  needing Git, Python, or Node.js.

## Task 12 - Prepare manual release and pilot evidence

- Create required Windows restart, offline, scanner, scheduler, clean restore, workflow, concurrency,
  reconciliation, and pilot checklist.
- Record automated evidence separately from pending user-operated checks.
- Acceptance: every Milestone 7 exit criterion has an automated result or an explicit manual result
  field; no manual/frontend/hardware claim is fabricated.

## Planning review

Reviewed `docs/milestones/m7-offline-deployment/feature-spec.md`, `docs/milestones/m7-offline-deployment/technical-design.md`, and this task list together against
`docs/product/mvp-requirements.md` 1.7, `docs/product/roadmap.md`, project `docs/architecture/technical-design.md`, Milestones 0-6 behavior,
and the current repository.

Findings corrected before implementation:

1. Gunicorn cannot run natively on the Windows host; the design places it in the Linux web container.
2. Automatic migrations on every restart would make startup/rollback unsafe; migrations are explicit
   install/update/restore operations.
3. A checksum alone is not a publisher signature; documentation describes integrity accurately.
4. Automatic rollback after attempted migrations could silently discard new data; rollback requires
   explicit confirmation and the pre-update dump.
5. Docker Desktop is per-user on the supported host; automatic service and scheduled-backup claims
   are bounded by Windows sign-in and require real-host verification.
6. Direct PowerShell redirection can corrupt binary dumps on older Windows PowerShell; dumps are
   produced/validated in the DB container and transferred with `docker cp`.
7. A future LAN recipe must not expose PostgreSQL; only the application port is eligible.
8. Remote TeamViewer access is useful for maintenance but must not become a runtime dependency.

Second review result: **passed**. The documents are mutually consistent, cover all milestone exit
criteria, retain the approved business behavior, and contain no unresolved material decision.

## Post-completion deployment correction

- Make Compose project identity an explicit persistent environment setting with a safe default.
- Document that project identity must remain unchanged through runtime-file replacement and must
  differ between installations sharing a Docker host.
- Add a deployment contract test for the Compose interpolation and example environment value.
- Re-run deployment-focused and full regression verification before the public release commit.
