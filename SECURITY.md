# Security Policy

## Supported code

Until the first tagged public release, security fixes are applied to the latest `main` revision.
After releases begin, only the latest release and current `main` branch will receive fixes unless a
release note states otherwise.

## Reporting a vulnerability

Do not disclose a vulnerability, credential, shop record, database dump, or exploit details in a
public issue. Use GitHub's private vulnerability reporting option under the repository's
**Security** tab. If private reporting is temporarily unavailable, contact the maintainer through
the GitHub profile before sharing technical details.

Include the affected revision/version, deployment type, reproduction steps, expected impact, and
whether real data may have been exposed. Do not include live passwords, secret keys, backups, or
customer data in the report.

## Deployment boundary

The supplied configuration is intended for localhost or a specifically reviewed trusted shop LAN.
It is not hardened for direct public-internet hosting. Local HTTP, localhost bindings, and the
single-host trust model are deliberate MVP constraints.

Every installation must:

- replace all placeholder secrets and passwords in `.env`;
- keep `.env`, backups, logs, releases, and database volumes outside Git;
- preserve a stable, unique `COMPOSE_PROJECT_NAME` across updates;
- restrict application and PostgreSQL ports with host bindings and firewall rules;
- use named user accounts rather than shared cashier credentials;
- keep verified backups outside the application container; and
- review HTTPS, trusted origins, allowed hosts, session cookies, CSRF cookies, and network access
  before enabling any LAN client.

Never resolve a deployment problem by deleting a production Docker volume.

## Sensitive operational data

Screenshots, fixtures, issues, and pull requests must use invented products, users, orders, and shop
details. Remove database dumps, logs, absolute user paths, tokens, and environment values before
sharing diagnostic material.
