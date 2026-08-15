# Changelog

All notable public changes will be documented in this file. The project follows
[Semantic Versioning](https://semver.org/) for tagged public releases.

## [Unreleased]

## [1.0.2] - 2026-08-15

### Added

- A desktop stop command that creates a verified shutdown backup, stops the POS containers, and
  shuts down Docker Desktop gracefully.

### Changed

- Local backup retention is capped at ten verified dumps while preserving the newest pre-update
  rollback backup within that limit; external backup copies are not pruned.

## [1.0.1] - 2026-08-15

### Added

- One-time Windows local-hostname setup and a desktop launcher for starting Docker Desktop, the POS,
  and `http://retailpos:8000` in Chrome.

### Changed

- Deployment guidance now separates immutable release packages from the permanent shop
  installation and provides complete first-install and update commands.
- Initial installation now directs operators to `bootstrap_pos`, which creates the required shop,
  terminal, sequences, and owner account.
- Product, architecture, milestone-planning, and completion documents now use a structured `docs/`
  hierarchy with checked internal links.
- Compose project identity is configurable and persistent through `COMPOSE_PROJECT_NAME`, allowing
  separate development, test, and shop installations to reuse their correct database volumes
  during updates.
- Deployment scripts reject dollar signs in `.env` values, ignore Docker Compose warning output
  when selecting the database container, and wait for the final PostgreSQL process before backup.

## [1.0.0] - 2026-08-14

### Added

- Public README, MIT license, security policy, contribution guide, documentation index, and GitHub
  Actions verification workflow.
- Complete single-shop MVP covering users, products, inventory, active POS orders, cash checkout,
  completed-order history, returns, voids, daily reporting, audit history, and offline deployment.

### Security

- Public deployment guidance now states the localhost/private-network boundary and private
  vulnerability-reporting process explicitly.
