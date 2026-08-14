# Milestone 4 Development Tasks - Cash Checkout and Order History

**Status:** Revised implementation complete; user frontend acceptance pending

**Version:** 1.1

**Prepared:** 2026-08-04  
**Planning review passed:** 2026-08-04  
**Inputs:** `docs/milestones/m4-checkout/feature-spec.md` v1.1 and `docs/milestones/m4-checkout/technical-design.md` v1.1

> **Historical task record:** These completed tasks preserve the Milestone 4 implementation
> evidence. The approved [Milestone 4.2 specification](../m4.2-clear-orders/feature-spec.md) governs the later
> Clear order and Close tab refinement.

## 1. Objective and implementation gate

Implement one atomic cash-checkout path from the existing Milestone 3 draft, create its permanent
financial/inventory evidence and replacement draft, and expose read-only completed-order history.

No implementation task may start until M4-00 records a passed whole-package review. Tasks are
ordered by dependency and each task includes focused automated tests. The final frontend acceptance
belongs to the user and is not performed by Codex unless explicitly requested.

## 2. Ordered task summary

| ID | Task | Depends on | Verification focus |
|---|---|---|---|
| M4-00 | Mandatory planning-package review | Planning documents | Scope and consistency gate |
| M4-01 | Sequence and audit vocabulary | M4-00 | Core schema/data/bootstrap |
| M4-02 | Completed-order and payment schema | M4-01 | Financial/state constraints |
| M4-03 | Sale movement source schema/helper | M4-02 | Immutable linked stock ledger |
| M4-04 | Checkout values, evaluation, and signing | M4-03 | Exact money and confirmation trust |
| M4-05 | Atomic checkout service | M4-04 | Completion, rollback, idempotency |
| M4-06 | Checkout HTTP flow and templates | M4-05 | Forms, CSRF, PRG, warnings |
| M4-07 | Completed-order history and detail | M4-05 | Permissions, search, pagination |
| M4-08 | Concurrency, rollback, and regression suite | M4-06, M4-07 | PostgreSQL safety/full suite |
| M4-09 | Automated completion evidence | M4-08 | Docker checks and traceability |
| M4-10 | User manual frontend acceptance | M4-09 | User-only release check |

## 3. Detailed tasks

### M4-00 - Mandatory planning-package review

**Status:** Completed; gate passed on 2026-08-04

**Work**

- Review `docs/milestones/m4-checkout/feature-spec.md`, `docs/milestones/m4-checkout/technical-design.md`, and this task file together against
  `docs/product/mvp-requirements.md`, `docs/product/roadmap.md`, `docs/architecture/technical-design.md`, approved M3/M3.1 behavior, project
  `AGENTS.md`, and the current code/migrations/tests.
- Check contradictions, missing requirements, speculative M5/M6 work, unsafe trust or concurrency
  assumptions, migration compatibility, task ordering, and acceptance/test traceability.
- Fix findings in their owning documents, rerun the review, and record the result in Section 7.

**Acceptance**

- Every finding is either corrected or explicitly resolved within approved M4 scope.
- Feature behavior, schema/services/UI design, and tasks are mutually consistent.
- Section 7 says `PASSED` before M4-01 begins.

### M4-01 - Sequence and audit vocabulary

**Work**

- Add `core.DocumentSequence` for the shop-scoped `ORDER` sequence with unique/check constraints.
- Add the locked allocation/`ORD-000001` formatter service.
- Create an existing-shop data migration and update `bootstrap_pos` to create the sequence
  idempotently for a new shop.
- Add `ORDER_ROUNDING_APPLIED` and `STOCK_SHORTAGE_ACKNOWLEDGED` audit choices.
- Add focused model, service, migration, and bootstrap tests, including rollback/non-consumption.

**Acceptance**

- Every bootstrapped/existing shop has exactly one order sequence.
- Locked allocations are unique, grow beyond six digits without truncation, and roll back with the
  caller transaction.
- Bootstrap repetition does not reset or duplicate an existing sequence.
- No return-number behavior is introduced.

### M4-02 - Completed-order and payment schema

**Work**

