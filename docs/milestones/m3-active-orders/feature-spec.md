# Milestone 3 - Active POS Orders

**Status:** Planning reviewed; implementation-ready

**Version:** 1.1

**Approved:** 2026-08-03
**Planning review passed:** 2026-08-04
**Inputs:** `docs/product/mvp-requirements.md` v1.4, `docs/product/roadmap.md` v1.3,
`docs/architecture/technical-design.md` v0.5, the approved Milestone 1 and Milestone 2 specifications/designs, and
the completed Milestone 2 application

> **Historical document:** This records the Milestone 3 behavior delivered in August 2026. Its
> retained discard/reason/audit requirements are superseded for future behavior by the approved
> [Milestone 4.2 feature specification](../m4.2-clear-orders/feature-spec.md). The current target uses **Clear
> order** and **Close tab** without discard history or audit.

## 1. Objective

Give every authorized sales user a fast, terminal-scoped workspace in which up to three customer
orders can be scanned, searched, edited, handed to another cashier, discarded with retained
history, and recovered after refresh, logout, browser restart, or application restart.

Milestone 3 ends with persistent `DRAFT` and retained `DISCARDED` orders. It does not accept cash,
complete a sale, allocate an order number, change inventory, or expose completed-order history.
Those behaviors remain in Milestone 4.

## 2. Actors

### Owner

- Can open and use the POS with the same sales permissions as an admin or cashier.
- Can create, select, edit, take over, and discard drafts on the active terminal.
- Can scan/search products and use the restricted POS quick-create flow.
- Retains the separate Milestone 2 permission to manage products and inventory outside the POS.

### Admin

- Has the same Milestone 3 POS permissions as the owner and cashier.
- Can create, select, edit, take over, and discard drafts on the active terminal.
- Can scan/search products and use the restricted POS quick-create flow.
- Retains the separate Milestone 2 catalog/inventory permissions.

### Cashier

- Can create, select, edit, take over, and discard drafts on the active terminal.
- Can scan or search active products and add them to a draft.
- Can quick-create a product only after an unknown checkout barcode scan and only with barcode,
  name, and selling price.
- Cannot enter the normal product-management or inventory-management workflows.

### Anonymous or inactive user

- Cannot view or mutate the POS workspace.
- Is handled by the authentication and active-session rules established in Milestone 1.

All actors operate only within their authenticated shop. Role parity inside the POS does not grant
a cashier any normal catalog, stock, user-management, report, void, or audit-history permission.

## 3. Compact-MVP decisions

1. The initial installation automatically uses the active terminal named by the existing
   server-side `POS_TERMINAL_CODE` setting, whose approved/default value is `TILL-1`. The resolver
   applies the same trim-and-uppercase normalization as bootstrap. There is no request-, session-,
   cookie-, or browser-selected terminal, terminal picker, application UI setting,
   cashier-to-terminal assignment, or browser enrollment flow in this milestone.
2. Drafts belong to the terminal, not the cashier. Every authorized sales user on the configured
   terminal (normally `TILL-1`) sees the same active tabs.
3. Tabs use stable, local labels `Order 1`, `Order 2`, and `Order 3`. A draft occupies one slot until
   it is discarded or, in Milestone 4, completed. Custom draft names, customer names, and notes are
   excluded.
4. The POS creates `Order 1` automatically when the terminal has no active draft. `New order`
   creates the lowest available slot only when fewer than three active drafts exist.
5. Empty drafts count toward the three-tab limit because they are real terminal drafts. An extra
   empty tab can be closed without a reason; it is still retained as `DISCARDED`. If the last active
   tab is closed or discarded, a fresh empty `Order 1` is created so the POS remains ready.
6. Selecting another cashier's draft does not silently change its handler or create an audit event.
   It first opens read-only and requires an explicit `Resume this order` action before editing.
7. A takeover requires confirmation but not a reason. It preserves the original creator, records
   the prior and new current cashier, and creates one audit event.
8. Product search is a compact checkout lookup, not a second catalog-management page. It searches
   active same-shop products by name, barcode, or SKU and adds the selected product.
9. POS quick-create exists only as the result of an unknown, non-empty barcode scan. The scanned
   barcode cannot be changed in that form; a wrong scan is cancelled and rescanned.
10. Quick-creating the product, recording its audit event, and adding its first draft line are one
    logical success. If any part fails, none of those effects remains.
