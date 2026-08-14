# Milestone 4.1 Feature Specification - Compact POS Workspace Redesign

**Status:** Approved

**Version:** 1.1

**Prepared:** 2026-08-06

> **Follow-on refinement:** Active-order removal behavior is now specified separately in the
> approved [Milestone 4.2 feature specification](../m4.2-clear-orders/feature-spec.md). It supersedes inherited
> discard wording with **Clear order** and **Close tab**; this M4.1 document remains the historical
> specification for the compact workspace redesign.

## 1. Objective

Redesign the existing POS workspace so it feels like a fast retail checkout rather than an
administration form. The redesign changes presentation and interaction layout only; approved
barcode, cart, draft, checkout, payment, inventory, audit, order-history, permission, and offline
behavior remains unchanged.

The primary target is one grocery/retail checkout computer at 1366x768 and 100% browser zoom.

## 2. Design direction

The approved reference direction is:

- the disciplined product/cart separation and fixed payment summary of reference image 1;
- the clean spacing, large interaction targets, and restrained modern appearance of image 2; and
- the compact information density of image 3 without its dated colors, small controls, or clutter.

Because this is a barcode-first grocery shop, the cart remains dominant. The selected order uses
approximately 65% of available width and the fallback product catalogue uses approximately 35%.

## 3. Actors and permissions

- Owner, admin, and cashier receive the same POS workspace structure when authorized to use POS.
- Existing current-cashier ownership, takeover, read-only, active-user, shop, and terminal rules do
  not change.
- Read-only orders show their contents without quantity, remove, scan, add, or checkout mutations.

## 4. Dedicated POS shell

The POS uses a dedicated compact shell instead of the normal application header/navigation.

The top toolbar contains only:

- shop/POS identity;
- up to three compact order tabs and New order;
- links to Orders and the read-only Products catalogue;
- current cashier identity; and
- Exit POS, returning to the normal authenticated home page where Log out remains available.

User management, inventory management, and shop settings remain reachable outside POS and do not
consume POS toolbar space.

## 5. Desktop layout

Below the toolbar, the workspace is a two-column bounded layout:

### 5.1 Selected order - approximately 65%

From top to bottom:

1. one compact scanner row with persistent scanner focus behavior;
2. a dense cart header showing item count and current cashier;
3. internally scrolling cart lines; and
4. a fixed checkout dock containing Total, Cash received, signed Change, and Complete sale.

Each editable cart line shows, on one row where space permits:

- product name and barcode snapshot;
- unit price;
- always-visible minus/current/plus quantity control;
- line total; and
- compact Remove action.

Shortage/inactive warnings use a compact inline row or label and must not enlarge every normal line.

### 5.2 Product catalogue - approximately 35%

The catalogue contains:

1. one fixed search field;
2. a compact two-column product grid; and
3. internal scrolling for additional results.

Each product tile shows name, price, current stock, barcode/SKU when useful, and one clear Add
action. Product photos and category navigation are not required in this refinement.

### 5.3 In-place completion and Recent sales

When JavaScript enhancement is available, Complete sale must not navigate away from POS. After the
existing atomic checkout succeeds:

1. the completed draft's slot is replaced by the fresh empty order already created by checkout;
2. the tabs, selected order, catalogue stock, and Recent sales area update in place;
3. the other active drafts remain unchanged;
4. scanner focus returns to the fresh order; and
5. a compact success toast shows the permanent order number, total, and signed Change.

The bottom of the catalogue pane contains a fixed compact **Recent sales** area showing the latest
three completed cash sales for the current shop, newest first. Each row shows order number,
completion time, total, prominently signed/coloured Change, and a View link to the immutable order
detail. It is visible to every POS role under the existing same-shop completed-order permission.

Recent sales is informational: it does not add edit, void, return, reprint, or undo controls. A
failed checkout leaves the draft and entered context intact where safe, displays an error, and does
not add a recent row. Repeated submissions retain the existing idempotent completion behavior.

With JavaScript unavailable, the existing POST and completed-order-detail redirect remain the safe
progressive-enhancement fallback.

## 6. Typography and density

The current typography is too large for the target checkout viewport. Use this compact hierarchy:

| Element | Target size |
|---|---:|
| Default UI/body text | 14px |
| Secondary barcode/stock/helper text | 12px |
| Toolbar and order-tab labels | 13-14px |
| Product and cart-line names | 14px |
| Section labels | 12px, semibold |
| Scanner, search, cash inputs | 14px |
| Normal buttons | 14px |
| Workspace/POS title | 18px maximum |
| Checkout Total value | 24px |
| Complete sale label | 14-16px |

No essential text may be smaller than 12px. Large display typography is limited to the checkout
total; product names, panel headings, tabs, and ordinary buttons must not compete with it.

Use compact 8/12/16px spacing, approximately 48-56px normal cart rows, and 40-44px interactive
controls. Do not reduce touch/click targets merely to fit more text.

## 7. Visual hierarchy and color

- Use a quiet neutral workspace with one existing brand-blue interaction color.
- Reserve emerald/green for Complete sale and successful state, amber for warnings, and red for
  shortage/destructive actions.
- Reduce nested cards, rounded containers, heavy shadows, and repeated borders.
- Use subtle row dividers and whitespace instead of placing every cart line inside a large card.
- Total and Complete sale are the strongest elements. Scanner/search are the next strongest.
- Fixed toast messages remain above the workspace and never consume its height.

## 8. Responsive behavior

- At 1366x768/100%, the complete-sale dock is reachable without whole-page scrolling.
- Cart and catalogue may scroll only within their bounded content regions.
- Below the desktop breakpoint, columns may stack and normal page scrolling is allowed.
- The compact desktop requirement does not require a separate mobile POS application.

## 9. Required states

The visual design must cover:

- empty order;
- populated editable order;
- three active order tabs;
- read-only/takeover order;
- inactive retained product;
- projected negative-stock warning;
- quantity one with disabled decrease;
- checkout with positive, zero, and negative Change;
- no catalogue result; and
- zero, one, and three recent completed sales;
- a successful in-place completion with a fresh same-slot order;
- an enhanced checkout failure that retains the draft; and
- fixed success, warning, and error toasts.

## 10. Explicit exclusions

- Product image upload/storage and image-based catalogue management.
- Categories, favorites, promotions, discounts, customers, tax, tables, dine-in, shipping, and
  multiple payment methods.
- Changing barcode, cart, checkout, payment, inventory, audit, or order-history business rules.
- Editing, undoing, voiding, or returning an order from Recent sales.
- A dashboard/sidebar, analytics, animated decoration, external fonts, or runtime network assets.
- Frontend implementation before this specification and wireframe are approved.

## 11. Acceptance criteria

1. At 1366x768/100%, toolbar, scanner, cart, checkout dock, search, and product catalogue are visible
   without whole-page scrolling.
2. The order occupies approximately 65% and catalogue approximately 35% of desktop workspace width.
3. Default UI text is visually compact, with ordinary content around 14px and only Total at 24px.
4. Cart lines are dense, readable, and expose all approved controls without an Update button.
5. The checkout dock stays visible regardless of cart/catalogue length or toast presence.
6. Catalogue tiles show sufficient text information without requiring product images.
7. Existing scan, search/add, quantity, removal, drafts, checkout, signed Change, warning, and
   permission behavior does not regress.
8. The interface remains fully styled and functional while the computer is offline.
9. Automated template/JavaScript/backend regression checks pass, while actual viewport, scanner,
   keyboard, and visual acceptance remains user-owned.
10. Enhanced checkout stays on POS, selects the fresh same-slot draft, refreshes stock and Recent
    sales, shows order/total/Change confirmation, and restores scanner focus.
11. Recent sales shows at most three newest same-shop paid completed orders with View links and
    clearly distinguished positive, zero, and negative Change.
12. Enhanced checkout errors do not clear the draft or navigate away; no-JavaScript checkout keeps
    the existing safe detail redirect.

## 12. Approval gate

After user approval, create `docs/milestones/m4.1-pos-workspace/technical-design.md`, then `docs/milestones/m4.1-pos-workspace/development-tasks.md`, run the
mandatory whole-project planning review, and only then begin implementation.
