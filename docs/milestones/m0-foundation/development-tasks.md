# Milestone 0 - Development Tasks

**Status:** Implemented and verified
**Version:** 1.1  
**Milestone:** Technical foundation  
**Inputs:** `docs/product/mvp-requirements.md` v1.3, `docs/product/roadmap.md` v1.2, `docs/architecture/technical-design.md` v0.3

## 1. Milestone objective

Create a reproducible Django/PostgreSQL foundation on Windows using Docker for PostgreSQL. At completion, a fresh developer installation can start the pinned database container, run the initial migrations, create the single shop/terminal/owner, start the application without internet-hosted assets, and run the automated checks.

This milestone establishes structure and infrastructure only. It does not implement functional POS workflows.

## 2. Task order

| ID | Task | Depends on |
|---|---|---|
| M0-01 | Establish repository baseline | None |
| M0-02 | Define and pin dependencies | M0-01 |
| M0-03 | Scaffold Django project and apps | M0-02 |
| M0-04 | Implement settings and environment configuration | M0-03 |
| M0-05 | Create foundational models before first migration | M0-04 |
| M0-06 | Configure PostgreSQL and create initial migrations | M0-05 |
| M0-07 | Create the installation/bootstrap command | M0-06 |
| M0-08 | Add the base template and local static assets | M0-06 |
| M0-09 | Establish automated tests and code-quality checks | M0-07, M0-08 |
| M0-10 | Write clean-install and development documentation | M0-09 |
| M0-11 | Run the Milestone 0 verification gate | M0-10 |

## 3. Detailed tasks

### M0-01 - Establish repository baseline

**Purpose:** Make the folder safe for source-controlled Django development.

#### Work

- Initialize Git if the project is not already a repository.
- Preserve the approved Markdown documents at the repository root.
- Add a Python/Windows `.gitignore` covering virtual environments, Python caches, environment files, IDE files, logs, collected static files, local uploads, database dumps, and backup directories.
- Add a concise root `README.md` with the project purpose and links to the requirements, milestones, technical design, and this task plan.
- Choose and document UTF-8 and LF as the repository text-file convention; Windows scripts may use the platform-appropriate format.

#### Acceptance criteria

- `git status` shows only intentional project files.
- A sample local environment file, log, and backup filename are ignored.
- No approved planning document is removed or renamed.
- The README links resolve to all planning documents.

### M0-02 - Define and pin dependencies

**Purpose:** Create a reproducible Python environment without introducing unnecessary packages.

#### Work

- Confirm an installed Python version supported by the chosen Django 5.2 patch.
- Create a project virtual environment at `.venv`.
- At implementation time, verify and exact-pin the latest available Django `5.2.x` patch.
- Add exact production dependencies for PostgreSQL, Waitress, local static-file serving, and environment-file loading.
- Add a small development dependency file containing only the chosen linter/formatter and any test-only dependency that is genuinely required.
- Use Django's built-in test runner unless a later requirement justifies another test framework.
- Ensure every runtime dependency can be packaged locally for offline installation in Milestone 7.

#### Acceptance criteria

- A clean virtual environment installs successfully from the requirement files.
- `python -m django --version` reports the pinned Django 5.2 patch.
- `python -m pip check` passes.
- Requirements contain exact versions and no unused frontend framework or CDN package.

### M0-03 - Scaffold Django project and apps

**Purpose:** Create the modular monolith structure approved in the technical design.

#### Work

- Scaffold `manage.py` and the `config` project package.
- Create `config/settings/base.py`, `development.py`, and `production.py`.
- Create the `apps` Python package and empty Django apps: `core`, `accounts`, `catalog`, `inventory`, and `sales`.
- Create root `templates`, `static/css`, `static/js`, and `tests` directories.
- Register apps using their explicit `AppConfig` paths.
- Create the root URL configuration and a minimal health/home route.
- Do **not** run the first migration yet; `AUTH_USER_MODEL` must be configured first.

#### Acceptance criteria

- Django imports every app without an application-registry error.
- URL resolution reaches the minimal health/home route.
- No product, inventory, order, payment, return, or reporting feature is implemented.
- No migration has been applied before M0-05 is complete.

### M0-04 - Implement settings and environment configuration

**Purpose:** Separate safe defaults from machine-specific and production configuration.

