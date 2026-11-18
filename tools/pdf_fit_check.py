#!/usr/bin/env python3
"""Page-fit checker for the Crown Zone print formats (no Frappe / bench needed).

Renders every CZ print format with dummy data in three sizes (small / typical / large), converts it to PDF with
wkhtmltopdf using options close to Frappe's (A4, 15mm margins, print media) and measures how much of the printable
page each result uses.

    python3 tools/pdf_fit_check.py                 # all formats, all sizes, prints a table
    python3 tools/pdf_fit_check.py --only Tour     # filter by format-name substring
    python3 tools/pdf_fit_check.py --margin 10     # margin in mm (use the value you configure on the Print Format)
    python3 tools/pdf_fit_check.py --png           # keep page PNGs in /tmp/cz_fit/ for eyeballing

Needs: wkhtmltopdf, pdftoppm (poppler-utils), pillow, jinja2.
Verdict per row:  OK = 1 page and fills >= --min-fill;  SHORT = 1 page but fills less;  OVERFLOW = more than one page;
                  SLIVER = last page holds almost nothing (worst case: a lone footer/wave on page 2).
"""
import argparse, datetime, os, re, subprocess, sys, types
from unittest.mock import MagicMock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))          # .../crown_zone_vouchers (repo root)
sys.path.insert(0, REPO)

# ---------------------------------------------------------------- stub frappe so utils/install import cleanly
fr = MagicMock(name="frappe")


class D(dict):
    def __getattribute__(self, k):
        if k == "get":
            return lambda key, default=None: dict.get(self, key, default)
        if k.startswith("__"):
            return object.__getattribute__(self, k)
        return dict.get(self, k)


fr._dict = D
fu = types.ModuleType("frappe.utils")
fu.flt = lambda v, p=None: float(v or 0)


def _getdate(d):
    if isinstance(d, datetime.datetime):
        return d.date()
    if isinstance(d, datetime.date):
        return d
    return datetime.date.fromisoformat(str(d)[:10])


fu.getdate = _getdate
fu.get_datetime = lambda d: d if isinstance(d, datetime.datetime) else datetime.datetime.fromisoformat(str(d))
fu.get_fullname = lambda u: "Full Name"
sys.modules.update({"frappe": fr, "frappe.utils": fu, "frappe.custom": MagicMock(), "frappe.custom.doctype": MagicMock(),
                    "frappe.custom.doctype.custom_field": MagicMock(),
                    "frappe.custom.doctype.custom_field.custom_field": MagicMock(), "frappe.model": MagicMock(),
                    "frappe.model.document": MagicMock(), "frappe.permissions": MagicMock()})
from crown_zone_vouchers import utils            # noqa: E402
from crown_zone_vouchers.setup import install    # noqa: E402
import jinja2                                    # noqa: E402

TERMS = {"Airline": 7, "Hotel": 6, "Visa": 8, "Transport": 3, "Umrah": 3, "Hajj": 3, "Tour": 0, "Ticketing": 7}
D0 = datetime.date(2026, 11, 5)


def R(**k):
    return D(**k)


