import json

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def svc(*names):
    return "eval:%s.includes(doc.service_type)" % json.dumps(list(names))


class _Builder:
    """Collects custom fields and chains insert_after in the order they are added."""

    def __init__(self, anchor):
        self.anchor = anchor
        self.fields = []
        self.n = 0

    def add(self, fieldname, label, fieldtype="Data", options=None, **kw):
        d = {"fieldname": fieldname, "fieldtype": fieldtype, "insert_after": self.anchor}
        if label:
            d["label"] = label
        if options is not None:
            d["options"] = options
        d.update(kw)
        self.fields.append(d)
        self.anchor = fieldname

    def tab(self, fieldname, label, dep=None):
        self.add(fieldname, label, "Tab Break", depends_on=dep)

    def sec(self, label, dep=None):
        self.n += 1
        self.add("cz_sb%d" % self.n, label, "Section Break", depends_on=dep)

    def col(self):
        self.n += 1
        self.add("cz_cb%d" % self.n, None, "Column Break")


INTERNAL = {"print_hide": 1}


def _so_anchor():
    """Field just before the Items tab so the voucher tabs sit between Details and Items."""
    try:
        names = [f.fieldname for f in frappe.get_meta("Sales Order").fields]
        if "items_tab" in names:
            for fn in reversed(names[: names.index("items_tab")]):
                if not fn.startswith("cz_") and fn != "service_type":
                    return fn
    except Exception:
        pass
    return "amended_from"


