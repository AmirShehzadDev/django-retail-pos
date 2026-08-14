# Milestone 1 - Completion Evidence

**Status:** Complete

**Verified:** 2026-08-03

**Manual acceptance:** Confirmed by the user on 2026-08-03

**Platform:** Windows 11, Python 3.13.14, Node 22.22.3, npm 10.9.8, Dockerized
PostgreSQL 16.14

## 1. Delivered

- Case-insensitive login and username uniqueness.
- Owner/admin/cashier authorization with same-shop enforcement.
- Owner management of admins/cashiers and admin management of cashiers only.
- User creation, identity/role editing, activation/deactivation, and password reset.
- Authenticated home, own-password change, POST logout, and browser-session expiry.
- Owner-editable and admin-readable shop settings with fixed PKR/Karachi values.
- Transactional, focused account/shop audit events with sensitive-payload rejection.
- Production Django-admin boundary.
- Tailwind CSS 4.3.3 templates compiled and served entirely from local files.

## 2. Automated evidence

| Check | Result |
|---|---|
| Docker PostgreSQL | Healthy on `127.0.0.1:5433` |
| Migrations | `accounts.0002` and `core.0002` applied successfully |
| Migration drift | No changes detected |
| Bootstrap repeat | No changes or duplicate records |
| Full PostgreSQL suite | 82 tests passed |
| Ruff lint | Passed |
| Ruff format check | 66 files formatted |
| Django development check | Passed with no issues |
| Python dependency check | No broken requirements |
| `npm ci` | Passed; 0 vulnerabilities |
| Tailwind build | Passed twice with identical output |
| Compiled CSS SHA-256 | `D84883EDAFF46B6C499274503E3F3968BD9CBDEF1AA12EFB2924580A36272C27` |
| `collectstatic` | Passed; generated assets available locally |
| Development login/CSS/health smoke | HTTP 200 / 200 / 200 |
| Waitress login/CSS/health smoke | HTTP 200 / 200 / 200 |
| Production `/admin/` | HTTP 404 |
| External URLs in rendered login | None |

The production deployment check reports the same four expected localhost-HTTP warnings recorded
in Milestone 0: HSTS, HTTPS redirect, secure session cookie, and secure CSRF cookie. The shop is not
being exposed to an untrusted network in this milestone.

## 3. Automated acceptance coverage

- All active roles can authenticate; invalid/inactive credentials remain non-disclosing.
- Logout, safe redirects, no-store caching, deactivation, password reset, and multiple-session
  behavior pass.
- The complete owner/admin/cashier policy matrix and cross-shop denial pass.
- Crafted fields cannot change owner/shop/staff/superuser/currency/timezone data.
- Account and shop mutations are atomic with accurate focused audit events.
- Failed, unchanged, unauthorized, repeated, and rolled-back operations create no false audit
  event.
- Password material is absent from audit payloads.
- Local Tailwind pages render without a CDN or JavaScript dependency.

## 4. Required manual browser acceptance

The user confirmed that the required interface and offline behavior checks passed. The checklist is
retained below as the acceptance record for future regression checks.

### Setup

```powershell
docker compose up -d db
.\.venv\Scripts\Activate.ps1
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
```

If the development owner password is unknown, set one interactively before starting:

```powershell
python manage.py changepassword owner
```

### Checklist

1. Open `http://127.0.0.1:8000/accounts/login/`. Confirm the page is styled, keyboard-usable, and
   contains no visibly missing fonts, icons, or assets.
2. Log in as owner. Confirm the header shows the correct shop, user, and role. Create one temporary
   admin and cashier; edit their names, promote/demote a non-owner, and reset a subordinate
   password. Confirm the owner row has no edit, reset, or deactivate actions.
3. Deactivate the temporary cashier and confirm login fails; reactivate them and confirm the same
   password works. Keep test accounts for history or deactivate them afterward; do not delete
   database rows.
4. Log in as the temporary admin. Confirm only cashiers are listed/manageable, shop settings are
   read-only, and direct visits to the owner detail and another admin detail return Not Found.
5. Log in as cashier. Confirm no Users or Shop settings navigation appears; direct visits to
   `/accounts/users/` and `/settings/shop/` are denied. Confirm own-password change works.
6. Log out and use the browser Back button, then refresh. Confirm protected content is not usable
   and the application returns to login. Optionally repeat a manager reset while the target is open
   in a private browser and confirm the target session ends on its next request.
7. Disconnect the computer from the internet while leaving Docker/application running. Repeat
   login, home, user list, settings, password change, and logout. Confirm styling and behavior remain
   intact with no external request failures.

Record pass/fail notes for each step. Any failed required check keeps Milestone 1 open.

## 5. Completion decision

The implementation, automated verification, and user-confirmed manual acceptance gates pass.
Milestone 1 is complete and Milestone 2 feature planning may begin.
