import json
import os

import frappe

from crown_zone_vouchers.setup import custom_fields
from crown_zone_vouchers.setup.seed import (AIRLINE_TAX_CODES, BRAND_DEFAULTS, SERVICES, TERMS, VISA_DOCUMENTS,
                                            VOUCHER_SERIES)

ROLES = ("Travel Sales", "Travel Accounts", "Travel Manager")
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
    # Sales Order = voucher
    _grant("Sales Order", "Travel Sales", read=1, write=1, create=1, submit=1, delete=1, print=1, email=1, report=1)
    _grant("Sales Order", "Travel Accounts", read=1, print=1, email=1, report=1, export=1)
    _grant("Sales Order", "Travel Manager", read=1, write=1, create=1, submit=1, cancel=1, delete=1, amend=1,
           print=1, email=1, report=1, export=1)
    # Sales Invoice = manual invoice (Sales has NO access)
    _grant("Sales Invoice", "Travel Accounts", read=1, write=1, create=1, submit=1, print=1, email=1, report=1, export=1)
    _grant("Sales Invoice", "Travel Manager", read=1, write=1, create=1, submit=1, cancel=1, delete=1, amend=1,
           print=1, email=1, report=1, export=1)
    # link targets needed by the forms
    for dt in ("Customer", "Supplier", "Item", "Currency", "Contact", "Address", "Company", "Terms and Conditions",
               "Sales Taxes and Charges Template", "Account", "Cost Center", "Price List", "Item Group", "UOM",
               "Print Format", "Travel Service Type", "Airline Tax Code"):
        for role in ROLES:
            _grant(dt, role, read=1)
    _grant("Customer", "Travel Sales", create=1, write=1)
    _grant("Contact", "Travel Sales", create=1, write=1)


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
def create_workspace():
    cards = [("Invoice Pending", "Pending", "#ECAD4B"), ("Invoice On Hold", "On Hold", "#FF5858")]
    for label, status, color in cards:
        if not frappe.db.exists("Number Card", label):
            frappe.get_doc({
                "doctype": "Number Card", "label": label, "document_type": "Sales Order", "function": "Count",
                "type": "Document Type", "is_public": 1, "show_percentage_stats": 0, "color": color,
                "module": "Crown Zone Vouchers",
                "filters_json": json.dumps([["Sales Order", "docstatus", "=", 1, False],
                                            ["Sales Order", "cz_invoice_status", "=", status, False]]),
            }).insert(ignore_permissions=True)

    if frappe.db.exists("Workspace", "Travel Vouchers"):
        return
    blocks = [{"id": "h1", "type": "header", "data": {"text": '<span class="h4"><b>Travel Vouchers</b></span>', "col": 12}}]
    shortcuts = []
    for c in cards:
        blocks.append({"id": "n_" + c[1].replace(" ", ""), "type": "number_card", "data": {"number_card_name": c[0], "col": 4}})
    blocks.append({"id": "h2", "type": "header", "data": {"text": '<span class="h5"><b>New Voucher</b></span>', "col": 12}})
    for name, *_ in SERVICES:
        label = "New %s Voucher" % name
        shortcuts.append({"label": label, "type": "URL", "url": "/app/sales-order/new?service_type=%s" % name})
        blocks.append({"id": "s_" + name, "type": "shortcut", "data": {"shortcut_name": label, "col": 3}})
    blocks.append({"id": "h3", "type": "header", "data": {"text": '<span class="h5"><b>Accounts</b></span>', "col": 12}})
    for label, url in (("Posted Voucher Queue", "/app/query-report/Posted Voucher Queue"),
                       ("All Vouchers", "/app/sales-order"), ("Invoices", "/app/sales-invoice")):
        shortcuts.append({"label": label, "type": "URL", "url": url})
        blocks.append({"id": "a_" + label.replace(" ", ""), "type": "shortcut", "data": {"shortcut_name": label, "col": 3}})

    frappe.get_doc({
        "doctype": "Workspace", "name": "Travel Vouchers", "label": "Travel Vouchers", "title": "Travel Vouchers",
        "module": "Crown Zone Vouchers", "public": 1, "content": json.dumps(blocks),
        "number_cards": [{"number_card_name": c[0], "label": c[0]} for c in cards],
        "shortcuts": shortcuts,
    }).insert(ignore_permissions=True)
