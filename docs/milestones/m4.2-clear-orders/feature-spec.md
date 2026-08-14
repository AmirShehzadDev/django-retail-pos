# Milestone 4.2 Feature Specification - Clear Order and Close Tab

**Status:** Approved; planning review passed

**Version:** 1.1

**Approved:** 2026-08-06

**Inputs:** `docs/product/mvp-requirements.md` v1.5 and the user-approved interaction decision

## 1. Objective

Replace the retained/audited draft-discard workflow with fast checkout-workspace actions that match
what the cashier intends:

- **Clear order** removes every item from a populated active order while keeping the same tab; and
- **Close tab** removes an empty tab when at least one other active tab remains.

Neither action creates a discard reason, audit event, discarded-order history, payment, inventory
movement, or order number.

## 2. Actors and permissions

Owner, admin, and cashier have the same behavior when they are the current cashier for the selected
same-shop draft on the configured terminal.

A read-only draft assigned to another cashier cannot be cleared or closed. The user must first use
the existing takeover flow. Anonymous, inactive, cross-shop, wrong-terminal, stale-version, and
crafted requests remain rejected on the server.

## 3. Clear a populated order

### Preconditions

- The selected record is an active `DRAFT`.
- The actor is its current cashier.
- The draft contains at least one line.

### Interaction

1. The workspace action is labelled **Clear order**.
2. Selecting it opens an in-POS modal dialog without navigation.
3. The dialog identifies the order and shows its item count and current PKR total.
4. It offers visible **Keep order** and **Clear order** buttons.
5. **Enter** confirms Clear order while the dialog is in its initial/default state.
6. **Escape** or **Keep order** closes the dialog without changing the draft.
7. Successful clearing updates the POS in place, keeps the same selected tab, restores scanner
   focus, and shows a compact success toast.

### Data effects

In one transaction:

- delete all `OrderItem` rows belonging to the active draft;
- set the draft subtotal to `0.00`;
- increment its optimistic version; and
- keep the same draft ID, slot, creator, current cashier, and active status.

No reason is requested or stored. No `AuditEvent` or `DISCARDED` order is created. Drafts do not
reserve stock, so product balances and inventory movements remain unchanged.

## 4. Close an empty tab

### Preconditions

- The selected record is an editable active `DRAFT`.
- It contains no lines and has a zero subtotal.
- At least one other active draft exists on the terminal.

### Interaction and effects

- The action is labelled **Close tab**.
- It executes immediately in place without a confirmation dialog.
- The empty draft row is deleted; no history or audit record is retained.
- Another existing tab becomes selected deterministically and scanner focus returns.
- A compact toast confirms that the tab was closed.

When the selected empty draft is the only active tab, **Close tab is not shown**. A crafted request
to close the last active tab is rejected without changing it.

## 5. Validation and concurrency

- Clear requires a non-empty draft; Close tab requires an empty draft and another active tab.
- Both actions require the submitted current optimistic version.
- Actor, terminal, order, and relevant line rows are locked consistently with other draft
  mutations.
- A concurrent scan/quantity/remove/takeover/checkout/clear/close produces one complete winner and a
  stale/conflict result for the loser; it never loses a committed mutation or partially clears.
- Repeated submissions cannot clear another version or close a second tab accidentally.
- Failures retain the current persisted order and return the latest server state where safe.

## 6. Accessibility and fallback

- The dialog has an accessible name/description and traps focus while open.
- Initial focus makes the approved Enter-to-confirm behavior explicit; visible focus remains clear.
- Escape and Keep order are equivalent non-destructive exits.
- After completion or cancellation, focus returns to the appropriate POS control.
- The enhanced path does not navigate. Without JavaScript, the Clear order action opens a
  server-rendered confirmation page with the same Keep order/Clear order choice; its POST clears and
  redirects to the retained draft. Close tab remains an ordinary POST that redirects to the
  selected remaining draft.

## 7. Explicit exclusions

- Retained discarded-draft records.
- `DRAFT_DISCARDED` audit events, reasons, PINs, approvals, fraud alerts, or discard reports.
- Clearing completed orders, payments, returns, voids, or inventory movements.
- Restoring cleared lines or closed empty tabs.
- Changing individual Remove, checkout, takeover, or completed-order behavior.
- Deleting legacy `DISCARDED` rows or obsolete schema fields in this interaction refinement.

## 8. Acceptance criteria

1. A populated editable draft shows Clear order and an empty eligible draft shows Close tab.
2. Clear order opens a POS dialog with item count, total, Keep order, and Clear order.
3. Enter clears from the dialog's initial state; Escape and Keep order change nothing.
4. Clear deletes all lines, resets the subtotal, increments the version, retains the same tab, and
   changes no stock/payment/audit data.
5. Close tab removes an eligible empty draft immediately without dialog/history/audit and selects
   another existing tab.
6. The last active empty tab has no Close tab action and cannot be closed by a crafted request.
7. Enhanced success/error updates remain on POS and restore appropriate focus.
8. Permission, scope, version, concurrency, progressive fallback, and regression tests pass.
9. Actual dialog layout, keyboard behavior, scanner focus, and responsive behavior are verified by
   the user, not claimed through server-side tests.

## 9. Supersession

This approved specification supersedes every MVP/Milestone 3 statement requiring a reason,
retained `DISCARDED` record, or `DRAFT_DISCARDED` audit for a new clear/close action. Historical M3
planning and completion evidence remains accurate for the implementation delivered at that time
and is marked as superseded for future behavior.
