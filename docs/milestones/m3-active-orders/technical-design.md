# Milestone 3 - Technical Design

**Status:** Planning reviewed; implementation-ready

**Version:** 1.1

**Approved:** 2026-08-03
**Planning review passed:** 2026-08-04

**Feature specification:** `docs/milestones/m3-active-orders/feature-spec.md` v1.1

**Project design:** `docs/architecture/technical-design.md` v0.5

> **Historical document:** This describes the Milestone 3 implementation delivered in August
> 2026. Its retained `DISCARDED` workflow is superseded for future behavior by
> [Milestone 4.2](../m4.2-clear-orders/feature-spec.md) and its
> [technical design](../m4.2-clear-orders/technical-design.md). Legacy schema remains compatible, but new POS
> actions will clear a populated draft or close an eligible empty tab without an audit record.

## 1. Purpose and scope

This refinement translates the approved Milestone 3 behavior into concrete Django 5.2 and
PostgreSQL models, constraints, indexes, authorization policies, service APIs, lock ordering,
transactions, forms, views, URLs, templates, local JavaScript interactions, migrations, and tests.

Milestone 3 creates persistent terminal-scoped `DRAFT` orders and retained `DISCARDED` orders. It
adds checkout product lookup, atomic restricted quick-create, captured draft prices, quantity and
removal operations, explicit cross-cashier takeover, and optimistic draft versioning.

It does not create payments, order numbers, stock movements, round-offs, completed sales, or order
history. The schema includes only fields required to preserve approved M3 data safely; Milestone 4
will add its own completion fields and behavior through a separate reviewed migration.

## 2. Existing foundation

Milestone 3 extends rather than replaces the completed M0-M2 application:

- Django 5.2 LTS, PostgreSQL 16, server-rendered templates, sessions, CSRF, and local static assets;
- `core.Shop` and bootstrap-created `core.Terminal`, with default code `TILL-1`;
- `accounts.User` with `OWNER`, `ADMIN`, and `CASHIER` roles and active/same-shop rules;
- `catalog.Product` with text barcode, zero-capable price, active state, creator/source/review
  metadata, and current stock;
- `inventory.InventoryMovement`, which M3 must neither create nor mutate;
- append-only `core.AuditEvent` and its allow-listed writer;
- exact-pinned Tailwind 4.3.3 build output and small local `static/js/app.js`; and
- existing `transaction.atomic()`, actor-first locking, service-boundary validation, scoped 404,
  no-store response, and PostgreSQL concurrency-test conventions.

The current empty `sales` app becomes the owner of draft-order behavior. No new Django app,
frontend framework, scanner package, API framework, or third-party dependency is introduced.

## 3. Code ownership and proposed structure

```text
apps/
|-- sales/
|   |-- exceptions.py
|   |-- forms.py
|   |-- models.py
|   |-- policies.py
|   |-- queries.py
|   |-- services.py
|   |-- signing.py
|   |-- terminals.py
|   |-- urls.py
|   |-- views.py
|   `-- tests/
|-- core/
|   |-- audit.py
|   |-- models.py
|   `-- migrations/
`-- catalog/
    `-- models.py                 # reused; no M3 field change

templates/
`-- sales/
    |-- pos_workspace.html
    |-- quick_create.html
    |-- takeover_confirm.html
    |-- discard_confirm.html
    |-- terminal_unavailable.html
    `-- partials/
        |-- draft_tabs.html
        |-- draft_panel.html
        |-- order_line.html
        `-- search_results.html

static/js/
`-- pos.js
```

Responsibilities:

- `models.py` owns persisted draft and line state plus database constraints.
- `policies.py` contains side-effect-free POS capability checks.
- `terminals.py` resolves server-configured `POS_TERMINAL_CODE` (default `TILL-1`); no request value
  selects a terminal.
- `queries.py` owns read-only workspace/product queries and eager loading.
- `services.py` owns every draft/product mutation and every version increment.
- `signing.py` creates/verifies short-lived unknown-scan context for quick-create.
- `views.py` handles HTTP, form errors, redirects, and optional fragment responses only.
- `pos.js` serializes scanner submissions and swaps server-rendered fragments; it never determines
  authorization, prices, quantities, totals, or versions independently.

No business mutation is placed in a signal, model `save()` override, template, or JavaScript-only
path.

## 4. Database design

### 4.1 `sales.Order`

`Order` is the persistent terminal draft aggregate. M3 defines exactly these fields:

| Field | Django type | M3 rule |
|---|---|---|
| `shop` | `ForeignKey(core.Shop, PROTECT)` | Required; derived from actor |
| `terminal` | `ForeignKey(core.Terminal, PROTECT)` | Required; resolved from server-side `POS_TERMINAL_CODE` |
| `slot` | `PositiveSmallIntegerField` | Stable value 1, 2, or 3 |
| `status` | `CharField(max_length=24)` | M3 choices are `DRAFT` and `DISCARDED` |
| `created_by` | `ForeignKey(accounts.User, PROTECT, related_name="created_orders")` | Original creator; never changed |
| `current_cashier` | `ForeignKey(accounts.User, PROTECT, related_name="current_orders")` | User currently allowed to edit |
| `subtotal` | `DecimalField(max_digits=38, decimal_places=2, default=0)` | Server sum of current line totals; displayed as M3 Total |
| `version` | `PositiveBigIntegerField(default=1)` | Optimistic concurrency token |
| `discarded_by` | Nullable `ForeignKey(accounts.User, PROTECT, related_name="discarded_orders")` | Set only on discard/empty close |
| `discard_reason` | `CharField(max_length=500, blank=True, default="")` | Required only for non-empty discard |
| `discard_was_empty` | `BooleanField(default=False)` | Distinguishes reasonless empty close |
| `discarded_at` | Nullable `DateTimeField` | Server timestamp set on discard |
| `created_at` | `DateTimeField(auto_now_add=True)` | Server timestamp |
| `updated_at` | `DateTimeField(auto_now=True)` | Updated on every material draft change |

