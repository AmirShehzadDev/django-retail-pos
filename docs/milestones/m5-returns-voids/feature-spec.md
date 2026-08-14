# Milestone 5 Feature Specification - Returns and Voids

**Status:** Approved

**Version:** 1.3

**Prepared:** 2026-08-06

**Inputs:** `docs/product/mvp-requirements.md` v1.7, `docs/product/roadmap.md` v1.6, completed Milestone 4 order
history, and the approved full-return-versus-void distinction

## 1. Objective

Allow the shop to correct a completed sale without deleting or rewriting its history:

- a **return** records goods brought back by a customer and may include some or every remaining
  item; and
- a **void** administratively reverses an entire sale that was completed in error.

Both operations record a cash refund and preserve the original order, item snapshots, receipt
payment, stock movements, cashier, total, and completion time.

## 2. Actors and permissions

### Cashier

- View completed same-shop orders read-only.
- Find an original order and process a linked partial or full return.
- Cannot void an order.

### Admin and owner

- Have the same linked-return capability as a cashier.
- May void an eligible entire completed order.
- Can view all return, void, refund, inventory, and audit details allowed to managers.

Every mutation is associated with the currently logged-in active user. Anonymous, inactive,
cross-shop, and crafted unauthorized requests are rejected on the server.

## 3. Find the original order

All roles use the existing Orders page and order detail as the entry point. Orders remain newest
first and can be found by:

- exact or partial order number;
- product name or historical barcode snapshot;
- date range;
- completing cashier;
- order status; or
- exact PKR order amount.

The result row/detail clearly shows status, date/time, completing cashier, item count, total, cash
received, and signed Change. A return or void action is offered only when the current actor and
persisted order state are eligible. Search and detail views never mutate the order.

## 4. Return eligibility and remaining quantities

A return requires an identifiable same-shop original order in `COMPLETED` or
`PARTIALLY_RETURNED` state.

For every original line:

`remaining returnable quantity = quantity sold - quantity in all committed prior returns`

- Remaining quantity is calculated by the server and cannot be supplied by the browser.
- A line with zero remaining quantity cannot be selected again.
- An order with no remaining quantities is `RETURNED` and cannot accept another return.
- A `VOIDED` order cannot be returned.
- An order that has any committed partial/full return can never be voided.

Multiple partial returns are allowed until all sold quantities have been returned.

## 5. Return interaction

1. From order detail, an eligible user selects **Return items**.
2. One return workspace/dialog lists every original line with product snapshot, unit price,
   quantity sold, quantity already returned, and quantity remaining.
3. Each return quantity starts at zero and accepts a whole number from zero through the remaining
   quantity.
4. **Return all remaining** fills every line with its remaining quantity. The user may still reduce
   individual quantities before completion.
5. Every line defaults to **Restock**. For each selected line, the user may keep Restock or change
   the disposition to:
   - **Restock** - the item is sellable and will increase stock; or
   - **Damaged / do not restock** - the item is returned financially but stock will not increase.
6. Convenience actions may set **Restock all selected** or **Damaged all selected**; each selected
   line remains visibly editable.
7. The user may enter an optional return reason/note.
8. The system shows the calculated cash refund continuously.
9. **Complete return** opens a compact confirmation containing the original order number, selected
   quantities, cash refund, and a warning that the return cannot be edited or deleted. There is no
   separate review page.
10. On confirmation, the return completes once and the same order detail updates to show the new
    status, return number, refund, dispositions, and remaining quantities.

Cancelling or closing before confirmation creates no return, refund, movement, audit event, or
status change.

## 6. Return refund calculation

- Refunds use the original immutable unit-price snapshots, never current product prices.
- Each return line refund is `original unit price x returned quantity`.
- The return refund is the exact sum of its line refunds in PKR with two decimal places.
- The cash refund is fixed to that calculated amount. The user cannot override it, apply a fee,
  enter cash tendered, or create separate refund change.
- Original Cash received and signed Change remain visible historical facts but do not change the
  refund amount.
- Completing the return means the calculated cash refund has been handed to the customer.

## 7. Return data effects

One database transaction must:

- lock and revalidate the actor, original order, prior returns, affected order lines, and affected
  products;
- allocate one permanent return number such as `RET-000001`;
- create one immutable return linked to the original order, including actor, optional reason/note,
  refund total, and timestamp;
- create immutable return lines containing original-line link, quantity, disposition, unit-refund
  snapshot, and line-refund total;
- create one cash refund payment for the return total;
- add exactly one positive `RETURN` inventory movement for each Restock line;
- add no inventory movement for Damaged / do not restock lines;
- update only the original order's derived status to `PARTIALLY_RETURNED` or `RETURNED`; and
- append the focused return audit event.

If any validation, numbering, refund, audit, or inventory operation fails, none of these effects
commit.

## 8. Full return

A cashier full return is the same return workflow with every remaining quantity selected. It may
contain Restock, Damaged, or mixed dispositions and results in order status `RETURNED`.

A full return is not a void: it represents a valid sale followed by a customer return, receives a
return number, and is permitted for all three roles.

## 9. Void eligibility and interaction

A void is available only to owner/admin when:

- the order is currently `COMPLETED`;
- it has no prior return; and
- it has not already been voided.

The manager selects **Void order**, sees the order number, completion time, cashier, items, sale
total, and exact cash refund, and enters a required reason. A confirmation dialog warns that the
entire sale and all sold quantities will be reversed. Cancelling changes nothing.

