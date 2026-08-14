# Milestone 4 Feature Specification - Cash Checkout and Order History

**Status:** Manual-acceptance revision reviewed; implementation pending

**Version:** 1.2

**Prepared:** 2026-08-04  
**Planning review passed:** 2026-08-04  
**Inputs:** `docs/product/mvp-requirements.md` v1.4, `docs/product/roadmap.md` v1.3,
`docs/architecture/technical-design.md` v0.5, the approved Milestone 3 and Milestone 3.1 planning documents, and
the completed Milestone 3.1 application

> **Historical milestone specification:** This remains the record for cash checkout and completed
> order history. The approved [Milestone 4.2 specification](../m4.2-clear-orders/feature-spec.md) separately
> supersedes inherited retained-discard behavior with **Clear order** and **Close tab**.

## 1. Objective

Allow an owner, admin, or cashier to turn an editable, non-empty POS draft into one permanent cash
sale. Checkout must calculate PKR totals and change on the server, support an explicitly confirmed
signed cash round-off, warn but permit an explicitly acknowledged stock shortage, update inventory,
and record the order, payment, movements, and audit evidence atomically.

The milestone also provides a read-only, shop-wide completed-order list and detail page. It does not
provide returns, voids, receipts, daily reports, or general audit-history screens.

## 2. Actors and permissions

### Owner, admin, and cashier

Each active user in these roles can:

- check out a draft that they currently handle on the configured terminal;
- enter cash received and an optional signed round-off;
- confirm a non-zero round-off without a separate PIN;
- acknowledge a projected negative stock balance without a separate PIN;
- view every completed order belonging to their shop; and
- search and filter the completed-order list within the Milestone 4 scope.

The user who completes checkout is stored as the completing cashier even when they did not create
the draft. Checkout does not expand a cashier's permissions to edit products, receive or adjust
stock, manage users, view general audit history, void orders, or process returns.

### Anonymous, inactive, or out-of-shop user

- Cannot open checkout or completed-order pages.
- Cannot complete or view a sale by guessing a draft ID, order ID, or order number.
- Is handled by the authentication and active-session rules established in Milestone 1.

## 3. Compact-MVP decisions

1. Payment method is cash only. There is one cash payment record per completed order.
2. Product prices are final prices. Tax, discounts, coupons, and promotions are absent; the only
   permitted total adjustment is the explicit signed cash round-off.
3. Checkout uses a conventional server-rendered form and redirect flow. Browser calculations are
   display conveniences only and never authorize a total or payment.
4. A normal checkout with no round-off and sufficient stock can complete on its first valid POST.
   A non-zero round-off or projected negative stock requires a separate confirmation page.
5. One confirmation page may confirm both a round-off and all current shortage warnings. It shows
   the exact subtotal, adjustment, final total, cash received, change, and projected negative
   balances before the cashier commits.
6. Confirmation is bound to the authenticated session, draft, draft version, normalized monetary
   inputs, and current warning set. It expires after a short period. Logout, draft changes, changed
   stock warnings, or edited checkout values require a fresh confirmation.
7. There is no configured round-off amount limit. Storage range, two-decimal PKR precision, and the
   rule that final total cannot be negative still apply.
8. Excess cash is normally recorded as cash received and change. It increases the sale total only
   when the cashier deliberately enters a positive round-off and confirms it. For example, a
   `PKR 99.00` subtotal, `PKR 1.00` adjustment, and `PKR 100.00` cash received produces a
   `PKR 100.00` final total and `PKR 0.00` change.
9. Drafts do not reserve stock. Checkout rechecks current stock while holding database locks. A
   shortage can be acknowledged and may produce a visible negative balance; the system never adds
   a correction movement to hide it.
10. A completed order is immutable. Its lines, captured identity and prices, financial values,
    payment, and sale movements cannot be edited or deleted through application behavior.
11. The successful sale occupies the existing draft record; checkout does not copy it into a
    second order. It receives its permanent number and `COMPLETED` status, then a new empty draft is
    created in the same terminal slot for the completing cashier.
12. Repeated or concurrent submission of the same checkout returns the already-completed sale and
    cannot create another payment, order number, sale movement, or replacement draft.
