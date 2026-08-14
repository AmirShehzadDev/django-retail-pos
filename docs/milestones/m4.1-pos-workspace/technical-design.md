# Milestone 4.1 Technical Design - Compact POS Workspace Redesign

**Status:** Version 1.1 reviewed - implementation ready

**Version:** 1.1

**Prepared:** 2026-08-06

**Input:** Approved `docs/milestones/m4.1-pos-workspace/feature-spec.md` v1.0

> **Follow-on refinement:** The approved [Milestone 4.2 technical design](../m4.2-clear-orders/technical-design.md)
> replaces the inherited retained-discard interaction. This document remains authoritative for
> the M4.1 layout, in-place checkout, and Recent sales work only.

## 1. Scope and invariants

The original refinement changed the POS shell/templates and presentation tests. Version 1.1 also
changes the workspace query/context, checkout HTTP response, enhanced JSON payload, and local
JavaScript needed for in-place completion and Recent sales. It does not change models, migrations,
forms, URLs, checkout services/transactions, permissions, or business rules.

The following existing contracts remain frozen:

- `#pos-draft-tabs[data-pos-tabs]` and `#pos-draft-panel[data-pos-panel]` are the two enhanced
  fragment replacement boundaries;
- scanner queue/version semantics and `data-pos-*` mutation hooks remain unchanged;
- all mutations remain CSRF-protected normal POST forms with progressive enhancement;
- the server remains authoritative for prices, quantities, totals, stock warnings, permissions,
  cash, Change, and completion;
- the initial-order protected auto-start and three-draft limit remain unchanged; and
- all M4 checkout/history and M3/M3.1 cart/catalogue business behavior remains unchanged; and
- normal non-enhanced checkout retains its completed-order-detail redirect.

## 2. Template architecture

### 2.1 Base shell extension point

Wrap the existing application header in a named `app_header` template block. The default block
renders the current header byte-for-byte for every non-POS page. `sales/pos_workspace.html`
overrides the block with no content.

The existing fixed messages partial remains outside `<main>` and is unaffected.

The POS override suppresses only the normal application header. It does not suppress fixed messages,
the skip link, or the authenticated Home destination used by Exit POS.

### 2.2 POS page shell

`sales/pos_workspace.html` becomes a dedicated full-height shell:

- `main_class` uses the whole desktop viewport with no outer max-width/padding and prevents
  whole-page overflow at the desktop breakpoint;
- the root `[data-pos-workspace]` remains a height-bounded flex column;
- a compact white toolbar is the only POS chrome;
- the toolbar contains the terminal/shop identity, current draft tabs, New order, Orders, Products,
  current cashier/role, and an Exit POS link to `core:home`;
- `data-pos-new-draft` remains on the same form so existing JavaScript can toggle it after fragment
  updates; and
- the live status region and local `pos.js` include remain unchanged.

Below desktop, the shell may return to natural height and page scrolling.

## 3. Active-order toolbar

`sales/partials/draft_tabs.html` keeps the same root ID/data attribute but renders compact horizontal
tabs rather than three large cards.

Each tab shows:

- `Order <slot>`;
- the current subtotal; and
- a compact ownership indicator (`Yours` or `Read only`) without cashier/detail duplication.

The selected tab retains `role=tab`, `aria-selected=true`, and `aria-current=page`. Tabs remain
ordinary GET links and are horizontally compact enough for three orders in the desktop toolbar.

The empty-tabs state is concise and does not add a large card.

## 4. Workspace geometry

`sales/partials/draft_panel.html` remains the enhanced panel boundary and uses:

- desktop columns `minmax(0, 13fr) minmax(18rem, 7fr)`, producing approximately 65/35;
- no gap between structural panes, using one neutral divider;
- a bounded `h-full min-h-0` desktop layout;
- natural stacked layout below the desktop breakpoint; and
- internal overflow only on cart-line and product-result regions.

The order pane is a plain white flex column. The catalogue pane uses a subtle neutral background.
Repeated large rounded cards and panel shadows are removed.

## 5. Selected-order pane

### 5.1 Order/scanner header

The order meta row uses 12-14px text and shows item count, current cashier, and the existing
Discard/Close action. The scanner row remains immediately below it, uses the existing scanner form,
and retains a 40-44px input/button target.

