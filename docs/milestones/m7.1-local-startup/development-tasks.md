# Milestone 7.1 Development Tasks - Local Startup and Deployment Hardening

**Status:** Implementation and automated verification complete; pending user verification
**Inputs:** Approved feature specification and technical design in this folder

1. Add friendly-host defaults without changing loopback binding.
2. Add strict, secret-safe `.env` dollar-sign preflight.
3. Make database-container discovery ignore non-ID output.
4. Implement idempotent elevated Windows hostname setup and existing `.env` refinement.
5. Add the bounded Docker/POS/browser desktop launcher.
6. Update initial-install, update, troubleshooting, startup, and secret-generation guidance.
7. Extend deployment contracts and documentation indexing.
8. Run PowerShell parsing, Compose configuration checks, Ruff, focused tests, and relevant full
   regression checks.
9. Record automated evidence and provide the required user-owned Windows checklist.

## Planning review

Reviewed against the parent Milestone 7 specification/design/tasks, project requirements and
architecture, the current `1.0.0` release workflow, the observed `$npid` backup failure, and the
current deployment scripts.

Corrections incorporated before implementation:

- The friendly hostname does not justify port 80, LAN binding, or weaker host/origin validation.
- New defaults do not update an existing `.env`; the one-time setup performs an idempotent targeted
  update instead of copying `.env.example`.
- Removing `$npid` from the affected live `.env` preserves the already-interpolated credential, but
  future deployment scripts must reject all dollar signs before Compose runs.
- Filtering database discovery is still required even after configuration validation because native
  tools may emit unrelated warnings in the future.
- GitHub release `1.0.0` remains immutable; publication of `1.0.1` occurs only after implementation,
  manual approval to commit/push, a clean release build, and separate release approval.

Second review result: **passed**. Scope, safety boundaries, implementation order, and acceptance
coverage are mutually consistent and ready for implementation.

## Implementation result

Tasks 1-8 are complete. Task 9 is complete for automated evidence and remains pending for the
user-owned Windows checklist recorded in `completion.md`.