13. Completed-order history is shop-wide and read-only for all three roles. Milestone 4 supplies
    order-number/product/barcode/amount search plus an adjusted-order filter. Date, cashier, and
    status filters are deferred to Milestone 5's return lookup; daily summaries remain Milestone 6.
14. No receipt is printed or generated in this milestone.

## 4. Preconditions

- Milestones 0 through 3.1 are complete.
- The actor is authenticated and active, their shop is active, and their role is `OWNER`, `ADMIN`,
  or `CASHIER`.
- The configured POS terminal resolves through the existing `POS_TERMINAL_CODE` behavior.
- The selected order is a `DRAFT` for that terminal and shop, its submitted optimistic version is
  current, and the actor is its current cashier.
- The draft contains at least one line.
- All monetary values use fixed-precision decimal arithmetic, accept at most two PKR decimal
  places, and are stored/displayed to two places; floating-point arithmetic is not used.
- All timestamps are timezone-aware and displayed in `Asia/Karachi`.
- Every state-changing request is CSRF-protected.

An empty, foreign-terminal, foreign-shop, stale, discarded, or another cashier's unresumed draft
cannot enter checkout. The existing takeover flow must be completed first when another cashier is
currently handling the draft.

## 5. Checkout presentation and input

The editable selected draft exposes a `Checkout` action. The checkout page shows server-trusted:

- order tab and terminal context;
- product name, captured unit price, positive whole-number quantity, and line total for every line;
- subtotal;
- signed round-off input, initially `PKR 0.00`;
- round-off reason input;
- final total;
- cash received input;
- change due when the submitted values are valid; and
- a clear action to return to the draft without mutation.

The signed adjustment accepts negative and positive PKR values. A negative value reduces the total;
a positive value increases it. The reason is required only when the adjustment is non-zero and is
limited to 500 trimmed characters. Zero adjustment must not retain a reason or create a round-off
audit event.

The server ignores any submitted subtotal, final total, change, unit price, stock balance, cashier,
shop, terminal, or confirmation flag that is not part of the server-issued confirmation context.

## 6. Amount calculation and validation

For checkout:

- `line total = captured unit price x quantity`;
- `subtotal = sum of all persisted line totals`;
- `final total = subtotal + signed round-off`; and
- `change = cash received - final total`.

The server recalculates all four values. Values must be finite, use no more than two decimal places,
and fit the supported database precision.

Validation rules are:

- the draft must contain at least one item;
- subtotal cannot be negative;
- final total cannot be negative;
- cash received cannot be negative or less than final total;
- a non-zero adjustment requires a non-blank reason and explicit confirmation;
- a zero adjustment stores a blank reason and no adjustment actor; and
- cash received greater than final total is valid and the difference is recorded as change.

A final total of `PKR 0.00` is valid when the adjustment exactly offsets the subtotal. It still
creates the one required cash payment record, with an amount of zero; cash received and change are
stored as entered and calculated. Invalid input changes no order, inventory, payment, sequence, or
audit data.

## 7. Stock validation and acknowledgement

Checkout evaluates each line against the product's current recorded stock, not the stock shown
when the draft was created. Products are locked in a deterministic order and must still be active.

For each line:

- `projected balance = locked stock on hand - sold quantity`.
- A projected balance of zero or more needs no warning.
- A projected balance below zero requires confirmation, including when the product was already
  negative before checkout.
- The warning shows product identity, current balance, sale quantity, and projected balance.
- The cashier may cancel and correct the draft or explicitly acknowledge and continue.

Acknowledgement requires no PIN or typed reason. If confirmation succeeds, each affected product
keeps its truthful projected negative balance and the sale movement records that balance. One
focused audit event records the cashier, order, time, and all acknowledged shortage details. No
automatic receipt, adjustment, or other compensating movement is created.

If stock changes after the warning is rendered, checkout recomputes it under lock. A changed or new
shortage set invalidates the old acknowledgement and displays a fresh confirmation. If the warning
disappears, checkout may proceed without recording a false shortage acknowledgement.

## 8. Conditional confirmation flow

