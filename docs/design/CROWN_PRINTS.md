# Crown navy/gold print formats

App-managed Jinja print formats, created/updated automatically on `bench migrate`
(`crown_zone_vouchers.setup.install.create_print_formats`).

| Print Format | DocType | Template |
|---|---|---|
| Crown Payment Voucher | Payment Entry | `templates/print/crown_payment_voucher.html` |
| Crown Sales Invoice | Sales Invoice | `templates/print/crown_sales_invoice.html` |
| Crown Sales Order Voucher | Sales Order | `templates/print/crown_sales_order_voucher.html` |

Shared styling: `templates/print/_crown_style.html` (inline `<style>`, `czg-*` classes).

## Design tokens

Defined as Jinja variables at the top of `_crown_style.html`:

| Token | Value | Use |
|---|---|---|
| navy | `#0B1F4B` | header band, table headers, totals |
| deep | `#07163A` | dark accents |
| gold | `#C9A227` | titles, rules, accents |
| lgold | `#E8D48A` | light gold text on navy |
| soft | `#FBF6E4` | zebra rows, amount-in-words strip |
| lnavy | `#EEF1F8` | info cards, label cells |
| ink | `#1A1A1A` | body text |
| muted | `#6B7280` | secondary text |
| line | `#D9DCE3` | borders |

Change a colour in one place (the `{% set %}` block) and all three formats follow.
Keep the layout table/float based: wkhtmltopdf's QtWebKit does not support grid/flex/gap.

## Behaviour

- Payment Voucher title is derived: `CASH`/`BANK` from `mode_of_payment`, `RECEIPT`/`PAYMENT`
  from `payment_type`. Party is resolved from `party_type` + `party` (Customer or Supplier).
- Sales Invoice: GST is the only tax row (`doc.taxes`); airline/service taxes stay on the
  item lines (Fare / Taxes / Amount). `TAX INVOICE` vs `INVOICE` follows the tax rows.
- Sales Order voucher prints service details only - no rates, amounts or totals.

These formats are additions. Existing `Payment Voucher`, `CZ Invoice`, `CZ Voucher`
formats and their defaults are unchanged.

## Test plan

```bash
# on a test site (never live first)
cd ~/frappe-bench
bench --site <site> migrate
bench --site <site> clear-cache
bench --site <site> execute crown_zone_vouchers.tests.crown_prints_probe.run
```

Manual checklist:

1. Payment Entry Receive (Cash and Bank) and Pay (Cash and Bank) - title correct.
2. Payment Entry with no allocations - "No document allocation" note, no broken table.
3. Payment Entry in foreign currency - amounts use the voucher currency.
4. Sales Invoice With Tax - only GST appears in the totals; airline taxes stay in the item columns.
5. Sales Invoice Without Tax - no tax rows, title reads INVOICE.
6. Sales Invoice / Order with a long description and an Arabic customer name - text wraps, nothing prints as `None`.
7. Sales Order voucher - no amounts anywhere; service sections match the service type.
8. Long lists (40+ rows) - table header repeats, rows do not split, footer stays last.
9. Print -> Get PDF for one document of each type.
