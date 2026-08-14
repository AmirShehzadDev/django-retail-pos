# Milestone 3 - Development Tasks

**Status:** Complete; M3-00 through M3-18 passed

**Version:** 1.1

**Approved:** 2026-08-04
**Planning review passed:** 2026-08-04

**Inputs:** `docs/milestones/m3-active-orders/feature-spec.md` v1.1 and `docs/milestones/m3-active-orders/technical-design.md` v1.1

> **Historical task record:** These tasks accurately record the completed Milestone 3 build. The
> retained discard behavior they implemented is superseded by the approved
> [Milestone 4.2 specification](../m4.2-clear-orders/feature-spec.md); it is not the target for new work.

## 1. Objective and hard gate

Implement and verify the terminal-scoped active POS workspace: up to three persistent order tabs,
known-barcode scan, product search, atomic unknown-barcode quick-create, captured prices, quantity
and removal operations, explicit cross-cashier takeover, retained discard, and optimistic draft
versioning.

Do not implement cash tendering, change, signed round-off, checkout completion, permanent order
numbers, payments, stock reservation/deduction, negative-stock acknowledgement, completed-order
history, returns, voids, reports, or other Milestone 4+ behavior.

> **Implementation gate:** M3-00 was the mandatory separate Sol xhigh whole-package planning
> review. It found and fixed every recorded issue, repeated the review against version 1.1, and is
> recorded `PASSED` in section 8. M3-01 through M3-18 may now proceed only in the dependency order
> and file lanes below.

Version 1.0 was approved as the task-plan input to that gate. This reviewed version 1.1 incorporates
the gate's fixes. “Approved for continuous implementation” removes a later user-approval pause; it
does not weaken the recorded M3-00 result or the remaining implementation/verification gates.

## 2. Ordered task summary

| ID | Task | Depends on | Gate/parallel rule |
|---|---|---|---|
| M3-00 | Perform separate whole-package planning review and fix cycle | Completed M3 spec/design/tasks | Passed 2026-08-04 |
| M3-01 | Extend focused audit vocabulary and migration | M3-00 | Schema lane |
| M3-02 | Add Order/OrderItem schema, constraints, indexes, and migration | M3-01 | Schema lane; serial after audit migration |
| M3-03 | Add POS exceptions, policies, and configured-terminal resolver | M3-02 | Domain lane |
| M3-04 | Add scoped workspace and product-search query layer | M3-03 | Domain lane |
| M3-05 | Implement locked draft lifecycle and version-conflict foundation | M3-02, M3-03 | Domain service owner only |
| M3-06 | Implement captured-line, quantity, removal, and total services | M3-05 | Same domain service owner |
| M3-07 | Implement known/unknown scan and search-add services | M3-04, M3-06 | Same domain service owner |
| M3-08 | Implement signed unknown-scan context and atomic quick-create/add | M3-01, M3-06, M3-07 | Same domain service owner |
| M3-09 | Implement takeover, retained discard, and last-tab replacement | M3-01, M3-05, M3-06 | Same domain service owner |
| M3-10 | Add validated POS forms | M3-03, M3-06, M3-08, M3-09 | HTTP lane may begin after service contracts stabilize |
| M3-11 | Add POS views, URLs, conflicts, and progressive response contract | M3-04, M3-07 through M3-10 | HTTP lane |
| M3-12 | Build server-rendered POS templates, navigation, and Tailwind UI | M3-11 | UI lane |
| M3-13 | Add minimal local POS JavaScript and scanner queue behavior | M3-11, M3-12 | UI lane |
| M3-14 | Complete PostgreSQL transaction/version concurrency tests | M3-05 through M3-09 | Dedicated test lane; production code read-only |
| M3-15 | Complete web, permission, persistence, template, JavaScript, and regression tests | M3-10 through M3-14 | Test/integration lane |
| M3-16 | Update operator/project documentation and prepare completion evidence | M3-12, M3-13, M3-15 | Documentation lane |
| M3-17 | Run full automated and production-style verification | M3-01 through M3-16 | Integration owner only |
| M3-18 | Perform required manual acceptance and close milestone | M3-17 | User/manual gate |

M3-01 through M3-18 are ordered implementation tasks, not permission to start before M3-00. Each
task includes its direct tests; M3-14/M3-15 then close cross-cutting concurrency and end-to-end gaps.

## 3. Detailed tasks

### M3-00 - Mandatory independent planning-package review

#### Work

- Assign a separate `gpt-5.6-sol` reviewer at `xhigh` reasoning; the reviewer must not rely only on
  summaries from the planning author.
- Read `AGENTS.md`, `docs/product/mvp-requirements.md` v1.4, `docs/product/roadmap.md` v1.3,
  `docs/architecture/technical-design.md` v0.5, all approved M0-M2 planning/completion artifacts, the current M0-M2
  code, `docs/milestones/m3-active-orders/feature-spec.md` v1.0, `docs/milestones/m3-active-orders/technical-design.md` v1.0, and this document completely.
- Compare the three M3 planning documents together for contradictions, missing requirements,
  unjustified scope, unsafe assumptions, incomplete acceptance coverage, invalid Django/PostgreSQL
  mechanics, incompatible current-code conventions, and dependency/ownership problems.
- Check the M3 schema and transaction design specifically for conditional slot uniqueness,
  structural maximum-three enforcement, discarded-state checks, decimal capacity, same-shop rules,
  lock order, version-conflict semantics, line-total exactness, quick-create rollback, and absence of
  premature M4 financial/stock behavior.
- Check the web protocol for GET safety, CSRF POST startup, signed quick-create context, scoped 404,
  403/409/422/503 behavior, normal HTML fallback, server-trusted fragments, and scanner queue
  semantics.
- Check every Feature Spec acceptance criterion and Milestone 3 exit criterion has an explicit
  implementation task plus automated or required manual evidence.
- Fix every finding in the appropriate planning document using the normal edit workflow, then
  repeat the entire comparison until no material finding remains.
- Record reviewer identity/model, date, reviewed commit/worktree state, fixes made, rerun result,
  and final pass in section 8 of this document.

#### Acceptance

- There are no unresolved contradictory, missing, unsafe, out-of-scope, or untestable M3 decisions.
- `docs/milestones/m3-active-orders/feature-spec.md`, `docs/milestones/m3-active-orders/technical-design.md`, and this document agree with the approved project
  sources and current implementation.
- All review fixes are reflected in task dependencies, acceptance criteria, and file ownership.
- The final review result is explicitly `PASSED`; a partial review, verbal assurance, or unresolved
  “follow up during implementation” does not open the gate.

#### Verification

- Reread the corrected package after fixes rather than reviewing only its diff.
- Run `git diff --check` on the corrected planning changes.
- Confirm section 8 contains a completed, dated pass record.
- Stop without implementation if the result is anything other than `PASSED`.

