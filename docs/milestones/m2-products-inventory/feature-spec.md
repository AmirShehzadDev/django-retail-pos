# Milestone 2 - Product Catalog and Inventory

**Status:** Approved

**Version:** 1.0

**Inputs:** `docs/product/mvp-requirements.md` v1.4, `docs/product/roadmap.md` v1.3,
`docs/architecture/technical-design.md` v0.5, and the completed Milestone 1 application

## 1. Objective

Allow the owner and admins to create and maintain the shop's product catalog, record opening and
newly received stock, make explained stock corrections, and verify every displayed stock balance
against an immutable movement history.

Milestone 2 does not add checkout orders or cashier product quick-creation. It prepares the catalog
and inventory foundation those later workflows will use.

## 2. Actors

### Owner

- Has the same catalog and inventory permissions as an admin.
- Can view, create, edit, deactivate, reactivate, receive, adjust, and review products.

### Admin

- Has full catalog and inventory access for the same shop.
- Can record receipts and positive or negative corrections.
- Can review products marked as needing admin review.

### Cashier

- Cannot access Milestone 2 catalog-management or inventory-management pages.
- Receives no quick-create or stock-changing permission in this milestone.
- Product lookup at checkout and unknown-barcode quick-create arrive in Milestone 3.

All actions use the authenticated user's shop. A URL or submitted identifier from another shop must
not reveal or modify that record.

## 3. MVP decisions made in this specification

1. A newly created product always starts with a stock balance of zero. Opening stock is recorded as
   a separate receipt so it appears in the movement history.
2. A USB barcode scanner is treated as a keyboard that types text and sends Enter. No scanner SDK,
   browser extension, or internet service is required.
3. Barcodes are stored as text. Leading zeroes are preserved, surrounding whitespace is removed,
   and an empty value is stored as no barcode.
4. A non-empty barcode is unique within the shop and is compared exactly after trimming. SKU is
   optional and is unique within the shop without regard to letter case.
5. Standard owner/admin creation uses source `CATALOG` and does not need admin review. The model also
   supports source `POS_QUICK_CREATE` and a needs-review flag for Milestone 3.
6. A needs-review product remains active and usable. An owner/admin can mark it reviewed from its
   edit/detail workflow; reviewing does not change stock or price.
7. Products are never deleted through the application. They may be deactivated and later
   reactivated.
8. A product may be deactivated while its stock is non-zero or negative after a clear confirmation.
   Deactivation does not change stock. Receipts and adjustments require the product to be active;
   the product must first be reactivated if a later correction is needed.
9. Received stock is a positive whole number. A correction is a non-zero signed whole number and
   always requires a reason.
10. A correction may produce a negative balance. The result is shown as a warning but is not
    blocked, capped, or automatically corrected.
11. Product prices are PKR amounts with two decimal places. Tax fields and tax calculations do not
    exist in the MVP.
12. Movement records cannot be edited or deleted through application code or application screens.
13. Price changes and manual stock adjustments generate focused audit events. A receipt is already
    attributable and immutable in the inventory ledger, so it does not create a duplicate audit
    event.

## 4. Permission matrix

| Capability | Owner | Admin | Cashier |
|---|---:|---:|---:|
| View/search catalog-management pages | Yes | Yes | No |
| Create/edit product | Yes | Yes | No |
| Deactivate/reactivate product | Yes | Yes | No |
| Mark product reviewed | Yes | Yes | No |
| Scan/search for inventory receipt | Yes | Yes | No |
| Receive stock | Yes | Yes | No |
| Make reasoned stock adjustment | Yes | Yes | No |
| View inventory movement history | Yes | Yes | No |
| Edit/delete movement history | No | No | No |

An unauthorized request returns the same access-denied behavior established in Milestone 1. Hiding
a navigation link is not considered authorization.

## 5. Preconditions and shared rules

- The user is authenticated and active.
- The bootstrap-created shop exists and uses `PKR` and `Asia/Karachi`.
- Quantity fields accept only base-10 whole numbers; decimal quantities such as `1.5` are invalid.
- Prices use standard decimal input and are stored with two decimal places; floating-point numbers
  are not used for money.
- The active state affects future operations only. Existing movement history remains visible.
- Every successful write uses POST with CSRF protection and redirects after success, preventing a
  browser refresh from repeating the write.
- Validation errors preserve safe form input and do not create or partially update records.

## 6. Product catalog flows

### 6.1 Product list and search

The product list is the catalog landing page. It shows, at minimum:

- name;
- barcode or a clear no-barcode value;
- SKU when present;
- selling price in PKR;
- current stock;
- active/inactive state; and
- needs-review state.

The list:

- is paginated at 50 products per page;
- sorts by product name and then identifier for a stable result;
- searches by partial, case-insensitive name, partial barcode, or partial, case-insensitive SKU;
- filters by active state, negative stock, and needs-review state; and
- retains the current search and filters while moving between pages.

The negative-stock filter means `stock < 0`, not zero stock. The needs-review filter works even
before the Milestone 3 quick-create UI exists so the review workflow is ready and testable.

### 6.2 Create product normally

