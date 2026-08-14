# Milestone 4.3 Development Tasks - Unified Products and Stock Workspace

**Status:** Complete; user frontend acceptance confirmed on 2026-08-06

**Version:** 1.1

**Prepared:** 2026-08-06

**Inputs:** Approved `docs/milestones/m4.3-products-stock/feature-spec.md` v1.1 and `docs/milestones/m4.3-products-stock/technical-design.md` v1.1

## 1. Objective and implementation gate

Consolidate the manager's routine product and inventory workflow into one progressively enhanced
Products & Stock workspace while retaining cashier read-only safety, immutable movements,
transactional stock rules, and full-page fallbacks.

> **Implementation gate:** M4.3-00 must review the complete planning package against the approved
> project and current code. Correct every finding and repeat the review before M4.3-01 begins.

## 2. Ordered task summary

| ID | Task | Depends on | Verification focus |
|---|---|---|---|
| M4.3-00 | Mandatory whole-project planning review | Spec/design/tasks | Scope, consistency, feasibility, acceptance coverage |
| M4.3-01 | Add optional atomic product receipt | M4.3-00 | Validation, real movement, rollback, no direct stock write |
| M4.3-02 | Refactor workspace query and add lookup/fragment protocol | M4.3-00 | Role/shop scope, exact barcode priority, fragment parity |
| M4.3-03 | Add modal-aware catalog and inventory endpoints | M4.3-01, M4.3-02 | Enhanced/fallback responses, forms, CSRF, permissions |
| M4.3-04 | Build unified workspace and reusable dialog partials | M4.3-02, M4.3-03 | One-screen actions, cashier safety, accessible markup |
| M4.3-05 | Add local progressive-enhancement JavaScript | M4.3-04 | Dialog lifecycle, validation, refresh, toast, focus hooks |
| M4.3-06 | Consolidate navigation/copy and preserve audit fallback | M4.3-04 | Fewer destinations, compatible direct routes/history |
| M4.3-07 | Add backend, template, concurrency, and JS coverage | M4.3-01 through M4.3-06 | Acceptance and regression evidence |
| M4.3-08 | Run full verification and record completion | M4.3-07 | All gates, docs, user checklist, commit |

## 3. Detailed tasks

### M4.3-00 - Mandatory whole-project planning review

- Reconcile the M4.3 spec/design/tasks with `docs/product/mvp-requirements.md`, `docs/product/roadmap.md`,
  `docs/architecture/technical-design.md`, completed M2/M3.1/M4.2 behavior, README, and current code/tests.
- Check role/confidentiality boundaries, exact scan/search semantics, atomic initial receipt,
  inventory lock/service reuse, fallback behavior, response protocol, error handling, and
  exclusions.
- Map every acceptance criterion to implementation and automated or user-owned verification.
- Fix all findings in the appropriate document and repeat the review.
- Record the repeated-review result in section 6.

**Complete when:** no contradiction, unsafe assumption, missing dependency, scope growth, or
uncovered acceptance criterion remains.

### M4.3-01 - Add optional atomic product receipt

- Add `ProductCreateForm` with optional positive whole-number Quantity received now and optional
  receipt note, preserving all `ProductForm` validation.
- Add `create_product_with_optional_receipt` with one outer transaction around existing catalog
  creation and `receive_stock`.
- Return product plus optional movement; produce success copy that truthfully states zero stock or
  receipt quantity/resulting stock.
- Keep editing on `ProductForm`; never expose `stock_on_hand` as a submitted model field.
- Add service/form tests for blank, valid, invalid, duplicate, unauthorized, and forced receipt
  failure/rollback cases.

**Complete when:** optional opening quantity always produces exactly one reconciling receipt or no
product/movement at all.

### M4.3-02 - Refactor workspace query and add lookup/fragment protocol

- Extract one role-aware, same-shop product list context/query builder.
- Add GET-only product lookup with exact barcode priority and enhanced JSON decisions.
- Preserve leading zeroes and route inactive/manager/cashier matches safely.
- Return a product-results partial for the `results` request header using the same filters,
  pagination, and query preservation as the full page.