### M3-01 - Focused audit vocabulary and migration

#### Ownership

- `apps/core/models.py`
- `apps/core/audit.py`
- the new M3 `apps/core/migrations/` file
- focused new M3 audit tests only

#### Work

- Add `PRODUCT_QUICK_CREATED`, `DRAFT_TAKEN_OVER`, and `DRAFT_DISCARDED` action choices.
- Add target type `ORDER`.
- Extend the central allow-list with quick-create → `PRODUCT` and takeover/discard → `ORDER`.
- Preserve every existing M1/M2 audit mapping and sensitive-key rejection rule.
- Create the choice-state migration with no audit-row data rewrite.
- Add focused mapping tests before services begin emitting the actions.

#### Acceptance

- Each new action accepts exactly its approved target type and rejects every other type.
- Existing account, shop, product-price, and inventory-adjustment events still validate unchanged.
- No password, token, cookie, session, CSRF, or raw form material becomes permitted.
- Migration applies/reverses on PostgreSQL without changing existing event contents.

#### Verification

- Run the focused `apps.core` audit tests, including all pre-M3 audit tests.
- Run migration forward/backward coverage on a disposable PostgreSQL test database.
- Run `python manage.py makemigrations --check --dry-run` after creating the reviewed migration.

### M3-02 - Order and OrderItem schema

#### Ownership

- `apps/sales/models.py`
- `apps/sales/migrations/0001_initial.py`
- `apps/sales/tests/test_models.py`
- migration tests dedicated to M3 sales schema

#### Work

- Implement the exact `Order` fields from Technical Design section 4.1: shop, terminal, slot,
  M3-only status, creator, current cashier, 38,2 subtotal, positive version, discard metadata, and
  timestamps.
- Give the three `accounts.User` foreign keys the reviewed distinct reverse names
  `created_orders`, `current_orders`, and `discarded_orders`; run Django system checks so no reverse
  accessor/query name can clash.
- Add slot 1-3, active terminal/slot uniqueness, non-negative subtotal, positive version, valid
  status, and complete draft/discard-state constraints using the exact three-branch truth table in
  Technical Design section 4.2, including the `DRAFT` pass-through and zero-priced non-empty case.
- Implement the exact `OrderItem` snapshot/product/quantity/money/timestamp fields.
- Add unique order/product, positive quantity, non-negative price/total, exact expression-backed
  line-total, non-empty name, and nullable-or-non-empty barcode constraints; inspect the generated
  PostgreSQL SQL for the multiplication expression.
- Add only the approved workspace/recovery indexes and relationship delete behavior.
- Make no operational Django-admin registration and expose no delete pathway.
- Make `sales.0001_initial` depend on the current account/catalog migrations and M3 core audit
  migration.
- Do not add order number, completing cashier, final/rounding/cash/payment fields, completion
  statuses, source movement fields, Payment, Return, or Void models.

#### Acceptance

- Only slots 1, 2, and 3 are valid.
- No terminal can persist two active drafts in one slot; three discarded rows may retain reused
  slots without blocking a new active draft.
- A fourth active draft is structurally impossible because all three valid unique slots are taken.
- Draft/discard metadata combinations match the exact state table, including reasonless empty close
  and reason-required non-empty discard.
- Direct database tests reject every partial/contradictory discard metadata combination that can be
  expressed within one order row.
- One product has at most one current line per order; all line arithmetic constraints are exact.
- Protected referenced product/user/shop/terminal records cannot be deleted through cascades.
- Introspection confirms no M4 model or field entered the schema.

#### Verification

- Run focused model/constraint tests against PostgreSQL, including direct database writes that
  bypass forms/services.
- Apply and reverse the sales migration on a disposable database, then apply it again.
- Run `python manage.py makemigrations --check --dry-run`.
- Inspect generated SQL/constraint state for the conditional unique and exact total expression.

### M3-03 - POS errors, policies, and terminal resolver

#### Ownership

- `apps/sales/exceptions.py`
- `apps/sales/policies.py`
- `apps/sales/terminals.py`
- `apps/sales/tests/test_policies.py`
- `apps/sales/tests/test_terminals.py`

#### Work

- Define the focused domain exceptions and their safe public attributes:
  `TerminalUnavailable`, `DraftLimitReached`, `DraftVersionConflict`,
  `DraftTakeoverRequired`, `BarcodeNowKnown`, and `QuickCreateContextInvalid`.
- Add the exact POS capability helpers from Technical Design section 6.2.
- Implement `resolve_pos_terminal(actor, for_update=False)` using only
  `settings.POS_TERMINAL_CODE`, whose approved/default value remains `TILL-1`; normalize the trusted
  setting with trim-and-uppercase to match bootstrap/`Terminal`, and reject blank/overlong values.
- Require authenticated/active owner, admin, or cashier, active actor shop, active same-shop
  terminal, and no client-selected terminal identity.
- Support a locked resolver for mutation transactions without starting its own transaction.
- Keep `is_staff`, `is_superuser`, normal catalog permission, URL possession, and template
  visibility out of POS authorization decisions.

#### Acceptance

- All three active roles can use POS; anonymous, inactive, missing-shop, and invalid-role actors
  cannot.
- Same-shop active terminal/drafts pass the intended view/edit/takeover/discard matrix.
- Cross-shop, wrong-terminal, discarded, and mismatched-current-cashier targets fail safely.
- Lowercase/space-padded configured code resolves the bootstrap-normalized terminal, while invalid,
  missing, or inactive configured codes raise `TerminalUnavailable`; the resolver never selects
  another row.
- No request value can select a shop or terminal.

#### Verification

- Run table-driven policy tests across all actor/draft/terminal combinations.
- Run terminal tests for valid, missing, inactive, foreign, and configured-code cases.
- Assert `for_update=True` is used only inside an atomic service test context.
- Rerun M1 account and M2 catalog permission tests to prove no role broadening.

### M3-04 - Workspace and product-search queries

#### Ownership

- `apps/sales/queries.py`
- `apps/sales/tests/test_queries.py`

#### Work

- Add the immutable/read-only `WorkspaceState` representation needed by views/templates.
- Implement `load_workspace(actor, terminal, selected_draft_id=None, query="")` with active
  same-shop/terminal draft loading, creator/current cashier eager loading, and
  stable line/product prefetch.
- Order tabs by slot, compute item counts without per-tab queries, and choose requested-valid,
  most-recently-updated, then lowest-slot fallback exactly as designed.
- Return `needs_initial_draft=True` when none exists without writing from the query or GET path.
- Implement `search_pos_products(actor, query, limit=20)` with trimmed active same-shop product
  search across name/barcode/SKU, case-insensitive where specified, ordered by lower name then ID,
  limited to 20.
