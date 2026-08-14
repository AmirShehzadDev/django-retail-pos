# Milestone 6 - Daily Summary and Audit Trail Evidence

**Status:** Implementation complete; user frontend acceptance pending

**Automated verification:** 2026-08-07

## 1. Delivered

- Added owner/admin-only **Reports** navigation and Home action; cashiers have no report access.
- Added a selected-day summary using exact `Asia/Karachi` boundaries and immutable payment-event
  dates.
- Added gross sales, return refunds, void refunds, net sales, completed order count, cash collected,
  cash refunded, non-zero-change order count, and algebraic signed-change total.
- Added explicit cash reconciliation: cash collected minus signed change equals gross sales; after
  refunds it equals net sales/net cash movement.
- Assigned later returns and voids to their actual correction dates without rewriting original-sale
  dates.
- Added current negative-stock and pending cashier-created-product counts with direct links to the
  existing filtered Products & Stock workspace.
- Added a newest-first, 50-row paginated audit trail with target, date range, actor, action, and
  target-type filters.
- Added same-shop actor choices, invalid-range handling, preserved pagination filters, and escaped
  expandable before/after payloads.
- Kept reports GET-only, read-only, server-rendered, and fully offline with no new runtime
  dependency or database migration.

## 2. Automated evidence

All gates passed against Dockerized PostgreSQL 16.14:

- complete project suite: **341 tests passed**;
- focused Milestone 6 report suite: **9 tests passed**;
- core application suite: **44 tests passed**;
- Node UI suite: **14 tests passed**;
- `python manage.py check`: no issues;
- `python manage.py makemigrations --check --dry-run`: no changes detected;
- `ruff check .`: passed;
- `ruff format --check .`: all **168 Python files** formatted;
- all local JavaScript syntax checks: passed;
- Tailwind 4.3.3 local build: passed;
- `python manage.py collectstatic --noinput`: passed;
- `python -m pip check`: no broken requirements;
- `python manage.py reconcile_inventory`: **7 products reconciled**;
- `git diff --check`: passed; and
- `docker compose ps`: PostgreSQL container healthy.

Coverage includes exact Decimal aggregation, zero days, positive/negative signed change, later-day
returns and voids, Karachi boundaries, shop isolation, current review counts, manager/cashier and
GET-only boundaries, audit filters, foreign-actor rejection, newest-first pagination, filter
preservation, payload escaping, and complete prior-milestone regression.

## 3. Required user frontend acceptance

Codex did not perform browser, visual, responsive, keyboard, or offline frontend verification.

1. Sign in as owner/admin and open **Reports** from both the top navigation and Home. Confirm the
   page defaults to today's Pakistan date and Previous, Next, date picker, **Audit trail**, and
   **View the day's orders** work.
2. Note the starting figures. Complete two controlled sales: one with positive Change and one with
   negative Change. Confirm Gross sales and Completed orders increase by both sales, Cash collected
   increases by the two tendered amounts, Non-zero-change orders increases by two, and Signed
   change is their algebraic sum.
3. Return one or more items from the first sale and void the second sale. Confirm Returns shows the
   exact returned-line refund, Voids shows the second sale total, Cash refunded is their sum, and
   Net sales is Gross minus Returns minus Voids.
4. Check the displayed reconciliation equations. Confirm Cash collected minus Signed change equals
   Gross sales and subtracting Cash refunded equals Net sales.
5. Select a different date. Confirm sales remain on their completion dates while any later return
   or void appears only on the date the correction was processed. Select a day with no activity and
   confirm all daily figures show zero.
6. In **Current review alerts**, open Negative stock and Cashier-created products. Confirm each link
   opens **Products & Stock** with the correct filter selected and the displayed report count agrees
   with the filtered result count.
7. Open **Audit trail**. Filter the controlled operations by date, actor, Return/Voided action,
   Order target type, and order number. Confirm rows are newest first and **View changes** shows
   readable actor/action/target/time and relevant values.
8. Sign in as cashier. Confirm Reports is absent from navigation/Home and direct access to
   `/reports/` and `/reports/audit/` is denied.
9. At the shop monitor resolution and 100% zoom, confirm metric cards, filters, audit rows/details,
   and pagination remain readable and keyboard reachable without overlap.
10. Disconnect the internet while leaving the local application and Docker database running.
    Reload both report pages and repeat one date/audit filter; confirm they still work and retain
    styling.

## 4. Release decision

Automated acceptance criteria pass. Milestone 6 is ready for user frontend/offline verification.
Do not mark it user-accepted until the required checklist passes or any reported issue is fixed.
