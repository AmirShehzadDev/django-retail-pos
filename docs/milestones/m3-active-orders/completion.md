# Milestone 3 - Completion Evidence

**Status:** Complete

**Verification date:** 2026-08-04

**Manual acceptance:** Milestone approved by the user on 2026-08-04

**Platform:** Windows 11, Python 3.13.14, Dockerized PostgreSQL 16.14, Tailwind CSS 4.3.3

> **Historical completion evidence:** Retained audited discard was correct for the approved
> Milestone 3 build at this date. The approved [Milestone 4.2 refinement](../m4.2-clear-orders/feature-spec.md)
> supersedes that interaction with **Clear order** and **Close tab** without discard audit/history.

## 1. Delivered

- Database-backed active orders with stable terminal slots 1-3 and an enforced three-draft limit.
- Exact captured product/barcode/price snapshots, quantities, line totals, and order subtotal.
- Barcode scan, product search, add, quantity update, and line removal workflows.
- Restricted session-bound unknown-barcode quick-create with audit and Needs review state.
- Cross-cashier read-only viewing, explicit audited takeover, and retained audited discard.
- Optimistic positive-bigint versions and PostgreSQL row locking for concurrent mutations.
- Server-rendered Tailwind workspace with local FIFO scanner JavaScript and no remote assets.
- Persistence across refresh, logout, browser/application restart, and cashier handoff.
- Strict separation from Milestone 4: no payment, checkout, completed history, receipt, stock
  reservation, stock change, or inventory movement.

## 2. Automated evidence

| Check | Result |
|---|---|
| Independent implementation review | No unresolved runtime, schema, security, concurrency, decimal, inventory, frontend-protocol, or scope finding |
| Docker PostgreSQL | PostgreSQL 16.14 healthy; isolated databases created and removed cleanly |
| Migrations and drift | All 23 migration nodes applied; no pending migration or model drift |
| Django development check | Passed with no issues |
| Focused sales suite | 122 tests passed on PostgreSQL |
| Full PostgreSQL regression suite | 269 tests passed in 364.790s; no skips; M0-M2 baseline 145 plus 124 M3 tests |
| Concurrency stress suite | 12/12 passed; full module repeated 36/36; price race 5/5; discard race 10/10 |
| Ruff 0.16.1 lint and format | Passed; 121 Python files formatted |
| Python dependency check | Passed; no broken requirements |
| JavaScript syntax/tests | `app.js`/`pos.js` syntax passed; 4/4 POS tests passed |
| npm install audit | 34 packages installed; 0 vulnerabilities |
| Tailwind deterministic build | Passed twice; 34,948 bytes; SHA-256 `8315DB85CEE3975A3D899E2A52F31B2117BEC986670C40953361C850AE2955B9` |
| Local static collection | Passed in development and production settings |
| Inventory reconciliation | Passed; one development product reconciled |
| Waitress 3.0.2 HTTP smoke | Login, authenticated POS, start, scan, search/add, and local assets returned HTTP 200 |
| Production safety | Invalid terminal returned safe 503; `/admin/` returned 404; zero rendered remote URLs |

The deployment check reports the four expected localhost-HTTP warnings already documented for
HSTS, HTTPS redirect, secure session cookies, and secure CSRF cookies. These protections are
required if the application is exposed through HTTPS or outside the trusted local shop network.
The isolated production smoke finished with two items, order version 3, subtotal PKR 15.75,
unchanged product stocks, and zero inventory movements. Its servers and database were removed.

Two material issues were found before release and fixed with regression coverage:

1. Joined `SELECT FOR UPDATE` queries also locked the Shop row, allowing a catalog price edit and
   first POS add to deadlock. Locks are now restricted to each intended model row with
   `of=("self",)`; repeated PostgreSQL races pass.
2. The enhanced New order control was outside the replaced fragments, so it could remain missing
   or disabled before the third tab. Enhanced responses now carry server-authoritative tab
   availability, the persistent control updates from it, and its button is re-enabled.

## 3. Acceptance traceability

