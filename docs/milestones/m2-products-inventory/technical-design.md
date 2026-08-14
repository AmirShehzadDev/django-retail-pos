# Milestone 2 - Technical Design

**Status:** Approved

**Version:** 1.0

**Feature specification:** `docs/milestones/m2-products-inventory/feature-spec.md` v1.0

**Project design:** `docs/architecture/technical-design.md` v0.5

## 1. Purpose and scope

This refinement translates the proposed Milestone 2 behavior into concrete Django models,
constraints, policies, services, transaction boundaries, forms, views, URLs, templates, commands,
and tests.

The user requested the feature specification, technical design, and task plan as one sequential
planning package and approved that package before implementation.

## 2. Existing foundation

Milestone 2 extends rather than replaces:

- Django 5.2 LTS and server-rendered templates;
- PostgreSQL 16 in the pinned Docker service;
- the custom `accounts.User` with owner/admin/cashier roles and shop ownership;
- `core.Shop`, fixed to PKR and `Asia/Karachi`;
- authenticated, CSRF-protected M1 pages and role policies;
- the immutable-by-application `core.AuditEvent` writer; and
- the exact-pinned local Tailwind build and minimal `static/js/app.js`.

The existing empty `catalog` and `inventory` applications become the owners of product and stock
behavior. No new third-party Python or JavaScript dependency is required.

## 3. Proposed code structure

```text
apps/
|-- catalog/
|   |-- forms.py
|   |-- models.py
|   |-- policies.py
|   |-- services.py
|   |-- urls.py
|   `-- views.py
|-- inventory/
|   |-- forms.py
|   |-- management/commands/reconcile_inventory.py
|   |-- models.py
|   |-- services.py
|   |-- urls.py
|   `-- views.py
`-- core/
    |-- audit.py
    `-- models.py

templates/
|-- catalog/
|   |-- product_confirm_status.html
|   |-- product_detail.html
|   |-- product_form.html
|   `-- product_list.html
`-- inventory/
    |-- adjustment_form.html
    |-- movement_list.html
    |-- receipt_form.html
    `-- scan.html

tests/
|-- catalog/
`-- inventory/
```

Catalog services own product mutations. Inventory services are the only application code allowed
to change current stock or create movement records. Views never call `Product.objects.update()` for
business mutations.

## 4. Data model

### 4.1 `catalog.Product`

| Field | Django type | Rules |
|---|---|---|
| `shop` | `ForeignKey(core.Shop, PROTECT)` | Required; indexed through constraints/queries |
| `barcode` | `CharField(64, null=True, blank=True)` | Trimmed; blank becomes `NULL`; leading zeroes retained |
| `sku` | `CharField(64, null=True, blank=True)` | Trimmed; blank becomes `NULL` |
| `name` | `CharField(200)` | Required after trimming |
| `selling_price` | `DecimalField(12, 2)` | Required and non-negative |
| `cost_price` | `DecimalField(12, 2, null=True, blank=True)` | Optional and non-negative |
| `stock_on_hand` | `BigIntegerField(default=0)` | Service-controlled; negative allowed |
| `created_by` | `ForeignKey(accounts.User, PROTECT)` | Required; creator must belong to product shop |
| `creation_source` | `CharField` with choices | `CATALOG` or future `POS_QUICK_CREATE` |
| `needs_review` | `BooleanField(default=False)` | Future quick-create uses `True` |
| `is_active` | `BooleanField(default=True)` | Deactivation replaces deletion |
| `created_at` | `DateTimeField(auto_now_add=True)` | Server timestamp |
| `updated_at` | `DateTimeField(auto_now=True)` | Server timestamp |

The default ordering is case-insensitive name followed by ID at the query layer. Model string
representation uses the product name and never assumes a barcode exists.

Database constraints:

- conditional unique `(shop, barcode)` where barcode is not `NULL`;
- conditional functional unique `(shop, Lower(sku))` where SKU is not `NULL`;
- `selling_price >= 0`;
- `cost_price IS NULL OR cost_price >= 0`; and
- catalog creation cannot be forced to a stock value through the product service.

Indexes support `(shop, barcode)`, `(shop, is_active, name)`, `(shop, needs_review)`, and the list
filters. PostgreSQL's ordinary B-tree index serves exact barcode scan lookup. Partial name/SKU
search is acceptable at one-shop MVP scale; trigram search is intentionally deferred.

Form and service normalization removes only surrounding whitespace. It must not cast a barcode to
a number, change case, remove punctuation, or strip leading zeroes. Form validation provides useful
duplicate errors; database constraints handle races.

