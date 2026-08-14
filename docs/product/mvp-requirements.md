# Single-Shop Retail POS - MVP Requirements

**Status:** Approved  
**Version:** 1.7
**Target:** One retail/grocery shop, one checkout computer initially  

## 1. Product goal

Build a fast, reliable POS that runs entirely inside the shop without internet access. It must manage products and stock, support up to three active customer orders, complete cash sales, process returns, and provide a searchable order history.

The design may allow additional checkout computers and shops later, but the MVP will not expose multi-shop features or introduce multi-tenant complexity.

## 2. Confirmed operating assumptions

- One checkout computer and one active cashier initially.
- A user must log out before another cashier uses the same computer.
- Future checkout computers may use the system simultaneously over the shop's local network.
- Products are sold only in whole-number quantities, not by weight.
- Tax calculation and reporting are excluded from the MVP; selling prices are final prices.
- Cash is the only payment method.
- Receipt printing is not required.
- The application must work without an internet connection.
- Returns are common and are part of the MVP.
- New stock is received and counted manually.
- A sale may continue when recorded stock is insufficient, but the exception must be warned, acknowledged, and audited.
- Checkout records the order total, cash received, and signed change (`cash received - total`). Cash received may be above or below the total and the signed change must be visible.
- Currency is Pakistani Rupees (`PKR`).
- Business timezone is `Asia/Karachi`.
- The host checkout computer runs Windows.

## 3. Roles and permissions

### Owner

- Full system access.
- Creates, disables, and manages admins.
- Can perform every admin and cashier action.

### Admin

- Creates, disables, and manages cashiers.
- Manages products, prices, and inventory.
- Processes sales, returns, and voids.
- Views all orders, daily summaries, and audit records.
- Cannot create or promote another owner.

### Cashier

- Creates, holds, resumes, and completes sales.
- Searches products and views information needed at checkout.
- Has read-only access to completed shop orders needed to find an original sale and process a return.
- Processes full and partial returns linked to an original order.
- Can quick-create a product from an unknown checkout barcode using only barcode, name, and selling price.
- Cannot otherwise manage users, products, prices, or stock.
- Cannot void completed sales.

All actions must be associated with the logged-in user. Passwords must never be stored in plain text.

## 4. Functional requirements

### 4.1 Authentication

- Users log in with a unique username and password.
- Inactive users cannot log in.
- Logout ends the current browser session.
- Protected actions must be authorized on the server, not only hidden in the interface.

### 4.2 Products

Each product has:

- Optional barcode stored as text so leading zeroes are preserved.
- Name.
- Selling price.
- Optional SKU.
- Optional cost price.
- Active/inactive status.
- Created and updated timestamps.
- Creator, creation source, and a needs-admin-review flag where applicable.

Rules:

- A product can be found by scanning its barcode or searching by name, barcode, or SKU.
- Scanning an unknown barcode from inventory management opens the create-product form with the barcode prefilled.
- Scanning an unknown barcode at checkout lets the cashier quick-create the product with the barcode prefilled, then add it to the current order.
- A quick-created product is active with zero opening stock, is marked as needing admin review, and generates an audit event.
- A non-empty barcode cannot belong to more than one product in the same shop.
- Barcode-less products are added to an order through product search.
- A product referenced by an order is deactivated rather than deleted.
- Price changes never change historical orders.

### 4.3 Inventory

- An admin can scan or search for a product and record received stock.
- During normal admin product creation, an optional quantity received now is recorded atomically as
  a real receipt movement; the product balance is never assigned directly by the product form.
- Received quantity must be a positive whole number.
- An admin can make a positive or negative stock correction with a required reason.
- Current stock is backed by an immutable inventory movement ledger; it is not silently overwritten.
- Movement types include `RECEIPT`, `SALE`, `RETURN`, `VOID`, and `ADJUSTMENT`.
- Every movement records product, quantity change, user, date/time, reason or source record, and resulting stock.
- Current stock may be negative when a recorded sale exceeds the system balance. The negative balance remains visible until corrected by a real receipt or a reasoned adjustment.
- The system must never create an automatic correction merely to hide negative stock.
- Draft orders do not reserve stock. Stock is checked again when checkout is completed.

### 4.4 Active and held orders

