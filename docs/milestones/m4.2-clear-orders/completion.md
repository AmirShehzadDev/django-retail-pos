# Milestone 4.2 - Clear Order and Close Tab Evidence

**Status:** Complete; user frontend acceptance confirmed on 2026-08-06

**Automated verification:** 2026-08-06

## 1. Delivered

- Populated editable drafts show **Clear order** instead of Discard order.
- Clear order opens an in-POS native dialog with item count, PKR total, **Keep order**, and
  **Clear order**.
- `Enter` confirms from the dialog's default state; `Escape` and **Keep order** cancel without a
  request or data change.
- Successful clear deletes every draft line, resets subtotal to zero, increments the version, and
  retains the same draft ID/slot/current cashier.
- Eligible empty drafts show **Close tab**, which immediately deletes only that tab and selects the
  next higher slot or highest lower slot.
- The only active tab cannot close; read-only drafts expose neither action.
- Enhanced clear/close stays on POS, replaces existing fragments, updates URL/version, shows a
  compact dismissible toast, and restores scanner focus.
- A no-JavaScript Clear order fallback provides the same Keep/Clear confirmation and redirects back
  to the retained draft; Close tab uses its normal protected POST fallback.
- The active discard view, route, reason form, service, policy, and template were removed.
- Clear/close creates no discarded order, audit event, payment, inventory movement, stock change,
  or replacement draft.
- Legacy `DISCARDED` schema, migrations, rows, and audit vocabulary remain compatible and inert.

## 2. Automated evidence

All gates passed against Dockerized PostgreSQL 16.14:

- `python manage.py test --keepdb`: **308 tests passed**.
- `python manage.py test apps.sales --keepdb`: **149 tests passed**.
- focused concurrency suite: **12 tests passed**.
- `python manage.py check`: no issues.
- `python manage.py makemigrations --check --dry-run`: no changes detected.
- `ruff check .`: passed.
- `ruff format --check .`: all 149 Python files formatted.
- `node --check static/js/pos.js`: passed.
- `node --test static/js/pos.test.js`: **7 tests passed**.
- `npm ci`: pinned dependencies installed; audit reported zero vulnerabilities.
- `npm run css:build`: Tailwind 4.3.3 build passed and generated local CSS.
- `python -m pip check`: no broken requirements.
- `python manage.py collectstatic --noinput`: passed.
- `git diff --check`: passed.

Coverage includes exact data effects, no-side-effect assertions, permissions/shop/terminal scope,
CSRF/method boundaries, stale versions, last-tab protection, deterministic selection, rollback,
clear-versus-edit concurrency, enhanced/fallback responses, conditional templates, legacy schema
compatibility, and keyboard-decision logic.

## 3. Required user frontend acceptance

**Result:** Passed and confirmed by the user on 2026-08-06.

Codex did not perform browser, visual, focus, responsive, or hardware-scanner verification.

1. Start Docker/database and Django, then sign in as the cashier and open **POS** at 1366x768 and
   100% browser zoom.
2. Add at least two product lines. Click **Clear order** and confirm the dialog stays over the POS,
   shows the correct line count/total, and displays both **Keep order** and **Clear order**.
3. Click **Keep order**. Confirm the dialog closes and every product/quantity/total remains.
4. Reopen it and press `Escape`. Confirm the same unchanged result, then scan/type a barcode to
   confirm scanner focus is usable.
5. Reopen it and press `Enter`. Confirm the cart clears in place, the same order tab remains with
   PKR 0.00, a dismissible success toast appears, and scanning can immediately start a new basket.
6. With only one empty tab, confirm **Close tab** is absent. Create a second empty tab, select it,
   click **Close tab**, and confirm there is no dialog, that tab disappears, another existing tab is
   selected, and a dismissible success toast appears.
7. Leave a draft assigned to one cashier, sign in as another cashier, and confirm Clear/Close is not
   offered on the read-only draft. Resume it and confirm the appropriate action then appears.
8. Temporarily disable JavaScript, open a populated order, and select **Clear order**. Confirm the
   fallback page offers **Keep order** and **Clear order**, Keep changes nothing, and Clear returns to
   the same now-empty POS tab. Re-enable JavaScript afterward.
9. Compare product stock before and after one clear and one close; confirm it is unchanged.

## 4. Optional confidence check

- Disconnect the computer from the internet and repeat one clear and close flow with the local
  server running. No asset or action should require internet access.

## 5. Exclusions retained

- No migration or cleanup of historical discarded rows.
- No undo/restore, reason, PIN, approval, fraud alert, or discard report.
- No change to checkout, completed orders, payments, returns, voids, tax, or receipts.
