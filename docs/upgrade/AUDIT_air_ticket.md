# AUDIT_air_ticket.md

## Dependency / hooks
- No `doc_events`, no scheduler. `doctype_js`: Sales Invoice (`public/js/sales_invoice.js`).
- `after_migrate = air_ticket.migrate.after_migrate`:
  - creates Sales Invoice Item fields: `tkt_section_break`, `tkt_fare`, `yq_total`, `yq_taxable`,
    `yq_non_taxable`, `apt_tax`, `fed_tax`, `xt_tax` (moduleless custom fields);
  - string-patches print formats using `TICKET_ANCHOR` (fragile; silently fails if HTML changes);
  - `ensure_travel_invoice_format()`.

## Conflict with the accounting rule
ONLY GST is a tax row. `air_ticket` keeps airline-specific amounts as item fields, which is
compatible, but its print patches render them as a tax block and its JS derives
`government_fee`/`final_price`/`tax_rate` on the Sales Invoice item. Crown now owns the
ticketing data model (`cz_*`) and VAT engine, so air_ticket is redundant.

## Live data check (2026-11-27)
All `tkt_*` / `yq_*` / `apt_tax` / `fed_tax` / `xt_tax` values on Sales Invoice Item are 0.

## Migration added (safe, idempotent)
`crown_zone_vouchers.patches.v1_0.migrate_air_ticket_fields`
- `yq_total` -> `cz_tax_yq`
- `apt_tax + fed_tax + xt_tax` -> `cz_tax_other`
- recalculates `cz_taxes_total`
Only fills empty `cz_*` fields; never overwrites.

## Retirement plan (needs owner approval — deletes schema/data)
1. Run migration + `migrate` twice; verify no non-zero legacy values remain.
2. Remove `air_ticket` print-format patching (`TICKET_ANCHOR`) and `ensure_travel_invoice_format`.
3. Delete the item custom fields (or hide first) after confirming all formats use `cz_*`.
4. Uninstall `air_ticket` from crown site / remove from bench, or keep as empty shim.
