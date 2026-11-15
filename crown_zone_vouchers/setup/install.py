import json
import os

import frappe

from crown_zone_vouchers.setup import custom_fields
from crown_zone_vouchers.setup.seed import (AIRLINE_TAX_CODES, BRAND_DEFAULTS, SERVICES, TERMS, VISA_DOCUMENTS,
                                            VOUCHER_SERIES)

ROLES = ("Booking Voucher User", "Travel Sales", "Travel Accounts", "Travel Manager")
TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates", "print")
INC = "crown_zone_vouchers/templates/print/"


# ------------------------------------------------------------------ entry points
def before_install():
    create_roles()


def after_install():
    run_all(force_print=True)


def after_migrate():
    force = False
    try:
        force = bool(frappe.db.get_single_value("Travel Voucher Settings", "overwrite_print_formats"))
    except Exception:
        pass
    run_all(force_print=force)


def run_all(force_print=False):
    steps = [
        ("roles", create_roles),
        ("seed", seed_masters),
        ("custom_fields", custom_fields.create),
        ("naming", sync_naming_options),
        ("permissions", setup_permissions),
        ("workflow", create_workflow),
        ("print_formats", lambda: create_print_formats(force_print)),
        ("workspace", create_workspace),
    ]
    for name, fn in steps:
        try:
            fn()
            frappe.db.commit()
        except Exception:
            frappe.db.rollback()
            frappe.log_error(title="Crown Zone Vouchers setup: %s" % name)
    frappe.clear_cache()


# ------------------------------------------------------------------ roles & permissions
def create_roles():
    for r in ROLES:
        if not frappe.db.exists("Role", r):
            frappe.get_doc({"doctype": "Role", "role_name": r, "desk_access": 1}).insert(ignore_permissions=True)


def _grant(doctype, role, **perms):
    from frappe.permissions import add_permission, update_permission_property

    add_permission(doctype, role, 0)
    for k, v in perms.items():
        update_permission_property(doctype, role, 0, k, v)


def setup_permissions():
    # Sales Order = Booking Voucher. New operational role; old Travel Sales kept for compatibility.
    _grant("Sales Order", "Booking Voucher User", read=1, write=1, create=1, print=1, email=1, report=1, export=1)
    _grant("Sales Order", "Travel Sales", read=1, write=1, create=1, submit=1, delete=1, print=1, email=1, report=1)
    # Accounts can approve/reject the workflow and submit the approved voucher. No create/edit of drafts.
    _grant("Sales Order", "Travel Accounts", read=1, write=1, submit=1, print=1, email=1, report=1, export=1)
    _grant("Sales Order", "Travel Manager", read=1, write=1, create=1, submit=1, cancel=1, delete=1, amend=1,
           print=1, email=1, report=1, export=1)
    # Sales Invoice = manual invoice from an approved posted voucher (Booking Voucher User has NO access)
    _grant("Sales Invoice", "Travel Accounts", read=1, write=1, create=1, submit=1, print=1, email=1, report=1, export=1)
    _grant("Sales Invoice", "Travel Manager", read=1, write=1, create=1, submit=1, cancel=1, delete=1, amend=1,
           print=1, email=1, report=1, export=1)
    # link targets needed by the forms
    for dt in ("Customer", "Supplier", "Item", "Currency", "Contact", "Address", "Company", "Terms and Conditions",
               "Sales Taxes and Charges Template", "Account", "Cost Center", "Price List", "Item Group", "UOM",
               "Print Format", "Travel Service Type", "Airline Tax Code", "Booking Service Assignment",
               "Workflow", "Workflow State", "Workflow Action Master"):
        for role in ROLES:
            _grant(dt, role, read=1)
    _grant("Customer", "Travel Sales", create=1, write=1)
    _grant("Contact", "Travel Sales", create=1, write=1)
    _grant("Customer", "Booking Voucher User", create=1, write=1)
    _grant("Contact", "Booking Voucher User", create=1, write=1)


