"""End-to-end smoke test for Crown Zone Vouchers.

Run on a TEST site only (it creates real documents):
    bench --site <site> execute crown_zone_vouchers.tests.smoke.run
Prints a PASS/FAIL line per check and a summary. Nothing is deleted afterwards.
"""
import frappe
from frappe.utils import add_days, flt, nowdate

RESULTS = []
PREFIX = {"Airline": "ATV", "Hotel": "HTV", "Visa": "VSV", "Transport": "TRN", "Umrah": "UMH", "Hajj": "HAJ",
          "Tour": "CZ-ACT", "Ticketing": "TKV"}


def _assert(cond, msg="assertion failed"):
    if not cond:
        raise AssertionError(msg)


def check(name, fn):
    try:
        out = fn()
        RESULTS.append((name, True, ""))
        return out
    except Exception as e:  # noqa
        RESULTS.append((name, False, "%s: %s" % (type(e).__name__, str(e)[:300])))
        frappe.db.rollback()
        return None


def ensure_party():
    if not frappe.db.exists("Customer", "CZ Test Customer"):
        frappe.get_doc({"doctype": "Customer", "customer_name": "CZ Test Customer", "customer_type": "Company",
                        "customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}, "name"),
                        "territory": frappe.db.get_value("Territory", {"is_group": 0}, "name")}).insert()
    if not frappe.db.exists("Supplier", "CZ Test Supplier"):
        frappe.get_doc({"doctype": "Supplier", "supplier_name": "CZ Test Supplier",
                        "supplier_group": frappe.db.get_value("Supplier Group", {"is_group": 0}, "name")}).insert()


def base(service):
    return {"doctype": "Sales Order", "service_type": service, "customer": "CZ Test Customer",
            "transaction_date": nowdate(), "cz_supplier": "CZ Test Supplier", "cz_booking_status": "Pending",
            "cz_booking_reference": "BK-%s" % service, "cz_lead_guest": "Ali Khan",
            "cz_supplier_confirmation_no": "CONF123", "cz_purchase_currency": "PKR", "cz_purchase_amount": 1000,
            "cz_travellers": [{"traveller_name": "Ali Khan", "traveller_type": "Adult", "passport_no": "AB1234567",
                               "nationality": "Pakistani", "room_no": 1}]}


def payload(service):
    d = base(service)
    t = nowdate()
    if service == "Airline":
        d.update(cz_air_tickets=[{"passenger_name": "Ali Khan", "airline": "Emirates", "pnr": "ABC123",
                                  "ticket_no": "176-1234567890", "supplier_fare": 500, "commission_percent": 7,
                                  "wht_percent": 12, "sale_amount_pkr": 150000}],
                 cz_air_taxes=[{"ticket_row_no": 1, "tax_code": "YQ", "amount": 50}],
                 cz_flight_segments=[{"sector_from": "KHI", "sector_to": "DXB", "flight_no": "EK601",
                                      "cabin_class": "Economy", "travel_date": add_days(t, 10),
                                      "departure_time": "09:05:00", "arrival_time": "11:20:00"}])
    elif service == "Hotel":
        d.update(cz_hotel_name="Hilton Dubai Jumeirah", cz_hotel_city_country="Dubai, UAE",
                 cz_check_in=add_days(t, 10), cz_check_out=add_days(t, 15), cz_total_adults=4,
                 cz_hotel_stays=[{"room_type": "Deluxe Room", "rooms": 2, "occupancy": "Double",
                                  "meal_plan": "BB", "sale_rate": 20000}])
    elif service == "Visa":
        d.update(cz_visa_type="UAE 5 Years Multiple Entry", cz_destination_country="United Arab Emirates",
                 cz_service_lines=[{"category": "Visa Fee", "description": "UAE 5 Years", "qty": 3, "rate": 60000},
                                   {"category": "Service Charge", "description": "Processing", "qty": 3, "rate": 10000}])
    elif service == "Transport":
        d.update(cz_transport_service="Airport transfer",
                 cz_trips=[{"vehicle_type": "Hiace Van", "plate_no": "K-1234",
                            "pickup_datetime": add_days(t, 10) + " 09:00:00", "pickup_location": "Jinnah Airport",
                            "dropoff_location": "Hotel", "passengers": 3}],
                 cz_service_lines=[{"category": "Transfer", "description": "One-way", "qty": 1, "rate": 8000}])
    elif service == "Tour":
        d.update(cz_voucher_title="Desert Safari", cz_tour_name="Desert Safari - Sharing (Land Cruiser)",
                 cz_tour_date=add_days(t, 5), cz_pickup_location="Ibis Deira Creekside Dubai",
                 cz_pickup_time="15:00:00", cz_total_adults=2, cz_total_children=1,
                 cz_service_lines=[{"category": "Tour", "description": "Desert Safari - Sharing", "qty": 3, "rate": 5000,
                                    "non_taxable_price": 1000}])
    elif service == "Ticketing":
        d.update(items=[
            {"item_code": "Airline Ticket", "qty": 1, "final_price": 105000, "cz_tax_rate": "0",
             "cz_passenger": "Ali Khan", "cz_ticket_no": "176-111", "cz_flight_no": "EK601", "cz_class": "Y",
             "cz_sector": "KHI-DXB", "cz_travel_date": add_days(t, 10), "cz_tax_sp": 5000,
             "cz_tax_psf": 2000, "cz_tax_srb": 300, "supplier": "CZ Test Supplier",
             "purchase_price": 90000, "cz_manual": 1},
            {"item_code": "Airline Ticket", "qty": 1, "final_price": 110000, "cz_tax_rate": "5",
             "cz_passenger": "Sara Khan", "cz_ticket_no": "176-222", "cz_sector": "KHI-DXB",
             "cz_tax_other": 1000, "supplier": "CZ Test Supplier", "purchase_price": 95000, "cz_manual": 1},
        ])
    else:  # Umrah / Hajj
        d.update(cz_package_name="%s Gold Package" % service, cz_travel_date=add_days(t, 30),
                 cz_return_date=add_days(t, 45),
                 cz_hotel_stays=[{"hotel_name": "Makkah Clock Tower", "city": "Makkah", "check_in": add_days(t, 30),
                                  "check_out": add_days(t, 38), "room_type": "Quad", "rooms": 1},
                                 {"hotel_name": "Pullman Zamzam Madinah", "city": "Madinah",
                                  "check_in": add_days(t, 38), "check_out": add_days(t, 45), "room_type": "Quad", "rooms": 1}],
                 cz_service_lines=[{"category": "Package", "description": "%s package" % service, "qty": 1, "rate": 450000}])
    return d