- Return only checkout display data; do not expose catalog mutation or quick-create from search.

#### Acceptance

- Workspace loading never changes current cashier, version, audit, order, or item records.
- Foreign, wrong-terminal, and discarded drafts cannot become selected through a crafted ID.
- Tabs/lines remain deterministic and execute without N+1 user/product/item queries.
- Empty query yields no results; inactive/foreign products never appear; the 21st result is absent.
- Leading-zero barcode and barcode-less product search behave correctly.

#### Verification

- Run query result, ordering, selected fallback, scope, no-write, and bounded-query-count tests.
- Assert search behavior for partial name, partial barcode, partial case-insensitive SKU, no result,
  and result limit.

### M3-05 - Locked draft lifecycle and version foundation

#### Ownership

- `apps/sales/services.py` and its direct service tests
- One domain-service owner retains this file through M3-09

#### Work

- Add common service helpers for locking/revalidating actor, server-resolved terminal, draft, and
  expected positive version in the exact global lock order.
- Implement `start_workspace(actor)` as an idempotent POST service: return an existing active draft
  or create slot 1 when none exists.
- Implement `create_draft(actor)` with terminal-row locking and deterministic lowest-free slot.
- Translate all-three-slots and unexpected conditional-unique races into `DraftLimitReached` or a
  focused current-workspace conflict; never expose raw `IntegrityError`.
- Add the reusable material-change version increment/update-time helper.
- Raise `DraftVersionConflict` before writes/audits when expected and persisted versions differ.
- Derive shop, terminal, slot, creator, current cashier, subtotal, version, and status server-side.

#### Acceptance

- Initial start creates exactly one slot-1 draft at subtotal zero/version 1 and becomes idempotent.
- New order fills the lowest gap and never exceeds three, including crafted service calls.
- Creator/current cashier are the locked actor; no caller-supplied metadata is accepted.
- Every stale targeted service request changes no row and exposes current version safely.
- A successful material change increments version exactly once; read/no-op behavior does not.

#### Verification

- Run direct service tests for initial, repeated initial, slot gap, full terminal, inactive actor,
  inactive terminal/shop, cross-shop, and database-race translation.
- Patch failure points to prove the surrounding atomic transaction rolls back.
- Assert lock ordering through controlled query/transaction tests where practical.

### M3-06 - Captured line, quantity, removal, and total services

#### Ownership

- Continue exclusive ownership of `apps/sales/services.py`
- Add focused service/calculation tests without editing HTTP/UI files

#### Work

- Implement the internal locked product-add primitive and public `add_product` contract.
- On first add, capture current product name, nullable barcode, and selling price; create quantity 1.
- On repeated add, increment the single existing line and preserve all captured snapshots.
- Implement positive whole-number quantity replacement, including positive-bigint range checks.
- For quantity replacement, use the locked-parent discovery pattern from Technical Design section
  9.3, then lock product before item and recheck identity/current quantity; never acquire an item
  lock and then its product lock.
- Require an active product for first add or quantity increase; allow inactive-line reduction and
  removal.
- Treat same-quantity submission as an exact-version-validated no-op with no version increment.
- Implement explicit item removal only for the locked current draft.
- Recompute each changed line and order subtotal from server-held Decimal data after every mutation
  inside a local context with at least 50 significant digits and trapped `Inexact`/`Rounded`; never
  rely on the process-default 28-digit Decimal context.
- Validate 38,2 aggregate capacity and roll back on any overflow/constraint failure.
- Do not call inventory services, modify `stock_on_hand`, or create a movement/audit event.

#### Acceptance

- First/repeated add yields one line with exact captured price and correct quantity/line/subtotal.
- A later catalog price/name/barcode edit cannot silently rewrite an existing line.
- Remove then re-add creates a new line with then-current snapshots.
- Invalid quantities and stale/foreign/wrong-cashier/discarded targets create no partial change.
- Removing the last line leaves an active zero-total draft.
- Every path leaves every product stock balance and InventoryMovement count unchanged.
- Valid near-capacity arithmetic is exact even when the process-default Decimal context is lowered
  in a test; a true 38,2 overflow fails without a partial item/order write.

#### Verification

- Run Decimal tests including zero price, large valid bigint quantity, maximum representable total,
  an intentionally low process-default context, and rejected overflow.
- Assert lock acquisition remains actor → terminal → draft → product → item for quantity increases,
  reductions, and no-ops.
- Run snapshot, repeated-add, no-op, invalid-quantity, inactive-product, removal, and rollback tests.
- Snapshot product stock/movement rows before and after every service case and assert equality.

### M3-07 - Barcode scan and search-add services

#### Ownership

- Continue exclusive ownership of `apps/sales/services.py`
- Add scan/add service tests in a dedicated file if useful

#### Work

- Implement edge-trim-only barcode normalization with 1-64 validation and leading-zero retention.
- Implement `scan_barcode`: exact same-shop lookup including inactive products, known-active add,
  inactive-known focused rejection, and write-free `UNKNOWN` outcome.
- Ensure unknown scan does not increment version or create a product, line, audit, or movement.
- Route search selection through the same locked `add_product` behavior so price/state is reloaded
  at successful add time.
- Keep overlapping mutation safety entirely on version checks; do not merge or auto-replay stale
  scans.

#### Acceptance

- Each known scan adds exactly one; repeated committed scans retain one line and captured price.
- `0012345` survives normalization, lookup, snapshot, display state, and repeated scan unchanged.
- An inactive known barcode never becomes quick-create eligible.
- Unknown/blank/overlong/foreign/stale scans have the exact approved no-partial-effect behavior.
- Search-add cannot add inactive/foreign/stale products or trust the rendered result price.

#### Verification

- Run service tests for known/repeated/unknown/inactive/blank/overlong/leading-zero scans.
- Change/deactivate a search result between read and add and assert successful fresh-price capture or
  safe rejection.
- Assert version, item, product, audit, stock, and movement deltas for every outcome.

### M3-08 - Signed quick-create context and atomic quick-create/add

#### Ownership

- `apps/sales/signing.py`
- continued exclusive changes to `apps/sales/services.py`
- signing and quick-create service tests

#### Work

- Implement a dedicated versioned Django signing salt and 15-minute context containing actor, shop,
  terminal, draft, normalized barcode, expected version, and a non-reversible `salted_hmac`
  fingerprint of the current Django session key. Never put the raw session key in the token.
- Verify signature, age, constant-time current-session fingerprint, current actor, shop, terminal,
  draft, and version; expose barcode only as decoded fixed context, never editable trusted input.
- Implement `quick_create_and_add` using the documented actor-terminal-draft locks and one atomic
  product/audit/line/subtotal/version transaction.
