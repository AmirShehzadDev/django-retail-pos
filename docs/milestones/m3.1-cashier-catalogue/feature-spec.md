# Milestone 3.1 Feature Specification - Cashier Read-Only Catalogue

**Status:** Approved on 2026-08-04

**Version:** 1.0

**Prepared:** 2026-08-04

## 1. Objective

Allow an active cashier to search and inspect same-shop product information needed at checkout
without granting any catalog-management, price-management, inventory, review, or audit access.

This is a small post-Milestone 3 enhancement. It satisfies the approved MVP requirement that a
cashier can search products and view information needed at checkout while preserving the rule that
a cashier cannot otherwise manage products, prices, or stock.

## 2. Actors and permissions

### Owner and admin

- Keep their existing product list, detail, create, edit, activate/deactivate, review, receipt, and
  stock-adjustment permissions unchanged.
- Continue to see cost price, creation/review information, inventory history, and management
  controls where currently allowed.

### Cashier

- Can open the same-shop product list and safe product detail page read-only.
- Can search and filter the permitted product information.
- Cannot create or edit a product, change its status or price, mark it reviewed, receive or adjust
  stock, or view inventory movement history.
- Cannot access another shop's product by changing a URL or request parameter.

### Anonymous, inactive, or shop-less user

- Cannot access the catalogue.

## 3. Cashier navigation

- Show a **Products** navigation link and home-page action to an active cashier.
- The link opens `/products/`.
- Do not show inventory, product-creation, edit, review, activation, receipt, adjustment, or
  movement-history navigation/actions to a cashier.
- Existing owner/admin navigation remains unchanged.

## 4. Read-only product list

The cashier list is shop-scoped, sorted by product name then identifier, and paginated at 50 rows.
It shows only:

- product name;
- barcode or an explicit `No barcode` value;
- SKU when present;
- selling price in PKR;
- current stock quantity;
- active/inactive status; and
- a read-only **View** link.

The page includes a clear notice that stock is informational; browsing and active drafts do not
reserve or change it. Authorized inventory operations may change stock, and completed checkout
will deduct stock when Milestone 4 is implemented.

### Search and filters

- Search by partial product name, barcode, or SKU using the existing case-insensitive behavior.
- Preserve barcode text and leading zeroes.
- Allow active/inactive status filtering.
- Allow the negative-stock filter because it directly explains checkout availability.
- Do not expose the Needs review filter or Needs review badges to cashiers; that is an owner/admin
  review workflow.
- Preserve valid search/filter parameters across pagination.
- Invalid or unknown filter values safely fall back to the unfiltered permitted list.

Owner/admin list behavior, including the Needs review filter and badge, remains unchanged.

## 5. Cashier-safe product detail

The cashier detail page shows only:

- product name;
- active/inactive status;
- selling price in PKR;
- current stock quantity, including a visible negative value;
- barcode or `No barcode`; and
- SKU or `No SKU`.

It also displays:

- `Stock is informational and may change before checkout.`
- For an inactive product: `This product cannot be added to a new order.`

The cashier detail page must not render or disclose:

- cost price;
- creator or creation source;
- Needs review state or review action;
- created/updated metadata;
- inventory movement rows, actors, balances, or reasons;
- inventory-history links;
- create, edit, activate/deactivate, receipt, adjustment, or review controls.

Owner/admin detail behavior remains unchanged.

## 6. Security and URL behavior

- Authorization is enforced in server-side policies and views, not only through hidden buttons.
- Cashiers may use GET only for the product list and same-shop detail pages.
- Every existing catalog or inventory mutation endpoint remains denied to cashiers for both GET and
  POST as applicable.
- A missing or cross-shop product detail returns the same not-found boundary without revealing
  whether the product exists.
- Crafted query parameters cannot reveal cost price, review state, movement data, or products from
  another shop.
- Pages retain the existing no-store/authentication behavior and local/offline asset posture.

## 7. Data and audit effects

- No model or database migration is required.
- Viewing, searching, filtering, and paginating create no audit event.
- No product, price, stock value, inventory movement, draft, or order is created or changed.
- Current stock is read directly as informational data; it is not reserved or recalculated by this
  feature.

## 8. Edge cases

- Inactive products remain visible when the cashier selects inactive/all status so a failed scan or
  customer query can be explained, but they are clearly labelled unavailable for a new order.
- Negative stock remains visible and is never converted to zero.
- Products without barcode or SKU display explicit fallback text without a broken link.
- Empty search returns the permitted shop list; a search with no matches shows a clear empty state.
- Deactivation, price changes, or stock changes performed by an authorized manager appear on the
  next cashier request; no stale client-side catalogue is maintained.

## 9. Acceptance criteria

1. Active owner, admin, and cashier users can open `/products/`; anonymous and inactive users
   cannot.
2. A cashier sees only products belonging to their shop.
3. A cashier can search by name, barcode (including leading zeroes), and SKU and paginate results.
4. A cashier can filter by active/inactive status and negative stock.
5. The cashier list shows name, identifiers, selling price, stock, status, and View only.
6. The cashier list hides Needs review information and every management/inventory action.
7. The cashier detail shows only the approved safe fields and informational guidance.
8. Cost price, creator/source, review state, timestamps, movements, movement actors/reasons, and
   management links are absent from cashier responses.
9. Direct cashier requests to create, edit, status, review, receipt, adjustment, and movement
   endpoints remain denied without data or audit changes.
10. Missing and cross-shop detail identifiers return the same not-found response.
11. Owner/admin catalog and inventory behavior has no regression.
12. The feature works with local assets while the computer has no internet connection.

## 10. Explicit exclusions

- Editing any product field or price as a cashier.
- Cashier access to cost/margin information, inventory ledger, Needs review workflow, or audit log.
- Adding a catalogue product directly to an active POS draft; scan/search within POS remains the
  order-entry workflow.
- Stock reservation, availability promises, low-stock alerts, or checkout stock deduction.
- Product images, categories, suppliers, bulk actions, import/export, or a separate API.
- Any Milestone 4 payment, checkout, completed-order, or stock-movement behavior.

## 11. Verification ownership

- Automated tests will cover policies, role and cross-shop matrices, safe-field response content,
  mutation denial, search/filter/pagination, and owner/admin regressions.
- Per `AGENTS.md`, Codex will not perform manual frontend verification unless explicitly asked.
  The user will receive steps to check navigation, list/detail visibility, narrow layouts, and
  offline behavior after implementation.

## 12. Approval gate

After this feature specification is approved, create the Milestone 3.1 technical refinement. Then
create development tasks, perform the required whole-package review/fix cycle, and only then begin
implementation.