`stock_on_hand` is a cached current balance for fast list and checkout reads. It is not independently
editable. Its value changes only in the same transaction that appends the corresponding movement.

### 4.2 `inventory.InventoryMovement`

| Field | Django type | Rules |
|---|---|---|
| `shop` | `ForeignKey(core.Shop, PROTECT)` | Required and equal to product shop |
| `product` | `ForeignKey(catalog.Product, PROTECT)` | Required |
| `movement_type` | `CharField` with choices | M2 writes `RECEIPT` or `ADJUSTMENT` |
| `quantity_change` | `BigIntegerField` | Signed, non-zero; receipt must be positive |
| `balance_after` | `BigIntegerField` | Product balance immediately after this movement |
| `actor` | `ForeignKey(accounts.User, PROTECT)` | Active same-shop user at write time |
| `reason` | `CharField(500)` | Always non-empty; adjustment uses submitted reason |
| `created_at` | `DateTimeField(auto_now_add=True)` | Server timestamp |

The choices also reserve `SALE`, `RETURN`, and `VOID` names defined by the approved project design,
but no M2 endpoint can create those types. Later milestone services will call the same internal
inventory primitive.

Database checks require:

- `quantity_change != 0`;
- `RECEIPT` has `quantity_change > 0`; and
- `reason != ''`.

Shop/product/actor consistency requires joined-record checks and is enforced by the service.
Indexes cover `(shop, -created_at)`, `(product, -created_at)`, and
`(shop, movement_type, -created_at)`.

Movement rows are append-only application records:

- there is no update or delete service;
- there is no edit/delete URL or form;
- the model is not registered for production administration;
- all foreign keys that could remove a referenced record use `PROTECT`; and
- code-review and tests reject any movement mutation path.

Corrections are represented by a later `ADJUSTMENT`, never by rewriting history. Direct database
administrator access remains an operational trust boundary and is protected through restricted
database credentials and backups rather than a database trigger in this compact MVP.

### 4.3 `core.AuditEvent` extensions

Add actions:

- `PRODUCT_PRICE_CHANGED`; and
- `INVENTORY_ADJUSTED`.

Add target type `PRODUCT` and map both actions to it in `core.audit._ALLOWED_TARGETS`.

The price event stores changed selling/cost values only. The adjustment event stores
`movement_id`, `quantity_change`, `reason`, `balance_before`, and `balance_after`. It does not copy
the entire product record. Existing sensitive-key rejection and same-shop actor validation remain
unchanged.

## 5. Authorization policies

Add catalog policy helpers:

- `can_manage_catalog(actor)`;
- `can_view_product(actor, product)`;
- `can_edit_product(actor, product)`; and
- `can_change_product_stock(actor, product)`.

An actor must be authenticated, active, have a shop, and have role owner or admin. Target helpers
also require the same shop. Cashiers always return false for M2 management actions.

Views use these helpers for early denial, but every mutation service locks and revalidates the
actor and target. Querysets are shop-scoped before `get_object_or_404`, so a foreign-shop ID appears
not found rather than disclosing record existence.

## 6. Business services

### 6.1 Catalog services

```text
create_product(actor, name, barcode, sku, selling_price, cost_price)
update_product(actor, product_id, name, barcode, sku, selling_price, cost_price)
set_product_active(actor, product_id, is_active)
mark_product_reviewed(actor, product_id)
```

Shared behavior:

- lock and revalidate the active actor using the M1 pattern;
- normalize input explicitly;
- derive shop, creator, source, review state, active state, and initial stock server-side;
- call model/constraint validation before saving; and
- translate expected duplicate conflicts into validation errors suitable for the form.

`update_product` locks the product. It records one `PRODUCT_PRICE_CHANGED` event only when selling
or cost price differs. The product update and event share one transaction.

`set_product_active` locks the product and changes no stock. `mark_product_reviewed` is valid and
idempotent only for a same-shop product; it changes `True` to `False` without rewriting creator or
source.

### 6.2 Inventory services

Public services:

```text
receive_stock(actor, product_id, quantity, note="")
adjust_stock(actor, product_id, quantity_change, reason)
```

An internal `_apply_movement(...)` primitive receives an already locked product, validated actor,
allowed movement type, signed quantity, and reason. It computes the new balance, writes
`stock_on_hand`, and creates exactly one movement.

M2 services do not expose a general caller-selectable movement type. This prevents a form or future
caller from fabricating a sale, return, or void.

For receipt, a blank note becomes `Manual stock receipt`. For adjustment, blank reason is invalid.
The adjustment service records its audit event after creating the movement but inside the same
atomic block.

