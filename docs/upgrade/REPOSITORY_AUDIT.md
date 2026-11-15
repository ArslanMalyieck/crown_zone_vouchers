# Crown Zone Vouchers — Repository Architecture Audit (Phase 0)

**Date:** 15 November 2026  
**Branch:** `upgrade/enterprise-v15`  
**Base commit:** `ff4ccdaad213b8db273aaf4067cb068894782508` (`main`)  
**Working tree:** clean at audit start; only documentation files added by this audit.  
**Scope:** read-only source and site-metadata inspection. No application code, schema, workflow, migration or production data changes were made.

## 1. Executive summary

The app is a working, custom Sales Order voucher layer for seven travel services (Airline, Hotel, Visa, Transport, Umrah, Hajj, Tour), with manual Sales Invoice creation. The core lifecycle is implemented and covered by a 70-check smoke test (baseline **70/70 passed**). Print coverage is broad: 23 app-managed formats (7 vouchers, 14 service/tax invoice variants, 2 dispatchers).

The main enterprise gaps are confirmed:

- **No approval workflow exists.** There is no `Workflow` for Sales Order or Sales Invoice. "Posting" is native Sales Order submit; it is not an Accounts approval step.
- **No per-user service entitlement exists.** `Sales Order.service_type` is a Link to `Travel Service Type`; there is no User Permission, assignment table, or server-side service restriction. Any user with Sales Order create access can create any service.
- **No "Booking Voucher User" role exists.** Existing roles are `Travel Sales`, `Travel Accounts`, `Travel Manager`. `Travel Sales` is the operational entry role and has submit but no cancel/amend.
- **Invoice eligibility is based on posted status and a status string, not approval.** The duplicate-guard and hold checks exist, but the duplicate check is application-level without a row lock.
- **The workspace/report layer is minimal.** Only two number cards (`Invoice Pending`, `Invoice On Hold`) and one script report (`Posted Voucher Queue`) exist. They are not approval-aware.

Confidence is **high** for the Crown repository and the clean test site. Confidence is **medium** for the production site because five additional apps are installed on `crown.zonetourism.ae` (`hrms`, `shaunglobal`, `chat`, `airscan`, `air_ticket`), and their full interaction with Sales Order/Sales Invoice was not exhaustively reviewed.

## 2. App, module and legacy naming

| Item | Verified value | Evidence |
|---|---|---|
| Package | `crown_zone_vouchers` | `crown_zone_vouchers/__init__.py`, `pyproject.toml` |
| App title | Crown Zone Vouchers | `crown_zone_vouchers/hooks.py` |
| Module | `Crown Zone Vouchers` | `crown_zone_vouchers/modules.txt` |
| Version | `0.0.1` | `crown_zone_vouchers/__init__.py` |
| Required apps | `erpnext` | `hooks.py` |
| Frappe/ERPNext constraint | `frappe >=15.0.0,<17.0.0`, `erpnext >=15.0.0,<17.0.0` | `pyproject.toml` |
| Legacy `shaunglobal`/`showunglobal` references in tracked Crown source | **none found** | repo-wide grep of `.py`, `.js`, `.json`, `.html`, `.md` |

Do **not** rename the app, module or role names on the basis of spelling. The Crown repository has no legacy-name reference. The production **bench** does contain a separate app at `apps/shaunglobal` (version `0.0.1`) and the Crown site has it installed; that is an environment concern, not a Crown source dependency (see §9.1).

## 3. File tree grouped by feature

Tracked files: **77**.

