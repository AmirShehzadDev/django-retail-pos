# Milestone 7 Technical Design - Offline Deployment and Shop Pilot

**Status:** Implemented  
**Version:** 1.0  
**Feature specification:** `docs/milestones/m7-offline-deployment/feature-spec.md`

## 1. Architecture

```text
USB scanner -> Windows browser -> 127.0.0.1:8000
                                      |
                         Docker Compose application network
                                      |
                    Gunicorn/Django/WhiteNoise -> PostgreSQL
                              |                       |
                        host log bind mount     named data volume

Windows scheduled task -> Backup-Database.ps1 -> host backup directory
Remote operator/USB     -> release package     -> Install-Update.ps1
```

Gunicorn is a Unix server, so it runs inside the Linux application container rather than directly
on Windows. PostgreSQL is reachable from the application as `db:5432` only. Its optional host port
remains bound to `127.0.0.1` for development/maintenance and is never a LAN port.

## 2. Container image

Add a root `Dockerfile` with these stages:

1. `assets`: pinned Node 22 Alpine family, `npm ci`, and the existing Tailwind build. The build
   context includes `templates/`, `apps/`, and `static/js/` before Tailwind runs so every configured
   `@source` path contributes its utility classes to the packaged CSS.
2. `runtime`: pinned Python 3.13 slim family, exact `requirements/base.txt`, non-root `pos` user,
   application source, built CSS, and production `collectstatic`.

The runtime image contains no Node/npm cache, source control metadata, `.env`, backups, local logs,
or database data. It sets production settings, exposes port 8000, and starts:

The Dockerfile uses only the engine's built-in Dockerfile syntax so repeat builds can use already
cached base images without resolving an optional external frontend. A first build still requires
the pinned Python and Node base images to have been downloaded.

```text
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2 --threads 4
```

Gunicorn logs to stdout/stderr. A conservative timeout and max-request recycling are configured in
`docker/gunicorn.conf.py`. Application file logging continues in the mounted log directory.
Gunicorn is exact-pinned; Waitress is removed.

## 3. Compose design

`compose.yaml` contains:

- `db`: existing exact PostgreSQL image, named data volume, init script, localhost-only maintenance
  port, health check, and `unless-stopped` restart;
- `web`: `${POS_APP_IMAGE}:${POS_APP_VERSION}`, optional local build definition, production settings,
  `.env`, explicit database host/port override, localhost app-port binding, log bind mount, a
  dependency on healthy `db`, application health check, and `unless-stopped` restart.

The selected version lives in `.env` as `POS_APP_VERSION`; scripts update only this key while
preserving all other lines. `POS_APP_IMAGE` defaults to `pos-codex`. The default app bind host is
`127.0.0.1` and may later be explicitly changed to a private LAN address.

The top-level Compose name resolves from `${COMPOSE_PROJECT_NAME:-pos_codex}`. The value belongs to
the installation, is stored in the untracked persistent `.env`, and remains stable across updates.
Separate development, test, and shop installations on one Docker host require unique project names
and non-conflicting host ports. Release packages never contain `.env`, so copying updated runtime
files preserves an installation that follows this identity contract.

Milestone 7.1 adds the friendly single-computer alias `retailpos` without changing the loopback bind.
New configurations include the host/origin from the start; an idempotent elevated Windows setup
script updates existing configurations and the hosts file. Deployment preflight rejects dollar
signs in `.env` values before Compose interpolation, and database-container discovery filters
native output for a valid hexadecimal ID instead of trusting the first output line.

Compose does not run migrations automatically on every container start. Install/update/restore
scripts invoke `python manage.py migrate --noinput` as a one-off web container after database health.

## 4. Health and version

`GET /health/` remains public and discloses no configuration. It executes `SELECT 1` against the
default database and returns:

```json
{"status": "ok", "version": "1.0.0"}
```

Database failure returns HTTP 503 with `{"status": "unavailable"}`. The version comes from
`POS_APP_VERSION`, defaults to `development`, and is validated as a display-only string. Docker
uses Python's standard-library HTTP client for the health check, avoiding curl as an image
dependency.

