# Single-Shop Retail POS - Initial Technical Design

**Status:** Revised design for review  
**Version:** 0.9

**Requirements:** `docs/product/mvp-requirements.md` version 1.7
**Milestones:** `docs/product/roadmap.md`

## 1. Purpose and scope

This document defines the project-level architecture and the technical rules that are expensive to change after development starts. It intentionally does not specify every screen interaction; those details will be written just before each functional milestone.

The MVP is a modular Django monolith for one retail/grocery shop. It runs on a Windows checkout computer, requires no internet connection, uses PostgreSQL locally, and can later serve additional checkout computers over the shop's local network.

## 2. Approved technical decisions

| Area | Decision |
|---|---|
| Application | One modular Django monolith; no microservices |
| Backend | Latest patch release in the Django 5.2 LTS series |
| Frontend | Django templates with locally compiled Tailwind CSS and small amounts of local JavaScript |
| Database | Pinned official PostgreSQL Docker image; SQLite is not used for production or concurrency tests |
| Authentication | Django session authentication with a custom user model |
| Currency | PKR using fixed-precision decimals |
| Timezone | Store timezone-aware timestamps; display and report in `Asia/Karachi` |
| Tax | No tax fields, calculations, configuration, or UI in the MVP |
| Deployment | Windows host, Docker Compose with Linux Gunicorn/Django and PostgreSQL containers, no runtime internet dependency |
| Inventory | Transactional current balance plus an immutable movement ledger |
| Stock shortages | Checkout may create a negative balance after visible cashier acknowledgement and audit |
| Cash difference | Signed change equals cash received minus order total; positive and negative values are permitted and visible |
| Draft scope | Maximum three active drafts per checkout terminal; drafts survive cashier changes |
| Sales history | Completed sales, voids, returns, and inventory movements are immutable |
| Concurrency | PostgreSQL transactions and row locks protect checkout and stock changes |
| Extension strategy | Include shop boundaries and service-layer APIs without building multi-shop UI |

## 3. Runtime topology

Initially, the browser, Django application, and PostgreSQL Docker container run on the same Windows computer:

```text
USB barcode scanner -> Browser -> Linux Docker container -> PostgreSQL container
                                      | Gunicorn/Django
                                      +-> WhiteNoise/local static assets

Windows Task Scheduler -> docker exec/pg_dump -> local backup directory -> optional external drive
```

The barcode scanner is treated as a keyboard device that sends the barcode followed by Enter. No scanner-specific driver or external barcode service is part of the application. A seeded terminal identity (`TILL-1`) scopes drafts on the initial computer.

When a second checkout computer is added, it will open the same Django application through a private LAN address. The original host remains the application and database server. This is offline operation, not offline synchronization: if the host is unavailable, other checkout computers cannot transact.

## 4. Proposed project structure

```text
pos_codex/
|-- manage.py
|-- config/
|   |-- urls.py
|   |-- wsgi.py
|   `-- settings/
|       |-- base.py
|       |-- development.py
|       `-- production.py
|-- apps/
|   |-- core/
|   |-- accounts/
|   |-- catalog/
|   |-- inventory/
|   `-- sales/
|-- templates/
|-- static/
|   |-- css/
|   `-- js/
|-- tests/
|-- requirements/
|   |-- base.txt
|   `-- development.txt
`-- docs already stored at the repository root
```

### App responsibilities

- `core`: shop/terminal configuration, document-number sequences, shared utilities, and audit events.
- `accounts`: custom user model, roles, authentication, and user management.
- `catalog`: product catalog, prices, barcode lookup, and product activation.
- `inventory`: stock balance, immutable movement ledger, receipts, and adjustments.
- `sales`: draft orders, checkout, payments, completed orders, voids, and returns.

Daily reporting and audit presentation are implemented as read-only query services in `core`; they
do not need a separate Django app or new reporting tables.

## 5. Domain model

All primary keys use Django `BigAutoField`. Public URLs do not rely on predictable IDs for authorization; every query is filtered by the logged-in user's shop and permissions.

All PKR values use `DecimalField` with two decimal places. Product and order quantities use positive integers. Inventory balances and movement deltas are signed integers because an acknowledged sale may produce negative stock. Barcodes and SKUs are strings, never numeric types.

### 5.1 Core and accounts

#### `Shop`

- Name.
- Currency fixed to `PKR` for the MVP.
- Timezone fixed to `Asia/Karachi` for the MVP.
- Active flag and timestamps.

