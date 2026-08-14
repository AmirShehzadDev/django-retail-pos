# Milestone 2 - Completion Evidence

**Status:** Complete

**Automated verification:** 2026-08-03

**Manual acceptance:** Confirmed by the user on 2026-08-03

**Platform:** Windows 11, Python 3.13.14, Node 22.22.3, npm 10.9.8, Dockerized
PostgreSQL 16.14

## 1. Delivered

- Owner/admin product create, edit, search, filter, detail, deactivate/reactivate, and review flows.
- Optional text barcode with leading-zero preservation and shop-scoped uniqueness.
- Optional case-insensitive shop-scoped SKU uniqueness.
- Inventory scanner workflow for known, inactive, and unknown barcodes.
- Zero-stock product creation followed by explicit opening-stock receipt.
- Positive receipts and signed reasoned adjustments using locked PostgreSQL transactions.
- Negative-stock display/filtering without blocking or automatic correction.
- Append-only receipt/adjustment movement history with actor, reason, signed change, and balance.
- Focused product-price and inventory-adjustment audit events.
- Read-only inventory reconciliation command.
- Role-aware Tailwind navigation, scanner focus, and projected-balance feedback using local assets.

## 2. Automated evidence

| Check | Result |
|---|---|
| Docker PostgreSQL | Healthy on `127.0.0.1:5433` |
| Migrations | `core.0003`, `catalog.0001`, and `inventory.0001` applied |
| Migration drift | No changes detected |
| Product/inventory model and audit tests | 17 passed |
| Catalog suite | 33 passed |
| Inventory suite | 26 passed, including concurrent receipts |
| Full PostgreSQL regression suite | 145 passed |
| Ruff lint | Passed |
| Ruff format check | 94 files formatted |
| Django development check | Passed with no issues |
| Python dependency check | No broken requirements |
| Inventory reconciliation | Passed; development catalog contained zero products at verification |
| Node JavaScript syntax check | Passed |
| `npm ci` | Passed; 0 vulnerabilities |
| Tailwind build | Passed twice with identical output |
| Compiled CSS SHA-256 | `F1EE2D508DF9420DF38EFE0002DDD414AF16C40B8EAF03C83A3F5A9CEBDAF998` |
| `collectstatic` | Passed; generated assets available locally |
| Authenticated production page smoke | Home, products, inventory scan, and movements returned HTTP 200 |
| Waitress production smoke | Health, login, and compiled CSS returned HTTP 200 |
| Production `/admin/` | HTTP 404 |

The deployment check reports the same four expected localhost-HTTP warnings recorded in earlier
milestones: HSTS, HTTPS redirect, secure session cookie, and secure CSRF cookie. The shop application
is not being exposed to an untrusted network in this milestone.

## 3. Automated acceptance coverage

- Owner/admin management succeeds while anonymous/cashier/cross-shop access is denied.
- Names and identifiers normalize safely; a barcode such as `0012345` retains its leading zeroes.
- Duplicate barcode, case-insensitive duplicate SKU, invalid price, decimal quantity, zero receipt,
  zero adjustment, blank reason, and inactive-product mutations are rejected without partial data.
- Product creation derives zero stock, creator, source, review, active, and shop metadata server-side.
- Price audit events are focused and occur only for actual price changes.
- Receipt and adjustment transactions update cached stock and append exactly one matching movement.
- Adjustment audit failure rolls back stock and movement changes.
- Two concurrent receipts preserve both changes and correct movement balances.
- Negative stock remains valid, visible, filterable, and reconciled.
- Browser refresh after a successful stock write does not repeat the movement.
- Reconciliation reports discrepancies and has no automatic-fix path.

## 4. Required manual acceptance

Automated tests cannot prove physical USB scanner behavior or operation with the Windows computer
actually disconnected from the internet. These checks are required before Milestone 2 is closed.

### Setup

From PowerShell in the project folder:

```powershell
docker compose up -d db
.\.venv\Scripts\Activate.ps1
python manage.py migrate
npm run css:build
python manage.py runserver 127.0.0.1:8000
```

Open `http://127.0.0.1:8000/accounts/login/` and log in as the owner or an admin.

### Checklist

1. Open **Inventory**. Confirm the barcode field is focused. Scan a new test barcode with leading
   zeroes, such as `0012345`. Expected: the create-product form opens with the exact barcode
   prefilled and no product has been created yet.
2. Enter a name and selling price, save the product, and inspect its detail. Expected: it is active,
   source is Catalog, it does not need review, and current stock is zero.
3. Choose **Receive stock**, enter quantity `10`, and save. Expected: current stock becomes 10 and
   one receipt movement shows `+10`, the resulting balance, logged-in actor, and receipt reason.
4. Return to **Inventory** and scan the same barcode. Expected: it opens that product's receipt
   page rather than creating another product.
5. Adjust stock by `-12` with a reason. Expected: the preview warns about negative stock, the save
   succeeds at `-2`, and exactly one adjustment movement plus its reason is visible.
6. Open **Products**, enable the negative-stock filter, and search by name, barcode, and SKU.
   Expected: the test product is found and clearly labelled negative.
7. Try a duplicate barcode, receipt quantity `0` or `1.5`, adjustment `0`, and an adjustment without
   a reason. Expected: each is rejected and stock/movement count does not change.
8. Deactivate the product. Expected: its balance/history remain unchanged and receipt/adjustment is
   unavailable until it is reactivated. Reactivate it afterward if the test product is retained.
9. Log in as a cashier. Expected: Products and Inventory links are absent; direct visits to
   `/products/` and `/inventory/scan/` are denied.
10. Disconnect internet access while leaving Docker and Django running. Repeat product search,
    known-barcode scan, and movement-history navigation. Expected: the pages and styling continue
    working with no missing remote assets.
11. Stop Django, run `python manage.py reconcile_inventory`, and restart it if needed. Expected: the
    command reports the product count and no discrepancy.

If a real scanner is temporarily unavailable, typing the barcode and pressing Enter is acceptable
for a development check. A physical-scanner pass remains required before the shop pilot.

## 5. Completion decision

The implementation, automated verification, and user-confirmed manual scanner/interface/offline
acceptance gates pass. Inventory reconciliation also passed with the user's test product. Milestone
2 is complete, and Milestone 3 feature planning may begin.