11. The first successful add of a product captures its current selling price. Repeated scans and
    search-adds increase the existing line without recapturing a later catalog price.
12. Removing a line ends that captured line. Adding the product again later creates a new line and
    captures the catalog price current at that later time.
13. The draft `Total` is also its subtotal in this milestone. There is no tax, discount, round-off,
    cash, change, or payment calculation.
14. Recorded stock is informational during drafting. Adding a product neither reserves nor changes
    stock, and zero or negative stock does not block a draft add. Final stock validation and shortage
    acknowledgement belong to Milestone 4.
15. Every draft mutation uses an optimistic version. A stale browser is told to refresh the current
    persisted draft; the server never merges or silently replays a stale quantity change or scan.
16. Discarded drafts remain stored but are not browsable through a new history page in Milestone 3.
    Their retention and audit effects are covered by tests; broader order/audit browsing comes later.
17. No manual unit-price override, arbitrary product creation link, draft duplication, or movement
    of a draft between terminals is included.

## 4. Permission matrix

| Capability | Owner | Admin | Cashier |
|---|---:|---:|---:|
| Open the POS and view active terminal drafts | Yes | Yes | Yes |
| Create/select a draft up to the terminal limit | Yes | Yes | Yes |
| Scan/search and add an active product | Yes | Yes | Yes |
| Quick-create from an unknown checkout barcode | Yes | Yes | Yes |
| Change quantity or remove a line | Yes | Yes | Yes |
| Resume/take over another user's draft | Yes | Yes | Yes |
| Discard an active draft | Yes | Yes | Yes |
| Override captured price | No | No | No |
| Change stock from the POS draft | No | No | No |
| Complete sale/accept payment in M3 | No | No | No |

The server repeats authentication, active-user, role, shop, terminal, draft-state, and version checks
for every mutation. A hidden control, draft ID, product ID, terminal ID, or submitted price never
grants authority.

## 5. Preconditions and terminal resolution

- Milestones 0-2 are complete, including the seeded shop, active `TILL-1`, roles, products,
  inventory ledger, focused audit writer, local Tailwind assets, and PostgreSQL database.
- The user is authenticated, active, and has role `OWNER`, `ADMIN`, or `CASHIER`.
- The user's shop is active and owns the resolved terminal.
- For this single-computer milestone, terminal resolution uses only the normalized server-side
  `POS_TERMINAL_CODE` in the authenticated user's shop. It defaults to `TILL-1`, matching bootstrap.
  A submitted URL/form/session/cookie terminal identifier cannot switch the workspace.
- If the configured terminal code is invalid, missing, or inactive, the POS shows a safe blocking
  configuration message and creates or changes no draft. Correction uses the installation
  configuration/bootstrap procedure; M3 adds no terminal-management UI.
- Products and barcodes follow the approved Milestone 2 normalization, uniqueness, price, active,
  review, and shop-boundary rules.
- All timestamps are timezone-aware and displayed in `Asia/Karachi`; money is PKR using fixed-
  precision decimals.
- All state-changing requests are CSRF-protected POST requests. Successful conventional form
  submissions redirect or return a server-trusted current draft state so refresh does not repeat a
  mutation.

The data model remains terminal-ready for later local-network use, but second-terminal registration
and browser identity are not introduced here.

## 6. POS workspace and persistent tabs

### 6.1 Enter the workspace

1. The authorized user opens the POS.
2. The server resolves the user's shop and active configured terminal (normally `TILL-1`).
3. The server loads all `DRAFT` orders for that terminal in slot order.
4. If none exists, it creates a fresh empty draft in slot 1 with the logged-in user as creator and
   current cashier.
5. The page selects the requested valid tab when supplied by the workspace itself; otherwise it
   selects the most recently updated active draft, falling back to the lowest slot.
6. Each tab shows its stable label, item count, total, and enough creator/current-cashier context to
   make a handoff visible.

Opening, refreshing, or merely viewing the workspace does not take over a draft and does not create
business audit events.

### 6.2 Create and select tabs

- `New order` creates the lowest free slot and selects it.
- The button is unavailable when three drafts exist, and a crafted or concurrent fourth-draft
  request is rejected by the server.
- Creating a draft records the authenticated user as both creator and current cashier.
- Switching tabs changes only which persisted draft is displayed. It does not save a browser-only
  cart, discard another tab, reserve stock, or change its current cashier.
