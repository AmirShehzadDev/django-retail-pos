# Milestone 4.1 - Compact POS Workspace Redesign Evidence

**Status:** Implementation and automated verification complete; user frontend acceptance pending

**Automated verification:** 2026-08-06

> **Follow-on refinement:** This evidence records the completed M4.1 build. The approved
> [Milestone 4.2 specification](../m4.2-clear-orders/feature-spec.md) changes the active-order removal interaction;
> its implementation and verification are intentionally separate.

## 1. Delivered

- Dedicated compact POS shell; the normal application header remains unchanged on non-POS pages.
- One toolbar containing shop/terminal identity, three compact order tabs, New order, Orders,
  Products, cashier identity, and Exit POS.
- Bounded desktop order/catalogue geometry of approximately 65/35 with internal content scrolling.
- Dense divider-based cart rows with unit price, always-visible minus/current/plus, line total, and
  Remove; no Update button.
- Fixed compact checkout dock with only Total, Cash received, signed Change, and Complete sale.
- Enhanced checkout remains on POS, selects the fresh same-slot order, refreshes stock/tabs, shows
  order/total/Change confirmation, and restores scanner focus.
- Fixed three-row Recent sales footer with newest same-shop paid orders, local time, total,
  signed/coloured Change, immutable-detail links, and a separate inset bordered panel below the
  catalogue scroll area.
- Structured enhanced checkout errors retain the draft without navigating; normal/no-JavaScript
  success retains the safe completed-detail redirect.
- Two-column, text-only catalogue tiles with whole-tile Add actions and read-only equivalents.
- Compact 12/14px normal typography with 18px maximum workspace identity and 24px Total/Change.
- Toast close controls dismiss immediately through a delegated handler, with a versioned local
  script URL to prevent a stale browser copy from retaining the defect.
- Existing CSRF, version, progressive enhancement, scanner, warning, permission, and checkout
  behavior preserved.

## 2. Automated evidence

| Check | Result |
|---|---|
| Mandatory planning-package review | Passed; implementation gate recorded |
| Focused POS UI contracts | 11 passed |
| Focused checkout/query/UI suite | 29 passed |
| Complete Sales suite | 146 passed |
| Complete PostgreSQL project suite | 305 passed in 316.834s |
| Local JavaScript | 8/8 passed, including completion messaging and safe dynamic toast insertion |
| Ruff and Django system check | Passed |
| Migration drift | No changes detected |
| Local Tailwind production build | Passed |
| Python/npm dependency checks | Passed; 0 npm vulnerabilities |
| Static collection | Passed |
| Final scope review | Checkout HTTP representation, bounded read query, templates/JS/tests/CSS only; atomic checkout service unchanged |

Expected permission, CSRF, not-found, conflict, validation, and service-unavailable messages in
test output are asserted failure paths, not failures.

## 3. Required user frontend acceptance

Codex did not perform browser, visual, responsive, scanner-hardware, focus, or offline checks.

### Start the application

```powershell
Set-Location C:\Projects\offline-retail-pos
docker compose up -d db
.\.venv\Scripts\Activate.ps1
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
```

### Checklist

1. At 1366x768 and 100% zoom, open POS. Confirm the normal site header is absent; the compact POS
   toolbar and checkout dock are fully visible without whole-page vertical scrolling.
2. Confirm the order pane is roughly 65% wide and catalogue roughly 35%. With enough cart lines and
   products to overflow, confirm only their inner lists scroll and the scanner, search, and checkout
   dock remain fixed.
3. Confirm the typography is noticeably smaller than before: ordinary content about 14px,
   secondary content 12px, and only Total/Change at 24px.
4. Open three orders. Confirm all tabs, totals, ownership dots, and New order behavior remain usable.
   Use Orders and Products, then return to POS. Confirm Exit POS opens Home without logging out.
5. Scan and add products. Confirm catalogue tiles form a two-column text-only grid and the full tile
   adds a product. Search, Clear, no-results, and inactive-product exclusion must still work.
6. Confirm each cart row shows name/barcode, unit price, quantity stepper, line total, and Remove.
   Plus/minus must save immediately, quantity-one minus must stay visible but disabled, and there
   must be no Update button.
7. Resume another cashier's order and confirm its initial view has no scanner, Add, quantity,
   Remove, cash input, or Complete sale controls. Confirm takeover restores editable controls.
8. Trigger a negative-stock warning and an inactive retained line. Confirm warnings remain compact
   and do not hide the checkout dock.
9. Keep two or three tabs open. Complete a sale with cash above Total. Confirm the browser stays on
   POS, the completed slot becomes a selected fresh empty order, the other drafts remain unchanged,
   catalogue stock refreshes, and scanner focus returns without a click.
10. Confirm the success toast contains the permanent order number, total, and `+` signed Change and
    can be closed. Repeat with cash below Total and confirm the negative Change is shown and the sale
    still completes without a second screen.
11. Confirm Recent sales is fixed below the product list, newest first, and never exceeds three
    rows. Verify positive Change is green with `+`, negative is red, zero is neutral, and View opens
    the correct immutable completed-order detail.
12. Submit an invalid cash value and confirm POS does not navigate, the draft remains populated, and
    an error is announced. Correct the value and confirm the same draft can then complete once.
13. Trigger another success and error toast. Confirm both float above the workspace, the cross works,
    and they do not move or cover the checkout dock or Recent sales.
14. Use the physical barcode scanner and keyboard workflow, then disconnect internet while Django
    and PostgreSQL remain running. Confirm focus/scanning, styling, search, cart changes, and checkout
    still work.

### Optional fallback confidence check

Disable JavaScript temporarily, complete a test sale, and confirm the traditional completed-order
detail redirect still works. Re-enable JavaScript and reload before continuing.

## 4. Completion decision

Planning, implementation, and automated verification are complete. M4.1 is pending only the user's
required frontend acceptance. The broader MVP is not ready for live shop use until its remaining
milestones, deployment, backup/recovery, and launch checks are complete.