```
crown_zone_vouchers/
  hooks.py, modules.txt, patches.txt, __init__.py
  api.py, utils.py, overrides.py (empty)
  config/
  events/
    sales_order.py            # validation, posting, child calculation, item sync, rebuild_items
    sales_invoice.py          # voucher link, item copy, invoice validation, status refresh
  public/js/
    sales_order.js            # item-grid mode, hold/release, Create Invoice, rebuild
    sales_invoice.js          # service/tax UI, column layout
  setup/
    install.py                # roles, permissions, seed, naming, print formats, workspace
    custom_fields.py          # Sales Order / Sales Invoice / item custom fields
    seed.py                   # service types, terms, items, tax codes, brand defaults
  crown_zone_vouchers/doctype/
    travel_service_type/ travel_service_term/ travel_voucher_settings/ airline_tax_code/
    voucher_traveller/ voucher_flight_segment/ voucher_air_ticket/ voucher_air_tax/
    voucher_hotel_stay/ voucher_service_line/ voucher_document_checklist/ voucher_transport_trip/
  crown_zone_vouchers/report/posted_voucher_queue/
    posted_voucher_queue.py, .js, .json
  templates/print/
    _css.html, _macros.html, _inv_totals.html
    voucher_airline.html, voucher_hotel.html, voucher_visa.html, voucher_transport.html,
    voucher_package.html, voucher_tour.html
    invoice_airline.html, invoice_hotel.html, invoice_generic.html
  tests/smoke.py
tools/pdf_fit_check.py        # added by the page-fit work; not an automated CI test
pyproject.toml, README.md, .gitignore
```

No `package.json`, `requirements.txt`, `setup.py`, CI workflow, pytest configuration, scheduler job, translation file, fixtures directory, or patch module exists. `patches.txt` has empty `[pre_model_sync]` and `[post_model_sync]` sections.

## 4. Actual Sales Order → invoice lifecycle

```
Sales Order (voucher)
  before_insert      naming_series from Travel Service Type
  before_validate    delivery flags, default Visa documents, child calculations,
                     remove empty Items, sync_items from tickets/rooms/service lines
  validate           calculate taxes, sales/profit/markup fields
  before_submit      validate_for_post (service-specific mandatory data)
                     stamp cz_posted_by / cz_posted_on
                     set cz_invoice_status = "Pending"
  before_cancel      only Travel Manager/System Manager; blocked if active invoice
  on_cancel          set cz_invoice_status = "Cancelled"

"Posted Voucher" == a submitted Sales Order (docstatus 1).
There is no separate Booking Voucher DocType and no approval state.
```

```
Sales Invoice (manual only; client button + report link + native make_sales_invoice)
  before_insert      _link_voucher; service invoice naming series
  before_validate    _link_voucher; copy item detail fields from Sales Order Item
  validate           voucher must be submitted (docstatus 1);
                     non-return invoice blocked when voucher On Hold;
                     duplicate active invoice check (docstatus < 2, non-return);
                     credit/debit note: Travel Manager and correction reason;
                     Without Tax cannot have tax rows; With Tax must have tax rows
  on_update/submit/cancel
                     refresh_invoice_status: Issued / Draft / Void / Pending
  on_trash           refresh voucher status excluding the deleted invoice

There is no automatic invoice creation and no accounting approval.
```

Confirmed in `crown_zone_vouchers/events/sales_order.py` and `events/sales_invoice.py`; client entry points in `public/js/sales_order.js` and `posted_voucher_queue.js`.

## 5. Data model and field map (key fields)

### Custom fields on Sales Order (`setup/custom_fields.py`)

