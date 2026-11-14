import frappe
from frappe import _
from frappe.utils import add_days, getdate, nowdate


def execute(filters=None):
    filters = frappe._dict(filters or {})
    return get_columns(), get_data(filters)


def get_columns():
    return [
        {"fieldname": "voucher", "label": _("Voucher No."), "fieldtype": "Link", "options": "Sales Order", "width": 150},
        {"fieldname": "service_type", "label": _("Type"), "fieldtype": "Link", "options": "Travel Service Type", "width": 90},
        {"fieldname": "posted_on", "label": _("Posted Date"), "fieldtype": "Datetime", "width": 150},
        {"fieldname": "customer", "label": _("Customer"), "fieldtype": "Link", "options": "Customer", "width": 180},
        {"fieldname": "supplier", "label": _("Supplier"), "fieldtype": "Link", "options": "Supplier", "width": 140},
        {"fieldname": "posted_by", "label": _("Posted By"), "fieldtype": "Link", "options": "User", "width": 140},
        {"fieldname": "sales_pkr", "label": _("Sales PKR"), "fieldtype": "Currency", "options": "currency", "width": 120},
        {"fieldname": "invoice_status", "label": _("Invoice Status"), "fieldtype": "Data", "width": 110},
        {"fieldname": "linked_invoice", "label": _("Invoice"), "fieldtype": "Link", "options": "Sales Invoice", "width": 150},
        {"fieldname": "action", "label": _("Action"), "fieldtype": "Data", "width": 170},
    ]


def get_data(f):
    flt = {"docstatus": 1, "service_type": ["is", "set"]}
    if f.service_type:
        flt["service_type"] = f.service_type
    if f.customer:
        flt["customer"] = f.customer
    if f.supplier:
        flt["cz_supplier"] = f.supplier
    if f.posted_by:
        flt["cz_posted_by"] = f.posted_by
    if f.invoice_status:
        flt["cz_invoice_status"] = f.invoice_status
    if f.voucher_no:
        flt["name"] = ["like", "%" + f.voucher_no + "%"]
    from_date = f.from_date or add_days(nowdate(), -30)
    to_date = f.to_date or nowdate()
    flt["cz_posted_on"] = ["between", [str(getdate(from_date)) + " 00:00:00", str(getdate(to_date)) + " 23:59:59"]]

    rows = frappe.get_all(
        "Sales Order", filters=flt, order_by="cz_posted_on desc",
        fields=["name as voucher", "service_type", "cz_posted_on as posted_on", "customer_name as customer",
                "cz_supplier as supplier", "cz_posted_by as posted_by", "base_net_total as sales_pkr",
                "cz_invoice_status as invoice_status", "cz_linked_invoice as linked_invoice", "customer as customer_id"],
    )
    for r in rows:
        r["customer"] = r.pop("customer_id")
    return rows