1. The cashier submits the checkout form.
2. The server authenticates the actor, validates the session-bound terminal and current draft
   authority, checks the draft version, normalizes the inputs, and calculates current totals and
   projected stock.
3. If neither a round-off nor a shortage needs confirmation, the server completes checkout.
4. Otherwise, no business state is changed. The server shows a confirmation page containing every
   applicable warning and a signed, expiring confirmation context.
5. The cashier can cancel back to the unchanged draft or confirm.
6. On confirmation, the server reacquires all required locks and recalculates every value. Only an
   exact, current confirmation may authorize completion.
7. A stale, expired, invalid, cross-session, or changed confirmation performs no mutation and sends
   the cashier through a fresh validation/confirmation cycle.

The confirmation page never uses a free-form checkbox or hidden boolean as proof of acknowledgement.

## 9. Atomic completion flow

Within one database transaction the server:

1. locks and revalidates the active actor, configured terminal, draft, version, and current-cashier
   authority;
2. discovers the retained line/product identities while the draft is locked;
3. locks all referenced products in ascending ID order, then the retained lines in ascending line
   ID order, and revalidates the line set, captured values, product links, and active products;
4. recalculates the subtotal, validates the adjustment, reason, final total, cash received, and
   required confirmations, and computes projected balances;
5. allocates the next shop-scoped human-readable order number;
6. stores completion fields on the existing order while retaining the draft line snapshots exactly
   as captured; it does not recapture current catalog values;
7. creates the one cash payment;
8. updates every product balance and creates exactly one `SALE` movement for every sold line;
9. writes round-off and/or shortage audit events when applicable;
10. changes the order status to `COMPLETED`; and
11. creates one empty replacement draft in the same terminal slot, owned by the completing cashier.

All effects commit together. A validation, concurrency, database, payment, inventory, audit,
sequence, or replacement-draft failure rolls back every effect, including the allocated order
number. The original draft remains recoverable and no partial stock change survives.

Because Milestone 3 already persisted the draft order and its lines, checkout finalizes those
existing records inside this transaction rather than duplicating them. All completion-specific
financial, inventory, audit, numbering, status, and replacement effects are nevertheless atomic.

## 10. Successful result and fresh order

After commit, the cashier is redirected using POST/Redirect/GET to the completed order detail. It
shows the order number, items, subtotal, adjustment and reason when applicable, final total, cash
received, and change. A success message makes clear that a fresh empty order is ready.

The previous terminal slot now contains a new draft with a new database identity, version one,
and no lines. Other active tabs remain unchanged. Returning to the POS selects an appropriate
active draft using the existing workspace rules.

The human-readable number is unique within the shop, permanent, and formatted `ORD-000001`,
`ORD-000002`, and so on. The numeric portion grows beyond six digits without truncation. Failed
transactions do not consume a number.

## 11. Completed-order list

All three active roles can open `/orders/` and see only their shop's `COMPLETED` orders. Draft and
discarded orders are not listed. The page:

- orders rows by completion time newest first, with ID as a stable tie-breaker;
- paginates at 50 orders per page and preserves valid search/filter parameters;
- shows order number, Karachi date/time, completing cashier, item count, final total, status, and an
  `Adjusted` badge when the signed adjustment is non-zero;
- accepts one trimmed search query matching order number, captured product name, captured barcode,
  or an exact valid PKR subtotal/final-total amount; and
- provides an adjusted-only filter.

Search is case-insensitive for order numbers and product names, preserves barcode characters, and
uses captured order-line values rather than the current catalog. A malformed amount is still a
normal text query and produces no error. Duplicate line matches do not duplicate an order row.

Invalid page values fall back safely. Empty results show a clear message and do not disclose other
shops' existence. Unknown query parameters cannot enable deferred filters or mutations.

## 12. Completed-order detail and immutability

The detail page is addressed by the human-readable order number and shows:

- permanent order number, `COMPLETED` status, terminal, creator, current/last cashier, completing
  cashier, and completion time;
- captured product name and barcode, captured unit price, quantity, and line total for each line;
- subtotal, signed round-off, round-off reason and actor when applicable, and final total;
- payment method, payment amount, cash received, change, processing user, and time; and
- whether a stock-shortage acknowledgement was recorded, with no cashier-facing general audit log.