- Render an explicit manager create-with-prefilled-barcode choice for unmatched search; never
  mutate on GET.
- Test search/filter/pagination parity, shop isolation, role behavior, lookup decisions, invalid
  input, method boundaries, and no side effects.

**Complete when:** full and fragment results agree and scan/search never exposes or mutates another
shop's data.

### M4.3-03 - Add modal-aware catalog and inventory endpoints

- Add shared request/JSON helpers for `modal`, `results`, and `lookup` without masking normal HTTP
  authorization/method/CSRF behavior.
- Update create, edit, details, status, and review catalog views for modal/fallback operation.
- Update receive and adjust inventory views for modal GET, 422 invalid, success JSON, and fallback
  redirect.
- Keep server-side validation and domain services authoritative; refresh locked state on rejected
  stock mutations where needed.
- Preserve safe cashier detail fields and reject all cashier mutation/modal requests.
- Test every route's successful, invalid, permission, cross-shop, inactive, CSRF, method, and
  fallback behavior.

**Complete when:** each enhanced route works without navigation and every direct URL remains a
secure usable fallback.

### M4.3-04 - Build unified workspace and reusable dialog partials

- Rework the product list into Products & Stock with prominent common input, compact filters,
  manager Add product, role-specific actions, and one dialog shell.
- Split results/table/pagination into a reusable fragment.
- Add create/edit, receive, adjust, details, and status dialog partials with accessible headings,
  close/cancel actions, validation regions, and correct current/projected balance context.
- Put Receive first for active manager products; keep inactive stock mutations unavailable.
- Include recent manager movements and link to full history; omit confidential manager material
  entirely for cashier output.
- Use one dialog at a time and bounded internal scrolling; retain complete full-page fallbacks.
- Add template tests for role/action matrices, fields, exact form targets, hooks, and fallback
  equivalence.

**Complete when:** all routine manager actions originate from one workspace and cashier HTML
contains no manager-only data or endpoints.

### M4.3-05 - Add local progressive-enhancement JavaScript

- Add versioned `products.js` and delegated modal-trigger handling.
- Fetch/replace dialog HTML; close/cancel safely; submit dynamic forms with CSRF and disable repeat
  submissions.
- Preserve invalid values on 422; on success close, refresh results, show dismissible toast, and
  restore/select the common input.
- Enhance lookup, filters, and pagination without removing their normal fallback semantics.
- Reinitialize projected-balance/negative-warning behavior in dynamic stock forms.
- Treat a post-success results-refresh failure as committed success requiring a page refresh; do
  not automatically repeat the mutation.
- Add pure helper Node tests, syntax checks, and server-rendered hook assertions. Do not perform or
  claim hands-on browser verification.

**Complete when:** automated JavaScript checks pass and the user can manually verify the real DOM,
focus, scanner, and responsive behavior from the completion checklist.

### M4.3-06 - Consolidate navigation/copy and preserve audit fallback

- Replace separate Products/Inventory navigation with role-appropriate Products & Stock/Products.
- Merge home Products and Receive stock actions into one card.
- Update breadcrumbs and guidance across fallback pages and movement history.
- Keep legacy inventory scan direct URLs compatible and full movement history reachable from the
  workspace.
- Update README/Milestones and mark the user's completed M4.2 frontend acceptance.
- Confirm POS, order history, checkout quick-create, returns, and other unrelated navigation remain
  unchanged.

**Complete when:** routine UI presents one product/stock destination and existing bookmarks do not
lose their secure fallback path.

### M4.3-07 - Add backend, template, concurrency, and JavaScript coverage

- Complete service/form/view/integration/template tests mapped to all feature acceptance criteria.
- Prove exact receipt/adjustment movement and audit effects, product-plus-receipt rollback, and no
  side effects from reads/cancellation/invalid submissions.
- Cover concurrent receipts/adjustments and identifier races using PostgreSQL-capable tests.
- Prove cashier confidential-field and mutation denial, cross-shop nondisclosure, and manager
  regression.
- Test fragment/result protocol, navigation consolidation, direct fallbacks, movement-history
  access, local script syntax, and pure helpers.