def voucher(service, n):
    """n = number of data rows per table (small=1, typical=3, large=9)."""
    t = lambda i: R(traveller_name="Muhammad Ali Khan %d" % i, traveller_type="Adult", gender="Male", relation="Self",
                    date_of_birth=D0, nationality="Pakistani", passport_no="AB12345%02d" % i, passport_expiry=D0,
                    frequent_flyer_no="12345", room_no=(i + 1) // 2 or 1)
    return D(
        name="ATV-2026-00001", service_type=service, transaction_date=D0, customer_name="ABC Enterprises (Pvt) Ltd",
        contact_display="Ali Khan", contact_mobile="+92 300 1234567", contact_email="ali.khan@abc.com",
        address_display="Office # 45, Clifton<br>Karachi, Pakistan", po_no="Corporate Travel",
        cz_booking_reference="BK-12345", cz_booking_date=D0, cz_booking_status="Confirmed", cz_supplier="Supplier",
        cz_supplier_confirmation_no="CONF-998877", cz_customer_remarks="Business travel - client meeting",
        cz_prepared_by="a@x.com", cz_posted_by="b@x.com", cz_prepared_on=datetime.datetime(2026, 11, 2, 10, 15),
        cz_posted_on=datetime.datetime(2026, 11, 2, 12, 45), cz_lead_guest="Mr. Ahmed Khan",
        cz_contact_whatsapp="+92 300 1234567", cz_nationality="Pakistani", cz_total_adults=2, cz_total_children=1,
        cz_children_ages="5, 9", cz_travellers=[t(i) for i in range(1, n + 1)],
        cz_air_tickets=[R(passenger_name="Muhammad Ali Khan %d" % i, airline="Emirates", pnr="ABC123",
                          ticket_no="176-12345678%02d" % i, booking_ref="BR-%d" % i, tour_code="TC1", ticket_date=D0,
                          gds="Galileo") for i in range(1, n + 1)],
        cz_flight_segments=[R(sector_from="KHI", sector_to="DXB", flight_no="EK 601", cabin_class="Economy",
                              travel_date=D0, departure_time=datetime.timedelta(hours=9, minutes=5),
                              arrival_time=datetime.timedelta(hours=11, minutes=20), status="Confirmed",
                              transport_mode="Flight") for _ in range(max(1, n // 2 + 1))],
        cz_hotel_name="Hilton Dubai Jumeirah", cz_hotel_address="The Walk, Jumeirah Beach Residence, Dubai",
        cz_hotel_city_country="Dubai, United Arab Emirates", cz_check_in=D0, cz_check_out=D0, cz_total_nights=5,
        cz_hotel_stays=[R(hotel_name="Makkah Clock Tower" if i % 2 else "Pullman Zamzam Madinah",
                          city="Makkah" if i % 2 else "Madinah", nights=5, room_type="Deluxe Room", rooms=2,
                          occupancy="Double", guests_text="4 Adults", meal_plan="BB", bed_type="King",
                          extra_bed="No") for i in range(1, max(2, n // 2 + 1) + 1)],
        cz_visa_type="UAE 5 Years Multiple Entry", cz_destination_country="United Arab Emirates",
        cz_processing_country="Pakistan", cz_embassy_center="VFS Global", cz_purpose_of_travel="Tourism / Visit",
        cz_application_ref="UAESY-778899", cz_application_date=D0, cz_expected_travel_date=D0,
        cz_expected_return_date=D0, cz_visa_validity="5 Years", cz_processing_time="10 - 15 Working Days",
        cz_visa_status="In Process",
        cz_doc_checklist=[R(document_name="Valid Passport (minimum 6 months)", received=i % 2) for i in range(1, 12)],
        cz_transport_service="Airport transfer / One-way",
        cz_trips=[R(vehicle_type="Hiace Van", plate_no="K-1234", pickup_datetime=datetime.datetime(2026, 11, 5, 9, 0),
                    pickup_location="Jinnah International Airport", dropoff_location="Hilton Dubai", passengers=3,
                    flight_no="EK 601", driver_name="Driver", driver_contact="+971 50 111 2222", waiting_hours=1,
                    driver_notes="Meet at arrivals") for _ in range(max(1, n // 3))],
        cz_package_name="Gold Package 15 Days", cz_package_type="Group", cz_travel_date=D0, cz_return_date=D0,
        cz_group_ref="GRP-77", cz_visa_ref="V-123", cz_flight_bus_details="", cz_transport_ziyarat="Ziyarat Makkah & Madinah",
        cz_meal_plan="Breakfast + Dinner", cz_room_sharing="Quad sharing", cz_mina_arafat="Mina Tent A12",
        cz_guide_meals="Guide + 3 meals", cz_inclusions="Visa, flights, hotels", cz_exclusions="Personal expenses",
        cz_voucher_title="Desert Safari", cz_tour_name="Desert Safari - Sharing (Land Cruiser)", cz_tour_date=D0,
        cz_pickup_location="Ibis Deira Creekside Dubai", cz_pickup_time=datetime.timedelta(hours=15),
        cz_dropoff_location="", cz_important_note="Please be ready at the pickup point 15 minutes before pickup.",
        in_words="PKR One Hundred Thousand Only", taxes=[],
        items=[R(ticket_no="TKT-%d" % i, cz_ticket_no="176-12345678%02d" % i, cz_passenger="Muhammad Ali Khan %d" % i,
                 cz_flight_no="EK 60%d" % i, cz_class="Y", cz_sector="KHI-DXB", cz_travel_date=D0,
                 description="Airline ticket %d" % i, item_name="Airline Ticket", qty=1.0,
                 final_price=52000.0 + i, rate=49000.0 + i, amount=49000.0 + i, cz_taxes_total=3000.0,
                 cz_tax_sp=2000.0, cz_tax_psf=1000.0, cz_tax_srb=0.0, cz_tax_rg=0.0, cz_tax_yq=0.0,
                 cz_tax_other=0.0) for i in range(1, n + 1)])


def invoice(service, n, with_tax):
    items = []
    for i in range(1, n + 1):
        taxes_item = 3000.0 if with_tax else 0.0
        selling = 50000.0 + i * 5000.0
        net = selling - taxes_item
        items.append(R(cz_passenger="Muhammad Ali Khan %d" % i, cz_ticket_no="176-12345678%02d" % i,
                       cz_airline="Emirates", cz_flight_no="EK 60%d" % i, cz_class="Y",
                       cz_sector="KHI-DXB-LHR", cz_travel_date=D0, cz_hotel_city="Hilton Dubai, Dubai",
                       cz_room_type="Deluxe", cz_lead_guest="Ali Khan", cz_rooms=2, cz_nights=5,
                       cz_unit_rate=20000.0, cz_other_fees=500.0,
                       description="Service line %d - description text" % i, item_name="Service", qty=1.0,
                       final_price=selling, rate=net, amount=net, cz_taxes_total=taxes_item,
                       cz_tax_sp=2000.0 if with_tax else 0.0, cz_tax_psf=1000.0 if with_tax else 0.0,
                       cz_tax_srb=0.0, cz_tax_rg=0.0, cz_tax_yq=0.0, cz_tax_other=0.0))
    if service == "Ticketing" and n >= 3:
        items.append(R(description="Service / card charge", item_name="Service Charge", qty=2.0, rate=2500.0,
                       amount=5000.0, final_price=5000.0, cz_taxes_total=0.0))
    net_total = sum(i.amount for i in items)
    tax_total = sum(i.cz_taxes_total for i in items)
    taxes = [R(description="GST 5%", rate=5, charge_type="Actual", tax_amount=tax_total)] if tax_total else []
    name = "INV-TKT-2026-00001" if service == "Ticketing" else "INV-AIR-2026-00001"
    return D(name=name, posting_date=D0, customer_name="ABC Enterprises (Pvt) Ltd", tax_id="1234567-8",
             cz_travel_voucher="ATV-2026-00001", cz_service_type=service,
             cz_invoice_tax_type="With Tax" if with_tax else "Without Tax", net_total=net_total,
             grand_total=net_total + tax_total, total_taxes_and_charges=tax_total,
             in_words="PKR One Hundred Thousand Only", items=items, taxes=taxes,
             po_no="Corporate Travel", contact_display="Ali Khan", contact_mobile="+92 300 1234567",
             contact_email="ali.khan@abc.com", address_display="Office # 45, Clifton<br>Karachi, Pakistan")


def make_env(V, logo):
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(REPO), undefined=jinja2.Undefined)
    brand = D(name="CROWN ZONE TOURISM & TRAVELS AGENCY", tagline="Your Journey Our Priority",
              address="31, Hussani Housing Society,<br>Main University Road, Karachi, 75300", ptcl="0092-21-33516247",
              mobile="0092-335-2226182", email="info@crownzone.com", website="", srb="S9687169-1", logo=logo,
              accounts_email=utils.ACCOUNTS_EMAIL, accounts_mobile=utils.ACCOUNTS_MOBILE)
    png = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
    env.globals.update(cz_brand=lambda: brand, cz_qr=lambda t: png, cz_money=utils.cz_money, cz_date=utils.cz_date,
                       cz_datefmt=utils.cz_datefmt, cz_time12=utils.cz_time12, cz_time=utils.cz_time,
                       cz_datetime=utils.cz_datetime, cz_addr=utils.cz_addr, cz_rooms=utils.cz_rooms, cz_stay=utils.cz_stay,
                       cz_terms=lambda s: ["Term %d - sample condition text that runs over a normal line length." % i
                                           for i in range(1, TERMS.get(s, 3) + 1)],
                       cz_user=lambda u: "User Name", cz_sector=utils.cz_sector, cz_voucher=lambda si: V,
                       cz_address=lambda d: "Office # 45, Clifton, Karachi, Pakistan",
                       cz_ticket_row=utils.cz_ticket_row, cz_ticket_rows=utils.cz_ticket_rows,
                       cz_chunks=utils.cz_chunks, cz_tax_buckets=utils.cz_tax_buckets,
                       cz_words=lambda a, c="PKR": "RUPEES %s ONLY" % utils.cz_money(a))
    return env


def calibrate():
    """Scale of this wkhtmltopdf build (patched-Qt builds used by Frappe give ~1.0, unpatched apt builds ~0.77).

    The PDF page is shrunk by the same factor so the layout in CSS px is identical to a 1:1 build."""
    from PIL import Image
    d = "/tmp/cz_fit"
    os.makedirs(d, exist_ok=True)
    open(d + "/calib.html", "w").write('<html><body style="margin:0"><div style="height:400px;width:300px;background:#000"></div></body></html>')
    subprocess.run(["wkhtmltopdf", "-q", "-T", "15mm", "-B", "15mm", "-L", "15mm", "-R", "15mm", "--page-size", "A4",
                    d + "/calib.html", d + "/calib.pdf"], stderr=subprocess.DEVNULL)
    subprocess.run(["pdftoppm", "-r", "100", "-png", "-singlefile", d + "/calib.pdf", d + "/calib"], check=True)
    im = Image.open(d + "/calib.png").convert("L")
    w, h = im.size
    px = im.load()
    ys = [y for y in range(h) if px[w // 8, y] < 50]
    measured_mm = (max(ys) - min(ys) + 1) / 100.0 * 25.4
    return max(0.3, min(1.2, measured_mm / (400 / 96.0 * 25.4)))


def measure(pdf, outprefix, margin_mm, keep, page_h_mm=297.0):
    """Return [(page_no, fill_ratio)] using the lowest non-white pixel inside the printable area."""
    from PIL import Image
    subprocess.run(["pdftoppm", "-r", "40", "-png", pdf, outprefix], check=True)
    pages = sorted(f for f in os.listdir(os.path.dirname(outprefix)) if f.startswith(os.path.basename(outprefix)) and f.endswith(".png"))
    res = []
    for i, f in enumerate(pages, 1):
        path = os.path.join(os.path.dirname(outprefix), f)
        im = Image.open(path).convert("L")
        w, h = im.size
        mm = h / page_h_mm
        top, bottom = int(margin_mm * mm), int(h - margin_mm * mm)
        px = im.load()
        last = top
        for y in range(h - 1, top - 1, -1):
            if any(px[x, y] < 245 for x in range(0, w, 2)):
                last = y
                break
        res.append((i, max(0.0, min(1.0, (min(last, bottom) - top) / float(bottom - top)))))
        if not keep:
            os.remove(path)
    return res


MONTHS = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"


def lint_text(text, name, doc_name):
    """Data-quality / wrapping defects visible in the rendered text."""
    issues = []
    if re.search(r"\bNone\b", text):
        issues.append("literal None")
    if "undefined" in text:
        issues.append("undefined")
    if "{{" in text:
        issues.append("unrendered {{")
    lines = [ln.rstrip() for ln in text.splitlines()]
    for idx, line in enumerate(lines[:-1]):
        nxt = lines[idx + 1].strip()
        if not nxt:
            continue
        if re.search(r"\d{1,2}-(?:%s)-?$" % MONTHS, line) and re.match(r"^\d", nxt):
            issues.append("date wrapped")
        if re.search(r"\d{3}-\d{2,}$", line) and re.match(r"^\d", nxt):
            issues.append("ticket no wrapped")
    clean = "\n".join(ln for ln in text.splitlines() if "quote invoice" not in ln.lower())
    if "Ticketing" in name and doc_name and clean.count(doc_name) > 1:
        issues.append("invoice no x%d" % clean.count(doc_name))
    return sorted(set(issues))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--margin", type=float, default=15.0)
    ap.add_argument("--min-fill", type=float, default=0.85)
    ap.add_argument("--png", action="store_true")
    ap.add_argument("--lint", action="store_true")
    ap.add_argument("--logo", default="")
    a = ap.parse_args()
    out = "/tmp/cz_fit"
    os.makedirs(out, exist_ok=True)
    scale = calibrate()
    print("wkhtmltopdf scale = %.3f (%s)" % (scale, "1:1 build" if abs(scale - 1) < 0.03 else "unpatched build - page is scaled to emulate 1:1"))
    rows = []
    sizes = (("small", 1), ("typical", 3), ("large", 9))
    for name, doctype, html in install.print_format_defs():
        if name in ("CZ Voucher", "CZ Invoice") or a.only.lower() not in name.lower():
            continue
        svc = next((s for s in TERMS if s in name), "Airline")
        for label, n in sizes:
            if doctype == "Sales Order":
                V, doc = voucher(svc, n), None
                doc = V
            else:
                V = voucher(svc, n)
                doc = invoice(svc, n, "With Tax" in name)
            env = make_env(V, a.logo)
            try:
                body = env.from_string(html).render(doc=doc)
            except Exception as e:
                rows.append((name, label, "RENDER-ERROR", str(e)[:60]))
                continue
            slug = (name + "_" + label).replace(" ", "_").replace("-", "").lower()
            htmlf, pdf = os.path.join(out, slug + ".html"), os.path.join(out, slug + ".pdf")
            open(htmlf, "w").write("<html><head><meta charset='utf-8'></head><body>%s</body></html>" % body)
            m = "%.2fmm" % (a.margin * scale)
            subprocess.run(["wkhtmltopdf", "-q", "--print-media-type", "--background", "--encoding", "UTF-8",
                            "--page-width", "%.2fmm" % (210 * scale), "--page-height", "%.2fmm" % (297 * scale),
                            "-T", m, "-B", m, "-L", m, "-R", m, htmlf, pdf], stderr=subprocess.DEVNULL)
            fills = measure(pdf, os.path.join(out, slug), a.margin * scale, a.png, 297 * scale)
            pages = len(fills)
            if pages == 1:
                verdict = "OK" if fills[0][1] >= a.min_fill else "SHORT"
            else:
                verdict = "SLIVER" if fills[-1][1] < 0.15 else "OVERFLOW"
            detail = "pages=%d  fill=%s" % (pages, " / ".join("%d%%" % (f * 100) for _, f in fills))
            if a.lint:
                txt = subprocess.run(["pdftotext", "-layout", pdf, "-"], capture_output=True, text=True).stdout
                issues = lint_text(txt, name, doc.name)
                if issues:
                    detail += "  [" + ", ".join(issues) + "]"
                    if verdict in ("OK", "SHORT"):
                        verdict = "LINT"
            rows.append((name, label, verdict, detail))
    w = max(len(r[0]) for r in rows)
    print("margin=%gmm  min-fill=%d%%" % (a.margin, a.min_fill * 100))
    for r in rows:
        print("%-*s  %-8s %-9s %s" % (w, r[0], r[1], r[2], r[3]))
    bad = [r for r in rows if r[2] != "OK"]
    print("\n%d of %d combinations need work" % (len(bad), len(rows)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
