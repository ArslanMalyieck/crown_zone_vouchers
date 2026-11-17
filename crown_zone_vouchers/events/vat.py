import frappe
from frappe import _
from frappe.utils import flt

ZERO_RATED_SERVICES = ("Airline", "Hotel", "Ticketing")


def default_tax_rate(service_type):
    """Service default GST rate; ticket-type services are zero rated unless set per row."""
    if not service_type or service_type in ZERO_RATED_SERVICES:
        return 0
    return flt(frappe.db.get_value("Travel Service Type", service_type, "default_tax_rate") or 0)


def gst_account(company):
    if not company:
        return None
    for like in ("%VAT 5% - %", "%GST%", "%Sales Tax%"):
        name = frappe.db.get_value(
            "Account", {"name": ["like", like], "company": company, "is_group": 0}, "name")
        if name:
            return name
    return frappe.db.get_value(
        "Account", {"account_type": "Tax", "company": company, "is_group": 0}, "name")


def rate_of(item, service_type=None):
    for key in ("cz_tax_rate", "tax_rate"):
        value = item.get(key)
        if value not in (None, ""):
            return flt(value)
    return default_tax_rate(service_type)


def split(item, service_type=None):
    """Selling price is tax inclusive. Returns (selling, taxable, vat, net, rate)."""
    selling = flt(item.get("final_price"))
    if selling <= 0:
        selling = flt(item.get("rate"))
    non_taxable = min(flt(item.get("government_fee")), selling)
    base = flt(selling - non_taxable, 2)
    rate = rate_of(item, service_type)
    if rate > 0 and base > 0:
        taxable = flt(base * 100 / (100 + rate), 2)
        vat = flt(taxable * rate / 100, 2)
    else:
        taxable = base
        vat = 0
    return selling, taxable, vat, flt(selling - vat, 2), rate


def apply_vat(doc, service_type=None):
    """Item-level VAT (shaunglobal method) with an exact grand total.

    GST is the only document-level tax; every other airline / service charge stays
    on the item row. Selling Price remains what the customer pays.
    """
    items = [i for i in (doc.get("items") or []) if (i.get("item_code") or i.get("custom_item_code"))]
    if not items:
        return
    service_type = service_type or doc.get("service_type") or doc.get("cz_service_type")
    company = doc.get("company")
    selling_total = 0.0
    net_total = 0.0
    groups = {}
    for item in items:
        qty = flt(item.get("qty")) or 1
        selling, taxable, vat, net, rate = split(item, service_type)
        item.taxed_price = taxable
        item.vat = vat
        item.price_list_rate = net
        item.rate = net
        if item.meta.has_field("tax_rate"):
            item.tax_rate = rate
        selling_total += selling * qty
        net_total += net * qty
        if vat > 0:
            groups[rate] = flt(groups.get(rate, 0) + vat * qty, 2)

    doc.set("taxes", [])
    if doc.meta.has_field("taxes_and_charges"):
        doc.taxes_and_charges = None
    residual = flt(flt(selling_total, 2) - flt(net_total, 2), 2)
    if groups and residual:
        top = max(groups, key=lambda r: groups[r])
        groups[top] = flt(groups[top] + residual - sum(groups.values()), 2)
        account = gst_account(company)
        if not account:
            frappe.throw(_("No GST / VAT tax account found for company {0}. Add one before saving this document.").format(company))
        cost_center = frappe.db.get_value("Company", company, "cost_center")
        for rate in sorted(groups):
            amount = groups[rate]
            if not amount:
                continue
            label = int(rate) if rate == int(rate) else rate
            doc.append("taxes", {
                "account_head": account,
                "charge_type": "Actual",
                "description": "GST {0}%".format(label),
                "rate": rate,
                "cost_center": cost_center,
                "tax_amount": amount,
                "base_tax_amount": amount,
                "tax_amount_after_discount_amount": amount,
                "total": flt(net_total, 2),
                "base_total": flt(net_total, 2),
            })
    doc.calculate_taxes_and_totals()
