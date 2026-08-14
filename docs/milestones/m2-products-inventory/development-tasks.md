# Milestone 2 - Development Tasks

**Status:** Complete

**Version:** 1.0

**Inputs:** `docs/milestones/m2-products-inventory/feature-spec.md` v1.0 and `docs/milestones/m2-products-inventory/technical-design.md` v1.0

## 1. Objective

Implement and verify the owner/admin product catalog, scanner-assisted product creation and stock
receipt, reasoned stock adjustments, immutable movement history, reconciliation, and focused audit
events. Do not implement checkout, cashier quick-create, sales, returns, suppliers, or other later
milestone behavior.

## 2. Ordered task summary

| ID | Task | Depends on |
|---|---|---|
| M2-01 | Add product model, constraints, indexes, and migration | Approved M2 package |
| M2-02 | Add inventory movement and audit extensions | M2-01 |
| M2-03 | Implement M2 policies and catalog services | M2-01, M2-02 |
| M2-04 | Implement transactional inventory services | M2-01, M2-02, M2-03 |
| M2-05 | Add read-only inventory reconciliation command | M2-04 |
| M2-06 | Implement catalog forms, queries, views, and URLs | M2-03 |
| M2-07 | Implement inventory forms, views, and URLs | M2-04, M2-06 |
| M2-08 | Build Tailwind product/inventory interface and scanner behavior | M2-06, M2-07 |
| M2-09 | Complete model, constraint, service, audit, and command tests | M2-01 through M2-05 |
| M2-10 | Complete page, permission, concurrency, and asset tests | M2-06 through M2-09 |
| M2-11 | Update operator and project documentation | M2-05, M2-08, M2-10 |
| M2-12 | Run automated and production-style verification | M2-09 through M2-11 |
| M2-13 | Perform manual acceptance and record completion evidence | M2-12 |

Only one task should be treated as the active integration task at a time. Independent tests and
template work may be delegated in parallel only when their file ownership is clearly separated and
the shared migration/service contracts are already stable.

## 3. Detailed tasks

### M2-01 - Product schema

#### Work

- Replace the `catalog` placeholder with `Product` and its `CreationSource` choices.
- Add shop, normalized optional identifiers, name, PKR prices, cached stock, creator/source/review
  metadata, active state, and timestamps.
- Add conditional barcode uniqueness, case-insensitive SKU uniqueness, price checks, and list/lookup
  indexes.
- Create and inspect the catalog migration; do not add product seed data.

#### Verification

- `makemigrations --check` reports no missing model changes after migration creation.
- Migration applies and reverses on PostgreSQL.
- Database constraints reject duplicate identifiers and negative prices.
- A barcode with leading zeroes round-trips unchanged.

### M2-02 - Movement schema and audit vocabulary

#### Work

- Replace the `inventory` placeholder with append-only `InventoryMovement`.
- Add movement type choices, product/shop/actor relations, signed quantity, resulting balance,
  required reason, timestamp, constraints, ordering, and indexes.
- Add `PRODUCT_PRICE_CHANGED`, `INVENTORY_ADJUSTED`, and target type `PRODUCT` to `AuditEvent`.
- Extend the central audit writer's allowed action-to-target map.
- Create the inventory/core migration state and confirm all relationships use `PROTECT`.
- Keep movement models out of production administration and add no update/delete pathway.

#### Verification

- Receipt and adjustment constraints reject zero/invalid changes and blank reasons.
- Audit writer accepts only the two valid product mappings and retains sensitive-field rejection.
- Movement rows cannot be deleted indirectly by deleting a referenced product, actor, or shop.

### M2-03 - Policies and catalog services

#### Work

- Add active owner/admin and same-shop catalog policy helpers.
- Implement explicit identifier and text normalization shared by forms/services.
- Implement transactional create, update, activate/deactivate, and mark-reviewed services.
- Derive shop, creator, source `CATALOG`, review false, active true, and opening stock zero on create.
- Lock and revalidate actor/target records in mutations.
- Generate one focused price audit event only when selling or cost price changes.
- Convert expected validation and identifier conflicts into safe domain errors.

#### Verification

- Owner/admin same-shop operations succeed; cashier, inactive, and foreign-shop actors fail.
- Callers cannot set opening stock or ownership metadata.
- Product state operations create no movement.
- Price change and unchanged edit produce the specified audit results atomically.

