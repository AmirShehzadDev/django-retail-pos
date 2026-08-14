# Milestone 5 Development Tasks - Returns and Voids

**Status:** Complete

**Inputs:** Approved `docs/milestones/m5-returns-voids/feature-spec.md` v1.3 and `docs/milestones/m5-returns-voids/technical-design.md` v1.3

## Task 1 - Add correction schema and migrations

- Extend order statuses and completed-like constraints.
- Add immutable return, return-item, and void models with request-token constraints.
- Generalize payments to receipt/refund with exactly one source.
- Add inventory return/void source links and sign/source constraints.
- Add return numbering and audit actions; seed sequences for existing/new shops.

**Acceptance:** migrations apply to an existing database; legacy sales remain unchanged; invalid
source combinations, duplicate operations, mutable corrections, and invalid money/quantity states
are rejected.

## Task 2 - Implement correction policies and read calculations

- Add return/void permission policies.
- Define shared completed-like statuses.
- Calculate sold, returned, and remaining quantities from committed records.
- Load related corrections and total refunded efficiently and within shop scope.

**Acceptance:** all roles can read same-shop completed-like orders; only eligible roles/states expose
their mutation; cross-shop and inconsistent states are rejected.

## Task 3 - Implement transactional return service

- Lock/revalidate actor, order, prior corrections, lines, and products deterministically.
- Normalize the optional return reason and validate selections, remaining quantities, receipt,
  snapshots, and shop relationships.
- Allocate return number and create immutable return, lines, refund, inventory, status, and audit.
- Implement request-token idempotency and all-or-nothing rollback.

**Acceptance:** partial/full and restock/damaged/mixed returns reconcile exactly; concurrency,
retry, stale input, and injected failures cannot duplicate or partially commit effects.

## Task 4 - Implement transactional void service

- Require owner/admin, a pristine completed order, and a reason.
- Create one void, exact refund, full stock reversal, status change, and audit atomically.
- Implement retry safety and mutual exclusion with returns.

**Acceptance:** cashier/direct/cross-shop voids fail; eligible voids reconcile exactly; repeated,
stale, returned, or already-voided operations have no new effects.

## Task 5 - Enhance order lookup and detail read model

- Include completed, partially returned, returned, and voided orders.
- Add date, cashier, status, exact amount/product/barcode/order-number, and change filters.
- Use `Asia/Karachi` local-date boundaries.
- Present original payment and all linked correction/refund/stock details.

**Acceptance:** approved lookup paths find only same-shop orders; pagination/query preservation and
newest-first ordering remain correct; original sale facts never change.

## Task 6 - Build server-rendered return and void workflows

- Add forms/formset, URLs, policies, GET/POST views, CSRF/method handling, and redirect fallback.
- Render return quantities, Restock-default dispositions with no empty choice, optional
  reason/refund, and void reason/refund confirmation.
- Return useful bound errors and refreshed persisted state.

**Acceptance:** complete return and void workflows work without JavaScript; cancellations/invalid
submissions create no records; server never trusts browser prices, balances, actor, or refund.

## Task 7 - Add progressive dialog enhancement

- Add shared dialog/form partials and order-detail fragment response.
- Add local JavaScript for modal loading, bulk helpers, integer-minor-unit refund preview,
  accessible confirmation, invalid response replacement, toast, and detail refresh.
- Keep generated CSS/local assets and existing navigation behavior.

**Acceptance:** enhanced success stays on the order detail, invalid data remains editable, keyboard
controls and buttons are present, and full fallback remains usable when JavaScript is disabled.

## Task 8 - Automated verification and evidence

- Add focused model, service, policy, form, view, filter, template, JavaScript-contract,
  concurrency/idempotency, rollback, and migration tests.
- Run Django checks, migration drift check, focused tests, and the complete PostgreSQL Docker suite.
- Update milestone status, completion evidence, README/project references, and commit with the
  configured project identity and a short message.

**Acceptance:** all automated checks pass; milestone evidence maps to feature acceptance and exit
criteria; user receives the required frontend/offline/manual cash-workflow checklist.

## Dependencies and order

Tasks execute in numeric order. Schema precedes services; policies/read calculations precede views;
fallback workflow precedes progressive enhancement; full verification follows implementation.

## Planning review record

Review pass 1 found payment source ambiguity, missing partial-return retry identity, inventory
source collision with sale movements, and undefined local-date boundaries. Those findings were
fixed in `docs/milestones/m5-returns-voids/technical-design.md` v1.1 and reflected in Tasks 1, 3, 5, and 8.

Review pass 2 compared all three Milestone 5 documents with `docs/product/mvp-requirements.md`, `docs/product/roadmap.md`,
`docs/architecture/technical-design.md`, completed Milestones 0-4.3, and the current models/services/views. No
remaining contradiction, speculative Milestone 6 scope, unsafe assumption, missing acceptance
coverage, or dependency-order issue was found. Planning is implementation-ready.