- Identity: `service_type` (Link → Travel Service Type, required, after `naming_series`).
- Booking: `cz_booking_reference`, `cz_booking_status` (Select: Pending/On Request/Confirmed/Cancelled), `cz_supplier` (Link Supplier), `cz_supplier_confirmation_no`, `cz_booking_date`, `cz_lead_guest`, `cz_contact_whatsapp`, `cz_nationality`, `cz_total_adults`, `cz_total_children`, `cz_children_ages`, `cz_customer_remarks`.
- Hotel: `cz_hotel_name`, `cz_hotel_address`, `cz_hotel_city_country`, `cz_check_in`, `cz_check_out`, `cz_total_nights` (read-only), `cz_hotel_stays` (Table → Voucher Hotel Stay).
- Visa: `cz_visa_type`, `cz_destination_country`, `cz_processing_country`, `cz_embassy_center`, `cz_purpose_of_travel`, `cz_application_ref`, `cz_application_date`, `cz_expected_travel_date`, `cz_expected_return_date`, `cz_visa_validity`, `cz_processing_time`, `cz_visa_status` (Select), `cz_doc_checklist` (Table → Voucher Document Checklist).
- Transport/Tour: `cz_transport_service`, `cz_voucher_title`, `cz_tour_name`, `cz_tour_date`, `cz_pickup_location`, `cz_pickup_time`, `cz_dropoff_location`, `cz_important_note`, `cz_trips` (Table → Voucher Transport Trip).
- Umrah/Hajj: `cz_package_name`, `cz_package_type`, `cz_travel_date`, `cz_return_date`, `cz_departure_city`, `cz_group_ref`, `cz_visa_ref`, `cz_flight_bus_details`, `cz_transport_ziyarat`, `cz_meal_plan`, `cz_room_sharing`, `cz_mina_arafat`, `cz_guide_meals`, `cz_inclusions`, `cz_exclusions`.
- People: `cz_travellers` (Table → Voucher Traveller), `cz_air_tickets` (Voucher Air Ticket), `cz_flight_segments` (Voucher Flight Segment), `cz_air_taxes` (Voucher Air Tax).
- Services: `cz_service_lines` (Table → Voucher Service Line).
- Finance/internal: `cz_purchase_currency`, `cz_exchange_rate`, `cz_purchase_amount`, `cz_purchase_amount_pkr`, `cz_sales_amount_pkr`, `cz_profit_pkr`, `cz_markup_percent`, `cz_internal_remarks`, `cz_supplier_evidence`.
- Posting/invoice: `cz_prepared_by`, `cz_prepared_on`, `cz_posted_by`, `cz_posted_on`, `cz_invoice_status` (Select: blank/Pending/Draft/Issued/Void/On Hold/Cancelled, read-only), `cz_linked_invoice` (Link Sales Invoice, read-only), `cz_follow_up_date` (allow_on_submit).

### Custom fields on Sales Invoice (`setup/custom_fields.py`)

- `cz_travel_voucher` (Link Sales Order, no_copy, standard filter).
- `cz_service_type` (Link Travel Service Type, read-only, no_copy).
- `cz_invoice_tax_type` (Select: Without Tax / With Tax, default Without Tax).
- `cz_correction_reason` (Small Text; credit/debit notes).

### Custom fields on Sales Order Item and Sales Invoice Item

`cz_passenger`, `cz_ticket_no`, `cz_airline`, `cz_sector`, `cz_travel_date`, `cz_hotel_city`, `cz_room_type`, `cz_lead_guest`, `cz_rooms`, `cz_nights`, `cz_unit_rate`, `cz_other_fees` (hidden by default; shown per service by client script).

### App-local DocTypes

`Travel Service Type`, `Travel Service Term`, `Travel Voucher Settings`, `Airline Tax Code`; child tables `Voucher Traveller`, `Voucher Flight Segment`, `Voucher Air Ticket`, `Voucher Air Tax`, `Voucher Hotel Stay`, `Voucher Service Line`, `Voucher Document Checklist`, `Voucher Transport Trip`.

`Travel Service Type` service names (fixed, seeded): `Airline`, `Hotel`, `Visa`, `Transport`, `Umrah`, `Hajj`, `Tour`. It is a **Link** field, not a Select field. `default_tax_rate` is a Select (`5`/`0`, default `0`), added in the current code; the current test and production masters have `5` set for all seven services. `Voucher Service Line.tax_rate` is Select (`5`/`0`) with no default; `compute_children()` uses the service default when the line value is blank.

### Existing data shape (test site, before smoke run)