PKR calculations use `Decimal`; the wider aggregate fields safely accommodate a product's current
12,2 price multiplied by a PostgreSQL positive bigint quantity. The service rejects arithmetic
outside the declared decimal range rather than rounding, truncating, or using floating point.

`subtotal` is the only order money aggregate in M3. A `draft_total` presentation property may
return `subtotal`, but there is no separate final-total, adjustment, payment, refund, or cash field.

### 4.2 `Order` constraints and indexes

Database constraints:

1. `sales_order_status_valid`: status is `DRAFT` or `DISCARDED`.
2. `sales_order_slot_1_3`: slot is between 1 and 3 inclusive for every status.
3. `sales_active_terminal_slot_uq`: conditional unique constraint on `(terminal, slot)` where
   `status = DRAFT`.
4. `sales_order_subtotal_nonneg`: subtotal is zero or greater.
5. `sales_order_version_positive`: version is one or greater.
6. `sales_order_discard_state`: the exact state branches below; no branch accepts partial discard
   metadata.
7. `sales_order_discard_reason`: the exact state branches below, including an explicit `DRAFT`
   pass-through rather than accidentally requiring discard metadata on an active order.

| Status/state | `discarded_by` | `discarded_at` | `discard_was_empty` | `discard_reason` | `subtotal` |
|---|---|---|---:|---|---:|
| `DRAFT` | `NULL` | `NULL` | `False` | blank | any non-negative valid subtotal |
| `DISCARDED` empty close | non-null | non-null | `True` | blank | exactly `0.00` |
| `DISCARDED` non-empty | non-null | non-null | `False` | non-empty | any non-negative valid subtotal, including `0.00` for zero-priced items |

The checks use these complete `OR` branches. Item existence is cross-table data and therefore the
service, not a row check, establishes whether the discarded branch is empty; tests use direct
database writes to prove every expressible invalid metadata combination is rejected.

The slot check plus conditional uniqueness is the database-level maximum-three guarantee. There
are only three valid slot values, and no terminal can have two active rows in one slot; therefore a
fourth `DRAFT` cannot be represented even if application validation is bypassed. Historical
`DISCARDED` rows retain their old slot without preventing reuse by a new `DRAFT`.

Cross-table consistency—order shop equals terminal/user shop—cannot be expressed as a normal
PostgreSQL row check and is revalidated in every service.

Indexes:

- `(terminal, status, slot)` as `sales_term_status_slot_idx` for workspace loading;
- `(shop, status, -updated_at)` as `sales_shop_status_upd_idx` for scoped recovery/future internal
  maintenance; and
- `(current_cashier, status)` as `sales_current_status_idx` for handoff-oriented queries.

Default query ordering is not used as a substitute for explicit workspace slot ordering.

### 4.3 `sales.OrderItem`

`OrderItem` stores the current contents of a draft and the snapshot data retained on discard:

| Field | Django type | Rule |
|---|---|---|
| `order` | `ForeignKey(Order, CASCADE, related_name="items")` | Aggregate parent; no application order-delete path exists |
| `product` | `ForeignKey(catalog.Product, PROTECT)` | Same shop; referenced products are deactivated, not deleted |
| `product_name` | `CharField(max_length=200)` | Product-name snapshot captured on first add |
| `product_barcode` | `CharField(max_length=64, null=True, blank=True)` | Barcode snapshot or `NULL` |
| `unit_price` | `DecimalField(max_digits=12, decimal_places=2)` | Selling-price snapshot captured on first add |
| `quantity` | `PositiveBigIntegerField` | Strictly greater than zero |
| `line_total` | `DecimalField(max_digits=38, decimal_places=2)` | Exact `unit_price * quantity` |
| `created_at` | `DateTimeField(auto_now_add=True)` | First-add time |
| `updated_at` | `DateTimeField(auto_now=True)` | Quantity-update time |

Database constraints:

- `sales_item_order_product_uq`: unique `(order, product)`;
- `sales_item_quantity_positive`: quantity is greater than zero;
- `sales_item_unit_price_nonneg`: captured unit price is zero or greater;
- `sales_item_line_total_nonneg`: line total is zero or greater;
- `sales_item_line_total_exact`: line total equals unit price multiplied by quantity, expressed as
  a Django `F("unit_price") * F("quantity")` database expression (wrapped in a decimal output
  field if required by the final Django expression) and verified against generated PostgreSQL SQL;
- `sales_item_name_not_empty`: product-name snapshot is not empty; and
- `sales_item_barcode_not_empty`: barcode is `NULL` or non-empty.

Indexes on `order` and `product` are supplied by their foreign keys; an explicit `(order, id)` index
may be added only if query-plan inspection shows a need. The unique order/product index already
supports lookup of an existing line during add.

### 4.4 Retained discarded data and mutation boundary

- `Order` has no delete service, delete URL, operational admin registration, or user-visible
  discarded-history edit path.
- `OrderItem` removal is allowed only while its locked parent is `DRAFT` and only through the
  explicit service.
- Takeover, line add, quantity update, and line removal all reject `DISCARDED` parents.
- Discard changes the parent status and metadata but does not rewrite or remove current items.
- Empty close is retained as an order with zero items, zero subtotal, blank reason, and
  `discard_was_empty = True`.
- A non-empty discard retains the exact items, snapshots, quantities, line totals, subtotal,
  creator, current cashier, discarding actor, reason, version, and timestamps.
- Reusing a freed slot creates a new `Order` primary key. A discarded order is never reopened or
  repurposed.

