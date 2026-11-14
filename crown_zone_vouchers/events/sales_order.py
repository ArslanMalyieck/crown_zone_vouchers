import frappe
from frappe import _
from frappe.utils import cint, date_diff, flt, getdate, now_datetime, nowdate

from crown_zone_vouchers.utils import cz_sector

DEFAULT_PREFIX = {"Airline": "ATV", "Hotel": "HTV", "Visa": "VSV", "Transport": "TRN", "Umrah": "UMH", "Hajj": "HAJ",
                  "Tour": "CZ-ACT"}
TRAVEL_ROLES = ("Travel Manager", "System Manager")


def voucher_series(service_type):
    custom = frappe.db.get_value("Travel Service Type", service_type, "voucher_series")
    if custom:
        return custom
    if service_type == "Tour":
        return "CZ-ACT-.YYYY.-.####"
    prefix = frappe.db.get_value("Travel Service Type", service_type, "voucher_prefix") or DEFAULT_PREFIX.get(service_type)
    return "%s-.YYYY.-.#####" % prefix


def company_currency(doc):
    return frappe.db.get_value("Company", doc.company, "default_currency") or "PKR"


# ------------------------------------------------------------------ hooks
def before_insert(doc, method=None):
    if doc.service_type:
        doc.naming_series = voucher_series(doc.service_type)


def before_validate(doc, method=None):
    if not doc.service_type:
        return
    doc.skip_delivery_note = 1
    if not doc.delivery_date:
        doc.delivery_date = doc.transaction_date or nowdate()
    if not doc.cz_prepared_by:
        doc.cz_prepared_by = frappe.session.user
        doc.cz_prepared_on = now_datetime()
    add_default_documents(doc)
    compute_children(doc)
    sync_items(doc)


def validate(doc, method=None):
    if not doc.service_type:
        return
    if hasattr(doc, "calculate_taxes_and_totals"):
        doc.calculate_taxes_and_totals()
    doc.cz_sales_amount_pkr = flt(doc.base_net_total)
    doc.cz_profit_pkr = doc.cz_sales_amount_pkr - flt(doc.cz_purchase_amount_pkr)
    doc.cz_markup_percent = (doc.cz_profit_pkr / flt(doc.cz_purchase_amount_pkr) * 100) if flt(doc.cz_purchase_amount_pkr) else 0


def before_submit(doc, method=None):
    """Posting: validate required data per service, lock, stamp user + time."""
    if not doc.service_type:
        return
    validate_for_post(doc)
    doc.cz_posted_by = frappe.session.user
    doc.cz_posted_on = now_datetime()
    doc.cz_invoice_status = "Pending"


def before_cancel(doc, method=None):
    if not any(r in frappe.get_roles() for r in TRAVEL_ROLES):
        frappe.throw(_("Only Travel Manager can cancel a posted voucher."))
    if frappe.db.exists("Sales Invoice", {"cz_travel_voucher": doc.name, "docstatus": ["<", 2]}):
        frappe.throw(_("Voucher has an active invoice. Cancel the invoice (or issue a credit note) first."))


def on_cancel(doc, method=None):
    frappe.db.set_value("Sales Order", doc.name, "cz_invoice_status", "Cancelled", update_modified=False)


# ------------------------------------------------------------------ calculations
def add_default_documents(doc):
    if doc.service_type == "Visa" and not doc.get("cz_doc_checklist"):
        lines = frappe.db.get_single_value("Travel Voucher Settings", "default_visa_documents") or ""
        for ln in lines.splitlines():
            if ln.strip():
                doc.append("cz_doc_checklist", {"document_name": ln.strip(), "received": 0})


