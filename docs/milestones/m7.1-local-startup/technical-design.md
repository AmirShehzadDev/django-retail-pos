# Milestone 7.1 Technical Design - Local Startup and Deployment Hardening

**Status:** Implemented; pending user verification
**Version:** 1.0
**Feature input:** `docs/milestones/m7.1-local-startup/feature-spec.md`

## Configuration

`.env.example` adds `POS_LOCAL_HOSTNAME=retailpos`, adds `retailpos` to allowed hosts, and adds the
matching HTTP origin with the existing port. Loopback binding remains unchanged. Existing `.env`
files are never replaced during an update.

The shared deployment module adds an environment preflight that scans non-comment assignments and
rejects any value containing `$`. This intentionally strict rule avoids both `$NAME` and `${NAME}`
Compose interpolation in secrets. The error reports only affected keys. Operators generate secrets
from random bytes encoded as Base64, which does not contain `$`.

## Hostname setup

`deploy/Configure-LocalHostname.ps1`:

1. Resolves the permanent root from `$PSScriptRoot` and reads `POS_LOCAL_HOSTNAME` and
   `POS_APP_PORT` from `.env`.
2. Validates a DNS-safe single-label hostname.
3. Relaunches itself through `Start-Process -Verb RunAs` when it lacks administrator rights.
4. Parses the Windows hosts file without exposing `.env` values.
5. Treats an existing `127.0.0.1 <hostname>` mapping as success, rejects any conflicting mapping,
   or appends one tagged `# Retail POS` entry.
6. Adds the hostname/origin to the existing CSV configuration values only when absent.
7. Flushes the Windows DNS cache.
8. Copies `deploy/Start-Retail-POS.cmd` to the current user's actual Desktop folder.
9. When Docker is available, recreates only `web` and waits for application health; otherwise it
   reports that the launcher will start Docker later.

## Desktop launcher

`deploy/Start-Retail-POS.cmd` reads `POS_LOCAL_HOSTNAME` and `POS_APP_PORT` from the permanent
`.env`, with `retailpos` and `8000` fallbacks. It checks `docker info`, starts the standard Docker
Desktop executable if required, polls for at most three minutes, calls the permanent
`deploy/Start-POS.ps1`, and opens Chrome from either Program Files location or the default browser.
Failures remain visible through `pause`; success closes the command window.

## Backup hardening

`Get-PosDatabaseContainer` filters merged native output for exactly one hexadecimal container ID of
12-64 characters. It ignores warnings and throws an actionable error when zero or multiple IDs are
found. `docker cp` therefore never receives Compose warning text as a container name.

## Verification

- Deployment contract tests assert the new defaults, scripts, preflight, valid-ID filtering, and
  documentation.
- PowerShell parser checks cover all `.ps1` and `.psm1` files on Windows.
- Focused Django documentation/deployment tests and Ruff checks run in the supported container.
- The user owns real Windows elevation, hosts-file, desktop, Docker Desktop, Chrome, restart, and
  successful-backup verification.