- 35 submitted Sales Orders, 0 draft; distribution 5 per service.
- Invoice status: 27 Pending, 4 Draft, 4 Void.
- Sales Invoices: 8 draft, 4 cancelled, 0 submitted.
- 8 invoice rows with custom `cz_travel_voucher` linkage on the test site; production had 0 native `Sales Invoice Item.sales_order` links in the inspected metadata. The app's primary link is the custom field; `_link_voucher` can fall back to native item links.

## 6. Current permissions matrix

Source: `crown_zone_vouchers/setup/install.py` (`ROLES`, `setup_permissions`), verified against site `Custom DocPerm`/`DocPerm`.

| Role | Sales Order | Sales Invoice |
|---|---|---|
| `Travel Sales` | read, write, create, submit, delete, report, export, print, email; **no cancel/amend** | none |
| `Travel Accounts` | read, report, export, print, email; **no write/create/submit/cancel** | read, write, create, submit, report, export, print, email; **no cancel/amend/delete** |
| `Travel Manager` | full (read/write/create/submit/cancel/amend/delete/report/export/print/email) | full |

- No `Booking Voucher User` role exists.
- No `User Permission` rows for `Sales Order` exist.
- No `Workflow` rows for `Sales Order` or `Sales Invoice` exist.
- No `permission_query_conditions`, `has_permission` override, or service-level server check exists in `hooks.py` or event modules.
- `rebuild_items` now calls `doc.check_permission("write")` and does not use `ignore_permissions`.
- `set_hold` is restricted to `Travel Accounts`, `Travel Manager`, `System Manager`; it changes only the status field and does not record actor/time/reason in an audit record.

## 7. Print-format inventory

23 app-managed formats are created from `setup/install.py`; 3 legacy formats were present only in site metadata. Total on the test site: 29 formats (26 active, 3 disabled).

| Format | DocType | Source | Notes |
|---|---|---|---|
| CZ Airline Voucher | Sales Order | `voucher_airline.html` | customer voucher |
| CZ Hotel Voucher | Sales Order | `voucher_hotel.html` | customer voucher |
| CZ Visa Voucher | Sales Order | `voucher_visa.html` | customer voucher |
| CZ Transport Voucher | Sales Order | `voucher_transport.html` | customer voucher |
| CZ Umrah Voucher | Sales Order | `voucher_package.html` + `pkg="Umrah"` | package |
| CZ Hajj Voucher | Sales Order | `voucher_package.html` + `pkg="Hajj"` | package |
| CZ Tour Voucher | Sales Order | `voucher_tour.html` | tour |
| CZ Airline Invoice - Without/With Tax | Sales Invoice | `invoice_airline.html` | service-specific, tax variant |
| CZ Hotel Invoice - Without/With Tax | Sales Invoice | `invoice_hotel.html` | service-specific, tax variant |
| CZ Visa Invoice - Without/With Tax | Sales Invoice | `invoice_generic.html` + `svc_title="VISA"` | generic template |
| CZ Transport Invoice - Without/With Tax | Sales Invoice | `invoice_generic.html` | generic |
| CZ Umrah Invoice - Without/With Tax | Sales Invoice | `invoice_generic.html` | generic |
| CZ Hajj Invoice - Without/With Tax | Sales Invoice | `invoice_generic.html` | generic |
| CZ Tour Invoice - Without/With Tax | Sales Invoice | `invoice_generic.html` | generic |
| CZ Voucher | Sales Order | dispatcher in `install.py` | default; switches by `doc.service_type` |
| CZ Invoice | Sales Invoice | dispatcher in `install.py` | default; switches by `doc.cz_service_type` and tax type |

Shared includes: `_css.html`, `_macros.html`, `_inv_totals.html`. Existing page-fit work is in these templates and `tools/pdf_fit_check.py`; it is not an automated test in the repo.

