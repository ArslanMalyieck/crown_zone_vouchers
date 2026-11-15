# Crown Zone Vouchers — Sales Invoice Print Field Map

**Scope:** verified ERPNext v15 Sales Invoice print context and the linked Sales Order voucher for the Airline ticket invoice. This map is based on repository source and site metadata; no schema change is proposed.

## Discovery sources

- `crown_zone_vouchers/events/sales_invoice.py::_copy_item_details`
- `crown_zone_vouchers/events/sales_order.py::sync_items`
- `crown_zone_vouchers/setup/custom_fields.py::item_fields`
- `crown_zone_vouchers/crown_zone_vouchers/doctype/voucher_air_ticket/voucher_air_ticket.json`
- `crown_zone_vouchers/crown_zone_vouchers/doctype/voucher_flight_segment/voucher_flight_segment.json`
- `crown_zone_vouchers/templates/print/invoice_airline.html`
- ERPNext v15 `Sales Invoice` / `Sales Invoice Item` metadata at `cz-test.localhost` and `crown.zonetourism.ae`.

## Airline ticket table mapping

| Display column | Actual field/link | Source | Missing behavior |
|---|---|---|---|
| Payer / Bill To | `Sales Invoice.customer_name` | Invoice | Required by invoice |
| Payer address | `Sales Invoice.address_display`; fallback `customer_address` / customer primary `Address` via `cz_address(doc)` | Invoice/customer | Address row omitted if no address |
| Invoice No. | `Sales Invoice.name` | Invoice | Always present |
| Invoice Date | `Sales Invoice.posting_date` | Invoice | Always present |
| Due Date | `Sales Invoice.due_date` | Invoice | “On receipt” |
| Currency | `Sales Invoice.currency` | Invoice | PKR fallback for display only |
| Voucher No. | `Sales Invoice.cz_travel_voucher` | App custom field | Row omitted if blank |
| Booking Ref. | linked `Sales Order.cz_booking_reference` via `cz_voucher(doc)` | Voucher | “—” |
| Customer PO / Ref. | `Sales Invoice.po_no` | Invoice | “—” |
| S/No | Jinja `loop.index` | Items | Always |
| Passenger | `Sales Invoice Item.cz_passenger` | Invoice item, copied from Sales Order Item (`sync_items`) | Item description fallback |
| Ticket No. | `Sales Invoice Item.cz_ticket_no` / `ticket_no` | Invoice item | Blank |
| Airline | `Sales Invoice Item.cz_airline`; voucher ticket `airline` fallback | Invoice/voucher | Blank |
| Flight | linked `Sales Order.cz_flight_segments[0].flight_no` | Voucher child table | Blank |
| Class (CL) | linked `Sales Order.cz_flight_segments[0].cabin_class` | Voucher child table | Blank |
| Departure Date | `Sales Invoice Item.cz_travel_date`; segment `travel_date` fallback | Invoice/voucher | Blank |
| Sector | `Sales Invoice Item.cz_sector`; `cz_sector(voucher)` fallback | Invoice/voucher | Blank |
| Fare | `Sales Invoice Item.net_amount` / `amount` | Invoice | 0.00 |
| Taxes (row-level) | **Not stored per Sales Invoice Item row in this app** | — | Column omitted; invoice-level tax summary is used |
| Amount | `Sales Invoice Item.amount` | Invoice | 0.00 |
| PNR | linked voucher ticket `pnr` (first ticket) | Voucher | “—” |
| Subtotal | `Sales Invoice.net_total` | Invoice | 0.00 |
| Tax breakup | `Sales Invoice.taxes` (child rows) | Invoice | Omitted without tax |
| Total taxes | `Sales Invoice.total_taxes_and_charges` | Invoice | 0.00 |
| Grand total | `Sales Invoice.grand_total` | Invoice | 0.00 |
| Amount in words | `Sales Invoice.in_words` | ERPNext | Omitted if blank |
| Paid / outstanding | `Sales Invoice.paid_amount`, `outstanding_amount` | ERPNext | Not shown for unsaved prints where not meaningful |
| Payment / inquiries | app constants `accounts1@zonetourism.ae`, `+92 327 8447933` | Provided business facts | Always shown |

## Verified field groups

- `Sales Invoice`: `name`, `posting_date`, `due_date`, `currency`, `customer`, `customer_name`, `customer_address`, `address_display`, `po_no`, `items`, `net_total`, `taxes`, `total_taxes_and_charges`, `grand_total`, `in_words`, `paid_amount`, `outstanding_amount`, `status`, app fields `cz_travel_voucher`, `cz_service_type`, `cz_invoice_tax_type`.
- `Sales Invoice Item`: standard `item_name`, `description`, `qty`, `rate`, `amount`, `net_amount`, `sales_order`, `so_detail`; app fields `cz_passenger`, `cz_ticket_no`, `cz_airline`, `cz_sector`, `cz_travel_date`.
- `Sales Order` voucher child tables: `cz_air_tickets` (passenger_name, airline, pnr, ticket_no, ticket_date, supplier_fare, taxes_total, ticket_gross, sale_amount_pkr, etc.) and `cz_flight_segments` (sector_from, sector_to, airline, flight_no, cabin_class, travel_date, departure_time, arrival_time, status, etc.).
- Existing `_copy_item_details` copies only the listed fields if present; ticket/passenger mapping is primarily created by the Sales Invoice mapping from Sales Order Item. The print map must not assume fields that are absent on a site; use blank fallbacks.

## Deliberate omissions / limitations

- **Per-passenger tax**: Sales Invoice does not carry a row-level tax amount for Airline items in the current app. The invoice-level `taxes` table is the source of truth. No proportional allocation or voucher supplier tax is presented as customer tax.
- **Page Total / Cumulative Total**: the app invoices are single-page for normal data; totals are displayed once. Multi-page tables repeat the header, but no fabricated page/cumulative subtotal is shown.
- **Service Charges / CC**: no verified Sales Invoice field in this app; omitted.
- **Multiple flight segments**: the Airline table displays the first linked segment (`[0]`) as the flight/class/departure summary. If multiple segments exist, a future itinerary block can be added only after business confirmation; this map does not invent a per-passenger segment link.
- **Tax IDs**: NTN/CNIC is shown only when `with_tax` and `doc.tax_id` exists; Without Tax invoices intentionally omit it.
- **Address**: `cz_address(doc)` falls back to the linked Address/customer primary address. If no address exists, the row is omitted rather than fabricated.

## Sample-shape QA fixture

The supplied `S H PACKAGES (1).pdf` is a visual reference only. For QA, use a disposable test invoice with five synthetic passenger rows; values may mirror the sample shape (fare 1,625,820 + taxes 331,180 = 1,957,000) but must be generated from test documents, not hardcoded in production. The actual row-to-tax breakdown is not available on Sales Invoice Item; test invoice-level totals and row order/identity instead.
