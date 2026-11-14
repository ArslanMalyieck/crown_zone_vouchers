# Crown Zone Vouchers (Frappe / ERPNext v15-v16)

Travel sales vouchers for Crown Zone Tourism & Travels Agency (Karachi, PKR):
Airline, Hotel, Visa, Transport, Umrah, Hajj, **Tour** (desert safari / city tour / activities; voucher no. CZ-ACT-YYYY-0001).

**Voucher = Sales Order** (Draft -> Submit = *Posted*).
**Invoice = Sales Invoice**, prepared manually by Accounts from the posted voucher (no auto invoice).

## Install (separate app, 8004 site)
```bash
cd ~/frappe-bench
bench get-app /path/to/crown_zone_vouchers        # or: bench get-app <git-url>
bench --site <site-on-8004> install-app crown_zone_vouchers
bench --site <site-on-8004> migrate
bench build --app crown_zone_vouchers && bench restart
```
Re-runnable setup (roles, seed data, custom fields, permissions, print formats, workspace):
`bench --site <site> execute crown_zone_vouchers.setup.install.run_all`
Errors in any setup step are written to Error Log ("Crown Zone Vouchers setup: ...").

## What gets created
* DocTypes: Travel Service Type, Travel Voucher Settings (brand/logo/SRB/default visa docs), Airline Tax Code,
  child tables Voucher Traveller / Flight Segment / Air Ticket / Air Tax / Hotel Stay / Service Line /
  Document Checklist / Transport Trip / Travel Service Term.
* Sales Order: Service Type picker + tabs (Booking, Passengers/Guests/Pilgrims, Flights & Tickets, Fare/ETR Taxes,
  Hotel/Room Allocation, Vehicle & Trip, Services & Documents, Sales & Purchase, Posting). Tabs show per service.
* Item-table columns from the PDF (hidden unless the service needs them): Airline - Passenger, Ticket No., Airline,
  Sector, Travel Date. Hotel - Hotel/City, Room Type, Lead Guest, Rooms, Nights, Rate, Other Fees.
  Items are **auto-built** from tickets / rooms / service lines on save.
* Roles: Travel Sales (create/edit/post vouchers, no invoice access), Travel Accounts (read vouchers incl. cost/profit,
  create invoices, hold/release), Travel Manager (cancel, credit/debit notes).
* Voucher numbers ATV/HTV/VSV/TRN/UMH/HAJ-YYYY-00001; invoice numbers INV-AIR/HTL/VISA/TRN/UMH/HAJ-YYYY-00001.
* Print formats (23): 7 customer vouchers (incl. CZ Tour Voucher) (no amounts, QR, terms, Prepared/Posted By), 14 invoices
  (Airline, Hotel, Visa, Transport, Umrah, Hajj, Tour x Without/With Tax) + dispatchers **CZ Voucher** and **CZ Invoice**
  (set as default print formats; pick the right layout automatically).
* Report "Posted Voucher Queue" + workspace "Travel Vouchers" (Invoice Pending / On Hold cards).

## Business rules enforced
* Posting needs: Booking Status = Confirmed, supplier, sales amount, service-specific mandatory data.
* Posting stamps Posted By / Posted On; submitted voucher is locked.
* Invoice only from a posted voucher; one active invoice per voucher; blocked while voucher is On Hold.
* "Without Tax" invoice cannot contain tax rows; "With Tax" must.
* Credit / debit notes need Travel Manager + Correction Reason. Track Changes is your audit trail
  (turn on "Track Changes" for Sales Order and Sales Invoice in Customize Form).
* Supplier cost / profit / internal remarks have print_hide and are never in the CZ print formats.

## After install - configure
1. Travel Voucher Settings: confirm company name, address, phones, SRB No., logo (blank = Company logo).
2. Travel Service Type: confirm default Item per service; set *Default Tax Template* for With-Tax invoices.
3. Airline With-Tax invoice: create a Sales Taxes and Charges Template with rows, e.g.
   Actual "Airline Taxes (ETR)", Actual "Passenger Service Fee (PSF)", and "SRB Sales Tax on PSF" as
   *On Previous Row Amount* (rate configurable). Row descriptions are printed as-is, so no double counting.
4. Assign roles to users.

## Assumptions to verify
* Airline supplier net = fare + airline taxes - commission + WHT-on-commission (formula in events/sales_order.py).
* Visa sample invoice was in AED in the PDF; the app is PKR-only per the design rules.
* Voucher series options are added to the naming_series Select of Sales Order / Sales Invoice.
* Service Type names (Airline, Hotel, Visa, Transport, Umrah, Hajj, Tour) are used in code - do not rename.
* Service Type is mandatory on Sales Order (site is dedicated to travel). Remove `reqd` in
  setup/custom_fields.py if normal sales orders are also needed.
