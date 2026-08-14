# Milestone 5 Technical Design - Returns and Voids

**Status:** Planning reviewed; implementation-ready

**Version:** 1.3

**Prepared:** 2026-08-06

**Input:** Approved `docs/milestones/m5-returns-voids/feature-spec.md` v1.3

## 1. Scope and approach

Extend completed-order history with immutable, linked correction transactions. The original sale,
sale payment, order lines, and sale inventory movements remain unchanged. Returns and voids are
created only through transactional domain services; order status is the only original-order field
updated after checkout.

The existing server-rendered Orders page remains the entry point. Full-page GET/POST/redirect is
the baseline. A small local JavaScript enhancement opens return and void forms in a native dialog,
calculates a non-authoritative refund preview, confirms the action, and refreshes the order detail
fragment after success.

## 2. Data model and constraints

### 2.1 Order

Add `PARTIALLY_RETURNED`, `RETURNED`, and `VOIDED` statuses. Database constraints treat these as
completed-like states: completion metadata and final totals remain required, while draft/discard
state remains forbidden. Application queries use one shared completed-like status set.

### 2.2 SalesReturn and SalesReturnItem

`SalesReturn` stores shop, unique permanent `return_number`, original order, processing actor,
optional reason/note, authoritative `total_refund`, a per-shop unique UUID `request_token`, and
creation time. `SalesReturnItem` stores the return, original order item, positive whole quantity,
`RESTOCK`/`DAMAGED` disposition, original `unit_refund` snapshot, and exact `line_refund`.

Constraints enforce nonnegative money, unique return number per shop, unique request token per
shop, and one original line per return. The return reason allows a normalized blank value. Models
and querysets reject update/delete.
Cross-table shop, quantity, snapshot, and total relationships are service-validated inside locks.

### 2.3 OrderVoid

`OrderVoid` stores shop, a one-to-one original order, processing owner/admin, required reason, a
per-shop unique UUID request token, and creation time. It is immutable. The one-to-one order link
prevents more than one committed void; service validation prevents any void after a return.

### 2.4 Payment

Generalize the existing immutable cash payment:

- add direction `RECEIPT` or `REFUND`;
- make the existing order source nullable and add nullable one-to-one return and void sources;
- require exactly one source;
- receipt rows require the order source, `cash_received`, and signed `change_given`, with
  `change_given = cash_received - amount`; and
- refund rows require a return or void source and null tender/change values.

Existing sale rows migrate to `RECEIPT` without changing values. Refund `amount` is positive and
represents cash leaving the shop; direction supplies the sign. Reverse names expose
`return.refund_payment` and `void.refund_payment`.

### 2.5 InventoryMovement

Keep sale `order_item` sources and add nullable `return_item`, `order_void`, and
`voided_order_item` sources. Database constraints require the source shape and quantity sign for
`SALE`, `RETURN`, and `VOID`; receipt/adjustment rows have no sale-correction source. A RESTOCK
return has one movement per return line. A void has one movement per original line, uniquely
identified by `voided_order_item` and its void. Damaged return lines intentionally have no movement.

### 2.6 Numbering and audit

Add `RETURN` to `DocumentSequence`; allocate `RET-000001` under a locked per-shop row. A data
migration creates the sequence for existing shops, and bootstrap creates it for new shops.

Add focused immutable audit actions `ORDER_RETURNED` and `ORDER_VOIDED`, targeted to the original
order. Metadata contains return/void identity, actor-independent business totals, quantities, and
dispositions; it contains no mutable browser-supplied prices.

## 3. Domain services and transaction boundaries

Create `apps.sales.corrections` with read helpers and two write services.

### 3.1 Return service

`complete_return(actor, order_id, request_token, reason, selections)` runs in one outer atomic
transaction:

1. lock/revalidate actor and same-shop completed-like order;
2. if the request token already identifies the same operation, return that committed result;
   reject token reuse for another order;
3. lock the order's items, prior return rows/items, absence of void, and affected products in
   deterministic primary-key order;
4. validate original receipt consistency and calculate remaining quantities exclusively from
   committed return lines;
5. validate positive selections and dispositions, normalize the optional reason/note, derive line
   refunds from original unit-price snapshots, and verify original line totals;
6. allocate the permanent return number;
7. create return, lines, and one `REFUND` payment;
8. for RESTOCK lines, apply one positive inventory movement and locked balance update; create no
   movement for DAMAGED lines;
9. derive and update order status from all returned quantities; and
10. append the return audit event.

Any exception rolls back numbering, payment, stock, status, and audit. PostgreSQL row locks
serialize competing corrections. The request-token uniqueness constraint makes browser retries
idempotent; a different stale request is revalidated and rejected with refreshed state.

### 3.2 Void service