Read-only state replaces the scanner with the current compact takeover notice. A read-only checkout
dock shows the total and Resume action rather than editable cash controls.

### 5.2 Warnings

Projected shortage and inactive-retained-product messages retain their exact semantics. The
shortage warning becomes a one-line 12px strip when it fits and wraps when necessary. Inactive
status remains secondary text within only the affected cart line.

### 5.3 Cart rows

`sales/partials/draft_line.html` becomes a divider-based dense row with desktop columns:

1. product name and captured barcode;
2. captured unit price;
3. existing minus/current/plus controls;
4. captured line total; and
5. existing Remove action.

Normal row targets approximately 48-56px but may grow for an inactive warning or wrapped long name.
The current forms, hidden fields, disabled boundaries, `data-pos-mutation` hooks, and accessible
labels remain unchanged. At smaller widths the row wraps/stacks without dropping information.

### 5.4 Checkout dock

The existing checkout form stays fixed as the order pane footer and preserves its fields and
endpoint. It uses a compact dark surface with:

- 12px labels;
- 24px Total;
- 14px cash input;
- prominently readable signed Change; and
- one green Complete sale button.

No new cash validation or client-authoritative calculation is introduced. Existing JavaScript
continues to provide the non-authoritative Change preview.

## 6. Product catalogue pane

The fixed catalogue header contains a 14px title and the existing GET search form. Search continues
to preserve the selected draft and optional Clear search action.

Results become a two-column grid at the POS catalogue width. Each product is one existing POST form whose button fills
the tile and contains:

- product name (14px);
- selling price (14px, emphasized);
- stock (12px); and
- barcode or SKU (12px, truncated when necessary).

The whole enabled tile is the Add target; no separate product image, category, or JavaScript action
is introduced. For read-only orders, results render as non-interactive tiles without a form.

### 6.1 Recent sales query and presentation

Add `recent_completed_orders(actor, limit=3)` to `apps.sales.queries`. It must:

- enforce POS authorization through the existing policy;
- filter by the actor's shop, `COMPLETED` status, and an existing cash payment;
- select the payment and completing cashier without per-row queries;
- order by `completed_at DESC, id DESC`; and
- clamp the internal limit to three.

`_workspace_context` loads this tuple for full pages and every enhanced panel refresh. The catalogue
aside renders it as a fixed footer below the internally scrolling product results. Positive Change
uses emerald, negative Change red, and zero a neutral colour. Every row links to the existing
same-shop read-only order detail; no mutation is exposed.

## 7. Enhanced checkout protocol

The existing checkout form remains a normal CSRF-protected POST and gains the existing
`data-pos-mutation` enhancement hook. `checkout_views.checkout` detects `X-POS-Enhanced: 1`.

On a successful enhanced checkout it returns the same workspace state envelope used by cart
mutations, selected to `CheckoutResult.replacement`, plus a `completed_order` object containing
only string/boolean presentation data:

- `order_number`;
- `detail_url`;
- `total`;
- `cash_received`;
- signed `change`; and
- `already_completed`.

The refreshed draft panel already contains current catalogue stock and Recent sales, so no third
fragment boundary is introduced. On enhanced validation/conflict failures, return JSON with the
current workspace fragments where available and an appropriate 4xx status. Terminal/database
failures return a small JSON error with 503 and never claim success. Non-enhanced requests retain
the existing message and detail redirect behavior.

`pos.js` continues to disable submit buttons before the request. When `completed_order` is present,
it applies the two existing fragments, replaces the URL with the replacement draft, announces the
completion, dispatches a local success-toast event containing order number/total/Change, and then
restores scanner focus. The server result remains authoritative; no client retry is introduced.

`app.js` owns safe dynamic toast creation in the existing fixed toast stack. It inserts message text
with `textContent`, initializes the existing pause/dismiss/timeout behavior, and makes no network
request.

## 8. Typography and Tailwind

Use only local compiled Tailwind utilities and the existing system font stack.

The implementation maps the feature typography as follows:

- default POS root: `text-sm` (14px);
- secondary content and labels: `text-xs` (12px);
- shell identity: `text-lg` (18px maximum);
- normal names, values, inputs, and buttons: `text-sm`;
- checkout Total and Change values: `text-2xl` (24px); and
- no `text-3xl` or larger utility within the POS workspace.

