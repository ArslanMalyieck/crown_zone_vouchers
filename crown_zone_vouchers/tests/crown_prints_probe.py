"""Render probe for the Crown navy/gold print formats.

Run on a test site:
    bench --site <site> execute crown_zone_vouchers.tests.crown_prints_probe.run
"""
import os

import frappe

OUT = "/home/frappe/print_tests"
TITLES = ("CASH RECEIPT VOUCHER", "BANK RECEIPT VOUCHER", "CASH PAYMENT VOUCHER", "BANK PAYMENT VOUCHER")


def _render(doctype, name, fmt):
    return frappe.get_print(doctype, name, fmt)


def run():
    frappe.set_user("Administrator")
    results = []

    def check(label, cond, extra=""):
        results.append((label, bool(cond), extra))

    def lint(label, html):
        body = html[html.find('class="czg"'):] if 'class="czg"' in html else html
        check(label + " renders", len(html) > 1500, len(html))
        check(label + " no literal None", "None" not in body)
        check(label + " has footer", "czg" in html and "Tel" in html)

    pe_names = frappe.get_all("Payment Entry", filters={"docstatus": 1}, pluck="name", order_by="posting_date desc", limit=2)
    pe_names += frappe.get_all("Payment Entry", filters={"docstatus": 0}, pluck="name", order_by="creation desc", limit=2)
    seen_titles = set()
    for name in pe_names[:4]:
        html = _render("Payment Entry", name, "Crown Payment Voucher")
        lint("Payment Voucher %s" % name, html)
        found = [t for t in TITLES if t in html]
        check("Payment Voucher %s title" % name, bool(found), found)
        seen_titles.update(found)
        check("Payment Voucher %s words" % name, "Amount in words" in html)
    check("Payment Voucher titles checked", bool(pe_names) == bool(seen_titles), sorted(seen_titles))

    invoices = frappe.get_all("Sales Invoice", filters={"docstatus": 1}, pluck="name", order_by="creation desc", limit=3)
    for name in invoices:
        html = _render("Sales Invoice", name, "Crown Sales Invoice")
        lint("Sales Invoice %s" % name, html)
        check("Sales Invoice %s title" % name, ("TAX INVOICE" in html) or ("INVOICE" in html))
        check("Sales Invoice %s words" % name, "Amount in words" in html)

    orders = frappe.get_all("Sales Order", filters={"service_type": ("is", "set")}, pluck="name", order_by="creation desc", limit=4)
    for name in orders:
        html = _render("Sales Order", name, "Crown Sales Order Voucher")
        lint("Sales Order %s" % name, html)
        check("Sales Order %s no amounts" % name, ("Grand Total" not in html) and ("Total Amount" not in html))

    os.makedirs(OUT, exist_ok=True)
    if invoices:
        try:
            from frappe.utils.pdf import get_pdf
            html = _render("Sales Invoice", invoices[0], "Crown Sales Invoice")
            pdf = get_pdf(html, {"load-error-handling": "ignore"})
            with open(os.path.join(OUT, "crown_sales_invoice.pdf"), "wb") as fh:
                fh.write(pdf)
            check("Crown Sales Invoice pdf", len(pdf) > 10000, len(pdf))
        except Exception as exc:  # noqa
            check("Crown Sales Invoice pdf", False, "%s: %s" % (type(exc).__name__, str(exc)[:120]))

    print("\n==== CROWN PRINT PROBE ====")
    for label, ok, extra in results:
        print(("PASS  " if ok else "FAIL  ") + label + ("" if ok else "  -> %s" % extra))
    fails = [r for r in results if not r[1]]
    print("\n%d checks, %d failed" % (len(results), len(fails)))
    return {"checks": len(results), "failed": len(fails)}
