# Milestone 4.3 - Unified Products and Stock Workspace Evidence

**Status:** Complete; user frontend acceptance confirmed on 2026-08-06

**Automated verification:** 2026-08-06

## 1. Delivered

- Replaced separate Products and Inventory navigation/home actions with one role-aware
  **Products & Stock** workspace for managers and **Products** for cashiers.
- Added one prominent scan/search field with exact-barcode priority, compact status/negative/review
  filters, existing pagination, and explicit unknown-value creation instead of automatic creation.
- Added one reusable native side dialog for manager product creation, receipt, adjustment, edit,
  status confirmation, safe details, review, and recent movement history.
- Kept the full paginated movement ledger reachable as **Stock history** and kept all secure
  full-page/direct-link fallbacks.
- Added optional **Quantity received now** and receipt note to normal manager product creation.
  Product creation remains zero-balance internally, followed by one real `RECEIPT` movement inside
  the same outer transaction; receipt failure rolls back the product.
- Kept product editing separate from stock. Receive and Adjust continue using the established
  locked inventory services, immutable movements, adjustment audit, and negative-balance rules.
- Added enhanced server-rendered fragments/JSON for success and validation, in-place row refresh,
  dismissible toasts, safe committed-success refresh failure handling, and scan/search focus hooks.
- Kept cashier output server-restricted: no cost, review metadata, movement history, or mutation
  endpoints/controls are rendered, and crafted mutations remain denied.
- Marked the user's Milestone 4.2 frontend verification as accepted and reconciled the MVP,
  milestones, project design, README, and M4.3 planning package.

## 2. Automated evidence

All gates passed against Dockerized PostgreSQL 16.14:

- `python manage.py test --keepdb`: **317 tests passed**.
- focused catalog/inventory suite: **76 tests passed**.
- focused core/catalog compatibility set: **36 tests passed**.
- `python manage.py check`: no issues.
- `python manage.py makemigrations --check --dry-run`: no changes detected.
- `ruff check .`: passed.
- `ruff format --check .`: all **153 Python files** formatted.
- JavaScript syntax checks for `app.js`, `pos.js`, and `products.js`: passed.
- Node test suite: **11 tests passed**.
- `npm ci`: pinned dependencies installed; audit reported zero vulnerabilities.
- `npm run css:build`: Tailwind 4.3.3 build passed and generated local CSS.
- `python -m pip check`: no broken requirements.
- `python manage.py collectstatic --noinput`: passed; 3 files copied and 131 unchanged.
- `git diff --check`: passed.
- `docker compose ps`: PostgreSQL container healthy.

Coverage includes composite creation/receipt success and rollback, no direct stock assignment,
identifier validation, exact/unknown lookup and leading zeroes, same-shop scoping, manager/cashier
modal detail separation, fragment parity, enhanced/fallback mutations, receipt/adjustment ledger
effects, existing concurrency coverage, navigation consolidation, no migration drift, and complete
project regression.

## 3. Required user frontend acceptance

**Result:** Passed and confirmed by the user on 2026-08-06.

Codex did not perform browser, visual, responsive, focus, hardware-scanner, or offline frontend
verification.

1. Start the local app, sign in as owner/admin, and confirm the header/home show one
   **Products & Stock** destination and no separate Inventory or Receive stock destination.
2. Open Products & Stock at 1366x768 and 100% zoom. Confirm the scan/search field, filters, product
   table, and actions are clear without overlapping or cut-off dialog controls.
3. Scan/type a known active barcode and press Enter. Confirm Receive opens in the side dialog,
   current/projected stock is correct, submitting stays on the workspace, updates the row, shows a
   dismissible toast, and returns focus to scan/search.
4. Enter an unknown barcode. Confirm no product is created automatically, the filtered empty state
   offers an explicit create action with the exact leading-zero barcode, and Create opens in the
   same dialog.
5. Create that product once with Quantity received now blank and confirm stock is zero. Create a
   second product with a positive Quantity received now and note; confirm the resulting row balance
   and Stock history contain exactly that receipt.
6. From product rows/details, try Edit, Adjust, Deactivate/Reactivate, Mark reviewed when available,
   and recent movements. Confirm each normal action uses the same dialog/workspace and the full
   Stock history link remains available.
7. Submit invalid receipt quantity `0`, adjustment quantity `0`, and an adjustment without reason.
   Confirm the dialog remains open with the entered values and clear validation, with no stock
   change.
8. Sign in as cashier. Confirm search/scan opens safe read-only details and that cost, review,
   movement history, Create, Receive, Adjust, Edit, and status actions are absent.
9. Disable JavaScript temporarily and use direct Create, product detail/Edit, Receive, Adjust, and
   status URLs/links. Confirm usable full-page fallbacks and redirects still work, then re-enable
   JavaScript.

## 4. Optional confidence checks

- Disconnect the computer from the internet while the local server/database remain running and
  repeat known-barcode Receive and cashier read-only lookup. No asset or action should require the
  internet.
- Repeat the workspace at the actual shop monitor resolution and with the physical USB scanner to
  confirm Enter suffix and focus recovery.

## 5. Exclusions retained

- No direct product balance editing, migration, supplier/purchasing flow, warehouse/location,
  stock-count session, batch/expiry, category, product image, or bulk import/export.
- No changes to POS quick-create, checkout, completed orders, payments, returns, voids, tax, or
  receipt printing.
- No cashier access to confidential catalog or inventory management data.