The page provides no edit, delete, void, return, refund, reprice, stock-correction, or receipt-print
control. Later product edits or deactivation cannot change captured sale values. Another shop's
order number returns the same non-disclosing not-found behavior as a nonexistent order.

## 13. Audit and data effects

A successful normal sale creates or changes only:

- the existing order, from `DRAFT` to `COMPLETED`;
- its retained order lines only where final snapshot normalization is required;
- one receipt payment;
- affected product stock balances;
- one immutable `SALE` inventory movement per order line; and
- one replacement empty draft.

A non-zero round-off additionally creates one audit event containing actor, order identifier,
subtotal, signed adjustment, reason, and final total. An acknowledged shortage additionally creates
one audit event containing actor, order identifier, and all affected product/current/quantity/
projected values. The immutable order, payment, and movement records remain the primary business
ledger.

Merely opening checkout, rendering confirmation, cancelling, searching history, or viewing order
detail creates no audit event.

## 14. Error and concurrency behavior

- A stale draft version is rejected with refresh guidance and no mutation.
- An inactive product blocks checkout and leaves the draft intact so it can be corrected.
- A product or line changed by another request is reloaded; stale monetary or warning context is
  never silently applied.
- Two checkout requests for the same draft produce one completed sale.
- Checkouts involving the same product serialize their balance calculation and each creates exactly
  one movement for each successfully completed sold line.
- Different products may be sold concurrently without lost updates or duplicate sequence numbers.
- A database or service exception returns a recoverable error and leaves no partial business state.
- Direct navigation to a completed draft's checkout resolves to its existing completed-order result
  for an authorized same-shop actor instead of attempting another sale.

## 15. Acceptance criteria

1. Each active owner, admin, and cashier can complete their current non-empty draft with cash.
2. Subtotal, signed adjustment, final total, cash received, and change use exact server-side PKR
   decimal arithmetic and reconcile.
3. Positive and negative non-zero adjustments require a reason and explicit confirmation; zero
   adjustment does not create adjustment evidence.
4. The final total cannot be negative and cash received cannot be less than it.
5. Sufficient-stock checkout completes without a stock warning and reduces each balance correctly.
6. A projected negative balance presents exact warning details; explicit acknowledgement allows
   completion, keeps the truthful negative balance, and creates the required audit event.
7. Changed stock or draft state invalidates stale confirmation and cannot create a false audit.
8. Order completion, payment, inventory balances/movements, audit events, sequence allocation, and
   replacement draft commit atomically or all roll back.
9. Concurrent checkout tests show no lost inventory update, duplicate sale movement, duplicate
   payment, or duplicate order number.
10. Repeated checkout of one draft returns one completed result and creates no duplicate effects.
11. A successful order has a permanent shop-scoped number and one fresh empty draft in the same
    terminal slot; the other tabs remain intact.
12. Later product edits do not change captured completed-order names, barcodes, prices, quantities,
    or totals.
13. All roles see only their shop's completed orders, newest first, with working pagination,
    order/product/barcode/amount search, and adjusted filter/badge.
14. Completed-order detail reconciles its lines, subtotal, adjustment, final total, payment, cash,
    change, actors, and time and offers no mutation control.
15. Failed or invalid checkout produces no partial financial, inventory, audit, sequence, order, or
    replacement-draft state.
16. Automated tests cover services, constraints, permissions, HTTP flows, search, snapshots,
    idempotency, rollback, and PostgreSQL concurrency.
17. The user, not Codex, performs the final frontend, keyboard/scanner, layout, and offline browser
    acceptance checks from a supplied checklist.

## 16. Explicit exclusions

- Card, bank-transfer, split, credit, or multiple payments.
- Tax, discounts, coupons, promotions, customer accounts, loyalty, or credit sales.
- Receipt printing, PDF receipts, email/SMS receipts, cash drawer, or hardware integration.
- Editing or deleting completed orders, payments, or movements.
- Returns, partial returns, refunds, voids, cancellation of completed sales, and reversal movements.
- Date, cashier, or multi-status history filters and return-oriented lookup workflow.
- Daily summaries, reports, general audit-event pages, till sessions, cash counts, and reconciliation.
- Terminal registration/picker, multiple-shop UI, online sync, and cloud operation.
- Frontend manual verification by Codex unless the user later requests it explicitly.

