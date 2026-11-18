import re
from datetime import timedelta

import frappe
from frappe.utils import flt, get_datetime, getdate, get_fullname


ACCOUNTS_MOBILE = "+92 327 8447933"
ACCOUNTS_EMAIL = "accounts1@zonetourism.ae"


def _embed_logo(logo):
    """Inline the logo as a data URI so PDFs never depend on the host / file permissions."""
    if not logo or str(logo).startswith("data:"):
        return logo or ""
    key = "cz_logo_uri:%s" % logo
    try:
        cached = frappe.cache().get_value(key)
        if cached:
            return cached
    except Exception:
        pass
    try:
        import base64
        import mimetypes

        name = frappe.db.get_value("File", {"file_url": logo}, "name")
        if not name:
            return logo
        f = frappe.get_doc("File", name)
        content = f.get_content()
        if not content:
            return logo
        mime = mimetypes.guess_type(f.file_name or "")[0] or "image/png"
        uri = "data:%s;base64,%s" % (mime, base64.b64encode(content).decode())
    except Exception:
        return logo
    try:
        frappe.cache().set_value(key, uri, expires_in_sec=3600)
    except Exception:
        pass
    return uri


def cz_brand():
    """Company block shown on every voucher / invoice."""
    s = frappe.get_cached_doc("Travel Voucher Settings")
    logo = s.logo
    if not logo:
        try:
            company = frappe.defaults.get_global_default("company") or frappe.db.get_single_value(
                "Global Defaults", "default_company")
            meta = frappe.get_meta("Company")
            for fn in ("custom_logo", "company_logo"):
                if company and meta.has_field(fn):
                    logo = frappe.db.get_value("Company", company, fn)
                    if logo:
                        break
        except Exception:
            logo = None
    return frappe._dict(
        name=s.company_name_display or "CROWN ZONE TOURISM & TRAVELS AGENCY",
        tagline=s.tagline or "",
        address=(s.address or "").replace("\n", "<br>"),
        ptcl=s.ptcl or "",
        mobile=s.mobile or "",
        email=s.email or "",
        website=s.website or "",
        srb=s.srb_no or "",
        logo=_embed_logo(logo),
        accounts_mobile=ACCOUNTS_MOBILE,
        accounts_email=ACCOUNTS_EMAIL,
    )


def cz_qr(text):
    """PNG data-URI QR code encoding the voucher reference."""
    text = str(text or "")
    try:
        import pyqrcode

        return "data:image/png;base64," + pyqrcode.create(text, error="M").png_as_base64_str(scale=4, quiet_zone=1)
    except Exception:
        pass
    try:
        import base64
        import io

        import qrcode

        img = qrcode.make(text)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return ""


def cz_money(v):
    return "{:,.2f}".format(flt(v))


def cz_date(d):
    return getdate(d).strftime("%d-%b-%Y") if d else ""


def cz_datefmt(d, fmt="%d %b %Y"):
    return getdate(d).strftime(fmt) if d else ""


def cz_time12(t):
    hhmm = cz_time(t)
    if not hhmm:
        return ""
    h, m = hhmm.split(":")
    h = int(h)
    return "%02d:%s %s" % ((h % 12) or 12, m, "AM" if h < 12 else "PM")


def cz_datetime(d):
    return get_datetime(d).strftime("%d-%b-%Y %I:%M %p") if d else ""


