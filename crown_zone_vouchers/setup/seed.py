SERVICES = [
    # name, voucher prefix, invoice prefix, item
    ("Airline", "ATV", "INV-AIR", "Airline Ticket"),
    ("Hotel", "HTV", "INV-HTL", "Hotel Booking"),
    ("Visa", "VSV", "INV-VISA", "Visa Service"),
    ("Transport", "TRN", "INV-TRN", "Transport Service"),
    ("Umrah", "UMH", "INV-UMH", "Umrah Package"),
    ("Hajj", "HAJ", "INV-HAJ", "Hajj Package"),
    ("Tour", "CZ-ACT", "INV-TUR", "Tour Service"),
]

# optional full naming-series override per service (default is PREFIX-.YYYY.-.#####)
VOUCHER_SERIES = {"Tour": "CZ-ACT-.YYYY.-.####"}

TERMS = {
    "Tour": [],
    "Airline": [
        "This ticket is issued subject to the airline's rules and regulations.",
        "Airline tickets are non-refundable.",
        "Changes, cancellations, date/time amendments and reissue are subject to airline policy and applicable charges.",
        "Passport, visa and all travel documents must be valid as per destination country requirements.",
        "The agency is not responsible for any schedule change, delay or cancellation by the airline.",
        "Please reconfirm flight details directly with the airline before travel.",
        "Any additional services (seat selection, baggage, meals, etc.) are subject to airline charges.",
    ],
    "Hotel": [
        "This booking is subject to hotel's rules and regulations.",
        "Changes, cancellations and no-show are subject to hotel policy.",
        "Check-in and check-out time as per hotel policy.",
        "Guest must present valid passport / ID at the hotel.",
        "The agency is not responsible for any loss, damage or additional charges.",
        "Any additional services (e.g. early check-in, late check-out, meals, etc.) are subject to hotel charges.",
    ],
    "Visa": [
        "This is a visa processing voucher only and not a visa approval.",
        "Visa approval is subject to the concerned embassy/immigration rules.",
        "All documents must be genuine and valid.",
        "Processing time is an estimate and may vary.",
        "The agency is not responsible for any refusal or delay.",
        "Service charges are non-refundable.",
        "Any additional charges (e.g. document verification, insurance, courier) will be applicable.",
        "Client must provide accurate information and comply with all requirements.",
    ],
    "Transport": [
        "Driver waiting time and extra hours subject to booking terms.",
        "Tolls, parking and inter-emirate charges apply as agreed.",
        "Non-refundable or change conditions follow confirmed booking terms.",
    ],
    "Umrah": [
        "Visa, flights, hotel, transport and ziyarat are included only where listed.",
        "Room sharing and hotel allocation subject to confirmed itinerary.",
        "Cancellation, changes and refund terms as per package agreement.",
    ],
    "Hajj": [
        "Hajj visa/permit and package services are subject to official approvals.",
        "Hotels, transport, tents and meals follow confirmed operator inclusions.",
        "Cancellation and changes follow written package terms and supplier policies.",
    ],
}

AIRLINE_TAX_CODES = [
    ("SP", "Service / Passenger tax"), ("SF", "Service fee"), ("YR", "Carrier surcharge YR"),
    ("YQ", "Carrier surcharge YQ"), ("PK", "Pakistan tax"), ("PB", "Airport tax PB"),
    ("IPTT", "IPTT"), ("TXD", "TXD"), ("OAZ", "OAZ"), ("OAB", "OAB"),
    ("KDP", "KDP"), ("KBB", "KBB"), ("GST", "GST on ticket"),
]

VISA_DOCUMENTS = [
    "Valid Passport (minimum 6 months)",
    "Passport Size Photo (White Background)",
    "National ID Card (Front & Back)",
    "6 Months Bank Statement (Stamped)",
    "Bank Maintenance Certificate",
    "Hotel Booking",
    "Return Ticket",
    "Travel Insurance",
    "Educational Certificate (if required)",
    "Previous Visas / Stamps (if available)",
    "Additional documents as per embassy",
]

BRAND_DEFAULTS = {
    "company_name_display": "CROWN ZONE TOURISM & TRAVELS AGENCY",
    "tagline": "Your Journey Our Priority",
    "address": "31, Hussani Housing Society,\nMain University Road, Karachi, 75300",
    "ptcl": "0092-21-33516247",
    "mobile": "0092-335-2226182",
    "email": "crownzone@zonetourism.ae",
    "website": "",
    "srb_no": "S9687169-1",
}
