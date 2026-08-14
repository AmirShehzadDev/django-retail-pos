# Retail POS Shop Operations

## Opening the shop

1. Sign in to the dedicated Windows shop account.
2. Double-click **Start Retail POS.cmd** on the desktop. It will start Docker Desktop if needed and
   open the POS when ready.
3. Sign in at `http://retailpos:8000/accounts/login/`.
4. If the page does not open after three minutes, run
   `C:\RetailPOS\deploy\Get-POSStatus.ps1` or contact the operator.
5. Confirm yesterday/last night's backup exists when the operator has shown you where to check it.

## Cashier handoff

1. Leave active customer baskets held in their order tabs.
2. Log out before leaving the computer.
3. The next cashier logs in with their own account and explicitly resumes a held basket when needed.
4. Never share passwords or leave one cashier signed in for another.

## Normal use

- Keep the host computer and Docker Desktop running.
- The scanner behaves like a keyboard and should send Enter after a barcode.
- Use the application's warning/confirmation steps; do not edit the database or Docker settings.
- Internet loss does not stop local POS work. TeamViewer may disconnect without affecting sales.
- Report any unexpected cash difference, stock balance, duplicated/missing order, or error message.

## Closing the shop

1. Complete or deliberately leave/clear each active customer basket as appropriate.
2. Log out of the POS.
3. Keep the dedicated Windows account signed in and Docker Desktop running through the scheduled
   backup time (default 23:00).
4. Do not use Docker cleanup/reset/volume commands.

## If the POS is unavailable

1. Do not repeatedly complete the same sale or recreate a possibly completed order.
2. Record the time, cashier, customer total, and visible message.
3. Check whether `http://retailpos:8000/health/` opens. If hostname setup is the problem, the
   operator can also check `http://127.0.0.1:8000/health/` on the POS computer.
4. Contact the operator. Do not restore backups or reinstall without authorization.