Application immutability is enforced by the absence of mutation paths plus service state checks;
the M3 database credentials remain the operational trust boundary. Database triggers and a public
discarded-history model API are not added.

### 4.5 Deliberately deferred sales fields

M3 does not create:

- permanent order number or document sequence;
- completing cashier or completion timestamp;
- rounding adjustment, reason, actor, or final total;
- cash tendered, change, or `Payment`;
- shortage acknowledgement data;
- inventory-movement source links;
- completed/voided/returned status transitions; or
- return/void records.

These are not nullable placeholders in M3. Milestone 4/5 will add only the fields their approved
behavior needs, avoiding unused financial columns and premature constraints now.

## 5. Audit extensions

Extend `core.AuditEvent.Action` with:

- `PRODUCT_QUICK_CREATED`;
- `DRAFT_TAKEN_OVER`; and
- `DRAFT_DISCARDED`.

Extend `core.AuditEvent.TargetType` with `ORDER`. Update `core.audit._ALLOWED_TARGETS`:

| Action | Required target |
|---|---|
| `PRODUCT_QUICK_CREATED` | `PRODUCT` |
| `DRAFT_TAKEN_OVER` | `ORDER` |
| `DRAFT_DISCARDED` | `ORDER` |

Payloads use integer IDs, booleans, text, and decimal strings formatted to two places:

- quick-create `after_values`: `product_id`, `barcode`, `name`, `selling_price`,
  `creation_source`, `needs_review`, and `draft_id`;
- takeover `before_values`: prior `current_cashier_id`; `after_values`: `creator_id`, new
  `current_cashier_id`, `slot`, `item_count`, and `subtotal`;
- discard `after_values`: `creator_id`, `current_cashier_id`, `discarded_by_id`, `slot`,
  `item_count`, `subtotal`, `reason`, and `was_empty`.

The audit target identifier is the product ID for quick-create and order ID for takeover/discard.
Audit writes occur inside the same transaction as the business change. An audit failure rolls back
the product/order change. Viewing, selecting, searching, validation failure, stale conflict,
cancelled confirmation, and ordinary draft-line mutation create no audit event.

The audit-history UI remains deferred to Milestone 6.

## 6. Terminal resolution and authorization

### 6.1 Terminal resolver

`sales.terminals` defines:

```text
resolve_pos_terminal(actor, *, for_update=False) -> Terminal
```

Rules:

- Require an authenticated, active actor with a shop and POS role.
- Require the actor's shop to be active.
- Resolve only `settings.POS_TERMINAL_CODE`, whose approved/default value remains `TILL-1`.
- Normalize that trusted setting with `str(value).strip().upper()`, exactly matching the current
  bootstrap/`Terminal` convention; reject an empty or over-32-character configured value as
  `TerminalUnavailable` rather than querying a fallback terminal.
- Filter by the actor's shop and `is_active=True`.
- Accept no terminal identifier from path, query, form, session, cookie, or JavaScript.
- Use `select_for_update()` when called inside a mutation transaction.
- Raise a dedicated `TerminalUnavailable` when missing, inactive, duplicated through corrupted data,
  or inconsistent; render a safe configuration page rather than fabricating a terminal.

The existing shop/code unique constraint prevents duplicate configured terminals. M3 adds no
terminal setting, browser enrollment, or fallback-to-first-terminal behavior.

### 6.2 POS policies

`sales.policies` contains side-effect-free functions:

```text
can_use_pos(actor)
can_view_draft(actor, draft, terminal)
can_create_draft(actor, terminal)
can_edit_draft(actor, draft, terminal)
can_take_over_draft(actor, draft, terminal)
can_discard_draft(actor, draft, terminal)
can_quick_create_product(actor)
```

Rules:

- `OWNER`, `ADMIN`, and `CASHIER` can use POS when active and attached to the active shop.
- View requires actor, order, and terminal to share a shop; order must belong to that terminal and
  be `DRAFT`.
- Edit/discard additionally require `current_cashier_id == actor.id`.
- Takeover requires a viewable draft whose current cashier differs from the actor.
- Quick-create requires POS access, not normal catalog-management permission.
- No policy consults `is_staff`, `is_superuser`, hidden controls, or submitted shop/terminal/user.

Views use policies for early response behavior. Mutation services lock and revalidate the actor and
targets; template visibility remains usability, not authorization.

## 7. Read queries

`sales.queries` provides read-only helpers separate from mutations.

### Workspace query

```text
load_workspace(actor, terminal, *, selected_draft_id=None, query="") -> WorkspaceState
```

- Filter orders by actor shop, resolved terminal, and `status=DRAFT`.
- `select_related("created_by", "current_cashier", "terminal", "shop")`.
- Prefetch items in stable line-ID order with their protected product for active-state display.
- Order tabs by slot.
- Annotate or derive item count without an N+1 query.
- Select the requested draft only if it appears in the scoped active set.
- Otherwise select most recently updated, with lowest slot as the deterministic final tie-break.
- Never load a foreign/discarded order merely because its ID was submitted.

If no draft exists, the GET result contains `needs_initial_draft=True`; GET itself performs no
write. The template's protected startup behavior is defined in section 11.

### Product search

```text
search_pos_products(actor, *, query, limit=20) -> QuerySet[Product]
```

- Trim query; empty query returns no results.
- Require POS access and scope to actor shop plus `is_active=True`.
- Match `name__icontains`, `barcode__icontains`, or `sku__icontains`.
- Order by case-insensitive name then ID.
- Return at most 20 results with name, barcode, SKU, selling price, active state, and informational
  current stock.
- Do not expose edit actions or create anything when no match exists.

The selected product is reloaded and locked by the add service; a search result is never trusted as
fresh authorization or price state.

## 8. Service API and domain errors

