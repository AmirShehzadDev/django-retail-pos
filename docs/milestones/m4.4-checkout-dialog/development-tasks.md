# Milestone 4.4 Development Tasks - Keyboard-first Checkout Dialog

**Status:** Complete; user frontend acceptance pending

**Prepared:** 2026-08-09

## 1. Ordered tasks

| ID | Task | Completion evidence |
|---|---|---|
| M4.4-00 | Review spec/design/tasks against project and current code | Section 3 |
| M4.4-01 | Build checkout trigger, native dialog, preview, and no-JS fallback | Template tests |
| M4.4-02 | Add scanner-to-checkout and dialog focus/keyboard behavior | Node tests |
| M4.4-03 | Preserve enhanced checkout/error/focus behavior | Sales view regression tests |
| M4.4-04 | Update project docs and add automated coverage | Docs and traceability |
| M4.4-05 | Run full verification, record completion, and commit | `docs/milestones/m4.4-checkout-dialog/completion.md` |

## 2. Detailed requirements

### M4.4-01 - Template

- Replace the inline enhanced cash dock with compact Order total and Complete sale trigger.
- Add one labelled native checkout dialog containing compact line snapshot preview, Order total,
  total-prefilled Cash received, signed Change, Cancel, and final Complete sale.
- Keep the final button immediately after cash in forward tab order and make the preview internally
  scrollable.
- Add a complete `noscript` POST fallback and omit checkout controls for read-only drafts.

### M4.4-02 - JavaScript

- Add delegated open/cancel/close handling safe across server fragment replacement.
- Intercept only unmodified Tab from the scanner when checkout is enabled.
- Select the default cash value on open, focus final submit on forward Tab, restore scanner focus on
  cancellation, and preserve exact signed Change preview.
- Keep submission double-click protection and the existing enhanced protocol.

### M4.4-03 - Server integration

- Reuse the existing form/view/service unchanged unless a rendering defect requires a focused fix.
- Preserve a bound invalid cash value in the returned dialog, version refresh, errors, replacement
  draft, recent sales, toast, and idempotency.

### M4.4-04/05 - Tests, docs, completion

- Add Django and Node assertions mapped to every acceptance criterion.
- Update milestone/project interaction text that still describes inline checkout.
- Run all project gates without performing or claiming browser/frontend verification.
- Record exact evidence and a user manual checklist, then create one short Git commit.

## 3. Mandatory planning review record

**Review date:** 2026-08-09

**Status:** PASSED after corrections

The review compared these documents with the MVP requirements, project technical design, completed
M4/M4.1 behavior, current POS fragment/enhanced checkout code, signed-change rules, permissions,
and deployment constraints. It corrected four initial ambiguities:

1. The Tab shortcut is scoped to the focused scanner and enabled checkout trigger, avoiding a
   global override of normal keyboard navigation.
2. “Keypad changes the numbers” is implemented by selecting the total-prefilled cash value, so the
   first digit replaces it; no extra on-screen calculator is added.
3. The dialog previews trusted server snapshots but does not make browser totals authoritative.
4. Moving controls into a JavaScript dialog retains a full `noscript` checkout form, so progressive
   fallback is not lost.

The repeated review found no unresolved permission, money, inventory, concurrency, fallback,
dependency, or scope conflict. Implementation may proceed.

**Completion evidence:** [Automated evidence and required user checklist](completion.md)
