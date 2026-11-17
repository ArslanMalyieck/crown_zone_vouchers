import frappe
from frappe import _
from frappe.utils import cint, date_diff, flt, getdate, now_datetime, nowdate

from crown_zone_vouchers.events.vat import apply_vat, default_tax_rate
from crown_zone_vouchers.utils import cz_sector

DEFAULT_PREFIX = {"Airline": "ATV", "Hotel": "HTV", "Visa": "VSV", "Transport": "TRN", "Umrah": "UMH", "Hajj": "HAJ",
                  "Tour": "CZ-ACT", "Ticketing": "TKV"}
TRAVEL_ROLES = ("Travel Manager", "System Manager")
BOOKING_ROLES = ("Booking Voucher User", "Travel Sales")
SERVICE_BYPASS_ROLES = ("Travel Manager", "System Manager")


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


# ------------------------------------------------------------------ authorization
def assigned_services(user=None):
    user = user or frappe.session.user
    if not frappe.db.exists("DocType", "Booking Service Assignment"):
        return set()
    return {
        row.service_type
        for row in frappe.get_all(
            "Booking Service Assignment",
            filters={"parent": user, "parenttype": "User", "enabled": 1},
            fields=["service_type"],
        )
    }


def workflow_is_active():
    try:
        return bool(frappe.db.exists("Workflow", {"document_type": "Sales Order", "is_active": 1}))
    except Exception:
        return False


def validate_service_access(doc):
    """Server-side entitlement for operational booking users; UI filters are not security."""
    user = frappe.session.user
    if user in ("Administrator", "Guest"):
        return
    if not frappe.db.exists("DocType", "Booking Service Assignment"):
        return
    roles = set(frappe.get_roles(user))
    if roles & set(SERVICE_BYPASS_ROLES):
        return
    if not (roles & set(BOOKING_ROLES)):
        return
    service = (doc.get("service_type") or "").strip()
    if not service:
        frappe.throw(_("Service Type is required for a booking user."), title=_("Service not assigned"))
    allowed = assigned_services(user)
    if service not in allowed:
        frappe.throw(
            _("You are not assigned to the {0} service. Ask an administrator to update your Booking Service Types.").format(service),
            title=_("Service not assigned"),
        )


def validate_workflow_post(doc):
    """Only Accounts may turn a pending voucher into the posted (submitted) voucher."""
    if not workflow_is_active():
        return
    if getattr(doc, "workflow_state", None) == "Approved":
        return
    if frappe.session.user == "Administrator" or "System Manager" in frappe.get_roles():
        return
    frappe.throw(
        _("This voucher must be approved by Accounts before it can be posted."),
        title=_("Accounts approval required"),
    )


# ------------------------------------------------------------------ hooks
def before_insert(doc, method=None):
    if doc.service_type:
        validate_service_access(doc)
        doc.naming_series = voucher_series(doc.service_type)


def before_validate(doc, method=None):
    if not doc.service_type:
        return
    validate_service_access(doc)
    if (workflow_is_active() and getattr(doc, "workflow_state", None) == "Rejected"
            and not (doc.get("cz_approval_remarks") or "").strip()):
        frappe.throw(_("Enter Approval / Rejection Remarks before rejecting a voucher."),
                     title=_("Rejection remarks required"))
    doc.skip_delivery_note = 1
    if not doc.delivery_date:
        doc.delivery_date = doc.transaction_date or nowdate()
    if not doc.cz_prepared_by:
        doc.cz_prepared_by = frappe.session.user
        doc.cz_prepared_on = now_datetime()
    add_default_documents(doc)
    compute_children(doc)
    if doc.get("service_type"):
        for row in list(doc.get("items") or []):
            if not (row.get("item_code") or row.get("custom_item_code")):
                doc.remove(row)
        sync_items(doc)


def validate(doc, method=None):
    if not doc.service_type:
        return
    validate_service_access(doc)
    fill_item_defaults(doc)
    apply_vat(doc, doc.service_type)
    doc.cz_sales_amount_pkr = flt(doc.base_net_total)
    doc.cz_profit_pkr = doc.cz_sales_amount_pkr - flt(doc.cz_purchase_amount_pkr)
    doc.cz_markup_percent = (doc.cz_profit_pkr / flt(doc.cz_purchase_amount_pkr) * 100) if flt(doc.cz_purchase_amount_pkr) else 0


