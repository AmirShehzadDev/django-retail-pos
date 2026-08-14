# Milestone 4.2 Development Tasks - Clear Order and Close Tab

**Status:** Complete; user frontend acceptance confirmed on 2026-08-06

**Version:** 1.1

**Prepared:** 2026-08-06

**Inputs:** Approved `docs/milestones/m4.2-clear-orders/feature-spec.md` v1.1 and approved
`docs/milestones/m4.2-clear-orders/technical-design.md` v1.1

## 1. Objective and implementation gate

Replace the active retained-discard path with two versioned POS mutations:

- clear every line from a populated draft while retaining the same draft/tab; and
- close an empty tab immediately when another active tab remains.

Neither operation records a reason, discarded order, audit event, payment, or inventory movement.
Legacy discard schema/data remains untouched.

> **Implementation gate:** M4.2-00 must review the complete planning package against the approved
> MVP, milestone plan, project design, completed behavior, and current code. Every finding must be
> corrected and the repeated review recorded as passed before M4.2-01 begins.

## 2. Ordered task summary

| ID | Task | Depends on | Verification focus |
|---|---|---|---|
| M4.2-00 | Mandatory whole-project planning review | Spec/design/tasks | Scope, consistency, feasibility, complete acceptance coverage |
| M4.2-01 | Replace discard domain path with clear/close services | M4.2-00 | Transactions, locks, versions, permissions, no audit/stock effects |
| M4.2-02 | Add clear/close HTTP endpoints and workspace context | M4.2-01 | POST/CSRF, enhanced and fallback responses, conditional eligibility |
| M4.2-03 | Build conditional POS actions and confirmation dialog | M4.2-02 | Labels, contents, no last-tab action, accessible markup |
| M4.2-04 | Add delegated dialog and keyboard enhancement | M4.2-03 | Enter clear, Escape/Keep cancel, fragment replacement, focus |
| M4.2-05 | Replace backend discard tests with clear/close coverage | M4.2-01, M4.2-02 | Data effects, validation, authorization, concurrency, regression |
| M4.2-06 | Add template and JavaScript automated coverage | M4.2-03, M4.2-04 | Conditional UI, dialog events, enhanced mutation behavior |
| M4.2-07 | Run full verification and record completion evidence | M4.2-05, M4.2-06 | Project suite, static build, drift/dependency checks, user checklist |

## 3. Detailed tasks

### M4.2-00 - Mandatory whole-project planning review

- Read the approved M4.2 specification and technical design completely.
- Reconcile them with `docs/product/mvp-requirements.md` v1.5, `docs/product/roadmap.md` v1.4,
  `docs/architecture/technical-design.md` v0.6, M3/M4/M4.1 historical documents, and the current code/tests.
- Check permission boundaries, terminology, no-audit behavior, transaction/lock ordering,
  optimistic versioning, last-tab invariant, progressive enhancement, and exclusions.
- Check that every acceptance criterion maps to an implementation task and automated or user-owned
  verification.
- Fix all findings in the appropriate planning document and repeat the review.
- Record the final result in section 6 before implementation begins.

**Complete when:** the repeated review passes with no unresolved findings and this document becomes
implementation-ready.

### M4.2-01 - Replace discard domain path with clear/close services

- Add `clear_draft(actor, draft_id, expected_version)` using the established actor, terminal,
  scoped-draft, edit-authority, item-lock, subtotal, and optimistic-version helpers.
- Require at least one current item; atomically delete all lines, set subtotal to zero, increment
  the same draft version, and return that draft.
- Add `close_empty_draft(actor, draft_id, expected_version)` with deterministic locks over the
  terminal's active drafts.
- Require an editable empty target, zero subtotal, exact version, and at least one other active
  draft; choose the approved deterministic remaining tab, delete only the target, and return the
  selection.
- Remove the active discard service and policy path so application code cannot create new retained
  discarded drafts. Keep legacy model fields/status/action choices and migrations unchanged.