### 8.1 Public services

`sales.services` exposes only these M3 mutation entry points:

```text
start_workspace(actor) -> Order
create_draft(actor) -> Order
scan_barcode(actor, draft_id, expected_version, barcode) -> ScanOutcome
add_product(actor, draft_id, expected_version, product_id) -> Order
quick_create_and_add(actor, draft_id, expected_version, barcode, name, selling_price) -> (Product, Order)
set_item_quantity(actor, draft_id, expected_version, item_id, quantity) -> Order
remove_item(actor, draft_id, expected_version, item_id) -> Order
take_over_draft(actor, draft_id, expected_version) -> Order
discard_draft(actor, draft_id, expected_version, reason="") -> (Order, replacement_or_none)
```

`start_workspace` is idempotent: with active drafts it returns the selected/lowest existing draft;
with none it creates slot 1. `create_draft` always requests another lowest-free slot and fails at
three.

`scan_barcode` returns either an updated draft or an `UNKNOWN` outcome carrying the normalized
barcode and unchanged version. Unknown scan is normal control flow, not a database write. Inactive
known barcode raises a focused validation error and never becomes `UNKNOWN`.

### 8.2 Domain errors

Define focused exceptions rather than parsing database messages in views:

- `TerminalUnavailable`;
- `DraftLimitReached`;
- `DraftVersionConflict(draft_id, expected_version, current_version)`;
- `DraftTakeoverRequired(draft_id, current_cashier_id)`;
- `BarcodeNowKnown(product_id, is_active)`; and
- `QuickCreateContextInvalid` for missing, expired, tampered, wrong-session, or wrong-actor signed
  context.

Use Django `PermissionDenied`, `ValidationError`, `Order.DoesNotExist`, `OrderItem.DoesNotExist`,
and `Product.DoesNotExist` for their established meanings. Views map inaccessible foreign IDs to
scoped 404 without disclosing them.

An expected unique race is caught inside a nested transaction savepoint, translated into a domain
error, and never leaves the surrounding connection in a broken transaction.

## 9. Transactions, lock ordering, and calculations

### 9.1 Common mutation preamble

Every public service runs in `transaction.atomic()` and locks in this global order:

1. actor row;
2. resolved terminal row;
3. draft order row, when applicable;
4. product row, when applicable; and
5. order-item row(s), when applicable.

The actor is reloaded with `select_for_update()` and `is_active=True`, then POS role and active-shop
rules are reapplied. The terminal is resolved server-side with `select_for_update()`. The draft is
loaded with `select_for_update()` through actor-shop and resolved-terminal filters.

After locking the draft, the service validates in this order:

1. status is `DRAFT`;
2. slot and same-shop/terminal invariants hold;
3. supplied version is a real positive integer and equals the persisted version; and
4. current-cashier authority holds for edits/discard, or takeover policy holds for takeover.

Version is checked before any domain write or audit insert. A stale request changes nothing.

### 9.2 Slot allocation and maximum three

`start_workspace` and `create_draft` lock the terminal row before reading active slots. They compute
the first missing value in `(1, 2, 3)` and create one order with actor as creator/current cashier,
zero subtotal, and version 1.

- `start_workspace` returns an existing active draft when one exists.
- `create_draft` raises `DraftLimitReached` when all slots are occupied.
- The conditional database unique constraint is the final race protection.
- If an unexpected integrity race still occurs, the service translates it into a controlled
  current-workspace conflict rather than showing a traceback.

Discard also holds the terminal lock through status change and optional replacement creation, so
slot release and the last-tab replacement are atomic.

### 9.3 Add, quantity, remove, and subtotal calculation

Known scan and search selection converge on one internal `_add_locked_product()` primitive:

1. lock and reload the product after the draft;
2. require same shop and `is_active=True`;
3. lock/find the existing order/product line;
4. if absent, create quantity 1 with current name, barcode, and selling-price snapshots;
5. if present, require the product still active and increment quantity by exactly 1 while preserving
   all snapshots;
6. compute the exact line total;
7. recompute order subtotal from all persisted current line totals;
8. increment order version once and update `updated_at`; and
9. return the freshly loadable order state.

Quantity replacement locks the target item after its parent. It requires a positive non-boolean
integer. If requested quantity exceeds the current quantity, the product must still be active;
equal or lower positive quantities preserve the snapshot and are allowed. Submitting the existing
quantity is a successful no-op after version validation and does not increment version.

To preserve the global product-before-item lock order while still discovering the item's product,
the already locked draft aggregate first performs a non-locking scoped read of the target item's
ID, product ID, and current quantity. Every compliant item writer already holds that parent lock.
The service then locks the referenced product, locks/reloads the item, and rechecks order/product/
quantity identity before deciding whether the edit is an increase, reduction, or no-op. It never
locks the item and then attempts to lock its product.

Removal locks the parent then target item, deletes only that current `DRAFT` item, recomputes
subtotal, and increments version. Removing the final line leaves subtotal zero and the draft active.

Calculations use `Decimal` only:

```text
line_total = unit_price * Decimal(quantity)
subtotal = sum(line.line_total, Decimal("0.00"))
```

Python's process-default decimal precision (normally 28 significant digits) is insufficient for a
valid 12,2 product price multiplied by a PostgreSQL positive bigint. All line/subtotal arithmetic
therefore runs in a local decimal context of at least 50 significant digits with `Inexact` and
`Rounded` trapped. Values are validated at exactly two decimal places without rounding a
more-precise submitted price; quick-create rejects more than two decimal places. The service then
validates values against the declared 38,2 fields before save. Any arithmetic signal, overflow, or
constraint failure becomes a focused validation failure and rolls back the mutation.
Client-submitted snapshots, line totals, subtotal, and stock are ignored.

### 9.4 Atomic quick-create and first add

