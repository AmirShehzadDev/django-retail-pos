# Single-Shop Retail POS - Delivery Milestones

**Source:** `docs/product/mvp-requirements.md`
**Status:** Approved scope, revised for requirements version 1.7

**Version:** 1.7
**Approach:** Deliver one testable capability at a time. A milestone is complete only when its exit criteria pass.

## Confirmed project decisions

- Tax functionality is excluded from the MVP; selling prices are final prices.
- Currency is `PKR`.
- Timezone is `Asia/Karachi`.
- The host checkout computer uses Windows.
- PostgreSQL runs in a pinned official Docker container, isolated from other local database installations.
- Checkout may continue into negative stock after a visible, audited acknowledgement.
- Checkout records total, cash received, and visible signed change without a round-off reason or availability choice.
- Cashiers may process linked returns and quick-create unknown products.
- Held drafts are checkout-terminal scoped and survive cashier changes.
- A populated draft is cleared in place after confirmation without a reason or audit record; an
  eligible empty tab closes immediately without confirmation.

The MVP requirements and milestone scope are approved.

## Milestone 0 - Technical foundation

**Goal:** Produce a working Django foundation that later milestones can extend safely.

**Development tasks:** `docs/milestones/m0-foundation/development-tasks.md`

**Completion evidence:** `docs/milestones/m0-foundation/completion.md`

### Deliverables

- Technical design covering models, relationships, status transitions, permissions, and transactional stock rules.
- Django 5.2 LTS project pinned to the latest compatible `5.2.x` patch.
- Docker Compose PostgreSQL development database and environment-based settings.
- Django apps: `core`, `accounts`, `catalog`, `inventory`, and `sales`.
- Initial `Shop` and `Terminal` boundaries in the domain model.
- Custom user model created before the first database migration.
- Base Django template, locally stored CSS/JavaScript, and navigation shell.
- Initial automated-test configuration and project setup instructions.

### Exit criteria

- A fresh installation can create the database, run migrations, and start the application.
- No page requires an internet connection or CDN asset.
- Automated tests run successfully.

## Milestone 1 - Authentication, roles, and shop settings

**Goal:** Ensure every operation is performed by an authorized, identifiable user.

**Feature specification:** `docs/milestones/m1-users/feature-spec.md`

**Technical refinement:** `docs/milestones/m1-users/technical-design.md`

**Development tasks:** `docs/milestones/m1-users/development-tasks.md`

**Completion evidence:** `docs/milestones/m1-users/completion.md`

### Deliverables

- Login and logout.
- Owner, admin, and cashier roles.
- Owner management of admins.
- Admin management of cashiers.
- User activation/deactivation.
- Single-shop settings for name, `PKR` currency, and `Asia/Karachi` timezone.
- Local Tailwind CSS build pipeline and styled authentication/management templates.
- Server-side permission checks and relevant audit events.

### Exit criteria

- Each role can access only its permitted pages and actions.
- A cashier cannot manage users, normal catalog/inventory workflows, or voids, but has explicit permissions for POS quick-create and linked returns.
- An inactive user cannot log in.
- Permission tests pass.

## Milestone 2 - Product catalog and inventory

**Goal:** Allow the shop to load products and establish accurate opening stock.

**Status:** Complete on 2026-08-03

**Planning documents:** [Feature specification](../milestones/m2-products-inventory/feature-spec.md),
[technical design](../milestones/m2-products-inventory/technical-design.md), and
[development tasks](../milestones/m2-products-inventory/development-tasks.md) (approved)

### Deliverables

- Product create, edit, search, list, and deactivate workflows.
- Optional barcode with conditional uniqueness and leading zero preservation.
- Unknown-barcode product creation with the barcode prefilled.
- Product creator, creation source, and needs-admin-review state.
- Manual stock receipts.
- Positive and negative stock adjustments with required reasons.
- Immutable inventory movement history.
- Negative-stock and needs-review product filters.

### Exit criteria

- An admin can scan an existing product and receive stock.
- An admin can create a product after scanning an unknown barcode.
- Stock shown for every product reconciles with its movement history.
- Duplicate non-empty barcodes and invalid adjustments are rejected.
- Negative balances remain visible and reconcile with their movement history.
- Catalog and inventory tests pass.

## Milestone 3 - Active POS orders

**Goal:** Give the cashier a fast, persistent checkout workspace.

**Status:** Complete on 2026-08-04

**Planning documents:** [Feature specification](../milestones/m3-active-orders/feature-spec.md),
[technical design](../milestones/m3-active-orders/technical-design.md), and
[development tasks](../milestones/m3-active-orders/development-tasks.md) (independently reviewed; implementation-ready)

