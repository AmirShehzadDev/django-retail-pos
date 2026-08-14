# Milestone 4.3 Technical Design - Unified Products and Stock Workspace

**Status:** Planning reviewed; implementation-ready

**Version:** 1.1

**Prepared:** 2026-08-06

**Input:** Approved `docs/milestones/m4.3-products-stock/feature-spec.md` v1.1

## 1. Scope and architectural choice

Use the existing catalog product list as the canonical **Products & Stock** workspace. Preserve the
existing catalog and inventory domain services, fallback URLs, full-page templates, permissions,
and movement-history page. Add progressive enhancement around those routes rather than creating a
parallel product/inventory backend or a client-side state store.

There is no schema migration and no new runtime dependency. Django remains the source of rendered
form/results HTML; local JavaScript manages one native dialog, focused fragment refresh, and
toasts.

## 2. Models and invariants

No model field or database constraint changes.

- `Product.stock_on_hand` remains service-managed and cannot be submitted in a product form.
- `InventoryMovement` remains immutable and is the permanent explanation for stock changes.
- Identifier uniqueness, whole-number stock, decimal PKR, shop scope, active-product rules, and
  negative-balance behavior remain unchanged.
- Catalog-created products retain `creation_source=CATALOG`, `needs_review=False`, active status,
  and a zero balance at their initial save.
- Checkout quick-create remains a separate zero-stock, audited, needs-review flow.

## 3. Forms and composite creation service

### 3.1 Forms

- Keep `ProductForm` for editing.
- Add `ProductCreateForm`, extending the product fields with optional
  `quantity_received_now` (`IntegerField`, minimum 1 when present) and optional
  `receipt_note` (maximum 500 characters).
- Keep `StockReceiptForm`, `StockAdjustmentForm`, `ProductSearchForm`, and movement filters as
  existing server-authoritative validation layers.

### 3.2 `create_product_with_optional_receipt`

`create_product_with_optional_receipt(actor, product values, quantity_received_now=None,
receipt_note="") -> (Product, InventoryMovement | None)`

Within one outer `transaction.atomic()` block:

1. call the existing catalog creation service, which locks/revalidates the actor and creates the
   product at zero;
2. if no quantity is supplied, return the product and no movement;
3. if a quantity is supplied, call the existing `receive_stock` service for the new product; and
4. return the product and receipt movement after both succeed.

Nested atomic blocks are savepoints inside the outer transaction. Any receipt validation,
permission, integrity, or database failure rolls back the product and movement together. The
inventory service remains the only code that changes `stock_on_hand`.

## 4. Workspace query and scan lookup

Refactor product-list query construction into a reusable context/helper so full-page and fragment
responses apply identical shop scoping, role filtering, search, status, negative, needs-review,
ordering, pagination, and query-string preservation.

Add `catalog:product_lookup`, GET-only:

- validate and normalize the submitted `q` value;
- look for an exact same-shop barcode before general search;
- normal request: redirect an active manager match to Receive, a cashier/inactive match to safe
  Details, or an unmatched value to `product_list?q=...`;
- enhanced request: return a small JSON decision containing the safe modal URL for an exact match,
  or the filtered workspace URL for search results.

The unmatched workspace state may render an explicit manager link to create with the current
value as `barcode`; no GET or lookup mutates data.

## 5. Enhanced response protocol

Use one documented request header, `X-Product-Workspace`, with these values:

- `modal`: an existing detail/form/status endpoint returns JSON containing server-rendered
  `dialog_html` rather than a complete page;
- `results`: `product_list` returns only the product-results fragment; and
- `lookup`: `product_lookup` returns its JSON decision.

Mutation responses:

- HTTP 200 success: `{result: "ok", message: "..."}`;
- HTTP 422 form/domain validation: `{result: "invalid", dialog_html: "..."}`;
- authorization/scope/method/CSRF remain normal 403/404/405/CSRF responses and are never converted
  to apparent validation success.

After enhanced success, JavaScript closes the dialog and fetches the current workspace URL with
`results`, replacing only `[data-product-results]`. This second read ensures the affected row,
filters, result count, status, and pagination are all server authoritative. If the current filter
excludes the changed/created product, the success toast still accurately reports the mutation.

## 6. Views and URLs

### Catalog

- `product_list`: canonical full workspace plus results-fragment response.
- `product_lookup`: new GET-only exact-barcode/search decision endpoint.
- `product_create`: use `ProductCreateForm` and the composite creation service; modal GET/invalid/
  success plus full-page fallback.
- `product_detail`: modal manager or cashier detail partial plus existing full-page fallback.
- `product_edit`: modal form protocol plus fallback; stock is context-only.
- `product_status`: modal confirmation protocol plus fallback.
- `product_review`: enhanced success JSON or existing redirect fallback.

### Inventory

