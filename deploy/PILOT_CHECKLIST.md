# Milestone 7 Required Shop Pilot Checklist

**Release version:** __________  **Date:** __________  **Operator:** __________  
**Owner:** __________  **Starting cash:** __________  **Ending cash:** __________

Use an agreed test product/order plan so every test transaction can be identified and reconciled.
Record Pass/Fail and notes. These checks require the real Windows host, browser, hardware, or shop
operation and are not replaced by automated tests.

## A. Deployment and recovery gate

- [ ] **Windows restart:** restart the host, sign in, wait for Docker Desktop, and confirm POS opens
      without manually starting containers. Result/notes: ______________________________
- [ ] **Offline:** disconnect internet, reload/login, use Products & Stock, POS, Orders, Returns,
      Reports, and Audit. No external asset/service error appears. Result: ______________
- [ ] **Daily task:** run the scheduled backup task and confirm a new non-empty dump plus SUCCESS log
      entry. Result: _________________________________________________________________
- [ ] **Clean restore:** restore that dump only in an isolated clean test installation; confirm
      health, owner login, latest order, sample stock, report totals, and inventory reconciliation.
      Test location/result: ___________________________________________________________
- [ ] **Update rehearsal:** install a versioned test/release package, confirm its displayed health
      version and retained pre-update dump. Result: ___________________________________

All five deployment/recovery checks are required before live pilot approval.

## B. Physical and workflow gate

- [ ] Scan a known barcode with the real USB scanner; one item is added and focus is ready again.
- [ ] Scan an unknown barcode; quick-create it, add it, and confirm Needs review/audit behavior.
- [ ] Complete one cash sale with positive Change and one with negative Change; Orders and daily
      report show the signed values correctly.
- [ ] Hold a populated draft, log out, sign in as another cashier, resume it, and confirm handoff
      attribution/audit.
- [ ] Use two browser sessions/clients against the host for the documented concurrent-checkout
      scenario; stock, order numbers, and movements remain consistent.
- [ ] Complete an acknowledged negative-stock sale; confirm warning, audit event, negative-product
      review filter, and inventory reconciliation.
- [ ] Process a linked partial return and then remaining full return; verify refund and RESTOCK stock.
- [ ] As owner/admin, void an eligible completed sale; verify refund, status, stock, and audit.
- [ ] Run `docker compose run --rm web python manage.py reconcile_inventory`; it reports no mismatch.

Workflow notes/exceptions: ____________________________________________________________

## C. Supervised live pilot

- [ ] Record opening cash and selected opening product counts.
- [ ] Operate the POS for the agreed supervised period: ______________________________
- [ ] Compare completed sales, returns, voids, signed Change, and cash movement to physical cash.
- [ ] Compare selected ending product counts to system stock and movement history.
- [ ] Every discrepancy is either zero or has a documented, accepted explanation.
- [ ] Owner approves normal use. Owner/signature: __________________ Date: _____________

Unexplained cash discrepancy: PKR __________  Unexplained stock discrepancy: __________

Milestone 7 cannot be marked user-verified while either unexplained value is non-zero or a required
deployment/recovery/workflow check has failed.
