# Milestone 5 - Returns and Voids Evidence

**Status:** Complete and user accepted

**Automated verification:** 2026-08-07

## 1. Delivered

- Added immutable linked partial/full returns for cashier, admin, and owner, with permanent
  `RET-000001` numbering, original-price refund snapshots, optional reasons/notes, and retry-safe
  request tokens.
- Added per-line Restock and Damaged/do-not-restock decisions, with Restock selected by default and
  no empty disposition choice. Restock creates one positive return movement and updates the locked
  product balance; Damaged changes no sellable stock.
- Added owner/admin-only whole-order voids with required reason, one exact cash refund, full stock
  reversal, and strict exclusion after any return. Cashiers cannot void.
- Preserved the original order, item snapshots, sale receipt, Cash received, signed Change, and sale
  movements. Corrections add immutable refund payments and correction records rather than editing
  the sale.
- Added completed-like order statuses: Completed, Partially returned, Returned, and Voided.
- Added transactional locking, server-derived remaining quantities/refunds/status, operation-level
  idempotency, database source/quantity/money constraints, rollback, audit events, and return
  sequence bootstrap/migration support.
- Expanded Orders lookup with product/barcode/order/amount search and date, completing-cashier,
  status, and non-zero-change filters using shop-local date boundaries.
- Expanded order detail with sold/returned/remaining quantities, total refunded, related returns,
  dispositions, refund information, void information, and role/state-appropriate actions.
- Added server-rendered no-JavaScript return/void fallbacks and local progressive dialogs with bulk
  return/disposition helpers, refund preview, confirmation, bound validation, toast, and in-place
  detail refresh.

## 2. Automated evidence

The milestone baseline and latest return-workflow maintenance gates passed against Dockerized
PostgreSQL 16.14:

- milestone baseline complete project suite: **330 tests passed**;
- latest sales regression suite: **164 tests passed**;
- focused Milestone 5 correction suite: **13 tests passed**;
- focused PostgreSQL correction-race suite: **2 tests passed**;
- `python manage.py check`: no issues;
- `python manage.py makemigrations --check --dry-run`: no changes detected;
- `ruff check .`: passed;
- `ruff format --check .`: all **161 Python files** formatted;
- correction JavaScript syntax check: passed;
- Node UI suite: **14 tests passed**;
- optional-return-reason migration applied to the working database;
- Tailwind 4.3.3 local build: passed;
- `python manage.py collectstatic --noinput`: passed;
- `python -m pip check`: no broken requirements;
- `git diff --check`: passed; and
- `docker compose ps`: PostgreSQL container healthy.

Coverage includes historical snapshot refunds, partial/full and mixed-disposition returns,
remaining-quantity enforcement, return numbering, status derivation, retry idempotency, immutable
records, optional normalized return reasons, mandatory void reasons, exact quantity-based refund
payments and previews, restock/damaged stock effects, owner voids, cashier denial, return/void mutual
exclusion, fallback and enhanced HTTP workflows, order lookup filters, database constraints, and
complete prior-milestone regression.

## 3. Required user frontend acceptance

Codex did not perform browser, visual, responsive, keyboard/focus, physical cash, scanner, or
offline frontend verification.

1. Start the local app and make a completed two-product cash sale with quantities greater than one.
   Note its original total, Cash received, signed Change, and both stock balances.
2. As cashier, open **Orders**, find the sale by order number, product/barcode, exact amount, date,
   cashier, and Completed status. Confirm each filter finds the same order and its Change remains
   highlighted.
3. Open the order, select **Return items**, choose one unit as **Restock** and one as
   **Damaged / do not restock**, leave the optional reason blank, and confirm. Verify the cash
   refund updates as each quantity changes, equals the original unit price multiplied by each
   returned quantity, stays on the detail page, shows a dismissible toast, assigns a `RET-...`
   number, and changes status to **Partially returned**.
4. Verify the Restock product increased by exactly one, the Damaged product did not change, and the
   original sale total, Cash received, signed Change, cashier, date, and item prices remain unchanged.
5. Return all remaining quantities using **Return all remaining**, exercise both bulk disposition
   buttons, confirm the exact refund, and verify status becomes **Returned** with zero remaining.
   Confirm another return and Void action are unavailable.
6. Complete a new sale. As cashier, confirm **Void order** is absent and its direct URL is denied.
   As owner/admin, void it with a reason; verify the exact sale-total refund, **Voided** status, all
   quantities restored once, original payment/history unchanged, and Return action absent.
7. On a third sale, make a partial return, then sign in as owner/admin and confirm Void is no longer
   available. Double-click/re-submit a correction where practical and verify only one refund,
   return/void record, and stock effect appears.
8. Submit a return with all quantities zero, a quantity above remaining, and a selected line
   without a disposition. Confirm clear validation and no status, refund, number, audit, or stock
   change. Separately confirm a blank return reason succeeds and a blank void reason is rejected.
9. Disable JavaScript temporarily. Complete one valid return and one manager void through the
   full-page forms, confirm redirects return to the updated order detail, then re-enable JavaScript.
10. At the shop's normal monitor resolution and 100% zoom, verify dialogs are not cut off, all
    controls are keyboard reachable, Escape safely cancels, visible Cancel/Complete buttons work,
    and no important order detail overlaps.

## 4. Optional confidence checks

- Disconnect the internet while keeping the local server and Docker database running, then repeat
  one return lookup and correction. All assets and operations should continue working.
- Have two logged-in computers attempt corrections against the same original order at nearly the
  same time. One valid operation should commit; stale quantities/state must not create a second
  invalid refund or stock reversal.

## 5. Exclusions retained

- No unlinked returns, exchanges, store credit, custom refund price, restocking fee, partial void,
  cashier void, card refund, customer account, return window, receipt printing, tax, or damaged-stock
  location.
- Daily summaries and the general manager audit screen remain Milestone 6.
