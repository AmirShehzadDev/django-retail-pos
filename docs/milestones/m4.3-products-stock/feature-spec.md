# Milestone 4.3 Feature Specification - Unified Products and Stock Workspace

**Status:** Approved direction; planning review passed

**Version:** 1.1

**Approved:** 2026-08-06

**Inputs:** `docs/product/mvp-requirements.md`, `docs/product/roadmap.md`, completed Milestone 2 and 3.1 behavior, and the
user-approved consolidation proposal

## 1. Objective

Replace the routine three-screen Products, Inventory, and Receive stock navigation with one
**Products & Stock** workspace. Owner/admin users can search or scan, create and edit products,
receive or correct stock, and inspect recent stock history without leaving the workspace. Cashiers
use the same workspace in read-only mode.

The change reduces navigation and clicks. It does not merge stock into ordinary product editing or
weaken the immutable inventory ledger.

## 2. Actors and permissions

### Owner and admin

- View same-shop products and stock.
- Scan/search products and use Create, Receive, Edit, Adjust, status, review, and history actions.
- View cost price and review metadata.
- Open the complete paginated inventory movement history.

### Cashier

- Search/scan and view the same safe product fields already approved in Milestone 3.1.
- Open read-only product details from the workspace.
- Cannot see cost, review metadata, receipt/adjustment/history data, or any mutation control.
- Cannot reach a mutation by a crafted enhanced or fallback request.

Anonymous, inactive, cross-shop, and unauthorized requests remain rejected on the server.

## 3. Workspace layout and navigation

- Main navigation contains one **Products & Stock** entry for owner/admin and **Products** for a
  cashier. The separate Inventory entry is removed.
- The home page contains one product/stock action instead of separate Products and Receive stock
  actions.
- The workspace has a prominent scanner/search field, compact filters, an Add product action for
  managers, and a paginated product table.
- Each manager row exposes a prominent **Receive** action for active products plus compact access
  to Edit, Adjust, status/review, and Details.
- Cashier rows expose only Details/View.
- The full movement-history page remains available to managers as an infrequent audit view from
  the workspace; it is not a second daily-workflow entry in the main navigation.

## 4. Search and scan behavior

1. The user scans or types a name, barcode, or SKU into the common field.
2. An exact same-shop barcode match takes priority over general text search.
3. For an active exact match, a manager receives the product's Receive stock dialog immediately;
   a cashier receives safe read-only details.
4. For an inactive exact match, the workspace identifies the product and does not offer a stock
   mutation until it is reactivated.
5. When there is no exact barcode match, the entered text filters the product list by name,
   barcode, or SKU.
6. A manager may explicitly choose to create a product with the unmatched value prefilled as its
   barcode. The system never creates a product merely because a search returned no result.
7. Search results, filter state, and pagination remain scoped to the user's shop.

Scanner input remains text so leading zeroes are preserved. Actual USB-scanner timing/focus is a
user-owned frontend verification item.

## 5. Create product dialog

The manager can enter:

- name;
- optional barcode;
- optional SKU;
- selling price;
- optional cost price;
- optional **Quantity received now**; and
- optional receipt note.

Quantity received now is blank or a positive whole number. Blank means no receipt. A supplied
quantity creates the product at zero internally and then records one real `RECEIPT` movement in the
same transaction. If either product creation or receipt fails, neither is committed. The resulting
balance and movement must reconcile.

This catalog-created product remains active, catalog-sourced, and not marked for cashier-product
review. Cashier quick-create at checkout remains unchanged: it starts at zero, is audited, and
needs admin review.

Duplicate identifiers and all existing price/product validation remain enforced.

## 6. Receive stock dialog

- Available only for an active same-shop product to owner/admin.
- Shows product name, barcode/SKU, current stock, quantity received, optional note, and projected
  stock.
- Quantity must be a positive whole number.
- Successful submission records exactly one immutable `RECEIPT` movement and updates current stock
  in the same transaction.
- Success closes the dialog, refreshes the affected workspace results in place, displays a compact
  dismissible toast, and restores the scan/search focus.

## 7. Edit product dialog

- Edits the existing product fields and never directly edits stock.
- Shows current stock as read-only context.
- Price-change audit behavior remains unchanged.
- Saving refreshes the workspace in place and does not alter historical sales.