`quick_create_and_add` uses one transaction and the common actor-terminal-draft locks:

1. verify the signed context at the view boundary, then pass its exact actor/shop/terminal/draft,
   normalized barcode, and expected version to the service;
2. repeat actor, terminal, draft, current-cashier, version, and barcode checks in the service;
3. query any same-shop product with that exact barcode, including inactive products;
4. if found, raise `BarcodeNowKnown` without changing it or the draft;
5. validate trimmed name and non-negative 12,2 selling price;
6. create `Product` with server-derived shop, creator, `POS_QUICK_CREATE`, `needs_review=True`,
   `is_active=True`, `stock_on_hand=0`, null SKU, and null cost price;
7. translate a simultaneous barcode unique failure inside a savepoint to `BarcodeNowKnown`;
8. append `PRODUCT_QUICK_CREATED` audit data;
9. create the first order line from that product's exact saved snapshots;
10. recompute subtotal and increment draft version once; and
11. commit all effects together.

The product, audit event, line, and order update are one success boundary. No inventory service is
called, no movement is created, and the product row's stock remains zero.

After a uniqueness race, the service queries the winning same-shop product under PostgreSQL READ
COMMITTED semantics and reports whether it is active. The UI may offer an explicit ordinary add
for an active winner using the current draft version; it never overwrites or automatically adds the
winner from the failed quick-create submission.

### 9.5 Takeover

`take_over_draft` locks the common context, checks exact version, requires another current cashier,
and then:

- preserves creator and every item/total;
- changes `current_cashier` to the actor;
- increments version and updates timestamp; and
- appends one `DRAFT_TAKEN_OVER` audit event with pre/post handlers and retained summary.

Calling takeover when the actor is already current returns a controlled validation message with no
version/audit change. Read-only workspace loading never calls this service.

### 9.6 Discard and last-tab replacement

`discard_draft` locks actor, terminal, order, and its current items. It checks version/current
cashier, recalculates subtotal, and determines emptiness from item existence—not from subtotal,
because zero-priced non-empty orders are valid.

- Non-empty: trim reason; require 1-500 characters; set `discard_was_empty=False`.
- Empty: require no business reason; store blank reason and `discard_was_empty=True`.
- Set status, discarded actor/time, retained subtotal, and increment version.
- Append exactly one `DRAFT_DISCARDED` audit event.
- Query remaining active slots while the terminal remains locked.
- If none remains, create a new slot-1 draft with the actor as creator/current cashier.
- Commit discard, audit, and optional replacement together.

A cancelled confirmation never invokes the service. If audit/replacement creation fails, the old
draft remains active. No discarded row or item is deleted, restored, or reused.

### 9.7 Version conflict and request replay

- Every mutation except initial `start_workspace`/new-tab creation carries `expected_version`.
- A material successful draft change increments version exactly once.
- Validation failure, no-op quantity, read/search, unknown scan, and cancellation do not increment.
- A stale mutation raises `DraftVersionConflict`; the view reloads current scoped state outside the
  failed transaction.
- Standard HTML requests receive a clear message and redirect to the latest draft.
- Asynchronous POS requests receive HTTP 409 plus server-rendered current fragments/version.
- The client stops any queued mutations on 409 and never automatically replays them against the
  new version.

This makes the draft itself the M3 idempotency/concurrency boundary. A response lost after commit
is recovered by reload; retrying the old version cannot apply the same mutation twice.

## 10. Signed unknown-scan context

The scan POST cannot expose an editable quick-create barcode while still enforcing that quick-create
originates from a real unknown scan. `sales.signing` uses Django's authenticated signing utilities:

```text
create_quick_create_context(actor, terminal, draft, barcode, *, session_key) -> signed_token
read_quick_create_context(token, actor, *, session_key, max_age=900) -> context
```

The signed payload contains actor ID, shop ID, terminal ID, draft ID, exact normalized barcode,
expected version, and a non-reversible session fingerprint. The fingerprint is produced with a
dedicated `salted_hmac` salt from the current Django session key; the raw session key is never put
in the signed-but-not-encrypted payload. The token uses a separate versioned signing salt such as
`sales.pos-quick-create.v1` and a 15-minute maximum age.

Rules:

- The barcode is displayed as text, not an editable form field.
- The form submits only the signed token, name, and selling price.
- Signature, age, constant-time session-fingerprint match, actor, shop, terminal, draft, and version
  are all verified.
- The token grants no authority; normal service locks and policies still run.
- Logout/session flush, user/session change, token tampering, expiry, draft mutation, takeover, or
  discard invalidates use. Relogging as the same actor creates a different session key and does not
  revive the old token.
- Successful quick-create increments the version, so token replay becomes stale.
- Cancelling writes nothing and returns to the signed draft only if it remains visible.

No unknown-scan context is stored in local storage, a new database table, or an unsigned query
parameter.

## 11. Forms, views, URLs, and response behavior

### 11.1 Forms

| Form | Accepted input |
|---|---|
| `StartWorkspaceForm` | CSRF only; no shop/terminal |
| `NewDraftForm` | CSRF only; no shop/terminal/slot |
| `BarcodeScanForm` | barcode and hidden positive `expected_version` |
| `PosProductSearchForm` | GET `q`, max 200, trimmed |
| `AddProductForm` | product ID and hidden positive `expected_version` |
| `QuickCreateProductForm` | signed context, name, selling price only; the view supplies the current session key separately for context verification |
| `QuantityForm` | positive bigint-compatible quantity and hidden version |
| `VersionedActionForm` | hidden positive version for remove/takeover |
| `DiscardDraftForm` | hidden version and reason; view makes reason required for non-empty draft |

Product price/name/barcode snapshots, line total, subtotal, creator/current/discard actor, slot,
terminal, shop, source, review state, active state, and stock never appear as trusted form fields.

