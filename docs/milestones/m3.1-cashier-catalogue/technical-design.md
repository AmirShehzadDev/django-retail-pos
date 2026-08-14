# Milestone 3.1 Technical Design - Cashier Read-Only Catalogue

**Status:** Approved on 2026-08-04

**Version:** 1.0

**Prepared:** 2026-08-04

**Input:** Approved `docs/milestones/m3.1-cashier-catalogue/feature-spec.md`

## 1. Design goal

Extend the existing server-rendered catalogue list and detail GET workflows to active cashiers while
keeping every catalog/inventory mutation and sensitive manager-only field behind the existing
owner/admin boundary.

The implementation reuses current URLs, search form, pagination, and manager pages. It adds no
model, migration, service, API, JavaScript, or runtime dependency.

## 2. Current-code constraints

- `apps.catalog.policies._active_manager()` currently makes every catalogue policy manager-only.
- `product_list` and `product_detail` call `_require_catalog_manager()` before reading data.
- The product list contains manager-only Create product, Needs review filter, and review badge.
- The product detail template renders cost, creator/source, review state/action, timestamps,
  movements, movement actors/reasons, inventory links, and mutation controls.
- Catalog and inventory mutation services already re-lock and re-authorize the actor; these service
  boundaries must remain unchanged.
- Catalogue URLs and `never_cache` behavior already meet the required local server-rendered model.

## 3. Data model and migrations

No schema change is permitted or required.

The feature reads existing `Product` fields:

- `shop_id`, `name`, `barcode`, `sku`, `selling_price`, `stock_on_hand`, and `is_active` for the
  cashier response;
- existing manager-only fields remain available only through the manager response.

There is no new status, relationship, index, constraint, audit action, inventory movement, or data
migration. `makemigrations --check --dry-run` must report no changes.

## 4. Authorization design

### 4.1 Policy functions

Refine `apps/catalog/policies.py` into two explicit capabilities:

- `can_view_catalog(actor)`: authenticated, active owner/admin/cashier with a shop.
- `can_manage_catalog(actor)`: the existing owner/admin-only capability.

Update the same-shop product policies:

- `can_view_product(actor, product)` uses `can_view_catalog` and same-shop equality.
- `can_edit_product(actor, product)` and `can_change_product_stock(actor, product)` continue to
  require `can_manage_catalog` and same-shop equality.

Do not infer authorization from template variables. Policy checks remain the source of truth.

### 4.2 View guards

Add `_require_catalog_viewer(actor)` for list/detail GET views.

- `product_list` and `product_detail` use the viewer guard.
- `product_create`, `product_edit`, `product_status`, and `product_review` continue to use
  `_require_catalog_manager` before rendering or mutating.
- Inventory receipt, adjustment, scanner, and movement-history views remain unchanged and
  manager-only.
- `_visible_product_or_404` continues to filter by `actor.shop_id` before lookup, then applies
  `can_view_product`; missing and foreign identifiers therefore share the 404 boundary.

Anonymous users continue to follow `login_required`. An authenticated but unauthorized actor gets
403 for the list and mutation surfaces; a foreign/missing product detail gets 404.

## 5. Product-list query and context

Keep the current same-shop query, case-insensitive partial search, stable name/id ordering,
50-product pagination, and query-string preservation.

Compute once per request:

```text
is_catalog_manager = can_manage_catalog(request.user)
```

Search/filter handling:

- `q`, `status`, and `negative` are honored for all catalogue viewers.
- `needs_review` is honored only when `is_catalog_manager` is true.
- For a cashier, a crafted `needs_review=on` is ignored and normalized context sets
  `needs_review=False`.
- Remove `needs_review` from the cashier's preserved pagination query string so an ignored
  manager-only filter is not echoed in generated links.
- Unknown status values remain normalized by the existing form and cause no authorization or data
  expansion.

Pass `is_catalog_manager` explicitly to the template. Do not pass cost, creator, movement, or audit
data through cashier-specific context additions.

The list request is read-only and does not need `transaction.atomic` or row locks. Changes committed
by managers appear on the next request.

## 6. Product-detail query and response

After same-shop lookup, branch on `is_catalog_manager`:

### Manager response

- Continue rendering `catalog/product_detail.html` with current recent movements and management
  controls.
- Preserve cost, creator/source, review state/action, timestamps, inventory guidance/history, and
  owner/admin behavior.

### Cashier response

- Render a separate `catalog/product_detail_readonly.html` template.
- Pass only `product` and the minimal display context required by the base template.
- Do not query `product.movements` for a cashier.
- The template accesses only name, active state, selling price, stock, barcode, SKU, and shop-safe
  navigation.
- It renders the approved informational stock notice and inactive-product guidance.

A distinct cashier template is preferred over a large conditional inside the manager detail page:
it makes sensitive-field non-rendering auditable and reduces the chance that a future manager field
is accidentally exposed.

The detail request is read-only and creates no transaction, lock, audit event, or data mutation.

## 7. Template and navigation changes

### `templates/catalog/product_list.html`

- Render **Create product** only when `is_catalog_manager`.
- Render the Needs review filter and per-row Needs review badge only when
  `is_catalog_manager`.
- Keep approved list columns for all roles.
- For cashiers, render an informational notice that browsing/drafts do not reserve or change
  stock, authorized inventory operations may change it, and M4 checkout will deduct it.
