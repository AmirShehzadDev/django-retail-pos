# Milestone 7 Feature Specification - Offline Deployment and Shop Pilot

**Status:** Implemented; required shop verification and pilot pending  
**Version:** 1.0  
**Requirements:** `docs/product/mvp-requirements.md` version 1.7
**Milestone:** `docs/product/roadmap.md` Milestone 7

## 1. Purpose

Install the POS on one Windows shop computer as a recoverable, offline-capable Docker deployment.
The application must start predictably, preserve shop data across application updates, create daily
database backups, and provide safe scripts and instructions for initial installation, remote updates,
rollback, recovery, and the supervised shop pilot.

This milestone changes deployment and operations. It does not add or change sales, inventory,
return, void, reporting, user, or permission behavior.

## 2. Actors and permissions

### Developer/operator

- Builds and verifies a versioned application image on a development computer.
- Transfers a release package to the shop, normally through TeamViewer or a USB drive.
- Installs updates, checks health, and performs rollback or restore when necessary.
- Has access to Docker Desktop, the deployment directory, and production environment file.

### Shop owner

- Keeps the Windows host and Docker Desktop running during shop operation.
- Confirms that the POS opens after Windows sign-in and that the latest backup exists.
- Participates in the supervised pilot and records unexplained cash or stock discrepancies.
- Does not need to use Git, Python, Node.js, or edit application source.

### Admin and cashier

- Use the same application capabilities and permissions approved in Milestones 1-6.
- Do not receive access to deployment scripts, secrets, backups, or Docker administration through
  the application.

## 3. Preconditions

- The host uses Windows with a supported Docker Desktop installation and Linux containers.
- Docker Desktop is configured to start when the dedicated shop Windows account signs in.
- The project has a production `.env` created from `.env.example` with unique secrets.
- The `.env` contains a stable, unique `COMPOSE_PROJECT_NAME` that identifies this installation's
  containers and database volume and is not changed during updates.
- Port 8000 is available on localhost. PostgreSQL is not exposed to the shop network.
- The initial owner, shop, and terminal setup has been completed.
- A release package was built and automatically tested before it is taken to the shop.
- TeamViewer may be used for maintenance, but POS operation and updates from a local package do not
  require TeamViewer or internet access.

## 4. Production runtime

1. Docker Compose starts a Linux application container and a PostgreSQL container.
2. Gunicorn serves the Django WSGI application; WhiteNoise serves collected local static assets.
3. The application waits for a healthy database and exposes a health endpoint checked by Docker.
4. The application is reachable at `http://127.0.0.1:8000` on the initial checkout computer.
5. Both services use restart policies so they resume after Docker Desktop starts.
6. Database data, backups, application logs, and production configuration survive replacement of
   the application image.
7. No runtime request loads a font, script, stylesheet, image, telemetry endpoint, or service from
   the internet.

## 5. Initial installation flow

1. The operator copies the deployment files and a versioned release package to a dedicated folder.
2. The operator creates the production `.env` with strong unique credentials and localhost hosts.
3. The install command verifies Docker, configuration, package checksum, and release metadata.
4. It loads the image, starts PostgreSQL, applies Django migrations as a one-off command, starts the
   application, and waits for a healthy response.
5. It records the installed application version without storing any secret in release metadata.
6. The operator installs the daily backup task and confirms one successful backup.
7. The owner opens the application and signs in using the separately established owner account.

Installation must stop with an actionable error if configuration, checksum, image loading,
migration, startup, or health verification fails.

## 6. Application update flow

1. The developer assigns a non-empty version, builds the production image, runs automated checks,
   and exports an offline release package containing the image, checksum, and non-secret manifest.
2. The package is transferred to the shop through TeamViewer, USB, or another file-transfer method.
3. The operator runs the update command against that package.
4. The update command verifies the checksum and refuses an invalid or already-corrupted package.
5. It loads the new image and creates a timestamped pre-update database backup before changing the
   running application.
6. It stops only the web container, selects the new version, runs migrations once, starts the web
   container, and waits for Docker/application health checks.
7. On success, the version record is updated and the pre-update backup is retained.
8. The operator performs the concise post-update smoke checklist before handing the POS back to the
   cashier.

An update must not use `git pull`, install packages from the internet on the shop computer, rebuild
source at the shop, replace the `.env`, or delete the PostgreSQL volume.

## 7. Failed update and rollback

- The previous application image remains locally available unless the operator deliberately removes
  it after a later maintenance review.
- If failure occurs before migrations, the prior version can be restarted without database restore.
- If any migration was attempted, rollback uses the mandatory pre-update backup before starting the
  prior image, because older code is not assumed to support a newer schema.
- Rollback and standalone restore are explicit operator actions with confirmation because they
  replace current shop data.
- A failed update must report the package version, retained backup path, current selected version,
  and the next recovery command.

## 8. Backup behavior

- A Windows scheduled task invokes the project backup script once daily under the dedicated shop
  Windows account while Docker Desktop is available.
- Each backup is a PostgreSQL custom-format dump with a timestamped filename.
- The script validates the dump with `pg_restore --list` before reporting success.
- Automatic cleanup deletes only matching POS dump files older than seven days inside the resolved,
  configured backup directory. It never recursively deletes a broad or unresolved path.