- A draft remains in its slot through refresh, logout, browser restart, and application restart.
- The page URL or browser state may remember the selected tab, but database records and server
  responses are the source of truth for all tab contents.

### 6.3 Draft presentation

The selected draft shows, at minimum:

- tab label;
- creator and current cashier when useful for handoff;
- one row per product with product name, captured unit price, positive whole-number quantity, and
  line total;
- barcode when the line has one, with a clear no-barcode presentation otherwise;
- the draft total in PKR; and
- scan, search, quantity, remove, resume/takeover, and discard controls when permitted by state.

An empty draft clearly prompts the cashier to scan or search. A foreign-current-cashier draft shows
its contents but keeps mutation controls disabled until takeover succeeds.

## 7. Barcode scan flow

The barcode scanner is treated as a keyboard that types the barcode and sends Enter.

1. The selected editable draft keeps a dedicated barcode input ready when the cashier is not
   actively typing in another control.
2. The scanned value is trimmed only at its edges; leading zeroes, case, punctuation, and internal
   characters are preserved.
3. The server performs an exact same-shop barcode lookup.
4. If the barcode belongs to an active product, one unit is added. If the product already has a
   line, its quantity increases by one and its captured unit price remains unchanged.
5. If the barcode belongs to an inactive product, the add is refused with a clear unavailable
   message. The barcode is not treated as unknown and no duplicate quick-create is offered.
6. If the barcode is unknown, the restricted quick-create flow opens with the exact scanned
   barcode. An enhanced scanner queue stops and clears any later queued barcode values at this
   workflow boundary; those physical items must be rescanned after quick-create or cancellation so
   the signed draft context cannot be invalidated behind the cashier's back.
7. Empty, overlong, stale-version, unauthorized, or otherwise invalid scans add nothing and leave
   the persisted draft unchanged.

After a successful known-product add, or a recoverable scan error that does not open another form,
focus returns to the scanner input. Focus behavior must not steal input while the cashier is using
search, quantity, quick-create, takeover, or discard controls. Overlapping scan mutations are not
blindly replayed; the returned version determines the next valid mutation.

## 8. Product search and add flow

- Search is available when a product has no barcode or scanning fails.
- A trimmed query searches partial, case-insensitive product name and SKU plus partial barcode
  within active products in the authenticated shop.
- Results are presented in stable name/identifier order and show product name, barcode/SKU where
  present, and current selling price. Current stock may be shown as information, clearly not as a
  reservation or M3 checkout decision.
- Selecting a result adds one unit to the editable selected draft using the same service behavior
  as a known scan.
- Selecting the same product again increases its one existing line and retains that line's captured
  price.
- Barcode-less products are fully supported through this flow.
- Inactive, out-of-shop, nonexistent, or stale search results are rejected when selected.
- An empty or no-result search creates no product. Quick-create cannot be reached from arbitrary
  search text.

The compact search may limit the initial result set for speed; full catalog pagination and editing
remain on the owner/admin Product pages built in Milestone 2.

## 9. Unknown-barcode quick-create

### 9.1 Form and flow

1. An editable draft receives an unknown non-empty barcode scan.
2. The quick-create form shows the scanned barcode as fixed context and accepts only:
   - required product name; and
   - required selling price.
3. The cashier can cancel without creating a product or changing the draft.
4. On submit, the server rechecks the authenticated browser session, actor, terminal, draft,
   version, barcode normalization, same-shop barcode uniqueness, name, and price. The signed
   context is bound to the session that performed the unknown scan, so logout/flush invalidates it
   even if the same user later logs in again.
5. On success, one transaction creates the product, records the quick-create audit event, and adds
   one unit to the selected draft using the new product's selling price.
6. The cashier returns to the selected tab with the new line visible and scanner input ready.

Owner and admin use exactly the same restricted behavior when quick-creating inside the POS. Their
normal catalog permissions do not make this form accept SKU, cost, stock, source, review, active,
shop, or creator fields.

### 9.2 Created-product rules

The new product:

- belongs to the authenticated user's shop;
- preserves the exact normalized scanned barcode, including leading zeroes;
- is active;
- has stock zero;
- has source `POS_QUICK_CREATE`;
- is marked as needing admin review;
- records the logged-in user as creator; and
- creates no inventory movement.