- Derive active zero-stock `POS_QUICK_CREATE`, `needs_review=True`, null SKU/cost, creator, and shop.
- Validate trimmed name and non-negative Product 12,2 price; zero is valid.
- Recheck all products, including inactive, for exact barcode immediately before create.
- Translate simultaneous unique conflicts from a nested savepoint into `BarcodeNowKnown` with the
  winning product's active state.
- Write the exact focused `PRODUCT_QUICK_CREATED` payload using decimal strings.
- Offer no automatic add or overwrite when the barcode became known.

#### Acceptance

- Valid context creates exactly one product, one audit event, one line, one subtotal/version update,
  and no inventory movement.
- Form/service callers cannot set barcode, SKU, cost, stock, source, review, active, creator, shop,
  terminal, snapshot price, or totals outside the approved derivation.
- Cancel, tamper, expiry, logout/session flush, same-user relogin, other-session reuse, actor change,
  stale version, inactive-known barcode, unique race, validation failure, audit failure, line
  failure, and order failure leave no orphan product/event.
- Successful context replay is stale and cannot create/add twice.
- Existing M2 Needs review filtering immediately finds the successful product.

#### Verification

- Run signing tests with frozen/controlled time for valid, expired, altered, wrong-actor, wrong-shop,
  wrong-terminal, wrong-draft, stale, session-flush, same-user-new-session, and copied-token cases.
- Patch each write boundary to prove complete rollback.
- Run PostgreSQL duplicate-barcode race coverage later in M3-14 and the full M2 review-filter test.

### M3-09 - Takeover, discard, and last-tab replacement

#### Ownership

- Continue exclusive ownership of `apps/sales/services.py`
- takeover/discard service and audit tests

#### Work

- Implement explicit exact-version takeover for another current cashier only.
- Preserve creator, lines, snapshots, quantities, and subtotal; update current cashier and version
  exactly once; write the focused before/after `DRAFT_TAKEN_OVER` event atomically.
- Treat view/select/refresh and already-current takeover as non-events.
- Implement discard using actor-terminal-order-item locks and determine emptiness from item count,
  not subtotal.
- Require trimmed 1-500 reason for non-empty; store blank reason/empty flag for empty close.
- Recalculate retained subtotal, set status/actor/time/reason/empty flag/version, and append exact
  `DRAFT_DISCARDED` audit atomically.
- While terminal remains locked, create fresh slot-1 order only when no active draft remains.
- Expose no discarded restore/edit/delete path and never reuse a discarded primary key.

#### Acceptance

- Another user sees but cannot edit until one successful takeover; creator never changes.
- Takeover preserves order contents/totals and writes exactly one accurate audit event.
- Non-empty discard requires authority, current version, confirmation at HTTP layer, and reason;
  empty close needs no reason.
- Discarded order/items remain queryable internally and immutable through every M3 service.
- Slot frees for reuse; last discard plus replacement is one atomic success.
- Any audit/replacement failure leaves the original draft active and unchanged.
- No path changes stock, movement, payment, or order-number data.

#### Verification

- Run takeover matrix/no-view-event/audit/stale/rollback tests.
- Run empty, zero-price-non-empty, reason validation, retained snapshot, slot reuse, last replacement,
  and rollback tests.
- Assert every M3 mutation service rejects `DISCARDED` aggregates.

### M3-10 - POS forms

#### Ownership

- `apps/sales/forms.py`
- `apps/sales/tests/test_forms.py`

#### Work

- Add the exact start/new, scan, search, search-add, quick-create, quantity, versioned action, and
  discard forms from Technical Design section 11.1.
- Reuse literal Tailwind class strings and accessible widget attributes.
- Normalize barcode/search/name/reason only as approved and reject invalid bigint/version/money.
- Display signed-context barcode as fixed text outside editable fields.
- Keep the session key/fingerprint out of form fields; the view supplies the current session key
  directly to the signing verifier.
- Make discard reason dynamically required only when the freshly scoped draft is non-empty; keep
  service validation authoritative.
- Never accept trusted shop, terminal, slot, actor, status, source, review, stock, snapshots,
  subtotal, line total, or version increment.

#### Acceptance

- Valid forms produce only the exact service arguments.
- Crafted extra fields cannot change derived metadata.
- Quantity rejects bool-like, exponent, decimal, zero/negative, blank, malformed, and out-of-range
  input.
- Quick-create accepts only signed context, valid name, and valid zero-or-positive 12,2 price.
- Non-empty/empty discard forms match the approved reason rules without weakening service checks.

#### Verification

- Run a table-driven form validation suite covering every Feature Spec section 13 rule.
- Inspect rendered form field names to prove forbidden fields are absent.

### M3-11 - POS views, URLs, and response protocol

#### Ownership

- `apps/sales/views.py`
- `apps/sales/urls.py`
- `config/urls.py`
- `apps/sales/tests/test_views.py` for endpoint contracts

#### Work

- Mount the approved `/pos/` URL set exactly; add no M4/history route.
- Implement read-only no-store workspace GET with optional scoped `draft` and search `q`.
- Implement POST-only idempotent start and new-draft endpoints.
- Implement scan POST with known mutation or signed unknown quick-create redirect.
- Implement search-add, quantity, removal, quick-create, takeover, and discard endpoints using only
  service APIs.
- Keep takeover/discard GET confirmation-only and repeat fresh checks on POST.
- Apply login/POS role/active shop/terminal/same-shop/CSRF/scoped-404 rules to every endpoint.
- Map validation, version, takeover, tab-limit, barcode-now-known, terminal, and unexpected failures
  to the exact normal/enhanced response behavior.
- Use POST-redirect-GET/messages for normal HTML and the documented server-rendered fragments for
  enhanced success/409/422 responses.
- Reload current scoped state after conflict; do not return client-derived values or replay input.
- Encode every bigint ID/version in enhanced JSON as a base-10 string, and require the browser to
  treat it as opaque text rather than a JavaScript number.
- On enhanced unknown scan, return the signed next URL as a workflow-boundary outcome; later queued
  scans must be cleared before navigation rather than mutating the draft behind quick-create.

#### Acceptance

- GET workspace/search/confirmation writes nothing and creates no audit event.
- Every mutation rejects GET and CSRF-free POST.
- Initial workspace creation occurs only through protected POST, never GET.
- Unknown scan refresh does not resubmit; quick-create token stays session/actor/draft/version
  bound.
- Foreign IDs are indistinguishable from nonexistent; role denial is 403; missing terminal is safe
  503; stale state is 409 for enhanced requests.
- Normal and enhanced paths produce the same persisted state and trusted values.
- Enhanced response IDs/versions remain exact above JavaScript's safe-integer limit, and unknown
  scan cannot leave a background queue that invalidates its signed context.
- No URL exposes checkout, cash, payment, stock mutation, completed/discarded history, return, void,
  or report behavior.

#### Verification

