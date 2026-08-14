# Milestone 1 - Development Tasks

**Status:** Complete

**Version:** 1.0

**Inputs:** `docs/milestones/m1-users/feature-spec.md` v1.0 and `docs/milestones/m1-users/technical-design.md` v1.0

## 1. Objective

Implement and verify authentication, role enforcement, user/password management, focused account
audit events, single-shop settings, and locally compiled Tailwind templates. Do not add workflows
from later milestones.

## 2. Ordered task summary

| ID | Task | Depends on |
|---|---|---|
| M1-01 | Add Tailwind build dependencies and repository configuration | Approved design |
| M1-02 | Add user constraints and `AuditEvent` migrations | Approved design |
| M1-03 | Implement audit writer and authorization policies | M1-02 |
| M1-04 | Implement transactional account and shop services | M1-03 |
| M1-05 | Configure authentication, sessions, and production admin boundary | M1-02 |
| M1-06 | Implement forms, views, and URLs | M1-04, M1-05 |
| M1-07 | Build Tailwind templates and role-aware navigation | M1-01, M1-06 |
| M1-08 | Complete automated test coverage | M1-02 through M1-07 |
| M1-09 | Update setup/development documentation | M1-01 through M1-08 |
| M1-10 | Run automated and production-style verification | M1-08, M1-09 |
| M1-11 | Record evidence and prepare manual acceptance checklist | M1-10 |

## 3. Detailed tasks

### M1-01 - Tailwind toolchain

#### Work

- Add exact-pinned `tailwindcss` and `@tailwindcss/cli` 4.3.3 development dependencies.
- Commit `package-lock.json` and ignore `node_modules/`.
- Add CSS build/watch scripts and the CSS-first Tailwind input file with explicit Django sources.
- Replace the handwritten output with deterministic compiled `static/css/app.css`.
- Keep Node/npm out of the application runtime path.

#### Acceptance criteria

- `npm ci` succeeds from the lockfile.
- `npm run css:build` succeeds and a second build produces no Git difference.
- Compiled CSS works without a CDN or browser-side Tailwind runtime.

### M1-02 - Models, constraints, and migrations

#### Work

- Add case-insensitive username uniqueness and one-owner-per-shop constraints.
- Add a migration precheck for existing case-insensitive duplicate usernames.
- Add `core.AuditEvent` with approved fields, action codes, indexes, and protected references.
- Keep audit records outside Django admin.
- Generate and review migrations without changing existing bootstrap data.

#### Acceptance criteria

- PostgreSQL rejects case-insensitive username duplicates and a second shop owner.
- Existing owner/shop/terminal data remains valid.
- Audit records can be appended with the required relationships and payloads.
- `makemigrations --check --dry-run` reports no changes.

### M1-03 - Audit writer and policies

#### Work

- Implement the focused audit append function and sensitive-key rejection.
- Implement pure actor/target authorization policies for every M1 capability.
- Enforce same-shop scope and ensure staff/superuser flags never influence business policy.
- Add table-driven unit tests for the full owner/admin/cashier matrix.

#### Acceptance criteria

- All approved role transitions and target restrictions match the feature specification.
- Cross-shop access is rejected.
- Sensitive values cannot enter an audit payload.
- No later-milestone generic permission framework is introduced.

### M1-04 - Transactional services

#### Work

- Implement create/edit/role/status/password services for managed users.
- Implement own-password change auditing.
- Implement owner-only shop-name update service.
- Lock/reload actors and targets, validate at the service boundary, and write audit events in the
  same transaction.
- Make unchanged edits and repeated active-state requests safe and non-auditing.

#### Acceptance criteria

- Owner can manage admins/cashiers; admin can manage cashiers only.
- No service can create/manage an owner or cross-shop target.
- Failed/audit-failed changes roll back completely.
- Passwords and hashes never appear in audit data.
- Deactivation/reactivation preserves role and password.

### M1-05 - Authentication and sessions

#### Work

- Configure login/logout redirects and browser-session expiry.
- Implement case-insensitive canonical username lookup with generic failure messages.
- Implement POST-only logout and no-store protected responses.
- Preserve only the current session after own-password change and invalidate other stale sessions.
- Ensure inactive users lose access on their next request.
- Mount Django admin only under development `DEBUG=True`.

#### Acceptance criteria

- All active roles can log in; inactive/invalid attempts fail without account disclosure.
- External `next` redirects are rejected.
- Logout flushes the session and GET logout is rejected.
- Password/deactivation session behavior matches the approved specification.
- `/admin/` returns 404 in production settings.