It is immediately usable in the draft. Zero stock does not trigger the Milestone 4 shortage
acknowledgement during drafting.

If another request assigns that barcode before quick-create is submitted, the product, audit event,
and line are not partially created. The cashier is shown that the barcode is now known and can
explicitly add the current product; submitted name/price values never overwrite it.

## 10. Draft lines, captured price, quantities, and totals

### 10.1 First add and repeated add

- A draft contains at most one current line per product.
- On the first successful add, the server captures the product's current selling price for that
  line. The retained line also carries enough product identity context for the current/discarded
  draft to remain understandable after later catalog edits.
- A catalog price change after the first add does not silently reprice the line.
- A repeated scan or search-add increments quantity by one using the existing captured price.
- If the product price changes between rendering a search result and the first successful add, the
  server captures the current persisted price at the time that add succeeds.
- There is no reprice button or manual unit-price override.

### 10.2 Quantity editing

- Quantity is a positive base-10 whole number within the supported storage range.
- A valid edit replaces the line quantity; it does not add the entered number to the old quantity.
- Zero, negative, decimal, blank, malformed, or out-of-range quantities are rejected without
  changing the line.
- Quantity cannot be changed to zero as a shortcut. The cashier uses the explicit remove action.
- If a product is deactivated after being added, the captured line remains visible. Its quantity
  may be reduced or removed, but it cannot be increased by scan, search, or quantity edit until the
  product is active again.

### 10.3 Line removal

- Remove is an explicit action on one line and needs no reason or confirmation.
- Removal changes no product or stock record.
- Removing the last line leaves an empty active draft; it does not implicitly discard the tab.
- A later add of the removed product creates a new line and captures the then-current catalog price.

### 10.4 Totals

- `line total = captured unit price x quantity`.
- `draft total = sum of current line totals`.
- An empty draft total is `PKR 0.00`.
- Totals are calculated and validated by the server with fixed-precision decimal arithmetic and
  stored/recalculated consistently after every successful line mutation.
- Browser-side previews, if present, are conveniences only; submitted totals and prices are ignored.
- The draft total is not a payable/completed amount and creates no financial record.

## 11. Cross-cashier resume and takeover

Drafts remain on the terminal when a user logs out. On the next login:

1. The new user sees every active terminal tab with its creator and current cashier context.
2. A draft whose current cashier is another user is viewable but not editable.
3. The user selects `Resume this order` and confirms the named handoff.
4. The server checks the current draft version and locks/revalidates the user, terminal, and draft.
5. On success, the original creator remains unchanged, the current cashier becomes the resuming
   user, the version advances, and exactly one `DRAFT_TAKEN_OVER` audit event is recorded.
6. The draft becomes editable for the new current cashier with all items, captured prices,
   quantities, and totals unchanged.

Takeover applies to another user's empty or non-empty draft and requires no reason. Merely opening,
selecting, or refreshing a foreign draft is not a takeover. If another session changes or takes the
draft first, the stale takeover fails and shows the latest state without a false audit event.

## 12. Draft discard and empty-tab close

### 12.1 Non-empty draft

1. The current cashier chooses Discard.
2. A confirmation view shows the tab, current items, quantities, and total.
3. The cashier enters a required reason of at most 500 characters and confirms.
4. The server locks the draft, validates the exact version and current-cashier authority, and
   recalculates its retained total.
5. On success, status becomes `DISCARDED`; the items, captured values, creator, current cashier,
   discarding cashier, time, total, and reason remain stored.
6. Exactly one `DRAFT_DISCARDED` audit event is created in the same transaction.
7. The discarded tab leaves the active workspace. If no active tab remains, a fresh empty
   `Order 1` is created for the current user.

A blank/whitespace reason, cancellation, stale version, unauthorized attempt, or database/audit
failure does not discard or partially change the draft.

### 12.2 Empty draft

- An empty tab uses a clearly labelled `Close empty tab` action.
- It does not require a typed reason or the non-empty-loss warning.
- It is marked and retained as `DISCARDED` with actor/time and an empty-close indication, and creates
  one discard audit event.
- The same last-tab rule keeps one fresh empty draft ready.

Discarding never deletes a draft, changes stock, creates payment, or allocates an order number.
M3 provides no general discarded-draft history page and no restore-from-discard action.

## 13. Validation and failure behavior