def sales_order_fields():
    # service type picker sits at the very top
    top = _Builder("naming_series")
    top.add("service_type", "Service Type", "Link", "Travel Service Type", reqd=1, bold=1,
            in_list_view=1, in_standard_filter=1, no_copy=0)

    b = _Builder(_so_anchor())

    # ---------------- 1. BOOKING ----------------
    b.tab("cz_booking_tab", "Booking", svc(*ALL))
    b.add("cz_booking_reference", "Booking Reference", in_list_view=1)
    b.add("cz_booking_status", "Booking Status", "Select",
          "Pending\nOn Request\nConfirmed\nCancelled", default="Pending")
    b.add("cz_supplier", "Supplier / Operator", "Link", "Supplier")
    b.add("cz_supplier_confirmation_no", "Supplier Confirmation No.")
    b.add("cz_booking_date", "Booking Date", "Date", default="Today")
    b.col()
    b.add("cz_lead_guest", "Passenger / Lead Guest / Lead Pilgrim")
    b.add("cz_contact_whatsapp", "Contact / WhatsApp")
    b.add("cz_nationality", "Nationality")
    b.add("cz_total_adults", "Total Adults", "Int", depends_on=svc("Hotel", "Umrah", "Hajj", "Tour"))
    b.add("cz_total_children", "Total Children", "Int", depends_on=svc("Hotel", "Umrah", "Hajj", "Tour"))
    b.add("cz_children_ages", "Children Ages", depends_on=svc("Hotel", "Umrah", "Hajj", "Tour"))
    b.add("cz_customer_remarks", "Remarks (printed on voucher)", "Small Text")

    # hotel
    b.sec("Hotel Details", svc("Hotel"))
    b.add("cz_hotel_name", "Hotel Name")
    b.add("cz_hotel_address", "Hotel Address", "Small Text")
    b.add("cz_hotel_city_country", "City / Country")
    b.col()
    b.add("cz_check_in", "Check-in Date", "Date")
    b.add("cz_check_out", "Check-out Date", "Date")
    b.add("cz_total_nights", "Total Nights (auto)", "Int", read_only=1)

    # visa
    b.sec("Visa Details", svc("Visa"))
    b.add("cz_visa_type", "Visa Type", description="e.g. UAE 5 Years Multiple Entry")
    b.add("cz_destination_country", "Destination Country")
    b.add("cz_processing_country", "Processing Country", default="Pakistan")
    b.add("cz_embassy_center", "Embassy / Visa Center")
    b.add("cz_purpose_of_travel", "Purpose of Travel")
    b.add("cz_application_ref", "Application / Reference No.")
    b.col()
    b.add("cz_application_date", "Application Date", "Date")
    b.add("cz_expected_travel_date", "Expected Travel Date", "Date")
    b.add("cz_expected_return_date", "Expected Return Date", "Date")
    b.add("cz_visa_validity", "Visa Validity")
    b.add("cz_processing_time", "Processing Time")
    b.add("cz_visa_status", "Application Status", "Select",
          "In Process\nSubmitted\nApproved\nRejected\nDelivered", default="In Process")

    # transport
    b.sec("Transport Details", svc("Transport"))
    b.add("cz_transport_service", "Service Type", description="Airport transfer / Full day / Intercity ...")

    # tour / activity (desert safari, city tour ...)
    b.sec("Tour Details", svc("Tour"))
    b.add("cz_voucher_title", "Voucher Title (printed)", description="e.g. Desert Safari -> prints DESERT SAFARI VOUCHER")
    b.add("cz_tour_name", "Tour / Activity", description="e.g. Desert Safari - Sharing (Land Cruiser)")
    b.add("cz_tour_date", "Tour Date", "Date")
    b.col()
    b.add("cz_pickup_location", "Pickup Location")
    b.add("cz_pickup_time", "Pickup Time", "Time")
    b.add("cz_dropoff_location", "Drop-off Location (optional)")
    b.add("cz_important_note", "Important Note (printed)", "Small Text",
          default="Please be ready at the pickup point 15 minutes before pickup.")

    # umrah / hajj package
    b.sec("Package Details", svc("Umrah", "Hajj"))
    b.add("cz_package_name", "Package Name")
    b.add("cz_package_type", "Package Type")
    b.add("cz_travel_date", "Travel Date", "Date")
    b.add("cz_return_date", "Return Date", "Date")
    b.add("cz_departure_city", "Departure City / Airport")
    b.add("cz_group_ref", "Group / Booking Ref.")
    b.add("cz_visa_ref", "Visa / Permit Ref.")
    b.col()
    b.add("cz_flight_bus_details", "Flight / Bus Details", "Small Text")
    b.add("cz_transport_ziyarat", "Transport / Ziyarat / Transfers", "Small Text")
    b.add("cz_meal_plan", "Meal Plan / Inclusions", "Small Text")
    b.add("cz_room_sharing", "Room / Tent Sharing", "Small Text")
    b.add("cz_mina_arafat", "Mina / Arafat Arrangements", "Small Text", depends_on=svc("Hajj"))
    b.add("cz_guide_meals", "Meals / Group / Guide", "Small Text", depends_on=svc("Hajj"))
    b.add("cz_inclusions", "Inclusions", "Small Text")
    b.add("cz_exclusions", "Exclusions", "Small Text")

    # ---------------- 2. TRAVELLERS ----------------
    b.tab("cz_travellers_tab", "Passengers / Guests / Pilgrims", svc(*ALL))
    b.add("cz_travellers", "Passengers / Guests / Applicants / Pilgrims", "Table", "Voucher Traveller")

    # ---------------- 3. FLIGHTS & TICKETS ----------------
    b.tab("cz_flight_tab", "Flights & Tickets", svc("Airline", "Umrah", "Hajj"))
    b.sec("Ticket Details", svc("Airline"))
    b.add("cz_air_tickets", "Tickets", "Table", "Voucher Air Ticket")
    b.sec("Flight Segments / Sectors")
    b.add("cz_flight_segments", "Flight Segments", "Table", "Voucher Flight Segment")

    # ---------------- 4. FARE / ETR TAXES ----------------
    b.tab("cz_fare_tab", "Fare / ETR Taxes", svc("Airline"))
    b.add("cz_air_taxes", "Airline / ETR Taxes", "Table", "Voucher Air Tax")

    # ---------------- 5. HOTEL / ROOMS ----------------
    b.tab("cz_hotel_tab", "Hotel / Room Allocation", svc("Hotel", "Umrah", "Hajj"))
    b.add("cz_hotel_stays", "Rooms / Hotels", "Table", "Voucher Hotel Stay")

    # ---------------- 6. VEHICLE & TRIP ----------------
    b.tab("cz_trip_tab", "Vehicle & Trip", svc("Transport"))
    b.add("cz_trips", "Trips", "Table", "Voucher Transport Trip")

    # ---------------- 7. SERVICES & DOCUMENTS ----------------
    b.tab("cz_service_tab", "Services & Documents", svc("Visa", "Transport", "Umrah", "Hajj", "Tour"))
    b.sec("Services / Charges (customer sale, PKR)")
    b.add("cz_service_lines", "Services", "Table", "Voucher Service Line")
    b.sec("Document Checklist", svc("Visa", "Umrah", "Hajj"))
    b.add("cz_doc_checklist", "Documents Received", "Table", "Voucher Document Checklist")

    # ---------------- 8. SALES & PURCHASE (internal) ----------------
    b.tab("cz_finance_tab", "Sales & Purchase", svc(*ALL))
    b.add("cz_purchase_currency", "Purchase Currency", "Link", "Currency", default="PKR", **INTERNAL)
    b.add("cz_exchange_rate", "Exchange Rate (to PKR)", "Float", default="1", precision="6", **INTERNAL)
    b.add("cz_purchase_amount", "Purchase Amount (Supplier Currency)", "Currency", **INTERNAL)
    b.add("cz_purchase_amount_pkr", "Purchase Amount (PKR)", "Currency", read_only=1, **INTERNAL)
    b.col()
    b.add("cz_sales_amount_pkr", "Sales Amount (PKR, before tax)", "Currency", read_only=1, **INTERNAL)
    b.add("cz_profit_pkr", "Profit (PKR)", "Currency", read_only=1, **INTERNAL)
    b.add("cz_markup_percent", "Markup %", "Percent", read_only=1, **INTERNAL)
    b.sec("Internal (never printed on customer voucher)")
    b.add("cz_internal_remarks", "Internal Remarks", "Small Text", **INTERNAL)
    b.add("cz_supplier_evidence", "Supplier Evidence (attach)", "Attach", **INTERNAL)

    # ---------------- 9. POSTING ----------------
    b.tab("cz_posting_tab", "Posting", svc(*ALL))
    b.add("cz_prepared_by", "Prepared By", "Link", "User", read_only=1, no_copy=1)
    b.add("cz_prepared_on", "Prepared On", "Datetime", read_only=1, no_copy=1)
    b.col()
    b.add("cz_posted_by", "Posted By", "Link", "User", read_only=1, no_copy=1)
    b.add("cz_posted_on", "Posted On", "Datetime", read_only=1, no_copy=1)
    b.col()
    b.add("cz_approved_by", "Approved By", "Link", "User", read_only=1, no_copy=1, allow_on_submit=1)
    b.add("cz_approved_on", "Approved On", "Datetime", read_only=1, no_copy=1, allow_on_submit=1)
    b.add("cz_approval_remarks", "Approval / Rejection Remarks", "Small Text", allow_on_submit=1,
          description="Required when Accounts rejects a voucher; recorded with the approval decision.")
    b.sec("Invoice Status (Accounts)")
    b.add("cz_invoice_status", "Invoice Status", "Select",
          "\nPending\nDraft\nIssued\nVoid\nOn Hold\nCancelled",
          read_only=1, no_copy=1, in_list_view=1, in_standard_filter=1, allow_on_submit=1, print_hide=1)
    b.add("cz_linked_invoice", "Linked Invoice", "Link", "Sales Invoice", read_only=1, no_copy=1,
          allow_on_submit=1, print_hide=1)
    b.add("cz_follow_up_date", "Follow-up Date", "Date", allow_on_submit=1)

    return top.fields + b.fields


