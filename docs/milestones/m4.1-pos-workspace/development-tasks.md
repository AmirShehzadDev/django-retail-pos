# Milestone 4.1 Development Tasks - Compact POS Workspace Redesign

**Status:** Version 1.1 implementation and automated verification complete; user acceptance pending

**Version:** 1.0

**Prepared:** 2026-08-06

**Inputs:** Approved `docs/milestones/m4.1-pos-workspace/feature-spec.md` v1.0 and `docs/milestones/m4.1-pos-workspace/technical-design.md` v1.0

> **Historical task record:** M4.1 is complete. The later approved
> [Milestone 4.2 specification](../m4.2-clear-orders/feature-spec.md) governs Clear order and Close tab behavior.

## 1. Objective and gate

Implement the approved compact, barcode-first grocery POS shell without changing any existing
business behavior. M4.1-01 may begin only after M4.1-00 records a passed mandatory review.

## 2. Task summary

| ID | Task | Depends on | Verification focus |
|---|---|---|---|
| M4.1-00 | Mandatory planning-package review | Spec/design/tasks | Scope and implementation gate |
| M4.1-01 | Dedicated POS shell | M4.1-00 | Full-height shell and unchanged non-POS header |
| M4.1-02 | Compact toolbar and order tabs | M4.1-01 | Navigation, tabs, fragments, draft creation |
| M4.1-03 | 65/35 pane geometry | M4.1-02 | Bounded desktop and responsive fallback |
| M4.1-04 | Dense cart and checkout dock | M4.1-03 | Rows, controls, warnings, payment visibility |
| M4.1-05 | Two-column catalogue tiles | M4.1-03 | Search/add/read-only/no-result states |
| M4.1-06 | Automated verification and evidence | M4.1-04, M4.1-05 | Regression, Tailwind, traceability |
| M4.1-07 | User frontend acceptance | M4.1-06 | User-only viewport/scanner/offline check |
| M4.1-08 | Recent sales query and panel | M4.1-00 | Scoped three-row read model and UI |
| M4.1-09 | Enhanced checkout response | M4.1-08 | In-place success/error protocol and fallback |
| M4.1-10 | Completion interaction and toast | M4.1-09 | State refresh, confirmation, focus, no redirect |
| M4.1-11 | Refinement verification and evidence | M4.1-10 | Regression and user checklist |

## 3. Detailed tasks

### M4.1-00 - Mandatory planning-package review

**Status:** Completed

**Work**

- Review the approved feature specification, technical design, and this task document together
  against project requirements/milestones/design, completed M3/M3.1/M4 behavior, `AGENTS.md`, and
  current templates, JavaScript, forms, views, tests, and fragment protocol.
- Fix contradictions, omissions, scope growth, unsafe interaction assumptions, missing state
  coverage, and task dependency problems; repeat until implementation-ready.
- Record findings and the passed gate in Section 6.

**Acceptance**

- No model/service/permission/checkout behavior is accidentally changed.
- Fragment, progressive-enhancement, responsive, typography, and user-only verification boundaries
  are explicit.
- M4.1-01 remains blocked until the review result is `PASSED`.

### M4.1-01 - Dedicated POS shell

**Work**

- Add a default-preserving `app_header` block around the existing base header.
- Override that block only in the POS workspace.
- Replace the current max-width/padded POS main class with the approved dedicated full-height shell.
- Preserve skip link, toast stack, main target, live region, and local scripts.
- Add template tests proving non-POS pages retain the original header/navigation.

**Acceptance**

- POS has no full application header and uses the desktop viewport height.
- Home, Orders, Products, Inventory, Users, and settings screens are unaffected.
- No whole-page desktop height is consumed by hidden/empty POS chrome.

### M4.1-02 - Compact toolbar and order tabs

**Work**

- Add terminal/shop identity, draft tabs, New order, Orders, Products, cashier identity, and Exit POS
  to one compact toolbar.
- Redesign tab markup as horizontal compact tabs while preserving root ID/data hook, link query,
  tab roles, selected state, ownership state, subtotal, and empty state.
- Keep `data-pos-new-draft` and its hidden/toggle behavior compatible with `pos.js`.
- Extend UI tests for toolbar links, current user, selected tab semantics, and enhanced fragments.

**Acceptance**

- Up to three tabs and New order remain usable without large tab cards.
- Enhanced add/quantity/remove/scan updates still replace the tab fragment correctly.
- Exit POS returns to authenticated Home and does not log out or mutate data.

### M4.1-03 - 65/35 pane geometry

**Work**