- `receive` and `adjust`: modal GET/invalid/success protocol plus existing full-page fallback.
- `scan`: retain as a compatible direct URL but redirect its landing GET to Products & Stock; a
  submitted barcode preserves its existing lookup semantics and lands in the appropriate fallback
  route.
- `movement_list`: unchanged manager-only paginated audit view, with navigation back to Products &
  Stock.

All views retain `never_cache`, login, HTTP method, shop-scope, and policy enforcement.

## 7. Templates

Split reusable, server-rendered partials:

- `catalog/_product_results.html`: table, empty state, manager actions, and pagination;
- `catalog/_product_form_dialog.html`: create/edit dialog body;
- `catalog/_product_detail_dialog.html`: role-safe details and manager actions/recent movements;
- `catalog/_product_status_dialog.html`: explicit status confirmation;
- `inventory/_receipt_dialog.html` and `_adjustment_dialog.html`: inventory forms and balance
  context.

The full workspace renders exactly one empty native `<dialog>` shell. Action links use delegated
`data-product-modal-url` hooks. Full-page fallback templates continue to render equivalent forms
and links, sharing smaller form-body partials where practical.

Manager product rows show Receive as the primary action for active products. Secondary actions are
compact and keyboard accessible. Cashier markup is generated without confidential fields or
manager URLs, not merely hidden by CSS.

The dialog has an accessible name, close/cancel controls, bounded viewport height, internal
scrolling, and no stacking. The product results remain independently usable when the dialog is
closed.

## 8. Local JavaScript

Add `static/js/products.js`, loaded only on the workspace and versioned locally.

- Intercept modal trigger links and fetch modal HTML.
- Submit dynamically loaded forms with CSRF-bearing `FormData` and double-submit protection.
- Replace dialog HTML on a 422 response without losing entered values.
- On success, close, refresh results, dispatch `app:toast`, and refocus/select the common input.
- Handle search/scan lookup decisions: open an exact-match modal or load filtered results and update
  browser history.
- Handle filter and pagination links/forms with progressive fragment enhancement where safe.
- Reinitialize projected-balance behavior in dynamically inserted Receive/Adjust dialogs.
- Keep native fallback navigation when fetch, response parsing, or enhancement initialization
  cannot run.

Expose small pure decision/quantity helpers for Node tests. Actual dialog layout, focus trap,
scanner behavior, and responsive interaction remain user verification.

## 9. Navigation and content updates

- Replace separate Products and Inventory navigation with the role-appropriate unified label.
- Merge the owner/admin home Products and Receive stock cards into one Products & Stock card.
- Update product/detail/receipt/adjustment/history breadcrumbs and copy to use Products & Stock.
- Update README and milestone records so product creation may optionally include a real receipt,
  while direct balance assignment remains prohibited.

## 10. Security, concurrency, and failure behavior

- Permission checks execute before rendering confidential modal HTML.
- Product IDs are always same-shop scoped; managers and cashiers receive different detail context.
- CSRF is mandatory for all enhanced and fallback mutations.
- Actor/product lock order remains compatible with current services; no new client value is trusted
  for stock, price, projected balance, role, or shop.
- Receive/adjust races serialize on product rows. Identifier races resolve through database
  constraints. Composite creation rolls back fully on receipt failure.
- JavaScript cancellation, lookup, list refresh failure, or dialog close has no data effect.
- A mutation success followed by a fragment-refresh failure shows a truthful success toast and a
  refresh-recommended state rather than resubmitting the mutation.

## 11. Automated tests

Cover:

- composite create with blank receipt, valid receipt, validation failure, forced receipt failure,
  permission, uniqueness, exact movement/balance, and rollback;
- manager/cashier workspace rendering and confidential-field/action exclusion;
- exact known/inactive/unknown lookup decisions, leading zeroes, shop scope, method boundaries, and
  no side effects;
- modal GET, invalid 422, successful enhanced JSON, fallback redirect, CSRF, permission, inactive
  product, and cross-shop behavior for create/edit/receive/adjust/status/review/details;
- results fragment parity with full-page search/filter/pagination;
- receipt/adjustment concurrency and regression of immutable ledger/audit behavior;
- navigation/home consolidation and full movement-history availability;
- JavaScript syntax and pure helper tests, template hook assertions, Tailwind build, Django checks,
  migration drift, Ruff, static collection, dependency integrity, and full project regression.

No automated test is described as proof of actual browser layout, focus, hardware scanning,
responsive behavior, or offline user experience.

## 12. Migration and deployment impact

- No schema/data migration.
- No new Python, Node, remote, or runtime dependency.
- Rebuild local Tailwind CSS and collect static assets.
- Version `products.js` and changed `app.js` only if the shared script is modified.
- Existing bookmarks/routes keep working through fallbacks.

## 13. Next workflow gate

Create `docs/milestones/m4.3-products-stock/development-tasks.md`, conduct the mandatory whole-project planning review, fix every
finding, and begin implementation only after the repeated review passes.