# ------------------------------------------------------------------ approval workflow
WORKFLOW_NAME = "Crown Voucher Approval"
WORKFLOW_STATES = [
    ("Draft", "0", "Booking Voucher User", ""),
    ("Pending Accounts Approval", "0", "Travel Accounts", "Warning"),
    ("Approved", "1", "Travel Manager", "Success"),
    ("Rejected", "0", "Booking Voucher User", "Danger"),
]
WORKFLOW_ACTIONS = ("Submit for Approval", "Approve & Post", "Reject", "Return to Draft")
WORKFLOW_TRANSITIONS = [
    ("Draft", "Submit for Approval", "Pending Accounts Approval", "Booking Voucher User", 1),
    ("Draft", "Submit for Approval", "Pending Accounts Approval", "Travel Sales", 1),
    ("Draft", "Submit for Approval", "Pending Accounts Approval", "Travel Manager", 1),
    ("Pending Accounts Approval", "Approve & Post", "Approved", "Travel Accounts", 0),
    ("Pending Accounts Approval", "Approve & Post", "Approved", "Travel Manager", 0),
    ("Pending Accounts Approval", "Reject", "Rejected", "Travel Accounts", 0),
    ("Pending Accounts Approval", "Reject", "Rejected", "Travel Manager", 0),
    ("Rejected", "Return to Draft", "Draft", "Booking Voucher User", 1),
    ("Rejected", "Return to Draft", "Draft", "Travel Sales", 1),
    ("Rejected", "Return to Draft", "Draft", "Travel Manager", 1),
]


def _ensure_workflow_state(state, style=""):
    if not frappe.db.exists("Workflow State", state):
        frappe.get_doc({
            "doctype": "Workflow State",
            "workflow_state_name": state,
            "style": style,
        }).insert(ignore_permissions=True)


def _ensure_workflow_action(action):
    if not frappe.db.exists("Workflow Action Master", action):
        frappe.get_doc({"doctype": "Workflow Action Master", "workflow_action_name": action}).insert(
            ignore_permissions=True
        )


def create_workflow():
    for state, _, _, style in WORKFLOW_STATES:
        _ensure_workflow_state(state, style)
    for action in WORKFLOW_ACTIONS:
        _ensure_workflow_action(action)

    if frappe.db.exists("Workflow", WORKFLOW_NAME):
        wf = frappe.get_doc("Workflow", WORKFLOW_NAME)
        wf.states = []
        wf.transitions = []
    else:
        wf = frappe.new_doc("Workflow")

    wf.update({
        "workflow_name": WORKFLOW_NAME,
        "document_type": "Sales Order",
        "is_active": 1,
        "override_status": 1,
        "send_email_alert": 0,
        "workflow_state_field": "workflow_state",
    })
    for state, doc_status, allow_edit, _style in WORKFLOW_STATES:
        wf.append("states", {
            "state": state,
            "doc_status": doc_status,
            "allow_edit": allow_edit,
            "send_email": 0,
        })
    for state, action, next_state, allowed, self_approval in WORKFLOW_TRANSITIONS:
        wf.append("transitions", {
            "state": state,
            "action": action,
            "next_state": next_state,
            "allowed": allowed,
            "allow_self_approval": self_approval,
            "send_email_to_creator": 0,
        })
    if wf.is_new():
        wf.insert(ignore_permissions=True)
    else:
        wf.save(ignore_permissions=True)

    field = frappe.db.get_value("Custom Field", {"dt": "Sales Order", "fieldname": "workflow_state"}, "name")
    if field:
        from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
        create_custom_fields({"Sales Order": [{
            "fieldname": "workflow_state",
            "fieldtype": "Link",
            "label": "Approval Status",
            "options": "Workflow State",
            "insert_after": "cz_approval_remarks",
            "hidden": 0,
            "read_only": 1,
            "no_copy": 1,
            "allow_on_submit": 1,
            "in_standard_filter": 1,
            "in_list_view": 0,
        }]}, update=True)
    frappe.clear_cache(doctype="Sales Order")