- Extend `Order.Status` with `COMPLETED` and add number, completion actor/time, signed adjustment,
  reason/actor, final total, and shortage-acknowledged fields.
- Replace/extend state constraints without weakening the existing draft/discard rules.
- Add conditional shop/order-number uniqueness and completed-history index.
- Add insert-only cash `Payment` with a protected one-to-one order link and exact financial
  constraints.
- Create a migration compatible with all current M3 draft/discarded rows.
- Add model/constraint/immutability tests for valid and invalid states, including a zero-total sale.

**Acceptance**

- Draft and discarded data migrates without fabricated completion values.
- Database constraints reject inconsistent completed totals, rounding evidence, payment/change,
  duplicate payment, duplicate number, and mixed discard/completion state.
- A valid completed order plus one cash payment can be represented exactly.
- Current draft/discard service and model tests still pass.

### M4-03 - Sale movement source schema and inventory helper

**Work**

- Add the nullable protected `InventoryMovement.order_item` source link.
- Add sale sign/source/one-per-line constraints while preserving existing receipt/adjustment rows.
- Add the internal already-locked sale movement helper without exposing `SALE` in manager inventory
  forms/services.
- Keep movement update/delete guards and add source-specific model/service tests.
- Extend inventory reconciliation expectations so linked sale movements reconcile with product
  balances without special correction behavior.

**Acceptance**

- A sale line can create exactly one negative linked movement with its truthful resulting balance.
- `SALE` without a source, non-negative sale quantity, duplicate source, or a source on current
  receipt/adjustment is rejected.
- Receipt and adjustment permissions, audits, and behavior do not regress.
- Negative stock remains valid and no correction movement is synthesized.

### M4-04 - Checkout values, evaluation, forms, and confirmation signing

**Work**

- Add exact fixed-precision parsing/calculation helpers and immutable checkout evaluation/warning
  value objects.
- Implement read-only checkout evaluation for current draft lines and projected stock.
- Add typed confirmation-required behavior representing round-off and exact shortage requirements.
- Implement the dedicated 10-minute, session-bound signed confirmation payload.
- Add checkout, confirmation, and completed-order-search forms.
- Test malformed, overflow, excessive precision, positive/negative/zero adjustment, reason,
  final-total, tender/change, and confirmation tampering/expiry/session/version boundaries.

**Acceptance**

- No float conversion or client-supplied calculated value enters the domain calculation.
- Evaluation makes no order, stock, payment, sequence, movement, audit, or replacement mutation.
- Non-zero adjustment and each current negative projection are represented as explicit confirmation
  requirements.
- A signature cannot authorize a different actor, session, draft/version, amount, reason, or warning
  set.

### M4-05 - Atomic checkout service

**Work**

- Implement `complete_cash_checkout` using the documented actor/terminal/draft/product/item/sequence
  lock order and one outer transaction.
- Revalidate current cashier, version, line set, exact snapshots/totals, product activity, money,
  and current warning requirements after locks are held.
- Allocate the number, finalize the existing order, create payment, update products, append one sale
  movement per line, write conditional audits, and create the same-slot replacement draft.
- Implement already-completed idempotent result behavior.
- Add focused service tests for normal sale, both round-off signs, excess cash/change, zero total,
  shortage acknowledgement, stale evidence, actors/shops/terminal, snapshots, other tabs, and all
  business side effects.
- Add injected failures after each critical write phase to prove total rollback, including sequence.

**Acceptance**

- One valid call creates one internally reconciled completed aggregate and fresh draft.
- Non-zero round-off and shortage audit payloads contain the approved exact values and actor.
- Insufficient acknowledged stock may go negative and has one linked movement per sold line.
- Invalid/stale/failed calls leave the original draft and every ledger unchanged.
- Repeated completion yields the same result without duplicate number/payment/movement/audit/draft.

### M4-06 - Checkout HTTP flow and templates

**Work**

- Add checkout GET/POST and confirmation POST URLs/views under the existing `/pos/` namespace.
- Map domain validation, stale, permission, confirmation-required, already-completed, and unexpected
  recoverable outcomes to safe HTTP behavior.
