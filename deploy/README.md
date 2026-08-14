# Retail POS Deployment and Recovery Runbook

This runbook is for the developer/operator maintaining the Windows shop computer. Run commands in
PowerShell from the installation folder, normally `C:\RetailPOS`. Never use `docker compose down
--volumes` on the shop installation.

## 1. Shop computer prerequisites

- Windows 11 with Docker Desktop using Linux containers.
- A dedicated Windows shop account configured to sign in when the shop opens.
- Docker Desktop **Start Docker Desktop when you sign in** enabled for that account.
- At least 10 GB free space plus room for seven database backups and two application images.
- Port 8000 available on loopback.

TeamViewer is optional and only provides remote operator access. The POS continues locally if the
internet or TeamViewer is unavailable.

## 2. Build a release

On the development computer, from the clean repository:

```powershell
.\deploy\Build-Release.ps1 -Version 1.0.0
```

The command runs automated checks, builds `pos-codex:1.0.0`, runs Django deployment checks inside
the image, and creates:

```text
releases\pos-codex-1.0.0\
  release.json
  pos-codex-1.0.0.tar
  runtime\
releases\pos-codex-1.0.0.zip
```

Do not edit `release.json` or the image after packaging. The installer rejects a checksum mismatch.
The SHA-256 detects corrupt or accidental modification; it is not a cryptographic publisher
signature.

## 3. Initial installation

1. Extract the release zip to `C:\RetailPOS\incoming\pos-codex-1.0.0`.
2. Copy the extracted `runtime` contents into `C:\RetailPOS`.
3. Create and edit production configuration:

```powershell
Set-Location C:\RetailPOS
Copy-Item .env.example .env
notepad .env
```

Set `DJANGO_DEBUG=false`. Replace every `replace-...` value with a unique secret/password. Keep
`POS_APP_BIND=127.0.0.1`, localhost allowed hosts/origins, and the initial `TILL-1` terminal.
Keep `COMPOSE_PROJECT_NAME` stable for the lifetime of the installation because it identifies the
Docker containers and database volume. Use a unique value such as `pos_codex_test` for a separate
test installation on the same computer; never reuse one project's ports for another project.

Generate a Django secret without uploading it anywhere:

```powershell
$bytes = New-Object byte[] 48
[Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
[Convert]::ToBase64String($bytes)
```

4. Install and start:

```powershell
.\deploy\Install-POS.ps1 `
  -ReleaseDirectory .\incoming\pos-codex-1.0.0 `
  -InstallDailyBackupTask
```

5. For a new database only, create/bootstrap the first owner interactively:

```powershell
docker compose run --rm web python manage.py bootstrap_pos
```

6. Open `http://127.0.0.1:8000/accounts/login/`, sign in, then run:

```powershell
.\deploy\Backup-Database.ps1 -Purpose initial-install
.\deploy\Get-POSStatus.ps1
```

Never store the owner password in `.env`, scripts, TeamViewer chat, release files, or Git.

## 4. Normal start, stop, status, and logs

```powershell
.\deploy\Start-POS.ps1
.\deploy\Get-POSStatus.ps1
docker compose logs --tail 200 web db
.\deploy\Stop-POS.ps1
```

Stopping retains all data. Normally leave both containers running; `restart: unless-stopped`
recovers them when Docker Desktop starts after Windows sign-in.

## 5. Daily backups

Manual verified backup:

```powershell
.\deploy\Backup-Database.ps1 -Purpose manual
```

Optional external copy:

```powershell
.\deploy\Backup-Database.ps1 -Purpose manual -ExternalCopyDestination E:\RetailPOSBackups
```

Install/update the daily 23:00 task:

```powershell
.\deploy\Install-BackupTask.ps1 -At 23:00
```

The dedicated Windows account must be signed in and Docker Desktop running at that time. In Task
Scheduler, run **Retail POS Daily Backup** once immediately; then confirm a new `pos-*.dump` under
`var\backups` and a success line in `var\log\backup.log`. Files older than seven days are pruned
only from the configured primary backup directory.

## 6. Install an update through TeamViewer or USB

Before maintenance, finish/hold the current customer order and tell the cashier the POS will be
briefly unavailable.