## 17. Approval gate

Milestone 4 implementation may begin only after:

1. this feature specification is reconciled with the approved requirements;
2. `docs/milestones/m4-checkout/technical-design.md` refines it against the current code;
3. `docs/milestones/m4-checkout/development-tasks.md` provides ordered, verifiable implementation work; and
4. the mandatory whole-package review finds and fixes all contradictions, omissions, unsafe
   assumptions, scope leakage, and acceptance-coverage gaps.

## 18. Manual-acceptance revision (v1.2)

This section replaces the v1.1 round-off and separate-checkout behavior wherever the earlier text
conflicts. Unchanged atomicity, inventory, numbering, snapshots, permissions, and history rules
continue to apply.

### 18.1 Simplified cash behavior

- The order total equals the server-trusted subtotal. There is no editable round-off/final-total
  field, reason, confirmation, PIN, or change-availability choice.
- The cashier enters only non-negative cash received.
- `signed change = cash received - total`.
- Cash received may be greater than, equal to, or less than total. Positive change means excess
  cash; negative change means a shortfall. Both complete successfully and remain visible.
- The immutable payment stores total, cash received, and signed change. No round-off audit event is
  created; the payment is the permanent financial evidence.
- Normal checkout requires one submit click from the POS. There is no separate checkout page or
  round-off confirmation screen.
- A detected stock shortage remains audited. The Complete sale action acknowledges any shortage
  visible in the current POS; a newly changed shortage may require the POS to refresh before retry.

### 18.2 Desktop POS layout

- At a target viewport of 1366x768 and 100% zoom, checkout controls remain visible without scrolling
  the page.
- The selected-order/checkout area occupies approximately two-thirds of the desktop content width.
- An always-visible active-product catalogue occupies approximately one-third on the right.
- The catalogue shows active same-shop products even before search and supports name/barcode/SKU
  filtering plus one-click add.
- Order lines and the catalogue may use their own bounded internal scrolling when their contents
  exceed available height; the cashier never needs to scroll the page to reach Complete sale.
- Smaller viewports may fall back to a responsive stacked layout and normal page scrolling.

### 18.3 Revised acceptance criteria

1. A current cashier can scan/add items, enter cash received, and complete a normal sale from the POS
   with one submit click.
2. Cash above, equal to, and below total completes; the stored signed change equals cash received
   minus total exactly.
3. No round-off, reason, confirmation, or change-availability control appears.
4. Signed change is prominently visible on completed-order list and detail, including negative
   shortfall values.
5. At 1366x768/100% zoom, page scrolling is not required to reach scanner, current lines, total,
   cash received, change guidance, and Complete sale.
6. The right third shows active same-shop catalogue products and supports search/add.
7. Atomicity, shortage audit, idempotency, inventory locking, snapshots, history isolation, and all
   unaffected v1.1 acceptance criteria continue to pass.

### 18.4 Cart quantity controls

- Every editable cart line shows explicit decrease and increase buttons on either side of the
  current quantity; the cashier does not use the browser's number-input spinner.
- Clicking either button immediately submits and persists the new quantity, recalculates line/order
  totals on the server, and refreshes the POS state. There is no separate Update button.
- Decrease remains visible but disabled at quantity one; removing the line remains a separate
  explicit action. Increase remains visible but disabled when the retained product is inactive or
  the supported quantity maximum has been reached.
- Read-only orders continue to show the quantity without mutation controls.

### 18.5 Non-blocking notifications

- Feedback messages render as a fixed toast stack and never consume POS workspace height or push
  checkout controls below the viewport.
- Every toast has an explicit close button. Success and informational feedback dismisses
  automatically after a short delay; warning and error feedback remains until dismissed or the
  user navigates away.
- Hovering or focusing an auto-dismiss toast pauses its timer so it can be read. Toasts remain
  accessible through live-region roles and keyboard-operable close buttons.
- The notification behavior is application-wide, but this refinement does not change the message
  text, business action, persistence, or authorization that produced a message.
