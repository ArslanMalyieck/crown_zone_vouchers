"""Enterprise smoke test for Booking Voucher User / Accounts approval / invoicing.

Run only on a disposable test site:
    bench --site cz-test.localhost execute crown_zone_vouchers.tests.enterprise_smoke.run
"""
import frappe
from frappe.utils import nowdate

from crown_zone_vouchers.tests import smoke

RESULTS = []
BOOKING = "cz.booking.air@example.com"
VISA = "cz.booking.visa@example.com"
ACCOUNTS = "cz.accounts@example.com"
BOTH = "cz.both@example.com"


def check(name, fn):
    try:
        out = fn()
        RESULTS.append((name, True, ""))
        return out
    except Exception as exc:
        RESULTS.append((name, False, "%s: %s" % (type(exc).__name__, str(exc)[:500])))
        frappe.db.rollback()
        return None


def make_user(email, first_name, roles, services):
    if not frappe.db.exists("User", email):
        frappe.get_doc({
            "doctype": "User", "email": email, "first_name": first_name,
            "user_type": "System User", "enabled": 1, "send_welcome_email": 0,
        }).insert(ignore_permissions=True)
    user = frappe.get_doc("User", email)
    current = {r.role for r in user.roles}
    for role in roles:
        if role not in current:
            user.append("roles", {"role": role})
    user.set("custom_booking_service_types", [])
    for service in services:
        user.append("custom_booking_service_types", {"service_type": service, "enabled": 1})
    user.save(ignore_permissions=True)
    frappe.db.commit()
    return email


def booking_payload(service):
    data = smoke.payload(service)
    data["cz_booking_status"] = "Confirmed"
    return data


