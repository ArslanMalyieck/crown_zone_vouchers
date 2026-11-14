import frappe
from frappe import _

ACCOUNTS_ROLES = ("Travel Accounts", "Travel Manager", "Accounts Manager", "System Manager")
DEFAULT_INV = {"Airline": "INV-AIR", "Hotel": "INV-HTL", "Visa": "INV-VISA", "Transport": "INV-TRN",
               "Umrah": "INV-UMH", "Hajj": "INV-HAJ", "Tour": "INV-TUR"}


def inv_series(service_type):
    prefix = frappe.db.get_value("Travel Service Type", service_type, "invoice_prefix") or DEFAULT_INV.get(service_type)
    return "%s-.YYYY.-.#####" % prefix


def _link_voucher(doc):
    if not doc.get("cz_travel_voucher"):
        so = next((i.sales_order for i in doc.items if i.get("sales_order")), None)
        if so:
            doc.cz_travel_voucher = so
        elif doc.get("is_return") and doc.get("return_against"):
            doc.cz_travel_voucher = frappe.db.get_value("Sales Invoice", doc.return_against, "cz_travel_voucher")
    if doc.get("cz_travel_voucher"):
        doc.cz_service_type = frappe.db.get_value("Sales Order", doc.cz_travel_voucher, "service_type")


def before_insert(doc, method=None):
    _link_voucher(doc)
    if doc.get("cz_service_type") and not doc.get("is_return"):
        doc.naming_series = inv_series(doc.cz_service_type)


def _copy_item_details(doc):
    if not doc.get("cz_travel_voucher"):
        return
    invoice_fields = {df.fieldname for df in frappe.get_meta("Sales Invoice Item").fields}
    order_fields = {df.fieldname for df in frappe.get_meta("Sales Order Item").fields}
    copy_fields = [f for f in ("supplier", "purchase_price", "purchase_tax_rate", "final_price",
                               "government_fee", "tax_rate", "taxed_price", "vat",
                               "ticket_no", "cz_ticket_no", "custom_item_code")
                   if f in invoice_fields and f in order_fields]
    for item in doc.items:
        source_name = item.get("so_detail")
        if not source_name:
            continue
        source = frappe.db.get_value("Sales Order Item", source_name, copy_fields, as_dict=True)
        if not source:
            continue
        for fieldname in copy_fields:
            value = source.get(fieldname)
            if value is not None and value != "":
                setattr(item, fieldname, value)
        if item.get("supplier") and "supplier_name" in invoice_fields:
            item.supplier_name = frappe.db.get_value("Supplier", item.supplier, "supplier_name")


def before_validate(doc, method=None):
    _link_voucher(doc)
    _copy_item_details(doc)


def validate(doc, method=None):
    if not doc.get("cz_travel_voucher"):
        return
    v = frappe.db.get_value("Sales Order", doc.cz_travel_voucher,
                            ["docstatus", "cz_invoice_status"], as_dict=True)
    if not v or v.docstatus != 1:
        frappe.throw(_("Invoice can only be prepared from a Posted voucher."))

    is_correction = doc.get("is_return") or doc.get("is_debit_note")
    if is_correction:
        if not any(r in frappe.get_roles() for r in ("Travel Manager", "Accounts Manager", "System Manager")):
            frappe.throw(_("Credit / Debit notes are controlled - only Travel Manager can issue them."))
        if not doc.get("cz_correction_reason"):
            frappe.throw(_("Correction Reason is required for credit / debit notes."))
    else:
        if doc.is_new() and v.cz_invoice_status == "On Hold":
            frappe.throw(_("Voucher is On Hold. Release the hold first."))
        dup = frappe.db.exists("Sales Invoice", {
            "cz_travel_voucher": doc.cz_travel_voucher, "docstatus": ["<", 2],
            "is_return": 0, "name": ["!=", doc.name or ""]})
        if dup:
            frappe.throw(_("Voucher {0} already has an active invoice {1}.").format(doc.cz_travel_voucher, dup))

    if doc.cz_invoice_tax_type == "Without Tax" and doc.get("taxes"):
        frappe.throw(_("Invoice Type is Without Tax but tax rows exist. Remove taxes or choose With Tax."))
    if doc.cz_invoice_tax_type == "With Tax" and not doc.get("taxes"):
        frappe.throw(_("Invoice Type is With Tax - add the applicable tax rows."))


def refresh_invoice_status(voucher, exclude=None):
    if not voucher:
        return
    filters = {"cz_travel_voucher": voucher, "is_return": 0}
    if exclude:
        filters["name"] = ["!=", exclude]
    rows = frappe.get_all("Sales Invoice", filters=filters, fields=["name", "docstatus"], order_by="creation asc")
    issued = [r for r in rows if r.docstatus == 1]
    draft = [r for r in rows if r.docstatus == 0]
    cancelled = [r for r in rows if r.docstatus == 2]
    current = frappe.db.get_value("Sales Order", voucher, "cz_invoice_status")
    if current == "Cancelled":
        return
    linked = None
    if issued:
        status, linked = "Issued", issued[-1].name
    elif draft:
        status, linked = "Draft", draft[-1].name
    elif cancelled:
        status = "Void"
    else:
        status = "On Hold" if current == "On Hold" else "Pending"
    frappe.db.set_value("Sales Order", voucher, {"cz_invoice_status": status, "cz_linked_invoice": linked},
                        update_modified=False)


def on_change(doc, method=None):
    if doc.get("cz_travel_voucher") and not doc.get("is_return"):
        refresh_invoice_status(doc.cz_travel_voucher)


def on_trash(doc, method=None):
    if doc.get("cz_travel_voucher") and not doc.get("is_return"):
        refresh_invoice_status(doc.cz_travel_voucher, exclude=doc.name)
