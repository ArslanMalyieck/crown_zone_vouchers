# Crown Zone Vouchers — Enterprise Changes (Phase 1–4)

## Delivered

### 1. Booking role and service entitlement

- New role: `Booking Voucher User`.
- Permissions: Sales Order read/write/create/print/email/report/export; no Sales Invoice, no cancel/amend/delete, no direct submit.
- `Travel Sales` role is retained for backward compatibility and also receives the service restriction.
- Users are assigned service types on the User form:
  - Field: **Booking Service Types**
  - Child table: **Booking Service Assignment**
  - Each row: `service_type`, `enabled`.
- Server-side guard: `crown_zone_vouchers/events/sales_order.py::validate_service_access`.
  - Applied on create, save, and submit.
  - `Administrator`, `System Manager`, `Travel Manager` bypass.
  - Missing assignment denies booking.
  - Direct service mutation is rejected even when using the REST/client API.
- Client service picker filters by assignment (UX only; server is authoritative).

### 2. Accounts approval workflow

- Native Frappe Workflow: **Crown Voucher Approval** on Sales Order.
- States:
  - `Draft` (docstatus 0)
  - `Pending Accounts Approval` (docstatus 0)
  - `Approved` (docstatus 1)
  - `Rejected` (docstatus 0)
- Transitions:
  - Booking user: **Submit for Approval** (Draft → Pending)
  - Travel Accounts: **Approve & Post** (Pending → Approved; native submit)
  - Travel Accounts: **Reject** (Pending → Rejected; remarks required)
  - Booking user: **Return to Draft** (Rejected → Draft)
- Self approval is disabled on approve/reject.
- Approval stamps `cz_approved_by` and `cz_approved_on`.
- `cz_approval_remarks` is required on rejection.
- Sales Invoice validation requires an approved, posted voucher and blocks Pending/Rejected vouchers.
- Invoice duplicate check is protected by a `SELECT ... FOR UPDATE` lock on the Sales Order row.
- Existing submitted vouchers were backfilled to `Approved` during migration; draft vouchers to `Draft`.
- `Booking Voucher User` has no `submit` permission; posting only occurs through the Accounts workflow transition.

### 3. Premium invoice design

Existing print formats were upgraded in place (no duplicate formats):

- `invoice_airline.html`
- `invoice_hotel.html`
- `invoice_generic.html`
- Shared: `_macros.html`, `_css.html`, `_inv_totals.html`

Design features: navy/brass brand band, invoice identity panel, status badge, bill-to/booking reference strip, service-specific fact cards, structured line table, tax/VAT summary, amount in words, payment/important panels, signature line and footer. A4 page height is used; the action banner is hidden in print/PDF.

All seven service invoice variants including the Airline With Tax variant render as **1 A4 page** in the test site PDF set.

### 4. Workspace and invoice-pending analysis

Updated `Travel Vouchers` workspace with:

- Total Posted Vouchers
- Draft Vouchers
- Pending Accounts Approval
- Approved Vouchers
- Invoice Pending
- Invoiced Vouchers
- On Hold
- Rejected Vouchers
- Cancelled Vouchers
- Void Invoices
- New Voucher shortcuts for all seven services
- **Invoice Pending Vouchers** report shortcut
- Pending Approval Queue, Posted Voucher Queue, All Vouchers, Invoices

New report: **Travel Voucher Invoice Pending**

- Approved/posted vouchers with no active Sales Invoice.
- Link columns and View Voucher action.
- Accounts can create the invoice from the report action.
- Uses `frappe.get_list` for normal read permissions.

## Admin steps after deployment

1. Open User → select the operational user.
2. Add role **Booking Voucher User**.
3. In **Booking Service Types**, add only the services that user may book.
4. Keep invoice users on **Travel Accounts** (or Travel Manager); do not give them Booking Voucher User unless they also need booking access.
5. Existing `Travel Sales` users will be restricted by the same service list; assign their services before they create/save.
6. Accounts users should use the workflow buttons on the voucher: **Approve & Post**, **Reject** (with remarks).

## Verification evidence