Forms use literal Tailwind class strings and existing accessible field/error partials. Quantity is
accepted as text or number with integer step but always parsed server-side; booleans, exponent
notation, decimal strings, signs producing non-positive values, and values outside PostgreSQL
positive bigint are rejected.

### 11.2 URLs

Mount `apps.sales.urls` at `/pos/`:

| Method | URL | Name | Behavior |
|---|---|---|---|
| GET | `/pos/` | `sales:workspace` | Read-only tabs, selected draft, optional `draft` and `q` |
| POST | `/pos/start/` | `sales:start_workspace` | Idempotently create slot 1 only when none exists |
| POST | `/pos/drafts/new/` | `sales:draft_create` | Create/select lowest free slot |
| POST | `/pos/drafts/<id>/scan/` | `sales:draft_scan` | Known add or signed unknown redirect |
| POST | `/pos/drafts/<id>/products/add/` | `sales:draft_add_product` | Search-result add |
| GET/POST | `/pos/drafts/<id>/quick-create/` | `sales:quick_create` | Verify signed context, display/save restricted product |
| POST | `/pos/drafts/<id>/items/<item_id>/quantity/` | `sales:item_quantity` | Replace positive quantity |
| POST | `/pos/drafts/<id>/items/<item_id>/remove/` | `sales:item_remove` | Remove current line |
| GET/POST | `/pos/drafts/<id>/takeover/` | `sales:draft_takeover` | Show confirmation / perform takeover |
| GET/POST | `/pos/drafts/<id>/discard/` | `sales:draft_discard` | Show retained summary / discard or empty-close |

There is no URL for terminal selection, draft rename/copy/transfer, discarded history, price
override, stock reservation, payment, checkout, completed order, return, or void.

### 11.3 View rules

- All views use login, active-user behavior, `never_cache`, and POS capability enforcement.
- GET workspace resolves terminal read-only and uses scoped query helpers.
- When no draft exists, GET renders a CSRF-protected `Start Order 1` form. Local `pos.js`
  auto-submits it once, giving the approved automatic entry behavior; without JavaScript the visible
  button provides a deterministic fallback. The mutation itself remains POST-only.
- Successful normal mutations use POST-redirect-GET and Django messages.
- Unknown scan uses POST, creates a signed context, and redirects to quick-create GET; refresh does
  not resubmit the scan.
- Scan/quick-create views require an existing authenticated Django session key and pass it only to
  the signing helper. The raw key is never rendered, logged, submitted as a form field, or returned
  in a response.
- Takeover/discard GETs show confirmation only. Their POSTs repeat fresh scope/version checks.
- Foreign/nonexistent IDs return scoped 404; role failures return 403; terminal configuration
  failure renders `terminal_unavailable.html` with HTTP 503 and creates nothing.
- `DraftLimitReached` and `BarcodeNowKnown` become focused conflict guidance rather than raw
  integrity errors.
- Form/business validation returns the form with safe values; production never exposes traceback.

For JavaScript-enhanced requests carrying a dedicated local header, successful draft mutations may
return JSON containing only identifiers/version plus Django-rendered `tabs_html` and
`draft_panel_html`. Every `BigAutoField`, item ID, draft ID, and positive-bigint version in JSON is a
base-10 string, not a JSON number, so JavaScript cannot lose precision above `Number.MAX_SAFE_INTEGER`.
A 409 response contains the same freshly rendered current state. The ordinary HTML/redirect
behavior remains the progressive fallback and the source of truth is identical.

## 12. Templates, navigation, accessibility, and local JavaScript

### 12.1 Server-rendered UI

`base.html` adds a POS navigation link for all three roles outside the owner/admin management-only
block. The authenticated home adds a POS action card for all roles.

The workspace template:

- identifies the resolved terminal (normally `TILL-1`) and the selected
  `Order 1`/`Order 2`/`Order 3`;
- renders tabs in slot order with item count, PKR total, creator/current handler context, and clear
  selected state;
- shows New order only below the three-draft limit;
- renders another cashier's draft read-only with an explicit Resume action;
- shows scanner/search/mutation controls only for the current cashier;
- renders product snapshots, quantity, unit price, line total, and subtotal-as-Total;
- labels inactive existing lines and permits only reduction/removal;
- labels zero/negative recorded stock as informational search context without M4 acknowledgement;
- contains no cash, change, round-off, complete-sale, order-number, or history control; and
- uses text plus color for statuses, visible focus, large scanner/touch controls, form labels,
  field errors, an `aria-live` status region, and keyboard-operable confirmations.

All currency uses consistent `PKR 1,234.00` presentation. Timestamps use `Asia/Karachi`. Templates
load only committed local assets.

### 12.2 `static/js/pos.js`

The POS-specific local script is included only on POS pages and remains framework-free. It may:

- autofocus/select scanner input when no other control is active;
- auto-submit the protected initial-start form once;
- intercept known draft mutation forms and submit them with CSRF via `fetch`;
- serialize rapid barcode values in a FIFO queue, injecting the newest server-returned version
  as an opaque decimal string immediately before each request;
- replace tabs/draft panel only with Django-rendered response fragments;
- update the selected draft query parameter with `history.replaceState`;
- stop/clear queued mutations on conflict or network failure;
- stop/clear queued scans and follow the signed next URL when an unknown scan opens quick-create;
  later physical items are deliberately rescanned after quick-create/cancel;
- announce success/error through the live region; and
- restore focus after a settled action without stealing it from search/quantity/confirmation forms.

It must not:

