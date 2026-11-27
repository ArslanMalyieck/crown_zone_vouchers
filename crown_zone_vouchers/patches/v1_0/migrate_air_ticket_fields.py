import frappe
from frappe.utils import flt


def execute():
    """Copy legacy air_ticket item taxes into crown cz_* buckets (idempotent)."""
    if not frappe.db.has_column("Sales Invoice Item", "yq_total"):
        return
    rows = frappe.db.sql(
        """
        select name, parent, yq_total, apt_tax, fed_tax, xt_tax, cz_tax_yq, cz_tax_other
        from `tabSales Invoice Item`
        where (ifnull(yq_total,0) <> 0 or ifnull(apt_tax,0) <> 0
               or ifnull(fed_tax,0) <> 0 or ifnull(xt_tax,0) <> 0)
        """,
        as_dict=True,
    )
    changed = set()
    for r in rows:
        updates = {}
        if flt(r.yq_total) and not flt(r.cz_tax_yq):
            updates["cz_tax_yq"] = flt(r.yq_total)
        other = flt(r.apt_tax) + flt(r.fed_tax) + flt(r.xt_tax)
        if other and not flt(r.cz_tax_other):
            updates["cz_tax_other"] = other
        if not updates:
            continue
        frappe.db.set_value("Sales Invoice Item", r.name, updates, update_modified=False)
        changed.add(r.name)

    for name in changed:
        row = frappe.db.get_value(
            "Sales Invoice Item", name,
            ["cz_tax_sp", "cz_tax_rg", "cz_tax_psf", "cz_tax_srb", "cz_tax_yq", "cz_tax_other"],
            as_dict=True,
        )
        total = sum(flt(row.get(f)) for f in ("cz_tax_sp", "cz_tax_rg", "cz_tax_psf",
                                              "cz_tax_srb", "cz_tax_yq", "cz_tax_other"))
        frappe.db.set_value("Sales Invoice Item", name, "cz_taxes_total", flt(total, 2),
                            update_modified=False)

    frappe.logger("crown_zone_vouchers").info(
        "migrate_air_ticket_fields: %s rows updated" % len(changed))