### M2-04 - Inventory transaction services

#### Work

- Implement `receive_stock` and `adjust_stock` with an internal movement primitive.
- Lock actor then product and calculate from the freshly locked balance.
- Require active same-shop product and movement-specific integer validation.
- Store a default receipt reason when no note is entered.
- Update cached stock and append exactly one movement in the same transaction.
- Permit a negative adjustment result without an automatic correction.
- Record `INVENTORY_ADJUSTED` with movement ID, delta, reason, and before/after balances in the same
  transaction.
- Keep later `SALE`, `RETURN`, and `VOID` types inaccessible through M2 public services.

#### Verification

- Receipt and adjustment return the correct balance/movement.
- Invalid and stale-inactive operations leave both product and ledger unchanged.
- Simulated movement or audit failure rolls back the entire operation.
- Concurrent operations do not lose updates and each movement has the correct resulting balance.

### M2-05 - Inventory reconciliation command

#### Work

- Add `python manage.py reconcile_inventory`.
- Compare each product's cached balance with the sum of its movements across all shops.
- Produce concise mismatch lines with identifying information.
- Exit successfully for an empty/clean ledger and with `CommandError` for any mismatch.
- Do not add a fix or automatic-adjustment option.

#### Verification

- Command tests cover empty, reconciled, negative, and deliberately inconsistent balances.
- Running the command never changes product or movement records.

### M2-06 - Catalog web workflows

#### Work

- Add product form with only the five approved editable fields and friendly validation.
- Add shop-scoped list search, active/negative/review filters, stable ordering, and 50-row pagination.
- Preserve filter query parameters across pagination.
- Add create, detail, edit, status-confirmation, and mark-reviewed endpoints.
- Support safely prefilled barcode input on create without trusting it as server metadata.
- Display recent product movements on detail without exposing mutation controls.
- Enforce login, roles, same-shop visibility, POST-only mutations, CSRF, messages, and
  POST-redirect-GET.

#### Verification

- Every catalog flow matches Feature Spec sections 6 and 8.
- Cashier receives access denial and foreign-shop identifiers produce not found.
- Deactivation with non-zero/negative stock changes no inventory data.
- Duplicate-race errors return a safe form response rather than a production traceback.

### M2-07 - Inventory web workflows

#### Work

- Add the exact-barcode scan form and landing page.
- Route known active, known inactive, unknown, blank, and leading-zero scans correctly.
- Add positive receipt and signed-adjustment forms with server-calculated balance context.
- Add global newest-first movement history with type/product filtering and 50-row pagination.
- Use inventory services exclusively for writes.
- Enforce owner/admin, shop scope, CSRF, POST-redirect-GET, and inactive-product revalidation.

#### Verification

- Existing scan reaches receipt; unknown scan reaches a prefilled unsaved product form.
- A receipt/adjustment creates one movement even after the result page is refreshed.
- Negative projected/resulting stock is visible but accepted.
- Movement history displays actor, reason, type, signed change, and resulting balance.

### M2-08 - Tailwind interface and scanner behavior

#### Work

- Add Products and Inventory navigation only for owner/admin.
- Create responsive list, detail, form, confirmation, scan, receipt, adjustment, and movement
  templates using existing UI patterns.
- Format PKR consistently with two decimals and signed inventory changes with explicit signs.
- Add text-labelled inactive, needs-review, and negative-stock badges/warnings.
- Keep scanner input prominent, labelled, and focused through a local `data-autofocus` behavior.
- Add optional projected-balance updates and submit-button protection in minimal local JavaScript.
- Ensure every workflow remains usable without JavaScript.
- Compile and commit the local Tailwind output; add no CDN or remote asset.

#### Verification

- Keyboard-only navigation and visible focus work on desktop and narrow layouts.
- Negative/inactive/review meaning is not conveyed by color alone.
- Cashier navigation shows no management links.
- A clean Tailwind build includes the new templates and changes committed CSS deterministically.

### M2-09 - Domain and command automated tests

#### Work

- Add product normalization, field, constraint, metadata, and price tests.
- Add movement constraint, relationship, ordering, and append-only pathway tests.
- Add full role/same-shop catalog service tests.
- Add receipt, adjustment, negative balance, rollback, and audit tests.
- Add reconciliation command tests.
- Use PostgreSQL for database-specific constraints and transactions.