`void_order(actor, order_id, request_token, reason)` uses the same lock ordering, then requires
owner/admin, `COMPLETED`, no return, and no prior void. It validates the original receipt and total,
creates the immutable void and refund payment, creates one positive VOID movement for every line,
sets status `VOIDED`, and records audit. A repeated same-token request returns the committed void;
a different repeat fails without effects.

### 3.3 Inventory integration

Inventory exposes correction-specific helpers which receive already locked products and immutable
source records. They are the only correction path that changes `stock_on_hand`; each updates the
balance and appends the matching immutable movement. They do not open independent transactions.

## 4. Policies and read model

- `can_process_return`: active owner/admin/cashier in the same active shop and an eligible order.
- `can_void_order`: active owner/admin in the same active shop and an eligible order.
- completed-order viewing stays available to all POS roles and remains same-shop scoped.

Create a return-state query helper that annotates each original item with returned and remaining
quantity and calculates total refunded. Detail queries prefetch returns, return items, actors,
refund payments, void, and correction movements without N+1 queries.

Order history includes all completed-like statuses. Extend filtering with local-business-date
range, same-shop completing cashier, status, exact/partial search, exact amount, and non-zero
change. Date boundaries are converted using the shop's `Asia/Karachi` timezone before querying
timezone-aware completion timestamps.

## 5. Forms, views, URLs, and response protocol

### Forms

- Extend `CompletedOrderSearchForm` with date-from, date-to, cashier, and status fields; cashier
  choices are injected from the actor's shop.
- `ReturnForm`: optional reason/note and UUID request token.
- Return item formset: immutable original-item id, quantity zero through server-calculated
  remaining, Restock selected by default with no empty choice, and disposition required only when
  quantity is positive.
- `VoidForm`: required reason and UUID request token.

Browser fields never include authoritative prices, remaining totals, shop, actor, or refund value.

### URLs and views

- `GET/POST /orders/<order_number>/return/`
- `GET/POST /orders/<order_number>/void/`

GET creates a new request token and returns a full fallback page or dialog HTML. Invalid POST
returns the bound full page or HTTP 422 dialog HTML. Successful fallback POST redirects to order
detail. Enhanced success returns `{result: "ok", message: "...", detail_url: "..."}`. Authorization,
scope, CSRF, and method failures retain normal 403/404/405 behavior.

Use request header `X-Order-Correction: modal` for dialog responses and `detail` for a refreshed
detail fragment.

## 6. Templates and local JavaScript

Split an order-detail content partial used by full and fragment responses. It displays:

- prominent current status and eligible Return/Void actions;
- immutable original sale, receipt, Cash received, signed Change, and original lines;
- sold/returned/remaining quantities;
- related return numbers, actors, reasons, refund totals, line dispositions, and stock effect;
- void actor, reason, refund, and reversal; and
- total refunded and remaining returnable quantity.

Return/void full-page templates share their form-body/dialog partials. The dialog JavaScript uses
native `<dialog>`, visible cancel/confirm buttons, keyboard behavior, one compact confirmation,
server error replacement, toast messaging, and detail-fragment refresh. Refund preview uses
integer minor units embedded by the server and is never trusted by the write service. Bulk return
and disposition helpers update only the form.

## 7. Migrations and compatibility

Create migrations in dependency order for core sequence/audit choices, sales statuses/models/
payments, then inventory correction sources. The data migration seeds missing return sequences and
backfills payment direction to receipt. Existing completed orders, payment reverse access,
checkout, recent-sales cards, and order-history URLs remain compatible.

## 8. Test strategy

Tests cover:

- model/database constraints and immutability for returns, voids, refund payments, and movements;
- role, active-user/shop, cross-shop, method, CSRF, and direct-URL boundaries;
- return calculations from historical snapshots, partial/full/mixed disposition, repeated returns,
  zero-price items, inactive/changed products, negative stock, and status derivation;
- void eligibility, full refund/reversal, and cashier denial;
- duplicate tokens, token misuse, stale/concurrent return-versus-return and return-versus-void;
- rollback on sequence/payment/movement/audit failure;
- order filters, local date boundaries, presentation, fragments, and no-JavaScript fallback;
- unchanged checkout/payment/history/recent-sales behavior; and
- full project regression in PostgreSQL Docker.

## 9. Planning review record

The mandatory whole-project review found and resolved four issues:

1. The project design's generic payment source was ambiguous against the existing non-null
   one-to-one sale payment. Section 2.4 now defines a source XOR and receipt/refund tender rules.
2. Partial returns needed operation-level retry protection beyond order status. Per-shop UUID
   request tokens and same-operation replay semantics were added.
3. Correction inventory sources could not reuse the sale line's existing unique source. Dedicated
   return and void source fields and uniqueness rules were added.
4. Search date filtering needed business-timezone boundaries. Section 4 now requires local-date
   conversion.

After these corrections, this design, the approved feature specification, development tasks,
MVP requirements, milestones, project design, completed behavior, and current codebase are mutually
consistent and implementation-ready. No Milestone 6 reporting or general audit UI is included.