The owner/admin opens the create form and enters:

- required name;
- optional barcode;
- optional SKU;
- required selling price; and
- optional cost price.

The form displays no opening-stock field. On success it creates an active product with zero stock,
source `CATALOG`, the logged-in creator, and `needs review = No`, then opens the product detail page.
The detail page offers a direct action to receive opening stock.

### 6.3 Create after an unknown inventory scan

On the inventory scan page, the owner/admin scans or enters a barcode and submits it.

- If exactly one active product has that barcode, the receipt flow opens for that product.
- If an inactive product has that barcode, its detail page opens with guidance to reactivate it;
  the system must not offer to create a duplicate.
- If no product has that barcode, the create-product form opens with the exact trimmed barcode
  prefilled.
- The unknown scan itself creates nothing. The user must complete and submit the product form.

An empty scan is rejected. The normal create form remains available for barcode-less products.

### 6.4 View product detail

The detail page shows all product fields, creator, creation source, review state, created/updated
times, current stock, and recent movements newest first. It provides permitted actions for edit,
receive, adjust, deactivate/reactivate, and mark reviewed.

### 6.5 Edit product

The owner/admin may change name, barcode, SKU, selling price, and cost price. Current stock,
creator, creation source, and timestamps are not editable fields.

- Removing a barcode or SKU stores no value rather than an empty identifier.
- Changing a selling or cost price does not alter movement history and will not alter historical
  order values when orders are introduced.
- A change to either price creates one price-change audit event containing the relevant before and
  after values.
- Submitting an unchanged form produces no price audit event.

### 6.6 Deactivate or reactivate

Deactivation and reactivation are explicit POST actions with a confirmation screen. The
confirmation shows the product and current stock. The operation changes only active status and
updated time; it creates no inventory movement.

An inactive product stays searchable when the inactive/all filter is selected. Its detail and
movement history remain accessible to owner/admin.

### 6.7 Mark product reviewed

For a product with `needs review = Yes`, an owner/admin can mark it reviewed using an explicit POST
action. The product's creator and creation source remain unchanged. A reviewed product cannot be
set back to needs-review through the Milestone 2 UI.

## 7. Inventory flows

### 7.1 Scan or search for a receipt

The inventory landing page places focus in the barcode input when the page loads and after a
validation error. Pressing Enter submits the exact barcode lookup. A normal product search link is
available when the item has no barcode or scanning fails.

Searching and selecting an active product opens its receipt form. Selecting an inactive product
opens its detail page with the reactivation guidance.

### 7.2 Record received stock

The receipt form shows product identity and current stock. The owner/admin enters a positive whole
quantity and may enter a short note. Before submission, the page shows or clearly labels that the
new balance will be current stock plus the quantity.

On success, one transaction:

1. locks and rereads the product;
2. validates that the product is active;
3. increases current stock exactly once;
4. appends one `RECEIPT` movement with the positive change, resulting balance, actor, time, and the
   submitted note or the default reason `Manual stock receipt`; and
5. commits both changes together.

The user returns to product detail with a success message containing the new balance.

### 7.3 Record a stock adjustment

The adjustment form is reached from product detail, not from the scanner's fast receipt path. It
shows current stock and accepts:

- a signed, non-zero whole-number change; and
- a required reason explaining the physical or recording correction.

Examples are `5` to add five and `-3` to remove three. The projected balance is shown. A negative
projected balance displays a visible warning but remains valid.

On success, one transaction locks the product, changes current stock, appends one `ADJUSTMENT`
movement, and creates one inventory-adjustment audit event containing the product, movement,
change, previous balance, resulting balance, and reason. All three effects succeed or fail
together.

### 7.4 View movement history

The global inventory history is paginated newest first and shows:

- date/time in `Asia/Karachi`;
- product;
- movement type;
- signed quantity change;
- resulting stock;
- actor; and
- reason.

It can be filtered by movement type and product search. Product detail shows the same records for
one product. There are no edit or delete actions.

### 7.5 Reconcile stock

The application provides a read-only maintenance command that compares each product's current
stock with the sum of all its movement changes. It reports discrepancies, exits unsuccessfully if
any exist, and never writes a correction. A mismatch must be investigated and fixed through code
repair or a deliberate, reasoned business adjustment as appropriate.

## 8. Validation and error handling

### Product validation

- Name is required after trimming and is limited to 200 characters.
- Barcode and SKU are each limited to 64 characters after trimming.
- Blank barcode and SKU values are normalized to no value.
- Non-empty barcode must be unique in the shop.
- Non-empty SKU must be unique in the shop case-insensitively.
- Selling price is required, has at most two decimal places, and cannot be negative.
- Cost price is optional, has at most two decimal places, and cannot be negative.
- The create/edit page reports a friendly field error for an identifier conflict; a database
  constraint remains the final protection against simultaneous submissions.

### Inventory validation

- A receipt quantity must be an integer greater than zero.
- An adjustment change must be a non-zero integer.
- Adjustment reason is required after trimming and is limited to 500 characters.
- Receipt note is optional and limited to 500 characters.
- Inactive products reject receipt and adjustment submissions, including stale forms.
- A repeated POST caused by double-clicking must not be encouraged by the UI. The submit button may
  be disabled after a valid submission, but correctness relies on the transaction and redirect,
  not JavaScript.