def compute_children(doc):
    base = company_currency(doc)
    cur = doc.cz_purchase_currency or base
    rate = 1 if cur == base else (flt(doc.cz_exchange_rate) or 0)
    if cur == base:
        doc.cz_exchange_rate = 1
    st = doc.service_type

    if st == "Airline":
        taxes = {}
        for t in doc.cz_air_taxes:
            k = cint(t.ticket_row_no) or 1
            taxes[k] = taxes.get(k, 0) + flt(t.amount)
        total = 0
        for t in doc.cz_air_tickets:
            t.taxes_total = taxes.get(t.idx, 0)
            t.ticket_gross = flt(t.supplier_fare) + flt(t.taxes_total)
            t.commission_amount = flt(t.supplier_fare) * flt(t.commission_percent) / 100
            t.wht_amount = flt(t.commission_amount) * flt(t.wht_percent) / 100
            t.supplier_amount_foreign = t.ticket_gross - t.commission_amount + t.wht_amount
            t.supplier_amount_pkr = flt(t.supplier_amount_foreign) * rate
            total += flt(t.supplier_amount_foreign)
        doc.cz_purchase_amount = total

    if doc.cz_check_in and doc.cz_check_out:
        doc.cz_total_nights = max(date_diff(doc.cz_check_out, doc.cz_check_in), 0)

    for r in doc.cz_hotel_stays:
        if st == "Hotel":
            r.check_in = r.check_in or doc.cz_check_in
            r.check_out = r.check_out or doc.cz_check_out
        r.nights = max(date_diff(r.check_out, r.check_in), 0) if r.check_in and r.check_out else 0
        r.amount = flt(r.rooms or 1) * flt(r.nights) * flt(r.sale_rate) + flt(r.other_fees)

    for r in doc.cz_service_lines:
        r.amount = flt(r.qty) * flt(r.rate)

    doc.cz_purchase_amount_pkr = flt(doc.cz_purchase_amount) * rate


def sync_items(doc):
    """Sales Order items are built from the service tabs; Sales never edits them by hand."""
    st = doc.service_type
    rows = []
    default_item = frappe.db.get_value("Travel Service Type", st, "default_item")

    if st == "Airline" and doc.cz_air_tickets:
        sector = cz_sector(doc)
        first_date = doc.cz_flight_segments[0].travel_date if doc.cz_flight_segments else None
        for t in doc.cz_air_tickets:
            rows.append(dict(
                item_code=default_item, qty=1, rate=flt(t.sale_amount_pkr),
                description="Airline ticket %s - %s" % (t.ticket_no or "", t.passenger_name or ""),
                cz_passenger=t.passenger_name, cz_ticket_no=t.ticket_no, cz_airline=t.airline,
                cz_sector=sector, cz_travel_date=first_date))
    elif st == "Hotel" and doc.cz_hotel_stays:
        for r in doc.cz_hotel_stays:
            name = r.hotel_name or doc.cz_hotel_name
            city = ", ".join([x for x in (name, r.city or doc.cz_hotel_city_country) if x])
            rows.append(dict(
                item_code=default_item, qty=1, rate=flt(r.amount),
                description="%s - %s x%s room(s), %s night(s)" % (name or "", r.room_type or "", r.rooms or 1, r.nights or 0),
                cz_hotel_city=city, cz_room_type=r.room_type, cz_lead_guest=doc.cz_lead_guest,
                cz_rooms=r.rooms, cz_nights=r.nights, cz_unit_rate=r.sale_rate, cz_other_fees=r.other_fees))
    elif st in ("Visa", "Transport", "Umrah", "Hajj", "Tour") and doc.cz_service_lines:
        for r in doc.cz_service_lines:
            rows.append(dict(
                item_code=r.item_code or default_item, qty=flt(r.qty) or 1, rate=flt(r.rate),
                description=" - ".join([x for x in (r.category, r.description) if x]) or st))

    if not rows:
        return
    if not all(r["item_code"] for r in rows):
        frappe.throw(_("Set a Default Service Item on Travel Service Type {0}.").format(st))

    cache = {}
    doc.set("items", [])
    for r in rows:
        code = r["item_code"]
        if code not in cache:
            cache[code] = frappe.db.get_value("Item", code, ["item_name", "stock_uom"], as_dict=True)
        info = cache[code]
        r.update(item_name=info.item_name, uom=info.stock_uom, stock_uom=info.stock_uom,
                 conversion_factor=1, delivery_date=doc.delivery_date)
        if frappe.get_meta("Sales Order Item").has_field("custom_item_code"):
            r["custom_item_code"] = code
        doc.append("items", r)


