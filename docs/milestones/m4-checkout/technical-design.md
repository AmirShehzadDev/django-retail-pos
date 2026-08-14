# Milestone 4 Technical Design - Cash Checkout and Order History

**Status:** Manual-acceptance revision reviewed; implementation pending

**Version:** 1.2

**Prepared:** 2026-08-04  
**Planning review passed:** 2026-08-04  
**Feature input:** `docs/milestones/m4-checkout/feature-spec.md` v1.1
**Project inputs:** `docs/architecture/technical-design.md` v0.5, completed Milestone 3.1 code and tests

> **Historical milestone design:** This remains the implementation record for cash checkout and
> order history. Its references to the then-current retained-discard model do not define future POS
> behavior; the approved replacement is [Milestone 4.2](../m4.2-clear-orders/technical-design.md).

## 1. Design goal

Add the smallest durable checkout ledger to the existing Django sales aggregate. The implementation
must preserve the Milestone 3 draft behavior, complete one cash sale in one PostgreSQL transaction,
remain safe when later terminals sell concurrently, and expose read-only completed-order history.

This refinement deliberately stops at `COMPLETED`. Milestone 5 adds returns, voids, refunds, and
their status transitions; Milestone 6 adds summary and audit-history pages.

## 2. Current-code constraints

The implementation extends, rather than replaces, these established behaviors:

- `Order` currently supports `DRAFT` and retained `DISCARDED`, slots 1-3, optimistic `version`,
  creator/current cashier, stored subtotal, and a partial unique constraint for active slots.
- `OrderItem` already stores product-name, barcode, unit-price, quantity, and exact line-total
  snapshots with one line per product.
- Draft mutation locks active actor, terminal, draft, product, then line as applicable. Checkout
  must use a compatible deterministic order to avoid creating a deadlock path.
- `Product.stock_on_hand` is a signed `BigIntegerField`; negative balances are already valid.
- `InventoryMovement` is insert-only and already has the `SALE` vocabulary, but has no source link.
- Focused `AuditEvent` records already support an `ORDER` target and an immutable append path.
- `/pos/` is implemented by `apps.sales.urls`; the new history group must not disturb its namespace.
- Tailwind CSS and the small local POS controller already operate offline. M4 adds no runtime
  dependency or frontend framework.

## 3. Data model and migrations

### 3.1 `core.DocumentSequence`

Add a shop-scoped sequence model:

| Field | Type | Rule |
|---|---|---|
| `shop` | protected FK to `Shop` | required |
| `document_type` | `CharField(16)` | M4 choice: `ORDER` |
| `next_number` | positive big integer | default 1; database check `>= 1` |
| `updated_at` | auto timestamp | operational visibility |

Constraints and behavior:

- Unique `(shop, document_type)`.
- Allocation locks the one row with `select_for_update(of=("self",))`, returns its current number,
  increments it, and saves inside the caller's transaction.
- Presentation is `ORD-{number:06d}`. Python's minimum width does not truncate numbers above six
  digits.
- Allocation happens only during final completion; transaction rollback restores `next_number`.
- A data migration creates an `ORDER` row for every existing shop.
- `bootstrap_pos` creates the row for a newly bootstrapped shop and remains idempotent.
- Milestone 5 may expand the choices and add a separate `RETURN` row; no return sequence is created
  now.

### 3.2 `sales.Order`

Extend `Status` with `COMPLETED` and add:

| Field | Type | Draft/discarded value | Completed value |
|---|---|---|---|
| `order_number` | `CharField(32)`, nullable/blank | null | permanent `ORD-...` |
| `completed_by` | protected user FK, nullable | null | checkout actor |
| `completed_at` | nullable datetime | null | transaction timestamp |
| `rounding_adjustment` | decimal `(38,2)` | `0.00` | signed amount, possibly zero |
| `rounding_reason` | `CharField(500)`, blank | blank | required only if non-zero |
| `rounding_by` | protected user FK, nullable | null | checkout actor only if non-zero |
| `final_total` | decimal `(38,2)`, nullable | null | subtotal plus adjustment |
| `shortage_acknowledged` | boolean | false | true only when warning was confirmed |