- Run method/permission/CSRF/status/redirect/message/fragment tests for every URL and role.
- Test direct crafted IDs/fields, token edge cases, response loss/retry, and refresh behavior.
- Assert query/view code never writes Product stock or InventoryMovement.

### M3-12 - Server-rendered POS interface and Tailwind

#### Ownership

- `templates/sales/**`
- coordinated edits to `templates/base.html` and `templates/core/home.html`
- `assets/css/input.css` only if an approved reusable style is necessary
- `static/css/app.css` regenerated by the integration owner after UI merge

#### Work

- Add POS navigation/action access for all roles while retaining owner/admin-only management links.
- Build workspace, tab, draft panel, line, search, quick-create, takeover, discard, and terminal-error
  templates with the approved server context/fragment boundaries.
- Render slot labels, item counts, creator/current handler, captured identity/price, quantity,
  line total, subtotal-as-Total, and PKR formatting.
- Render foreign-handler drafts read-only until Resume; show inactive retained lines with only
  reduction/removal.
- Render stock only as optional informational search context; never as reservation/checkout warning.
- Add CSRF-protected auto-start form plus visible no-JavaScript Start Order fallback.
- Add large scanner/touch targets, labels, field errors, keyboard focus, selected-tab semantics,
  live-region messaging, and text-plus-color status communication.
- Exclude cash/change/round-off/checkout/order-number/history controls and all remote assets.
- Compile Tailwind only after template source is stable.

#### Acceptance

- Owner/admin/cashier see POS; only owner/admin retain catalog/inventory/user/settings navigation.
- Three slots, empty state, non-empty state, handoff state, inactive-line state, search results, and
  confirmations are understandable with JavaScript disabled.
- Keyboard-only operation and narrow/desktop layouts retain visible focus and usable controls.
- No M4 label/control or external URL appears in rendered POS HTML.
- Tailwind output contains required literal classes and is deterministic.

#### Verification

- Run template/navigation/accessibility-oriented Django assertions for every state/role.
- Run `npm ci` then `npm run css:build` twice; the second build must create no diff.
- Search rendered POS pages for external `http://`/`https://` asset URLs and forbidden M4 controls.

### M3-13 - Minimal local JavaScript and scanner sequencing

#### Ownership

- `static/js/pos.js`
- any no-dependency Node test file dedicated to POS JavaScript
- coordinated script include in POS templates only

#### Work

- Add focus behavior that respects active search/quantity/quick-create/confirmation controls.
- Auto-submit the protected initial-start form once; preserve visible fallback on failure/no JS.
- Intercept only approved POS mutation forms and send CSRF-protected local requests.
- Serialize rapid scanner barcodes FIFO, injecting the last server-returned version immediately
  before each request as an opaque decimal string.
- Replace only server-rendered tab/draft fragments and update selected-draft URL state.
- On 409, validation, terminal, or network failure, stop/clear the queue, render/announce the safe
  error/current state, and require deliberate retry.
- When a scan returns an unknown quick-create next URL, stop/clear later queued scans before
  navigating; require those physical items to be rescanned after quick-create/cancel.
- Never calculate trusted price/total/stock, increment a version locally, auto-takeover, replay a
  failed mutation, coerce bigint IDs/versions through `Number`, store a cart/token locally, or load
  remote code.
- Keep normal server forms fully functional without JavaScript.

#### Acceptance

- Three rapid same-client scans acknowledged in order produce three service requests with successive
  returned versions and no lost scan.
- External concurrent mutation causes the next queued stale scan to stop with current server state;
  remaining entries are not replayed.
- An unknown barcode behind or ahead of rapid scans opens exactly one quick-create flow and clears
  all unprocessed scan values; no later request invalidates its token automatically.
- Response/network loss cannot duplicate a committed mutation through automatic retry.
- Scanner focus returns only after settled safe actions and never steals another active input.
- Script is local, syntax-valid, framework-free, and contains no client total/price authority.

#### Verification

- Run `node --check static/js/pos.js`.
- Use Node's built-in test runner or an equally dependency-free harness for pure queue/version state
  logic if factored for testing; add no JavaScript package solely for this task.
- Run Django response-fragment contract tests and the manual real-scanner scenario in M3-18.

### M3-14 - PostgreSQL concurrency and rollback suite

#### Ownership

- `apps/sales/tests/test_concurrency.py`
- Production files are read-only for this lane; send defects to their owning agent/integration owner

#### Work

- Use `TransactionTestCase`, separate connections, barriers, `ThreadPoolExecutor`, and explicit
  connection cleanup following the proven M2 inventory pattern.
- Test concurrent initial/new draft allocation and full three-slot boundary.
- Test same-version scan/quantity/remove requests: exactly one wins and the other reports current
  version without silent overwrite.
- Test sequential queue-version scan behavior separately from truly concurrent stale requests.
- Test simultaneous takeovers and exact one-event winner.
- Test discard racing scan/quantity and retained immutability of the winning final state.
- Test simultaneous unknown quick-create for one barcode with one product/audit/line winner and one
  `BarcodeNowKnown` loser.
- Test price edit racing first add captures one fully committed old-or-new price.
- Assert zero stock/movement effect in every case.

#### Acceptance

- No race creates a fourth/duplicate slot, duplicate product barcode, duplicate line, false audit,
  partial quick-created product, mutable discarded order, lost acknowledged update, or unhandled
  database error.
- Every loser gets a defined domain conflict and can reload the winning state.
- Deadlock/time-out failures are absent under repeated test runs.
- Product stock and movement ledger remain byte-for-value/equivalent unchanged.

#### Verification

- Run the concurrency module repeatedly against PostgreSQL with fresh connections.
- Record final rows, versions, audit counts, and exception type for every race assertion.
- Run the existing concurrent inventory receipt test afterward to detect lock-order regression.

### M3-15 - Web, persistence, security, asset, and regression test completion

#### Ownership

- New disjoint files under `apps/sales/tests/` for integration/persistence/templates
- shared production fixes remain with their lane owner or integration owner

#### Work

- Close any model/audit/policy/query/service/form/view coverage gap against all 22 Feature Spec
  acceptance criteria and six Milestone 3 exit criteria.
- Test anonymous/inactive/owner/admin/cashier and cross-shop behavior for every URL.
- Test GET safety, POST-only/CSRF enforcement, PRG, enhanced 409/422 fragments, safe 503, and no
  production traceback.
- Test signed token expiry/tamper/replay/handoff and forbidden-form-field injection end to end.
- Test session-bound token invalidation across logout/flush, same-user relogin, and a second browser
  session; assert no raw session key appears in token payload, form HTML, response, audit, or logs.
- Test three distinct drafts through refresh, new client/session, logout/cashier login, connection
  close, and application-state reload.