#### Verification

- Every Feature Spec data/audit acceptance criterion has a direct automated assertion.
- Tests prove failed writes create no partial product, stock, movement, or audit effect.
- Existing M0/M1 tests remain green.

### M2-10 - Web, permission, concurrency, and asset tests

#### Work

- Test all catalog and inventory URLs for anonymous, cashier, admin, owner, inactive, and
  foreign-shop access as applicable.
- Test product search/filter/pagination and retained query parameters.
- Test scan routing and every form validation/edge case.
- Test POST-only mutation endpoints, redirects, messages, and safe conflict handling.
- Add PostgreSQL transaction tests for simultaneous movement updates.
- Test navigation visibility, semantic warning labels, and rendered stock/price values.
- Run Tailwind build and production-style smoke assertions with `DEBUG=False`.

#### Verification

- Permission tests prove URLs cannot bypass hidden navigation.
- Concurrency final balance equals the sum of committed changes with no duplicate/lost movement.
- Full automated suite and Django system checks pass.

### M2-11 - Documentation

#### Work

- Update README setup/routine commands with product/inventory and reconciliation guidance where
  useful.
- Document that products begin at zero and opening stock must be received.
- Document scanner keyboard/Enter behavior and the no-internet dependency.
- Add a Milestone 2 completion-evidence file containing exact automated commands and manual-check
  setup, actions, and expected results.
- Promote planning documents from draft only after user approval; record approved versions.

#### Verification

- Commands are copyable in Windows PowerShell and use the existing Docker/Python/npm workflow.
- Documentation does not suggest direct database stock edits or movement deletion.

### M2-12 - Automated and production-style verification

#### Work

- Start the pinned PostgreSQL Docker service and apply migrations.
- Run Django deployment/system checks and migration drift checks.
- Run the full PostgreSQL test suite.
- Run the exact-pinned Tailwind production build and confirm no uncommitted generated drift.
- Run reconciliation on the development database.
- Start the application with production-style settings and smoke-test M2 pages while internet is
  unavailable or no external runtime resources are requested.
- Review the final diff for later-milestone scope and accidental secrets/generated local files.

#### Verification

- All commands and their results are recorded in completion evidence.
- Git status contains only intended tracked changes.
- No checkout, sales, returns, supplier, or public audit UI has entered the implementation.

### M2-13 - Manual acceptance and milestone closure

#### Work

- Provide the required setup/actions/expected-results checklist from Feature Spec section 12.
- Have the user test a real USB scanner when available, including an unknown leading-zero barcode.
- Verify create, receive, positive/negative correction, negative filter, movement history, duplicate
  rejection, refresh safety, reconciliation, role boundary, and disconnected-internet operation.
- Record user results and any accepted limitations in `docs/milestones/m2-products-inventory/completion.md`.
- Mark M2 complete only when automated evidence and required manual checks pass.

#### Verification

- Manual results reconcile displayed current stock with the visible movement sequence.
- Scanner and offline checks are explicitly passed, deferred for pilot, or recorded as blockers.
- The user receives a clear statement of any manual verification still required.

## 4. Explicit exclusions

- Cashier quick-create, POS order tabs, sale checkout, return, and void behavior.
- Suppliers, purchase orders, bulk catalog import, stocktakes, and warehouse transfers.
- Weighted items, batches, expiry, variants, labels, or inventory valuation.
- Automatic stock correction, reorder alerts, tax, or public audit-history screens.
- Deployment/backup packaging beyond the proportional M2 development smoke checks.

## 5. Approval and completion rules

The user approved these tasks with `docs/milestones/m2-products-inventory/feature-spec.md` and `docs/milestones/m2-products-inventory/technical-design.md` on 2026-08-03.
They are ready for implementation in the listed dependency order.

Milestone 2 is complete only when M2-01 through M2-13 pass, completion evidence is recorded, and
the user is told exactly which real-scanner/offline checks were performed or remain outstanding.

## 6. Implementation progress

- M2-01 through M2-13 are complete with evidence recorded in `docs/milestones/m2-products-inventory/completion.md`.
- The user confirmed the required scanner, interface, offline, and reconciliation checks on
  2026-08-03.