- Build Tailwind-styled checkout and combined confirmation templates using server-trusted values.
- Add the checkout action to an editable non-empty draft and the appropriate completed-result link.
- Use PRG to completed detail after success and preserve CSRF/no-mutation-on-GET rules.
- Add form/view/template tests for role parity, current-cashier authority, signature boundaries,
  conditional warnings, success redirect, errors, and absence of client-authoritative fields.

**Acceptance**

- A zero-adjustment/sufficient-stock POST can complete directly.
- A non-zero adjustment and/or shortage renders one exact confirmation page and mutates nothing
  until a valid confirmation POST.
- Cancel/stale/expired/tampered confirmation cannot partially complete a sale.
- Successful refresh cannot repeat checkout, and returning to POS exposes the fresh draft.
- Checkout remains functionally usable with JavaScript disabled and all assets remain local.

### M4-07 - Completed-order history and detail

**Work**

- Add same-shop completed-order list/detail query functions with deterministic ordering and
  efficient related loading/annotations.
- Add the separate `/orders/` URL namespace, role guards, list/detail views, and search form.
- Implement 50-row pagination, query preservation, order number/snapshot product/barcode/exact
  amount search, and adjusted-only filtering without duplicate rows.
- Build read-only list/detail templates with all approved rows, totals, payment, actors, warning
  indicator, status, and adjusted badge.
- Add Orders navigation for owner, admin, and cashier.
- Add permission, cross-shop, search/filter/pagination, snapshot, query-count where useful, and
  immutable-control-absence tests.

**Acceptance**

- All three roles see all and only their shop's completed orders newest first.
- Search uses captured line data and exact supported amounts; adjusted filtering and pagination work
  together without duplicates.
- Detail values reconcile with the payment and line snapshots and expose no edit/delete/return/void
  or receipt action.
- Drafts/discarded orders and foreign-shop identifiers are not disclosed.
- Deferred date/cashier/status/report/audit behaviors are absent.

### M4-08 - Concurrency, rollback, and regression suite

**Work**

- Add PostgreSQL `TransactionTestCase` coverage using independent connections, barriers, and bounded
  threads for same-draft idempotency, same-product stock serialization, emerging shortages,
  concurrent order-number allocation, and documented lock-order completion.
- Confirm each successful sold line has one movement and each product's final balance matches its
  ordered ledger.
- Run focused M0-M3.1 regression suites, fixing only M4-caused regressions.
- Verify migrations forward on representative current data and that no unplanned migration remains.

**Acceptance**

- Concurrency tests demonstrate no lost update, duplicate ledger record/number, false warning
  acknowledgement, or deadlock within bounded test time.
- All rollback injection tests leave no partial state.
- Existing authentication, catalog, inventory, POS drafting, takeover/discard, and cashier catalogue
  behavior passes unchanged.

### M4-09 - Automated completion evidence

**Work**

- Run the configured local Tailwind build/check for any new utility classes.
- Run inside Docker: migration drift check, Django system checks, focused M4 tests, and full test
  suite.
- Record commands/results and acceptance/exit-criterion traceability in the milestone completion
  evidence or this task document.
- Inspect `git diff`, confirm only intended files, and create short logical commits using the
  configured Amir Shahzad identity.

**Acceptance**

- `makemigrations --check --dry-run`, `manage.py check`, focused tests, and full tests pass in Docker.
- Generated local CSS is committed when changed; runtime uses no CDN/network asset.
- Every feature acceptance criterion and milestone exit criterion has automated evidence or is
  explicitly assigned to M4-10.
- Milestone is not described as live-ready; M5 returns and later deployment/backups remain gates.

### M4-10 - User manual frontend acceptance

**Owner:** User only

**Work**

- Codex supplies a concise ordered checklist covering login-to-sale, both round-off signs, cash and
  change, sufficient/insufficient stock warnings, fresh-tab behavior, completed list/detail,
  search/filter/pagination, keyboard/scanner interaction, layout, and offline browser assets.
- User performs the checks on Windows using the intended browser and scanner/keyboard.
- Any failure is reported before Milestone 4 is approved.

**Acceptance**

- User confirms required frontend flows and offline presentation, or identified defects are fixed
  and retested.