- calculate or submit trusted price/total/stock values;
- invent or increment a version locally;
- coerce bigint identifiers/versions through JavaScript `Number` or arithmetic;
- retry a stale or failed mutation automatically;
- take over a draft merely on selection;
- store carts or quick-create context in local storage;
- depend on a CDN, remote font, telemetry, WebSocket, service worker, or frontend framework.

Without JavaScript, normal forms, Enter-to-submit scan, GET search, redirects, confirmations, and
manual initial Start Order remain functional. A real USB scanner pass remains a manual gate.

## 13. Validation and HTTP error mapping

### Server validation

- Barcode: trim edges, require 1-64 characters for scan/quick-create, preserve all remaining text.
- Search query: trim, maximum 200; empty means no results.
- Quick-create name: trim, require 1-200 characters.
- Selling price: use the existing Product decimal conversion; non-negative, maximum 12 total
  digits and two decimal places; zero allowed.
- Quantity: non-boolean positive integer within PostgreSQL bigint range.
- Discard reason: trim; 1-500 for non-empty, blank for empty close.
- Version: positive integer matching the locked draft exactly.
- Product: same shop and active for a first add or increase; reductions/removal may retain an
  inactive product snapshot.

### Response mapping

| Condition | Normal HTML behavior | Enhanced request behavior |
|---|---|---|
| Invalid field/business value | Render form or redirect with focused error | 422 with server-rendered error/current fragment |
| Stale draft version | Message and redirect to current draft | 409 with current fragments/version |
| Takeover required | Read-only page with Resume action | 409 with current handler/state |
| Three drafts already active | Message and redirect to workspace | 409 current tabs |
| Unknown scan | Redirect to signed quick-create GET | Success payload containing signed next URL |
| Barcode became known | Show current product state and explicit next choice | 409 with known-product guidance |
| Foreign/nonexistent object | 404 | 404 generic response |
| Authenticated but role-forbidden | 403 | 403 generic response |
| Terminal unavailable | Safe 503 configuration page | 503 safe error |
| Unexpected database/network failure | Friendly recoverable error; committed state survives | Error; queue stops and refresh is offered |

No error response includes SQL, stack traces, secret/signing material beyond the opaque token, or
foreign-record details.

An enhanced unknown-scan outcome is a queue boundary, not an ordinary successful increment: the
client clears later queued values before navigating to the signed next URL. The token and URL never
contain the raw session key.

## 14. Migration plan

1. Add a `core` migration extending audit action/target field choices for M3. It changes validation
   vocabulary only and does not rewrite existing events.
2. Add `sales.0001_initial` depending on the current `accounts`, new `core` audit migration, and
   `catalog.0001`; create `Order`, then `OrderItem`, constraints, and indexes.
3. Verify forward and backward migration against PostgreSQL and run `makemigrations --check`.

There is no data backfill, draft seed, inventory rewrite, product rewrite, or document sequence.
The first draft is created only through the protected POS start service, with a real actor.

Migration state uses only `DRAFT`/`DISCARDED` status choices and M3 constraints. Later status values
will require an explicit migration that revises the status constraint; they are not smuggled in as
unused behavior now.

## 15. Automated test strategy

SQLite is not an accepted substitute. Constraint and concurrency tests run against PostgreSQL.

### 15.1 Model and migration tests

- exact Order/OrderItem field types, defaults, protected references, and decimal precision;
- distinct reverse accessors for creator/current/discarding user relationships, with Django system
  checks proving no reverse-query clash;
- status, slot range, positive version/subtotal, and discard-state constraints;
- conditional active terminal/slot uniqueness while many discarded rows may retain the same slot;
- structural impossibility of a fourth active draft;
- unique one-line-per-order/product and positive quantity/non-negative captured price;
- exact line-total database check and non-empty snapshot rules;
- direct constraint truth-table coverage for active, empty-discard, non-empty-discard, and every
  invalid partial metadata combination;
- product deletion protection and absence of M4 financial/order-number models/fields;
- audit choice/target migrations and no migration drift.

### 15.2 Terminal, policy, and query tests

- default `TILL-1` resolution, normalized configured-code resolution, invalid/missing/inactive
  failure, active shop/terminal checks, and rejection of submitted/cross-shop terminal identity;
- every owner/admin/cashier/anonymous/inactive policy combination;
- cross-shop and wrong-terminal draft visibility denial;
- tabs ordered by slot with eager-loaded items/users and deterministic selected fallback;
- search name/barcode/SKU matching, active/same-shop scope, stable order, empty query, and 20-result
  limit;
- workspace viewing/searching creates no takeover or other audit event.

### 15.3 Service and calculation tests

- idempotent initial start, lowest-free new slot, exact three limit, slot reuse, and last-discard
  atomic replacement;
- known scan, repeated scan, search add, barcode-less add, leading-zero preservation, unknown
  outcome, and inactive-known refusal;
- first-add snapshots, catalog price change isolation, repeated-add retained price, and remove/re-add
  recapture;
- positive quantity replacement, invalid quantity matrix, no-op version behavior, line removal, and
  exact Decimal line/subtotal calculations including zero-priced products;
- near-capacity valid calculations under an intentionally low process-default decimal context,
  proving the service's local high-precision context prevents silent rounding, plus exact rollback
  for true 38,2 overflow;
- active-to-inactive product behavior: retained display, reduction/removal allowed, increase denied;
- no Product stock change and no InventoryMovement for every draft operation;
- quick-create derived fields, restricted input, focused audit payload, first line, version change,
  needs-review filter visibility, and complete rollback when product/audit/line/order save fails;
- takeover creator preservation, handler update, unchanged lines/totals, exact audit, and no event on
  view/already-current/stale/failure;
- non-empty reason validation, empty-close behavior, retained discard data, exact audit, and
  rollback when audit/replacement creation fails;
- all unauthorized, inactive actor, stale role, wrong shop/terminal, discarded-state, and crafted
  ID attempts.

