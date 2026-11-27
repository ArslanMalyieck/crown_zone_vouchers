# STATUS.md — Crown bench (verified 2026-11-27)

| # | Point | Status | Evidence / remaining |
|---|---|---|---|
| F1 | Print-view / attachments sidebar hidden | **FIXED (needs browser check)** | `crown_theme.css`: all `.layout-side-section` width/background/border/hover rules scoped to `body.cz-workspace-route` (16 selectors), sidebar selector removed from global `margin-left`, duplicate `body{padding-left}` removed (1 left). `crown_theme.js` sets the class on `frappe.router.on('change')` + `page-change` only for Workspaces/home routes. Live site 200. Playwright check not available; browser verification pending. |
| F2 | Theme duplication | **DONE** | `shaunglobal` theme files deleted (P1), `grep` shows no references. `shaunglobal/hooks.py` fixtures contain **no Workspace entry** (verified grep); `fixtures/workspace.json` is an orphan file (not synced). `crown_theme.workspace.apply_all` now runs **once per version** (`cz_workspace_version = 2026-11-27.1` in Global Defaults); second call returns `{"skipped": true}` (verified). Raw `update tabUser` SQL replaced with `frappe.db.set_value` loop. |
| F3 | Hook conflicts | **PARTIAL** | `HOOK_ORDER.md` documents order; `shaunglobal.calculate_amounts` early-returns for travel SO (`service_type`) / SI (`cz_travel_voucher`) — verified normal SI still taxed (1000 + 5% = 1050), smoke 84/84. OPEN: Quotation qty double-count bug (`rate_map += vat * qty` with amount already qty), apps-order guard/test, override table re-check. |
| F3b | air_ticket retirement | **PARTIAL** | Idempotent patch `crown_zone_vouchers.patches.v1_0.migrate_air_ticket_fields` added + migrated (live legacy non-zero rows = 0, not-migrated = 0). OPEN (safe): stop `TICKET_ANCHOR` print patching, hide `tkt_*` fields. OPEN (approval): delete fields / uninstall app. |
| F3c | airscan | **PARTIAL** | API `get_pdf_attachments_for`, Sales Order button added (`public/js/sales_order.js`), fills Ticketing items / Airline ticket rows. Parser: `pdftotext` fallback (pdfplumber failed), non-ticket PDF guard, Emirates + flydubai profiles. Measured on 14 ticket PDFs: PNR 14/14, route 14/14, ticket no ~12/14, name 12/14, departure 13/14. OPEN: duplicate-row guard when scanning twice, multi-PDF batch, OCR deps missing. |
| F3d | shaunglobal UAE fixtures | **OPEN** | 473 custom fields (module Shaun Global) remain; no hide/usage report yet. |
| P4 | Booking voucher redesign | **PARTIAL** | Existing: per-row supplier on service lines, workflow/roles/entitlement. OPEN: header `cz_supplier` still on Booking tab, traveller↔service-line link, per-item docs checklist + gate, tab labels, Accounts tab, status strip. |
| P5 / 4B | Highcharts dashboard | **OPEN** | No Highcharts; Accounting still uses native 7 charts + 4 number cards. |
| P6 / 5B | Print formats unify | **PARTIAL** | 7 invoice variants render on 1 A4 page (guarantee kept). OPEN: two CSS systems, no `_crown_base.html`, defaults `CZ Voucher`/`CZ Invoice`, air_ticket print patching, no automated PDF tests. |

## Commands run this phase
```
bench --site crown.zonetourism.ae backup --with-files
bench --site crown.zonetourism.ae migrate
bench --site crown.zonetourism.ae execute crown_theme.workspace.apply_all   # -> skipped
bench --site crown.zonetourism.ae clear-cache
supervisorctl restart crown-bench-web:* crown-bench-workers:*
```

## Pending owner decisions (data-affecting)
1. Delete `air_ticket` `tkt_*`/`yq_*` fields and uninstall app (values already 0, migration done).
2. Hide vs delete the 473 shaunglobal custom fields (UAE-only candidates).
3. Delete legacy site-only print formats (`Sales Invoice Print`, `Sales Invoice Return`, `Sales Auditing Voucher`) after export.
