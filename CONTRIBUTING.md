# Contributing

Thank you for considering a contribution to Offline Retail POS.

## Before changing code

- Read [README.md](README.md), [AGENTS.md](AGENTS.md), and the relevant requirement/design records in
  the [documentation index](docs/README.md).
- Open or discuss an issue before a large feature, schema change, security-boundary change, or
  deployment change.
- Keep the single-shop, offline-runtime, PKR, cash-only MVP scope explicit unless a change has an
  approved specification.

## Development

Use Python 3.13, PostgreSQL 16, Node.js 22, and the exact-pinned dependencies in the repository.
Create `.env` from `.env.example`; never commit the resulting local file.

When templates use new Tailwind classes, rebuild and commit `static/css/app.css`:

```powershell
npm ci
npm run css:build
```

## Verification

Before submitting a pull request, run:

```powershell
docker compose up -d db
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test --noinput
ruff check .
ruff format --check .
python -m pip check
node --test static/js/*.test.js
npm run css:build
git diff --check
```

Automated tests must cover money, inventory, permission, transaction, and concurrency behavior.
Template/JavaScript assertions do not replace user-owned browser, scanner, focus, responsive, or
offline acceptance checks.

## Pull requests

- Keep changes focused and commit messages short.
- Explain user-visible behavior, data effects, migrations, security implications, and verification.
- Include a manual checklist when hardware or browser interaction is relevant.
- Use invented data in tests and screenshots.
- Do not include `.env`, backups, logs, release archives, generated shop data, or credentials.