def fill_item_defaults(doc):
    """Every voucher line carries its own selling price, GST rate, supplier and cost."""
    rate = default_tax_rate(doc.service_type)
    for row in doc.get("items") or []:
        if not (row.get("item_code") or row.get("custom_item_code")):
            continue
        if row.get("cz_tax_rate") in (None, ""):
            row.cz_tax_rate = str(cint(rate))
        if not flt(row.get("final_price")):
            row.final_price = flt(row.get("rate"))
        if not row.get("supplier") and doc.get("cz_supplier") and row.meta.has_field("supplier"):
            row.supplier = doc.cz_supplier
        if not flt(row.get("purchase_price")) and not flt(row.get("government_fee")):
            row.purchase_price = 0
        total = sum(flt(row.get(f)) for f in ("cz_tax_sp", "cz_tax_rg", "cz_tax_psf", "cz_tax_srb",
                                              "cz_tax_yq", "cz_tax_other"))
        if row.meta.has_field("cz_taxes_total"):
            row.cz_taxes_total = flt(total, 2)


def before_submit(doc, method=None):
    """Posting: validate approval + service data, lock, stamp user + time."""
    if not doc.service_type:
        return
    validate_service_access(doc)
    validate_workflow_post(doc)
    validate_for_post(doc)
    doc.cz_posted_by = frappe.session.user
    doc.cz_posted_on = now_datetime()
    if getattr(doc, "workflow_state", None) == "Approved" and doc.meta.has_field("cz_approved_by"):
        doc.cz_approved_by = doc.cz_approved_by or frappe.session.user
        doc.cz_approved_on = doc.cz_approved_on or now_datetime()
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
            if not flt(t.get("purchase_amount")):
                t.purchase_amount = t.supplier_amount_pkr
            if not t.get("supplier") and doc.get("cz_supplier"):
                t.supplier = doc.cz_supplier
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

    default_tax_rate = cint(frappe.db.get_value("Travel Service Type", doc.service_type,
                                               "default_tax_rate") or 0)
    for r in doc.cz_service_lines:
        r.amount = flt(r.qty) * flt(r.rate)
        tax_rate = cint(r.get("tax_rate") if r.get("tax_rate") not in (None, "") else default_tax_rate)
        r.tax_rate = str(tax_rate)
        non_taxable = flt(r.get("non_taxable_price"))
        taxable = flt((flt(r.rate) - non_taxable) * 100 / (100 + tax_rate), 2) if (100 + tax_rate) else 0
        r.taxable_price = taxable
        r.vat = flt(taxable * tax_rate / 100, 2)

    line_purchase_total = sum(flt(r.get("purchase_amount")) for r in doc.cz_service_lines)
    doc.cz_purchase_amount_pkr = flt(doc.cz_purchase_amount) * rate
    if line_purchase_total:
        doc.cz_purchase_amount_pkr = line_purchase_total
        if not doc.cz_purchase_currency or doc.cz_purchase_currency == "PKR":
            doc.cz_purchase_amount = line_purchase_total


def _row_dicts(doc, all_rows=False):
    """Item rows as dicts: hand-added rows only, or every row (Ticketing)."""
    out = []
    meta = frappe.get_meta("Sales Order Item")
    names = [df.fieldname for df in meta.fields]
    for r in doc.get("items") or []:
        if not all_rows and not cint(r.get("cz_manual")):
            continue
        if not (r.get("item_code") or r.get("custom_item_code")):
            continue
        out.append({fn: r.get(fn) for fn in names if r.get(fn) not in (None, "")})
    return out


def _fill_item_master(doc, rows, item_meta):
    cache = {}
    for r in rows:
        code = r.get("item_code") or r.get("custom_item_code")
        if not code:
            continue
        if code not in cache:
            cache[code] = frappe.db.get_value("Item", code, ["item_name", "stock_uom"], as_dict=True)
        info = cache[code] or frappe._dict()
        r["item_code"] = code
        r.setdefault("item_name", info.get("item_name"))
        r["uom"] = r.get("uom") or info.get("stock_uom")
        r["stock_uom"] = info.get("stock_uom")
        r["conversion_factor"] = r.get("conversion_factor") or 1
        r["delivery_date"] = doc.delivery_date
        if item_meta.has_field("custom_item_code"):
            r["custom_item_code"] = code