Keep `current_cashier` as the last active handler snapshot and set `completed_by` independently.
Completion increments `version` once so stale draft requests remain invalid.

Add database constraints:

- status is one of `DRAFT`, `DISCARDED`, or `COMPLETED`;
- conditional unique `(shop, order_number)` where the number is non-null;
- draft and discarded rows have null completion fields, zero adjustment, blank rounding reason,
  null rounding actor, and `shortage_acknowledged=False`;
- completed rows have non-null number, completing actor/time, adjustment, and final total, with no
  discard actor/time/reason/empty marker;
- completed `final_total >= 0`;
- completed `final_total = subtotal + rounding_adjustment` using a typed database expression;
- zero adjustment requires blank reason and null rounding actor;
- non-zero adjustment requires non-blank reason and non-null rounding actor; and
- the existing discard-reason and slot/subtotal/version constraints remain valid.

Add `(shop, status, -completed_at, -id)` as the history index. Retain the terminal/status/slot index
and active-slot unique constraint; changing the old order to `COMPLETED` frees the slot before the
replacement draft insert in the same transaction.

`Order` and its lines remain mutable only while the status is `DRAFT`. Sales services do not offer
any completed mutation. Django admin does not register them for mutation. Milestone 5 creates
separate reversal records rather than rewriting completed financial fields or line snapshots.

### 3.3 `sales.Payment`

Add an insert-only payment model containing only the M4 cash-receipt shape:

| Field | Type | Rule |
|---|---|---|
| `shop` | protected FK | must match order's shop; service-enforced |
| `order` | protected one-to-one FK | exactly one payment per completed order |
| `method` | `CharField(16)` | only `CASH` |
| `amount` | decimal `(38,2)` | final sale total; `>= 0` |
| `cash_received` | decimal `(38,2)` | `>= amount` |
| `change_given` | decimal `(38,2)` | `cash_received - amount`; `>= 0` |
| `processed_by` | protected user FK | completing actor |
| `processed_at` | auto timestamp | completion transaction time |

Database constraints enforce the only method, non-negative values, tender at least amount, and
exact change expression. A custom queryset and model guard reject update/delete, matching
`InventoryMovement`. The service validates cross-table shop, actor, order status, and amount
equality before insert. Direction, refund sources, split payments, and additional methods are not
added until a milestone needs them.

A payment amount of zero is allowed for an exactly offset final total. The record still exists so
every completed sale has the same ledger shape.

### 3.4 `inventory.InventoryMovement`

Add nullable `order_item`, a protected FK to `sales.OrderItem`, with related name `sale_movements`.
Add constraints:

- a `SALE` movement has `order_item IS NOT NULL` and `quantity_change < 0`;
- current non-sale movement types have `order_item IS NULL`; and
- one conditional unique movement exists per `order_item` where type is `SALE`.

Existing receipt/adjustment rows migrate with null source. The FK plus unique constraint supplies
the idempotency evidence for one sale movement per sold line. `shop`, `product`, actor, quantity,
balance, reason, and timestamp remain denormalized ledger facts validated by the checkout service.

The sale reason uses a stable source description such as `Sale ORD-000001`; source identity is the
FK, not parsed reason text.

### 3.5 Audit vocabulary

Add focused action choices:

- `ORDER_ROUNDING_APPLIED`; and
- `STOCK_SHORTAGE_ACKNOWLEDGED`.

Both use target type `ORDER` and the permanent order number as `target_identifier`. The rounding
event stores subtotal, signed adjustment, reason, and final total. The shortage event stores a list
ordered by product ID with product ID, captured name/barcode, balance before, sold quantity, and
balance after. Existing event rows need no data change.