One shop is created during initial setup. Multi-shop switching and cross-shop access do not exist in the MVP.

#### `Terminal`

- Belongs to one shop and has a shop-unique code, display name, active flag, and timestamps.
- One terminal (`TILL-1`) is created during initial setup.
- Draft orders are scoped to a terminal so they survive logout and can be resumed by the next cashier on the same computer.

The initial localhost installation always resolves to `TILL-1`. A later LAN terminal is registered once and receives a signed local browser identifier; the server validates that the terminal belongs to the user's shop. The identifier scopes workflow but does not replace user authentication.

#### `User`

- Extends Django `AbstractUser` and is configured as `AUTH_USER_MODEL` before the first migration.
- Belongs to one shop.
- Role: `OWNER`, `ADMIN`, or `CASHIER`.
- Stores who created the account and standard activation/login information.

Users are deactivated instead of deleted. The first owner is created by an installation command; the UI cannot create or promote owners.

#### `DocumentSequence`

- One row per shop and document type, initially `ORDER` and `RETURN`.
- Stores the next number.
- Is locked while allocating a number so concurrent checkouts cannot receive the same number.

Numbers are assigned only when a sale or return is completed. Formatting is presentation logic, for example `ORD-000001` and `RET-000001`.

#### `AuditEvent`

- Shop, actor, action code, target type, target identifier, timestamp.
- Optional JSON before/after values and request metadata.
- Append-only and unavailable for editing through normal application pages.

This is a focused audit record, not a generic event framework. MVP action codes cover account/role changes, price changes, manual stock adjustments, cashier product quick-creation, negative-stock checkout acknowledgement, draft takeover, returns, and voids. Clearing a draft or closing an empty tab deliberately creates no audit event. Immutable order/payment records represent cash and signed change; immutable domain records remain the primary financial and inventory audit trail.

### 5.2 Catalog and inventory

#### `Product`

- Shop, optional barcode, optional SKU, name.
- Selling price and optional cost price.
- `stock_on_hand` integer balance.
- Creator and creation source: `CATALOG` or `POS_QUICK_CREATE`.
- `needs_review` flag for cashier-created products.
- Active flag and timestamps.

Constraints and indexes:

- A non-empty barcode is unique within a shop and preserves leading zeroes.
- A non-empty SKU is unique within a shop.
- Selling price and cost price cannot be negative.
- Barcode lookup is indexed; product name search starts with normal PostgreSQL text search suitable for one shop.

`stock_on_hand` is the fast current balance and may be negative. It may only change through the inventory service in the same transaction that creates an `InventoryMovement`. The movement ledger is the permanent explanation for every change. A reconciliation command will compare product balances with movement totals. The unified manager Products & Stock workspace provides `Negative stock` and `Needs review` filters, while the full movement ledger remains a separate audit view.

A cashier can quick-create only from an unknown checkout barcode and can provide only barcode, name, and selling price. The product is active, starts at zero stock, is marked `needs_review`, records its creator/source, and emits an audit event. Normal catalog creation and editing remain owner/admin-only. Barcode-less products are added through search.

#### `InventoryMovement`

- Shop and product.
- Type: `RECEIPT`, `SALE`, `RETURN`, `VOID`, or `ADJUSTMENT`.
- Signed integer quantity change and possibly negative balance after the change.
- Actor, timestamp, reason, and optional links to the source order/return line.

Movements cannot be updated or deleted by application code or the Django admin. Source-link uniqueness protects sale, return, and void operations from creating duplicate stock movements.

### 5.3 Sales

#### `Order`

- Shop and optional completed order number.
- Checkout terminal.
- Status: `DRAFT`, `COMPLETED`, `VOIDED`, `PARTIALLY_RETURNED`, or `RETURNED` in the active workflow. `DISCARDED` remains a legacy compatibility value but no new POS operation creates it.
- Creator, current/last cashier, and completing cashier.
- Stored subtotal/final total and deprecated round-off fields retained as zero/blank/null for
  migration compatibility.
- Created, updated, and completed timestamps. Existing discarded timestamps/reasons remain legacy compatibility fields and are not populated by the approved workflow.
- Integer `version` used to detect two browser sessions editing the same draft.

A terminal may have at most three active draft tabs. This limit is enforced in the sales service. Any authenticated sales user on the same terminal can see and resume them. Resuming a draft created by another cashier updates the current/last cashier and emits a takeover audit event. Clearing a populated draft deletes its lines and resets its total while preserving the same `DRAFT` row and tab. Closing an eligible empty tab deletes that empty draft row. Neither operation asks for a reason, creates history/audit records, or affects inventory. The only remaining active tab cannot be closed.