def sync_items(doc):
    """Item rows are the posting input: tab rows are rebuilt, hand-added rows are kept."""
    st = doc.service_type
    if not st:
        return
    item_meta = frappe.get_meta("Sales Order Item")

    if st == "Ticketing":
        kept = _row_dicts(doc, all_rows=True)
        if not kept:
            return
        for r in kept:
            r["cz_manual"] = 1
        _fill_item_master(doc, kept, item_meta)
        doc.set("items", [])
        for r in kept:
            doc.append("items", r)
        return

    kept = _row_dicts(doc)
    rows = _tab_rows(doc, item_meta)
    if not rows and not kept:
        return
    if rows and not all(r.get("item_code") for r in rows):
        frappe.throw(_("Set a Default Service Item on Travel Service Type {0}.").format(st))
    _fill_item_master(doc, rows, item_meta)
    doc.set("items", [])
    for r in kept:
        doc.append("items", r)
    for r in rows:
        if (len(rows) == 1 and item_meta.has_field("purchase_price") and not flt(r.get("purchase_price"))):
            r["purchase_price"] = flt(doc.get("cz_purchase_amount_pkr"))
        doc.append("items", r)


def _tax_fields(row, item_meta, selling, gst, non_taxable, supplier, purchase):
    if item_meta.has_field("final_price"):
        row["final_price"] = flt(selling)
    if item_meta.has_field("government_fee"):
        row["government_fee"] = flt(non_taxable)
    if item_meta.has_field("cz_tax_rate"):
        row["cz_tax_rate"] = str(cint(gst))
    if item_meta.has_field("tax_rate"):
        row["tax_rate"] = flt(gst)
    if item_meta.has_field("supplier") and supplier:
        row["supplier"] = supplier
    if item_meta.has_field("purchase_price"):
        row["purchase_price"] = flt(purchase)


def _tab_rows(doc, item_meta):
    """Item rows generated from the service tabs (passenger / room / service details)."""
    st = doc.service_type
    rows = []
    default_item = frappe.db.get_value("Travel Service Type", st, "default_item")
    gst = default_tax_rate(st)

    if st == "Airline" and doc.cz_air_tickets:
        sector = cz_sector(doc)
        first_date = doc.cz_flight_segments[0].travel_date if doc.cz_flight_segments else None
        for t in doc.cz_air_tickets:
            row = dict(
                item_code=default_item, qty=1, rate=flt(t.sale_amount_pkr),
                description="Airline ticket %s - %s" % (t.ticket_no or "", t.passenger_name or ""),
                cz_passenger=t.passenger_name, cz_ticket_no=t.ticket_no, cz_airline=t.airline,
                cz_sector=sector, cz_travel_date=first_date, cz_manual=0)
            _tax_fields(row, item_meta, t.sale_amount_pkr, t.tax_rate if t.get("tax_rate") not in (None, "") else gst,
                        t.non_taxable, t.get("supplier") or doc.get("cz_supplier"), t.supplier_amount_pkr)
            rows.append(row)
    elif st == "Hotel" and doc.cz_hotel_stays:
        for r in doc.cz_hotel_stays:
            name = r.hotel_name or doc.cz_hotel_name
            city = ", ".join([x for x in (name, r.city or doc.cz_hotel_city_country) if x])
            row = dict(
                item_code=default_item, qty=1, rate=flt(r.amount),
                description="%s - %s x%s room(s), %s night(s)" % (name or "", r.room_type or "", r.rooms or 1, r.nights or 0),
                cz_hotel_city=city, cz_room_type=r.room_type, cz_lead_guest=doc.cz_lead_guest,
                cz_rooms=r.rooms, cz_nights=r.nights, cz_unit_rate=r.sale_rate, cz_other_fees=r.other_fees,
                cz_manual=0)
            _tax_fields(row, item_meta, r.amount, r.tax_rate if r.get("tax_rate") not in (None, "") else gst,
                        r.non_taxable, r.get("supplier") or doc.get("cz_supplier"), r.purchase_amount)
            rows.append(row)
    elif st in ("Visa", "Transport", "Umrah", "Hajj", "Tour") and doc.cz_service_lines:
        for r in doc.cz_service_lines:
            row = dict(
                item_code=r.item_code or default_item, qty=flt(r.qty) or 1, rate=flt(r.rate),
                description=" - ".join([x for x in (r.category, r.description) if x]) or st,
                cz_manual=0)
            _tax_fields(row, item_meta, r.rate, r.tax_rate if r.get("tax_rate") not in (None, "") else gst,
                        r.non_taxable_price, r.get("supplier") or doc.get("cz_supplier"), r.purchase_amount)
            if item_meta.has_field("taxed_price"):
                row["taxed_price"] = flt(r.get("taxable_price"))
            if item_meta.has_field("vat"):
                row["vat"] = flt(r.get("vat"))
            if item_meta.has_field("ticket_no"):
                row["ticket_no"] = r.get("ticket_no")
            if item_meta.has_field("cz_ticket_no"):
                row["cz_ticket_no"] = r.get("ticket_no")
            rows.append(row)
    return rows


