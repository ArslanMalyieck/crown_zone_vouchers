# AUDIT_airscan.md

## Dependency / hooks
- No `doc_events`; `doctype_js`: Sales Invoice (Scan PDF button). Parser: `airscan/parser.py`
  (`get_pdf_text`, `extract_ticket_fields`), API in `airscan/api.py`.
- No `required_apps` declared. It works standalone but the new Sales Order flow needs
  `crown_zone_vouchers` fields.

## P3 changes (safe, no data migration)
- API: added `get_pdf_attachments_for(doctype, docname)`; `get_pdf_attachments(docname)` kept as a
  Sales Invoice wrapper.
- Hooks: added `"Sales Order": "public/js/sales_order.js"`.
- New `public/js/sales_order.js`: on a draft Booking Voucher with a service type, adds
  **Scan PDF > Air Ticket PDF**, lists attached PDFs, parses the ticket, shows a review dialog and
  appends:
  - Ticketing service: an Items row (`cz_manual=1`, passenger, ticket no, airline, sector,
    travel date, flight no, supplier from voucher);
  - Airline service: a `Voucher Air Ticket` row (passenger, airline, PNR, ticket no).
- It never saves automatically; the user reviews and saves.

## Test plan
1. Attach a ticket PDF to a draft Ticketing Sales Order.
2. Scan PDF > Air Ticket PDF > pick attachment > Add.
3. Verify a new Items row exists with parsed values and blank selling price (fill manually).
4. Repeat on an Airline voucher; verify `cz_air_tickets` row.
5. `node --check public/js/sales_order.js`; no console errors.

## Known limits
- Parser returns text fields only; prices/fare are not filled (manual entry).
- Multiple passengers in one PDF: first passenger is used (same as the Sales Invoice flow).