def run():
    frappe.set_user("Administrator")
    smoke.ensure_party()
    make_user(BOOKING, "Air Booking", ["Booking Voucher User"], ["Airline", "Hotel"])
    make_user(VISA, "Visa Booking", ["Booking Voucher User"], ["Visa"])
    make_user(ACCOUNTS, "Accounts Approver", ["Travel Accounts"], [])
    make_user(BOTH, "Self Approver", ["Booking Voucher User", "Travel Accounts"], ["Airline"])

    created = {}

    def create_authorized():
        frappe.set_user(BOOKING)
        doc = frappe.get_doc(booking_payload("Airline")).insert()
        _assert(doc.workflow_state == "Draft", "new voucher must start in Draft")
        created["airline"] = doc.name
        frappe.db.commit()
        return doc.name

    check("Booking Voucher User creates assigned Airline voucher", create_authorized)

    def unauthorized_service():
        frappe.set_user(BOOKING)
        try:
            frappe.get_doc(booking_payload("Visa")).insert()
        except frappe.ValidationError as exc:
            _assert("not assigned" in str(exc).lower(), "unexpected error: %s" % exc)
            return
        raise AssertionError("unauthorized Visa voucher was created")

    check("Booking Voucher User cannot create unassigned Visa voucher", unauthorized_service)

    def direct_service_mutation():
        frappe.set_user(BOOKING)
        doc = frappe.get_doc("Sales Order", created["airline"])
        doc.service_type = "Visa"
        try:
            doc.save()
        except frappe.ValidationError as exc:
            _assert("not assigned" in str(exc).lower(), "unexpected error: %s" % exc)
            return
        raise AssertionError("direct service mutation was accepted")

    check("Direct service mutation is rejected server-side", direct_service_mutation)

    def cannot_create_invoice():
        frappe.set_user(BOOKING)
        _assert(not frappe.has_permission("Sales Invoice", "create"), "booking user can create Sales Invoice")
        return True

    check("Booking Voucher User has no Sales Invoice create permission", cannot_create_invoice)

    def submit_for_approval():
        frappe.set_user(BOOKING)
        doc = frappe.get_doc("Sales Order", created["airline"])
        from frappe.model.workflow import apply_workflow
        apply_workflow(doc, "Submit for Approval")
        doc.reload()
        _assert(doc.workflow_state == "Pending Accounts Approval", "state=%s" % doc.workflow_state)
        _assert(doc.docstatus == 0, "submit-for-approval must stay draft")
        frappe.db.commit()
        return doc.name

    check("Booking user submits voucher for Accounts approval", submit_for_approval)

    def booking_cannot_post():
        frappe.set_user(BOOKING)
        doc = frappe.get_doc("Sales Order", created["airline"])
        try:
            doc.submit()
        except Exception as exc:
            _assert("approval" in str(exc).lower() or "permission" in str(exc).lower(), "unexpected error: %s" % exc)
            return
        raise AssertionError("booking user posted without approval")

    check("Booking user cannot post before approval", booking_cannot_post)

    def self_approval_blocked():
        frappe.set_user(BOTH)
        doc = frappe.get_doc(booking_payload("Airline")).insert()
        from frappe.model.workflow import apply_workflow
        apply_workflow(doc, "Submit for Approval")
        doc.reload()
        try:
            apply_workflow(doc, "Approve & Post")
        except frappe.ValidationError as exc:
            _assert("self approval" in str(exc).lower(), "unexpected error: %s" % exc)
            frappe.db.rollback()
            return
        raise AssertionError("creator approved own voucher")

    check("Self approval is blocked", self_approval_blocked)

    def approve_and_post():
        frappe.set_user(ACCOUNTS)
        doc = frappe.get_doc("Sales Order", created["airline"])
        from frappe.model.workflow import apply_workflow
        apply_workflow(doc, "Approve & Post")
        doc.reload()
        _assert(doc.workflow_state == "Approved", "state=%s" % doc.workflow_state)
        _assert(doc.docstatus == 1, "approved voucher must be submitted")
        _assert(doc.cz_approved_by == ACCOUNTS, "approved_by=%s" % doc.cz_approved_by)
        _assert(doc.cz_invoice_status == "Pending", "invoice_status=%s" % doc.cz_invoice_status)
        frappe.db.commit()
        return doc.name

    check("Accounts user approves and posts voucher", approve_and_post)

    created_invoice = {}

    def create_invoice():
        frappe.set_user(ACCOUNTS)
        from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice
        si = make_sales_invoice(created["airline"])
        si.cz_invoice_tax_type = "Without Tax"
        si.taxes = []
        si.insert()
        created_invoice["name"] = si.name
        _assert(si.cz_travel_voucher == created["airline"], "voucher link missing")
        _assert(frappe.db.get_value("Sales Order", created["airline"], "cz_invoice_status") == "Draft", "status not Draft")
        frappe.db.commit()
        return si.name

    check("Accounts creates invoice from approved voucher", create_invoice)

    def duplicate_blocked():
        frappe.set_user(ACCOUNTS)
        from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice
        try:
            si = make_sales_invoice(created["airline"])
            si.cz_invoice_tax_type = "Without Tax"
            si.taxes = []
            si.insert()
        except frappe.ValidationError as exc:
            _assert("active invoice" in str(exc).lower(), "unexpected error: %s" % exc)
            return
        raise AssertionError("duplicate active invoice was accepted")

    check("Duplicate active invoice is blocked", duplicate_blocked)

    def invoice_print():
        frappe.set_user(ACCOUNTS)
        html = frappe.get_print("Sales Invoice", created_invoice["name"], "CZ Airline Invoice - Without Tax")
        _assert("SALES INVOICE" in html and created_invoice["name"] in html, "print format failed")
        return True

    check("Premium Airline invoice print renders", invoice_print)

    def invoice_submit_and_cancel():
        frappe.set_user(ACCOUNTS)
        si = frappe.get_doc("Sales Invoice", created_invoice["name"])
        si.submit()
        _assert(frappe.db.get_value("Sales Order", created["airline"], "cz_invoice_status") == "Issued", "not Issued")
        frappe.db.commit()
        frappe.set_user("Administrator")
        si.reload()
        si.cancel()
        _assert(frappe.db.get_value("Sales Order", created["airline"], "cz_invoice_status") == "Void", "not Void")
        frappe.db.commit()
        return True

    check("Invoice status: submit -> Issued, manager cancel -> Void", invoice_submit_and_cancel)

    def reject_requires_remarks():
        frappe.set_user(BOOKING)
        doc = frappe.get_doc(booking_payload("Airline")).insert()
        frappe.db.commit()
        from frappe.model.workflow import apply_workflow
        apply_workflow(doc, "Submit for Approval")
        doc.reload()
        frappe.db.commit()
        frappe.set_user(ACCOUNTS)
        doc = frappe.get_doc("Sales Order", doc.name)
        try:
            apply_workflow(doc, "Reject")
        except frappe.ValidationError as exc:
            _assert("remarks" in str(exc).lower(), "unexpected error: %s" % exc)
            return doc.name
        raise AssertionError("rejection without remarks accepted")

    check("Rejection without remarks is rejected", reject_requires_remarks)

    def report_rows():
        frappe.set_user(ACCOUNTS)
        from crown_zone_vouchers.crown_zone_vouchers.report.travel_voucher_invoice_pending.travel_voucher_invoice_pending import get_data
        rows = get_data(frappe._dict(invoice_status="Pending"))
        _assert(any(r["voucher"] == created["airline"] for r in rows), "approved invoice-pending voucher missing")
        return True

    check("Invoice-pending report includes approved pending voucher", report_rows)

    print("\n==== CROWN ZONE ENTERPRISE SMOKE ====")
    for name, ok, msg in RESULTS:
        print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else "  -> " + msg))
    fails = [r for r in RESULTS if not r[1]]
    print("\n%d checks, %d failed" % (len(RESULTS), len(fails)))
    frappe.set_user("Administrator")
    frappe.db.commit()
    return {"checks": len(RESULTS), "failed": len(fails)}


def _assert(condition, message):
    if not condition:
        raise AssertionError(message)