- Test takeover/read-only/discard UI and exact underlying audit/retained data.
- Test quick-created product visibility in the existing Needs review filter.
- Test role-aware navigation, PKR/line/total display, local assets, accessibility labels/live region,
  and absence of M4 controls/URLs/models.
- Test enhanced response IDs/versions above `Number.MAX_SAFE_INTEGER` as opaque decimal strings and
  the unknown-scan queue-boundary contract.
- Run all M0-M2 suites, reconciliation, Django production-admin boundary tests, and static asset
  smoke assertions.

#### Acceptance

- Every Feature Spec acceptance criterion has a named passing test or M3-18 required manual check.
- All terminal tabs and business records survive the approved persistence boundaries.
- Permission/template hiding cannot be bypassed by direct URL/form requests.
- No test relies on SQLite for constraints, locking, or concurrency.
- Existing 145-test M0-M2 baseline remains green before counting new M3 tests.

#### Verification

- Produce an acceptance traceability list from test name to Feature Spec criterion 1-22.
- Run focused sales suite, existing M0-M2 suites, then the entire PostgreSQL suite.
- Run `python manage.py reconcile_inventory` and assert no M3-created movement/discrepancy.

### M3-16 - Documentation and completion-evidence preparation

#### Ownership

- `README.md`
- `docs/product/roadmap.md`
- new `docs/milestones/m3-active-orders/completion.md`
- planning documents only for review-approved corrections/status records

#### Work

- Update README with POS URL/navigation, server-configured terminal/default `TILL-1`,
  scanner-as-keyboard behavior, three-tab persistence/handoff, quick-create review state, discard
  behavior, and explicit “drafts do not change/reserve stock” note.
- Keep README clear that payment/checkout/order history do not exist until M4.
- Add exact Windows PowerShell commands for focused/full tests, JavaScript check, Tailwind build,
  collectstatic, and production smoke where useful.
- Add M3 planning-document links to MILESTONES only after M3-00 records the package as reviewed.
- Create `docs/milestones/m3-active-orders/completion.md` as an evidence structure; do not claim results before they run.
- Include setup/actions/expected outcomes for required manual scanner, persistence, handoff, price
  capture, quick-create, discard, offline, and role checks.

#### Acceptance

- Commands are copyable for the existing Windows/Docker/venv/npm environment.
- Documentation never suggests client/local-storage carts, direct order/stock edits, arbitrary
  cashier product creation, or M4 capabilities.
- MILESTONES status remains non-complete until M3-18 passes.
- Completion evidence distinguishes planned, automated-passed, required-manual-passed, deferred,
  and blocked states accurately.

#### Verification

- Run documentation link/path checks and `git diff --check`.
- Have integration owner compare every documented command with the command actually executed.

### M3-17 - Full automated and production-style verification

#### Ownership

- Integration owner; no parallel writes while this verification/fix cycle runs

#### Work

- Start and confirm the pinned PostgreSQL container is healthy.
- Apply migrations from the current database state and verify migration drift is absent.
- Run Django development checks, focused sales tests, full PostgreSQL regression suite, Ruff lint,
  Ruff format check, Python dependency check, JavaScript syntax/tests, Tailwind build, collectstatic,
  and inventory reconciliation.
- Rebuild Tailwind twice and confirm committed generated CSS is deterministic.
- Exercise production settings/Waitress for health, login, local CSS/JavaScript, authenticated POS
  workspace, scan/search mutation smoke, safe terminal failure, and production `/admin/` 404.
- Verify rendered pages request no runtime internet asset and repeat proportional POS smoke with
  internet unavailable when practical.
- Review complete diff for secrets, local databases/backups, untracked generated files, accidental
  M4 schema/UI, unrelated user changes, and unsafe migration operations.
- Fill `docs/milestones/m3-active-orders/completion.md` only with exact observed command versions/counts/results.

#### Required command set

```powershell
docker compose up -d db
docker compose ps
python manage.py migrate
python manage.py makemigrations --check --dry-run
python manage.py check
python manage.py test apps.sales
python manage.py test
ruff check .
ruff format --check .
python -m pip check
npm ci
node --check static/js/app.js
node --check static/js/pos.js
npm run css:build
python manage.py collectstatic --noinput
python manage.py reconcile_inventory
git diff --check
git status --short
```

Run any dependency-free POS JavaScript test command added by M3-13 and the existing documented
production/Waitress check as additional required evidence.

#### Acceptance

- Every command passes, or an exact expected localhost-only deployment warning is recorded and
  reconciled with the existing security posture.
- Full regression count includes all existing M0-M2 tests plus M3 tests; no baseline test is skipped.
- Migrations work on PostgreSQL, compiled assets are local/deterministic, reconciliation is clean,
  and production smoke uses no CDN/network dependency.
- Diff contains only intended M3/planning/documentation changes and no M4 behavior.

#### Verification

- Repeat any failed command after its root cause is fixed; record only the final pass plus material
  issue/fix history.
- Do not proceed to M3-18 while an automated, migration, security, scope, or production smoke check
  remains unresolved.

### M3-18 - Required manual acceptance and milestone closure

#### Ownership

- Integration owner prepares/runs setup and records results; user performs or confirms the physical
  scanner and real offline/browser workflow checks

#### Work and expected results

1. **Initial POS:** With `POS_TERMINAL_CODE=TILL-1`, log in as cashier, open POS, and confirm
   `TILL-1`, one ready `Order 1`, focused barcode input, PKR display, and no
   cash/checkout/history controls.
2. **Real scanner:** Scan one known barcode three times with a physical USB scanner. Expect one
   line at quantity 3, exact totals, and scanner focus restored.
3. **Search/quantity/removal:** Add a barcode-less product through search, set a valid quantity,
   reject `0` and `1.5`, then remove it. Expect correct totals and no stock/movement change.
4. **Three-tab persistence:** Populate three distinct tabs, reject a fourth, refresh, close/reopen
   browser, and restart Django. Expect every tab/item/price/quantity/total to remain separate/exact.
5. **Quick-create:** Cancel one unknown leading-zero scan, repeat and quick-create it. Expect exact
   barcode, immediate line, active zero-stock POS source, Needs review visibility, one audit event,
   and no movement.
6. **Captured price:** Add a product, edit catalog price in another authorized session, rescan in
   original draft, then remove/re-add. Expect repeated add to retain old captured price and re-add
   to capture new price.
7. **Handoff:** Leave a non-empty draft as Cashier A, log out, log in as Cashier B, view read-only,
   explicitly resume, then edit. Expect unchanged items/totals, retained creator, new current
   cashier, and one takeover event.
8. **Discard:** Try non-empty discard without reason, cancel, then confirm with reason. Close an
   extra empty tab. Expect retained/audited discard data, no stock change, and fresh `Order 1` when
   the final tab is removed.