- Do not call audit, inventory, payment, checkout, or replacement-draft services.

**Complete when:** focused service tests prove exact success effects, all rejection paths, rollback,
version increments, deterministic selection, and absence of audit/inventory/payment records.

### M4.2-02 - Add clear/close HTTP endpoints and workspace context

- Replace the discard URL/view with safe GET/POST `sales:draft_clear` and POST-only
  `sales:draft_close` routes.
- Use `VersionedActionForm`; no reason form or reason input remains in the active workflow.
- Extend workspace context with versioned clear/close forms and a server-derived
  `can_close_selected_tab` flag.
- Return the existing enhanced state envelope on success and structured current-state errors for
  conflicts/validation.
- Normal Clear order GET renders a server confirmation fallback; its success redirects to the
  retained draft. Normal close success redirects to the selected remaining draft.
- Preserve indistinguishable 404 scope handling, current-cashier enforcement, CSRF, active-user,
  terminal, and database-failure behavior.
- Remove the active discard confirmation view/template route.

**Complete when:** HTTP tests cover method, CSRF, permissions/scope, stale version, success redirects,
enhanced fragments, errors, and absence of a routable discard endpoint.

### M4.2-03 - Build conditional POS actions and confirmation dialog

- Render **Clear order** only for a populated editable selected draft.
- Render **Close tab** only for an editable empty selected draft when another active draft exists.
- Render no removal action for read-only drafts or the only active empty draft.
- Use a Clear order fallback link that JavaScript intercepts to open an in-panel native dialog;
  without JavaScript it opens the server-rendered confirmation page.
- Add the dialog containing the order label, current item count, PKR total,
  cannot-undo warning, **Keep order**, and **Clear order**.
- Mark the clear confirmation as the dialog's explicit/default submit action while keeping both
  buttons visible and keyboard-focusable.
- Submit Close tab immediately through the existing enhanced mutation mechanism.
- Preserve the compact no-page-scroll workspace and existing fragment boundaries.

**Complete when:** server-rendered template tests prove every conditional state, correct form action
and version, dialog content/semantics, and no discard reason/control.

### M4.2-04 - Add delegated dialog and keyboard enhancement

- Add delegated open/close behavior that survives draft-panel replacement.
- On open, show the dialog, establish the approved initial/default clear action, and prevent scanner
  shortcuts from consuming dialog keys.
- `Enter` submits Clear order; `Escape` and **Keep order** close without a request or mutation.
- Dispatch a compact success toast only for clear/close through an explicit form hook.
- Restore scanner focus after cancellation and after successful clear/close through the existing
  mutation success path.
- Keep double-submit protection and state/version replacement behavior.
- Add no external dependency or remote asset.

**Complete when:** Node tests prove the exported Enter/Escape decision behavior and existing
scanner/mutation helpers remain correct; Django template tests prove delegated hooks survive
fragment rendering. Hands-on dialog event wiring/focus remains user verification.

### M4.2-05 - Replace backend discard tests with clear/close coverage

- Replace historical active discard expectations in service, view, integration, form, policy, UI,
  signing, and concurrency tests.
- Retain schema/migration compatibility tests for legacy discarded rows and fields.
- Prove clear retains ID/slot/creator/current cashier/status, removes all items, sets zero subtotal,
  increments version, and creates no audit/payment/inventory data.
- Prove close deletes only the chosen empty draft, does not create a replacement, and selects the
  next higher slot or highest lower slot.
- Prove last-tab, non-empty-close, empty-clear, stale, takeover-required, wrong shop/terminal,
  inactive actor, malformed ID, repeated request, and transaction rollback behavior.
- Cover races with scan/quantity/takeover/checkout where the database test harness supports them.

**Complete when:** focused Sales tests pass and no active test expects creation of a new discarded
draft or discard audit event.

### M4.2-06 - Add template and JavaScript automated coverage

- Add template assertions for Clear order, Close tab, hidden last-tab action, dialog text, and
  removal of discard/reason wording.