**Completion evidence:** [Automated evidence and required user checklist](../milestones/m3-active-orders/completion.md)

### Deliverables

- Up to three active order tabs per checkout terminal.
- Always-ready barcode input suitable for a USB scanner.
- Product search fallback.
- Cashier quick-create for an unknown barcode using barcode, name, and selling price, with audit and admin-review flag.
- Add-on-scan, quantity editing, and line removal.
- Line and final total calculations.
- Database-persisted draft orders.
- Cross-cashier resume on the same terminal with takeover auditing.
- Retained `DISCARDED` history was delivered in this historical milestone, but its active behavior
  is superseded by the approved Milestone 4.2 Clear order and Close tab refinement.
- Unit price captured when the item is added and protected from later silent catalog changes.

### Exit criteria

- Repeated scans increase item quantity correctly.
- Three separate terminal orders can be created and resumed.
- Drafts survive refresh, cashier change, logout, browser restart, and application restart.
- Draft orders do not change inventory.
- Totals are calculated using fixed-precision decimal values.
- Quick-created products are immediately sellable, audited, and visible in the admin review filter.

## Milestone 3.1 - Cashier read-only catalogue enhancement

**Goal:** Let cashiers inspect same-shop checkout product information without gaining catalog or
inventory management permissions.

**Status:** Complete on 2026-08-04

**Feature specification:** [Cashier read-only catalogue](../milestones/m3.1-cashier-catalogue/feature-spec.md)

**Technical refinement:** [Cashier read-only catalogue design](../milestones/m3.1-cashier-catalogue/technical-design.md)

**Development tasks:** [Cashier read-only catalogue tasks](../milestones/m3.1-cashier-catalogue/development-tasks.md)

**Completion evidence:** [Automated evidence and user checklist](../milestones/m3.1-cashier-catalogue/completion.md)

### Planned deliverables

- Cashier-visible Products navigation and home action.
- Same-shop read-only product search, filters, pagination, and safe detail view.
- Selling price, barcode/SKU, active status, and informational current stock visibility.
- Server-enforced exclusion of cost, review, movement, audit, and all mutation capabilities.
- No database migration, inventory effect, POS draft mutation, or Milestone 4 behavior.

### Exit criteria

- Cashier safe-field and mutation-denial tests pass without owner/admin regression.
- Cross-shop products remain undisclosed.
- User verifies the read-only list/detail presentation and offline behavior.

## Milestone 4 - Cash checkout and order history

**Goal:** Complete a real cash sale safely from scan to recorded order.

### Deliverables

- Cash-received input and change calculation.
- Signed change calculated as cash received minus total; above-total and below-total cash are permitted without a reason or change-availability choice.
- Atomic creation of order, order items, payment, and inventory movements.
- Stock locking and final availability check during checkout.
- Insufficient-stock warning and audited cashier acknowledgement without blocking the sale.
- Permanent human-readable order numbers.
- Historical product, price, and barcode snapshots.
- Fresh order after successful checkout.
- Paginated order history with product/amount search, non-zero-change filter/badge, and prominently highlighted signed change.

### Exit criteria

- The complete flow works: login, scan, calculate, accept cash, complete sale, and reduce stock.
- A failed checkout makes no partial database or inventory changes.
- Concurrent attempts produce consistent balances and one movement per sold line; an acknowledged shortage may result in a negative balance.
- Changing a product after a sale does not change the completed order.
- Orders appear newest first and respect role-based visibility.
- Positive and negative change reconcile with payment and order totals and remain visible.

**Internal release gate:** At this point the system can run complete test sales, but it is not ready for live use until returns, backups, and deployment are finished.

## Milestone 4.2 - Clear order and Close tab refinement

**Goal:** Remove an unwanted customer basket quickly without creating false order history or
leaving the POS workspace.

**Status:** Complete; user frontend acceptance confirmed on 2026-08-06

**Planning documents:** [Feature specification](../milestones/m4.2-clear-orders/feature-spec.md) and
[technical design](../milestones/m4.2-clear-orders/technical-design.md)

**Completion evidence:** [Automated evidence and required user checklist](../milestones/m4.2-clear-orders/completion.md)

### Deliverables

- **Clear order** for populated drafts, with an in-POS confirmation dialog.
- Visible **Keep order** and **Clear order** dialog actions; `Enter` confirms and `Escape` cancels.
- In-place removal of all lines while retaining the same empty draft tab.
- **Close tab** for empty drafts, immediate when at least one other active tab remains.
- No discard reason, retained discarded order, audit event, or inventory effect.
- Stale-version and concurrent-request protection for both operations.

### Exit criteria

