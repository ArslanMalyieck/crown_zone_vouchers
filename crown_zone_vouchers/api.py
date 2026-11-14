import frappe
from frappe import _


@frappe.whitelist()
def set_hold(voucher, hold=1):
    """Accounts: put a Pending/Void voucher On Hold, or release it back to Pending."""
    if not any(r in frappe.get_roles() for r in ("Travel Accounts", "Travel Manager", "System Manager")):
        frappe.throw(_("Not permitted"), frappe.PermissionError)
    v = frappe.db.get_value("Sales Order", voucher, ["docstatus", "cz_invoice_status"], as_dict=True)
    if not v or v.docstatus != 1:
        frappe.throw(_("Voucher is not posted."))
    if int(hold):
        if v.cz_invoice_status not in ("Pending", "Void"):
            frappe.throw(_("Only Pending / Void vouchers can be put on hold."))
        status = "On Hold"
    else:
        if v.cz_invoice_status != "On Hold":
            frappe.throw(_("Voucher is not On Hold."))
        status = "Pending"
    frappe.db.set_value("Sales Order", voucher, "cz_invoice_status", status, update_modified=True)
    return status
