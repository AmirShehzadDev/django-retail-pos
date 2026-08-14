# Milestone 4 - Cash Checkout and Order History Evidence

**Status:** Revised implementation and automated verification complete; user frontend acceptance pending

**Automated verification:** 2026-08-06

> **Historical completion evidence:** Discard checks below describe the build verified at this
> date. The approved [Milestone 4.2 specification](../m4.2-clear-orders/feature-spec.md) replaces that interaction;
> its implementation and manual checklist will be delivered separately.

## 1. Delivered

- One-screen cash checkout inside the POS: Total, Cash received, signed Change, and Complete sale.
- No round-off, reason, change-availability selector, or extra checkout/confirmation page.
- Exact `change = cash received - total`; positive, zero, and negative values are permitted.
- Compact 1366x768 desktop target with order/checkout in the left two-thirds and an active-product
  catalogue in the right third; long lists scroll inside their panels.
- Default active same-shop product catalogue with search and Add actions.
- Always-visible minus/current/plus quantity controls that save immediately; no Update button.
- Fixed top-right toast notifications that do not consume POS height, with close buttons and safe
  auto-dismiss behavior for success/information messages.
- Locked atomic order completion, permanent order numbering, payment, inventory movements, focused
  shortage audit, and same-slot replacement draft.
- Same-draft idempotency and deterministic product locking for future simultaneous terminals.
- Same-shop read-only completed Orders list/detail for owner, admin, and cashier.
- Newest-first 50-row pagination, order/product/barcode/exact-total search, non-zero Change filter,
  and clearly highlighted positive/negative Change values.

Returns, voids, refunds, receipts, daily reporting, and advanced return lookup remain later work.

## 2. Automated evidence

| Check | Result |
|---|---|
| Revised planning review | Passed; no unresolved scope or design contradiction |
| Focused checkout/history/schema/concurrency tests | 18 passed |
| Complete Sales suite | 139 passed |
| Complete PostgreSQL project suite | 298 passed in 241.933s |
| Django system check | Passed with no issues |
| Development migration | Sales `0003` applied successfully |
| Migration drift | No changes detected |
| Ruff | Passed |
| POS JavaScript | 5/5 tests passed, including exact signed-change formatting |
| Tailwind | Local production build passed |
| Python/npm dependencies | No broken requirements; 0 npm vulnerabilities |
| Static collection | Passed; 3 copied and 128 unchanged |
| Inventory reconciliation | Passed for 2 development products |

The expected permission, CSRF, not-found, conflict, validation, and service-unavailable warnings in
test output are asserted failure paths, not test failures.

## 3. User frontend acceptance

Codex did not perform browser, visual, responsive, scanner-hardware, or offline frontend
verification. Perform these checks before approving the revision.

### Start the application

```powershell
Set-Location C:\Projects\offline-retail-pos
docker compose up -d db
.\.venv\Scripts\Activate.ps1
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
```

Use a cashier account and prepare an active `PKR 99.00` product with stock, plus a low-stock product.

### Required checks

1. Set the browser to 1366x768 and 100% zoom. Open POS. Confirm the whole page does not need
   vertical scrolling to complete a sale, the order uses roughly two-thirds of the width, and the
   product catalogue uses the right third. Long order/catalogue lists may scroll internally.
2. Confirm checkout shows only Total, Cash received, Change, and Complete sale. There must be no
   round-off field, reason, change-availability selector, or second confirmation screen.
3. Discard an order and confirm its success message appears as a fixed top-right toast without
   moving or cutting off the checkout footer. Close it with the cross. Repeat and leave it alone;
   confirm it disappears automatically after about five seconds. Confirm an error/warning toast
   remains until closed.
4. Add the `PKR 99.00` item, enter `100.00`, and watch Change update to `PKR 1.00`. Click Complete
   sale once. Confirm the completed order opens, stock decreases once, and a fresh empty order is
   ready in the same tab.
5. Complete another `PKR 99.00` order with `98.00` cash. Confirm it completes without an error or
   confirmation and stores Change as `PKR -1.00`.
6. Open Orders. Confirm positive Change is strongly highlighted, negative Change is strongly
   highlighted in a different color, and the non-zero Change filter returns both types.
7. Confirm the right catalogue initially lists active products, search narrows it, and Add places the
   selected product into the current order. An inactive product must not appear there.
8. On an editable cart line, confirm minus and plus are always visible and no Update button exists.
   Click plus once and confirm quantity, line total, and order total update immediately; then click
   minus and confirm they immediately return. At quantity one, minus must remain visible but
   disabled. Remove must still remove the line separately.
9. Keep two or three order tabs active and complete one. Confirm only the completed tab becomes a
   fresh empty order; the other drafts retain their products, quantities, cashier, and totals.
10. Sell more low-stock units than recorded. Confirm the POS warns about projected negative stock
   but Complete sale remains one action with no acknowledgement selector or extra screen. Confirm
   the completed detail shows the shortage note and inventory becomes the displayed negative value.
11. Repeat scanning and checkout with the physical barcode scanner. Confirm scanning stays focused
   and all checkout controls remain reachable.
12. Disconnect internet access while Django and PostgreSQL remain running, refresh, and complete a
    test sale. Confirm styling and checkout still work.

## 4. Completion decision

Planning, implementation, migration, and automated verification pass. Milestone 4 remains pending
only the revised user frontend acceptance. The POS is not ready for live shop use until returns,
backup/recovery, and deployment work are complete.
