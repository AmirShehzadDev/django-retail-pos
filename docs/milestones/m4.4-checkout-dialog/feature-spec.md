# Milestone 4.4 Feature Specification - Keyboard-first Checkout Dialog

**Status:** Implemented; user frontend acceptance pending

**Version:** 1.0

**Approved:** 2026-08-09

## 1. Objective

Make cash checkout faster from the scanner-first POS without changing checkout, inventory, cash,
or audit rules. The compact POS footer opens one payment dialog that previews the order and supports
the scanner -> Tab -> Enter -> keypad -> Tab -> Enter workflow.

## 2. Actors and availability

- Owner, admin, and cashier receive the same interaction for an editable current draft.
- Checkout is enabled only for a populated editable draft.
- A read-only or empty draft exposes no enabled checkout interaction.
- Existing shop, terminal, role, draft ownership, stale-version, and CSRF checks remain authoritative.

## 3. Keyboard interaction

1. The barcode input remains the initial and post-mutation focus target.
2. An unmodified `Tab` pressed while that scanner input owns focus jumps directly to the enabled
   **Complete sale** trigger. `Shift+Tab`, modified keys, and Tab elsewhere retain normal behavior.
3. `Enter` or `Space` on the trigger opens the checkout dialog.
4. Opening the dialog focuses and selects all of **Cash received**. It is prefilled with the exact
   current order total, so the first number typed with the main keyboard or numeric keypad replaces
   the default.
5. The next forward `Tab` from Cash received focuses the dialog's **Complete sale** button; `Enter`
   on that button submits checkout.
6. `Escape` or **Cancel** closes the dialog without mutation and restores scanner focus.

## 4. Dialog content and behavior

- Use **Order total** for the payable amount.
- Show Cash received and signed Change, with Change updating locally as cash is edited.
- Show a compact preview of every order line: product name, quantity, captured unit price, and line
  total.
- Preserve server-rendered prices and totals; the browser preview is not authoritative.
- Cash received remains non-negative with at most two decimal places. Cash below, equal to, or
  above the order total remains allowed; signed Change equals cash received minus Order total.
- Prevent accidental repeat submission while the request is pending.
- A validation/conflict response refreshes the current server-rendered order safely and reports the
  error without claiming success.
- Successful checkout stays on the POS, shows the recent sale/toast, creates the replacement draft,
  and restores scanner focus as already implemented.

## 5. Progressive enhancement and accessibility

- Use the native accessible `dialog` element with a labelled heading, Cancel, and Complete sale.
- A `noscript` inline cash form preserves a usable no-JavaScript checkout fallback.
- The modal is bounded to the viewport and its line preview scrolls internally when necessary.
- Focus is never moved by the shortcut when the trigger is absent or disabled.
- No remote asset, frontend framework, or new runtime dependency is introduced.

## 6. Explicit exclusions

- No payment method, tax, discount, round-off reason, change-availability choice, receipt, customer,
  or calculator keypad UI.
- No change to checkout models, database schema, stock rules, negative-stock behavior, completed
  order history, returns, voids, or reports.
- No global keyboard shortcut when focus is outside the scanner.

## 7. Acceptance criteria

1. Scanner focus and physical scanning remain unchanged.
2. Scanner `Tab` focuses the enabled Complete sale trigger and Enter opens the dialog.
3. The dialog accurately previews all current lines and the server-rendered Order total.
4. Cash received starts equal to the total, focused and selected; keypad input replaces it and
   signed Change updates exactly.
5. The next Tab reaches dialog Complete sale and Enter completes exactly one sale.
6. Cancel/Escape causes no mutation and restores scanner focus.
7. Enhanced success remains on the POS with replacement draft, recent sale, toast, and scanner
   focus; failures retain recoverable persisted state.
8. Read-only/empty orders cannot invoke checkout, no-JavaScript checkout remains usable, focused
   automated tests and the full regression suite pass.
9. Actual browser focus, keyboard, keypad, scroll, responsive, and scanner behavior is verified by
   the user from the completion checklist.