### 3.6 Migration split and dependency order

Use three narrow migrations:

1. `core`: `DocumentSequence`, existing-shop sequence data, and M4 audit vocabulary;
2. `sales`: completed-order fields/constraints/indexes and `Payment`, depending on the core
   sequence migration; and
3. `inventory`: nullable sale source plus constraints, depending on the sales migration.

This ordering avoids a circular dependency. Migrations must run on a database containing current
draft/discarded orders and current receipt/adjustment movements without requiring fake completion
values.

## 4. Authorization and policy design

Add explicit policies in `apps.sales.policies`:

- `can_complete_draft(user, order, terminal)` requires active sales role, same shop, configured
  active terminal, `DRAFT`, and `current_cashier_id == user.id`;
- `can_view_completed_orders(user)` requires active `OWNER`, `ADMIN`, or `CASHIER` with an active
  shop; and
- completed-order query functions always apply `shop_id=user.shop_id` and `status=COMPLETED`
  before resolving an order number.

The checkout service repeats authorization after locking the actor, terminal, and draft. History
views never rely only on hidden navigation. Same-shop actors may view all completed sales, not only
sales they created or completed. Cross-shop and nonexistent detail use the same 404 response.

## 5. Monetary parsing and calculation

Add a reusable M4 money parser that:

- rejects booleans, NaN, infinities, malformed strings, and more than two decimal places;
- quantizes only exact two-decimal values under the existing high-precision decimal context;
- accepts signed adjustment and non-negative cash inputs within `(38,2)`; and
- never converts through `float`.

Reuse the M3 exact line and subtotal calculations. Checkout locks/loads the current lines and
recalculates their `line_total` from persisted `unit_price * quantity`; a mismatch blocks checkout
rather than silently changing evidence. It then recalculates the sum and persists that trusted
subtotal on completion.

Use typed decimal expressions/validators for:

```text
final_total = subtotal + rounding_adjustment
change_given = cash_received - final_total
```

The form may redisplay a calculated preview, but only the service result is authoritative.

## 6. Confirmation-context design

Create `apps.sales.checkout_signing` rather than embedding trust in hidden form fields.

The signed payload contains:

- authenticated user ID and current session-key fingerprint;
- shop, terminal, draft ID, and expected version;
- canonical decimal strings for adjustment and cash received;
- normalized rounding reason;
- boolean that round-off confirmation is required; and
- the exact sorted shortage product IDs and projected balances shown.

Use Django signing with a dedicated salt and a 10-minute maximum age. The raw session key is not
stored in the payload. Signature verification compares the current user/session and rejects missing,
expired, malformed, cross-session, or mismatched context.

The signed payload is evidence only that the cashier saw a prior preview. Final authorization
always reacquires locks and recalculates. If the current required round-off/shortage confirmation
does not equal the signed context, the domain result requests a fresh confirmation and writes
nothing.

## 7. Checkout service boundary

Keep HTTP signing and form behavior outside the business mutation. In `apps.sales.services`, add:

- `evaluate_checkout(actor, draft_id, expected_version, adjustment, reason, cash_received)` returning
  an immutable `CheckoutEvaluation` with server totals, shortage rows, and confirmation needs but
  making no business mutation; and
- `complete_cash_checkout(..., confirmed_adjustment=False,
  acknowledged_shortages=())` returning an immutable `CheckoutResult` or raising a typed
  `CheckoutConfirmationRequired` carrying a fresh evaluation.

`complete_cash_checkout` owns the full `transaction.atomic()` boundary. Views catch domain
validation, stale, permission, confirmation-required, and already-completed outcomes and map them
to safe pages/messages. No signal creates payments, movements, audit events, or replacement drafts.

### 7.1 Lock order

Use this deterministic order for checkout:

1. active actor row, self table only;
2. configured terminal row, self table only;
3. draft order row, self table only;
4. referenced products in ascending product ID, self table only;
5. order items in ascending item ID, self table only;
6. shop `ORDER` sequence row, self table only.

The draft line/product IDs may be discovered through unlocked scalar queries after the draft lock,
then locked in the fixed order and revalidated. Avoid `select_related()` joins in locking queries;
use `select_for_update(of=("self",))` where supported. Existing inventory and catalog services
already lock actor then product, which remains compatible. The draft lock prevents concurrent line
mutation while checkout continues.

### 7.2 Atomic completion algorithm

Inside one outer transaction:

1. Lock active actor, resolve/lock terminal, and lock the target order.
2. If it is already `COMPLETED`, verify same-shop access and return its stored result. If it is any
   other non-draft state, reject it.
3. Require exact version/current-cashier authority and at least one line.
4. Discover IDs, lock products in ID order, then lock lines in ID order; verify the line set,
   product links, quantities, exact line totals, and active products are unchanged.
5. Recalculate subtotal, normalize/validate adjustment and reason, calculate final total, normalize
   cash received, and calculate change.
6. Calculate each projected stock balance and compare the exact required warning set with supplied
   acknowledgement evidence.
7. If a non-zero adjustment is unconfirmed or the exact shortage set is unacknowledged, raise
   `CheckoutConfirmationRequired`. The transaction exits without business writes.
8. Lock/allocate the order number.
9. Set completion fields, status, stored totals, warning flag, and incremented version on the order;
   retain the existing order-line identity/price snapshots without recapturing catalog values.
10. Insert the one `Payment`.
11. For each line ordered by product ID, set the product's projected balance and insert one linked
    negative `SALE` movement.
12. Append focused rounding/shortage audit events when required.
13. Insert one empty `DRAFT` with the completed order's terminal/slot and completing actor as creator
    and current cashier.
14. Return completed order, payment, and replacement identifiers; commit on successful exit.

The order status must be persisted before inserting the replacement so the partial unique active
slot constraint is satisfied. All following inserts remain inside the same transaction, so a later
failure rolls the status change back.

### 7.3 Inventory mutation helper

Refactor the current private inventory movement creator only as far as needed to provide an internal
helper that accepts an already locked product and a fully validated source line. It must:

- run inside the caller's transaction without opening an independent commit boundary;
- permit `SALE` only through the checkout-owned path;
- use a negative whole-number quantity;
- update `stock_on_hand` and append the linked movement; and
- never enforce a non-negative result or add a corrective movement.

Owner/admin receipt and adjustment APIs retain their existing policies and behavior.

### 7.4 Idempotency and failure behavior

The persisted draft is the idempotency key. Once its locked status is `COMPLETED`, the service
returns the existing order/payment/replacement state and ignores resubmitted financial inputs. The
unique payment/order number/sale source/active-slot constraints provide defense in depth.

Failures after sequence allocation, payment insert, one or more stock updates, audit insert, or
replacement insert are injected in tests to prove outer-transaction rollback. No exception handler
may catch an integrity error and continue in a broken transaction without a savepoint.

## 8. Query design for completed orders

Add `apps.sales.history` (or a clearly named query module) with pure shop-scoped queries.

### 8.1 List query

Base queryset:

- `shop_id=actor.shop_id`, `status=COMPLETED`;
- `select_related("completed_by")`;
- annotated item count;
- ordered `-completed_at, -id`; and
- `distinct()` only where line search joins require it.

Search behavior for trimmed `q`:

- `order_number__icontains=q`;
- `items__product_name__icontains=q`;
- `items__product_barcode__icontains=q` for non-empty captured barcodes; and
- when `q` parses as an exact supported PKR amount, `subtotal=q OR final_total=q`.

Apply adjusted-only as `~Q(rounding_adjustment=0)`. Paginate 50 rows after filtering. Preserve only
normalized `q`, `adjusted`, and `page` parameters in generated links.

