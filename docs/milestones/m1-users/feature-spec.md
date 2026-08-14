# Milestone 1 - Authentication, Roles, and Shop Settings

**Status:** Approved

**Version:** 1.0

**Inputs:** `docs/product/mvp-requirements.md` v1.4, `docs/product/roadmap.md` v1.3,
`docs/architecture/technical-design.md` v0.5, and the Milestone 0 foundation

## 1. Objective

Ensure that every application action is performed in an authenticated user session and that the
owner, admins, and cashiers can access only the operations allowed for their role.

Milestone 1 adds login/logout, account management, password management, role enforcement, focused
account audit events, and the single-shop settings page. It does not add product, inventory, POS,
order, return, or reporting screens.

## 2. Actors

### Owner

- The single owner is created by the installation bootstrap command.
- Can perform every admin and cashier action.
- Can create and manage admins and cashiers.
- Can promote a cashier to admin or demote an admin to cashier.
- Can edit the shop name.
- Cannot create another owner or change an account to the owner role through the application.

### Admin

- Can create and manage cashier accounts in the same shop.
- Cannot create, edit, activate, deactivate, reset the password of, or change the role of an owner
  or another admin.
- Cannot promote a cashier to admin.
- Can view the fixed shop settings but cannot change them.

### Cashier

- Can log in, log out, view their own identity, and change their own password.
- Cannot access user management or the shop settings page.
- Retains the approved future permissions to sell, quick-create an unknown scanned product, view
  completed shop orders, and process linked returns when those features are implemented.

### Anonymous visitor

- Can access only login, health, and locally served static files.
- Is redirected to login when requesting any other application page.

## 3. MVP decisions made in this specification

1. The bootstrap-created owner remains the only owner. There is no owner creation, promotion,
   demotion, activation, or deactivation workflow in the application.
2. The owner manages all non-owner users. An admin manages cashiers only, regardless of who
   originally created the cashier.
3. A manager supplies and confirms an initial password when creating a subordinate account.
   There is no emailed invitation or temporary link because the system is fully offline.
4. A manager can set a new password for a subordinate account. The current password is never
   displayed, recoverable, or included in audit data.
5. Every user can change their own password by supplying the current password and confirming the
   new password.
6. Forced password changes, password expiry, forgotten-password questions, email recovery, and
   login lockout are excluded from the MVP.
7. Usernames are unique without regard to letter case. Leading/trailing spaces are removed, and
   users log in with the stored username and password.
8. The owner can edit only the shop name. Currency remains `PKR` and timezone remains
   `Asia/Karachi`; both are displayed as read-only values. Admins may view these values.
9. Sessions expire when the browser session ends. There is no remember-me or switch-user action;
   a cashier leaving the computer must explicitly log out first.
10. Django admin is a development inspection tool, not a shop workflow. It must not provide a
    production bypass around these role and owner-account rules.

## 4. Permission matrix

| Capability | Owner | Admin | Cashier |
|---|---:|---:|---:|
| Log in, log out, and change own password | Yes | Yes | Yes |
| View cashier list/details | Yes | Yes | No |
| Create, edit, activate, deactivate, or reset a cashier | Yes | Yes | No |
| View admin list/details | Yes | No | No |
| Create, edit, activate, deactivate, or reset an admin | Yes | No | No |
| Promote cashier to admin or demote admin to cashier | Yes | No | No |
| Create or promote an owner | No | No | No |
| View shop settings | Yes | Yes | No |
| Edit shop name | Yes | No | No |
| Edit currency or timezone | No | No | No |
| Future normal catalog/inventory management | Yes | Yes | No |
| Future sale and linked-return operations | Yes | Yes | Yes |
| Future completed-sale void | Yes | Yes | No |
| Future reports and audit-history pages | Yes | Yes | No |

Hiding a link is not authorization. Every protected view and mutation must repeat the role and
same-shop checks on the server.

## 5. Preconditions and shared rules

- Milestone 0 migrations and `bootstrap_pos` have created one active shop, `TILL-1`, and one
  active owner.
- All users belong to the single shop and have exactly one role: `OWNER`, `ADMIN`, or `CASHIER`.
- The current user's shop determines the scope of every account and settings query.
- An object identifier alone never grants access. An unauthorized or out-of-shop target is not
  revealed through a detail page, form, error message, or mutation response.
- Passwords use Django's configured password validation and password hashing.
- State-changing requests use POST and CSRF protection. Logout is also a POST action.
- Deactivation is used instead of deletion so future transaction history can retain user links.
- Timestamps are timezone-aware and displayed using `Asia/Karachi`.

## 6. Authentication flows

### 6.1 Login

1. An anonymous visitor opens the login page.
2. The form requests username and password only.
3. The server validates the credentials and confirms that the user is active.
4. On success, the previous session key is rotated and the user is redirected to the authenticated
   home page.
5. The page identifies the logged-in user, their role, and the shop name.

Rules and errors:

- Invalid credentials and inactive accounts receive the same generic error so account status is
  not disclosed.
- Password input is never echoed, logged, or preserved after a failed submission.
- An already authenticated user requesting the login page is redirected to the authenticated home
  page; the page is not a user-switch mechanism.