- Each checkout terminal can maintain up to three active order tabs.
- Scanning a known barcode adds one unit to the selected order.
- Scanning the same product again increases its quantity.
- The cashier can change quantity to a positive whole number or remove a line before checkout.
- Product search can add an item when scanning fails.
- Each line shows product name, unit price, quantity, and line total.
- The order shows the final total.
- Active orders are saved in the database so refresh, logout, or browser restart does not lose them.
- A cashier logging into the same terminal can see and resume drafts left by the previous cashier; creator, resuming cashier, and completing cashier are recorded.
- Resuming another cashier's draft creates an audit event.
- A populated active order uses **Clear order**. It requires an in-POS confirmation dialog with visible **Keep order** and **Clear order** buttons. `Enter` confirms clearing; `Escape` or **Keep order** closes the dialog without changing the order.
- Clearing removes every item, resets the total, and keeps the same active order tab ready for the next customer. It requires no reason, creates no discard/audit/history record, and does not affect stock.
- An empty order tab uses **Close tab** and closes immediately without confirmation, but only when another active tab remains. The only active empty tab cannot be closed, so its close action is hidden.
- A line's unit price is captured when the product is added. Later catalog price changes do not silently change an existing draft.
- The system records both the user who created the order and the user who completes it.

### 4.5 Cash checkout

- Checkout accepts the cash amount received and shows signed change.
- The order subtotal is the sum of its line totals.
- The order total equals its subtotal; checkout has no separate round-off input, reason, change-availability choice, or round-off confirmation.
- `change = cash received - total`. Positive change means cash exceeds the total; negative change means cash is short of the total. Both are permitted and stored exactly.
- The cashier completes the normal sale from the POS with one submit action rather than navigating through a separate checkout page.
- Checkout warns when requested quantities exceed recorded stock. After cashier acknowledgement, the sale may continue, stock may become negative, and the exception is audited.
- Completing a sale creates the order, cash payment, order lines, and stock movements in one database transaction.
- If any part fails, none of the checkout changes are committed.
- Stock rows are locked and rechecked during checkout to prevent overselling when more computers are added.
- A completed order receives a permanent human-readable order number.
- After success, the completed order summary is shown and its tab becomes a fresh order.
- Each order line stores snapshots of product name, barcode, and unit price.

### 4.6 Completed orders, voids, and returns

- Completed orders cannot be edited or deleted.
- An admin may void an entire completed order entered in error.
- A void records the admin, date/time, required reason, cash refunded, and sellable-stock reversal. It never deletes the original order.
- Owner, admins, and cashiers can process a full or partial return against a completed order.
- Every return must be linked to an identifiable original order; unlinked returns are not permitted.
- The original order can be found by order number, product/barcode, date range, cashier, or amount.
- Returned quantity cannot exceed quantity sold minus quantity already returned.
- Each returned line is marked either `RESTOCK` or `DAMAGED/NOT_RESTOCKED`.
- Restocked items create positive inventory movements; damaged/non-restocked items do not increase sellable stock.
- Cash refunded, processing user, date/time, and an optional return reason/note are recorded.
- A return is a separate immutable transaction linked to the original order.
- An order with any return cannot be voided, and a voided order cannot be returned.
- An order exposes a clear status: `COMPLETED`, `VOIDED`, `PARTIALLY_RETURNED`, or `RETURNED`.

### 4.7 Orders page

- Orders are listed newest first with pagination.
- Each row shows order number, date/time, cashier, item count, total, status, and prominently highlighted signed change.
- Users can search by order number, product/barcode, or amount and filter by date, cashier, status, and whether change is non-zero.
- All roles can view completed shop orders read-only so an original return transaction can be found. Reports and audit pages remain owner/admin-only.
- Order details show line items, total, cash received, signed change, payment, stock-impacting reversals, and related returns.
- The MVP does not print receipts.

### 4.8 Daily summary and audit

- Owner and admins can view a selected day's gross sales, returns, voids, net sales, completed order count, cash collected/refunded, non-zero-change order count, and signed change total.
- Product and inventory pages provide filters for negative stock and cashier-created products needing review.
- The system records audit events for login-relevant account changes, product price changes, inventory adjustments, product quick-creation, negative-stock checkout acknowledgement, draft takeover, voids, and returns. Clearing an order or closing an empty tab is not audited. Cash/change is permanently represented by the immutable payment rather than a separate audit event.
- Audit events include actor, action, target, date/time, and relevant before/after values.

## 5. Tax rule