#### Work

- Put shared apps, middleware, templates, timezone behaviour, static configuration, and primary-key defaults in `base.py`.
- Configure `Asia/Karachi`, timezone-aware timestamps, and PKR project constants without adding tax settings.
- Configure the Dockerized PostgreSQL connection entirely from environment variables; do not provide a silent SQLite fallback.
- Add an ignored local `.env` and a committed `.env.example` containing non-secret variable names and safe examples.
- Configure `DEBUG`, `SECRET_KEY`, database credentials, allowed hosts, CSRF origins, static destination, log directory, and terminal bootstrap defaults by environment.
- Make production settings fail clearly when required secrets/configuration are missing.
- Configure WhiteNoise/local static serving and Waitress-compatible WSGI behaviour without external assets.
- Add rotating local application logging without request passwords, secrets, or sensitive form values.

#### Acceptance criteria

- Development settings load from a local environment without secrets in source control.
- Production settings have `DEBUG=False` and reject missing required values.
- The configured database engine is PostgreSQL in development, production, and tests.
- `Asia/Karachi`, timezone-aware operation, PKR, and local static settings are verifiable through Django settings.

### M0-05 - Create foundational models before first migration

**Purpose:** Establish identity and shop/terminal boundaries that later models will depend on.

#### Work

- Create `Shop` with name, fixed MVP currency/timezone values, active flag, and timestamps.
- Create `Terminal` with shop, shop-unique code, display name, active flag, and timestamps.
- Create the custom `User` by extending Django `AbstractUser`.
- Add the user's shop, fixed role choices (`OWNER`, `ADMIN`, `CASHIER`), creator reference, and standard activation behaviour.
- Configure `AUTH_USER_MODEL` before generating any migrations.
- Add database constraints for shop-unique terminal codes and valid fixed choices where appropriate.
- Register only foundation models in Django admin for development inspection; later critical transaction models will not be editable there.
- Deactivation, not deletion, is the expected lifecycle for users, shops, and terminals referenced by future history.

#### Acceptance criteria

- `AUTH_USER_MODEL` resolves to the custom user model.
- The initial migration history has never referenced Django's default concrete user model.
- Model validation and database constraints reject duplicate terminal codes within one shop.
- The three role values exist, but role-management screens are not implemented.
- No speculative product, audit, sequence, order, or return model is created in this milestone.

### M0-06 - Configure Docker PostgreSQL and create initial migrations

**Purpose:** Prove the real target database works from the beginning.

#### Work

- Add `compose.yaml` using a pinned official PostgreSQL image, a named data volume, localhost-only port binding, and a health check.
- Use a dedicated development/test database role with `CREATEDB` so Django can create its PostgreSQL test database. Keep the future shop runtime role restricted; it will not reuse credentials from another local application.
- Document container start, stop, status, and safe volume-reset commands.
- Create and review initial migrations for `core` and `accounts` after the custom user is configured.
- Apply all Django and project migrations to a clean PostgreSQL container database.
- Verify Django can create and destroy a separate PostgreSQL test database.
- Verify migration generation reports no unexpected model changes after a clean apply.

#### Acceptance criteria

- `python manage.py migrate` succeeds on an empty PostgreSQL database.
- `python manage.py makemigrations --check --dry-run` reports no changes.
- Django's test runner can create and destroy the PostgreSQL test database.
- No SQLite database file exists or is referenced by settings.

### M0-07 - Create the installation/bootstrap command

**Purpose:** Provide a safe, repeatable way to create the first operational records.

#### Work

- Add an interactive management command such as `bootstrap_pos`.
- Create the single shop using PKR and `Asia/Karachi`.
- Create terminal `TILL-1` for the initial checkout computer.
- Create the first owner using an interactively supplied username/password; never put a default production password in code or documentation.
- Make the command idempotent: rerunning it must not duplicate the shop, terminal, or owner.
- Refuse ambiguous existing data and provide a clear corrective message instead of guessing.

#### Acceptance criteria

- The command creates exactly one initial shop, terminal, and owner on a clean database.
- The password is hashed by Django and is not echoed into logs.
- A second run makes no duplicates and reports the existing setup clearly.
- Automated command tests cover clean setup, repeat execution, and conflicting data.