# ------------------------------------------------------------------ masters
def seed_masters():
    # brand settings
    s = frappe.get_doc("Travel Voucher Settings")
    for k, v in BRAND_DEFAULTS.items():
        if not s.get(k):
            s.set(k, v)
    if not s.default_visa_documents:
        s.default_visa_documents = "\n".join(VISA_DOCUMENTS)
    s.save(ignore_permissions=True)

    # airline tax codes
    for code, desc in AIRLINE_TAX_CODES:
        if not frappe.db.exists("Airline Tax Code", code):
            frappe.get_doc({"doctype": "Airline Tax Code", "code": code, "description": desc}).insert(ignore_permissions=True)

    # service items + service types
    group = "Services" if frappe.db.exists("Item Group", "Services") else frappe.db.get_value(
        "Item Group", {"is_group": 0}, "name")
    for name, vp, ip, item in SERVICES:
        if not frappe.db.exists("Item", item):
            try:
                frappe.get_doc({"doctype": "Item", "item_code": item, "item_name": item, "item_group": group,
                                "stock_uom": "Nos", "is_stock_item": 0, "is_sales_item": 1,
                                "is_purchase_item": 0, "description": item}).insert(ignore_permissions=True)
            except Exception:
                frappe.log_error(title="Crown Zone seed item %s" % item)
        if not frappe.db.exists("Travel Service Type", name):
            doc = frappe.get_doc({"doctype": "Travel Service Type", "service_name": name, "enabled": 1,
                                  "voucher_prefix": vp, "invoice_prefix": ip,
                                  "voucher_series": VOUCHER_SERIES.get(name),
                                  "default_item": item if frappe.db.exists("Item", item) else None})
            for t in TERMS[name]:
                doc.append("terms", {"term": t})
            doc.insert(ignore_permissions=True)


def sync_naming_options():
    """Add voucher / invoice series of every service type to the naming_series Select options."""
    from frappe.custom.doctype.property_setter.property_setter import make_property_setter

    v_opts, i_opts = [], []
    for st in frappe.get_all("Travel Service Type", fields=["voucher_prefix", "invoice_prefix", "voucher_series"]):
        v_opts.append(st.voucher_series or "%s-.YYYY.-.#####" % st.voucher_prefix)
        i_opts.append("%s-.YYYY.-.#####" % st.invoice_prefix)
    for doctype, new in (("Sales Order", v_opts), ("Sales Invoice", i_opts)):
        meta = frappe.get_meta(doctype)
        existing = (meta.get_field("naming_series").options or "").split("\n")
        merged = []
        for o in existing + new:
            if o and o not in merged:
                merged.append(o)
        make_property_setter(doctype, "naming_series", "options", "\n".join(merged), "Text")


# ------------------------------------------------------------------ print formats
VOUCHERS = [
    ("CZ Airline Voucher", "voucher_airline.html", ""),
    ("CZ Hotel Voucher", "voucher_hotel.html", ""),
    ("CZ Visa Voucher", "voucher_visa.html", ""),
    ("CZ Transport Voucher", "voucher_transport.html", ""),
    ("CZ Umrah Voucher", "voucher_package.html", '{% set pkg = "Umrah" %}'),
    ("CZ Hajj Voucher", "voucher_package.html", '{% set pkg = "Hajj" %}'),
    ("CZ Tour Voucher", "voucher_tour.html", ""),
]

# (service, template, title)
INVOICES = [
    ("Airline", "invoice_airline.html", "AIRLINE"),
    ("Hotel", "invoice_hotel.html", "HOTEL"),
    ("Visa", "invoice_generic.html", "VISA"),
    ("Transport", "invoice_generic.html", "TRANSPORT"),
    ("Umrah", "invoice_generic.html", "UMRAH PACKAGE"),
    ("Hajj", "invoice_generic.html", "HAJJ PACKAGE"),
    ("Tour", "invoice_generic.html", "TOUR"),
]


def _inc(tpl):
    return '{%% include "%s%s" %%}' % (INC, tpl)