The order total equals the server-calculated sum of captured line totals. Checkout does not expose
round-off, a reason, or a change-availability decision. It stores signed
`change = cash_received - total`; both positive and negative results are valid and visible.

#### `OrderItem`

- Order and protected link to the product.
- Positive integer quantity.
- Product name, optional barcode, and unit-price snapshots.
- Stored line total.

There is one line per product per order, enforced by a unique constraint. Repeated scans increase that line's quantity. The current catalog price is captured when the product is first added and does not silently change if the catalog price changes later. Draft quantities and totals are recalculated by the server after every change; checkout finalizes the captured values.

#### `Payment`

- Shop and direction: `RECEIPT` or `REFUND`.
- Method fixed to `CASH` in the MVP.
- Amount applied to the sale/refund.
- Cash tendered and change given where applicable.
- Processing user and timestamp.
- Link to exactly one source: completed order, return, or void.

The schema permits future payment methods without exposing them now. Daily cash reporting uses receipt and refund events rather than inferring cash from the current order status.

#### `OrderVoid`

- One-to-one link to a completed order.
- Processing admin/owner, required reason, timestamp, and refund payment.

Voiding creates reversing inventory movements and a cash-refund event but never deletes or rewrites the original order or receipt payment.

#### `SalesReturn`

- Shop, return number, original completed order.
- Processing cashier/admin/owner, optional reason/note, total refund, and timestamp.

#### `SalesReturnItem`

- Return and original order item.
- Positive return quantity.
- Disposition: `RESTOCK` or `DAMAGED`.
- Unit refund and line-refund snapshots.

Multiple partial returns may reference the same original line. The return service requires an identifiable original completed order, locks it, and validates the total already returned before accepting another return. Unlinked returns are not represented in the schema.

Child records such as order items inherit their shop boundary through their parent aggregate. Independently queried or transacted records carry an explicit shop foreign key. This avoids contradictory duplicated shop values while keeping future shop isolation clear.

## 6. Business-service boundaries

Views and forms handle HTTP concerns; business mutations live in explicit service functions. Critical behaviour is not hidden in Django signals or model `save()` overrides.

### Inventory services

- `receive_stock(product, quantity, actor, note)`
- `adjust_stock(product, quantity_delta, actor, reason)`

Normal manager product creation may optionally orchestrate `create_product` followed by
`receive_stock` inside one outer transaction. The product row is still created at zero and the
opening quantity is represented by a genuine `RECEIPT` movement; a receipt failure rolls back the
new product. Product edit never accepts a stock balance.
- Internal `apply_movement(...)`, used by sales and return services

Each service locks the product, validates the requested movement, updates `stock_on_hand`, and appends the movement inside one `transaction.atomic()` block. A resulting negative balance is valid data and is never automatically corrected.

### Sales services

- Create, take over, clear, close, and mutate a terminal-scoped draft order.
- Add an item by barcode or product search.
- Quick-create an unknown scanned product using the restricted cashier fields.
- Recalculate the draft subtotal/final total and signed cash change.
- Complete cash checkout.
- Void a completed order.
- Process a full or partial return.

Only these services may transition an order status or create financial/inventory records.

## 7. Transaction and concurrency design

### Checkout

Checkout runs in one PostgreSQL transaction:

1. Lock the draft order and reject it if it is no longer `DRAFT` or does not belong to the active terminal/shop.
2. Validate that it has at least one item.
3. Recalculate the server-trusted subtotal from captured line prices.
4. Validate non-negative cash received and calculate signed change as cash received minus total;
   cash may be below the total.
5. Lock referenced products in a deterministic product-ID order and verify they remain active.
6. Calculate projected balances. If any will be negative, prepare a focused audit event; do not
   create a correction movement or ask for a second confirmation.
7. Lock and allocate the next order number.
8. Create the cash payment for the order total, cash received, and signed change.
9. Decrease each product balance, allowing a negative result, and append exactly one sale movement
   per order line.
10. Record the stock-shortage audit event where applicable.
11. Store final snapshots, total, completing user, completion time, and `COMPLETED` status.
12. Commit all changes together and create a fresh draft in the same slot.

The draft order itself is the idempotency boundary. A repeated checkout submission cannot create another sale because the locked order is no longer a draft; the endpoint returns the existing completed result.

