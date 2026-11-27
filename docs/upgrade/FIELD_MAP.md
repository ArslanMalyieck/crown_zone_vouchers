# FIELD_MAP.md — item-level fields (Sales Order Item / Sales Invoice Item)

Audit date: 2026-11-27. Two field families coexist:

- `shaunglobal` (module "Shaun Global"): pricing + generic travel/pax fields.
- `crown_zone_vouchers` (module NULL, created by `setup/custom_fields.py`): `cz_*` booking/ticket fields.

## Canonical decision

| Concern | Canonical field | Owner | Notes |
|---|---|---|---|
| Selling price (tax inclusive) | `final_price` | shaunglobal | crown reads/writes; existing docs depend on it |
| Non-taxable / government fee | `government_fee` | shaunglobal | |
| Taxable base | `taxed_price` | shaunglobal | computed |
| GST rate | `tax_rate` | shaunglobal | Float, hidden; crown mirrors its own `cz_tax_rate` (0/5) into it |
| GST amount per row | `vat` | shaunglobal | computed |
| Supplier (per row) | `supplier` (SI) / `supplier` (SO standard field) + `supplier_name` (SO custom) | shared | crown copies supplier from SO row to SI row |
| Purchase price | `purchase_price` | shaunglobal | per-row cost |
| Purchase tax rate | `purchase_tax_rate` | shaunglobal | |
| Passenger name | `cz_passenger` | crown | legacy: `passenger`, `full_name` |
| Ticket number | `cz_ticket_no` | crown | legacy: `ticket_no` |
| Airline | `cz_airline` | crown | legacy: `airline` |
| Flight number / class | `cz_flight_no`, `cz_class` | crown | new |
| Sector / routing | `cz_sector` | crown | legacy: `routing` |
| Travel date | `cz_travel_date` | crown | legacy: `departure`, `travel_start` |
| Hotel / city | `cz_hotel_city` | crown | legacy: `hotel` |
| Room type, rooms, nights, unit rate, extra fees | `cz_room_type`, `cz_rooms`, `cz_nights`, `cz_unit_rate`, `cz_other_fees` | crown | |
| Airline tax buckets (income, not GST) | `cz_tax_sp`, `cz_tax_rg`, `cz_tax_psf`, `cz_tax_srb`, `cz_tax_yq`, `cz_tax_other`, total `cz_taxes_total` | crown | legacy: `tkt_fare`, `yq_total`, `yq_taxable`, `yq_non_taxable`, `apt_tax`, `fed_tax`, `xt_tax` |
| Manual postable row flag | `cz_manual` | crown | keeps hand-added rows on re-sync |

## Legacy → canonical migration (P3, data change — needs approval)

| Legacy field (doctype) | New field | Migration |
|---|---|---|
| `passenger`, `full_name` (SO/SI Item) | `cz_passenger` | copy when `cz_passenger` empty |
| `ticket_no` (SO/SI Item) | `cz_ticket_no` | copy when empty |
| `airline` (SO/SI Item) | `cz_airline` | copy when empty |
| `routing` (SO/SI Item) | `cz_sector` | copy when empty |
| `hotel` (SO/SI Item) | `cz_hotel_city` | copy when empty |
| `tkt_fare`, `yq_total`, `yq_taxable`, `yq_non_taxable`, `apt_tax`, `fed_tax`, `xt_tax` (SI Item, air_ticket) | `cz_tax_*` | verified all-zero on live before rollback; migrate values then delete fields |
| `supplier_name` (SO Item) | `supplier` | keep both; sync in `fill_item_defaults` (already) |

After migration, hide/deprecate the legacy fields (do not drop columns until prints/reports are confirmed).

## Collisions found

- `supplier`: exists on SI Item (custom, Shaun Global) and SO Item (standard DocField). Crown does not redefine it.
- `tax_rate`: hidden Float (Shaun Global) vs `cz_tax_rate` Select (crown). Crown treats `cz_tax_rate` as source of truth and writes the Float copy for shaunglobal reports.
- `passenger`/`cz_passenger`, `ticket_no`/`cz_ticket_no`, `airline`/`cz_airline`, `routing`/`cz_sector`, `hotel`/`cz_hotel_city`: same meaning, different names. Prints currently use `cz_*`; old documents may still have only legacy names.
- `air_ticket` fields (`tkt_*`, `yq_*`, `apt_*`, `fed_*`, `xt_*`) are moduleless and recreated by `air_ticket/migrate.py::after_migrate`; they conflict with the "only GST is tax" rule. Retire in P3.

## Print format dependency

- Crown prints (`Crown Sales Invoice`, `Crown Sales Order Voucher`, `Crown Payment Voucher`, `Crown Quotation`) and CZ formats read the canonical set above.
- Legacy CZ formats read `cz_*` + `final_price`/`vat`; keep those fields until formats are retired.