def print_format_defs():
    defs = []
    for name, tpl, pre in VOUCHERS:
        defs.append((name, "Sales Order", (pre + "\n" + _inc(tpl)).strip()))
    for svc, tpl, title in INVOICES:
        for with_tax in (0, 1):
            label = "With Tax" if with_tax else "Without Tax"
            html = '{%% set with_tax = %s %%}\n{%% set svc_title = "%s" %%}\n%s' % (
                "True" if with_tax else "False", title, _inc(tpl))
            defs.append(("CZ %s Invoice - %s" % (svc, label), "Sales Invoice", html))

    # dispatchers (default print formats)
    v = []
    for i, (svc, tpl, pre) in enumerate([("Airline", "voucher_airline.html", ""), ("Hotel", "voucher_hotel.html", ""),
                                         ("Visa", "voucher_visa.html", ""), ("Transport", "voucher_transport.html", ""),
                                         ("Umrah", "voucher_package.html", '{% set pkg = "Umrah" %}'),
                                         ("Hajj", "voucher_package.html", '{% set pkg = "Hajj" %}'),
                                         ("Tour", "voucher_tour.html", "")]):
        v.append('{%% %s doc.service_type == "%s" %%}%s%s' % ("if" if i == 0 else "elif", svc, pre, _inc(tpl)))
    v.append("{% else %}<p>Select a Service Type to print this voucher.</p>{% endif %}")
    defs.append(("CZ Voucher", "Sales Order", "\n".join(v)))

    s = ['{% set with_tax = (doc.cz_invoice_tax_type == "With Tax") %}']
    for i, (svc, tpl, title) in enumerate(INVOICES):
        s.append('{%% %s doc.cz_service_type == "%s" %%}{%% set svc_title = "%s" %%}%s' % (
            "if" if i == 0 else "elif", svc, title, _inc(tpl)))
    s.append("{% else %}{% set svc_title = \"\" %}" + _inc("invoice_generic.html") + "{% endif %}")
    defs.append(("CZ Invoice", "Sales Invoice", "\n".join(s)))
    return defs


def create_print_formats(force=False):
    for name, doctype, html in print_format_defs():
        exists = frappe.db.exists("Print Format", name)
        # dispatchers are app-managed: always refresh so new services (e.g. Tour) are picked up on migrate
        if exists and not force and name not in ("CZ Voucher", "CZ Invoice"):
            continue
        doc = frappe.get_doc("Print Format", name) if exists else frappe.new_doc("Print Format")
        doc.update({"name": name, "doc_type": doctype, "print_format_type": "Jinja", "custom_format": 1,
                    "standard": "No", "disabled": 0, "html": html, "align_labels_right": 0,
                    "show_section_headings": 0, "line_breaks": 0, "raw_printing": 0})
        if exists:
            doc.save(ignore_permissions=True)
        else:
            doc.insert(ignore_permissions=True)

    from frappe.custom.doctype.property_setter.property_setter import make_property_setter

    make_property_setter("Sales Order", None, "default_print_format", "CZ Voucher", "Data", for_doctype=True)
    make_property_setter("Sales Invoice", None, "default_print_format", "CZ Invoice", "Data", for_doctype=True)


# ------------------------------------------------------------------ workspace
def _card(label, filters, color):
    doc = frappe.get_doc("Number Card", label) if frappe.db.exists("Number Card", label) else frappe.new_doc("Number Card")
    doc.update({
        "label": label,
        "document_type": "Sales Order",
        "function": "Count",
        "type": "Document Type",
        "is_public": 1,
        "show_percentage_stats": 0,
        "color": color,
        "module": "Crown Zone Vouchers",
        "filters_json": json.dumps([["Sales Order"] + list(f) for f in filters]),
    })
    if doc.is_new():
        doc.insert(ignore_permissions=True)
    else:
        doc.save(ignore_permissions=True)