- Clearing a populated draft leaves the same tab selected, empty, and ready to scan.
- Cancelling by `Escape` or **Keep order** preserves every line and total.
- Closing an eligible empty tab selects another existing tab without creating a replacement.
- The only remaining active tab cannot be closed.
- Neither operation creates order history, audit history, payment, or inventory movement.

## Milestone 4.3 - Unified Products and Stock workspace

**Goal:** Reduce routine catalog and inventory work to one role-aware screen without weakening the
stock ledger or cashier permissions.

**Status:** Complete; user frontend acceptance confirmed on 2026-08-06

**Planning documents:** [Feature specification](../milestones/m4.3-products-stock/feature-spec.md),
[technical design](../milestones/m4.3-products-stock/technical-design.md), and
[development tasks](../milestones/m4.3-products-stock/development-tasks.md) (planning review passed)

**Completion evidence:** [Automated evidence and required user checklist](../milestones/m4.3-products-stock/completion.md)

### Deliverables

- One Products & Stock workspace with scanner/search, filters, pagination, and role-safe details.
- Manager create, receive, edit, adjust, status, review, and recent-history dialog workflows.
- Optional Quantity received now during manager product creation, recorded as a real atomic receipt.
- Cashier read-only access without cost, review, movement-history, or mutation exposure.
- Consolidated navigation/home actions with secure full-page and movement-history fallbacks.

### Exit criteria

- Routine manager product and stock work is available from one workspace without normal page
  navigation.
- Product-plus-optional-receipt, receipts, and adjustments preserve ledger, audit, permission, and
  concurrency guarantees.
- Exact barcode and general search behavior remain safe and same-shop scoped.
- Cashier read-only regressions, focused catalog/inventory tests, and full project tests pass.
- The user verifies actual dialog, focus/scanner, responsive, and offline frontend behavior.

## Milestone 4.4 - Keyboard-first checkout dialog

**Goal:** Complete a cash sale quickly from the scanner using a compact payment dialog.

**Status:** Implementation complete; user frontend acceptance pending

**Planning documents:** [Feature specification](../milestones/m4.4-checkout-dialog/feature-spec.md),
[technical design](../milestones/m4.4-checkout-dialog/technical-design.md), and
[development tasks](../milestones/m4.4-checkout-dialog/development-tasks.md) (planning review passed)

**Completion evidence:** [Automated evidence and required user checklist](../milestones/m4.4-checkout-dialog/completion.md)

### Deliverables

- Scanner Tab shortcut to Complete sale without changing normal keyboard navigation elsewhere.
- Native checkout dialog with line preview, Order total, total-prefilled Cash received, signed
  Change, and keyboard-first completion.
- Cancel/Escape focus restoration and a no-JavaScript checkout fallback.

### Exit criteria

- The approved scanner -> Tab -> Enter -> keypad -> Tab -> Enter flow completes exactly one sale.
- Existing checkout, stock, signed-change, recent-sale, replacement-draft, and permission behavior
  remains correct.
- Automated gates pass and the user verifies actual focus, scanner, keypad, dialog, and layout.

## Milestone 5 - Returns and voids

**Goal:** Correct mistakes and handle common customer returns without altering history.

**Status:** Complete; user frontend acceptance pending

**Feature specification:** [Returns and voids](../milestones/m5-returns-voids/feature-spec.md)

**Technical design:** [Returns and voids technical design](../milestones/m5-returns-voids/technical-design.md)

**Development tasks:** [Returns and voids development tasks](../milestones/m5-returns-voids/development-tasks.md)

**Completion evidence:** [Milestone 5 evidence](../milestones/m5-returns-voids/completion.md)

### Deliverables

- Owner/admin-only full-order void with required reason and recorded cash refund.
- Cashier, admin, and owner full/partial returns linked to the original order.
- Optional return reason/note; void reasons remain required.
- Read-only shop-wide order lookup by order number, product/barcode, date, cashier, and amount.
- Remaining-returnable-quantity enforcement.
- `RESTOCK` and `DAMAGED/NOT_RESTOCKED` handling.
- Cash refund recording.
- Inventory reversal movements and immutable return records.
- Completed, voided, partially returned, and returned statuses.
- Mutual exclusion between voids and returns.

### Exit criteria

- Returned quantity can never exceed the remaining sold quantity.
- A return cannot be completed without an identifiable original order.
- Restocked returns increase sellable stock exactly once.
- Damaged returns do not increase sellable stock.
- Voids and returns retain the original sale and record actor and time; voids require a reason and
  returns may record an optional reason/note.
- Order, return, payment, and inventory figures reconcile in automated tests.

## Milestone 6 - Daily summary and audit trail

**Goal:** Give the owner a trustworthy daily operational view.

**Feature specification:** [Daily summary and audit trail](../milestones/m6-reporting-audit/feature-spec.md)