| Test | Result |
|---|---|
| Baseline smoke `crown_zone_vouchers.tests.smoke.run` | 70 checks, 0 failed |
| Enterprise smoke `crown_zone_vouchers.tests.enterprise_smoke.run` | 14 checks, 0 failed |
| Service assignment create/deny/direct mutation | Passed |
| Self approval / unapproved posting | Blocked |
| Accounts approve & post | Passed |
| Duplicate active invoice | Blocked |
| Invoice status submit → Issued → cancel → Void | Passed |
| Rejection without remarks | Blocked |
| Invoice-pending report | Passed |
| Premium PDFs (7 services + Airline With Tax) | 1 A4 page each |

## Deployment notes

- Backup: `20261115_150508-crown_zonetourism_ae-{database,public,private,files}` under the site's `private/backups`.
- Live migration completed with no Crown setup errors.
- `bench build --app crown_zone_vouchers` and supervisor restart completed.
- Live metadata: workflow active; existing submitted vouchers approved; existing drafts draft; 7 invoice-pending vouchers; zero setup errors.
- Live had no Sales Invoices linked to vouchers at deploy time; PDF page-by-page QA was performed on the disposable test site with the same app code and print formats.

## Known limitations

- The test site's PDF `Get PDF` path logged a cosmetic wkhtmltopdf asset warning; PDFs were rendered for QA by removing the standard `print.bundle` link before generation. The app's own inline print CSS is complete. The live site uses the public asset host.
- Empty item-table rows are intentionally kept to preserve the full-page frame for short invoices.
- Page numbers remain limited by the wkhtmltopdf renderer and are not added.
- Legacy site-only formats (`Sales Auditing Voucher`, `Sales Invoice Print`, `Sales Invoice Return`) were not modified or deleted.
- Existing `Travel Sales` users need service assignments after this deployment.

## Phase 5 � Item-level GST, item-driven vouchers, Ticketing

### VAT engine (crown-owned)

- crown_zone_vouchers/events/vat.py applies the shaunglobal-style method to voucher Sales Orders:
  - Selling Price is tax inclusive.
  - Taxable = (Selling Price - Non Taxable) / (1 + rate); VAT = Taxable x rate.
  - Item Rate = Selling Price - VAT.
  - GST is the only document-level tax row (Actual, GST 5%); every airline / service charge
    stays on the item row.
  - One row per rate; the rounding residual is absorbed so the grand total always equals the
    sum of Selling Prices (fixes the 1-paisa short totals).
- Runs after other app hooks on voucher Sales Orders only. Existing Sales Invoice calculations,
  rates and tax rows remain with shaunglobal / ERPNext; Crown does not recalculate them.
- Invoice Type (cz_invoice_tax_type) is now derived from the data and read-only.
- Zero-rated services (Airline, Hotel, Ticketing) default to 0% unless a row sets its own rate.

### Item-level fields

- Shared with shaunglobal when present (never overwritten): inal_price (Selling Price),
  government_fee (Non Taxable), 	axed_price, 	ax_rate, at, purchase_price,
  purchase_tax_rate, supplier.
- Crown-owned: cz_tax_rate (0/5), cz_tax_sp, cz_tax_rg, cz_tax_psf, cz_tax_srb,
  cz_tax_yq, cz_tax_other, cz_taxes_total, cz_flight_no, cz_class, cz_manual.
- supplier column is created on Sales Order Item so every line can have its own supplier.

### Voucher items

- Items are the posting input for every voucher type; the service tabs still generate them.
- Hand-added rows are kept (cz_manual) and the same item may appear twice at different
  rates / suppliers (llow_multiple_items enabled).
- Airline / Hotel child rows carry their own supplier, purchase amount, GST rate and
  non-taxable amount.
- Ticketing uses the Items grid directly (no tab rows).

### Ticketing service

- New Travel Service Type Ticketing (voucher TKV-, invoice INV-TKT-, item Airline Ticket).
- Voucher print: passengers, fare / taxes / amount per ticket, taxes breakup, totals.
- Invoice print: PDF-style statement with per-page totals, cumulative totals, taxes breakup,
  net total, amount in words and signatures; 14 tickets on page 1 and 20 per page after.

### Verification

- 	ests/smoke.py: 82/82 (cz-test and a restored copy of live with shaunglobal active).
- 	ests/enterprise_smoke.py: 14/14.
- 	ests/print_probe.py: 15/15 (pagination, breakup, PDF).