1. Transfer and extract the new package under `C:\RetailPOS\incoming`.
2. Copy its `runtime` contents over `C:\RetailPOS`. This updates scripts/Compose but does not contain
   or overwrite `.env`, database data, logs, or backups.
   Confirm that the installed `.env` still contains its original `COMPOSE_PROJECT_NAME` before
   continuing. A release update must reuse the existing Compose project and database volume.
3. Run:

```powershell
Set-Location C:\RetailPOS
.\deploy\Install-Update.ps1 -ReleaseDirectory .\incoming\pos-codex-1.1.0
```

The command validates/loads the image, creates a verified pre-update dump, stops only the web
container, selects the new version, migrates once, starts it, and checks health. Then perform the
post-update smoke check:

```powershell
.\deploy\Get-POSStatus.ps1
```

If Docker reports that the database port is already allocated, stop. Run `docker compose config`
and confirm its top-level `name` matches the existing container prefix before retrying. Do not
create another database project, change volumes, or run `down --volumes` to resolve a port conflict.

In the browser, sign in, open POS, add/remove one item in a temporary draft, open Products & Stock,
Orders, and Reports, then clear the temporary draft. Do not create a fake completed sale on live
data unless the owner explicitly wants a test transaction and reconciliation plan.

## 7. Failed update and rollback

If failure happens before migrations, the update output tells you to start the prior version:

```powershell
.\deploy\Start-POS.ps1
```

If a migration was attempted, do not start the older app against the changed database. Use the exact
version and backup path printed by the failed update:

```powershell
.\deploy\Rollback-Release.ps1 `
  -PreviousVersion 1.0.0 `
  -PreUpdateBackup .\var\backups\pos-YYYYMMDD-HHMMSS-pre-update-1.1.0.dump `
  -ConfirmRollback
```

Rollback replaces the database with the pre-update snapshot, so transactions entered after that
snapshot are lost. Confirm timing with the owner before proceeding.

## 8. Standalone restore

Restore replaces current POS data. First preserve the current state with another backup if it is
readable, then run:

```powershell
.\deploy\Restore-Database.ps1 `
  -BackupPath .\var\backups\pos-YYYYMMDD-HHMMSS-daily.dump `
  -ConfirmDataReplacement
```

For the required clean-restore test, use a separate computer or an isolated Compose project and
separate host directories/ports. Never perform the clean-restore test against the live database.
After restore, verify health, owner login, latest order number/amount, one product stock balance,
daily report totals, and `python manage.py reconcile_inventory` through a one-off web container.

## 9. Future second checkout over private LAN

This is documentation, not approval to expose the current system. Before enabling it:

1. Reserve a private static IP for the host computer.
2. Set `POS_APP_BIND` to that private host IP (or `0.0.0.0` only when justified).
3. Add the IP/hostname to `DJANGO_ALLOWED_HOSTS` and its `http://host:8000` origin to
   `DJANGO_CSRF_TRUSTED_ORIGINS`.
4. Add a Windows Firewall inbound TCP 8000 rule scoped only to the private shop subnet.
5. Create and configure a distinct Django terminal for the second checkout before selling.
6. Confirm PostgreSQL host port 5433 is still loopback-only and unreachable from the LAN.
7. Test concurrent checkout and cashier/terminal attribution.

The second checkout depends on the host. This design has no offline synchronization and must never
be exposed directly to the public internet.

## 10. Troubleshooting

- Docker is unavailable: start Docker Desktop under the dedicated shop account and retry.
- Database is unhealthy: `docker compose logs --tail 200 db`; do not delete its volume.
- Web is unhealthy: `docker compose logs --tail 200 web` and verify `.env` hosts/secrets/version.
- Checksum mismatch: discard the transferred package and transfer the original zip again.
- Backup failed: inspect `var\log\backup.log`, confirm free disk space and DB health, then rerun.
- Port 8000 is occupied: identify the conflicting local program before changing the configured port.
- TeamViewer disconnected: leave the running POS untouched; reconnect later or use local/USB files.

Escalate before any database restore, rollback, volume operation, public/LAN exposure, or unexplained
cash/stock discrepancy.
