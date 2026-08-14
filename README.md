# Offline Retail POS

Offline Retail POS is a self-hosted, single-shop point-of-sale application designed to keep
operating without an internet connection after installation. It uses Django server-rendered
templates, PostgreSQL, Tailwind CSS, and a versioned Docker/Gunicorn deployment for Windows shop
computers.

> **Project status:** The MVP implementation and automated test suite are complete. Physical
> scanner acceptance, deployment recovery checks, and a supervised real-shop pilot should be
> completed before live use. This application is designed for localhost or a trusted private shop
> network, not the public internet.

## Key features

- Owner, admin, and cashier roles with controlled user management.
- Barcode scanning, product search, restricted cashier quick-create, and scanner-first keyboard
  checkout.
- Up to three persistent active order tabs per checkout terminal.
- Cash checkout with captured prices, signed change, stock deduction, and recent-sale feedback.
- Unified Products & Stock workspace with receipts, adjustments, negative-stock visibility, and an
  immutable inventory movement ledger.
- Searchable completed-order history with partial/full returns and manager-only voids.
- Daily cash and sales summaries plus filtered operational audit history.
- Versioned offline Docker releases, verified pre-update backups, rollback tooling, and daily backup
  retention.

## Deliberate MVP scope

This is a focused POS for one retail or grocery shop:

- Currency is PKR and the business timezone is Asia/Karachi.
- Payments are cash-only.
- Products are sold by whole quantity, not by weight.
- Taxes, receipt printing, discounts, customer accounts, suppliers, purchase orders, and cloud
  synchronization are not included.
- A terminal may keep at most three active orders.
- Negative stock is permitted but remains visible and auditable.
- Cash received may be above or below the order total; signed change is recorded as
  `cash received - order total`.
- The installed runtime works without internet, but a development machine may need internet access
  to download dependencies and base images when building a release.

## Architecture

- **Application:** Django 5.2 LTS modular monolith with server-rendered templates and minimal local
  JavaScript.
- **Database:** PostgreSQL 16 with transactional stock balances, immutable movement history, and row
  locking for checkout and inventory updates.
- **Frontend:** Tailwind CSS compiled locally; no CDN, web font, analytics, or runtime framework.
- **Shop runtime:** Linux Gunicorn/Django and PostgreSQL containers managed by Docker Compose on a
  Windows 11 host.
- **Offline model:** The host computer is the local server. Additional checkout computers may use a
  trusted private LAN, but there is no offline synchronization when the host is unavailable.

## Development requirements

- Windows 11 and PowerShell
- Python 3.13
- Docker Desktop with Docker Compose
- Node.js 22 and npm 10 for compiling Tailwind CSS

The default development database port is `127.0.0.1:5433` and can be changed in `.env`.

## Development setup

```powershell
git clone https://github.com/AmirShehzadDev/offline-retail-pos.git
Set-Location offline-retail-pos
Copy-Item .env.example .env
notepad .env
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements\development.txt
npm ci
npm run css:build
docker compose up -d db
python manage.py migrate
python manage.py bootstrap_pos
python manage.py runserver 127.0.0.1:8000
```

Replace every `replace-...` value in `.env` before starting. `bootstrap_pos` prompts for the first
owner account and does not store a default owner password. Open
`http://127.0.0.1:8000/accounts/login/` after initialization.

`COMPOSE_PROJECT_NAME` is the stable identity of an installation's containers and database volume.
Use a distinct value and unused ports for every separate development, test, or shop installation,
and never change that value during an update.

## Verification

Start the development database before running the Django suite:

```powershell
docker compose up -d db
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test --noinput
ruff check .
ruff format --check .
python -m pip check
node --check static/js/app.js
node --check static/js/pos.js
node --check static/js/products.js
node --check static/js/order_corrections.js
node --test static/js/*.test.js
npm run css:build
python manage.py collectstatic --noinput
```

`python manage.py reconcile_inventory` is a read-only operational check. It compares displayed
product balances with the sum of immutable inventory movements and fails on a discrepancy; it never
creates an automatic correction.

## Shop deployment and updates

The shop computer runs only locally bundled Docker images and static assets. Build a checked,
versioned package on the development computer:

```powershell
.\deploy\Build-Release.ps1 -Version 1.0.0
```

Follow the exact install, update, backup, restore, and rollback procedures in the
[deployment and recovery runbook](deploy/README.md). An update verifies the packaged image, creates
a pre-update database backup, migrates the existing database once, starts the new application, and
checks health.

Never use `docker compose down --volumes` on a shop installation. It permanently deletes the named
database volume.

## Security boundary

The default application and database ports bind to localhost. Local HTTP is an explicit MVP choice
for one trusted Windows host. Before enabling access from another computer, review allowed hosts,
CSRF origins, local firewall rules, authentication, and HTTPS requirements. Do not expose this
configuration directly to the public internet.

Never commit `.env`, database dumps, backups, logs, release archives, or shop/customer data. See
[SECURITY.md](SECURITY.md) for vulnerability reporting and deployment guidance.

## Documentation

The [documentation index](docs/README.md) links to requirements, architecture, milestone records,
deployment procedures, shop operations, and manual acceptance checklists. Contributors should also
read [CONTRIBUTING.md](CONTRIBUTING.md) and the repository's [AGENTS.md](AGENTS.md) workflow.

## License

This project is licensed under the [MIT License](LICENSE).