## 8. Adjust stock dialog

- Accepts a positive or negative non-zero whole-number change and a required reason.
- Shows current and projected stock, including a clear warning if the result is negative.
- Records exactly one immutable `ADJUSTMENT` movement and the existing adjustment audit event.
- It never silently overwrites or automatically corrects a balance.

## 9. Details, status, review, and history

- One reusable dialog/drawer shows product identity, prices/stock allowed for the actor, status,
  and recent movements for a manager; cashier details remain restricted to approved safe fields.
- Manager details expose Edit, Adjust, status change, and Mark reviewed where applicable without
  adding separate main navigation destinations.
- Deactivation/reactivation requires explicit confirmation and retains the product record.
- Mark reviewed uses the existing review rule and creates no stock movement.
- Managers can open full paginated movement history when recent entries are insufficient.
- Only one product dialog/drawer may be open at a time; dialogs do not stack.

## 10. Progressive enhancement and errors

- Normal use loads forms/details into one local, accessible dialog/drawer and submits them without
  full-page navigation.
- Successful enhanced actions close the dialog, refresh the server-rendered product results,
  preserve compatible filters, show a toast, and return focus to search/scan.
- Validation errors remain inside the open dialog with entered values preserved.
- Permission, stale/concurrent, and unexpected errors do not claim success or partially mutate
  product/stock data.
- Existing full-page product, receipt, adjustment, status, detail, and movement routes remain
  functional no-JavaScript/direct-link fallbacks. No remote asset or frontend framework is added.

## 11. Concurrency and data effects

- Product and actor locks, shop scope, `transaction.atomic`, and identifier constraints remain
  server authoritative.
- Receive and adjustment services lock the product and append one movement with its resulting
  balance.
- Composite create-with-receipt is atomic across product creation and receipt creation.
- Concurrent receives/adjustments cannot lose a committed update; displayed data is refreshed from
  the server after success.
- Listing, search, scan, details, cancellation, and validation failure change no product or stock.
- No model or database migration is required.

## 12. Explicit exclusions

- Direct stock editing on the product form.
- Bulk import/export, purchase orders, suppliers, delivery documents, batch/expiry tracking,
  warehouse/location support, stock transfer, or physical stock-count sessions.
- Product images, categories, units by weight, taxes, receipt printing, or internet services.
- Cashier access to cost, review, movement history, or stock/product mutations.
- Removal of full-page fallback URLs or the full audit-history page.
- Changes to POS quick-create, checkout, returns, voids, payments, or completed orders.

## 13. Acceptance criteria

1. Owner/admin can complete routine create, receive, edit, adjust, status/review, and recent-history
   work from one Products & Stock workspace without normal full-page navigation.
2. Cashier can use the same list/search/details workspace with no confidential field or mutation
   control exposed.
3. Exact known barcode scan opens the correct role-appropriate interaction; an unknown value never
   auto-creates a product and can explicitly prefill manager product creation.
4. Optional Quantity received now creates one atomic product-plus-receipt result; blank creates a
   zero-stock product with no movement.
5. Receive and Adjust retain all existing validation, ledger, audit, negative-stock, permission,
   and concurrency guarantees.
6. Product edit cannot directly change stock and price changes do not alter historical orders.
7. Enhanced success stays on the workspace, refreshes server data, shows a dismissible toast, and
   restores intended focus; validation errors remain in the dialog.
8. No-JavaScript/direct-link fallbacks and the full movement history continue to work.
9. Navigation/home no longer present Products, Inventory, and Receive stock as separate routine
   destinations.
10. Focused and full automated regression gates pass with no migration drift.
11. Actual modal layout, keyboard use, focus/scanner behavior, responsive behavior, and offline
    browser behavior are verified by the user rather than claimed through server tests.

## 14. Requirement reconciliation

This specification changes only the presentation and orchestration of approved Milestone 2 and
3.1 capabilities. The phrase "new products always start at zero" remains true at the product-row
creation boundary: optional opening stock is applied immediately afterward through a genuine,
atomic receipt movement. It does not permit direct opening-balance assignment. The separate
Inventory and product screens remain historical/fallback implementation details rather than
routine navigation.