- Replace the equal three-column layout with desktop `13fr/7fr` order/catalogue columns.
- Remove structural gap, large rounding, nested panel shadows, and excess outer padding.
- Keep cart and catalogue content regions independently scrollable on desktop.
- Preserve natural stacked responsive fallback below desktop.
- Add template contract assertions for geometry and bounded overflow utilities.

**Acceptance**

- Static markup encodes approximately 65/35 desktop geometry.
- Order header/scanner and checkout dock are non-scrolling; only cart lines scroll.
- Catalogue search is non-scrolling; only product results scroll.

### M4.1-04 - Dense cart and checkout dock

**Work**

- Replace cart-line cards with divider-based 48-56px-target rows containing snapshot identity, unit
  price, stepper, line total, and Remove.
- Preserve all existing forms, hidden values, disabled boundaries, mutation hooks, labels, and
  inactive-product restrictions.
- Compact order metadata, scanner, read-only takeover, empty state, and shortage strip.
- Restyle the existing checkout dock to the approved font hierarchy and fixed footer layout.
- Render an unambiguous read-only footer without active cash/checkout affordances.
- Update tests for fields, values, controls, warnings, states, and absence of oversized POS text.

**Acceptance**

- Normal lines are dense without dropping any approved value/control.
- Total is 24px; default content is 14px; secondary content is 12px; no POS text is `text-3xl+`.
- Checkout endpoint/fields and signed-Change preview hooks are unchanged.

### M4.1-05 - Two-column catalogue tiles

**Work**

- Compact the catalogue title/search header while preserving selected draft and Clear search.
- Render results as two-column product tiles in the existing result order/limit.
- Make the whole editable tile the existing Add form submit target.
- Render non-interactive tiles for read-only orders.
- Preserve name, price, stock, barcode/SKU, empty results, shop/active filtering, and no images.
- Add UI assertions for grid, tile POST forms, read-only state, and deferred-feature absence.

**Acceptance**

- Product add remains one existing CSRF/versioned mutation.
- Tiles are compact, text-only, and contain all approved retail information.
- No category/image/schema/query behavior is introduced.

### M4.1-06 - Automated verification and evidence

**Work**

- Run template parsing, focused UI/view/integration tests, full Sales suite, and full PostgreSQL suite.
- Run JavaScript tests/syntax, Ruff, Django checks, migration drift, local Tailwind build, dependency
  checks where relevant, and `git diff --check`.
- Review the final diff for unintended behavior/model/URL/dependency changes.
- Create `docs/milestones/m4.1-pos-workspace/completion.md` with automated evidence and a user-owned acceptance checklist.
- Commit with the configured Amir Shahzad identity and a short message.

**Acceptance**

- All automated checks pass and no migration is generated.
- Generated local CSS is committed and no runtime network dependency is introduced.
- Every feature acceptance criterion is automated or assigned explicitly to M4.1-07.

### M4.1-07 - User frontend acceptance

**Owner:** User only

**Work**

- Verify 1366x768/100% fit, typography, 65/35 balance, cart/catalogue internal scrolling, empty and
  long-content states, all three tabs, read-only/takeover, shortage/inactive states, signed Change,
  toast overlap, physical scanner/focus, keyboard controls, responsive fallback, and offline assets.

**Acceptance**

- User approves the visual/interaction result or reports defects for correction.
- Codex does not claim hands-on evidence from template tests.

### M4.1-08 - Recent sales query and panel

**Status:** Completed

**Work**

- Add a permission-checked, same-shop, paid-completed-order query limited to the newest three rows.
- Load it in every workspace context and render a fixed Recent sales footer below catalogue results.
- Show order number, local completion time, total, signed/coloured Change, and View detail link.
- Cover ordering, limit, payment requirement, shop isolation, permissions, empty state, and markup.

**Acceptance**

- The query is bounded and does not introduce per-row queries.
- Recent sales never exposes another shop or a non-paid/non-completed record.
- The product list retains its independent scroll region.

### M4.1-09 - Enhanced checkout response

**Status:** Completed

**Work**

- Detect the frozen enhanced header on checkout POST.
- On success, return current tabs/panel state selected to the replacement draft plus immutable
  completion presentation data.
- Return structured enhanced validation/conflict/not-found/service errors without false success.
- Preserve the existing non-enhanced completed-detail redirect and Django messages.
- Extend view/integration tests for success, repeat/idempotency, errors, CSRF, and fallback.

**Acceptance**

- Enhanced success returns JSON 200 and never redirects.
- The response selects the fresh same-slot draft and includes refreshed Recent sales.
- Failed enhanced checkout leaves the original draft/payment state correct.

### M4.1-10 - Completion interaction and toast

**Status:** Completed

**Work**