def create_workspace():
    cards = [
        ("Total Posted Vouchers", [["docstatus", "=", 1, False]], "#2490EF"),
        ("Draft Vouchers", [["docstatus", "=", 0, False], ["workflow_state", "=", "Draft", False]], "#8D99AE"),
        ("Pending Accounts Approval", [["docstatus", "=", 0, False],
                                        ["workflow_state", "=", "Pending Accounts Approval", False]], "#ECAD4B"),
        ("Approved Vouchers", [["docstatus", "=", 1, False], ["workflow_state", "=", "Approved", False]], "#28A745"),
        ("Invoice Pending", [["docstatus", "=", 1, False], ["cz_invoice_status", "=", "Pending", False]], "#F0AD4E"),
        ("Invoiced Vouchers", [["docstatus", "=", 1, False], ["cz_invoice_status", "=", "Issued", False]], "#6F42C1"),
        ("On Hold", [["docstatus", "=", 1, False], ["cz_invoice_status", "=", "On Hold", False]], "#FF5858"),
        ("Rejected Vouchers", [["docstatus", "=", 0, False], ["workflow_state", "=", "Rejected", False]], "#DC3545"),
        ("Cancelled Vouchers", [["docstatus", "=", 2, False]], "#6C757D"),
        ("Void Invoices", [["docstatus", "=", 1, False], ["cz_invoice_status", "=", "Void", False]], "#A9A9A9"),
    ]
    for label, filters, color in cards:
        _card(label, filters, color)

    blocks = [
        {"id": "h1", "type": "header", "data": {"text": '<span class="h4"><b>Travel Vouchers — Operations</b></span>', "col": 12}},
        {"id": "p1", "type": "paragraph", "data": {"text": "Approval, posting and invoice-pending control for all seven travel services.", "col": 12}},
    ]
    for idx, (label, _filters, _color) in enumerate(cards):
        blocks.append({"id": "n_%s" % idx, "type": "number_card", "data": {"number_card_name": label, "col": 3}})

    shortcuts = []
    blocks.append({"id": "h2", "type": "header", "data": {"text": '<span class="h5"><b>New Voucher</b></span>', "col": 12}})
    for name, *_ in SERVICES:
        label = "New %s Voucher" % name
        shortcuts.append({"label": label, "type": "URL", "url": "/app/sales-order/new?service_type=%s" % name})
        blocks.append({"id": "s_" + name, "type": "shortcut", "data": {"shortcut_name": label, "col": 3}})

    blocks.append({"id": "h3", "type": "header", "data": {"text": '<span class="h5"><b>Accounts &amp; Analysis</b></span>', "col": 12}})
    report_links = (
        ("Invoice Pending Vouchers", "/app/query-report/Travel Voucher Invoice Pending"),
        ("Pending Approval Queue", "/app/sales-order?workflow_state=Pending%20Accounts%20Approval"),
        ("Posted Voucher Queue", "/app/query-report/Posted Voucher Queue"),
        ("All Vouchers", "/app/sales-order"),
        ("Invoices", "/app/sales-invoice"),
    )
    for label, url in report_links:
        shortcuts.append({"label": label, "type": "URL", "url": url})
        blocks.append({"id": "a_" + label.replace(" ", ""), "type": "shortcut", "data": {"shortcut_name": label, "col": 3}})

    if frappe.db.exists("Workspace", "Travel Vouchers"):
        ws = frappe.get_doc("Workspace", "Travel Vouchers")
    else:
        ws = frappe.new_doc("Workspace")
        ws.update({"name": "Travel Vouchers", "label": "Travel Vouchers", "title": "Travel Vouchers",
                   "module": "Crown Zone Vouchers", "public": 1})
    ws.set("number_cards", [])
    ws.set("shortcuts", [])
    ws.content = json.dumps(blocks)
    for label, _filters, _color in cards:
        ws.append("number_cards", {"number_card_name": label, "label": label})
    for shortcut in shortcuts:
        ws.append("shortcuts", shortcut)
    if ws.is_new():
        ws.insert(ignore_permissions=True)
    else:
        ws.save(ignore_permissions=True)