- Run focused catalog/inventory suites during implementation.

**Complete when:** focused automated coverage passes without claiming manual frontend behavior.

### M4.3-08 - Run full verification and record completion

- Run Django checks, migration drift, focused catalog/inventory tests, concurrency tests, and the
  complete project suite against Dockerized PostgreSQL.
- Run Ruff lint/format, Node syntax/tests, Tailwind build, dependency checks, static collection,
  `git diff --check`, and final scope/diff review.
- Create `docs/milestones/m4.3-products-stock/completion.md` with delivered behavior, exact automated evidence, exclusions, and a
  concise required user frontend checklist.
- Update planning/task status and project docs truthfully.
- Commit with the configured Amir Shahzad identity and a short message.

**Complete when:** all automated gates pass, completion evidence exists, the commit is clean, and
the user receives the required final manual checklist.

## 4. Acceptance traceability

| Feature acceptance | Implementation tasks | Verification owner |
|---|---|---|
| One manager workspace for routine actions | M4.3-02 through M4.3-06 | Automated + user |
| Cashier safe read-only workspace | M4.3-02 through M4.3-04, M4.3-07 | Automated + user |
| Exact known/unknown scan behavior | M4.3-02, M4.3-05, M4.3-07 | Automated + user scanner check |
| Optional atomic product receipt | M4.3-01, M4.3-03, M4.3-07 | Automated |
| Ledger/audit/negative/concurrency guarantees | M4.3-01, M4.3-03, M4.3-07 | Automated |
| Product edit never directly changes stock/history | M4.3-01, M4.3-03, M4.3-07 | Automated |
| Enhanced in-place success/error behavior | M4.3-03 through M4.3-05 | Automated hooks + user |
| Direct/no-JS fallback and full movement history | M4.3-03, M4.3-04, M4.3-06, M4.3-07 | Automated + user |
| Consolidated navigation/home | M4.3-06, M4.3-07 | Automated + user |
| Actual visual/focus/scanner/responsive/offline behavior | M4.3-08 checklist | User only |

## 5. Explicit non-tasks

- No model/migration work or direct stock field editing.
- No bulk catalog tools, suppliers, purchasing, locations, stock counts, expiry/batches, images,
  categories, weighted goods, tax, or receipt printing.
- No changes to checkout quick-create, orders, cash payment, returns, voids, or reporting.
- No cashier cost/review/history/mutation access.
- No new frontend framework, DOM-test dependency, remote asset, or manual frontend verification by
  Codex.

## 6. Mandatory planning review record

**Review date:** 2026-08-06

**Status:** PASSED after corrections

The first whole-project review found and corrected four issues:

1. An earlier concept treated every unmatched general search as a barcode create candidate without
   making creation explicit. The specification/design/tasks now require a clearly labelled choice
   and prohibit automatic product creation from lookup.
2. The optional opening quantity could have been interpreted as direct `stock_on_hand` assignment.
   All documents now require zero-balance creation followed by exactly one genuine receipt inside
   one outer transaction, including rollback coverage.
3. The initial response design did not specify what happens when a mutation commits but the later
   results refresh fails. The design/tasks now prohibit automatic resubmission and require a
   truthful committed-success/refresh state.
4. The consolidation risked removing the full movement ledger and no-JavaScript routes. The
   documents now explicitly retain the manager audit page and all secure direct-link fallbacks
   while removing only duplicate routine navigation.

The repeated review reconciled `docs/milestones/m4.3-products-stock/feature-spec.md` v1.1,
`docs/milestones/m4.3-products-stock/technical-design.md` v1.1, and this document with `docs/product/mvp-requirements.md`, `docs/product/roadmap.md`,
`docs/architecture/technical-design.md`, completed M2/M3.1/M4.2 behavior, the current catalog/inventory services,
views, forms, templates, policies, tests, PostgreSQL transaction rules, and the local dependency
set. Permissions, confidentiality, lock/service reuse, progressive fallback, acceptance mapping,
scope, and task order are implementation-ready with no unresolved finding. M4.3-01 may proceed.
