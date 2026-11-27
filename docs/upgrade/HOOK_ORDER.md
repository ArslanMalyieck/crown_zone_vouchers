# HOOK_ORDER.md — Crown bench (crown.zonetourism.ae, 2026-11-27)

Apps order on the site (execution order): `frappe`, `shaunglobal`, `air_ticket`, `erpnext`, `chat`, `hrms`, `airscan`, `crown_zone_vouchers`.
`crown_zone_vouchers` is last, so its `validate` hooks run after `shaunglobal`.

## Sales Invoice

| Event | Order | Owner |
|---|---|---|
| before_insert | crown `events.sales_invoice.before_insert` | crown |
| before_validate | crown `events.sales_invoice.before_validate` | crown |
| validate | 1 `shaunglobal.custom_method.transactions.calculate_amounts` · 2 `...generated_system_nov2` · 3 `...fetch_missing_values` · 4 `crown_zone_vouchers.events.sales_invoice.validate` | both |
| on_update / on_submit / on_cancel | crown `on_change` + shaunglobal `new_purchase_invoice`, `create_todo`, `cancel_buying_transaction` | both |
| on_trash | crown `on_trash` + shaunglobal `delete_buying_transaction` | both |
| Controller class | `shaunglobal.overrides.CustomSalesInvoice` (calls `super()`) | shaunglobal |

Single source of truth:
- Normal invoices (no `cz_travel_voucher`): `shaunglobal.calculate_amounts`.
- Voucher invoices: crown `validate` runs last and owns item VAT + GST rows; shaunglobal is overwritten. Works only because crown is the last app in `apps.txt`.

Guard implemented (P2): `shaunglobal.calculate_amounts` now early-returns for voucher invoices (`cz_travel_voucher`) and travel Sales Orders (`service_type`), so crown is the only calculator for travel documents. Non-travel invoices keep using shaunglobal (verified: normal SI 1000 + 5% = 1050).

## Sales Order (= Booking Voucher)

| Event | Order | Owner |
|---|---|---|
| before_insert | crown `before_insert` (series, service access) | crown |
| before_validate | crown `before_validate` (sync items, defaults) | crown |
| validate | 1 `shaunglobal.calculate_amounts` · 2 `generated_system_nov2` · 3 `crown_zone_vouchers.events.sales_order.validate` | both |
| before_submit / before_cancel / on_cancel | crown only | crown |
| on_submit | shaunglobal `new_purchase_order` (skipped when `service_type` is set), `create_todo` | shaunglobal |
| on_cancel / on_trash | shaunglobal buying cleanup + crown status | both |

Implemented in P2 (same guard as above); crown `apply_vat` is the only calculator for travel vouchers.

## Quotation

| Event | Order | Owner |
|---|---|---|
| validate | `shaunglobal.custom_method.transactions.calculate_amounts` | shaunglobal |
| print | `Crown Quotation` (crown template) | crown |

Known bug: for items without `final_price`, `calculate_amounts` does `vat = amount * rate/100` and then `rate_map += vat * qty` — quantity is counted twice (e.g. qty 2 → 10,000 + 1,000 extra). Fix in P3 (single source): guard in shaunglobal or move Quotation to crown's VAT engine.

## Payment Entry

| Event | Order | Owner |
|---|---|---|
| before_insert | shaunglobal `set_naming_series_by_payment_type` | shaunglobal |
| before_submit | shaunglobal `change_party_account_type` | shaunglobal |
| on_submit | shaunglobal `revert_party_account_type` | shaunglobal |
| Controller class | `shaunglobal.overrides.CustomPaymentEntry` (no-op validator override) | shaunglobal |

Crown has no Payment Entry hooks; only print format `Crown Payment Voucher`.

## Other apps

- `air_ticket`: no doc_events; `after_migrate` creates SI Item fields (`tkt_fare`, `yq_*`, `apt_tax`, `fed_tax`, `xt_tax`) and string-patches print formats (`TICKET_ANCHOR`). Fragile; conflicts with the GST-only accounting rule. P3: migrate data, retire after_migrate patching.
- `airscan`: no hooks; only SI client script (Scan PDF button) + parser.
- `crown_theme`: `User.after_insert → set_default_workspace`; `boot_session → crown_theme.boot.update_boot`; app_include CSS/JS; `after_migrate` applies Accounting/Buying/Selling workspaces.

## override_doctype_class

| Doctype | shaunglobal | Others |
|---|---|---|
| Sales Invoice | `CustomSalesInvoice` (cancel + validate with `super()`) | — |
| Payment Entry | `CustomPaymentEntry` | — |
| Report | `CustomReport` | — |
| Navbar Settings | `CustomNavbarSettings` | — |

No collision today; keep this table current when adding overrides.