- Enhance the checkout form through the existing mutation pipeline and double-submit guard.
- Apply returned fragments/URL, announce order/total/Change, and restore scanner focus.
- Add safe dynamic success-toast creation to the existing fixed notification stack.
- Add JavaScript tests for completion formatting/event dispatch and dynamic toast behavior.

**Acceptance**

- Successful enhanced checkout remains on POS with a fresh order ready.
- Other draft tabs are retained and Recent sales/catalogue stock update in the same response.
- No HTML from the server completion object is inserted as executable content.

### M4.1-11 - Refinement verification and evidence

**Status:** Completed

**Work**

- Run focused checkout/query/UI/JavaScript tests, complete Sales and PostgreSQL suites, Ruff, Django
  checks, migration drift, local Tailwind build, dependencies, static collection, and diff checks.
- Review the final diff against the approved no-business-change boundary.
- Update `docs/milestones/m4.1-pos-workspace/completion.md`, commit with configured identity, and provide the user-only checklist.

**Acceptance**

- All automated checks pass with no model/migration/dependency change.
- Browser, scanner, visual, focus, and offline checks remain explicitly assigned to the user.

## 4. Explicit exclusions

- Models, migrations, services, forms, URLs, permissions, transaction logic, and business rules.
- Product photos/categories and every deferred feature in the approved specification.
- Browser/visual/scanner/offline verification by Codex.

## 5. Acceptance traceability

| Feature acceptance | Tasks |
|---|---|
| AC1 desktop fit | M4.1-01, M4.1-03, M4.1-04, M4.1-07 |
| AC2 65/35 geometry | M4.1-03, M4.1-07 |
| AC3 compact typography | M4.1-01-M4.1-05, M4.1-07 |
| AC4 dense cart controls | M4.1-04, M4.1-06, M4.1-07 |
| AC5 fixed checkout | M4.1-03, M4.1-04, M4.1-07 |
| AC6 text-only catalogue | M4.1-05, M4.1-06, M4.1-07 |
| AC7 behavior regression | M4.1-02-M4.1-06 |
| AC8 offline | M4.1-01-M4.1-06, M4.1-07 |
| AC9 verification split | M4.1-06, M4.1-07 |
| AC10 in-place checkout | M4.1-09-M4.1-11 |
| AC11 Recent sales | M4.1-08, M4.1-11 |
| AC12 error/fallback behavior | M4.1-09-M4.1-11 |

## 6. Mandatory planning-review record

**Result:** PASSED

**Reviewed:** 2026-08-06

**Sources reviewed:** `AGENTS.md`, `docs/product/mvp-requirements.md`, `docs/product/roadmap.md`, project
`docs/architecture/technical-design.md`, completed M3/M3.1/M4 behavior, the approved M4.1 specification and design,
current POS templates, `pos.js`, forms/view context, enhanced response protocol, and UI/integration
tests.

**Findings resolved:**

1. Clarified that Exit POS returns to authenticated Home; logout stays in the normal shell.
2. Made fixed toasts, skip navigation, and the main target explicit invariants when suppressing the
   normal header.
3. Required read-only orders to omit editable cash and completion controls, not merely disable them.
4. Froze CSRF/version/progressive-enhancement behavior for whole-tile catalogue forms.
5. Clarified that the two-column catalogue applies within its 35% pane and preserves current query
   ordering, limits, shop filtering, and active filtering.
6. Reconfirmed that actual pixel fit, physical scanner behavior, keyboard focus, responsive visuals,
   and offline browser presentation are user-owned checks and will not be claimed by automation.

No unresolved feature, permission, data, transaction, dependency, or migration decision remains.
M4.1-01 through M4.1-06 are authorized for implementation.

### Version 1.1 refinement review

**Result:** PASSED

**Reviewed:** 2026-08-06

**Sources reviewed:** approved MVP/M4/M4.1 requirements, project and milestone designs, current
checkout service/view, workspace query/context, two-fragment JSON protocol, POS/toast JavaScript,
same-shop order-history policy, current templates, and checkout/UI/integration tests.

**Findings resolved:**

1. Kept the atomic checkout service, locking, stock, payment, audit, and idempotency behavior frozen.
2. Preserved the completed-detail redirect for normal/no-JavaScript POSTs.
3. Limited Recent sales to three newest same-shop completed records having a payment.
4. Reused the existing tabs and draft-panel fragments so stock, the fresh order, and Recent sales
   update together without a new fragment protocol.
5. Required structured JSON for every enhanced checkout outcome and no queued Django messages on
   enhanced paths.
6. Required server-formatted completion strings and text-only dynamic toast insertion.
7. Assigned actual no-navigation, panel fit, focus, scanner, toast, and offline evidence to the user.

No unresolved feature, security, data, transaction, fallback, or dependency decision remains.
M4.1-08 through M4.1-11 are authorized for implementation.