### Return

Return processing is available to all three roles. It requires and locks an identifiable original completed order, refuses a voided order, locks affected product rows, validates remaining returnable quantities, allocates a return number, records the refund and audit event, adds stock only for `RESTOCK` lines, updates the order's return status, and commits atomically.

### Void

A void is owner/admin-only. It locks the completed order, refuses an order that is already voided or has any full/partial return, creates the cash refund and reversal movements, records the reason/actor/audit event, and changes only the order status. Original line, total, and receipt-payment data remain unchanged. A voided order cannot later be returned.

### Draft editing

Every draft mutation sends the last known version. The server increments the version after a successful change and rejects stale mutations with a refresh-required response. Drafts are terminal-scoped rather than user-scoped. When a different cashier resumes a draft on the same terminal, the service records the takeover before permitting mutation. Clearing a populated draft is an atomic versioned mutation that removes its lines, resets totals, and increments the same draft version. Closing an empty draft is also atomic and version-checked; it is rejected when no other active tab exists. The detailed interaction and lock ordering are defined in `docs/milestones/m4.2-clear-orders/technical-design.md`.

## 8. Authorization model

| Capability | Owner | Admin | Cashier |
|---|---:|---:|---:|
| Create and complete sales | Yes | Yes | Yes |
| View own orders | Yes | Yes | Yes |
| View completed shop orders read-only | Yes | Yes | Yes |
| Manage products and inventory | Yes | Yes | No |
| Quick-create unknown scanned product | Yes | Yes | Yes |
| Process linked returns | Yes | Yes | Yes |
| Void a completed order | Yes | Yes | No |
| View reports and audit history | Yes | Yes | No |
| Create/deactivate cashiers | Yes | Yes | No |
| Create/deactivate admins | Yes | No | No |
| Create/promote owners | Installation only | No | No |

Views use role-aware mixins/decorators, and critical service functions repeat authorization checks. Every queryset is shop-scoped before retrieving its target; possession of another record's ID never grants access.

## 9. Web and template design

Most pages are conventional server-rendered Django templates and forms. The POS page uses a small local JavaScript controller for fast cart interactions while Django remains the source of truth.

Tailwind CSS is compiled locally with the official CLI into a versioned Django static file. The
build dependencies are exact-pinned when the pipeline is introduced. Tailwind Play CDN is not
used; Node.js/the CLI is a development and packaging dependency only, and the shop runtime serves
the generated CSS without an internet connection or JavaScript framework.

- Scanner input stays focused and submits on Enter.
- An unknown scan opens a restricted quick-create form with barcode prefilled; success adds the new product to the active draft.
- Barcode-less products are found and added through search.
- Scan, quick-create, search, quantity, removal, tab, and checkout operations use CSRF-protected requests.
- The server returns validated cart state and totals; the browser does not independently determine prices or final totals.
- The desktop POS keeps order lines and the checkout trigger in the left two-thirds and the
  active-product catalogue in the right third. Tab from the focused scanner moves to Complete sale;
  its native dialog keeps the line preview, order total, total-prefilled Cash received, signed
  Change, and final action reachable without whole-page scrolling at 1366x768 and 100% zoom.
- Insufficient recorded stock displays affected products/projected balances; the single Complete
  sale action records the focused audit without a separate confirmation screen.
- Network/server errors leave the persisted draft intact and show a recoverable message.
- Buttons and inputs are keyboard-friendly and sized for quick checkout use.
- No runtime fonts, libraries, telemetry, analytics, or assets are loaded from the internet.

Indicative URL groups:

- `/accounts/` - login, logout, and user management.
- `/products/` - catalog and product editing.
- `/inventory/` - receive, adjust, and view movements.
- `/pos/` - active drafts and cart mutation endpoints.
- `/orders/` - shop order search/history, details, owner/admin voids, and linked returns for all roles.
- `/reports/` and `/reports/audit/` - owner/admin operations.

Exact screens, form fields, and endpoint payloads are decided in each milestone's feature specification.

## 10. Reporting rules

Daily boundaries use `Asia/Karachi`, while timestamps remain timezone-aware in the database.

- Gross sales: receipt amounts for orders completed during the selected local day.
- Returns: refund amounts for returns processed during that day.
- Voids: refund amounts for voids processed during that day.
- Net sales: receipt amounts minus return/void refunds recorded during that day.
- Cash collected: cash tendered on receipts; cash refunded is the sum of return/void refunds.
- Cash differences: counts and algebraic signed totals derived from recorded change on completed
  orders. Gross sales reconcile as cash collected minus signed change.