| Feature-spec acceptance area | Evidence |
|---|---|
| Roles, authentication, CSRF, active shop, terminal trust | Policy, HTTP, UI, and M3 integration suites |
| Three stable drafts and persistence | Schema, lifecycle, concurrency, HTTP, integration, and user checks 1/4 |
| Known/repeated scan and scanner sequencing | Service, HTTP, JavaScript FIFO, concurrency, and user check 2 |
| Search, barcode-less add, quantity, removal, totals | Query/service/form/UI/integration tests and user check 3 |
| Session-bound quick-create, leading zeroes, audit, review | Signing/service/HTTP/security/integration tests and user check 5 |
| Captured price under catalog changes | Service and PostgreSQL price-race tests plus user check 6 |
| Cross-cashier read-only/takeover/audit | Policy/service/HTTP/concurrency/integration tests and user check 7 |
| Reasoned retained discard and last-tab replacement | Schema/service/HTTP/concurrency/rollback tests and user check 8 |
| Version conflicts and large integer transport | Form/service/HTTP/concurrency/integration/JavaScript tests |
| No inventory or Milestone 4 effects | Domain/concurrency/integration/scope review and user checks 3/5/8 |
| Local/offline frontend behavior | Local-asset automated checks and required user check 9 |

## 4. User frontend acceptance

Browser, visual, responsive, scanner, focus, and offline frontend verification was reserved for the
user. The user approved Milestone 3 on 2026-08-04. Separate pass/fail notes for each scenario were
not supplied; the approval is recorded as the manual acceptance decision. The checklist remains
below for future regression and shop-pilot checks.

### Setup

From PowerShell in the project folder:

```powershell
docker compose up -d db
.\.venv\Scripts\Activate.ps1
python manage.py migrate
npm run css:build
python manage.py runserver 127.0.0.1:8000
```

Prepare an owner/admin, two active cashier accounts, one active product with a known barcode, and
one active product without a barcode. Note their starting stock values and movement counts. Connect
a USB scanner configured to send Enter after each scan. Open
`http://127.0.0.1:8000/accounts/login/`.

### Retained checklist

1. **Initial workspace:** Log in as Cashier A and open **POS**. Expected: terminal `TILL-1`, a ready
   Order 1, focused barcode input, PKR amounts, and no payment/checkout/history controls.
2. **Physical scanner:** Scan the known barcode three times. Expected: one line at quantity 3,
   exact line/order totals, no duplicate lines, and scanner focus restored after each scan.
3. **Search and line editing:** Search for and add the barcode-less product; change it to a valid
   whole quantity, then try `0` and `1.5`, and remove it. Expected: valid totals update, invalid
   values are rejected, and product stock/movement counts never change.
4. **Three tabs and persistence:** Create and populate Orders 1-3, then try to create a fourth.
   Refresh, log out/in, close/reopen the browser, and restart Django. Expected: the fourth is
   unavailable/rejected and all three orders remain separate with exact items/prices/totals.
5. **Unknown quick-create:** Scan an unknown barcode with leading zeroes, cancel once, rescan, and
   create it with name/price. Expected: exact barcode, immediate line, active zero-stock product,
   Needs review visibility, one focused audit event, and no inventory movement.
6. **Captured price:** Add a product, change its catalog selling price from an authorized second
   session, rescan it in the original draft, then remove and re-add it. Expected: the retained line
   keeps its captured price; a fresh re-add captures the new catalog price.
7. **Cashier handoff:** Leave a non-empty draft as Cashier A, log out, and log in as Cashier B.
   Expected: the draft is initially read-only; explicit **Resume** enables editing, preserves its
   creator/items/totals, changes current cashier, and creates one takeover audit event.
8. **Discard:** Attempt non-empty discard without a reason, cancel, then confirm with a reason;
   also close an empty tab and finally remove the last active tab. Expected: validation and retained
   audit data are correct, stock never changes, and a fresh Order 1 replaces the final removed tab.
9. **Offline/local frontend:** Disconnect internet while Docker and Django remain running. Repeat
   scan, search, tab switch, quantity edit, handoff, and browser restart. Expected: pages remain
   styled and functional with no missing remote asset or request failure.

Also inspect the POS at the shop's normal display size and at a narrow browser width. Confirm tabs,
forms, totals, buttons, validation, and confirmation pages remain readable without overlapping or
unreachable controls. This layout check is recommended frontend confidence evidence; the nine
workflow checks above are the recommended Milestone 3 regression set.

If a physical scanner is unavailable during a future regression run, typing the barcode and
pressing Enter is only a development substitute; record the physical check for the shop pilot.

## 5. Completion decision

Implementation, independent review, automated verification, and user approval are recorded.
Milestone 3 is complete. The cashier read-only catalogue is tracked as a separate post-M3
enhancement and does not reopen the completed milestone.
