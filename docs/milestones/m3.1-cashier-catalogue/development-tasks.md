# Milestone 3.1 Development Tasks - Cashier Read-Only Catalogue

**Status:** Complete; M3.1-00 through M3.1-06 passed

**Prepared:** 2026-08-04

**Inputs:** Approved `docs/milestones/m3.1-cashier-catalogue/feature-spec.md` and approved `docs/milestones/m3.1-cashier-catalogue/technical-design.md`

## 1. Objective and implementation gate

Implement a same-shop cashier-safe product list/detail experience without exposing manager data or
weakening any catalog/inventory mutation boundary.

Implementation may begin only after M3.1-00 reviews the feature specification, technical design,
and these tasks against the project and records a passing rerun.

## 2. Ordered task summary

| Task | Work | Dependency |
|---|---|---|
| M3.1-00 | Review/fix/rerun the whole planning package | Approved spec/design and drafted tasks |
| M3.1-01 | Split catalogue view and management policies | M3.1-00 |
| M3.1-02 | Add role-aware list/detail view behavior | M3.1-01 |
| M3.1-03 | Add cashier-safe templates and navigation | M3.1-02 |
| M3.1-04 | Complete policy, security, view, and regression tests | M3.1-01 through M3.1-03 |
| M3.1-05 | Run full verification and record completion evidence | M3.1-04 |
| M3.1-06 | User manual frontend acceptance | M3.1-05 |

## 3. Detailed tasks

### M3.1-00 - Mandatory planning-package review

Review `docs/milestones/m3.1-cashier-catalogue/feature-spec.md`, `docs/milestones/m3.1-cashier-catalogue/technical-design.md`, and this document against
`docs/product/mvp-requirements.md`, `docs/product/roadmap.md`, project technical design, M1-M3 behavior, current code, and
`AGENTS.md`.

Check permissions, same-shop disclosure, sensitive response fields, direct URL behavior, filter
crafting, data/audit invariants, owner/admin regressions, dependency ordering, test traceability,
frontend-verification ownership, and exclusion of M4 scope. Fix every finding in its source
document and repeat the review until clean. Record exact findings and rerun status in section 7.

**Acceptance:** Section 7 records `PASSED`; the three documents are mutually consistent and every
acceptance criterion maps to implementation and verification.

### M3.1-01 - Catalogue viewer policy

Files:

- `apps/catalog/policies.py`
- focused policy tests

Work:

- Add an active same-shop catalogue-viewer capability for owner/admin/cashier.
- Keep catalog management and stock-changing capabilities owner/admin-only.
- Make `can_view_product` use the viewer boundary while edit/stock policies retain manager rules.
- Cover anonymous, inactive, shop-less, foreign-shop, inactive-product, and all-role cases.

**Acceptance:** Cashier can view only same-shop products and cannot manage/edit/change stock;
existing manager behavior remains unchanged.

### M3.1-02 - Role-aware catalogue views

Files:

- `apps/catalog/views.py`
- focused view tests

Work:

- Add a viewer guard for list/detail GET requests.
- Preserve manager guards on create/edit/status/review and every inventory endpoint.
- Scope list/detail to `request.user.shop_id` before lookup.
- Honor `q`, status, and negative filters for cashiers; ignore `needs_review` for cashiers and
  remove it from generated pagination links.
- Pass explicit `is_catalog_manager` context.
- Query/render recent movements only for owner/admin detail.
- Select the separate cashier detail template without adding services, locks, transactions, or
  audit events.

**Acceptance:** Cashier list/detail GET succeeds with safe context; mutation URLs remain denied;
foreign/missing product details share 404; reads have no data/audit effect.

### M3.1-03 - Cashier-safe templates and navigation

Files:

- `templates/catalog/product_list.html`
- new `templates/catalog/product_detail_readonly.html`
- `templates/base.html`
- `templates/core/home.html`
- generated `static/css/app.css` only if deterministic build changes it

Work:

- Show Products navigation/home access to cashiers while retaining manager-only Inventory/Users/
  settings links.
- Conditionally hide Create product, Needs review filter, and review badges on the list.
- Add the approved informational stock notice for cashiers.
- Render only approved safe fields/guidance in the read-only detail template.
- Include no manager/mutation/history form or URL in cashier HTML.
- Use existing Tailwind/local assets and no new JavaScript.

**Acceptance:** Cashier HTML exposes only safe product information and read-only navigation;
owner/admin list/detail presentation and controls remain available.

### M3.1-04 - Security and regression coverage

Files:

- existing or new disjoint tests under `apps/catalog/tests/`
- navigation tests under `apps/core/tests/` where appropriate

Work:

- Add all-role list/detail and inactive/anonymous coverage.
- Test same-shop search by name, leading-zero barcode, and SKU; status/negative filters;
  pagination/query preservation; empty results; no identifier fallbacks.
- Test crafted `needs_review` is ignored and review/cost/creator/source/timestamp/movement data is
  absent from cashier responses, including known sentinel values.