Database or concurrency conflicts return a safe form-level error or conflict response and must not
expose a traceback in production.

## 9. Concurrency and edge cases

- Concurrent stock changes lock the same product row and apply sequentially. Each movement's
  resulting balance must match the balance after its own committed change.
- A product deactivated after a form is opened cannot receive or adjust stock from that stale form.
- Simultaneous attempts to assign the same barcode or case-insensitive SKU allow only one success.
- Leading zeroes survive scan, form validation, storage, list/detail display, and later lookup.
- A barcode may be moved from one product to another only after it is removed from the first
  product in a separate successful update.
- Negative, zero, and positive current stock are all valid stored states. Only negative stock is
  highlighted as an exception.
- Product edits never recalculate stock. Stock writes never edit product identity or price.
- Browser refresh after a successful receipt or adjustment shows the redirected page and does not
  repeat the movement.

## 10. Data and audit effects

| Action | Product effect | Movement effect | Audit effect |
|---|---|---|---|
| Create product | New active product at zero stock | None | Creator/source stored on product |
| Edit identity only | Update allowed fields | None | None |
| Change price | Update allowed prices | None | `PRODUCT_PRICE_CHANGED` |
| Deactivate/reactivate | Change active state | None | None in M2 |
| Mark reviewed | Clear needs-review flag | None | None in M2 |
| Receive stock | Increase current stock | Append `RECEIPT` | Ledger is the record |
| Adjust stock | Apply signed change | Append `ADJUSTMENT` | `INVENTORY_ADJUSTED` |

Audit events use the existing immutable `AuditEvent` writer and store only necessary before/after
business values. Movement history is the source of truth for who changed stock and when.

## 11. Acceptance criteria

1. Owner and admin can create a barcode product and a barcode-less product; cashier cannot access
   either workflow.
2. A barcode such as `0012345` is stored, displayed, and found with its leading zeroes unchanged.
3. Duplicate non-empty barcode and case-insensitive SKU submissions are rejected without partial
   writes.
4. Scanning an existing active barcode opens its receipt workflow.
5. Scanning an unknown barcode opens the create form with that barcode prefilled and creates
   nothing until the form is submitted.
6. Scanning an inactive product does not offer duplicate creation or allow stock receipt.
7. Product creation starts at zero; receiving 10 creates exactly one `RECEIPT` movement with
   resulting stock 10.
8. A `-12` correction with a reason changes stock from 10 to -2, creates exactly one movement and
   one audit event, and appears in the negative-stock filter.
9. Zero adjustment, decimal quantity, missing adjustment reason, negative price, and receipt of
   zero or a negative quantity are rejected.
10. Product current stock equals the ordered sum of all committed movement changes and the
    reconciliation command succeeds.
11. A price edit creates an audit event with before/after values; an unchanged edit does not.
12. Product deactivate/reactivate changes no stock and creates no movement.
13. A needs-review product can be filtered, inspected, and marked reviewed without changing its
    creator or source.
14. Movement records cannot be changed or deleted through services, views, or the production
    administration boundary.
15. Concurrent receipts/adjustments do not lose a change and retain correct movement balances.
16. All catalog, inventory, permission, audit, command, and page tests pass against PostgreSQL.

## 12. Manual acceptance scenarios for milestone completion

Manual verification is required when implementation finishes because automated tests cannot prove
the physical scanner behavior or the complete Windows offline experience.

Required scenarios:

1. Use a real USB scanner to scan a known barcode and receive stock.
2. Scan an unknown barcode containing leading zeroes, create the product, then scan it again.
3. Receive opening stock, apply both positive and negative corrections, and compare the displayed
   balance with movement history.
4. Create a negative balance and confirm the warning and negative-stock filter remain visible.
5. Attempt duplicate barcode and invalid-quantity submissions and confirm no movement is created.
6. Disconnect internet access and repeat catalog search, scan, receipt, and history navigation.
7. Run the reconciliation command and confirm it reports no discrepancies.

If scanner hardware is temporarily unavailable, keyboard entry followed by Enter is an acceptable
development check, but a real-scanner pass remains required before shop pilot.

## 13. Explicit exclusions

- Checkout orders, held tabs, sale deductions, returns, and void reversals.
- Cashier quick-create; the model fields needed for it are prepared but its behavior is Milestone 3.
- Suppliers, purchase orders, receiving documents, and supplier balances.
- Bulk import/export, barcode label generation, and barcode printing.
- Product variants, packs, serial numbers, batches, expiry dates, and weighted products.
- Stocktake/counting sessions, reservations, multi-warehouse transfers, and multiple shops.
- Reorder points, low-stock alerts, automatic corrections, and inventory valuation reports.
- Tax configuration or calculation.
- Public audit-history UI; focused M2 events become visible on the Milestone 6 audit page.

## 14. Approval record

The user approved this specification together with the Milestone 2 technical design and development
tasks on 2026-08-03. Material behavior changes must return here for review before implementation
continues.