### Shared mutation validation

Every create, takeover, scan, search-add, quick-create, quantity, removal, close, and discard action
revalidates:

- authenticated and active sales actor;
- active actor shop and same-shop target records;
- active resolved terminal and terminal ownership;
- `DRAFT` status and valid terminal slot;
- current-cashier authority where editing is requested; and
- the exact last-known draft version.

The server derives shop, terminal, creator, current cashier, captured price, totals, audit actor,
timestamps, source, review state, and stock defaults. Submitted alternatives are ignored or rejected.

### Product and quick-create validation

- Scan/quick-create barcode is required after trimming, at most 64 characters, and unique within
  the shop when non-empty.
- Quick-create name is required after trimming and at most 200 characters.
- Selling price is a non-negative PKR decimal with at most two decimal places and within the
  supported money range. A zero price is valid under the approved catalog rules.
- A product must be active and same-shop when newly added or increased.
- Barcode/SKU/name matching never crosses the actor's shop.

### User-facing failures

- Validation errors identify the field or action and preserve only safe input.
- Authorization and cross-shop failures follow the existing 403/not-found behavior without
  disclosing foreign records.
- A stale-version response clearly says the order changed elsewhere and renders or reloads the
  current server state. It does not apply the submitted change automatically.
- A network/server failure leaves the last committed draft intact and shows a recoverable message.
  If the response was lost after commit, refresh reveals the committed state; the client does not
  blindly replay the old mutation.
- Unknown-scan quick-create context is short-lived, signed, actor/shop/terminal/draft/version bound,
  and bound to a non-reversible fingerprint of the current authenticated session. The raw session
  key is never placed in the token. Logout, expiry, tampering, user/session change, takeover,
  discard, or any intervening draft mutation prevents its use.
- No failure exposes a production traceback or creates a partial product, line, takeover, discard,
  or audit event.

## 14. Concurrency and versioning

- Each draft has an integer version representing its latest committed state.
- Every mutation sends the version displayed by the client. The server locks the draft, compares
  versions, applies at most one mutation, and advances the version only for a successful material
  change.
- A mismatched version rejects the entire request. The server does not use last-write-wins for
  scans, quantities, removals, takeover, or discard.
- The terminal's maximum-three-draft rule and slot allocation are enforced transactionally. Two
  simultaneous `New order` requests cannot create duplicate slots or a fourth active draft.
- Concurrent takeovers allow only the request with the current version to succeed. Later users see
  the new current cashier and must deliberately take over that newer state if still appropriate.
- Concurrent scan/quantity/remove requests on one draft are serialized by the locked order and
  protected by version checks, preventing a silent lost increment or overwritten quantity.
- A quick-create race is additionally protected by the approved shop/barcode database uniqueness
  rule. Product creation, audit, and line addition roll back together on conflict or stale draft.
- Draft operations do not lock or decrement inventory balances and do not claim stock. Inventory
  concurrency and final availability are intentionally deferred to Milestone 4 checkout.

## 15. Data and audit effects

| Action | Draft/order effect | Product/inventory effect | Audit effect |
|---|---|---|---|
| Create tab | New terminal-scoped `DRAFT` with creator/current cashier and slot | None | None |
| Add first product | New retained draft line with product reference, captured price/identity, quantity, and total | No stock change or movement | None |
| Repeated add/quantity edit | Update quantity and server totals; advance version | No stock change or movement | None |
| Remove line | Remove current draft line and recalculate total | No stock change or movement | None |
| Quick-create | Add the new product as a draft line | Active zero-stock `POS_QUICK_CREATE` product needing review; no movement | `PRODUCT_QUICK_CREATED` |
| Take over | Preserve creator; change current cashier; advance version | None | `DRAFT_TAKEN_OVER` |
| Discard/close | Retain draft and current lines as `DISCARDED` with actor/time/reason as applicable | None | `DRAFT_DISCARDED` |

Quick-create, takeover, and discard audit events are append-only and written in the same successful
transaction as their business effect. Focused payloads identify the target, actor, time, and relevant
transition without storing raw requests or sensitive values:

- quick-create: product ID, barcode, name, selling price, source, needs-review state, and draft ID;
- takeover: draft ID/slot, creator ID, previous current-cashier ID, new current-cashier ID, item
  count, and total; and
