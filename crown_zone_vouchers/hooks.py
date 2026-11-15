app_name = "crown_zone_vouchers"
app_title = "Crown Zone Vouchers"
app_publisher = "Metadaftr"
app_description = "Travel sales vouchers (Airline, Hotel, Visa, Transport, Umrah, Hajj) on Sales Order with manual invoicing"
app_email = "info@metadaftr.com"
app_license = "mit"
required_apps = ["erpnext"]

before_install = "crown_zone_vouchers.setup.install.before_install"
after_install = "crown_zone_vouchers.setup.install.after_install"
after_migrate = "crown_zone_vouchers.setup.install.after_migrate"

doctype_js = {
    "Sales Order": "public/js/sales_order.js",
    "Sales Invoice": "public/js/sales_invoice.js",
}

_so = "crown_zone_vouchers.events.sales_order."
_si = "crown_zone_vouchers.events.sales_invoice."

doc_events = {
    "Sales Order": {
        "before_insert": _so + "before_insert",
        "before_validate": _so + "before_validate",
        "validate": _so + "validate",
        "before_submit": _so + "before_submit",
        "before_cancel": _so + "before_cancel",
        "on_cancel": _so + "on_cancel",
    },
    "Sales Invoice": {
        "before_insert": _si + "before_insert",
        "before_validate": _si + "before_validate",
        "validate": _si + "validate",
        "on_update": _si + "on_change",
        "on_submit": _si + "on_change",
        "on_cancel": _si + "on_change",
        "on_trash": _si + "on_trash",
    },
}

jinja = {
    "methods": [
        "crown_zone_vouchers.utils.cz_brand",
        "crown_zone_vouchers.utils.cz_qr",
        "crown_zone_vouchers.utils.cz_money",
        "crown_zone_vouchers.utils.cz_date",
        "crown_zone_vouchers.utils.cz_datetime",
        "crown_zone_vouchers.utils.cz_datefmt",
        "crown_zone_vouchers.utils.cz_time12",
        "crown_zone_vouchers.utils.cz_time",
        "crown_zone_vouchers.utils.cz_addr",
        "crown_zone_vouchers.utils.cz_address",
        "crown_zone_vouchers.utils.cz_rooms",
        "crown_zone_vouchers.utils.cz_stay",
        "crown_zone_vouchers.utils.cz_terms",
        "crown_zone_vouchers.utils.cz_voucher",
        "crown_zone_vouchers.utils.cz_user",
        "crown_zone_vouchers.utils.cz_sector",
    ]
}