- Exercise cashier GET/POST requests to catalog create/edit/status/review plus inventory scanner,
  receipt, adjustment, and movement endpoints.
- Snapshot products, stock, movements, and audit events around denial tests.
- Preserve owner/admin catalog/inventory and M3 POS regression coverage.

**Acceptance:** Every Feature Spec criterion has a named automated test or M3.1-06 manual check;
security assertions validate response absence as well as hidden navigation.

### M3.1-05 - Automated verification and evidence

Files:

- `README.md`
- `docs/product/roadmap.md`
- new `docs/milestones/m3.1-cashier-catalogue/completion.md`
- task/spec/design statuses

Run:

```powershell
docker compose up -d db
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test apps.catalog apps.core.tests.test_views apps.inventory.tests.test_views
.\.venv\Scripts\python.exe manage.py test
ruff check .
ruff format --check .
.\.venv\Scripts\python.exe -m pip check
npm ci
npm run css:build
.\.venv\Scripts\python.exe manage.py collectstatic --noinput
.\.venv\Scripts\python.exe manage.py reconcile_inventory
git diff --check
git status --short
```

Also verify the Tailwind build is deterministic, rendered cashier responses contain no remote
runtime assets/sensitive sentinel values, production settings retain `/admin/` 404, and the diff
contains no migration, mutation broadening, secret, local database, or M4 behavior.

**Acceptance:** All checks pass and exact evidence is recorded without claiming user frontend
acceptance.

### M3.1-06 - User manual frontend acceptance

Codex must not perform this step unless the user explicitly asks. Provide the user with setup,
actions, and expected results for:

1. Cashier Products navigation/home action.
2. Search/filter/pagination and leading-zero display.
3. Safe list/detail fields and informational stock/inactive guidance.
4. Absence/denial of cost, review, history, and mutation capabilities.
5. Owner/admin regression comparison.
6. Normal/narrow layout and internet-disconnected behavior.

**Acceptance:** User reports the manual result; only then mark M3.1 complete.

## 4. Acceptance traceability

| Feature criterion | Implementation tasks | Verification |
|---|---|---|
| Roles and authentication | M3.1-01, M3.1-02 | Policy/view role tests |
| Same-shop only | M3.1-01, M3.1-02 | Foreign/missing 404 tests |
| Search/filter/pagination | M3.1-02 | Query/pagination tests |
| Safe cashier list | M3.1-02, M3.1-03 | Response allow/deny tests; M3.1-06 |
| Hidden review/management data | M3.1-02, M3.1-03 | Sensitive-sentinel tests |
| Safe cashier detail | M3.1-02, M3.1-03 | Separate-template response tests; M3.1-06 |
| Mutation denial/no effects | M3.1-01, M3.1-02 | URL matrix and state snapshots |
| Owner/admin compatibility | M3.1-02, M3.1-03 | Existing/full regression suite |
| Local/offline behavior | M3.1-03 | Asset checks; M3.1-06 |

## 5. Explicit exclusions

- No schema/migration/service/audit/URL/API/JavaScript change.
- No cashier cost, margin, review, inventory-ledger, audit, or mutation access.
- No direct catalogue-to-draft add action or client-side cache.
- No stock reservation/deduction and no M4 payment/checkout/history behavior.

## 6. Completion rule

M3.1 is complete only when M3.1-00 through M3.1-05 pass with recorded evidence and the user
approves M3.1-06. Until then, MILESTONES must state the exact planning, implementation, automated,
or manual-pending status.

## 7. Mandatory planning-review record

**Status:** PASSED - IMPLEMENTATION GATE OPEN

**Review date:** 2026-08-04

**Method and sources:** A separate planning-review pass reread the approved feature specification,
approved technical refinement, and complete task plan against `docs/product/mvp-requirements.md`,
`docs/product/roadmap.md`, `docs/architecture/technical-design.md`, M1-M3 specifications/design/evidence, `AGENTS.md`, and the
current catalogue, inventory, accounts, core, and POS code/tests.

**Finding and correction:** The draft catalogue notice said that only checkout changes stock once
M4 exists, which contradicted the existing authorized inventory receipt/adjustment workflows. The
feature specification, technical design, and UI task now state precisely that browsing and active
drafts do not reserve/change stock, authorized inventory operations can change it, and completed
checkout will deduct it in M4. The review also made the crafted manager-only `needs_review` filter
handling complete: cashier requests ignore it and generated pagination links remove it.

**No-change checks:** The rerun found no cost/review/movement disclosure path, mutation
broadening, same-shop gap, schema/service/audit requirement, owner/admin regression, missing
acceptance mapping, unsafe task dependency, remote runtime dependency, or M4 payment/checkout/
history implementation. The separate cashier detail template and state-snapshot denial tests make
the sensitive-data and no-mutation boundaries directly verifiable.

**Rerun result:** PASSED. All 12 Feature Spec acceptance criteria map to an implementation task and
automated or user-owned verification. M3.1-01 may begin.