Site-only legacy formats observed: `Sales Auditing Voucher` (Sales Order), `Sales Invoice Print`, `Sales Invoice Return` (Sales Invoice). **No source file in the Crown repo creates these**; they are database-only legacy artifacts and must not be deleted without owner approval.

Default print formats are set by Property Setter to `CZ Voucher` and `CZ Invoice` in `setup/install.py`. `create_print_formats()` refreshes dispatchers on migrate; non-dispatcher service formats are not overwritten unless the settings flag `overwrite_print_formats` is set. This is an implementation assumption that needs owner confirmation before Phase 3.

## 8. Reports and workspace

- Report: `Posted Voucher Queue` (`crown_zone_vouchers/crown_zone_vouchers/report/posted_voucher_queue/`), Script Report, ref DocType Sales Order, roles `Travel Accounts`, `Travel Manager`, `System Manager`.
- Columns: voucher, service, posted date, customer, supplier, posted by, sales PKR, invoice status, linked invoice, action.
- Data source: `frappe.get_all("Sales Order", ...)` with filters on posted status/service/customer/supplier/posted by/invoice status/date. It uses `customer` then overwrites it with the linked customer ID (the label remains Link → Customer). It does **not** use an explicit permission query or approval predicate; row visibility depends on report role and Frappe defaults, not an audited row-level policy.
- Action JS: View Voucher and Create Invoice (for Pending/Void) via native `make_sales_invoice`; no server-side approval check beyond the existing posted/hold/duplicate checks.
- Workspace: `Travel Vouchers`, created by `setup/install.py` (not a JSON workspace file). It has two Number Cards: `Invoice Pending` (docstatus 1 + `cz_invoice_status=Pending`) and `Invoice On Hold` (docstatus 1 + `On Hold`), plus shortcuts for New `<Service>` Voucher, `Posted Voucher Queue`, `All Vouchers`, `Invoices`.
- There is no Approved / Invoiced / Rejected KPI, no approval date/by, no cost/profit card, and no dedicated Invoice Pending report; the number-card label "Invoice Pending" is a status filter, not the target "approved and invoice-eligible with no active invoice" predicate.
- Number cards use filters JSON; there is no shared KPI function and no independent reconciliation test.

## 9. Findings and risks

### 9.1 Environment and app isolation

1. **Production site has extra apps.** `crown.zonetourism.ae` installed apps: `frappe`, `erpnext`, `hrms`, `shaunglobal`, `chat`, `airscan`, `air_ticket`, `crown_zone_vouchers`. The clean test site has only `frappe`, `erpnext`, `crown_zone_vouchers`.
2. `shaunglobal` has fixtures/overrides that touch Sales Invoice, reports and print formats; `air_ticket` has Sales Invoice Item migrations/client JS and a travel invoice format; `airscan` has Sales Invoice JS. These are outside the Crown repo; full interaction was **not verified**. They can collide with Crown print defaults, item fields and invoice UI.
3. The Crown source has **no** `shaunglobal` import/reference. Do not rename Crown based on the environment app; isolate the upgrade on a clean v15 site first.

### 9.2 Authorization and workflow

1. **No service entitlement.** `service_type` is a Link, and no server-side check restricts a `Travel Sales` user to assigned services. Client-side `depends_on`/filters are presentation only.
2. **No Accounts approval.** `before_submit` posts immediately after validation; there is no approval state, approver, rejection reason, hold transition or audit trail. Self-approval is therefore not prevented because approval does not exist.
3. **No Booking Voucher User role.** `Travel Sales` is the closest existing role. Creating a new role or reusing `Travel Sales` is a Phase 1 decision; renaming is not justified by this audit.
4. **`set_hold` has no remarks/audit record.** It changes `cz_invoice_status` only.

### 9.3 Invoice and accounting