### 6.3 Service return values and errors

Write services return the saved domain object and any created movement needed for redirect/messages.
They raise:

- `PermissionDenied` for invalid actor or cross-role action;
- `Product.DoesNotExist` or a not-found translation for inaccessible targets;
- `ValidationError` for invalid business input or inactive product; and
- a controlled conflict validation error for identifier races.

Views map validation errors back to forms and never duplicate service rules.

## 7. Transaction and concurrency design

### Product mutations

Each catalog mutation uses `transaction.atomic()` and locks records in this order:

1. active actor;
2. existing product, when applicable; and
3. audit insert, when required.

The database unique constraint is authoritative for simultaneous identifier assignments.

### Receipt and adjustment

Each stock mutation uses one PostgreSQL transaction:

1. lock and validate the active actor;
2. lock the same-shop product with `select_for_update()`;
3. reject it if inactive;
4. validate movement-specific input;
5. compute `balance_after` from the freshly locked `stock_on_hand`;
6. update current stock;
7. append one movement containing the same resulting balance;
8. append the adjustment audit event when applicable; and
9. commit all effects together.

Consistent actor-then-product locking and a deterministic product-ID order for later multi-product
operations avoid deadlocks. The product row lock prevents lost updates. A failed movement or audit
insert rolls back the cached balance update.

No generic idempotency key is added for an ordinary M2 form. POST-redirect-GET, a disabled submit
button after submission, and database transactions cover routine use. Checkout obtains a stronger
domain idempotency boundary in its own milestone.

## 8. Forms and validation

### Catalog forms

- `ProductForm` exposes only name, barcode, SKU, selling price, and cost price.
- `ProductScanForm` has one barcode text field and uses exact lookup after trimming.
- `ProductSearchForm` represents query/filter parameters and treats invalid filter values as the
  safe default rather than raising a server error.

The product form performs friendly same-shop duplicate checks. It must still handle a service/database
conflict caused by a concurrent request.

### Inventory forms

- `StockReceiptForm`: positive integer `quantity`, optional 500-character `note`.
- `StockAdjustmentForm`: signed non-zero integer `quantity_change`, required 500-character `reason`.
- `MovementFilterForm`: product search and movement type.

Projected balances are computed server-side for the initial page and after validation errors. Small
local JavaScript may update the preview while typing, but the service ignores client calculations.

Money fields use Django decimal fields and render with two-place examples. Quantity fields use text
or number inputs configured to accept integer steps and signed adjustment values without weakening
server validation.

## 9. Views and URLs

### Catalog URLs

| Method | URL | Name | Purpose |
|---|---|---|---|
| GET | `/products/` | `catalog:product_list` | Search/filter/paginate products |
| GET/POST | `/products/new/` | `catalog:product_create` | Normal or prefilled creation |
| GET | `/products/<id>/` | `catalog:product_detail` | Product and recent movement detail |
| GET/POST | `/products/<id>/edit/` | `catalog:product_edit` | Edit allowed catalog fields |
| GET/POST | `/products/<id>/status/` | `catalog:product_status` | Confirm deactivate/reactivate |
| POST | `/products/<id>/review/` | `catalog:product_review` | Clear needs-review state |

The create GET may accept `?barcode=` only from the inventory unknown-scan redirect. It passes
through the same normalization and validation as manual input.

### Inventory URLs

| Method | URL | Name | Purpose |
|---|---|---|---|
| GET | `/inventory/scan/` | `inventory:scan` | Exact barcode lookup and scan landing |
| GET/POST | `/inventory/products/<id>/receive/` | `inventory:receive` | Record positive receipt |
| GET/POST | `/inventory/products/<id>/adjust/` | `inventory:adjust` | Record signed correction |
| GET | `/inventory/movements/` | `inventory:movement_list` | Filtered immutable history |

The scan form uses GET because it is read-only. A known active product redirects to receipt; a known
inactive product redirects to detail with a message; an unknown value redirects to product creation
with a URL-encoded prefill. Empty input stays on the scan page with an error.

All mutation responses use POST-redirect-GET. Status/review actions require POST even if a caller
constructs the URL manually. The project URL configuration includes both app namespaces.

## 10. Queries and pagination

Product list starts with `Product.objects.filter(shop=request.user.shop)` and uses `Q` expressions
for the combined search. Search/filter values are reapplied to paginator links. Page size is 50.

Product detail preloads creator and a bounded recent-movement list. The global movement list uses
`select_related("product", "actor")`, shop scoping, newest-first ordering, and a page size of 50.
Filters are applied before pagination.

