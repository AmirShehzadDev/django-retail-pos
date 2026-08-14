# Milestone 7.1 Completion Evidence - Local Startup and Deployment Hardening

**Implementation status:** Complete on 2026-08-14  
**Milestone acceptance:** Pending user-owned Windows checks and the versioned `1.0.1` package  
**Planning:** Feature specification, technical design, and development tasks in this folder

## Implemented

- New installations allow the friendly `http://retailpos:8000` address while the application
  remains bound to `127.0.0.1`.
- An idempotent elevated Windows setup script adds the local hosts entry, updates only the required
  existing `.env` settings, flushes DNS, installs a desktop launcher, and safely refreshes a running
  web container.
- The desktop launcher starts Docker Desktop when required, waits for readiness, starts the POS
  through its permanent lifecycle script, and opens Chrome or the default browser.
- Deployment preflight rejects `$` in `.env` values and identifies only affected setting names.
- Database-container discovery filters warning output and accepts exactly one hexadecimal container
  identifier, preventing warning text from reaching `docker cp`.
- Initial-install, existing-update, shop-operation, troubleshooting, and pilot documentation now
  covers the hostname, launcher, unsafe-secret repair, and backup verification workflow.

## Automated evidence

Verification ran from the Windows development host without changing the active `C:\RetailPOS`
containers or database. The full Django suite used an isolated temporary PostgreSQL 16.14 container
and network, both removed after the run.

- PowerShell parser: all deployment `.ps1` and `.psm1` files passed.
- `docker compose --env-file .env.example config --quiet`: passed.
- Ruff check and format check: passed; 190 files formatted.
- Focused deployment/documentation suite: 8 tests passed.
- Full Django regression suite: 351 tests passed in 157.521 seconds.
- JavaScript suite: 16 tests passed.
- Tailwind CSS production build: passed.
- `makemigrations --check --dry-run`: no model changes detected.
- `python manage.py check`: no issues.
- `python -m pip check`: no broken requirements.
- `git diff --check`: passed before completion evidence was recorded.

## Required manual checks

These checks require the real Windows account, administrator prompt, hosts file, Desktop, Docker
Desktop, Chrome, and installed POS. Automated tests do not claim them.

1. Correct any existing `.env` secret containing `$` before installing the update. For the known
   `$npid` value, remove only that exact text and do not share the complete secret.
2. Install the checked `1.0.1` update into the existing `C:\RetailPOS` installation and confirm its
   existing `COMPOSE_PROJECT_NAME` and database data are retained.
3. Run `.\deploy\Configure-LocalHostname.ps1`, approve elevation, and confirm it reports
   `http://retailpos:8000` plus the installed desktop launcher.
4. Run the setup script a second time; confirm it succeeds without duplicate hosts or `.env`
   entries.
5. With Docker Desktop stopped, double-click **Start Retail POS.cmd** and confirm Docker starts,
   the POS becomes healthy, and Chrome opens `http://retailpos:8000` within three minutes.
6. Close Chrome but leave Docker running; double-click again and confirm the POS opens promptly.
7. Restart Windows, sign in, use the launcher, and confirm the same address works without internet.
8. Run `.\deploy\Backup-Database.ps1 -Purpose post-1.0.1` and confirm it creates and validates a
   non-empty dump without an `npid` warning or `docker cp` error.
9. Confirm another computer cannot reach the POS; this refinement must remain loopback-only.

The milestone remains **pending user verification** until every applicable item passes. The
checked `1.0.1` release can be built only after the intended changes are committed with user
approval; the existing `1.0.0` package must remain unchanged.