# ------------------------------------------------------------------ posting validation
def validate_for_post(doc):
    st = doc.service_type
    e = []
    add = e.append

    if doc.cz_booking_status != "Confirmed":
        add(_("Booking Status must be Confirmed - unconfirmed entries cannot be posted."))
    if not doc.cz_supplier:
        add(_("Supplier / Operator is required."))
    if not doc.items or flt(doc.base_net_total) <= 0:
        add(_("Sales amount is missing - add tickets / rooms / service lines with sale rates."))
    if (doc.cz_purchase_currency or company_currency(doc)) != company_currency(doc) and flt(doc.cz_exchange_rate) <= 0:
        add(_("Exchange rate is required for foreign supplier amounts."))

    needs_people = st in ("Airline", "Hotel", "Visa", "Umrah", "Hajj")
    if needs_people and not [t for t in doc.cz_travellers if t.traveller_name]:
        add(_("Add at least one passenger / guest / applicant / pilgrim."))
    if st == "Transport" and not doc.cz_lead_guest:
        add(_("Passenger / Lead Guest is required."))

    if st == "Airline":
        if not doc.cz_air_tickets:
            add(_("Add at least one ticket."))
        for t in doc.cz_air_tickets:
            for fn, lb in (("passenger_name", "Passenger"), ("airline", "Airline"), ("pnr", "PNR"), ("ticket_no", "Ticket No.")):
                if not t.get(fn):
                    add(_("Ticket row {0}: {1} is required.").format(t.idx, lb))
            if flt(t.sale_amount_pkr) <= 0:
                add(_("Ticket row {0}: Sale Amount is required.").format(t.idx))
        if not doc.cz_flight_segments:
            add(_("Add at least one flight segment."))
        for s in doc.cz_flight_segments:
            if not (s.sector_from and s.sector_to and s.travel_date):
                add(_("Flight segment row {0}: From, To and Travel Date are required.").format(s.idx))

    elif st == "Hotel":
        if not doc.cz_hotel_name:
            add(_("Hotel Name is required."))
        if not (doc.cz_check_in and doc.cz_check_out) or getdate(doc.cz_check_out) <= getdate(doc.cz_check_in):
            add(_("Valid Check-in / Check-out dates are required."))
        if not doc.cz_supplier_confirmation_no:
            add(_("Supplier Confirmation No. is required."))
        if not doc.cz_hotel_stays:
            add(_("Add at least one room row."))

    elif st == "Visa":
        if not doc.cz_visa_type:
            add(_("Visa Type is required."))
        if not doc.cz_destination_country:
            add(_("Destination Country is required."))
        for t in doc.cz_travellers:
            if not t.passport_no:
                add(_("Applicant row {0}: Passport No. is required.").format(t.idx))
        if not doc.cz_service_lines:
            add(_("Add at least one service line."))

    elif st == "Transport":
        if not doc.cz_trips:
            add(_("Add at least one trip."))
        for t in doc.cz_trips:
            if not (t.pickup_datetime and t.pickup_location and t.dropoff_location):
                add(_("Trip row {0}: Pickup date/time, Pickup and Drop-off location are required.").format(t.idx))
        if not doc.cz_service_lines:
            add(_("Add at least one service line."))

    elif st == "Tour":
        if not doc.cz_lead_guest:
            add(_("Guest Name (Lead Guest) is required."))
        if cint(doc.cz_total_adults) < 1:
            add(_("Total Adults must be at least 1."))
        for fn, lb in (("cz_tour_name", "Tour / Activity"), ("cz_tour_date", "Tour Date"),
                       ("cz_pickup_location", "Pickup Location"), ("cz_pickup_time", "Pickup Time")):
            if not doc.get(fn):
                add(_("{0} is required.").format(lb))
        if not doc.cz_service_lines:
            add(_("Add the tour price in Services & Documents."))

    elif st in ("Umrah", "Hajj"):
        if not doc.cz_package_name:
            add(_("Package Name is required."))
        if not (doc.cz_travel_date and doc.cz_return_date):
            add(_("Travel Date and Return Date are required."))
        for t in doc.cz_travellers:
            if not t.passport_no:
                add(_("Pilgrim row {0}: Passport No. is required.").format(t.idx))
        if not [h for h in doc.cz_hotel_stays if h.hotel_name]:
            add(_("Add Makkah / Madinah hotel rows with hotel names."))
        if not doc.cz_service_lines:
            add(_("Add package price in Services & Documents."))

    if e:
        frappe.throw("<br>".join(e), title=_("Cannot Post Voucher"))