- Codex does not claim these hands-on checks from automated test results.

## 4. Acceptance traceability

| Feature acceptance | Primary tasks |
|---|---|
| AC 1-4 cash and adjustment | M4-02, M4-04, M4-05, M4-06 |
| AC 5-7 stock warnings | M4-03, M4-04, M4-05, M4-06, M4-08 |
| AC 8 atomicity | M4-01-M4-05, M4-08 |
| AC 9 concurrency | M4-03, M4-05, M4-08 |
| AC 10 idempotency | M4-02-M4-05, M4-08 |
| AC 11 number/replacement | M4-01, M4-02, M4-05, M4-06 |
| AC 12 snapshots | M4-02, M4-05, M4-07 |
| AC 13-14 history/detail | M4-07 |
| AC 15 rollback | M4-05, M4-08 |
| AC 16 automated tests | M4-01-M4-09 |
| AC 17 user frontend verification | M4-10 |

## 5. Milestone exit-criterion traceability

| Milestone 4 exit criterion | Evidence tasks |
|---|---|
| Login, scan, calculate, cash, complete, reduce stock | M4-05, M4-06, M4-09, M4-10 |
| Failed checkout has no partial state | M4-05, M4-08, M4-09 |
| Concurrent balances and one movement per line | M4-03, M4-08, M4-09 |
| Product edits do not change completed sale | M4-02, M4-05, M4-07 |
| Newest-first orders and role visibility | M4-07, M4-09 |
| Both adjustment signs reconcile and audit | M4-02, M4-04-M4-06, M4-09 |

## 6. Explicit exclusions

- Returns, voids, refunds, reversals, and M5 status transitions.
- Daily summary, reports, general audit history, and M6 reconciliation screens.
- Receipt output/hardware, cards, split payments, tax, discount, customer, or till sessions.
- Date/cashier/status history filters beyond completed-only M4 history.
- Terminal selection/registration and online/cloud behavior.
- Frontend manual verification by Codex.

## 7. Mandatory planning-review record

**Result:** PASSED on 2026-08-04

**Reviewed inputs**

- `docs/product/mvp-requirements.md` v1.4 and `docs/product/roadmap.md` v1.3;
- `docs/architecture/technical-design.md` v0.5;
- approved/completed Milestone 3 and 3.1 planning and behavior;
- current core, sales, inventory, catalog, authentication, URL, bootstrap, migration, and test code;
- project `AGENTS.md`; and
- `docs/milestones/m4-checkout/feature-spec.md`, `docs/milestones/m4-checkout/technical-design.md`, and `docs/milestones/m4-checkout/development-tasks.md` together.

**Findings fixed before the rerun**

1. Changed the replacement draft from version zero to version one so it matches the existing model
   default, database constraint, and `_create_order` behavior.
2. Removed wording that could imply catalog values are recaptured at checkout. Completion retains
   the exact Milestone 3 product-name, barcode, unit-price, quantity, and line-total snapshots.
3. Aligned the feature flow with the technical deadlock-avoidance order: draft, products in ID
   order, then lines in ID order, then sequence.
4. Clarified that monetary input accepts at most two decimal places and is stored/displayed to two,
   rather than incorrectly requiring users to type trailing zeroes.
5. Clarified that checkout finalizes the already-persisted M3 order and lines; it atomically creates
   only completion-specific financial, inventory, audit, numbering, and replacement effects.

**Resolved scope checks**

- M4 includes completed-only history with order number, snapshot product/barcode, exact amount
  search, and adjusted filtering. Date/cashier/status return lookup remains M5, consistent with the
  milestone split.
- Only the `ORDER` sequence row is introduced now. The project design's future `RETURN` sequence is
  deferred to M5 to satisfy just-in-time planning and avoid speculative functionality.
- Returns, voids, refunds, reversal presentation, daily reporting, general audit UI, receipts, tax,
  cards, and till reconciliation remain outside M4.
- Frontend/manual verification remains assigned only to the user; automated backend/template tests
  do not claim that evidence.

**Rerun conclusion**