### 15.4 PostgreSQL concurrency tests

Use `TransactionTestCase`, separate database connections, barriers, and `ThreadPoolExecutor`,
following the existing inventory concurrency pattern:

1. concurrent initial/new-draft requests allocate distinct lowest slots, never duplicate a slot,
   and never exceed three;
2. two requests with the same draft version yield one commit and one `DraftVersionConflict`, never
   a silent lost update;
3. the JavaScript queue contract is separately tested to send rapid same-client scans sequentially
   with returned versions so all acknowledged scans persist;
4. simultaneous takeovers create one event for the winning version and a conflict for the loser;
5. discard racing scan/quantity leaves either the complete draft mutation or the complete retained
   discard, never partial/mutable discarded data;
6. simultaneous quick-create of one barcode creates one product and one winning product audit/line;
   the loser receives `BarcodeNowKnown` with no orphan effects;
7. price edit racing first add captures one fully committed old-or-new price, never a mixed line;
8. all concurrency cases preserve zero stock/movement impact.

### 15.5 Forms, views, templates, and JavaScript tests

- method, login, role, CSRF, no-store, scoped 404, and response mapping for every URL;
- GET workspace never writes; protected start POST auto/fallback behavior creates exactly once;
- POST-redirect-GET prevents browser refresh duplication;
- signed quick-create context validity, expiry, tampering, actor/shop/terminal/draft mismatch, stale
  version, logout/session flush, same-user relogin, other-session reuse, cancellation, and replay;
- forms reject crafted shop/terminal/slot/actor/source/review/stock/price/total fields;
- normal and enhanced responses return the same server-trusted state;
- enhanced IDs/versions are decimal strings and JavaScript never passes them through numeric
  coercion;
- 409 responses replace stale state and do not replay the mutation;
- role-aware navigation, three tab states, read-only handoff, inactive-line controls, accessible
  labels/errors/live region, PKR formatting, and absence of M4 controls;
- local-only asset URLs, `node --check static/js/pos.js`, and deterministic Tailwind rebuild;
- JavaScript scanner FIFO/version update, focus discipline, conflict queue stop, unknown-scan queue
  clear/navigation, and network-failure recovery at the practical DOM/unit level supported by the
  existing toolchain.

### 15.6 Persistence and regression verification

- new Django test clients/sessions see the same terminal drafts after logout/login;
- re-query after closed connections/application process restart preserves tabs and lines;
- all 22 `docs/milestones/m3-active-orders/feature-spec.md` acceptance criteria map to automated evidence or required manual
  scanner/offline checks;
- existing M0-M2 account, audit, catalog, inventory, reconciliation, production-admin, offline
  asset, and PostgreSQL suites remain green;
- Ruff, format check, Django checks, migration check, `npm ci`, Tailwind build, collectstatic, and
  production-style Waitress smoke tests pass.

## 16. Implementation invariants and boundaries

The later development-task document and implementation must preserve these invariants:

1. Only sales services create/change draft/order rows and versions.
2. Every mutation locks actor, server-resolved terminal, and target aggregate in the documented
   order before checking version or writing.
3. Slot allocation is both terminal-lock serialized and database constrained.
4. Quantity edits preserve product-before-item locking, and every item mutation recalculates
   persisted subtotal with the service-owned high-precision decimal context.
5. The browser never supplies a trusted price, total, stock, actor, terminal, shop, or version
   increment.
6. Quick-create product, audit, first line, subtotal, and version are one transaction.
7. Takeover/discard audit writes are in the same transaction as their transition.
8. Discarded orders and their retained items have no M3 mutation/delete route.
9. No draft operation calls inventory movement services or changes `stock_on_hand`.
10. No M4 checkout/history behavior is exposed, even if later architecture is considered.

This section is dependency/invariant guidance, not the Milestone 3 development-task breakdown. No
implementation may begin until the task document exists and the separate package review gate has
passed.

## 17. Explicit technical exclusions

- `Payment`, `DocumentSequence`, completed order numbers, completion fields, or completed statuses.
- Round-off fields/services, cash/change calculation, stock-shortage acknowledgement, checkout
  idempotency, product stock locks for sale deduction, or `SALE` movements.
- Completed/discarded order-history UI, return/void models, reports, or audit-history UI.
- Direct stock editing, reservations, product availability promises, or negative-stock blocking.
- Cashier use of normal `catalog`/`inventory` forms or arbitrary quick-create endpoints.
- Price override, discount, promotion, tax, weighted quantity, customer, loyalty, or draft-note
  fields.
- Terminal picker/configuration, signed terminal-browser enrollment, second-terminal deployment,
  shifts, till assignment, draft transfer, multi-shop UI, or offline synchronization.
- REST/GraphQL API, Django REST Framework, SPA, WebSocket, service worker, scanner SDK, remote asset,
  CDN, telemetry, or new JavaScript dependency.
- Database triggers, generic event sourcing, generic idempotency-key tables, or speculative payment
  abstractions.
- Public restore/edit/delete operations for discarded drafts.

## 18. Approval and required package-review gate

On 2026-08-03, the user authorized continuous Milestone 3 planning and implementation without
intermediate user-approval pauses. Version 1.0 was therefore recorded as **Approved for continuous
implementation** and served as input to the Milestone 3 development-task document.

That authorization did not permit implementation immediately after task writing. The required
separate Sol xhigh review was completed on 2026-08-04 against the MVP requirements, milestones,
project design, completed M0-M2 behavior, current code, and all three M3 planning documents. Its
findings were corrected in version 1.1 and the entire package was reviewed again. The evidence-backed
pass is recorded in `docs/milestones/m3-active-orders/development-tasks.md` section 8; implementation may proceed only in that
reviewed task order and remains limited to Milestone 3.