The refund equals the original order/payment amount applied to the sale (`final_total`), not Cash
received and not signed Change. It cannot be manually changed.

## 10. Void data effects

One database transaction must:

- lock and revalidate the actor, order, absence of returns/void, original items, and products;
- create one immutable void linked one-to-one to the original order with manager, reason,
  timestamp, and refund payment;
- create one exact cash refund payment for the original final total;
- create exactly one positive `VOID` inventory reversal for every original order line and full sold
  quantity;
- change only the original order's derived status to `VOIDED`; and
- append the focused void audit event.

The original order, sale payment, line snapshots, sale movements, totals, Cash received, signed
Change, order number, and timestamps remain unchanged. A repeated/stale void cannot issue another
refund or stock reversal.

## 11. Status rules

- `COMPLETED`: no committed return and no void.
- `PARTIALLY_RETURNED`: at least one quantity returned and at least one sold quantity remains
  returnable.
- `RETURNED`: no sold quantity remains returnable, regardless of restock/damaged disposition.
- `VOIDED`: the eligible whole sale was administratively voided.

Statuses are derived and changed only by the return/void services. Users cannot select a status
directly.

## 12. Validation, concurrency, and edge cases

- At least one return line must have a positive quantity.
- Quantities are whole numbers; decimals, negatives, and values above remaining quantity fail.
- Every selected line requires a valid disposition. A return reason may be blank; a void reason
  cannot be blank.
- Inactive products and products whose names/prices later changed can still be returned/voided
  because the protected original line and product relationship remain authoritative.
- A Restock return may increase a negative balance toward or above zero; it never creates an
  automatic correction beyond the returned quantity.
- Damaged lines never change stock, including when current stock is negative.
- Two users attempting returns/voids on the same order serialize through database locks. The loser
  receives refreshed remaining/state information and no partial effects.
- Duplicate submissions and retries cannot allocate multiple return numbers, refunds, audits, or
  movements for the same committed operation.
- A missing/inconsistent original receipt payment, line total, or shop relationship blocks the
  operation without mutation.
- Returns and voids remain valid while the shop is offline because they use only the local server,
  database, and assets.

## 13. Completed-order presentation

Order history/detail must show:

- the current status prominently;
- the original items, total, Cash received, signed Change, and original payment unchanged;
- every related return number, date/time, processing user, optional reason/note, refund, returned lines, and
  dispositions;
- void manager, date/time, reason, refund, and inventory reversal when voided;
- total refunded and remaining returnable quantities; and
- no edit/delete controls for any completed order, return, void, payment, or movement.

The Orders page supports the approved return-finding filters for all roles. Reports and the broader
audit page remain manager-only.

## 14. Accessibility and fallback

- Return quantities, dispositions, reason, calculated refund, validation, and confirmation are
  keyboard accessible and clearly labelled.
- Destructive/financial confirmation uses visible Cancel and Complete/Confirm actions with clear
  focus behavior.
- Enhanced success may update order detail in place, but server-rendered GET/POST/redirect
  fallbacks must support the complete workflow without JavaScript.
- No remote dependency or internet asset is introduced.
- Actual browser layout, focus, keyboard, responsive, offline, and cash-desk workflow require user
  frontend verification after implementation.

## 15. Explicit exclusions

- Unlinked returns, returns without an original order, or returns above remaining quantity.
- Exchanges, store credit, gift cards, credit/card refunds, bank transfers, or multiple refund
  methods.
- Custom refund prices, restocking fees, discounts, tax adjustments, or manual refund overrides.
- Returning only money without an item quantity.
- Voiding part of an order; partial correction uses a return.
- Cashier void permission, manager PIN/second approval, return windows, receipt printing, customer
  accounts, supplier returns, or automatic damaged-stock locations.
- Editing/deleting completed orders, returns, voids, refund payments, audits, or inventory
  movements.
- Daily summary calculations and the general audit screen, which remain Milestone 6.

## 16. Acceptance criteria

1. Every role can find a same-shop original order using the approved fields and view it read-only.
2. Cashier/admin/owner can complete a linked partial or full return; cashier cannot void.
   A return reason is optional, while a void reason remains required.
3. Returned quantity never exceeds remaining sold quantity across one or concurrent returns.
4. Return all remaining produces a normal immutable full return and `RETURNED` status.
5. Refunds use original snapshots and cannot be overridden; original Cash received/Change remain
   unchanged.
6. Restock creates exactly one positive movement per selected line; Damaged creates none.
7. Owner/admin can void only a return-free `COMPLETED` order, refund the original total, and reverse
   every sold quantity exactly once.
8. Any return prevents void; void prevents return; repeated/stale submissions create no duplicate
   financial, inventory, numbering, or audit effects.
9. Original sales and all correction records remain immutable, visible, and reconcilable.
10. Validation/transaction failures leave order, refund, status, inventory, numbering, and audit
    state unchanged.
11. Enhanced and no-JavaScript workflows, role/shop/CSRF/method boundaries, concurrency, and full
    regression tests pass.
12. The user verifies actual return/void dialog presentation, keyboard/focus, responsive, offline,
    and physical cash workflow before milestone acceptance.

## 17. Requirement reconciliation

The MVP phrase "refunding admin" is interpreted as the **processing user** for returns because the
approved role table explicitly permits cashier, admin, and owner returns. Voids remain
owner/admin-only. Cash refunds use the immutable payment `amount`/order `final_total`; Cash received
and signed Change are tender history, not the refundable sale value. No Milestone 6 reporting or
general audit UI is pulled into this milestone.