### M0-08 - Add the base template and local static assets

**Purpose:** Establish the server-rendered frontend shell without implementing feature screens.

#### Work

- Add `templates/base.html` with semantic page structure, title blocks, messages, and content blocks.
- Add a minimal locally authored CSS foundation suitable for a checkout computer.
- Add an empty/minimal local JavaScript entry point with deferred loading.
- Add a simple home/health template showing that the local application is operational.
- Add navigation placeholders only for implemented pages; do not add dead links for future POS features.
- Ensure no font, stylesheet, script, icon, telemetry, or image is requested from the internet.

#### Acceptance criteria

- The home page renders through a Django template.
- Browser developer tools show no external runtime requests.
- `collectstatic` succeeds.
- The page remains usable when the computer is disconnected from the internet.

### M0-09 - Establish automated tests and code-quality checks

**Purpose:** Make every later milestone start with a working verification loop.

#### Work

- Configure the test suite to use PostgreSQL and Django's built-in test runner.
- Add smoke tests for settings, URL routing, template rendering, and local static references.
- Add model tests for Shop, Terminal, custom User, role values, and terminal uniqueness.
- Add bootstrap-command tests.
- Add a production-settings validation test for required configuration.
- Configure one lightweight Python linter/formatter and exclude generated migrations only where appropriate.
- Document standard local commands for checks, migrations, tests, and formatting.

#### Acceptance criteria

- The complete test suite passes against PostgreSQL.
- The linter/formatter check passes.
- `python manage.py check` passes in development settings.
- `python manage.py check --deploy` is reviewed under production settings; unavoidable local-HTTP warnings are documented rather than silently ignored.

### M0-10 - Write clean-install and development documentation

**Purpose:** Ensure the foundation can be reproduced without relying on the original developer's machine state.

#### Work

- Document supported Python, Docker, and PostgreSQL image versions actually used.
- Document Windows commands for virtual-environment creation and activation.
- Document dependency installation, environment configuration, Docker PostgreSQL startup, migrations, bootstrap, application startup, tests, and static collection.
- Document development startup separately from the Waitress production-style smoke command.
- Document that the runtime is internet-independent after dependencies are installed.
- Add a short troubleshooting section for database connection, missing variables, migrations, static files, and occupied ports.

#### Acceptance criteria

- A reader can follow the README from an empty database to a running local home page.
- Every documented command has been executed successfully on Windows or is explicitly marked for a later deployment milestone.
- Documentation contains no real password, secret, machine-specific absolute path, or database dump.

### M0-11 - Run the Milestone 0 verification gate

**Purpose:** Produce evidence that the milestone exit criteria are satisfied before feature development starts.

#### Work

- Recreate the virtual environment from pinned requirements.
- Create or reset a dedicated clean test database using safe, explicitly named development resources.
- Apply migrations and run `bootstrap_pos`.
- Run framework checks, migration checks, lint/format checks, automated tests, and `collectstatic`.
- Start the application through the documented development command and the Waitress production-style smoke command.
- Open the home page with internet disconnected and confirm there are no external requests.
- Review the repository for committed secrets, dumps, logs, virtual environments, and generated static output.
- Record command results in the milestone completion note or pull-request description.

#### Acceptance criteria

- A clean setup can migrate, bootstrap, start, and render successfully.
- All automated checks pass.
- No page requires a CDN or internet-hosted asset.
- The custom user model was present before the first project migration.
- The repository contains no secret or local runtime artifact.
- The Milestone 0 exit criteria in `docs/product/roadmap.md` are satisfied with recorded evidence.

## 4. Explicitly excluded from Milestone 0

- Custom login/logout and user-management screens; these belong to Milestone 1.
- `AuditEvent`, product, inventory, order, payment, void, and return models.
- Barcode input, held-order UI, checkout, round-offs, and negative-stock workflows.
- Reports, audit-history UI, and order filters.
- Windows automatic service installation and scheduled backups; these belong to Milestone 7.
- LAN terminal registration UI and multi-computer enablement.
- Feature specifications and development tasks for later milestones.

## 5. Completion rule

Milestone 0 is complete only after M0-01 through M0-11 meet their acceptance criteria. Passing on the original developer machine alone is insufficient; the documented clean-install path must also be exercised using a clean virtual environment and database.