### M1-06 - Forms, views, and URLs

#### Work

- Add the approved authentication, user create/edit, password, and shop forms.
- Add protected list/detail/create/edit/status/password-change views.
- Add read-only admin and editable owner shop-settings behavior.
- Scope user lookup/search/filter queries by the actor's shop and visible roles.
- Use POST-redirect-GET, CSRF protection, friendly messages, 403, and non-disclosing 404 behavior.

#### Acceptance criteria

- Each URL and submitted field obeys the approved permission matrix.
- Crafted POST fields cannot alter owner/shop/staff/superuser/currency/timezone fields.
- User filters never widen visible scope.
- Successful forms redirect and refresh does not repeat changes.

### M1-07 - Templates and Tailwind UI

#### Work

- Restyle the base shell with local Tailwind utilities and role-aware navigation.
- Add login, home, user list/detail/form, password, shop-settings, and 403 templates.
- Provide explicit labels, accessible errors, focus states, status text, and large controls.
- Use a normal POST form for logout and account-status confirmations.
- Keep full Tailwind class names statically discoverable and JavaScript optional.

#### Acceptance criteria

- Owner, admin, and cashier see only permitted navigation/actions.
- Forms are keyboard-usable and communicate errors/status without relying on color alone.
- No page loads a CDN, remote font, telemetry script, or external asset.
- Pages remain functional without JavaScript.

### M1-08 - Automated tests

#### Work

- Add model/constraint and audit tests.
- Add policy/service matrix, rollback, idempotency, and cross-shop tests.
- Add login/logout/session/password/no-store tests.
- Add form/view permission, filtering, crafted-field, CSRF, and redirect tests.
- Add template/navigation/local-asset tests and production-admin routing tests.
- Preserve and run all M0 tests against PostgreSQL.

#### Acceptance criteria

- Every acceptance criterion in `docs/milestones/m1-users/feature-spec.md` has an automated test where practical.
- Tests prove both allowed and denied behavior for all three roles.
- The complete PostgreSQL suite passes without weakening M0 coverage.

### M1-09 - Documentation

#### Work

- Document Node/npm versions, `npm ci`, Tailwind watch/build commands, and generated-output policy.
- Update setup and routine development commands without making Node a runtime dependency.
- Document bootstrap/login flow and production admin unavailability.
- Add troubleshooting for stale CSS, missing Node modules, and account access.

#### Acceptance criteria

- A new developer can build CSS and run Django from committed instructions.
- The shop runtime can use committed compiled CSS without npm or internet access.
- Documentation contains no real credentials or machine-specific absolute path.

### M1-10 - Verification gate

#### Work

- Apply migrations to the Docker PostgreSQL database.
- Run Django checks, migration checks, Ruff, formatter check, full PostgreSQL tests, pip check,
  Tailwind clean install/build, and `collectstatic`.
- Start development and Waitress production-style servers and smoke login/static/health routes.
- Confirm production `/admin/` is unavailable and rendered pages contain no external URLs.
- Review Git for secrets, environment files, node modules, generated runtime output, and stale CSS.

#### Acceptance criteria

- All automated and build checks pass.
- Migrations apply cleanly and the application starts through both server paths.
- Local compiled CSS is served successfully with no runtime network dependency.
- Repository status contains only intentional source and compiled frontend artifacts.

### M1-11 - Completion and manual handoff

#### Work

- Create `docs/milestones/m1-users/completion.md` mapping results to the milestone exit criteria.
- Mark automated completion separately from manual acceptance.
- Give the user an ordered real-browser checklist covering each role, password/status changes,
  settings, navigation, Back behavior, direct-access denial, and disconnected-internet operation.
- Do not prepare Milestone 2 until required manual checks are accepted or explicitly deferred.

#### Acceptance criteria

- Automated evidence is recorded with command results.
- Required and optional manual checks are clearly distinguished.
- Any failed manual behavior keeps the milestone open.

## 4. Explicit exclusions

- Owner creation/management, email recovery, lockout, 2FA, user deletion, and shift management.
- Editable currency/timezone/shop activity or terminal settings.
- User-visible audit history.
- Product, inventory, POS, order, payment, void, return, reporting, backup, or service installation.
- JavaScript UI frameworks, Tailwind CDN, or Node as a shop runtime dependency.

## 5. Completion rule

Milestone 1 is complete only when M1-01 through M1-11 pass, all automated evidence is recorded, and
the required manual acceptance scenarios either pass or are explicitly deferred by the user with
the milestone remaining marked accordingly.