1. **Duplicate active invoice guard is application-level.** `validate()` checks `docstatus < 2` in a normal read; there is no row lock, unique constraint or idempotency key. Two concurrent requests can race.
2. **Manual-only invoicing is confirmed**; no auto-invoice path exists. Existing manual behavior must be preserved.
3. **No partial invoice support was found.** The duplicate guard allows only one active non-return invoice; returns are excluded. The policy should be confirmed before Phase 2.
4. **Cancellation behavior is implemented** (`Issued` → `Void`; invoice cancel re-evaluates status). The test covers submit → Issued and cancel → Void; income/debtors account configuration is required on a real site.
5. **Voucher cancellation is blocked with an active invoice** and restricted to Travel Manager/System Manager. Good baseline.
6. **Custom link is primary.** Production had 0 native `Sales Invoice Item.sales_order` links; the custom `cz_travel_voucher` remains the source of truth for existing rows. Do not backfill destructively.

### 9.4 Data / fresh-install

1. **Item-level custom fields are site-only in production.** The live site has item fields such as `supplier`, `purchase_price`, `purchase_tax_rate`, `final_price`, `government_fee`, `tax_rate`, `taxed_price`, `vat`, `custom_item_code`; these are used by event code and print machinery when present. The clean test site did not have all of them. `setup/custom_fields.py` creates item fields on Sales Order Item / Sales Invoice Item, but does not create the `Item` master's custom fields. A fresh install can therefore behave differently from production.
2. **After-migrate setup is best-effort.** `run_all()` catches exceptions per step and logs; a failed permission/print step does not fail the install. This is convenient but can leave a site half-configured.
3. **No patches/migrations** exist for the current schema. New role/workflow/service-assignment changes will need additive, idempotent setup and a backfill plan.
4. **Naming series**: options are merged into Property Setters by `sync_naming_options()`; service prefixes are current. `Tour` uses a 4-digit series (`CZ-ACT-.YYYY.-.####`), other services use 5 digits. Preserve this.

### 9.5 Print / reporting

1. The app has no automated print-render test; the smoke test checks HTML presence, not PDF clipping/page fit. `tools/pdf_fit_check.py` is a manual tool.
2. Page numbers are not reliably supported by wkhtmltopdf with CSS counters; the page-fit work found this limitation. Do not promise page numbers without a PDF-engine change.
3. The current report/workspace are not approval-aware and do not implement the target approved → invoice-pending predicate.
4. Legacy site-only print formats exist; they are not in source. Do not delete them; inventory them in Phase 3.

## 10. Backward-compatibility and migration risks

- Preserve `cz_*` fieldnames, service names/values, naming series, custom `cz_travel_voucher` links and existing submitted records.
- Do not rename `Travel Sales`/`Travel Accounts`/`Travel Manager` in place; add a new role only if the owner approves, then assign users deliberately.
- Any approval workflow must coexist with existing submitted Sales Orders that have no workflow state; a migration/default state policy is required.
- Existing invoices with `docstatus=0/2` and vouchers with `Pending/Draft/Issued/Void/On Hold/Cancelled` must keep their meaning; the new approval status must not silently rewrite historical statuses.
- Adding a service-assignment child table or User field requires an install patch and a fallback for existing users; no production migration has been run.
- Production extra apps may modify Sales Invoice Item or print defaults; staging must mirror production app set before rollout, not just the clean test site.

## 11. File-by-file change plan (discovery-first; no implementation yet)