- Extend local JavaScript tests for the pure dialog keyboard decision and add static/template
  assertions for the delegated open/cancel/toast hooks without adding a DOM-test dependency.
- Check enhanced success keeps the user on POS, updates tabs/panel/URL/version, announces success,
  and restores the intended focus.
- Keep actual appearance, responsive layout, hardware scanner behavior, and hands-on focus
  verification assigned to the user.

**Complete when:** template and Node tests pass without claiming manual frontend acceptance.

### M4.2-07 - Run full verification and record completion evidence

- Run Django system checks, the focused Sales suite, and the complete project suite.
- Run Ruff lint/format checks, migration drift check, JavaScript syntax/tests, Tailwind build,
  dependency check, and static collection.
- Run `git diff --check` and review the final diff for scope and accidental legacy-data removal.
- Create `docs/milestones/m4.2-clear-orders/completion.md` with delivered behavior, automated evidence, exclusions, and a concise
  required user frontend checklist.
- Commit with the configured Amir Shahzad Git identity and a short message.

**Complete when:** all automated gates pass, completion evidence is recorded, the worktree is clean,
and the user receives only the required manual frontend checklist at handoff.

## 4. Acceptance traceability

| Feature acceptance | Implementation tasks | Verification owner |
|---|---|---|
| Conditional Clear order / Close tab | M4.2-02, M4.2-03 | Automated + user |
| Dialog contents and visible actions | M4.2-03 | Automated + user |
| Enter clears; Escape/Keep preserve | M4.2-04 | Automated + user |
| Clear data effects and no side effects | M4.2-01, M4.2-05 | Automated |
| Eligible Close tab and deterministic selection | M4.2-01, M4.2-02, M4.2-05 | Automated + user |
| Last tab cannot close | M4.2-01 through M4.2-03, M4.2-05 | Automated + user |
| Enhanced in-place state and focus | M4.2-02, M4.2-04, M4.2-06 | Automated + user |
| Permission/scope/version/concurrency/fallback | M4.2-01, M4.2-02, M4.2-05 | Automated |
| Actual visual/scanner/responsive behavior | M4.2-07 checklist | User only |

## 5. Explicit non-tasks

- No model, migration, status-choice, legacy-row, or audit-choice deletion.
- No returns, voids, receipt printing, tax, new payment method, or reporting work.
- No undo/restore, fraud detection, discard reporting, reason, PIN, or approval.
- No new frontend framework, remote dependency, or manual frontend verification by Codex.

## 6. Mandatory planning review record

**Review date:** 2026-08-06

**Status:** PASSED after corrections

The first whole-project review found and corrected three issues:

1. The progressive-enhancement acceptance criterion lacked a reachable no-JavaScript Clear order
   confirmation. The specification/design/tasks now require a safe GET confirmation fallback and
   POST mutation while the normal enhanced path remains an in-POS dialog.
2. The JavaScript tasks promised complete delegated-DOM testing although the project deliberately
   has no DOM-test dependency. Coverage is now divided honestly between a pure keyboard-decision
   unit, Django-rendered hook assertions, syntax checks, and required user frontend verification.
3. The compact clear/close toast was present in the design but not explicit in the task acceptance
   text. M4.2-04 and M4.2-06 now require the dedicated toast hook without changing quieter cart
   mutations.

The repeated review reconciled `docs/milestones/m4.2-clear-orders/feature-spec.md` v1.1,
`docs/milestones/m4.2-clear-orders/technical-design.md` v1.1, and this task document with `docs/product/mvp-requirements.md` v1.5,
`docs/product/roadmap.md` v1.4, `docs/architecture/technical-design.md` v0.6, historical M3/M4/M4.1 behavior, the existing
PostgreSQL locking order, the current Django views/templates, and the local dependency set. No
unresolved contradiction, unsafe assumption, scope growth, dependency gap, or uncovered acceptance
criterion remains. M4.2-01 may proceed.