Tax calculation, configuration, display, and reporting are excluded from the MVP. Product selling prices are treated as final prices, so the order total is the sum of its line totals. Tax support may be designed and migrated separately in a future version.

## 6. Core records

- `Shop` - one seeded shop in the MVP.
- `Terminal` - one seeded checkout terminal initially; additional terminals can be added later.
- `User` - custom Django user with owner, admin, or cashier role.
- `Product` - catalog and current sellable quantity.
- `InventoryMovement` - immutable stock ledger.
- `Order` - terminal-scoped draft or completed sale with creator, completing cashier, subtotal, and final total.
- `OrderItem` - quantity and historical product/price snapshots.
- `Payment` - cash received and change; designed to permit more methods later.
- `Return` and `ReturnItem` - immutable refund and restock decisions.
- `AuditEvent` - security and business-operation audit trail.

Core business records should contain `shop_id` even though only one shop is supported. The UI and permissions remain strictly single-shop in the MVP.

## 7. Technical requirements

- **Backend:** Django 5.2 LTS, pinned to the latest compatible `5.2.x` patch release.
- **Frontend:** Django templates styled with locally compiled Tailwind CSS and minimal locally
  bundled JavaScript; no runtime CDN dependency.
- **Database:** PostgreSQL running from a pinned official Docker image on the shop host.
- **Currency:** PKR, stored as fixed-precision decimal values.
- **Money:** fixed-precision decimal values; never floating-point values.
- **Deployment:** Django runs on the Windows checkout computer and connects through `localhost` to the PostgreSQL Docker container.
- **Future terminals:** additional computers connect through the local network to the same application and database; internet is not required.
- **Production service:** the application starts automatically after a computer restart and is served by a production-capable Python server, not Django's development server.
- **Time:** store timezone-aware timestamps and display them in `Asia/Karachi`.
- **Assets:** all application assets, fonts, and dependencies required at runtime are stored locally.

Django 5.2 is an LTS release supported with security updates for at least three years from its April 2025 release: <https://docs.djangoproject.com/en/5.2/releases/5.2/>.

## 8. Backup and recovery

- A local automated PostgreSQL backup runs daily.
- At least seven recent daily backups are retained.
- Backups are copied to a second physical location, such as an external drive, when available.
- No cloud service is required for normal operation or backup creation.
- A documented restore procedure must be tested before launch.

## 9. Explicitly out of scope

- Products sold by weight or barcode scales.
- Multiple shops, warehouses, or public internet access.
- Suppliers, purchase orders, and supplier balances.
- Customer accounts, loyalty, store credit, and credit sales.
- Discounts, coupons, promotions, and manual round-off controls.
- Card, bank, wallet, or split payments.
- Receipt printing and cash-drawer integration.
- Cashier shifts, opening float, and end-of-day cash counting.
- Product variants, batches, serial numbers, and expiry tracking.
- All tax calculation, configuration, display, and reporting.
- Returns that cannot be linked to an original completed order.
- Online synchronization, cloud hosting, and offline-first browser synchronization.
- Mobile applications and advanced analytics.

## 10. Acceptance criteria / definition of done

The MVP is ready for pilot use when:

1. Owner, admin, and cashier permissions pass automated tests.
2. A real USB barcode scanner can create/find products and add items to an order.
3. Three terminal-scoped held orders survive refresh, cashier change, logout, and application restart.
4. A cash sale records payment and deducts the correct stock exactly once.
5. Concurrent checkouts update stock consistently; an acknowledged shortage may create an auditable negative balance but never a lost or duplicate movement.
6. Full and partial cashier returns require the original order, enforce remaining returnable quantities, and apply correct restocking.
7. Completed order history remains unchanged after later product changes.
8. Orders, signed change, returns, voids, inventory changes, and daily totals reconcile in test scenarios.
9. The application starts after machine restart and works with internet disconnected.
10. A backup is created and successfully restored on a test installation.

## 11. Delivery sequence

1. Project setup, local deployment, custom user model, roles, and shop settings.
2. Product catalog, optional-barcode workflow, and inventory movement ledger.
3. Terminal-scoped three-tab checkout, product search/quick-create, totals, and cash calculation.
4. Transactional checkout, stock exceptions, signed change, and order history.
5. Linked partial/full cashier returns, admin voids, audit trail, and daily summary.
6. Automated tests, offline deployment packaging, backup/restore, and shop pilot.