9. **Offline:** Disconnect internet while keeping local services running; repeat scan, search, tab
   switch, quantity edit, handoff, and browser restart. Expect complete local styling/behavior and
   no remote request failures.

- If physical scanner hardware is unavailable, keyboard-plus-Enter may be recorded only as a
  development check; M3 remains manually incomplete until the real-scanner result is passed or the
  user explicitly defers it to the pilot with that release risk recorded.
- Record actor/setup, date, action, expected result, actual result, and pass/fail for each scenario
  in `docs/milestones/m3-active-orders/completion.md`.
- Mark M3 complete in MILESTONES only after M3-17 and all required M3-18 checks pass.

#### Acceptance

- All nine required scenarios pass or any user-authorized deferral is explicit, scoped, and does
  not conceal a release blocker.
- Automated evidence and manual observations agree on order, audit, product-review, and inventory
  effects.
- The user is told exactly which manual verification passed, remains required, or was deferred.
- `docs/milestones/m3-active-orders/completion.md` and MILESTONES contain no premature or ambiguous completion claim.

#### Verification

- Review the completed evidence against Feature Spec section 17 and Milestone 3 exit criteria.
- Run final `git diff --check`, inspect `git status --short`, and confirm no unrelated user work is
  included before any commit is proposed.

## 4. Acceptance traceability

| Approved behavior | Primary implementation tasks | Closure evidence |
|---|---|---|
| Roles, active shop, configured/default `TILL-1`, no client terminal switch | M3-03, M3-11, M3-12 | M3-15, M3-17, M3-18.1 |
| Stable slots, maximum three, persistence | M3-02, M3-05, M3-11 | M3-14, M3-15, M3-18.4 |
| Known/repeated scan and leading zeroes | M3-06, M3-07, M3-11, M3-13 | M3-15, M3-18.2 |
| Search and barcode-less product add | M3-04, M3-06, M3-11 | M3-15, M3-18.3 |
| Restricted atomic quick-create and Needs review | M3-01, M3-08, M3-10, M3-11 | M3-14, M3-15, M3-18.5 |
| Captured price, quantity, removal, totals | M3-02, M3-06, M3-10 | M3-15, M3-18.3/6 |
| No stock reservation/change or movement | M3-06 through M3-09 | M3-14, M3-15, M3-18.3/5/8 |
| Explicit takeover and focused audit | M3-01, M3-03, M3-09, M3-11 | M3-14, M3-15, M3-18.7 |
| Retained reasoned discard and empty close | M3-02, M3-09 through M3-12 | M3-14, M3-15, M3-18.8 |
| Version conflicts and concurrent safety | M3-05 through M3-09, M3-11, M3-13 | M3-14, M3-15 |
| Refresh/logout/browser/app restart survival | M3-02, M3-04, M3-11 | M3-15, M3-18.4/7 |
| Offline/local accessible interface | M3-12, M3-13 | M3-15, M3-17, M3-18.9 |
| No M4 checkout/history scope | All tasks, especially M3-02/M3-11/M3-12 | M3-15, M3-17 |

Feature Spec acceptance criteria 1-22 must each appear by number in the final automated/manual
evidence map; this grouped table is the planning summary, not a substitute for that final map.

## 5. Parallel-safe Sol-high implementation ownership

No implementation agent may start until M3-00 passes. Afterward, the integration owner may delegate
only along these file boundaries.

| Lane | Recommended tasks | Exclusive writable files | Must treat as read-only |
|---|---|---|---|
| Schema/audit | M3-01, M3-02 | `apps/core/models.py`, `apps/core/audit.py`, new core migration; `apps/sales/models.py`, sales migration, focused model/audit tests | services, views, templates, generated CSS |
| Domain | M3-03 through M3-09 | `apps/sales/exceptions.py`, `policies.py`, `terminals.py`, `queries.py`, `signing.py`, `services.py`, direct domain tests | migrations after handoff, HTTP/UI/docs |
| HTTP | M3-10, M3-11 | `apps/sales/forms.py`, `views.py`, `urls.py`, `config/urls.py`, form/view tests | domain services, models/migrations, templates/assets |
| UI | M3-12, M3-13 | `templates/sales/**`, coordinated `base.html`/`core/home.html`, `static/js/pos.js`, UI/JS tests, approved CSS input | models/services/views/migrations/docs |
| Concurrency | M3-14 | `apps/sales/tests/test_concurrency.py` only | all production files; report defects instead of patching them |
| Integration tests | M3-15 | new disjoint sales test modules assigned in advance | production files unless explicitly handed back by owner |
| Docs/evidence | M3-16, M3-18 records | `README.md`, `docs/product/roadmap.md`, `docs/milestones/m3-active-orders/completion.md` | application/migration/test code |
| Integration owner | M3-17 and merges | migration graph, `package.json` scripts if needed, generated `static/css/app.css`, cross-lane fixes after coordination | preserve unrelated user changes |

Coordination rules:

1. One Sol-high domain agent owns `apps/sales/services.py` continuously from M3-05 through M3-09;
   those tasks must not be split among concurrent writers.
2. Schema/migration contracts are frozen and handed off before domain/web agents depend on them.
3. Service signatures/exceptions/return state are frozen and communicated before HTTP/UI work.
4. View context names, fragment IDs, form data attributes, and response JSON keys are frozen before
   UI/JavaScript work proceeds in parallel.
5. Test agents use distinct filenames and report production defects to the owning lane; they do not
   opportunistically edit shared production files.
6. Only the integration owner regenerates/accepts `static/css/app.css`, resolves migration
   dependencies, and runs final repository-wide formatting/verification.
7. No agent edits `docs/milestones/m3-active-orders/feature-spec.md`, `docs/milestones/m3-active-orders/technical-design.md`, or this document during
   implementation unless a material mismatch is escalated and planning is deliberately reopened.
8. Agents inspect `git status` before edits and preserve all unrelated/user-owned changes.

Safe parallel waves after M3-00:

- **Wave A:** M3-01 then M3-02 are serial schema foundations.
- **Wave B:** M3-03/M3-04/domain preparation; schema/audit tests may be extended independently in
  their owned files.
- **Wave C:** M3-05 through M3-09 stay serial in the domain lane; test-only agents may add disjoint
  black-box cases after each contract stabilizes.
- **Wave D:** M3-10/M3-11 HTTP work; after context/response freeze, M3-12/M3-13 UI work and M3-14
  concurrency tests may run in parallel with disjoint ownership.
- **Wave E:** M3-15 integration tests and M3-16 documentation may run in parallel; M3-17 then runs
  alone on the integrated tree.
- **Wave F:** M3-18 requires the verified integrated application and user/hardware participation.

## 6. Explicit exclusions

- Cash received, change due, payment, cash drawer, receipt printing, or sale completion.
- Signed round-off, adjusted total, shortage warning/acknowledgement, stock lock/deduction, or
  `SALE` movement.