- A safe, local `next` destination may be honored after login. External or unauthorized redirect
  targets are rejected and the user is sent to the authenticated home page.
- A user deactivated during an existing session loses authenticated access on the next request.

### 6.2 Logout

1. The logged-in user selects Logout.
2. A CSRF-protected POST request ends the complete browser session.
3. The user is redirected to login and protected pages require authentication again.

Using the browser Back button after logout must not restore access to protected data.

### 6.3 Authenticated home

- All roles see the shop name, their display name/username, role, and logout action.
- Navigation contains only pages implemented and permitted in the current milestone.
- Owner sees user management and shop settings links.
- Admin sees cashier management and the read-only shop settings link.
- Cashier sees no management links until later cashier workflows exist.

## 7. User-management flows

### 7.1 User list

- Owner sees the owner account as a read-only row plus all admins and cashiers in the shop.
- Admin sees cashiers in the shop only.
- Each manageable row shows username, optional full name, role, active/inactive status, creator,
  and creation date.
- The page supports a simple username/name search and role/status filters. Empty filters show all
  users visible to the current role.
- Pagination is not required for the single-shop MVP; it can be added if real account counts make
  it necessary.
- Inactive accounts remain visible and can be reactivated by an authorized manager.

### 7.2 Create a user

1. The manager opens Create user.
2. Owner chooses `ADMIN` or `CASHIER`; admin receives a fixed `CASHIER` role.
3. The manager enters username, optional first and last name, password, and password confirmation.
4. The server validates the manager's permission, username uniqueness, password, role, and shop.
5. The account is created active in the manager's shop with `created_by` set to the manager.
6. A success message is shown and the manager returns to the user detail or list page.

Validation:

- Username is required after trimming and is unique case-insensitively.
- Username uses Django's normal username character validation and maximum length.
- Password and confirmation must match and pass all configured password validators.
- Password values are discarded after submission and never appear in success messages or audit
  records.
- A submitted shop ID or owner role is ignored/rejected; neither is selected by the browser.
- Validation failure creates no user and no audit event.

### 7.3 Edit identity or role

- An authorized manager can edit a subordinate user's username and optional first/last name.
- Only the owner can change a non-owner account between `ADMIN` and `CASHIER`.
- Admin receives no editable role field and cannot alter role by crafting a request.
- Shop, creator, password hash, last login, staff flags, and owner role are not editable here.
- A successful identity or role change returns a clear success message and records the relevant
  before/after values.
- Submitting unchanged values succeeds without creating a misleading change audit event.

### 7.4 Deactivate or reactivate

1. The authorized manager opens the target account.
2. The page clearly states the effect of deactivation and requests confirmation.
3. A POST action changes the active status and records the actor and transition.
4. Deactivation prevents new logins and invalidates the target's authenticated access on their
   next request.
5. Reactivation restores login eligibility but does not change the role or password.

Rules:

- Accounts are never deleted.
- No user can deactivate or reactivate themselves through user management.
- The owner cannot be deactivated through the application.
- An admin cannot target an owner or admin, including through a crafted URL or stale form.
- Repeating the same active-state request is safe and must not create duplicate change events.

### 7.5 Manager password reset

1. An authorized manager opens Reset password for a subordinate user.
2. The manager enters and confirms a new password.
3. The server rechecks target scope and permission, validates the new password, and replaces the
   password hash.
4. Existing sessions for the target user are invalidated.
5. The system records that a manager reset the password, but stores no password value or hash in
   the audit event.

Owner may reset an admin or cashier password. Admin may reset a cashier password only. The
bootstrap owner password can be changed only through the owner's own password-change form or an
explicit maintenance command outside normal shop workflow.

### 7.6 Change own password

1. The user enters their current password, new password, and confirmation.
2. The server verifies the current password and validates the new password.
3. On success, the password hash changes while the current session remains authenticated with a
   rotated session auth hash.
4. Other existing sessions for that user are invalidated.
5. A password-change audit event is recorded without password data.

Generic validation messages must not disclose password hashes or internal exceptions.

## 8. Shop settings flow

- Owner and admin can open a single-shop settings page.
- The page displays name, currency `PKR`, timezone `Asia/Karachi`, and active status.
- Owner can edit the shop name only. The name is required after trimming and cannot exceed the
  existing model limit.
- Admin sees the same page read-only.
- Cashier receives an authorization failure without learning a settings URL through navigation.
- Currency, timezone, shop identity, and active status cannot be changed by crafted form fields.
- A changed shop name is reflected in the header on subsequent responses and creates an audit
  event with old/new names.
- Submitting an unchanged name succeeds without a change audit event.

## 9. Audit requirements

Milestone 1 records focused, append-only audit events for:

- user account created;
- username or name changed;
- role changed;
- user activated or deactivated;
- manager password reset;
- user changed their own password; and
- shop name changed.

Each event records the shop, actor, action, target type/identifier, timestamp, and only the relevant
non-sensitive before/after values. Passwords, password hashes, session IDs, cookies, CSRF tokens,
and raw form submissions are never stored.