### 8.2 Detail query

Resolve by same-shop, completed status, and normalized order number. Load:

- creator/current/completing/rounding users and terminal;
- ordered items with product only for identity linkage, while displaying snapshot fields; and
- the one payment and processing actor.

The shortage boolean is displayed as focused completion evidence; the general audit payload is not
shown to cashiers. M5 may add prefetches for reversal/return records without changing captured M4
data.

## 9. Forms, views, URLs, and HTTP behavior

### 9.1 Forms

Add:

- `CheckoutForm`: hidden positive `expected_version`, signed `rounding_adjustment` default zero,
  optional `rounding_reason` max 500, and non-negative `cash_received`; cross-field checks perform
  friendly validation but do not replace service validation.
- `CheckoutConfirmForm`: one hidden signed `context`; no user-editable trust boolean.
- `CompletedOrderSearchForm`: optional `q` max 200 and boolean `adjusted`; unknown fields ignored.

All money widgets use `step="0.01"` and decimal input hints. Server validation remains authoritative.

### 9.2 POS checkout endpoints

Extend the existing `sales` namespace under `/pos/`:

- `GET /pos/drafts/<draft_id>/checkout/` - render current checkout;
- `POST /pos/drafts/<draft_id>/checkout/` - validate and either complete or render confirmation;
- `POST /pos/drafts/<draft_id>/checkout/confirm/` - verify signed context, recalculate, and complete
  or render a fresh warning; and
- no mutation is accepted by GET.

Success uses PRG to completed-order detail. An authorized request naming an already-completed draft
redirects to its detail. Stale/invalid recoverable requests keep or return to the draft with a clear
message; permission and shop boundaries use established 403/404 behavior without disclosure.

### 9.3 Completed-order endpoints

Create a separate `order_history` URL namespace included by `config.urls` at `/orders/`:

- `GET /orders/` - list/search/filter/paginate;
- `GET /orders/<order_number>/` - read-only detail.

This avoids including the existing `/pos/` URL set under a second prefix or creating a duplicate
`sales` namespace. All history requests are GET/read-only.

## 10. Template and local-JavaScript design

Add:

- `templates/sales/checkout.html`;
- `templates/sales/checkout_confirm.html`;
- `templates/sales/order_list.html`; and
- `templates/sales/order_detail.html`.

Update the POS workspace with a checkout action only when the selected draft is editable and
non-empty. Add `Orders` navigation for all sales roles.

Templates use the current local Tailwind output and existing PKR/Karachi presentation helpers.
They include clear positive/negative adjustment styling, prominent shortage warnings, readable
cash/change summary, pagination, empty results, and an `Adjusted` badge. They do not expose manager
catalog fields or general audit payloads.

The checkout works with normal form submission when JavaScript is absent. A small enhancement may
preview final total/change from already-rendered values, but it must use local code, cannot enable
submission the server would reject, and is not required for correctness. No browser or manual
frontend verification is performed by Codex; the user receives a final checklist.

## 11. Test design

### 11.1 Model and migration tests

Cover:

- sequence uniqueness/check/allocation format and existing-shop migration path;
- all `Order` completion-state, exact-total, adjustment-reason, number, and active-slot constraints;
- `Payment` exact-change, cash-only, one-order, non-negative, and immutability constraints;
- `InventoryMovement` sale sign/source/uniqueness and existing receipt/adjustment compatibility;
- valid zero-total/zero-payment completion shape; and
- migration on representative current M3 draft/discarded/movement data.

### 11.2 Service tests

Cover:

- normal checkout and exact reconciliation;
- positive/negative/zero round-offs, required reason/confirmation, no configured cap within storage,
  negative-total refusal, and normal excess-cash change;
- sufficient stock and one/multiple shortages, already-negative stock, acknowledgement, changed
  warning set, and no correction movement;