Existing shared form widgets may retain their global min-height class; POS-specific visible inputs
may receive template-local sizing only where rendering a widget directly would break density.

## 9. Accessibility and progressive enhancement

- Preserve the skip link and `#main-content` target.
- Preserve tab roles/selection state and the assertive POS live region.
- Maintain visible text labels for scanner/search/cash and accessible labels for icon/compact actions.
- All button targets remain at least 40px in the POS even with smaller text.
- Keyboard focus styles remain visible.
- Recent sales has a labelled region/list and descriptive View-link labels.
- Dynamic completion confirmation is exposed through the existing live region and toast status.
- With JavaScript disabled, tabs, search, add, quantity, remove, takeover, discard, checkout, and
  initial start continue through normal links/forms and redirects.

## 10. Testing

Update `apps.sales.tests.test_ui` to verify:

- POS suppresses the normal primary header but other pages retain it;
- dedicated shell links and cashier identity are present;
- tabs remain fragment-compatible and accessible;
- desktop 13fr/7fr geometry and two-column catalogue utilities render;
- the POS contains no `text-3xl`/larger utility and keeps the approved compact markers;
- dense line columns and all existing step/remove boundaries render;
- read-only, empty, inactive, shortage, and no-result states remain valid;
- checkout fields/actions and enhanced fragment IDs remain unchanged; and
- no new deferred controls or runtime network assets appear.
- Recent sales query ordering, three-row limit, shop isolation, payment requirement, and permissions;
- enhanced checkout success payload/fragments/replacement selection without a redirect;
- enhanced checkout validation, conflict, not-found, terminal, and database failures;
- unchanged normal POST redirect fallback and checkout idempotency; and
- JavaScript completion message/event behavior and dynamic toast safety.

Run template parsing, affected view/integration tests, the full Sales suite, complete PostgreSQL
suite, JavaScript tests/syntax, Ruff, Django checks, migration-drift check, local Tailwind build,
and `git diff --check`.

Automated checks do not prove pixel fit, real scanner focus, touch targets, wrapping of actual shop
data, or offline browser presentation. Those remain user-owned manual acceptance.

## 11. Migration and deployment impact

- No model or data migration.
- No dependency or environment change.
- Rebuild and commit `static/css/app.css`.
- No external font, image, CDN, or runtime network request.

## 12. Implementation order

1. Add base header block and dedicated POS shell.
2. Compact the order tabs within the shell toolbar.
3. Implement the 13fr/7fr order/catalogue geometry.
4. Densify cart rows and checkout dock.
5. Convert catalogue results to the two-column tile grid.
6. Update automated UI contracts and rebuild Tailwind.
7. Run focused/full verification and record evidence.

Version 1.1 refinement order:

1. Add/test the bounded Recent sales query and workspace context.
2. Render the fixed Recent sales catalogue footer.
3. Add enhanced checkout JSON success/error responses while retaining normal redirect fallback.
4. Enhance checkout submission, completion announcement/toast, state replacement, and scanner focus.
5. Run regression verification and update completion evidence.

## 13. Planning-review adjustments

The mandatory whole-project review confirmed the presentation-only boundary and added these
implementation safeguards:

- the dedicated header override must preserve fixed toasts and the skip-link/main target;
- read-only orders must not render cash input or a Complete sale action;
- catalogue tile forms must preserve CSRF, expected-version fields, normal POST fallback, selected
  draft search state, and the existing enhanced mutation hooks;
- fragment roots must remain direct, replaceable roots after every layout change; and
- the two-column catalogue applies at the narrow POS pane without adding product photos or changing
  query ordering/limits.

The Version 1.1 refinement review also confirmed:

- checkout service/transaction/idempotency code remains unchanged; only its HTTP representation is
  enhanced;
- the normal POST detail redirect remains the progressive-enhancement fallback;
- Recent sales excludes completed records without a payment, is same-shop and permission checked,
  and is hard-limited to three rows;
- refreshed stock and Recent sales travel inside the existing draft-panel fragment, avoiding a
  third replacement boundary;
- enhanced failures return JSON without queuing Django messages that could appear on a later page;
- completion presentation values are server-formatted strings and dynamic toast text is inserted
  with `textContent`; and
- an already-completed replay remains a successful idempotent response and selects an available
  replacement/current draft without creating another payment or stock movement.