- Preserve manager layout and actions.

### New `templates/catalog/product_detail_readonly.html`

- Extend `base.html` and keep the Products breadcrumb.
- Render only the six approved safe product values and the two approved guidance messages.
- Render no form and no link to create/edit/status/review/receive/adjust/movements.

### `templates/base.html`

- Show Products to every authenticated catalogue viewer.
- Keep Inventory, Users, and Shop settings under their existing role rules.

### `templates/core/home.html`

- Show a cashier-safe **Browse products** action linked to the product list.
- Keep owner/admin management actions unchanged.

No new JavaScript is needed. Tailwind classes use the existing local build; regenerate and commit
`static/css/app.css` only if the build output changes.

## 8. URL and HTTP contract

No URL changes:

- `GET /products/` - owner/admin management list or cashier read-only list.
- `GET /products/<id>/` - owner/admin full detail or cashier safe detail.

Existing mutation URLs retain their methods and manager-only guards. The feature adds no POST,
JSON, API, browser-storage, client-cache, or background request behavior.

All catalogue GET responses remain `never_cache`; CSRF behavior on existing mutation forms is
unchanged.

## 9. Sensitive-data boundary

For cashier list/detail responses, automated assertions must prove the absence of:

- cost-price labels and known cost values;
- creator username, creation source, timestamps, review state/badges/actions;
- movement types, balances, actors, reasons, and history URLs;
- create/edit/status/review/receipt/adjustment controls or URLs.

Hiding these elements is a response-data requirement, not merely a navigation preference.
Manager response assertions must prove the same information remains available to owner/admin.

## 10. Mutation and audit invariants

Before and after crafted cashier requests to every catalog/inventory mutation endpoint, tests take
snapshots of:

- product fields and row count;
- stock balances;
- inventory movement count/content; and
- relevant audit-event count/content.

Every request must be denied and snapshots must remain identical. Existing domain services remain
unchanged so direct service calls by a cashier continue to fail independently of the views.

Catalogue views themselves never record an audit event.

## 11. Test design

### Policy tests

- Active cashier can view the catalogue and same-shop product.
- Cashier cannot manage/edit/change stock.
- Foreign product, inactive user, anonymous user, and shop-less user remain denied as applicable.
- Owner/admin permissions remain unchanged.

### Catalog view tests

- Anonymous redirect, inactive denial, all active-role list/detail success.
- Same-shop query, leading-zero name/barcode/SKU search, status/negative filters, stable ordering,
  pagination, and preserved query string.
- Crafted cashier `needs_review` parameter is ignored and review data is absent.
- Cashier list contains exactly the safe columns/actions plus informational notice.
- Cashier detail contains approved fields/guidance and excludes every sensitive label, value, URL,
  form, movement, and manager action.
- Missing and cross-shop product IDs both return 404.
- Cashier GET/POST mutation matrix returns the designed denial and changes no product, movement, or
  audit state.
- Owner/admin list/detail/create/edit/status/review coverage continues to pass.

### Navigation and cross-app regression tests

- Cashier sees Products/POS but not Inventory/Users/Shop settings.
- Owner/admin navigation remains unchanged.
- Cashier remains denied from inventory scanner, receipt, adjustment, and movement pages.
- POS search/quick-create behavior and stock invariants remain unchanged.

### Required verification

- Focused catalogue/core/inventory tests.
- Full PostgreSQL regression suite.
- Django check and migration-drift check.
- Ruff lint/format, deterministic local Tailwind build, and `git diff --check`.
- Source/response scan for remote runtime assets and accidental M4 scope.

No concurrency test is required because the feature adds only ordinary read-only GET queries and no
new consistency guarantee. Existing catalog, inventory, and POS concurrency tests remain in the
full regression run.

## 12. Acceptance traceability

| Feature-spec area | Technical implementation | Automated evidence |
|---|---|---|
| All active roles view list/detail | Viewer policy and GET guards | Policy/view role matrix |
| Same-shop only | Shop-filtered lookup/query | Foreign/missing 404 tests |
| Search/filter/pagination | Existing form/query with role-aware review filter | Query and pagination tests |
| Safe cashier list | Conditional manager controls/review data | Response allow/deny assertions |
| Safe cashier detail | Separate read-only template; no movement query | Sensitive-data absence tests |
| Mutation denial | Existing manager guards and service policies | GET/POST snapshot matrix |
| Owner/admin compatibility | Manager branch unchanged | Existing and explicit regression tests |
| No data/audit effect | Read-only GET paths, no services/transactions | Before/after snapshots |
| Offline/local frontend | Existing local Tailwind/templates, no JS/CDN | Asset scan plus user check |

## 13. Explicit technical exclusions

- No product/inventory model, migration, service, audit, or URL changes.
- No client-side product cache, API, JavaScript filter, POS-cart integration, or stock reservation.
- No cashier access to cost, margins, review queues, movements, audit data, or mutations.
- No Milestone 4 checkout, payment, completion, history, or stock-deduction implementation.

## 14. Implementation gate

After this technical refinement is approved, create `docs/milestones/m3.1-cashier-catalogue/development-tasks.md`. Then perform the
mandatory independent review of the approved feature specification, this technical design, and the
development tasks against the whole project. Fix and rerun that review before implementation.