- Backup failure returns a non-zero exit and is written to an operational log.
- An optional second copy may be written to an external drive; failure of that copy does not delete
  the verified primary backup.
- A backup containing production data is never committed to Git or included in a release package.

## 9. Restore behavior

1. The operator selects an existing dump and explicitly confirms data replacement.
2. The script validates the dump before stopping the application.
3. It replaces only the configured POS application database, restores the dump, reapplies any
   migrations required by the selected application image, and starts the application.
4. It waits for a healthy response and reports the restored file and selected application version.
5. Restore failure leaves the web application stopped and presents recovery instructions; it must
   never claim success from an unverified dump.

A clean-install restore test uses a separate test deployment/project name or a documented isolated
test computer so it cannot overwrite live shop data.

## 10. Future local-network terminal

- The default installation binds only to localhost.
- Documentation may describe how an operator later opts into LAN access by configuring allowed
  hosts, trusted origins, the app port binding, a distinct terminal record, and a private Windows
  Firewall rule.
- PostgreSQL remains internal to the Docker network and is not published to the LAN.
- LAN terminals depend on the host computer; offline synchronization and multi-host databases are
  excluded.
- LAN access is not enabled or tested as part of the one-computer MVP release.

## 11. Pilot and operating instructions

The runbook must give short instructions for starting the shop day, confirming system/backup health,
normal cashier handoff, ending the day, reporting a problem, and contacting the operator. The pilot
records pass/fail evidence for:

- restart and automatic service recovery;
- disconnected-internet operation;
- physical USB scanner and unknown-product quick-create;
- signed positive and negative change;
- cashier logout/login handoff and draft persistence;
- two-client concurrency against the same host;
- negative-stock acknowledgement;
- linked partial/full return and manager void;
- inventory reconciliation;
- backup creation and isolated clean restore; and
- end-of-pilot cash and stock discrepancy review.

## 12. Validation and edge cases

- Missing/placeholder secrets, missing release files, invalid checksums, invalid versions, unhealthy
  services, and failed commands stop the relevant operation.
- File paths with spaces are supported by the PowerShell scripts.
- A release version cannot contain path separators or shell control characters.
- Backup and restore scripts discover the actual Compose database container instead of assuming a
  hard-coded container name.
- Re-running start/status/backup operations is safe. Re-running an already successful update to the
  selected version performs no schema/data mutation and reports that it is already installed.
- Loss of internet has no effect on login, catalog, inventory, checkout, orders, returns, voids,
  reports, local static assets, backup, or restore.
- Docker Desktop not starting before Windows sign-in is documented as an operating limitation and
  is a required real-host verification, not an automated claim.
- TeamViewer failure does not stop a running POS; it only delays remote maintenance.

## 13. Data effects

- Normal container restart and application image replacement do not alter business records.
- Django migrations may evolve schema during an update and are covered by a pre-update dump.
- Backups create files outside the database volume; retention removes only expired matching files.
- Restore deliberately replaces the configured POS database with the selected backup.
- Operational version/status files contain no credentials or business data.

## 14. Acceptance criteria

1. A production image builds with pinned application dependencies, compiled local CSS, collected
   static assets, Gunicorn, and no Waitress dependency.
2. Compose starts PostgreSQL and the app, waits on database health, and reports both healthy.
3. Production configuration passes Django's deployment check without debug mode or placeholder
   secrets.
4. The application and all core workflows operate with the internet disconnected.
5. A signed/checksummed versioned package can be loaded and installed without downloading runtime
   dependencies at the shop.
6. An update retains the database/configuration, takes a verified pre-update backup, applies
   migrations once, and exposes the selected healthy version.
7. A failed or incompatible update has a documented, testable path back to the prior image and
   pre-update database.
8. A scheduled daily backup is installed; verified dumps older than seven days are safely pruned.
9. A selected backup restores successfully into an isolated clean test installation and the app
   passes health/login/data spot checks.
10. Docker/application services recover after real Windows restart/sign-in.
11. Localhost is the default; future private-LAN enablement is documented without publishing the
    database port.
12. The user completes the physical scanner, offline, restart, clean restore, and supervised pilot
    checklist without unexplained cash or stock discrepancies.

## 15. Explicit exclusions

- Public internet hosting, cloud database, cloud backup, SaaS monitoring, or automatic online update.
- Kubernetes, reverse proxy, TLS certificate automation, high availability, or failover host.
- TeamViewer installation/configuration or unattended remote-access security policy.
- Enabling a second terminal, offline synchronization, or supporting operation when the host is off.
- In-app deployment controls, database restore controls, or exposing secrets/backups to POS users.
- Automatic deletion of old application images.
- New business features, receipt printing, tax, card payments, weighted products, or profit analytics.

## 16. Requirements reconciliation

- `docs/product/mvp-requirements.md` requires Windows, one checkout initially, offline operation, local assets,
  PostgreSQL, safe backup/restore, physical-scanner testing, and future LAN compatibility. This
  specification supplies the deployment and verification behavior without changing business scope.
- `docs/product/roadmap.md` Milestone 7 requires automatic startup, seven-day backups, tested restore, LAN
  documentation, scanner testing, operating instructions, and a supervised pilot. Every deliverable
  and exit criterion is represented above.
- The approved user direction replaces the project-level Waitress choice with Gunicorn inside a
  Linux application container and adds versioned offline Docker-image updates.
