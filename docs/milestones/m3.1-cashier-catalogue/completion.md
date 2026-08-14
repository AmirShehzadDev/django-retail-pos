# Milestone 3.1 - Cashier Read-Only Catalogue Evidence

**Status:** Complete

**Automated verification:** 2026-08-04

**Manual acceptance:** Approved by the user on 2026-08-04

## 1. Delivered

- Cashier-visible Products navigation and Browse products home action.
- Same-shop read-only product list with search, active/inactive and negative-stock filters,
  50-product pagination, and preserved permitted query parameters.
- Cashier-safe detail page showing only name, selling price, stock, barcode, SKU, and status.
- Informational stock and inactive-product guidance.
- Server-side separation between catalogue viewing and owner/admin catalogue management.
- Cashier denial for catalog creation/edit/status/review and all inventory management/history URLs.
- Separate cashier detail template with no cost, creator/source, review, timestamp, movement, audit,
  or management response data.
- No model, migration, service, audit, inventory, POS-draft, or Milestone 4 behavior change.

## 2. Automated evidence

| Check | Result |
|---|---|
| Mandatory planning-package review | Passed after correcting stock-notice semantics and crafted review-filter pagination handling |
| Focused integrated catalogue/core/inventory/POS checks | 56 passed |
| Full PostgreSQL regression suite | 278 passed in 241.751s; no skips |
| New regression coverage | 9 additional tests beyond the 269-test M3 baseline |
| Django system check | Passed with no issues |
| Migrations and drift | No migrations to apply; no model changes detected |
| Policy/security response checks | Passed for all roles, inactive/anonymous, cross-shop, sensitive sentinels, and mutation snapshots |
| Ruff lint and format | Passed; 104 Python files formatted |
| Python dependency check | No broken requirements |
| npm audit | 34 packages; 0 vulnerabilities |
| JavaScript regression | Syntax passed; 4/4 POS tests passed |
| Tailwind deterministic build | Passed twice; SHA-256 `AFE8EF69A47A63BCDB87482B034349B6A8D06ABADDF80C3715D9F56529C79148` |
| Static collection | Passed; 1 copied and 130 unchanged |
| Inventory reconciliation | Passed for 1 development product |
| Production check | Passed; deploy check has the 4 documented localhost-HTTP warnings |
| Local/offline asset scan | No remote runtime source; only Tailwind's inert license URL comment |
| Scope review | No cashier mutation broadening, schema change, secret, or M4 behavior |

The mutation-denial test exercises cashier GET/POST requests for catalog create, edit, status,
review, inventory scan, receipt, adjustment, and movement history. Product, price, stock, movement,
and audit snapshots remain unchanged after every denied request.

## 3. User frontend acceptance

Codex did not perform manual browser, visual, responsive, or offline frontend verification. The
user approved the completed enhancement on 2026-08-04. The checklist remains below for future
regression checks.

### Setup

```powershell
docker compose up -d db
.\.venv\Scripts\Activate.ps1
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
```

Prepare one cashier and one owner/admin account plus active, inactive, negative-stock, leading-zero
barcode, and barcode-less products in the same shop.

### Required checklist

1. Log in as the cashier. Expected: **Products** appears in primary navigation and **Browse
   products** appears on Home; Inventory, Users, and Shop settings remain absent.
2. Open Products and search by partial name, leading-zero barcode, and SKU. Test active, inactive,
   and negative-stock filters and move between pages if enough products exist. Expected: matching
   same-shop results, preserved permitted filters, exact barcode text, and informational stock
   notice.
3. Inspect list rows and open active/inactive product details. Expected: only name, barcode/SKU,
   PKR selling price, stock, and status; inactive detail says it cannot be added to a new order.
4. Confirm cost price, Needs review, creator/source, timestamps, movements, actors/reasons, Create,
   Edit, Receive, Adjust, Review, and status-changing actions are absent. Directly opening known
   manager URLs should be denied and must not change any data.
5. Log in as owner/admin. Expected: existing Create, cost, Needs review, inventory history, edit,
   receive, adjust, and status/review controls remain available.
6. Repeat the cashier list/detail checks at the shop's normal and narrow browser widths, then with
   internet disconnected while local services remain running. Expected: readable controls and
   complete local styling with no remote-request failure.

## 4. Completion decision

The planning review, implementation, automated verification, and user approval all pass.
Milestone 3.1 is complete, and Milestone 4 feature specification may begin.
