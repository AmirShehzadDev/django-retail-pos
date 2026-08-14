# Milestone 6 Development Tasks - Daily Summary and Audit Trail

**Status:** Complete

**Inputs:** Approved `docs/milestones/m6-reporting-audit/feature-spec.md` v1.0 and `docs/milestones/m6-reporting-audit/technical-design.md` v1.0

## Task 1 - Add report policy and forms

- Add manager-only report policy.
- Add daily date and audit filter forms with same-shop actor choices and range validation.

**Acceptance:** owner/admin pass, cashier fails, invalid/foreign filter values cannot broaden scope.

## Task 2 - Implement exact reporting queries

- Add local-day boundary helper.
- Aggregate receipt, return-refund, void-refund, cash, change, and count metrics from payments.
- Calculate exact reconciliation fields with Decimal arithmetic.
- Count current negative-stock and pending quick-created products.
- Add filtered same-shop audit queryset.

**Acceptance:** empty, normal, signed-change, later-correction, timezone-boundary, and cross-shop
cases reconcile exactly.

## Task 3 - Build daily summary page

- Add GET-only URL/view and selected/previous/next dates.
- Render compact metric cards, reconciliation guidance, signed-change emphasis, and empty states.
- Link review counts to existing Products & Stock filters and link to Audit trail.

**Acceptance:** manager can understand one day's sales/cash/corrections and reach both review queues;
cashier/direct POST access is denied.

## Task 4 - Build filtered audit history

- Add GET-only URL/view, form validation, 50-row pagination, and query preservation.
- Render actor/action/target/time and escaped structured before/after values.

**Acceptance:** filtering and pagination stay same-shop, newest-first, readable, and safe; invalid
filters show errors without misleading rows.

## Task 5 - Integrate navigation and local styling

- Add manager-only Reports links to primary navigation and Home.
- Rebuild local Tailwind CSS and collect static assets.

**Acceptance:** managers have a clear route into reports, cashiers do not, and no internet asset is
required.

## Task 6 - Automated verification and evidence

- Add focused query, permission, view, template, filter, timezone, and safety tests.
- Run focused tests, full project regression, Django/migration/Ruff/Node/Tailwind/static/dependency
  gates, and `git diff --check`.
- Record completion evidence and required manual frontend/offline checklist.

**Acceptance:** all Milestone 6 and prior milestone behavior passes, completion evidence is
recorded, and the user receives the final manual verification checklist.

## Planning review record

Reviewed on 2026-08-07 against `docs/product/mvp-requirements.md` v1.7, `docs/product/roadmap.md` v1.6,
`docs/architecture/technical-design.md` v0.8, accepted Milestones 0-5, and the current codebase.

Findings resolved before implementation:

1. **Historical-status ambiguity:** Current order status cannot assign a later return/void to the
   correct reporting date. All money is therefore classified by immutable payment event timestamp.
2. **Cash terminology ambiguity:** Cash collected is explicitly cash tendered (`cash_received`),
   while signed change stays separate. The page shows the exact reconciliation to gross/net sales.
3. **Duplicate review UI risk:** Negative-stock and quick-create review filters already exist in the
   unified Products & Stock workspace. Milestone 6 adds current counts and filtered links only.
4. **Audit payload safety:** Existing sensitive-key rejection remains enforced; JSON display is
   server formatted and template escaped, never marked safe.
5. **Shop leakage risk:** Every query begins with actor shop scope and audit actor choices are
   same-shop. Forged choices fail validation.
6. **Date-boundary risk:** Every report/audit date uses half-open `Asia/Karachi` aware boundaries;
   no UTC-date truncation is used.
7. **Scope growth:** Exports, charts, profit, drawer sessions, new audit actions, and duplicated
   product management remain excluded.

Review result: the specification, technical design, tasks, project requirements, and implemented
data model are mutually consistent and implementation-ready.