## 5. Deployment scripts

All scripts live under `deploy/` and use strict PowerShell error behavior, checked native exit
codes, literal paths, and repository-root discovery based on `$PSScriptRoot`.

### Shared module

`deploy/PosDeployment.psm1` provides:

- Docker/Compose command invocation with exit checking;
- strict release version validation (`[A-Za-z0-9][A-Za-z0-9._-]{0,63}`);
- `.env` lookup and single-key update without logging secret values;
- Compose database-container discovery;
- safe resolved directory validation;
- health polling with bounded timeout; and
- deployment-state read/write under `var/deployment/`.

### Build-Release.ps1

Input: mandatory `-Version`, optional output directory.

1. Run CSS build, Python tests, JavaScript tests, Ruff, migrations check, and production deployment
   checks through the supported local toolchain.
2. Build `pos-codex:<version>` with OCI version/revision labels.
3. Save the image as `pos-codex-<version>.tar`.
4. Calculate SHA-256 and create `release.json` with schema version, app version, image reference,
   image filename, checksum, Git commit, and build timestamp.
5. Copy the runtime Compose file and deployment scripts/runbooks needed on the shop host into the
   release directory, then create a zip for transfer.

The first implementation may offer `-SkipChecks` only for local troubleshooting; release/pilot
evidence must use checks.

### Install-POS.ps1

Input: release directory; optional backup schedule switch.

- Validate `.env`, release, checksum, Docker, and Compose.
- Load the image and select its version.
- Start `db`, run migrations, start `web`, poll health, and persist current version.
- On a new database, initialization remains a separate documented owner-creation command so no
  password is accepted or stored by the install script.
- Optionally install the Windows backup task after a successful start.

### Install-Update.ps1

Input: release directory.

- Validate and load package; no-op when already current.
- Record prior version and take `pre-update` backup.
- Stop web, select new version, migrate, start, and poll health.
- Persist previous/current version and retained backup on success.
- On failure after selection, restore the previous version key. If migrations were attempted, the
  error directs the operator to the exact restore/rollback command using the pre-update backup;
  automatic destructive restore is deliberately avoided.

### Backup-Database.ps1

- Default target: `var/backups` or configured `POS_BACKUP_DIR`.
- Generate a custom-format dump inside the DB container, validate it there, copy it to a temporary
  host filename, atomically rename it, and remove the exact temporary container file.
- Prune only `pos-*.dump` files older than seven days in the validated target.
- Append success/failure information without credentials to `var/log/backup.log`.
- Optional external copy target receives the verified final dump.

### Restore-Database.ps1

Requires `-BackupPath` and `-ConfirmDataReplacement`. It validates the file, stops web, copies the
dump to a fixed temporary container path, terminates connections, drops/recreates only the configured
application database, restores it as the application role, runs migrations, starts web, and polls
health. All destructive database names come from the locally resolved `.env` and are validated as
PostgreSQL identifiers before use.

### Rollback-Release.ps1

Requires previous version, pre-update backup, and explicit confirmation. It verifies the old image
exists, selects it, calls the restore workflow, and records rollback state only after health passes.

### Other scripts

- `Start-POS.ps1`: start services and poll health.
- `Stop-POS.ps1`: stop containers without deleting volumes.
- `Get-POSStatus.ps1`: show Compose status, selected version, last backup, and app health.
- `Install-BackupTask.ps1`: create/update the daily Windows task for the current shop account.

No normal script invokes `docker compose down -v`, deletes images, or recursively deletes a volume,
project root, home directory, or unresolved environment path.

## 6. Backup scheduler

The task runs daily at 23:00 by default under the current dedicated shop Windows account using an
interactive token. This matches Docker Desktop's per-user Linux engine. The operating requirement is
that this account remains signed in and Docker Desktop remains running at backup time. The task
command uses absolute quoted paths and a non-interactive PowerShell invocation.

