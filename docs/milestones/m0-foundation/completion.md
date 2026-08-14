# Milestone 0 - Completion Evidence

**Status:** Complete

**Verified:** 2026-08-03

**Platform:** Windows 11, Python 3.13.14, Docker Desktop 29.6.1 / Compose 5.2.0

## Delivered

- Django 5.2.16 modular project with split development and production settings.
- PostgreSQL-only configuration using `postgres:16.14-alpine` on localhost port `5433`.
- Foundation `Shop`, `Terminal`, and custom `accounts.User` models and initial migrations.
- Idempotent `bootstrap_pos` command for one shop, `TILL-1`, and the first owner.
- Local Django template, CSS, and JavaScript with no external runtime assets.
- PostgreSQL-backed tests, Ruff checks, environment validation, WhiteNoise, and Waitress.
- Reproducible Windows setup, verification, troubleshooting, and safe database reset guidance.

## Verification results

| Check | Result |
|---|---|
| Dependency installation from pinned requirements | Passed |
| `python -m django --version` | `5.2.16` |
| `python -m pip check` | Passed; no broken requirements |
| Docker database health | Passed; `pos_codex-db-1` healthy |
| PostgreSQL image | `postgres:16.14-alpine` |
| `python manage.py migrate` on the new project database | Passed |
| `python manage.py makemigrations --check --dry-run` | Passed; no changes |
| PostgreSQL test database create/destroy | Passed |
| `python manage.py test` | Passed; 22 tests |
| `ruff check .` | Passed |
| `ruff format --check .` | Passed; 46 files formatted |
| `python manage.py check` | Passed; no issues |
| `python manage.py collectstatic --noinput` | Passed; 129 files copied |
| Development server home/CSS/JavaScript requests | HTTP 200 |
| Waitress production-style home and health requests | HTTP 200 |
| External URL scan of rendered home page | Passed; none found |
| Bootstrap clean run and repeat run | Passed; no duplicates or password reset |

The production deployment check has four expected warnings in the documented localhost HTTP
configuration: HSTS, HTTPS redirect, secure session cookies, and secure CSRF cookies. HTTPS
protections are deferred until deployment scope requires TLS; none are silently disabled for an
internet-facing deployment.

## Exit criteria

- A fresh database can be migrated and bootstrapped.
- The custom user model exists in the initial project migration history.
- The application starts through both Django's development server and Waitress.
- The rendered page and authored assets contain no external runtime dependency.
- All automated checks pass against PostgreSQL.
- Local secrets, the virtual environment, logs, collected static files, and database data are
  excluded from Git.

Milestone 0 contains no catalog, inventory, order, payment, return, or reporting functionality.
