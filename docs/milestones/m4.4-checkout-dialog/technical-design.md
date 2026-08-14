# Milestone 4.4 Technical Design - Keyboard-first Checkout Dialog

**Status:** Implemented; automated verification passed

**Version:** 1.0

**Prepared:** 2026-08-09

## 1. Architectural choice

Keep the current checkout form, endpoint, `CheckoutForm`, service transaction, enhanced response
protocol, and server-rendered POS fragments. Move the enhanced cash controls into a native dialog
inside `draft_panel.html`; retain a compact footer trigger and a `noscript` fallback form. No model,
migration, URL, or dependency change is required.

## 2. Template structure

For a writable selected draft:

- footer: server-rendered Order total and enabled/disabled `data-pos-checkout-trigger` button;
- dialog: `data-pos-checkout-dialog`, accessible title/description, order-line preview, Order total,
  the existing checkout POST form, Cash received, signed Change, Complete sale, and Cancel;
- fallback: a `noscript` checkout form using the same endpoint, hidden version, total-prefilled cash
  input, and submit button.

Each preview row uses the draft's immutable name/unit-price snapshots and calculated line total.
The cart and checkout form continue to share the selected draft/version rendered by one server
context. Form errors are rendered next to Cash received and exposed to assistive technology.

## 3. JavaScript behavior

Extend delegated `pos.js` handling so fragment replacement needs no per-element reinitialization:

- intercept unmodified Tab only from `[data-pos-scanner]` when an enabled visible checkout trigger
  exists, then focus that trigger;
- clicking/activating the trigger calls `showModal()`, runs the existing exact Change preview, then
  focuses and `select()`s Cash received;
- Cancel and native Escape close the dialog and asynchronously force scanner focus;
- ensure forward Tab from Cash received targets dialog Complete sale (DOM order plus a focused key
  guard), while Shift+Tab remains normal;
- update signed Change from exact integer minor-unit helpers on every input;
- existing delegated checkout submission posts the same form and enhanced header. Server fragment
  replacement removes the open dialog on success/error; subsequent scanner focus uses the new
  panel.

Export small pure keyboard-decision helpers for Node tests. Do not create a client cart, derive
prices, or bypass the checkout form/service.

## 4. Error, concurrency, and fallback behavior

- Empty/read-only drafts render no enabled trigger and cannot be shortcut-opened.
- Invalid local cash text shows `PKR --`; server validation remains final.
- Pending submission disables only submit controls and existing stale-version/idempotency behavior
  prevents duplicate completion.
- Enhanced validation/conflict continues returning a fresh panel and message. The submitted cash
  value is retained when the server returns a bound invalid form.
- Without JavaScript, the `noscript` form performs the existing POST/redirect flow.
- Cancellation, opening, preview calculation, and keyboard movement perform no server request.

## 5. Verification design

- Django template tests cover trigger/dialog/fallback hooks, line snapshots, field defaults/errors,
  and empty/read-only exclusions.
- Node tests cover shortcut eligibility, dialog key decisions, exact cash parsing/change, and
  existing queue/completion behavior.
- Existing checkout service/view tests prove totals, cash, signed Change, stock, idempotency,
  concurrency, replacement draft, and enhanced fragments.
- Run checks, migration drift, focused sales tests, full Django tests, Node tests/syntax, Ruff,
  Tailwind build, static collection, and diff checks.
- Real browser focus, native dialog behavior, keypad/scanner input, and layout remain user-owned
  manual verification.