Audit events are created in the same successful transaction as the associated change. Failed,
unauthorized, unchanged, or rolled-back operations do not create business-change events. The audit
history page is deferred to Milestone 6; these events are retained now for later display.

Successful/failed login history, brute-force monitoring, IP intelligence, and a session-management
screen are excluded from the MVP. Normal application logs may record a generic authentication
failure without storing the submitted username or password.

## 10. Concurrency and edge cases

- Permissions are evaluated again when a form is submitted; seeing an earlier page does not
  preserve authority after the actor or target role changes.
- If two managers submit conflicting changes, each accepted mutation uses the current persisted
  target and creates an accurate before/after event. No form may silently overwrite protected role,
  shop, creator, or password fields.
- If an admin is demoted or deactivated while viewing a management page, their next request is
  denied according to the new state.
- A manager cannot use different username capitalization to create a confusing duplicate.
- Direct requests for another shop's user return the same not-found response as a nonexistent user.
- A database or audit-write failure rolls back the account or shop change and shows a recoverable
  error; partial changes are not reported as successful.
- An inactive target can be edited or password-reset by an authorized manager, but remains unable
  to log in until explicitly reactivated.
- Browser refresh after a successful POST does not repeat the mutation because all successful
  form submissions use redirect-after-POST.

## 11. Data effects

- Existing `User` records remain the source of authentication identity, role, shop, creator, and
  active status.
- Existing `Shop` records remain fixed to `PKR` and `Asia/Karachi`; only the name is mutable here.
- A case-insensitive username uniqueness rule is added without changing the displayed stored case.
- Milestone 1 introduces append-only account/shop audit records needed by later milestones.
- User deactivation and password changes invalidate affected sessions without deleting users or
  historical references.
- No catalog, inventory, order, payment, return, or document-sequence record is created.

## 12. Acceptance criteria

### Authentication

1. An active owner, admin, and cashier can log in with valid credentials.
2. Invalid credentials and inactive accounts cannot log in and receive a non-disclosing error.
3. Logout ends the session, and protected pages remain inaccessible after browser Back/refresh.
4. A deactivated user's existing session loses access on the next request.
5. External `next` URLs cannot be used for an open redirect.

### Authorization and user management

6. Owner can create and manage admins and cashiers, including permitted role changes.
7. Admin can create and manage cashiers only.
8. Cashier cannot view or mutate user management or shop settings through navigation or direct
   requests.
9. Admin cannot view or mutate an owner/admin account or promote a cashier, including through a
   crafted request.
10. No application flow can create, promote, demote, deactivate, or reset the password of the
    owner account.
11. Usernames cannot be duplicated by changing letter case.
12. Deactivation preserves the account and reactivation preserves its role and password.

### Passwords, settings, and audit

13. Own-password change requires the current password and keeps only the current session active.
14. Authorized password reset invalidates the target user's existing sessions and records no
    password material.
15. Only owner can change the shop name; `PKR` and `Asia/Karachi` cannot be changed through any
    submitted form.
16. Every successful material account/shop change creates exactly one accurate audit event in the
    same transaction.
17. Failed, unauthorized, and unchanged operations do not create change audit events.
18. All permission, form, session, audit, model-constraint, and view tests pass against PostgreSQL.

## 13. Manual acceptance scenarios for milestone completion

Automated tests are required, but the completed milestone should also be manually checked in a
real browser:

1. Log in and out once as owner, admin, and cashier; confirm identity, role, permitted navigation,
   and Back-button behavior.
2. As owner, create an admin and cashier, change a role, deactivate/reactivate an account, and
   reset a subordinate password.
3. As admin, manage a cashier and confirm owner/admin targets and role promotion are unavailable
   and rejected by direct requests.
4. As cashier, confirm user-management and shop-settings pages cannot be opened.
5. Change each role's own password and confirm the old password stops working.
6. Change the shop name as owner, confirm it appears in the application header, and confirm admin
   sees `PKR` and `Asia/Karachi` as read-only.
7. Disconnect internet access and repeat login, navigation, and logout to confirm no external
   runtime dependency.

The exact runnable setup and expected result for each scenario will be provided again when
Milestone 1 implementation is finished.

## 14. Explicit exclusions

- Creating or managing another owner.
- Email address workflows, invitations, email delivery, and emailed password reset.
- Password recovery questions, forced expiry, forced first-login change, two-factor
  authentication, and login throttling/lockout.
- User deletion, bulk import/export, employee scheduling, shifts, and cashier till assignment.
- Editing currency, timezone, tax, terminal configuration, or shop active status.
- A user-visible audit history page; this belongs to Milestone 6.
- Product, inventory, checkout, order, payment, void, return, report, and backup workflows.
- Django admin as an operational shop interface.
- Multi-shop switching or cross-shop management.

## 15. Review gate

This feature specification must be reviewed before creating `docs/milestones/m1-users/technical-design.md`. After the
feature behavior is approved, the next document will define models/migrations, session
invalidation, permission services, forms, views, URLs, templates, audit writes, and the automated
test matrix. Development tasks will be created only after that technical refinement is approved.
