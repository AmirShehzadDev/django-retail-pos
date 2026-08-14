# Milestone 4.4 Completion - Keyboard-first Checkout Dialog

**Implementation status:** Complete

**User frontend acceptance:** Pending

**Completed:** 2026-08-09

## Delivered behavior

- The focused scanner's unmodified Tab key moves directly to the enabled Complete sale trigger.
- Enter/Space/click opens a bounded native checkout dialog without leaving the POS.
- The dialog previews every captured order line with quantity, unit price, and line total.
- Order total is clearly labelled; Cash received defaults to the exact total and is focused/selected
  for immediate keyboard or numeric-keypad replacement.
- Signed Change updates from exact minor-unit arithmetic while cash is edited.
- Forward Tab from Cash received focuses the final Complete sale button; Enter uses the existing
  atomic checkout endpoint.
- Cancel/Escape makes no change and restores scanner focus.
- Enhanced success retains replacement draft, recent sale, toast, stock update, and scanner focus;
  invalid cash is returned in a reopened dialog with its server error.
- Empty/read-only drafts cannot open checkout, and a `noscript` cash form preserves fallback use.
- No model, migration, checkout-service, inventory, payment, audit, or permission rule changed.

## Automated evidence

- Focused POS/template/checkout tests: **21 passed** in 41.309 seconds.
- Full Django suite against PostgreSQL: **348 passed** in 582.912 seconds.
- JavaScript suite: **16 passed**, including the new scanner/dialog keyboard decisions and existing
  toast, return-refund, scanner queue, exact cash, product lookup, and stock-preview checks.
- Django system check: no issues.
- Migration drift: no changes detected.
- Ruff lint: passed; Ruff formatting: **180 files already formatted**.
- Python dependency check: no broken requirements.
- JavaScript syntax checks: passed.
- Tailwind 4.3.3 production CSS build: passed.
- Django static collection: passed.
- `git diff --check`: passed.

Expected permission, CSRF, conflict, validation, not-found, and simulated service-unavailable log
entries were exercised by negative-path tests; the suite finished successfully.

## Required user frontend checklist

Codex did not perform browser/frontend verification, per project instruction.

1. Open POS with one editable empty order and confirm the scanner input owns focus.
2. Add two different products (including quantity greater than one) and confirm scanner focus
   returns after each addition.
3. With the scanner focused, press Tab. Confirm focus jumps directly to the footer Complete sale
   button. Confirm Shift+Tab and Tab from other controls still behave normally.
4. Press Enter. Confirm one modal opens and lists both products, quantities, unit prices, line
   totals, and the correct Order total.
5. Confirm Cash received equals Order total and is already focused with the whole value selected.
6. Type a different value using the physical numeric keypad. The first digit should replace the
   default and signed Change should update correctly for cash below and above the total.
7. Press Tab once. Confirm the modal Complete sale button receives focus; press Enter once.
8. Confirm no page redirect occurs, exactly one recent sale appears, a fresh empty order is ready,
   inventory changed once, and scanner focus is restored.
9. On another populated draft, open the modal and test Escape, then Cancel. Both must preserve all
   lines/totals and return focus to the scanner.
10. Test at the shop's normal resolution/zoom with enough lines to scroll. The dialog must remain
    fully usable, with only the line-preview area scrolling and payment actions visible.
11. Repeat once with the real USB barcode scanner and once while the computer is disconnected from
    the internet.

Report any failed checklist step with a screenshot and the exact key sequence used.
