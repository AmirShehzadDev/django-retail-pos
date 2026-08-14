# Changelog

All notable public changes will be documented in this file. The project follows
[Semantic Versioning](https://semver.org/) for tagged public releases.

## [Unreleased]

### Added

- Public README, MIT license, security policy, contribution guide, documentation index, and GitHub
  Actions verification workflow.
- Complete single-shop MVP covering users, products, inventory, active POS orders, cash checkout,
  completed-order history, returns, voids, daily reporting, audit history, and offline deployment.

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

### Security

- Public deployment guidance now states the localhost/private-network boundary and private
  vulnerability-reporting process explicitly.
