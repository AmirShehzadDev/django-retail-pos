# Milestone 6 Technical Design - Daily Summary and Audit Trail

**Status:** Planning reviewed; implementation-ready

**Version:** 1.0

**Prepared:** 2026-08-07

**Input:** Approved `docs/milestones/m6-reporting-audit/feature-spec.md` v1.0

## 1. Scope and architecture

Add a read-only reporting layer to the existing `core` app. No new database model or migration is
required. A query module derives daily figures from immutable `Payment` rows, counts current review
products, and provides a shop-scoped audit queryset. Thin views handle forms, pagination, and
templates.

URLs remain under the core namespace:

- `GET /reports/` - daily summary;
- `GET /reports/audit/` - filtered audit history.

Both views use `login_required`, `never_cache`, `require_GET`, and a manager policy guard.

## 2. Permissions and isolation

Create `apps.core.policies.can_view_reports(actor)`. It returns true only for an authenticated,
active owner/admin with a shop. Every report query takes the actor and begins with
`shop_id=actor.shop_id`; request-supplied shop identifiers do not exist.

Audit actor choices are built exclusively from active and inactive users belonging to the actor's
shop so historical actors remain filterable. A forged foreign actor choice fails form validation.

## 3. Forms

Add to `apps.core.forms`:

- `DailySummaryForm` with optional HTML date field. The view supplies the shop-local current date
  when missing; invalid submitted values render errors and fall back to today without querying a
  misleading date.
- `AuditFilterForm` with optional target query, From, To, actor, action, and target-type fields.
  Actor choices are injected from the shop. `clean()` rejects From after To.

Fields use existing local Tailwind-compatible control classes. Unknown choices are normal Django
validation errors.

## 4. Reporting queries

Create `apps.core.reporting`.

### 4.1 Local boundaries

`business_day_bounds(shop, date)` builds `[start, end)` from local midnight in
`ZoneInfo(shop.timezone)` using timezone-aware datetimes. The same helper applies to payment and
audit filters.

### 4.2 Daily summary

`daily_summary(actor, business_date)` returns a frozen data object containing the selected date and
all Decimal/count metrics.

Receipt query:

- shop-scoped `Payment` rows;
- `direction=RECEIPT`, non-null order;
- `processed_at >= start`, `< end`.

It aggregates amount, cash received, signed change, and receipt count, plus a filtered non-zero
change count. Refund queries share the same date range and direction, splitting return-source and
void-source payments. Existing payment source constraints guarantee exclusive classification.

`net_sales`, `cash_refunded`, and the two reconciliation expressions are calculated with Decimal
arithmetic. Missing aggregates normalize to `Decimal("0.00")`.

Current review counts query shop-scoped `Product` rows for `stock_on_hand < 0` and for
`creation_source=POS_QUICK_CREATE, needs_review=True`.

### 4.3 Audit history

`audit_events(actor, filters)` starts with same-shop `AuditEvent.select_related("actor")`, applies
validated target/date/actor/action/type filters, and retains model ordering
`-created_at, -id`. Date filters use inclusive local dates via half-open aware boundaries.

The view paginates at 50 rows. It attaches JSON text generated with `json.dumps(...,
ensure_ascii=False, indent=2, sort_keys=True, default=str)` for non-empty before/after dictionaries.
Templates autoescape these strings inside `<pre>` elements.

## 5. Views and templates

### Daily summary

`daily_summary_view` validates the date form, defaults/falls back to shop-local today, loads the
summary and current review counts, and renders `core/daily_summary.html`. Previous/next dates are
derived with `timedelta(days=1)`. Order and product links use existing routes and query parameters.

### Audit history

`audit_history` validates filters. Valid filters query/paginate events. Invalid filters render no
events and form errors. The view removes `page` when constructing the preserved query string.

`core/audit_history.html` renders a compact filter bar, accessible table/cards, expandable escaped
payload details, empty state, and pagination.

`templates/base.html` and `templates/core/home.html` expose Reports only to owner/admin. The daily
summary includes a direct Audit trail action.

No custom JavaScript is required. Tailwind is rebuilt because new template classes must be present
in compiled local CSS.

## 6. Data and transaction behavior

No write transaction is opened and no locks are required. PostgreSQL statement-level consistency
is sufficient for each aggregate/query; a checkout committing between separate page queries may be
visible after reload. The page does not claim to be a frozen accounting close.

No audit event is written for viewing reports. Existing immutable payment, correction, movement,
and audit constraints remain unchanged.

## 7. Tests

Add Milestone 6 tests covering:

- exact Decimal daily aggregation and reconciliation;
- positive/negative change and zero-activity dates;
- later-day return and void allocation;
- `Asia/Karachi` midnight boundaries;
- current review counts and filtered links;
- owner/admin/cashier/anonymous access and hidden navigation;
- same-shop isolation and forged actor filters;
- audit action/actor/target/date filters, invalid ranges, ordering, pagination, and query retention;
- escaped payload display and readable empty states;
- GET-only behavior, Django checks, Tailwind build, and full regression.

## 8. Deployment impact

There is no migration or new runtime dependency. Deployment requires updated Python/templates,
rebuilt `static/css/app.css`, and normal static collection. All functionality remains available on
the local offline server.