No unresolved contradiction, requirement omission, unsafe trust boundary, migration dependency
problem, lock-order conflict, task dependency gap, acceptance-coverage gap, or later-milestone scope
leak remains. The three documents are mutually consistent and implementation-ready. Implementation
is intentionally not started by this planning package.

## 8. Completion rule

Milestone 4 is technically complete only when M4-01 through M4-09 pass and their evidence is
recorded. It is approved only after the user completes M4-10. The project is still not ready for
live shop use until at least returns, backups, and deployment/recovery milestones are complete.

## 9. Implementation and automated-verification record

**Result:** M4-01 through M4-09 PASSED on 2026-08-05

- Core order sequence and audit vocabulary implemented with existing-shop migration/bootstrap.
- Completed-order, immutable cash-payment, and linked sale-movement schema implemented.
- Exact cash checkout, signed round-off/shortage confirmation, atomic inventory/payment/audit writes,
  idempotency, and same-slot replacement draft implemented.
- Checkout pages and same-shop read-only completed-order list/detail implemented with local Tailwind.
- Dedicated service, constraint, signing, HTTP/CSRF, history, rollback, and PostgreSQL concurrency
  coverage passes.
- All 135 Sales tests and the complete 297-test project suite pass against PostgreSQL.
- Migration drift, Django checks, Ruff, local Tailwind build, dependency checks, npm audit, static
  collection, inventory reconciliation, and existing POS JavaScript tests pass.
- Development migrations were applied successfully to the Docker-hosted PostgreSQL database.

M4-10 remains user-owned. See `docs/milestones/m4-checkout/completion.md` for the required manual checklist. Codex did not
perform browser, visual, scanner-hardware, responsive, or offline frontend verification.

## 10. Manual-acceptance revision tasks

The user rejected the v1.1 multi-screen round-off workflow during M4-10. These tasks supersede the
affected M4-04, M4-06, M4-07, and M4-10 behavior without reopening unaffected atomic checkout work.

| Task | Work | Acceptance |
|---|---|---|
| M4-R00 | Reconcile requirements/spec/design/tasks | Signed change and layout rules are consistent |
| M4-R01 | Alter payment constraints | Cash below total and signed change persist exactly |
| M4-R02 | Simplify checkout service/form/HTTP | One inline POS submit; no round-off/reason/confirm |
| M4-R03 | Add default right-side catalogue | Active same-shop products visible/searchable/addable |
| M4-R04 | Rebuild desktop POS layout | Two-thirds order, one-third catalogue, checkout always reachable |
| M4-R05 | Highlight signed change in Orders | Positive/zero/negative values are visually distinct |
| M4-R06 | Replace affected tests and rerun verification | Focused and full PostgreSQL suites pass |
| M4-R07 | User frontend re-acceptance | User performs revised 1366x768/scanner/offline checklist |

### M4-R00 review record

**Result:** PASSED on 2026-08-06

- Reconciled the user's clarification with `docs/product/mvp-requirements.md`, `docs/product/roadmap.md`, project technical
  design, `docs/milestones/m4-checkout/feature-spec.md` v1.2, `docs/milestones/m4-checkout/technical-design.md` v1.2, current schema/code, and M4
  completion evidence.
- Resolved the financial meaning to one signed formula: `change = cash received - total`; no
  change-availability decision is stored.
- Confirmed total is the captured line subtotal, cash received is non-negative, and below-total cash
  is intentionally permitted.
- Preserved atomicity, numbering, snapshots, role/shop isolation, inventory locking, shortage audit,
  idempotency, cash-only payment, and future multi-terminal safety.
- Limited layout guarantee to 1366x768 at 100% zoom, with internal panel scrolling allowed and
  responsive fallback below the desktop target.
- Removed separate round-off reason/confirmation and separate checkout page from the active scope.

The revision is implementation-ready. M4 remains unapproved until M4-R07 passes.

### M4 revision implementation record

**Result:** M4-R01 through M4-R06 PASSED on 2026-08-06

- Removed tender-at-least-total and non-negative-change constraints via Sales migration `0003`.
- Replaced the round-off/reason/signing/confirmation flow with one inline cash checkout action.
- Implemented exact signed Change for above/equal/below-total cash and automatic shortage audit.
- Added the default right-third catalogue and compact desktop POS layout with internal scrolling.
- Added highlighted signed Change and non-zero Change filtering to completed Orders.
- Passed 18 focused tests, all 138 Sales tests, all 296 project tests, Ruff, 5 JavaScript tests,
  Django checks, migration drift check, and the local Tailwind production build.