- discard: draft ID/slot, creator/current/discarding actor IDs, item count, total, reason when
  required, and whether the draft was empty.

The completing cashier, completed time, permanent order number, payment, round-off, and completion
status remain unset because no sale is completed in Milestone 3. There are no `SALE` inventory
movements or any other stock balance changes.

## 16. Acceptance criteria

### Access, terminal, and tabs

1. Owner, admin, and cashier can open the POS; anonymous/inactive users cannot, and a cashier gains
   no normal catalog or inventory permission.
2. The POS automatically uses the active same-shop terminal selected only by normalized
   server-side `POS_TERMINAL_CODE` (default `TILL-1`); invalid/missing/inactive configuration blocks
   safely, and submitted identifiers cannot switch shop or terminal.
3. With no active drafts, entering POS creates one empty `Order 1`; the user can create `Order 2`
   and `Order 3`, but no fourth draft can be created through normal, crafted, or concurrent requests.
4. Three tabs retain separate products, quantities, captured prices, totals, creators, and current
   cashiers through refresh, logout, browser restart, and Django/application restart.

### Scan, search, and quick-create

5. Scanning a known active barcode adds one unit; repeated scans increase exactly one product line
   by one each without recapturing price.
6. A barcode such as `0012345` keeps its leading zeroes through scan, lookup, quick-create,
   display, audit data, and later repeated scan.
7. Search finds active same-shop products by partial name, barcode, or SKU and can add a barcode-less
   product; inactive, foreign, or stale results cannot be added.
8. An inactive known barcode is reported unavailable and cannot open duplicate quick-create.
9. An unknown scan opens only the restricted barcode/name/selling-price flow. Success atomically
   creates an active zero-stock product with source `POS_QUICK_CREATE`, `needs_review = Yes`, one
   focused audit event, and one draft line.
10. Quick-create validation or a duplicate/stale race leaves no partial product, audit event, or
    line; the Milestone 2 needs-review filter exposes every successful quick-created product.

### Lines, totals, persistence, and stock isolation

11. First add captures the current selling price. A later catalog price change does not change the
    existing line, repeated adds, line total, or draft total.
12. Removing and later re-adding a product captures the then-current price as a new line.
13. Positive whole-number quantity edits and explicit removal recalculate exact fixed-precision line
    and draft totals; zero, negative, decimal, blank, malformed, and out-of-range quantities do not.
14. A product deactivated after being added remains visible and removable, but its quantity cannot
    be increased until reactivation.
15. Draft creation and every draft mutation leave `stock_on_hand` and the inventory movement count
    unchanged, including for zero- and negative-stock products.

### Handoff, discard, audit, and concurrency

16. Another cashier can view a terminal draft after logout but cannot edit it until explicitly
    taking it over; takeover preserves creator, changes current cashier, changes no line/total, and
    creates exactly one accurate audit event.
17. Viewing or refreshing another cashier's draft creates no takeover event.
18. A non-empty discard cannot succeed without current-cashier authority, exact version,
    confirmation, and a non-blank reason; success retains its items, captured values, total, actor,
    time, and reason and creates exactly one audit event.
19. An empty tab can close without a typed reason, is retained/audited, and closing/discarding the
    last active tab leaves one fresh empty `Order 1` ready.
20. Stale scan, search-add, quick-create, quantity, removal, takeover, and discard submissions make
    no partial change and return the current persisted version.
21. Concurrent mutations do not lose increments, overwrite newer quantities, create duplicate tab
    slots/barcodes, or exceed three active drafts.
22. All model/constraint, service, transaction, concurrency, permission, form/view, audit,
    persistence, template, JavaScript, Tailwind, PostgreSQL, and regression tests pass.

## 17. Manual acceptance scenarios for milestone completion

Automated tests are required for exact data, audit, rollback, and concurrency guarantees. Manual
verification is also required for physical scanner behavior and the complete persistence/handoff
experience.

### Required release checks

1. With `POS_TERMINAL_CODE=TILL-1`, log in as a cashier and open POS. Confirm `TILL-1`, one ready
   `Order 1`, focused barcode input, PKR formatting, and no cash/checkout/order-history controls.
2. With a real USB scanner, scan one known barcode three times. Confirm one line at quantity 3,
   exact line/total arithmetic, and focus returning for the next scan.
3. Search for and add a barcode-less product. Change its quantity to another positive whole number,
   reject `0` and `1.5`, then remove the line and confirm totals update without stock changing.