- Counts and statuses are presented separately from cash totals.

Using event timestamps means a return made today affects today's cash summary even if the original sale occurred earlier. Reports do not rewrite historical days when later reversals occur. The orders page exposes a non-zero-change filter and highlighted signed Change, and order detail shows total, cash received, and Change. Admin product/inventory pages expose `Needs review` and `Negative stock` filters.

## 11. Settings, secrets, and dependencies

- Shared settings live in `base.py`; debug and production differences live in separate modules.
- Secrets, database credentials, allowed hosts, and deployment paths come from environment variables or an ignored local environment file.
- `DEBUG` is always false in the shop installation.
- Dependencies are exact-pinned when Milestone 0 is scaffolded.
- A versioned Docker image package contains Python dependencies, compiled CSS, and collected static
  assets so installation and updates do not download runtime dependencies at the shop.
- Static files are collected into the image and served locally through WhiteNoise behind Gunicorn.
- Application images are replaceable; `.env`, database data, logs, and backups remain persistent.
- Updates verify the release checksum, take a pre-update database backup, apply migrations once,
  start the selected version, and require a health check. Rollback after attempted migrations uses
  the retained prior image plus pre-update database dump.

No secret, owner password, production database dump, or environment file is committed to source control.

## 12. Security and operational safeguards

- Django password hashing, CSRF protection, secure session configuration, and server-side permissions remain enabled.
- The application listens on localhost initially and may use the Windows hosts alias `retailpos` for
  the same `127.0.0.1` endpoint. Future LAN access is limited by Windows Firewall to the private
  shop subnet; it is never exposed directly to the public internet.
- Critical transaction models are not editable through Django admin.
- Users and products referenced by history are deactivated, not deleted.
- Application errors are written to rotating local logs without passwords or sensitive form values.
- Friendly checkout errors never expose stack traces and never discard the active draft.

Local HTTP is acceptable for the single-computer localhost MVP. The security design for future LAN terminals, including local HTTPS if required, is reviewed before enabling network access.

## 13. Backup and recovery design

- Windows Task Scheduler runs `pg_dump` through the PostgreSQL container daily to a configured local backup directory.
- Seven daily backups are retained; cleanup targets only the configured backup directory.
- A second copy may be written to an external drive without making that drive necessary for normal operation.
- Restore uses a documented `pg_restore` process into a clean PostgreSQL database.
- Milestone 7 is not complete until a generated backup has been restored and tested.

Application source, deployment configuration, and database backups are handled separately. Restoring only the source code is not considered data recovery.

## 14. Test strategy

- Model and constraint tests cover valid/invalid field values and uniqueness.
- Service tests cover inventory, quick-create, terminal handoff, price capture, signed cash change,
  negative-stock audit, checkout, voids, linked returns, idempotency, and audit events.
- Permission tests cover every role and shop boundary.
- View tests cover forms, pagination, filters, CSRF-protected mutations, and error responses.
- PostgreSQL `TransactionTestCase` tests use separate connections to prove concurrent checkout produces consistent balances, never loses/duplicates a movement, and cannot allocate duplicate document numbers. Negative balances are valid only through recorded movements.
- Manual acceptance tests cover the real USB scanner, keyboard workflow, browser restart, Windows restart, internet disconnection, backup, and restore.

Business-critical totals and stock transitions require automated tests before their milestone can be completed.

## 15. Deferred decisions

The user-management forms and password-reset workflow are resolved in `docs/milestones/m1-users/feature-spec.md` and
refined in `docs/milestones/m1-users/technical-design.md`.

The remaining decisions are intentionally left to their just-in-time feature specifications:

- Draft-order naming and the exact takeover notification presentation.
- Product search interaction and catalog page layout.
- Checkout shortcuts beyond the approved scanner Tab-to-checkout and dialog completion workflow.
- Return-screen workflow and damaged-item wording.
- Daily-summary layout and export options.
- Exact Windows installation directory and service wrapper.

The following require future requirements and schema migrations rather than speculative MVP fields: tax, weighted products, additional payment methods, receipt printing, suppliers, multiple shops, and offline synchronization between independent servers.

## 16. Design completion criteria

This initial design is ready to support scaffolding when:

1. The model boundaries, app structure, transaction rules, and deployment topology are accepted.
2. Any requested architectural changes are incorporated.
3. Milestone 0 development tasks are created from the approved design.
