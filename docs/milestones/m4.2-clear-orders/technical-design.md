# Milestone 4.2 Technical Design - Clear Order and Close Tab

**Status:** Planning reviewed; implementation-ready

**Version:** 1.1

**Prepared:** 2026-08-06

**Input:** Approved `docs/milestones/m4.2-clear-orders/feature-spec.md` v1.1

## 1. Scope and invariants

Implement two draft-only operations without changing checkout, payment, stock, takeover, product,
completed-order, or Recent sales behavior.

Existing legacy `DISCARDED` status/fields/action codes remain schema-compatible but become unused by
normal POS flows. No migration or destructive cleanup is part of this refinement. No new clear or
close operation creates a retained row or audit event.

## 2. Domain services

### 2.1 `clear_draft`

`clear_draft(actor, draft_id, expected_version) -> Order`

Within `transaction.atomic`:

1. lock and revalidate the active actor and configured terminal;
2. lock the scoped draft and its current items;
3. require editable/current-cashier authority and exact version;
4. require at least one current item;
5. delete all draft items;
6. set subtotal to `0.00`, increment version, and save the same draft; and
7. return the refreshed empty draft.

No call to the audit recorder or inventory service is permitted.

### 2.2 `close_empty_draft`

`close_empty_draft(actor, draft_id, expected_version) -> Order`

Within `transaction.atomic`:

1. lock/revalidate actor, then terminal, then all active terminal drafts in slot order, followed by
   the target's items in ID order;
2. require current-cashier authority, exact version, no items, and zero subtotal;
3. require at least one other active draft;
4. select the next higher slot, falling back to the highest lower slot;
5. delete the empty target draft; and
6. return the selected remaining draft.

The service rejects the last active tab and never creates a replacement. It records no audit.

## 3. Forms, views, and URLs

- Use version-only POST forms; remove reason from the active clear workflow.
- Add a safe GET/POST endpoint named `sales:draft_clear` and a POST-only endpoint named
  `sales:draft_close`.
- Enhanced requests return the existing tabs/panel state envelope.
- Normal Clear order GET renders a server confirmation fallback containing the same facts/actions
  as the POS dialog; its POST clears and redirects to the retained draft.
- Normal clear success redirects to the same draft; normal close success redirects to the selected
  remaining draft.
- Enhanced validation/conflict responses use the current structured POS error protocol.
- The old discard route/template is removed. Legacy internal data remains unavailable through POS.

## 4. Templates and dialog

The order header renders exactly one relevant action. Clear order uses a fallback link that local
JavaScript intercepts to open the in-panel dialog; without JavaScript, the link reaches the safe
server-rendered confirmation page:

- non-empty editable draft: **Clear order** dialog trigger;
- empty editable draft with two or three active tabs: immediate **Close tab** POST form; or
- only active empty draft/read-only draft: no action.

The Clear order dialog is rendered inside the draft-panel fragment so enhanced updates always carry
the current version/item count/total. It shows:

- `Clear Order <slot>?`;
- `<count> items - PKR <subtotal>`;
- a warning that the action cannot be undone;
- Keep order; and
- Clear order.

Local POS JavaScript opens/closes the dialog, sets initial focus to the destructive confirmation as
approved, maps Escape to cancel, and restores scanner focus after cancellation. Native dialog
semantics and visible labels are used; no external library is introduced.

## 5. JavaScript and enhancement

- Clear/close POSTs use the existing `data-pos-mutation` handler and button-disable protection.
- Add minimal delegated dialog open/close/keydown behavior because the draft panel is replaced.
- Enter in the dialog's initial/default state submits the clear form.
- Escape and Keep order close without a request.
- Clear/close success replaces the two existing fragments, updates the URL/version, announces the
  result, dispatches a local success toast through an explicit clear/close form hook, and restores
  scanner focus. Other cart mutations retain their existing quieter behavior.
- No new fragment boundary, runtime dependency, or network asset is added.

## 6. Legacy compatibility

Existing `DISCARDED` rows, discard metadata fields, constraints, migrations, and the historical
`DRAFT_DISCARDED` action choice remain untouched in this no-migration refinement. They are not
queried into active tabs and no new UI/service path creates them. A later cleanup migration may be
considered only after confirming production data requirements; it is not needed for the MVP flow.

## 7. Tests

Cover:

- clear success retains draft identity/slot/cashier, deletes every line, resets subtotal, increments
  version, and creates no audit/inventory/payment data;
- close success deletes only an eligible empty draft, returns deterministic selection, and creates
  no replacement/audit;
- last-tab, non-empty-close, empty-clear, stale version, read-only/current-cashier, shop/terminal,
  inactive user, malformed ID, and method/CSRF boundaries;
- clear/close races with scan, quantity, takeover, and checkout;
- dialog content, conditional actions, enhanced fragments, and normal fallback;
- exported keyboard-decision helper coverage plus JavaScript syntax/static-hook checks without a
  new DOM-test dependency; actual dialog event wiring and focus remain user verification;
- complete Sales/project regression, Ruff, Django checks, migration drift, Tailwind, dependencies,
  static collection, and diff review.

Actual browser dialog appearance, keyboard behavior, scanner focus, and responsive layout remain
user-owned manual verification.

## 8. Migration and deployment impact

- No schema or data migration.
- No dependency/environment change.
- Rebuild local Tailwind output and version local POS JavaScript.
- Existing legacy discard rows remain inert and internal.

## 9. Next workflow gate

After technical-design review, create `docs/milestones/m4.2-clear-orders/development-tasks.md`, run the mandatory whole-project
planning review, fix findings, and only then implement.