- Permanent order/document numbers, completed-order summary/list/search/detail, or discarded-order
  history UI.
- Returns, refunds, voids, reversal movements, daily summary, report, or public audit-history UI.
- Normal cashier catalog/inventory management, arbitrary product creation, price override,
  discount, tax, weighted quantity, customer/loyalty, or credit behavior.
- Product reservation, customer/draft name/note/copy, cross-terminal transfer, shifts, terminal
  picker/configuration/enrollment, multi-shop UI, or offline synchronization.
- REST/GraphQL/DRF, SPA framework, WebSocket, service worker, scanner SDK, remote asset, CDN,
  telemetry, new JavaScript testing dependency, or speculative generic event/idempotency system.
- Deployment/backup packaging beyond proportional production/offline smoke; full packaging remains
  Milestone 7.

## 7. Approval and completion rules

The user authorized the Milestone 3 workflow to proceed without intermediate approval pauses and
approved `docs/milestones/m3-active-orders/feature-spec.md` v1.0, `docs/milestones/m3-active-orders/technical-design.md` v1.0, and this task plan v1.0 as the
inputs to M3-00. The separate whole-project/package Sol xhigh review corrected the affected
behavior, schema, service, response, test, and dependency contracts and passed the rereview on
2026-08-04. Version 1.1 is therefore **planning reviewed and implementation-ready**.

Milestone 3 is complete only when:

- M3-00 is recorded passed;
- M3-01 through M3-17 pass with exact automated/production evidence;
- M3-18 required manual results are passed or explicitly user-deferred with risk recorded;
- all Feature Spec acceptance criteria and MILESTONES exit criteria have evidence;
- no M4+ behavior entered the code; and
- the user is told exactly which scanner/offline/manual checks passed or remain outstanding.

## 8. Mandatory planning-review record

**Status:** PASSED — IMPLEMENTATION GATE OPEN

**Reviewer:** Independent Codex task `/root/m3_plan_review`, `gpt-5.6-sol`, `xhigh` reasoning

**Review date:** 2026-08-04

**Reviewed state:** `main` at `7d850cf`; the v1.0 task plan was an untracked planning input at
review start. The reviewer made no application-code or migration changes and no commit.

**Scope read completely:** `AGENTS.md`; `docs/product/mvp-requirements.md` v1.4; `docs/product/roadmap.md` v1.3;
`docs/architecture/technical-design.md` v0.5; M0-M2 task/specification/design/completion artifacts; all three M3 v1.0
documents; and the relevant current models, policies, services, forms, views, URLs, settings,
bootstrap configuration, migrations, tests, templates, and local JavaScript.

**Findings and fixes:**

1. The three planned `Order` foreign keys to `accounts.User` had no distinct reverse names, which
   would fail Django system checks. Technical Design 4.1 and M3-02 now require
   `created_orders`, `current_orders`, and `discarded_orders` plus direct system-check coverage.
2. Valid 12,2-price × positive-bigint calculations can exceed Python Decimal's default 28-digit
   precision even though the planned aggregate fields are 38,2. Technical Design 9.3 and M3-06 now
   require a local precision of at least 50 with `Inexact`/`Rounded` traps and near-capacity tests.
3. Quantity replacement needed an item lookup to discover its product but did not say how to avoid
   item-before-product locking. Technical Design 9.3 and M3-06 now define locked-parent discovery,
   then product lock, item lock, and identity/quantity recheck.
4. The feature used literal `TILL-1` language while M0 already supports trusted server-side
   `POS_TERMINAL_CODE`, and bootstrap uppercases it. All M3 documents now use the configured code
   (default `TILL-1`) and require trim/uppercase normalization plus invalid-code failure tests.
5. The signed quick-create context promised logout invalidation but contained no session binding.
   Feature Spec 9/13, Technical Design 10/11/15, and M3-08/M3-10/M3-15 now require a non-reversible
   `salted_hmac` session fingerprint, constant-time comparison, no raw session key in the token, and
   logout/same-user-relogin/second-session tests.
6. Enhanced JSON did not specify safe transport for positive-bigint versions and BigAutoField IDs;
   JavaScript numeric coercion could lose precision. Technical Design 11/12/15 and
   M3-11/M3-13/M3-15 now require base-10 strings and forbid `Number` coercion.
7. A FIFO scanner queue did not define what happens when an unknown scan opens quick-create; later
   queued scans could mutate the draft and invalidate the token invisibly. Feature Spec 7,
   Technical Design 12/13/15, and M3-11/M3-13/M3-15 now make unknown scan a queue-clearing workflow
   boundary with deliberate rescan.
8. Discard constraints and exact line-total mechanics were described semantically but not precisely
   enough for direct-database verification. Technical Design 4.2/4.3 and M3-02 now provide the
   complete three-branch discard truth table, explicit draft pass-through, zero-priced non-empty
   case, expression-backed exact-total requirement, SQL inspection, and invalid-state tests.

**No-change checks:** The review found no missing approved M3 feature, no M4+ payment/checkout/stock/
history/return/report scope, no inventory mutation or reservation path, no role broadening, no new
runtime/network dependency, and no remaining task dependency or writable-file-lane conflict. All
22 Feature Spec criteria and all six Milestone 3 exit criteria retain implementation plus
automated/manual closure coverage. The existing M0-M2 audit allow-list, product rules, stock-ledger
boundary, bootstrap terminal setting, URL structure, PostgreSQL-only concurrency convention, and
local Tailwind/JavaScript posture remain preserved.

**Rerun result:** PASSED. The corrected v1.1 feature specification, technical design, and task plan
were reread together against every source above. They are mutually consistent and
implementation-ready. `git diff --check` and final link/status checks are recorded in the review
handoff; M3-01 may begin, but no M4+ work is authorized.

## 9. Implementation and verification record

**Recorded:** 2026-08-04

- M3-01 through M3-16 are implemented and independently reviewed.
- M3-17 passed: 122 focused sales tests and 269 full PostgreSQL tests passed, with migration,
  lint, format, dependency, JavaScript, deterministic Tailwind, static collection, reconciliation,
  and automated production HTTP checks also passing.
- PostgreSQL concurrency verification passed 12/12, three repeated module runs (36/36), five
  repeated catalog-price/add races, and ten repeated discard/edit races.
- Implementation review found and fixed joined-row lock amplification that could deadlock a price
  edit against first add, and a stale enhanced New order control that could block the third tab.
  Both fixes have regression coverage; the final independent review found no unresolved runtime
  or scope issue.
- M3-18 was approved by the user on 2026-08-04. Manual frontend verification remains user-owned
  under `AGENTS.md`; the retained regression steps are in `docs/milestones/m3-active-orders/completion.md`.
