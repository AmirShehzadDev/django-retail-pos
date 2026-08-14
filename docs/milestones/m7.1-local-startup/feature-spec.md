# Milestone 7.1 Feature Specification - Local Startup and Deployment Hardening

**Status:** Implemented; pending user verification
**Version:** 1.0
**Parent milestone:** Milestone 7 offline deployment

## Purpose

Make the Windows shop installation easier to start and safer to operate without changing any POS
business behavior. A cashier should be able to double-click one launcher and open the POS at the
friendly local address `http://retailpos:8000`. Deployment commands must reject ambiguous Docker
Compose interpolation and must not mistake warning text for a database container identifier.

## Actors and permissions

- The developer builds and publishes a versioned offline release package.
- The shop operator runs the one-time hostname setup with Windows administrator approval.
- A cashier uses the desktop launcher without administrator access.

## Preconditions

- The permanent installation is `C:\RetailPOS` and has a configured `.env`.
- Docker Desktop is installed with Linux containers.
- The application remains bound to `127.0.0.1`; this refinement does not enable LAN access.

## Approved behavior

1. New `.env` files include `retailpos` in `DJANGO_ALLOWED_HOSTS`, include
   `http://retailpos:8000` in `DJANGO_CSRF_TRUSTED_ORIGINS`, and declare
   `POS_LOCAL_HOSTNAME=retailpos`.
2. A one-time PowerShell script requests elevation when necessary, validates the configured local
   hostname, and adds an idempotent `127.0.0.1 retailpos` hosts-file entry.
3. The setup script refuses to replace an existing conflicting hostname mapping.
4. For an existing installation, the setup script appends the hostname and origin to `.env` without
   changing other values or exposing secrets, then recreates only the web container when Docker is
   available.
5. The setup script places the packaged launcher on the current user's Windows Desktop.
6. The launcher starts Docker Desktop when necessary, waits with a bounded timeout, starts the POS
   through the permanent lifecycle script, and opens Chrome or the default browser at the friendly
   local URL.
7. Deployment preflight rejects dollar signs in `.env` values before Compose can interpolate them;
   errors identify setting names but never values.
8. Database-container discovery accepts only a valid hexadecimal container ID and ignores unrelated
   Compose output such as warnings.
9. Existing `1.0.0` installations remain updateable; the refinement is packaged as a new `1.0.1`
   release rather than replacing the immutable `1.0.0` artifact.

## Validation and edge cases

- Hostnames are lowercase single-label names containing only letters, numbers, and interior hyphens.
- Existing correct hosts entries are a successful no-op; conflicting mappings stop safely.
- Missing Docker Desktop or a Docker startup timeout leaves a visible actionable launcher message.
- Missing Chrome falls back to the Windows default browser.
- Re-running hostname setup never duplicates the hosts entry, allowed host, trusted origin, or
  desktop launcher.
- The setup process does not change the application port, Compose project name, database volume,
  database credentials, backups, or business data.

## Acceptance criteria

1. New-install configuration accepts `http://retailpos:8000` while remaining loopback-only.
2. One administrator-approved setup run makes `retailpos` resolve to `127.0.0.1` and creates the
   desktop launcher.
3. Double-click startup works when Docker is stopped and when it is already running.
4. Unsafe `$name`-style `.env` content stops deployment with setting names only.
5. Compose warnings cannot be used as a `docker cp` source container.
6. PowerShell syntax, deployment contracts, documentation links, Ruff, and relevant Django tests
   pass.
7. The user performs the required Windows hostname, launcher, Chrome, restart, and backup checks.

## Explicit exclusions

- Removing `:8000`, binding port 80, LAN access, public DNS, TLS, or internet exposure.
- Starting Docker before Windows sign-in or changing Docker Desktop's own startup configuration.
- Automatic GitHub tagging, release publication, download, or self-update.
- Any sales, inventory, order, return, report, authentication, or permission change.