def cz_time(t):
    if not t:
        return ""
    if isinstance(t, timedelta):
        total = int(t.total_seconds())
        return "%02d:%02d" % ((total // 3600) % 24, (total % 3600) // 60)
    parts = str(t).split(":")
    try:
        return "%02d:%02d" % (int(parts[0]), int(parts[1]))
    except Exception:
        return str(t)


def cz_addr(html):
    if not html:
        return ""
    s = re.sub(r"<br\s*/?>", ", ", str(html), flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"(,\s*)+", ", ", s).strip(" ,\n")


def cz_address(doc):
    """Invoice bill-to address, including a fallback to the linked Address record."""
    raw = doc.get("address_display")
    if raw and "<" in str(raw):
        return cz_addr(raw)
    addr_name = doc.get("customer_address") or doc.get("shipping_address_name")
    if not addr_name and doc.get("customer"):
        addr_name = frappe.db.get_value(
            "Dynamic Link",
            {"link_doctype": "Customer", "link_name": doc.customer, "parenttype": "Address"},
            "parent",
        )
    if addr_name and frappe.db.exists("Address", addr_name):
        try:
            a = frappe.get_doc("Address", addr_name)
            parts = [a.address_line1, a.address_line2, a.city, a.state, a.pincode, a.country]
            return ", ".join([p for p in parts if p])
        except Exception:
            pass
    return cz_addr(raw)


def cz_user(user):
    return get_fullname(user) if user else ""


def cz_rooms(travellers):
    """[{room, names:[..]}] grouped by room number for 'Guest Names (Room-wise)'."""
    groups = {}
    for t in travellers or []:
        if not t.traveller_name:
            continue
        groups.setdefault(t.room_no or 1, []).append(t.traveller_name)
    return [{"room": k, "names": v} for k, v in sorted(groups.items())]


def cz_stay(doc, keyword):
    """'Hotel Name (N nights); ...' for stay rows whose city / hotel mentions keyword."""
    out = []
    for r in doc.get("cz_hotel_stays") or []:
        hay = ((r.city or "") + " " + (r.hotel_name or "")).lower()
        if keyword.lower() in hay:
            out.append("%s (%s nights)" % (r.hotel_name or r.city, r.nights or 0))
    return "; ".join(out)


def cz_terms(service_type):
    if not service_type or not frappe.db.exists("Travel Service Type", service_type):
        return []
    st = frappe.get_cached_doc("Travel Service Type", service_type)
    return [t.term for t in st.terms if t.term]


def cz_voucher(si):
    """Linked posted voucher (Sales Order) of a Sales Invoice, or an empty dict."""
    name = si.get("cz_travel_voucher") if si else None
    if name and frappe.db.exists("Sales Order", name):
        return frappe.get_doc("Sales Order", name)
    return frappe._dict()


def cz_sector(doc):
    """KHI-DXB-LHR style itinerary string from flight segments."""
    segs = doc.get("cz_flight_segments") or []
    if not segs:
        return ""
    parts = [segs[0].sector_from or ""]
    for s in segs:
        parts.append(s.sector_to or "")
    return "-".join([p for p in parts if p])


TAX_BUCKETS = (
    ("SP", "cz_tax_sp", "Service / Passenger Tax"),
    ("RG", "cz_tax_rg", "Regulatory / Government"),
    ("PSF", "cz_tax_psf", "Passenger Service Fee"),
    ("SRB", "cz_tax_srb", "Sindh Revenue Board"),
    ("YQ", "cz_tax_yq", "Carrier Surcharge (YQ)"),
    ("Other", "cz_tax_other", "Other Taxes"),
)


def cz_ticket_row(row):
    """Printed split of one ticket row: fare + taxes = selling price."""
    taxes = flt(row.get("cz_taxes_total"))
    selling = flt(row.get("final_price"))
    if selling <= 0:
        selling = flt(row.get("rate"))
    return frappe._dict(
        fare=flt(selling - taxes, 2),
        taxes=flt(taxes, 2),
        amount=flt(selling, 2),
        taxes_breakup=_breakup(row),
    )


def _breakup(row):
    out = []
    for code, field, _label in TAX_BUCKETS:
        amount = flt(row.get(field))
        if amount:
            out.append("%s %s" % (code, cz_money(amount)))
    return "  ".join(out)


def cz_ticket_rows(items):
    """Split invoice / voucher lines into ticket rows and other charges."""
    tickets, charges = [], []
    for row in items or []:
        if row.get("cz_ticket_no") or row.get("cz_passenger") or row.get("cz_taxes_total"):
            tickets.append(row)
        else:
            charges.append(row)
    return frappe._dict(tickets=tickets, charges=charges)


def cz_chunks(rows, first=14, rest=20):
    rows = list(rows or [])
    if not rows:
        return []
    out = [rows[:first]]
    start = first
    while start < len(rows):
        out.append(rows[start:start + rest])
        start += rest
    return out


def cz_tax_buckets(items):
    out = []
    for code, field, label in TAX_BUCKETS:
        total = sum(flt(r.get(field)) for r in (items or []))
        if total:
            out.append(frappe._dict(code=code, label=label, total=flt(total, 2)))
    return out


def cz_words(amount, currency="PKR"):
    from frappe.utils import money_in_words
    try:
        words = money_in_words(amount, currency)
    except Exception:
        return ""
    return words.upper() if currency == "PKR" else words
