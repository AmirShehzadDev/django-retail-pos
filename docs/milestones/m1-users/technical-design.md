# Milestone 1 - Technical Design

**Status:** Approved

**Version:** 1.0

**Feature specification:** `docs/milestones/m1-users/feature-spec.md` v1.0

**Project design:** `docs/architecture/technical-design.md` v0.5

## 1. Purpose and scope

This refinement translates the approved Milestone 1 behavior into concrete Django models,
constraints, services, forms, views, URLs, templates, session rules, Tailwind tooling, and tests.

It implements authentication, authorization, user/password management, account audit events, and
single-shop settings only. It does not add product, inventory, POS, order, return, void, report, or
audit-history screens.

## 2. Existing foundation

Milestone 1 extends the following Milestone 0 records rather than replacing them:

- `accounts.User`, derived from `AbstractUser`, with `shop`, `role`, `created_by`, and `is_active`.
- `core.Shop`, with fixed `PKR` currency and `Asia/Karachi` timezone constraints.
- The bootstrap-created owner, shop, and `TILL-1` terminal.
- Django database sessions, CSRF middleware, templates, WhiteNoise, and PostgreSQL.

Application roles remain separate from Django's groups and model-permission tables. The business
authorization policy uses the `role` field and same-shop checks. `is_staff` and `is_superuser` are
installation/development concerns and never grant access through a business service.

## 3. Proposed code structure

