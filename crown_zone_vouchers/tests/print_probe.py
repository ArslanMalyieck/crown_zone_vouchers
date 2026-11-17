"""Print probe: renders the Ticketing voucher / invoice and checks pagination + totals.

Run on a test or clone site:
    bench --site <site> execute crown_zone_vouchers.tests.print_probe.run
"""
import os

import frappe
from frappe.utils import add_days, flt, nowdate

OUT = "/home/frappe/print_tests"


def _so(items, tag):
    so = frappe.get_doc({
        "doctype": "Sales Order",
        "service_type": "Ticketing",
        "customer": frappe.db.get_value("Customer", {}, "name"),
        "transaction_date": nowdate(),
        "cz_booking_status": "Confirmed",
        "cz_booking_reference": "PROBE-%s" % tag,
        "cz_lead_guest": "Probe Pax",
        "cz_supplier": frappe.db.get_value("Supplier", {}, "name"),
        "items": items,
    })
    so.insert(ignore_permissions=True)
    so.submit()
    return so


def _item(idx, selling, gst="0"):
    return {
        "item_code": frappe.db.get_value("Travel Service Type", "Ticketing", "default_item"),
        "qty": 1, "final_price": selling, "cz_tax_rate": gst, "cz_manual": 1,
        "cz_passenger": "Probe Pax %02d" % idx,
        "cz_ticket_no": "176-9000%03d" % idx,
        "cz_flight_no": "EK%03d" % (600 + idx),
        "cz_class": "Y",
        "cz_sector": "KHI-DXB",
        "cz_travel_date": add_days(nowdate(), 10),
        "cz_tax_sp": 5000, "cz_tax_psf": 2000, "cz_tax_srb": 300,
    }


def run():
    frappe.set_user("Administrator")
    results = []

    def check(name, cond, extra=""):
        results.append((name, bool(cond), extra))

    small = _so([_item(1, 105000), _item(2, 110000, "5")], "SMALL")
    check("small voucher total", flt(small.grand_total) == 215000, small.grand_total)

    big_items = [_item(i, 100000 + i, "0") for i in range(1, 31)]
    big = _so(big_items, "BIG")
    check("big voucher total", flt(big.grand_total) == sum(100000 + i for i in range(1, 31)), big.grand_total)

    from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice

    si_small = make_sales_invoice(small.name)
    si_small.insert(ignore_permissions=True)
    check("small invoice total == voucher", flt(si_small.grand_total) == 215000, si_small.grand_total)
    check("small invoice GST", abs(flt(si_small.total_taxes_and_charges) - 5238.10) < 0.01,
          si_small.total_taxes_and_charges)

    si_big = make_sales_invoice(big.name)
    si_big.insert(ignore_permissions=True)

    os.makedirs(OUT, exist_ok=True)
    for label, doctype, name, fmt in (
        ("ticketing_voucher", "Sales Order", small.name, "CZ Ticketing Voucher"),
        ("ticketing_invoice", "Sales Invoice", si_small.name, "CZ Invoice"),
        ("ticketing_invoice_big", "Sales Invoice", si_big.name, "CZ Invoice"),
    ):
        html = frappe.get_print(doctype, name, fmt)
        with open(os.path.join(OUT, "%s.html" % label), "w") as fh:
            fh.write(html)
        check("%s html" % label, len(html) > 2000, len(html))

    big_html = frappe.get_print("Sales Invoice", si_big.name, "CZ Invoice")
    check("big invoice paginates", "PAGE 1 OF 2" in big_html and "PAGE 2 OF 2" in big_html,
          big_html.count("PAGE "))
    check("big invoice cumulative totals", big_html.count("Cumulative Total") == 2,
          big_html.count("Cumulative Total"))
    check("big invoice tax breakup", "PSF" in big_html and "SRB" in big_html)

    small_html = frappe.get_print("Sales Invoice", si_small.name, "CZ Invoice")
    check("small invoice single page", "PAGE 1 OF 1" in small_html, small_html.count("PAGE "))
    check("small invoice GST line", "GST 5%" in small_html)
    check("small invoice words", "ONLY" in small_html.upper())

    voucher_html = frappe.get_print("Sales Order", small.name, "CZ Ticketing Voucher")
    check("voucher shows fare/taxes", "TAXES BREAKUP" in voucher_html and "176-9000001" in voucher_html)

    try:
        import re

        from frappe.utils.pdf import get_pdf
        clean = re.sub(r"<link[^>]*print\.bundle[^>]*>", "", big_html)
        clean = re.sub(r"<script[^>]*print\.bundle[^>]*>\s*</script>", "", clean)
        pdf = get_pdf(clean, {"orientation": "Portrait", "load-error-handling": "ignore",
                              "load-media-error-handling": "ignore"})
        path = os.path.join(OUT, "ticketing_invoice_big.pdf")
        with open(path, "wb") as fh:
            fh.write(pdf)
        check("big invoice pdf", len(pdf) > 10000, len(pdf))
    except Exception as exc:  # noqa
        check("big invoice pdf", False, "%s: %s" % (type(exc).__name__, str(exc)[:200]))

    print("\n==== PRINT PROBE ====")
    for name, ok, extra in results:
        print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else "  -> %s" % extra))
    fails = [r for r in results if not r[1]]
    print("\n%d checks, %d failed" % (len(results), len(fails)))
    print("files: %s" % OUT)
    return {"checks": len(results), "failed": len(fails)}