ALL = ("Airline", "Hotel", "Visa", "Transport", "Umrah", "Hajj", "Tour", "Ticketing")


def item_fields():
    """Item-table columns used by the PDF invoice layouts (airline / hotel)."""
    b = _Builder("item_name")
    common = {"hidden": 1}
    b.add("cz_passenger", "Passenger", **common)
    b.add("cz_ticket_no", "Ticket No.", **common)
    b.add("cz_airline", "Airline", **common)
    b.add("cz_sector", "Sector", **common)
    b.add("cz_travel_date", "Travel Date", "Date", **common)
    b.add("cz_hotel_city", "Hotel / City", **common)
    b.add("cz_room_type", "Room Type", **common)
    b.add("cz_lead_guest", "Lead Guest", **common)
    b.add("cz_rooms", "Rooms", "Int", **common)
    b.add("cz_nights", "Nights", "Int", **common)
    b.add("cz_unit_rate", "Rate / Room / Night", "Currency", **common)
    b.add("cz_other_fees", "Other Fees", "Currency", **common)
    return b.fields


SHARED_ITEM_FIELDS = (
    ("final_price", "Selling Price", "Currency", None, {}),
    ("government_fee", "Non Taxable", "Currency", None, {}),
    ("taxed_price", "Taxable", "Currency", None, {"read_only": 1}),
    ("tax_rate", "Tax Rate", "Float", None, {"default": "5"}),
    ("vat", "VAT", "Currency", None, {"read_only": 1}),
    ("purchase_price", "Purchase Price", "Currency", None, {}),
    ("purchase_tax_rate", "IP Tax Rate", "Select", "5\n0", {"default": "5"}),
)