No view trusts a posted `shop`, `actor`, `stock_on_hand`, `balance_after`, `creation_source`, or
`needs_review` value.

## 11. Templates, Tailwind, and scanner interaction

Existing layout, flash messages, form partials, focus styles, minimum touch targets, and responsive
patterns are reused.

Add owner/admin navigation links for Products and Inventory. Cashier navigation has neither link.
The home page may add management shortcuts for owner/admin only.

Important presentation rules:

- prices render as `PKR 1,234.00`;
- signed movement changes include `+` or `-`;
- negative balances use text and an icon/label as well as color;
- inactive and needs-review states use explicit badges;
- the scan field is the page's primary control and receives focus using a `data-autofocus`
  attribute; and
- create/edit forms never render current stock as an editable input.

Minimal local JavaScript may focus/select the scanner field, update projected-balance text, and
disable a submit button after submission. The flows remain usable with JavaScript disabled by
typing the barcode and pressing Enter or submitting the form.

Tailwind is compiled through the existing pinned toolchain. No CDN, remote font, scanner library,
or frontend framework is added.

## 12. Reconciliation command

Add:

```powershell
python manage.py reconcile_inventory
```

The command groups movements by product, treats no movement as zero, and compares the sum of
`quantity_change` with `stock_on_hand`. It prints product ID/name and both values for every mismatch.
It exits zero for a clean ledger and raises `CommandError` for any mismatch.

The command is read-only: it has no `--fix` option. It checks all shops in the database even though
the current UI exposes one shop.

## 13. Migration plan

1. Add `catalog.Product` with constraints and indexes.
2. Add `inventory.InventoryMovement` with constraints and indexes.
3. Extend audit choices/target type in the relevant migration state.

There is no product backfill because M2 starts from an empty catalog. Migrations must run forward
and backward against the development database. No seed products or stock movements are committed.

## 14. Test strategy

### Model and constraint tests

- blank identifier normalization and leading-zero preservation;
- conditional barcode uniqueness and case-insensitive SKU uniqueness;
- price checks and nullable cost price;
- allowed negative stock;
- movement quantity/type/reason checks; and
- protected relationships.

### Service tests

- derived product metadata and zero opening stock;
- product update and focused price audit behavior;
- deactivate/reactivate and review behavior;
- receipt/adjustment balance and movement creation;
- negative adjustment acceptance;
- rollback when movement/audit creation fails;
- inactive and cross-shop rejection; and
- simultaneous stock mutations proving no lost update and correct `balance_after` sequence.

### View, form, and permission tests

- owner/admin success and cashier denial for every M2 endpoint;
- shop-scoped 404 behavior;
- searches, filters, sorting, pagination, and retained query string;
- known, inactive, unknown, blank, and leading-zero scan cases;
- every validation rule and friendly duplicate error;
- POST-only mutations, CSRF expectation, redirect-after-write, and messages;
- movement history has no mutation control; and
- role-aware navigation and negative/review presentation.

### Command and asset tests

- clean reconciliation, empty catalog, and discrepancy failure;
- system checks and migrations;
- Tailwind production build contains the M2 templates' required classes; and
- production-style page smoke tests use PostgreSQL with `DEBUG=False`.

SQLite is not an accepted substitute for constraint or concurrency verification.

## 15. Implementation sequence

1. Add models, migrations, audit choices, and constraint tests.
2. Add role policies and catalog services.
3. Add inventory transaction services and reconciliation command.
4. Add forms, shop-scoped views, URLs, queries, and pagination.
5. Add accessible Tailwind templates, navigation, and minimal scanner interaction.
6. Complete service, concurrency, permission, page, command, and asset tests.
7. Run PostgreSQL, migration, Tailwind, production-style, and manual verification.

## 16. Explicit technical exclusions

- A REST API, SPA framework, WebSockets, service worker, or scanner SDK.
- Database full-text/trigram search at current one-shop volume.
- Database triggers for ledger immutability.
- Opening-balance fields or direct stock editing.
- Product import, supplier, purchase-order, stocktake, and valuation schemas.
- Order-linked movement fields before the relevant order/return migrations.
- Cashier product quick-create and its audit event before Milestone 3.
- Audit-history screen before Milestone 6.

## 17. Approval record

The user approved this design together with `docs/milestones/m2-products-inventory/feature-spec.md` and `docs/milestones/m2-products-inventory/development-tasks.md` on
2026-08-03. Material behavior changes must be resolved in the approved feature specification before
the affected M2 code is written.