- inactive products, empty/stale/foreign/unresumed drafts, malformed/overflow money, and exact
  captured subtotal validation;
- permanent number, completing actor, payment, movements, audits, and same-slot replacement;
- other tabs unchanged;
- idempotent repeated completion; and
- injected rollback at payment, movement, audit, and replacement stages.

### 11.3 PostgreSQL concurrency tests

Use `TransactionTestCase`, separate database connections/threads, barriers, and bounded joins to
prove:

- two requests for one draft create one completed aggregate;
- two drafts selling the same product cannot lose an update and record truthful ordered balances;
- a shortage emerging behind another checkout requires current acknowledgement;
- concurrent orders receive distinct numbers; and
- no deadlock or duplicate linked movement occurs under the documented lock order.

These tests run against PostgreSQL in the Docker test environment; SQLite is not accepted as proof
of row-lock behavior.

### 11.4 Form, signing, view, and history tests

Cover:

- money/reason/search form boundaries;
- confirmation expiry, tampering, cross-user, cross-session, stale version, and changed warnings;
- GET/POST/CSRF contracts and PRG behavior;
- role parity and cross-shop/nonexistent isolation;
- conditional confirmation and error rendering;
- newest-first ordering, 50-row pagination, query preservation, no duplicate rows;
- order number, snapshot name/barcode, exact subtotal/final amount search, and adjusted filtering;
- immutable detail content and absence of M5 controls; and
- navigation/template regression for owner, admin, and cashier.

### 11.5 Automated verification commands

Implementation verification runs in the Docker image and includes, at minimum:

```powershell
docker compose run --rm web python manage.py makemigrations --check --dry-run
docker compose run --rm web python manage.py check
docker compose run --rm web python manage.py test
```

Run the repository's configured Tailwind build/check command if templates introduce new classes.
Codex does not open or manually inspect the frontend unless the user explicitly changes that rule.

## 12. Acceptance traceability

| Feature acceptance | Technical coverage |
|---|---|
| AC 1-4 cash and round-off | Sections 3.2-3.3, 5-7, 9, 11 |
| AC 5-7 stock and acknowledgement | Sections 3.4-3.5, 6-7, 11.2-11.3 |
| AC 8 atomicity | Sections 3, 7.2-7.4, 11.2 |
| AC 9 concurrency | Sections 7.1, 7.4, 11.3 |
| AC 10 idempotency | Sections 3.3-3.4, 7.4, 11.2-11.3 |
| AC 11 numbering/replacement | Sections 3.1-3.2, 7.2, 11.2 |
| AC 12 immutable snapshots | Sections 3.2-3.4, 8.2, 11.1-11.2 |
| AC 13-14 order history/detail | Sections 4, 8-10, 11.4 |
| AC 15 rollback | Sections 7.2-7.4, 11.2 |
| AC 16 automated coverage | Section 11 |
| AC 17 user frontend verification | Sections 10 and 11.5 |

## 13. Explicit technical exclusions

- M5 order states, `OrderVoid`, `SalesReturn`, return lines, refund payments, and reversal links.
- M6 reporting queries or public audit-history UI.
- Payment abstractions for cards, splits, accounts, or cash sessions.
- Database triggers or signals for checkout side effects.
- Client-authoritative amounts, stock, permissions, or confirmation.
- Receipt generation/printing and hardware integration.
- Runtime CDN, JavaScript framework, or online dependency.
- Frontend manual verification by Codex.

## 14. Implementation gate

Implementation starts only after `docs/milestones/m4-checkout/development-tasks.md` is derived from this design and the
mandatory planning review reconciles all three Milestone 4 documents with the project requirements,
milestones, technical design, completed behavior, and current code. Review findings must be fixed
and the review rerun before the gate is marked passed.

## 15. Manual-acceptance technical revision (v1.2)

This section supersedes the v1.1 round-off/signing/separate-page design.