M4-R07 remains user-owned. See `docs/milestones/m4-checkout/completion.md`; no frontend verification was performed by Codex.

## 11. Cart quantity-control revision

| Task | Work | Acceptance |
|---|---|---|
| M4-R08 | Reconcile quantity feedback in spec/design/tasks | Explicit always-visible step controls are consistent with M3/M4 mutation rules |
| M4-R09 | Implement immediate minus/plus forms | Each click persists one step; Update button is absent |
| M4-R10 | Automated regression verification | Template, Sales, lint, and Tailwind checks pass |
| M4-R11 | User frontend recheck | User verifies mouse/touch behavior and compact layout |

### M4-R08 review record

**Result:** PASSED on 2026-08-06

- Reuses the existing CSRF-protected, versioned, server-authoritative quantity service and enhanced
  fragment response; no new endpoint, model, migration, or speculative feature is introduced.
- Keeps removal explicit, so decrement at one is disabled instead of silently deleting a line.
- Keeps both controls visible at their boundaries and preserves the inactive-product rule by
  disabling only increase.
- Preserves JavaScript-disabled operation through ordinary POST forms and prevents rapid stale
  updates through the existing mutation button disabling/version checks.
- Adds targeted template coverage and retains user-owned hands-on frontend verification.

The refinement is consistent with the approved M4 scope and ready for implementation.

### M4-R09/M4-R10 implementation record

**Result:** PASSED on 2026-08-06

- Replaced the editable number field and Update button with explicit minus/current/plus controls.
- Each enabled step is an immediate CSRF-protected POST through the existing enhanced mutation flow.
- Minus remains visible but disabled at one; plus remains visible but disabled for inactive products
  and at the supported maximum; Remove remains separate.
- Passed 18 focused template/HTTP tests, all 139 Sales tests, all 297 project tests, Ruff, migration
  drift, Django checks, and the local Tailwind production build.

M4-R11 remains user-owned; no hands-on frontend verification was performed by Codex.

## 12. Non-blocking toast revision

| Task | Work | Acceptance |
|---|---|---|
| M4-R12 | Reconcile notification feedback in spec/design/tasks | Toast policy preserves message semantics and POS fit |
| M4-R13 | Implement fixed dismissible toast stack | Messages do not consume layout height; close/timeout behavior works |
| M4-R14 | Automated regression verification | Markup, JavaScript, Sales, lint, and Tailwind checks pass |
| M4-R15 | User frontend recheck | User verifies toast placement/dismissal and visible checkout footer |

### M4-R12 review record

**Result:** PASSED on 2026-08-06

- Fixes the reported checkout cut-off at the shared presentation boundary rather than adding a
  POS-only spacing workaround.
- Preserves Django message creation and one-request consumption; no business action, database,
  permission, URL, or transaction behavior changes.
- Auto-dismiss is limited to success/info. Warning/error remains available until explicit dismissal
  or navigation, preventing important failures from silently disappearing.
- Fixed positioning removes notification height from the 1366x768 POS calculation; bounded stacking
  prevents many messages from overflowing the viewport.
- Keeps all assets local and assigns hands-on toast/layout validation to the user.

The refinement is consistent with M4 accessibility, offline, and compact-layout requirements and is
ready for implementation.

### M4-R13/M4-R14 implementation record

**Result:** PASSED on 2026-08-06

- Replaced in-flow message banners with a fixed, bounded, top-right toast stack outside `<main>`.
- Added keyboard-accessible close buttons, success/info auto-dismiss, hover/focus timer pausing, and
  persistent warning/error behavior using local JavaScript.
- Added automated toast policy/markup coverage and passed 36 focused tests, all 298 project tests,
  JavaScript syntax, Ruff, migration drift, Django checks, and the local Tailwind production build.

M4-R15 remains user-owned; no hands-on toast or POS viewport verification was performed by Codex.