def sync_items(doc):
    """Item rows are the posting input: tab rows are rebuilt, hand-added rows are kept."""
    st = doc.service_type
    if not st:
        return
    item_meta = frappe.get_meta("Sales Order Item")

    if st == "Ticketing":
        kept = _row_dicts(doc, all_rows=True)
        if not kept:
            return
        for r in kept:
            r["cz_manual"] = 1
        _fill_item_master(doc, kept, item_meta)
        doc.set("items", [])
        for r in kept:
            doc.append("items", r)
        return

    kept = _row_dicts(doc)
    rows = _tab_rows(doc, item_meta)
    if not rows and not kept:
        return
    if rows and not all(r.get("item_code") for r in rows):
        frappe.throw(_("Set a Default Service Item on Travel Service Type {0}.").format(st))
    _fill_item_master(doc, rows, item_meta)
    doc.set("items", [])
    for r in kept:
        doc.append("items", r)
    for r in rows:
        if (len(rows) == 1 and item_meta.has_field("purchase_price") and not flt(r.get("purchase_price"))):
            r["purchase_price"] = flt(doc.get("cz_purchase_amount_pkr"))
        doc.append("items", r)


# ------------------------------------------------------------------ posting validation
def validate_for_post(doc):
    st = doc.service_type
    e = []
    add = e.append

    if doc.cz_booking_status != "Confirmed":
        add(_("Booking Status must be Confirmed - unconfirmed entries cannot be posted."))
    line_suppliers = [r.get("supplier") for r in doc.cz_service_lines or []]
    if not doc.cz_supplier and not (line_suppliers and all(line_suppliers)):
        add(_("Supplier / Operator is required."))
    if not doc.items or flt(doc.base_net_total) <= 0:
        add(_("Sales amount is missing - add tickets / rooms / service lines with sale rates."))
    for i in doc.items or []:
        if flt(i.get("final_price") or i.get("rate")) <= 0:
            add(_("Item row {0}: Selling Price is required.").format(i.idx))
        if not i.get("supplier") and not doc.get("cz_supplier"):
            add(_("Item row {0}: Supplier is required.").format(i.idx))
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

    elif st == "Ticketing":
        if not doc.items:
            add(_("Add at least one ticket line in the Items table."))
        for i in doc.items or []:
            if not (i.cz_passenger or i.cz_ticket_no):
                add(_("Item row {0}: Passenger / Ticket No. is required.").format(i.idx))

    if e:
        frappe.throw("<br>".join(e), title=_("Cannot Post Voucher"))


@frappe.whitelist()
def rebuild_items(docname):
    """Rebuild Sales Order items from service lines (draft vouchers only)."""
    doc = frappe.get_doc("Sales Order", docname)
    doc.check_permission("write")
    if doc.docstatus != 0:
        frappe.throw(_("Only draft vouchers can be rebuilt."))
    if not doc.get("service_type"):
        frappe.throw(_("This is not a travel voucher."))
    sync_items(doc)
    doc.save()
    return doc.name