4. Create and populate all three tabs with different products. Try to create a fourth, refresh,
   close/reopen the browser, and restart Django. Confirm all three orders remain separate and exact.
5. Scan an unknown leading-zero barcode, cancel once, then repeat and quick-create it. Confirm the
   barcode is unchanged, the item is immediately on the draft, stock remains zero, and an
   owner/admin can find it with the existing Needs review product filter.
6. Add a product, note its captured unit price, change the product's catalog price as owner/admin in
   another session, then scan it again on the original draft. Confirm quantity increases while the
   original captured unit price and totals remain based on that price. Remove and re-add it and
   confirm the new line captures the new price.
7. Leave a non-empty draft as Cashier A and log out. Log in as Cashier B on the same terminal,
   confirm the draft is visible/read-only, explicitly resume it, and confirm items/totals remain
   unchanged while Cashier B can now edit.
8. Attempt to discard a non-empty draft without a reason, cancel once, then confirm with a reason.
   Confirm it leaves the active tabs and no inventory changes. Close an extra empty tab and confirm
   no typed reason is required. Confirm one new empty tab remains if the last active tab was removed.
9. Disconnect internet access and repeat known scan, product search, tab switching, quantity edit,
   logout/login handoff, and browser restart. Confirm no missing asset or remote dependency.

If physical scanner hardware is temporarily unavailable, typing the barcode followed by Enter is
an acceptable development check, but a real-scanner pass remains required before Milestone 3 is
declared complete.

### Optional confidence checks

1. Open the same draft in two authenticated browser sessions. Change it in one and submit the stale
   page in the other; confirm the stale action is rejected and the newer server state is shown.
2. Have two users attempt takeover at nearly the same time; confirm one succeeds and the other sees
   the updated current cashier before deciding whether to take over again.
3. Inspect the retained audit/data records through a developer shell to confirm quick-create,
   takeover, non-empty discard, and empty close each recorded exactly one event. This is optional
   manually because automated tests are authoritative and the audit-history UI is Milestone 6.

The exact setup commands and final pass/fail checklist will be recorded again in the Milestone 3
completion evidence after implementation.

## 18. Explicit exclusions

- Cash received, change due, payment, cash drawer, or receipt behavior.
- Signed round-off, round-off reason/confirmation, adjusted totals, or adjusted-order badges.
- Checkout completion, permanent order numbers, completed-order summaries, or fresh-tab-after-sale
  behavior.
- Inventory reservation, sale deduction, final stock locking/recheck, negative-stock warning or
  acknowledgement, and `SALE` movements.
- Completed-order list/search/detail, historical sale browsing, or any order-history page.
- Returns, refunds, damaged/restock decisions, completed-sale voids, and reversal movements.
- Daily summary, report pages, or user-visible audit-history pages.
- Normal cashier catalog editing, SKU/cost/opening-stock entry, receipt/adjustment, or arbitrary
  product creation outside an unknown POS barcode.
- Tax, discounts, coupons, promotions, price overrides, weighted quantities, split payment, or any
  non-cash payment method.
- Product reservations, customer accounts, loyalty, customer/draft names, draft notes, draft copy,
  or draft transfer between terminals.
- Terminal selection, terminal administration, signed browser enrollment, cashier shifts/till
  assignment, multi-shop switching, and offline synchronization.
- Scanner SDKs, browser extensions, external services, runtime CDN assets, SPA frameworks,
  WebSockets, and service workers.
- Restore of a discarded draft or deletion/editing of its retained history.

## 19. Continuous-workflow approval record

On 2026-08-03, the user explicitly authorized the Milestone 3 workflow to continue without
intermediate approval pauses and requested that planning proceed through the required feature
specification, technical refinement, development tasks, separate Sol xhigh planning review/fix
gate, implementation, and verification sequence.

Version 1.0 was recorded as **Approved for continuous implementation**. The mandatory independent
planning review on 2026-08-04 corrected the terminal-resolution wording and made the unknown-scan
queue/session-security behavior explicit without changing approved product scope. This reviewed
version 1.1 is implementation-ready and does not authorize Milestone 4 checkout/history
functionality. Continuous authorization waives normal user-approval pauses; it does not waive the
required document order, automated/manual verification, or reconciliation of any later material
scope change with the approved MVP.