**Technical design:** [Daily summary and audit technical design](../milestones/m6-reporting-audit/technical-design.md)

**Development tasks:** [Daily summary and audit development tasks](../milestones/m6-reporting-audit/development-tasks.md)

**Completion evidence:** [Milestone 6 evidence](../milestones/m6-reporting-audit/completion.md)

### Deliverables

- Daily gross sales, returns, voids, net sales, order count, cash collected/refunded, non-zero-change order count, and signed change total.
- Negative-stock and cashier-created-product review filters.
- Audit history for user changes, price changes, stock adjustments, quick-created products, stock-shortage acknowledgements, draft takeover, voids, and returns.
- Admin/owner-only access to reports and audit records.

### Exit criteria

- Daily figures reconcile with completed orders and reversal transactions.
- Reports remain correct for partial returns and returns made on a later date.
- Positive and negative change is visible on orders and reconciles with the selected day's totals.
- Audit records identify the actor, action, target, time, and relevant changes.

## Milestone 7 - Offline deployment and shop pilot

**Goal:** Install a recoverable system that operates reliably without internet access.

**Status:** Implementation complete; required real-host verification and supervised pilot pending

**Planning documents:** [Feature specification](../milestones/m7-offline-deployment/feature-spec.md),
[technical design](../milestones/m7-offline-deployment/technical-design.md), and
[development tasks](../milestones/m7-offline-deployment/development-tasks.md) (planning review passed)

**Completion evidence:** [Automated evidence and required shop checklist](../milestones/m7-offline-deployment/completion.md)

### Deliverables

- Production-capable local application service with automatic startup.
- Local PostgreSQL Docker container and locally bundled runtime assets/images.
- Daily automated backups with seven-day retention.
- Documented and tested backup restoration.
- Local-network configuration documented for a future second checkout computer.
- Real USB barcode-scanner testing.
- Pilot checklist and operating instructions for the owner, admins, and cashiers.

### Exit criteria

- The application starts successfully after a computer restart.
- Core workflows work while the internet is disconnected.
- A backup is restored successfully to a clean test installation.
- Scanner, quick-create, signed-change, cashier-handoff, concurrent-checkout, negative-stock, linked-return, void, and inventory-reconciliation scenarios pass.
- The shop completes a supervised pilot without unexplained stock or cash discrepancies.

## Milestone 7.1 - Local startup and deployment hardening

**Goal:** Make the one-computer Windows deployment easier to start and safer around local
configuration and backups.

**Status:** Implementation and automated verification complete; pending user verification and
versioned release packaging

**Planning documents:** [Feature specification](../milestones/m7.1-local-startup/feature-spec.md),
[technical design](../milestones/m7.1-local-startup/technical-design.md), and
[development tasks](../milestones/m7.1-local-startup/development-tasks.md) (planning review passed)

### Deliverables

- Friendly loopback-only `http://retailpos:8000` address.
- Idempotent Windows hostname configuration and desktop launcher.
- Strict protection against Docker Compose interpolation in `.env` secrets.
- Backup container discovery that cannot consume warning text as an identifier.
- Versioned `1.0.1` offline update package after verification and release approval.

### Exit criteria

- Automated deployment, documentation, formatting, and regression checks pass.
- The user verifies Windows elevation, hosts resolution, double-click startup, Chrome opening,
  restart behavior, and a successful database backup on the shop computer.

## MVP completion

The MVP is complete when Milestones 0-7 pass their exit criteria and every acceptance criterion in `docs/product/mvp-requirements.md` has evidence from an automated test, deployment check, or documented pilot result.

## Recommended future enhancement - Product performance and gross profit

**Status:** Recommendation only; not approved MVP scope and not scheduled for implementation.

Provide an owner/admin report over a selectable date range that helps identify:

- products with the highest gross and net units sold;
- gross revenue, return/void deductions, and net revenue by product;
- estimated cost of goods, gross profit, and gross margin by product; and
- products whose missing cost prevents a reliable profit calculation.

Before profit reporting is implemented, completed order lines should capture a nullable immutable
`unit_cost` snapshot at sale time. The report must not calculate historical profit using a product's
current cost, because later cost changes would rewrite the apparent profitability of old sales.
Existing sales without a captured cost should show profit as **Unknown**, not zero or an estimate.

The first version should use the same event-date rules as Milestone 6, provide a sortable table
without charts or exports, and describe profit as **gross profit** only. Rent, salaries, utilities,
tax, and other operating expenses remain outside that calculation.

If this recommendation is approved later, it may be planned as an optional pre-pilot refinement or
as a post-MVP milestone. It must follow the normal feature specification, technical design,
development-task, and planning-review workflow before implementation.