```text
apps/
|-- accounts/
|   |-- forms.py
|   |-- policies.py
|   |-- services.py
|   |-- urls.py
|   |-- views.py
|   `-- tests/
|-- core/
|   |-- audit.py
|   |-- forms.py
|   |-- services.py
|   |-- urls.py
|   |-- views.py
|   `-- tests/
assets/
`-- css/
    `-- input.css
static/
`-- css/
    `-- app.css
templates/
|-- accounts/
|-- core/
|-- errors/
`-- partials/
package.json
package-lock.json
```

Files are kept inside the existing `accounts` and `core` apps. No new Django app or frontend
framework is introduced.

## 4. Database design

### 4.1 User constraints

`accounts.User` keeps its current fields and receives two PostgreSQL constraints:

1. `accounts_user_username_ci_unique`: functional unique constraint on `Lower("username")`.
   The original case remains stored and displayed, while `amir` and `Amir` cannot coexist.
2. `accounts_user_one_owner_per_shop`: conditional unique constraint on `shop` where
   `role="OWNER"`. This enforces at most one owner per shop.

The existing exact-case username uniqueness and role check remain. Application forms strip
leading/trailing whitespace before validation. A migration precheck fails with a clear message if
legacy case-insensitive duplicates exist before the new constraint is applied.

Business services always set newly managed accounts to `is_staff=False` and
`is_superuser=False`. They do not expose group, permission, staff, or superuser fields.

### 4.2 AuditEvent

Milestone 1 introduces `core.AuditEvent`:

| Field | Type and rule |
|---|---|
| `id` | `BigAutoField` primary key |
| `shop` | Required `ForeignKey(Shop, PROTECT)` |
| `actor` | Required `ForeignKey(User, PROTECT)` |
| `action` | `CharField(max_length=64)` using Milestone 1 action choices |
| `target_type` | `CharField(max_length=64)`, initially `USER` or `SHOP` |
| `target_identifier` | `CharField(max_length=64)` containing a stable string primary key |
| `before_values` | `JSONField(default=dict)` with approved non-sensitive previous values |
| `after_values` | `JSONField(default=dict)` with approved non-sensitive new values |
| `created_at` | `DateTimeField(auto_now_add=True)` |

Indexes support `(shop, -created_at)`, `(shop, action, -created_at)`, and
`(target_type, target_identifier)`. The model is not registered in Django admin and has no update
or delete service. Normal application code can append events only through `core.audit.record()`.

Initial action codes:

- `USER_CREATED`
- `USER_PROFILE_UPDATED`
- `USER_ROLE_CHANGED`
- `USER_ACTIVATED`
- `USER_DEACTIVATED`
- `USER_PASSWORD_RESET`
- `USER_PASSWORD_CHANGED`
- `SHOP_NAME_CHANGED`

Choices can be extended by later approved milestones without widening the field. A database check
is not added to `action` or `target_type`, avoiding repeated constraint replacement each time the
approved audit vocabulary grows.

### 4.3 Migration order

1. Add a data-validation operation for case-insensitive username duplicates.
2. Add the functional username uniqueness and one-owner-per-shop constraints in `accounts`.
3. Create `AuditEvent` in `core`; its migration depends on the current custom user migration.
4. Run migration/model-state checks against PostgreSQL.

No existing owner password, role, shop, terminal, or session is rewritten. The development
database is backed up before applying the migration if it contains non-disposable data.

## 5. Authorization design

### 5.1 Policy functions

`accounts.policies` contains side-effect-free decisions that accept real user/target objects:

- `can_view_user(actor, target)`
- `can_create_role(actor, requested_role)`
- `can_edit_user(actor, target)`
- `can_change_role(actor, target, requested_role)`
- `can_change_active_state(actor, target)`
- `can_reset_password(actor, target)`
- `can_view_shop_settings(actor)`
- `can_edit_shop_settings(actor)`

The rules implement the approved matrix exactly:

- Owner can manage same-shop admins and cashiers, including transitions between those roles.
- Admin can manage same-shop cashiers only.
- Nobody can manage the owner or create/promote another owner.
- Cashier cannot access management operations.
- No role can target a different shop.

These policies do not rely on `is_superuser`, `is_staff`, template visibility, or a submitted role.
Later milestones may add named capability helpers, but M1 does not build a speculative generic
permission framework.

### 5.2 HTTP behavior

- Anonymous requests to protected pages redirect to login with a safe local `next` value.
- An authenticated user lacking page-level capability receives HTTP 403.
- A user ID that is nonexistent, out-of-shop, or not visible to the actor returns HTTP 404.
- A stale form is authorized again during POST processing against fresh database state.
- Templates show only allowed navigation/actions, but views and services remain authoritative.

### 5.3 Django admin boundary

The `/admin/` URL is mounted only when `DEBUG=True`. Production settings return 404 for `/admin/`,
so the bootstrap owner's Django superuser flag cannot bypass application workflow rules. Existing
foundation registrations remain available to a developer in local development only.

## 6. Service and transaction design

All business changes use explicit service functions. Views load display data and forms validate
HTTP input, but neither writes protected fields directly.

### 6.1 User services

`accounts.services` provides:

- `create_managed_user(actor, username, first_name, last_name, role, password)`
- `update_managed_user(actor, target_id, username, first_name, last_name, role)`
- `set_managed_user_active(actor, target_id, active)`
- `reset_managed_user_password(actor, target_id, new_password)`

Each service:

1. Opens `transaction.atomic()`.
2. Reloads and locks the active actor; mutation is refused if their current role no longer permits
   it.
3. Locks an existing target where applicable.
4. Applies same-shop and role policy checks.
5. Revalidates normalized values at the service boundary.
6. Saves only explicitly permitted fields.
7. Appends the exact audit event in the same transaction.
8. Returns the changed object and whether a material state transition occurred.

An unchanged edit or repeated active-state request returns successfully without writing an audit
event. Exceptions roll back both the domain write and the audit append.

Creation always derives `shop` and `created_by` from the actor, sets the permitted role, and forces
non-owner Django staff/superuser flags off. Passwords are validated using Django's configured
validators before `set_password()`.

### 6.2 Own password change

Django's `PasswordChangeForm` validates the current password and new password. A small service
saves the new hash and appends `USER_PASSWORD_CHANGED` atomically. After commit, the view calls
`update_session_auth_hash()` so the current session survives with a rotated authentication hash.
Other sessions retain the old hash and are rejected on their next request.

### 6.3 Manager password reset

The reset service checks the fresh target and actor, validates the new password in the target's
context, calls `set_password()`, and records `USER_PASSWORD_RESET` without before/after password
data. All of the target's existing sessions carry a stale authentication hash and stop working on
their next request.

### 6.4 Shop settings

`core.services.update_shop_name(actor, name)` locks the actor and their shop, requires owner role,
normalizes/validates the name, saves only `name`, and appends `SHOP_NAME_CHANGED` atomically.
Currency, timezone, active status, and shop ID never come from submitted form data.

### 6.5 Audit writer

`core.audit.record()` requires an active actor, verifies `actor.shop_id == shop.id`, accepts only an
approved action/target pair, copies explicitly supplied dictionaries, and rejects sensitive key
names such as password, hash, token, cookie, session, and CSRF. It does not catch database errors;
the calling transaction must fail rather than leave an unaudited change.

## 7. Authentication and session design

Settings add:

```python
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:home"
LOGOUT_REDIRECT_URL = "accounts:login"
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
```

### Login

- A custom `AuthenticationForm` strips the entered username and resolves it with
  `username__iexact` to the single canonical stored username before calling Django authentication.
- Missing, duplicate, inactive, and invalid credentials all produce the same generic form error.
- Django's `LoginView` rotates the session key and validates `next` against allowed hosts/schemes.
- Authenticated requests to login redirect to the home page.
- Login responses and protected views use `never_cache`/`Cache-Control: no-store`.

### Logout

- A dedicated POST-only view calls Django logout, flushes the session, and redirects to login.
- There is no GET logout or switch-user route.

### Active-state enforcement

Django's authentication backend rejects inactive users while restoring a session. User services
also reload `is_active` from PostgreSQL before mutations. Deactivating an account therefore blocks
new login and removes existing authenticated access on the next request.

The implementation does not enumerate or store session identifiers in audit records.

## 8. Forms

| Form | Exposed fields and validation |
|---|---|
| `PosAuthenticationForm` | Username, password; trimmed case-insensitive canonical lookup and generic failure |
| `ManagedUserCreateForm` | Username, first name, last name, permitted role, password, confirmation |
| `ManagedUserUpdateForm` | Username, first name, last name, owner-only role selection |
| `ManagedPasswordResetForm` | New password and confirmation; validates in target context |
| `PosPasswordChangeForm` | Current password, new password, confirmation |
| `ShopSettingsForm` | Shop name only; currency/timezone rendered outside the submitted form |

Forms receive the actor (and target where relevant) in their constructor. They limit visible choices
for usability; services independently repeat authorization. Email, groups, individual permissions,
staff/superuser status, shop, creator, last login, and date joined are never accepted from these
forms.

Widget classes are set explicitly in Python/template helpers using complete Tailwind class strings.
Templates do not construct partial class names dynamically, because Tailwind scans source text for
complete utility tokens.

## 9. Views and URLs

| URL | Methods | Access | Behavior |
|---|---|---|---|
| `/accounts/login/` | GET, POST | Anonymous | Login form; authenticated users redirect home |
| `/accounts/logout/` | POST | Authenticated | Flush session and redirect to login |
| `/accounts/password/change/` | GET, POST | Authenticated | Change own password |
| `/accounts/users/` | GET | Owner/admin | Scoped list, search, role/status filters |
| `/accounts/users/create/` | GET, POST | Owner/admin | Create only an allowed subordinate role |
| `/accounts/users/<id>/` | GET | Authorized manager | Scoped details and available actions |
| `/accounts/users/<id>/edit/` | GET, POST | Authorized manager | Edit allowed identity/role fields |
| `/accounts/users/<id>/deactivate/` | POST | Authorized manager | Idempotent deactivation |
| `/accounts/users/<id>/reactivate/` | POST | Authorized manager | Idempotent reactivation |
| `/accounts/users/<id>/password/` | GET, POST | Authorized manager | Set a new subordinate password |
| `/settings/shop/` | GET, POST | Owner/admin | Owner edits name; admin GET is read-only |
| `/` | GET | Authenticated | Role-aware home/dashboard |
| `/health/` | GET | Public | Existing minimal local health response |

All successful mutations use POST-redirect-GET and Django messages. User list filters use GET:
`q`, `role`, and `status`. Invalid filter values are ignored or rejected consistently without
expanding the actor's visible queryset. The list uses `select_related("shop", "created_by")` and is
not paginated for the approved single-shop scale.

## 10. Templates and UI

Templates remain server-rendered and progressively usable without JavaScript:

- `accounts/login.html`
- `accounts/user_list.html`
- `accounts/user_detail.html`
- `accounts/user_form.html`
- `accounts/password_reset.html`
- `accounts/password_change.html`
- `core/home.html`
- `core/shop_settings.html`
- `errors/403.html`
- shared navigation, messages, field errors, status badge, and confirmation partials

The base template shows shop name, authenticated identity/role, permitted navigation, and a POST
logout form. Forms have explicit labels, field-level errors, summaries, autocomplete attributes,
visible keyboard focus, and sufficiently large controls. Active/inactive and role states use text
as well as color. No icon, font, or component library is fetched at runtime.

Confirmation for activation/deactivation occurs on the detail page with a clear POST button;
JavaScript modal behavior is not required. The M1 JavaScript entry point remains minimal.

## 11. Tailwind build design

The project uses the official Tailwind CLI without Vite, PostCSS, a Django Tailwind package, or a
JavaScript UI framework.

Pinned development packages:

```json
{
  "scripts": {
    "css:build": "tailwindcss -i ./assets/css/input.css -o ./static/css/app.css --minify",
    "css:watch": "tailwindcss -i ./assets/css/input.css -o ./static/css/app.css --watch"
  },
  "devDependencies": {
    "@tailwindcss/cli": "4.3.3",
    "tailwindcss": "4.3.3"
  }
}
```

The verified build environment is Node 22.22.3 with npm 10.9.8. `package-lock.json` is committed;
`node_modules/` is ignored. Node/npm are required to develop or rebuild CSS, but not to operate the
installed POS.

`assets/css/input.css` uses Tailwind v4's CSS-first configuration:

```css
@import "tailwindcss" source(none);
@source "../../templates";
@source "../../apps";
@source "../../static/js";
```

The file also defines a small `@theme` palette and sizing tokens suitable for checkout screens.
Source paths are explicit and relative to the stylesheet, preventing accidental scanning of the
virtual environment, generated static files, or `node_modules`.

Package scripts:

- `npm run css:watch` compiles `assets/css/input.css` to `static/css/app.css` with `--watch`.
- `npm run css:build` performs the minified deterministic production build.

The generated `static/css/app.css` is committed so a Django-only checkout/runtime can start without
Node or internet access. Verification rebuilds it and fails if committed output is stale. The
existing handwritten M0 stylesheet is replaced by the generated file; any genuinely necessary
custom rules move into `input.css` using CSS/Tailwind directives.

Tailwind class names are written as complete literal strings in templates and Python widget
configuration. If later runtime variants are required, the complete possible classes are placed in
source or explicitly safelisted rather than built through string interpolation.

## 12. Audit payloads

| Action | `before_values` | `after_values` |
|---|---|---|
| User created | `{}` | Username, names, role, active status, creator ID |
| Profile updated | Changed old identity fields only | Changed new identity fields only |
| Role changed | Old role | New role |
| Activated/deactivated | Old active status | New active status |
| Manager password reset | `{}` | `{}`; the action code is the complete audit fact |
| Own password changed | `{}` | `{}`; the action code is the complete audit fact |
| Shop name changed | Old name | New name |

If profile and role change in one submitted edit, the service creates one
`USER_PROFILE_UPDATED` event for identity changes and one `USER_ROLE_CHANGED` event for the role
transition. Each event is focused and appears only when its values changed.

Audit timestamps are generated by the database-backed Django write time and displayed in
`Asia/Karachi` later. M1 does not expose an audit list/detail view.

## 13. Security and failure handling

- All mutations require CSRF-protected POST.
- Password fields use appropriate autocomplete values and are never repopulated.
- Application logs contain no submitted usernames on failed login and no password/form dumps.
- Protected responses use `no-store`; static assets retain normal cache behavior.
- Service exceptions become friendly form/page errors without stack traces in production.
- Production removes the Django admin URL and keeps `DEBUG=False`.
- Cross-shop identifiers do not disclose whether the target exists.
- Database/audit failures roll back the whole mutation.
- No role or permission decision trusts hidden inputs, query parameters, or JavaScript state.

## 14. Automated test design

### Model and migration tests

- Case-insensitive username duplicates fail at the database level.
- Only one owner can exist per shop; different shops may each have one owner.
- Valid role/shop users continue to work after migration.
- Audit fields, ordering/index intent, and protected references behave as designed.
- No unexpected migrations remain after implementation.

### Policy and service tests

- Table-driven tests cover every actor/target/role transition in the approved matrix.
- Cross-shop targets fail for owner, admin, and cashier.
- Services recheck a freshly loaded active actor and reject stale authority.
- Create/edit/role/status/password/shop changes write the expected focused audit event.
- Unchanged, repeated, failed, unauthorized, and rolled-back operations write no change event.
- Deactivation/reactivation preserves the target's role and password hash.
- Password audit payloads contain no password or hash material.
- Concurrent/stale status and role submissions preserve constraints and accurate before/after data.

### Authentication and session tests

- Active roles can log in; invalid and inactive users receive the same generic error.
- Username canonical lookup is case-insensitive and cannot become ambiguous.
- Safe local `next` works and external `next` is rejected.
- Login rotates the session key; POST logout flushes it; GET logout is rejected.
- Browser-session expiry is configured.
- Deactivation blocks an existing session on its next request.
- Own password change preserves only the current session; manager reset invalidates target sessions.
- Protected pages set no-store cache headers.

### View and form tests

- Every URL's anonymous, owner, admin, and cashier response matches the permission matrix.
- Direct/crafted POSTs cannot change owner, shop, staff flags, superuser flags, or unauthorized
  roles.
- User search and filters never expand beyond the actor's visible scope.
- Shop form changes only name; PKR/timezone remain fixed under crafted submissions.
- POST-redirect-GET prevents refresh duplication.
- CSRF-enforced client tests reject unprotected state changes.
- Production settings return 404 for `/admin/`; development retains the inspection route.

### Template and frontend tests

- Navigation and action controls match the authenticated role.
- Labels, errors, status text, logout form, and identity context render correctly.
- Rendered HTML contains only local asset URLs.
- `npm ci` and `npm run css:build` pass from the lockfile.
- Rebuilding Tailwind produces no uncommitted `static/css/app.css` change.
- `collectstatic`, WhiteNoise/Waitress smoke checks, Ruff, Django checks, and all PostgreSQL tests
  pass.

## 15. Implementation sequence constraints

The later development-task document should preserve these technical dependencies:

1. Add and verify data constraints/AuditEvent migrations.
2. Implement audit writer, policies, and transaction services with tests.
3. Implement authentication/session behavior and permission mixins.
4. Add Tailwind build inputs, pinned lockfile, compiled output, and base components.
5. Implement forms, views, URLs, and templates.
6. Complete permission/session/view/frontend tests and production smoke checks.
7. Record automated evidence and execute the required browser/manual checklist.

This sequence is dependency guidance, not the Milestone 1 development-task breakdown.

## 16. Explicit technical exclusions

- Email backend/user email workflow, invitations, and emailed password resets.
- Login throttling, lockout, two-factor authentication, and session-management UI.
- Django groups, per-object permission packages, or a generic rules engine.
- User deletion, owner management, terminal assignment, shifts, or employee records.
- Editable currency, timezone, shop activity, tax, or terminal settings.
- Audit history UI and login-attempt analytics.
- Vite, React, Vue, Alpine, Tailwind Play CDN, Tailwind Plus, and third-party form renderers.
- Product, inventory, sales, order, return, report, backup, and deployment-service behavior.

## 17. Technical review gate

Before creating `docs/milestones/m1-users/development-tasks.md`, confirm that:

1. The data constraints and focused audit model match the approved feature behavior.
2. The role policy and production Django-admin boundary are accepted.
3. Password/session invalidation behavior is accepted.
4. The URLs, forms, and page set are sufficient without adding later-milestone screens.
5. Tailwind CLI 4.3.3, committed compiled CSS, and Node-as-build-only are accepted.
6. The test matrix covers every Milestone 1 acceptance criterion.
