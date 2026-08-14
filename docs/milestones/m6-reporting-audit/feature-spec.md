# Milestone 6 Feature Specification - Daily Summary and Audit Trail

**Status:** Approved for implementation

**Version:** 1.0

**Prepared:** 2026-08-07

**Inputs:** `docs/product/mvp-requirements.md` v1.7, `docs/product/roadmap.md` v1.6, accepted Milestone 5
returns/voids, and existing product review filters

## 1. Objective

Give the owner and admins a trustworthy, compact view of one business day's sales and cash events,
plus a searchable audit trail of security-sensitive and exceptional operations. Reporting is
read-only and uses existing immutable sales, refund, and audit records.

## 2. Actors and permissions

### Owner and admin

- View the daily summary for their own shop.
- Choose any business date.
- Open the shop's audit trail and filter it.
- Follow review links to negative-stock and cashier-created products needing review.

### Cashier

- Cannot view the daily summary or audit trail.
- Does not see report navigation or home-page actions.

All queries are restricted to the authenticated user's shop. Inactive or unauthenticated users
have no access through the normal authentication rules.

## 3. Daily summary date and accounting rules

- The default date is today in the shop timezone, `Asia/Karachi`.
- A date picker and previous/next-day links select one complete local calendar day.
- Local midnight boundaries are converted to timezone-aware instants before database filtering.
- Money remains fixed-precision PKR with two decimal places.
- Monetary events belong to the date their immutable `Payment.processed_at` occurred.
- A return or void processed later is reported on the later correction date, not rewritten into the
  original sale date.

The summary calculates:

- **Gross sales:** sum of receipt payment amounts processed that day, before later corrections.
- **Returns:** sum of refund payments linked to customer returns processed that day.
- **Voids:** sum of refund payments linked to administrative voids processed that day.
- **Net sales:** `gross sales - returns - voids`.
- **Completed orders:** count of receipt payments/original orders processed that day.
- **Cash collected:** sum of original receipt `cash_received` values (cash tendered).
- **Cash refunded:** `returns + voids`.
- **Non-zero-change orders:** receipt count where signed change is not zero.
- **Signed change total:** algebraic sum of receipt `change_given`; positive and negative values are
  preserved rather than converted to absolute values.

The existing invariant `gross sales = cash collected - signed change total` is explained on the
page. Therefore `net sales = cash collected - signed change total - cash refunded`.

Days with no activity display zero for every metric without errors. Zero-price sales and refunds
remain valid events and counts.

## 4. Review alerts

The daily summary also shows current operational counts, clearly labelled as current rather than
historical-to-date:

- products whose `stock_on_hand` is below zero; and
- products created through POS quick-create that still have `needs_review=True`.

Each count links to the existing role-protected **Products & Stock** workspace with the matching
`Negative stock` or `Needs review` filter applied. Milestone 6 does not duplicate catalog editing or
inventory controls on the report page.

## 5. Audit trail

The audit page lists the newest events first with 50 events per page. Each row shows:

- shop-local date/time;
- actor name/username and current role;
- human-readable action;
- target type and identifier; and
- relevant before/after values when recorded.

Filters are:

- target identifier search;
- local From and To dates, inclusive;
- actor from the same shop;
- action; and
- target type.

Filters are optional, combine with AND semantics, survive pagination, and cannot reveal another
shop's actors or events. Invalid date ranges show a validation error and no misleading result set.

The trail includes the existing approved audit vocabulary: account/profile/role/active/password
changes, shop-name changes, product price changes, inventory adjustments, POS quick-created
products, stock-shortage acknowledgements, draft takeovers, returns, and voids. Legacy audit rows
remain visible if present. Clearing a draft and closing an empty tab remain deliberately unaudited.

Before/after payloads are displayed as escaped, read-only structured text. Existing sensitive-key
rejection remains authoritative; the report never marks audit data as trusted HTML.

## 6. Navigation and presentation

- Managers see one **Reports** link in primary navigation and one Reports action on Home.
- The Reports page opens the daily summary and provides a visible **Audit trail** action.
- The summary uses compact metric cards, emphasizes Net sales, and visually distinguishes return
  and void deductions.
- Signed change uses positive/negative/zero styling consistent with Orders.
- A visible explanation differentiates selected-day metrics from current product-review counts.
- The implementation is server-rendered and requires no new JavaScript.

## 7. Data effects and integrity

Both pages are read-only GET endpoints. They create, update, or delete no sales, payments, products,
inventory movements, users, or audit events. They do not create an audit event merely for viewing a
report. Totals are derived on request from committed database rows.

## 8. Validation and edge cases

- Missing date selects the current shop-local date.
- An invalid date or From-after-To audit range produces visible form errors.
- Unknown actor/action/target filter values fail validation rather than bypassing scope.
- An actor from another shop cannot be selected through a forged query string.
- Refund classification requires exactly one return or void source, consistent with existing
  payment constraints.
- Current order status is not used to move historical money between days.
- Pagination outside the valid range uses Django's safe first/last-page behavior.
- Large valid Decimal totals remain exact; Python/JavaScript floating point is not used.

## 9. Explicit exclusions

- Charts, trends, comparisons, forecasts, profit/cost/margin, tax, discounts, and payment methods
  other than cash.
- CSV/PDF export, printing, emailing, scheduled reports, shift/cash-drawer sessions, and manual
  opening/closing cash counts.
- Editing/deleting audit events or corrections.
- A new duplicate product-review screen.
- Login-success/login-failure tracking, since the approved MVP requires audit of account changes,
  not authentication-session logging.

## 10. Acceptance criteria

1. Owner/admin can view same-shop daily summary and audit pages; cashier and cross-shop data cannot.
2. Default and selected dates use exact `Asia/Karachi` day boundaries.
3. Gross, return, void, net, order-count, collected/refunded cash, non-zero-change count, and signed
   change figures reconcile with immutable payments.
4. A later-date return or void affects only the correction date's refund/net figures.
5. Positive and negative signed change aggregate algebraically and remain visually distinguishable.
6. Empty days show exact zero values.
7. Current negative-stock and pending quick-created-product counts link to the correct existing
   filtered workspace.
8. Audit rows show actor, action, target, local time, and escaped relevant changes newest first.
9. Audit filters, validation, same-shop choices, pagination, and query preservation work together.
10. Reports are GET-only, read-only, local/offline capable, and introduce no runtime web dependency.
11. Automated report/query/view/template/permission/regression checks pass.
12. The user manually verifies the summary layout, filter usability, signed-change emphasis, review
    links, audit readability, responsive behavior, and offline access.