Task installation and its first real run are manual Windows checks. The script reports this
limitation rather than claiming a machine-level Windows service.

## 7. Configuration and secrets

Add the following non-secret configuration keys to `.env.example`:

- `POS_APP_IMAGE=pos-codex`
- `POS_APP_VERSION=development`
- `POS_APP_BIND=127.0.0.1`
- `POS_APP_PORT=8000`
- `POS_BACKUP_DIR=var/backups`
- `POS_BACKUP_RETENTION_DAYS=7`

Production uses `DJANGO_DEBUG=false`, a random 32+ character secret, unique database passwords, and
localhost allowed hosts/origins. `.env` remains ignored and is not copied into the image or package.

## 8. LAN extension documentation

The runbook documents, but does not perform, these future changes:

1. reserve a private static address for the host;
2. change `POS_APP_BIND` to that private address or `0.0.0.0` only when needed;
3. add the private host/IP to Django allowed hosts and HTTP origin to trusted origins;
4. add a Windows Firewall inbound rule limited to the private subnet and app port;
5. create/assign a distinct Django `Terminal` for the second computer before checkout; and
6. verify that port 5432/5433 is not reachable from the LAN.

Local HTTP remains acceptable only for the trusted private shop network. Public exposure is
forbidden.

## 9. Documentation artifacts

- `deploy/README.md`: install, update, rollback, backup, restore, health, logs, and troubleshooting.
- `deploy/SHOP_OPERATIONS.md`: short owner/admin/cashier daily instructions.
- `deploy/PILOT_CHECKLIST.md`: required real-host/pilot evidence with result fields.
- Root `README.md`: development instructions plus a pointer to production deployment docs.
- Project `docs/architecture/technical-design.md`: replace Waitress topology with Dockerized Gunicorn and versioned
  release packages.

## 10. Automated verification

- Existing Django and JavaScript suites remain green.
- Health tests cover database success, database failure, and version disclosure.
- Deployment contract tests parse Compose/YAML-relevant text and release artifacts to check:
  Gunicorn/no Waitress, non-root image, production settings, local asset build/collectstatic,
  localhost bindings, DB health dependency, restart policies, named DB volume, no migration-on-web-
  startup, and no `down -v` in scripts.
- PowerShell parser checks every `.ps1`/`.psm1` file for syntax errors.
- `docker compose config` validates interpolation using a safe test environment.
- A production image is built and inspected; it runs Django checks, migrations, and automated tests
  against PostgreSQL.
- Backup creation and clean isolated restore are integration/manual release checks because they
  manipulate real Docker state and cannot be proven by unit tests alone.

## 11. Transaction and data boundaries

Business-service transaction rules remain unchanged. Deployment scripts serialize operator actions
by a file lock under `var/deployment/` so install/update/restore/rollback do not run concurrently.
Database dumps are consistent PostgreSQL custom-format snapshots. A restore is a deliberate whole-
application-database replacement, never a row-level merge.

## 12. Security decisions

- App runs as a non-root Linux user; DB uses separate admin and application roles.
- Production Django checks run during release verification.
- Default ports bind to loopback; database is not exposed in the LAN recipe.
- Health discloses only status and application version.
- Release integrity uses SHA-256 to detect accidental/corrupt transfer. It is not a publisher
  signature and does not protect against a malicious operator with filesystem access.
- Remote-access security, disk encryption, Windows account policy, and signed-code infrastructure
  are outside MVP scope but should be handled operationally by the shop/operator.

## 13. Planning decisions

- Gunicorn 26.0.0 is exact-pinned based on the current production/stable PyPI release and runs only
  in Linux Docker.
- Docker image packages are the update unit; Git is not used on the shop host.
- Destructive rollback is never silently automatic.
- Windows sign-in plus Docker Desktop startup is the supported automatic-start boundary.
- Real restart, USB scanner, disconnected internet, Task Scheduler, clean restore, and supervised
  pilot evidence must be performed by the user/operator.
