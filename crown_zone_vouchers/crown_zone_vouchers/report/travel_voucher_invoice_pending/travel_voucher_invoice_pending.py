import frappe
from frappe import _
from frappe.utils import add_days, getdate, nowdate


def execute(filters=None):
    return get_columns(), get_data(frappe._dict(filters or {}))


def get_columns():
    return [
        {"fieldname": "voucher", "label": _("Voucher No."), "fieldtype": "Link", "options": "Sales Order", "width": 145},
        {"fieldname": "service_type", "label": _("Service"), "fieldtype": "Link", "options": "Travel Service Type", "width": 90},
        {"fieldname": "posted_on", "label": _("Posted On"), "fieldtype": "Datetime", "width": 145},
        {"fieldname": "customer", "label": _("Customer"), "fieldtype": "Link", "options": "Customer", "width": 180},
        {"fieldname": "supplier", "label": _("Supplier"), "fieldtype": "Link", "options": "Supplier", "width": 140},
        {"fieldname": "approved_by", "label": _("Approved By"), "fieldtype": "Link", "options": "User", "width": 130},
        {"fieldname": "approved_on", "label": _("Approved On"), "fieldtype": "Datetime", "width": 145},
        {"fieldname": "sales_pkr", "label": _("Sales (PKR)"), "fieldtype": "Currency", "options": "currency", "width": 120},
        {"fieldname": "invoice_status", "label": _("Invoice Status"), "fieldtype": "Data", "width": 110},
        {"fieldname": "action", "label": _("Action"), "fieldtype": "Data", "width": 160},
    ]


def get_data(f):
    filters = {
        "docstatus": 1,
        "service_type": ["is", "set"],
        "cz_invoice_status": ["in", ["Pending", "Void"]],
    }
    if f.service_type:
        filters["service_type"] = f.service_type
    if f.customer:
        filters["customer"] = f.customer
    if f.supplier:
        filters["cz_supplier"] = f.supplier
    if f.company:
        filters["company"] = f.company
    if f.from_date or f.to_date:
        from_date = f.from_date or add_days(nowdate(), -30)
        to_date = f.to_date or nowdate()
        filters["cz_posted_on"] = ["between", [str(getdate(from_date)) + " 00:00:00",
                                                str(getdate(to_date)) + " 23:59:59"]]

    rows = frappe.get_list(
        "Sales Order",
        filters=filters,
        or_filters=[["workflow_state", "=", "Approved"], ["workflow_state", "is", "not set"]],
        fields=[
            "name as voucher", "service_type", "cz_posted_on as posted_on", "customer",
            "customer_name", "cz_supplier as supplier", "cz_approved_by as approved_by",
            "cz_approved_on as approved_on", "base_net_total as sales_pkr",
            "cz_invoice_status as invoice_status", "workflow_state",
        ],
        order_by="cz_posted_on desc",
        limit=0,
    )
    if not rows:
        return rows

    names = [r.voucher for r in rows]
    active = frappe.get_all(
        "Sales Invoice",
        filters={"cz_travel_voucher": ["in", names], "docstatus": ["<", 2], "is_return": 0},
        fields=["cz_travel_voucher"],
    )
    active_set = {r.cz_travel_voucher for r in active}
    return [r for r in rows if r.voucher not in active_set]