CROWN_ITEM_FIELDS = (
    ("cz_tax_rate", "GST Rate", "Select", "0\n5", {"default": "0", "in_list_view": 1}),
    ("cz_manual", None, "Check", None, {"hidden": 1, "default": "0"}),
    ("cz_flight_no", "Flight No.", "Data", None, {"hidden": 1}),
    ("cz_class", "Class", "Data", None, {"hidden": 1}),
    ("cz_tax_sp", "SP - Service / Passenger Tax", "Currency", None, {"hidden": 1}),
    ("cz_tax_rg", "RG - Regulatory / Government", "Currency", None, {"hidden": 1}),
    ("cz_tax_psf", "PSF - Passenger Service Fee", "Currency", None, {"hidden": 1}),
    ("cz_tax_srb", "SRB - Sindh Revenue Board", "Currency", None, {"hidden": 1}),
    ("cz_tax_yq", "YQ - Carrier Surcharge", "Currency", None, {"hidden": 1}),
    ("cz_tax_other", "Other Taxes", "Currency", None, {"hidden": 1}),
    ("cz_taxes_total", "Taxes Total", "Currency", None, {"hidden": 1, "read_only": 1}),
)


def ensure_item_fields():
    """Create the item-level pricing/tax columns only where they do not exist yet.

    On sites that already run the shaunglobal app these fieldnames exist and are
    left untouched, so its reports keep working; on a clean site crown owns them.
    """
    for dt in ("Sales Order Item", "Sales Invoice Item"):
        existing = {df.fieldname for df in frappe.get_meta(dt).fields}
        anchor = "item_name"
        fields = []
        if "supplier" not in existing:
            fields.append({"fieldname": "supplier", "label": "Supplier", "fieldtype": "Link",
                           "options": "Supplier", "insert_after": anchor})
            anchor = "supplier"
        for fieldname, label, fieldtype, options, kw in SHARED_ITEM_FIELDS + CROWN_ITEM_FIELDS:
            if fieldname in existing:
                continue
            d = {"fieldname": fieldname, "label": label or "", "fieldtype": fieldtype,
                 "insert_after": anchor}
            if options:
                d["options"] = options
            d.update(kw)
            fields.append(d)
            anchor = fieldname
        if fields:
            create_custom_fields({dt: fields}, update=False)


def sales_invoice_fields():
    b = _Builder("naming_series")
    b.add("cz_travel_voucher", "Travel Voucher", "Link", "Sales Order", no_copy=1, in_standard_filter=1)
    b.add("cz_service_type", "Service Type", "Link", "Travel Service Type", read_only=1, no_copy=1,
          in_standard_filter=1)
    b.add("cz_invoice_tax_type", "Invoice Type", "Select", "Without Tax\nWith Tax", default="Without Tax",
          bold=1, read_only=1, no_copy=1,
          description="Derived from the lines: GST rows present = With Tax")
    b.add("cz_correction_reason", "Correction Reason (credit / debit note)", "Small Text",
          depends_on="eval:doc.is_return || doc.is_debit_note")
    return b.fields


def user_fields():
    return [
        {
            "fieldname": "custom_booking_service_types",
            "fieldtype": "Table",
            "label": "Booking Service Types",
            "options": "Booking Service Assignment",
            "insert_after": "roles",
            "no_copy": 1,
            "description": "Booking Voucher Users can create vouchers only for these service types. Leave blank to deny booking access.",
        }
    ]


def get_custom_fields():
    return {
        "Sales Order": sales_order_fields(),
        "Sales Order Item": item_fields(),
        "Sales Invoice": sales_invoice_fields(),
        "Sales Invoice Item": item_fields(),
        "User": user_fields(),
    }


def create():
    create_custom_fields(get_custom_fields(), update=True)
    ensure_item_fields()