def run():
    frappe.set_user("Administrator")
    ensure_party()
    posted = {}
    for service in ("Airline", "Hotel", "Visa", "Transport", "Umrah", "Hajj", "Tour", "Ticketing"):
        so = check("[%s] create draft voucher" % service, lambda s=service: frappe.get_doc(payload(s)).insert())
        if not so:
            continue
        frappe.db.commit()
        check("[%s] number series (%s)" % (service, so.name),
              lambda s=service, n=so.name: _assert(n.startswith(PREFIX[s])))
        check("[%s] items auto-built & amount > 0" % service, lambda: _assert(so.items and so.base_net_total > 0))
        check("[%s] profit computed" % service,
              lambda: _assert(so.cz_purchase_amount_pkr is not None and so.cz_sales_amount_pkr > 0))

        def must_fail(n=so.name):
            try:
                frappe.get_doc("Sales Order", n).submit()
            except Exception:
                return
            raise AssertionError("posted while Booking Status was Pending")
        check("[%s] cannot post unconfirmed" % service, must_fail)
        frappe.db.rollback()

        def post(n=so.name):
            d = frappe.get_doc("Sales Order", n)
            d.cz_booking_status = "Confirmed"
            d.save()
            d.submit()
            _assert(d.cz_posted_by and d.cz_posted_on and d.cz_invoice_status == "Pending")
            return d
        p = check("[%s] confirm + post -> Invoice Pending" % service, post)
        if not p:
            continue
        posted[service] = p.name

        def printed(s=service, n=p.name):
            html = frappe.get_print("Sales Order", n, "CZ %s Voucher" % s)
            low = html.lower()
            _assert("voucher" in low and n in html)
            for bad in ("profit", "purchase amount", "markup", "supplier evidence"):
                _assert(bad not in low, "internal field leaked on voucher: " + bad)
        check("[%s] customer voucher prints, no cost/profit" % service, printed)
        check("[%s] default 'CZ Voucher' dispatcher prints" % service,
              lambda n=p.name: _assert(n in frappe.get_print("Sales Order", n, "CZ Voucher")))

    v = posted.get("Airline")
    if v:
        from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice

        def hold_release():
            from crown_zone_vouchers.api import set_hold
            _assert(set_hold(v, 1) == "On Hold")
            try:
                si = make_sales_invoice(v)
                si.insert()
            except Exception:
                pass
            else:
                raise AssertionError("invoice created while On Hold")
            _assert(set_hold(v, 0) == "Pending")
        check("[Accounts] hold blocks invoice, release restores Pending", hold_release)

        def invoice():
            si = make_sales_invoice(v)
            si.insert()
            _assert(si.cz_travel_voucher == v and si.naming_series.startswith("INV-AIR"))
            _assert(frappe.db.get_value("Sales Order", v, "cz_invoice_status") == "Draft")
            return si
        si = check("[Accounts] manual invoice (draft) -> voucher status Draft", invoice)

        def dup():
            try:
                s2 = make_sales_invoice(v)
                s2.insert()
            except Exception:
                return
            raise AssertionError("duplicate active invoice allowed")
        if si:
            check("[Accounts] duplicate active invoice blocked", dup)
            check("[Accounts] invoice print (Without Tax)", lambda: _assert(
                "SALES INVOICE" in frappe.get_print("Sales Invoice", si.name, "CZ Airline Invoice - Without Tax")))

            def submit_invoice():
                d = frappe.get_doc("Sales Invoice", si.name)
                d.submit()
                _assert(frappe.db.get_value("Sales Order", v, "cz_invoice_status") == "Issued")
                d.reload()
                d.cancel()
                _assert(frappe.db.get_value("Sales Order", v, "cz_invoice_status") == "Void")
            check("[Accounts] submit -> Issued, cancel -> Void (needs income/debtors accounts configured)", submit_invoice)

        def tax_type_derived():
            s3 = make_sales_invoice(v)
            s3.insert()
            _assert(s3.cz_invoice_tax_type == "Without Tax", "zero rated voucher must give Without Tax")
            frappe.db.rollback()
        check("[Accounts] Invoice Type derived from data (no manual switch)", tax_type_derived)

    tk = posted.get("Ticketing")
    if tk:
        def ticketing_items():
            d = frappe.get_doc("Sales Order", tk)
            _assert(len(d.items) == 2, "same item twice must be kept as two rows")
            first, second = d.items
            _assert(flt(first.cz_taxes_total) == 7300, "ticket tax buckets must total 7300")
            _assert(flt(first.rate) == 105000, "zero rated ticket keeps selling price as rate")
            _assert(abs(flt(second.rate) - 104761.90) < 0.01, "ticket net rate")
            _assert(abs(flt(second.vat) - 5238.10) < 0.01, "ticket GST")
            _assert(abs(flt(d.grand_total) - 215000) < 0.01, "grand total must equal sum of selling prices")
            _assert(len(d.taxes) == 1 and abs(flt(d.taxes[0].tax_amount) - 5238.10) < 0.01, "single GST row")
        check("[Ticketing] same item twice at different rates + VAT at item level", ticketing_items)

        def ticketing_invoice():
            from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice as mk
            si = mk(tk)
            si.insert()
            _assert(si.naming_series.startswith("INV-TKT"))
            _assert(si.cz_invoice_tax_type == "With Tax", "GST invoice must be With Tax")
            _assert(len(si.items) == 2)
            row = [i for i in si.items if i.cz_ticket_no == "176-222"][0]
            _assert(row.supplier == "CZ Test Supplier", "item supplier must come from the voucher")
            _assert(abs(flt(row.final_price) - 110000) < 0.01, "selling price must come from the voucher")
            _assert(abs(flt(si.grand_total) - 215000) < 0.01, "invoice total must match the voucher")
            html = frappe.get_print("Sales Invoice", si.name, "CZ Invoice")
            _assert("176-222" in html and "AIRLINE TICKETS" in html.upper())
            return si
        check("[Ticketing] invoice fetches items, supplier, GST + print", ticketing_invoice)

        def ticketing_voucher_print():
            html = frappe.get_print("Sales Order", tk, "CZ Ticketing Voucher")
            _assert("AIRLINE TICKETING VOUCHER" in html and "176-111" in html)
        check("[Ticketing] voucher print", ticketing_voucher_print)

    t = posted.get("Tour")
    if t:
        def tour_invoice():
            from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice as mk
            si = mk(t)
            si.insert()
            _assert(si.naming_series.startswith("INV-TUR"))
            _assert(si.cz_invoice_tax_type == "With Tax", "tour line has 5% GST")
            _assert(abs(flt(si.total_taxes_and_charges) - 571.43) < 0.05, "GST on the taxable part only")
            html = frappe.get_print("Sales Invoice", si.name, "CZ Invoice")
            _assert("INVOICE" in html and "Desert Safari" in html)
        check("[Tour] invoice series INV-TUR + GST on taxable part + print", tour_invoice)

    get_data = frappe.get_attr(
        "crown_zone_vouchers.crown_zone_vouchers.report.posted_voucher_queue.posted_voucher_queue.get_data")
    for service, name in posted.items():
        check("[%s] queue report lists voucher" % service,
              lambda n=name: _assert(any(r["voucher"] == n for r in get_data(frappe._dict(invoice_status=""))) or
                                     any(r["voucher"] == n for r in get_data(frappe._dict()))))

    print("\n==== CROWN ZONE SMOKE TEST ====")
    for name, ok, msg in RESULTS:
        print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else "  -> " + msg))
    fails = [r for r in RESULTS if not r[1]]
    print("\n%d checks, %d failed" % (len(RESULTS), len(fails)))
    frappe.db.commit()
    return {"checks": len(RESULTS), "failed": len(fails)}