| Concern | Exact existing path | Planned Phase 1/2 change | Test target |
|---|---|---|---|
| Role and permissions | `crown_zone_vouchers/setup/install.py` (`ROLES`, `setup_permissions`) | Idempotently add/rename decision for Booking Voucher role; add service-assignment field/table and grants | role matrix + setup re-run |
| Service fields | `crown_zone_vouchers/setup/custom_fields.py` | add user/service assignment only after design decision; no changes to existing `service_type` | fresh install + migrate |
| Sales Order server guard | `events/sales_order.py` (`before_validate`, `before_submit`, `validate`) | enforce service entitlement on create/save/submit/amend; add approval transition checks | unit + direct API tests |
| API guard | `crown_zone_vouchers/api.py` (`set_hold`), any new whitelisted actions | permission and workflow checks; audit remarks | REST/whitelist tests |
| Invoice lifecycle | `events/sales_invoice.py` (`validate`, `refresh_invoice_status`) | approval/hold eligibility, transaction-safe duplicate guard, cancellation policy | invoice/cancel/concurrency tests |
| Client UX | `public/js/sales_order.js`, `public/js/sales_invoice.js` | workflow buttons/status; filters are UX only | form regression |
| Workflow | new fixture/JSON under the repo’s setup convention (path TBD) or `setup/install.py` | native v15 Workflow for Sales Order; exact state/docstatus matrix first | workflow transition tests |
| Print | `setup/install.py` (`VOUCHERS`, `INVOICES`), `templates/print/*.html` | improve existing formats; no duplicates; preserve tax variants | PDF matrix |
| Report | `report/posted_voucher_queue/posted_voucher_queue.py/.js/.json` | approval-aware invoice-pending predicate; permission-safe query | report role/filter tests |
| Workspace | `setup/install.py` (`create_workspace`) | KPI cards and click-through | reconciliation tests |
| Tests | `tests/smoke.py` | extend or add unit/security tests; no CI exists | `run-tests`/smoke |
| Patches | `patches.txt` (empty) | additive patches only after design/backfill approval | clean install + upgrade fixture |
| Docs | new `docs/upgrade/` | audit, assumptions, phase reports | review gate |

No new Booking Voucher DocType is justified by this audit; retain Sales Order as the voucher.

## 12. Baseline environment and test evidence

| Item | Value |
|---|---|
| Branch / commit | `upgrade/enterprise-v15` / `ff4ccda` |
| Site used for baseline | `cz-test.localhost` (disposable; 3 apps only) |
| Frappe | `15.103.1` |
| ERPNext | `15.102.0` |
| Crown app | `0.0.1` |
| MariaDB | `10.11.14-MariaDB` |
| Python | `3.12.3` (pyproject requires `>=3.10`) |
| Production apps observed | `frappe`, `erpnext`, `hrms`, `shaunglobal`, `chat`, `airscan`, `air_ticket`, `crown_zone_vouchers` |
| Test apps | `frappe`, `erpnext`, `crown_zone_vouchers` |
| Baseline command | `bench --site cz-test.localhost execute crown_zone_vouchers.tests.smoke.run` |
| Baseline result | **70 checks, 0 failed** |
| Smoke side effect | creates documents; it does not delete them; run only on a disposable site |

## 13. Unknowns / not verified

- Full behavior and patch history of `shaunglobal`, `air_ticket`, `airscan`, `hrms`, `chat` on the production site; their hooks overlap Sales Invoice/JS/print areas.
- Production record counts and approval/status distribution were not read in this audit (no production PII inspection).
- Whether all production `Sales Invoice Item` links are custom-only; native item link count was 0 in the inspected metadata.
- Any hidden site scripts, server scripts, user-created workflows, client scripts or property setters not represented in the Crown repo; DB metadata was sampled, not exhaustively exported.
- Final approval state/docstatus matrix and migration policy for existing submitted vouchers; owner decision required.
- Whether partial invoicing is used in historical production data; not established.

## 14. Phase 0 exit gate

This report satisfies the audit-only gate. **No Phase 1 implementation should begin until the owner reviews and approves** the following decisions:

1. Reuse `Travel Sales` as Booking Voucher User, or create a new dedicated role (no rename without approval).
2. Service entitlement design (User child table vs. another link-safe mapping) and admin bypass policy.
3. Approval state/docstatus matrix for existing submitted vouchers and new drafts.
4. One-active-invoice policy and partial-invoice policy; cancelled-invoice reopening behavior.
5. Staging app set: clean test site vs. production-equivalent extra apps.
6. Whether legacy site-only print formats are retained, migrated or retired.