### 15.1 Payment and order rules

- `Order.subtotal` and `Order.final_total` are equal for new checkout completions.
- Deprecated rounding fields remain zero/blank/null for migration compatibility and are not exposed
  or written by the revised checkout path.
- `Payment.amount` equals the order total.
- `Payment.cash_received` remains non-negative but no longer has to be at least `amount`.
- Existing `Payment.change_given` stores signed `cash_received - amount`; its database non-negative
  and tender-at-least-total constraints are removed while exact-change remains.
- Round-off audit creation and checkout-confirmation signing are removed from the active path.

### 15.2 Checkout service and HTTP

- `complete_cash_checkout(actor, draft_id, expected_version, cash_received)` owns the existing
  atomic lock/write algorithm.
- It validates cash as non-negative `(38,2)`, calculates signed change, locks/rechecks stock,
  finalizes the order/payment/movements/audit/replacement, and redirects to detail.
- No GET checkout screen or confirm endpoint is required. A single inline POST endpoint under the
  draft completes checkout.
- Existing same-draft idempotency and PostgreSQL lock ordering remain unchanged.
- Shortages are shown inline from current product balances; completion audits any final negative
  projection without a separate round-off-style confirmation page.

### 15.3 Workspace query and template

- An empty POS product query returns the first 50 active same-shop products ordered by normalized
  name/id; a non-empty query filters name/barcode/SKU within the same limit.
- Desktop workspace uses a bounded viewport-height flex/grid layout. The main order column spans two
  of three columns and keeps scanner, total, cash, signed-change explanation, and submit controls
  fixed; lines scroll internally.
- The product catalogue spans the right column and scrolls internally. Search and add use existing
  server-authoritative endpoints.
- `CheckoutForm` contains only expected version and non-negative cash received.
- The completed list/detail renders signed change with distinct positive, zero, and negative styles.

### 15.4 Migration and tests

- Add a Sales migration removing `sales_payment_tender_gte_amount` and
  `sales_payment_change_nonneg`; keep the exact-change constraint.
- Replace round-off/signing/confirmation tests with cash-above/equal/below, signed-change,
  one-submit POS, catalogue default/search, page-structure, rollback, idempotency, shortage audit,
  and concurrency coverage.
- Frontend fit at 1366x768, internal scrolling, scanner focus, and offline presentation remain
  user-owned manual verification.

### 15.5 Immediate quantity stepping

- Workspace line controls provide server-derived previous/next quantity values within the existing
  positive-big-integer boundary.
- Each minus/plus control is its own CSRF-protected POST form to the existing versioned quantity
  endpoint. This preserves progressive enhancement: normal POST/redirect works without JavaScript,
  while the existing POS mutation handler replaces the current fragments when JavaScript is active.
- Minus is disabled at one. Plus is disabled for an inactive retained product or at the maximum.
  Disabled controls remain visible. The separate remove endpoint is unchanged.
- Template tests cover visible controls, disabled boundaries, immediate-submit forms, and absence of
  the old Update button; existing service/HTTP/concurrency tests continue to cover the mutation.

### 15.6 Toast notification presentation

- Move the shared messages partial outside the normal `<main>` content flow and render a fixed,
  top-right, high-z-index toast stack with bounded width/height and no page-layout contribution.
- Map Django message levels to existing local Tailwind success/info/warning/error colors. Each toast
  exposes a local close button and appropriate status/alert semantics.
- Local `app.js` dismisses success after 5 seconds and info after 7 seconds, pauses/resumes the timer
  on hover/focus, animates removal, and leaves warnings/errors persistent. With JavaScript disabled,
  toasts remain fixed and manually dismissible behavior is unavailable, but navigation clears them.
- Server/template tests cover markup, level mapping, close controls, and timeout policy; JavaScript
  syntax and the complete regression suite remain automated checks. Visual stacking and POS fit are
  user-owned frontend verification.
