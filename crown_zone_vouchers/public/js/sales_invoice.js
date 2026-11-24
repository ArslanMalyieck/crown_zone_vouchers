// Crown Zone Vouchers - Sales Invoice (manual invoice by Accounts)
const CZ_SI_COLS = {
	Airline: ["cz_passenger", "cz_ticket_no", "cz_airline", "cz_sector", "cz_travel_date"],
	Ticketing: ["cz_passenger", "cz_ticket_no", "cz_airline", "cz_flight_no", "cz_class", "cz_sector", "cz_travel_date"],
	Hotel: ["cz_hotel_city", "cz_room_type", "cz_lead_guest", "cz_rooms", "cz_nights", "cz_unit_rate", "cz_other_fees"],
};
const CZ_SI_ALL = [...new Set(Object.values(CZ_SI_COLS).flat())];
const CZ_SI_EXISTING = ["custom_item_code", "final_price", "government_fee", "taxed_price", "vat",
	"supplier", "purchase_price", "purchase_tax_rate"];
const CZ_SI_GRID_ALL = ["item_code", "description", "qty", "rate", "amount", "price_list_rate",
	"final_price", "government_fee", "taxed_price", "vat", "supplier", "supplier_name",
	"purchase_price", "purchase_tax_rate", "cz_tax_rate", "cz_taxes_total", "cz_passenger",
	"cz_ticket_no", "cz_airline", "cz_sector", "cz_travel_date", "cz_flight_no", "cz_class",
	"cz_hotel_city", "cz_room_type", "cz_lead_guest", "cz_rooms", "cz_nights", "cz_unit_rate", "cz_other_fees"];
const CZ_SI_LAYOUT = {
	Ticketing: [["item_code", 1], ["cz_passenger", 1], ["cz_ticket_no", 1], ["cz_sector", 1],
		["cz_travel_date", 1], ["final_price", 1], ["cz_tax_rate", 1], ["cz_taxes_total", 1],
		["purchase_price", 1], ["supplier", 1]],
	default: [["item_code", 1], ["description", 2], ["final_price", 1], ["government_fee", 1],
		["cz_tax_rate", 1], ["purchase_price", 1], ["supplier", 1], ["vat", 1]],
};

function cz_si_layout(grid, service) {
	const layout = CZ_SI_LAYOUT[service] || CZ_SI_LAYOUT.default;
	const shown = new Set(layout.map((x) => x[0]));
	CZ_SI_GRID_ALL.forEach((fn) => cz_si_prop(grid, fn, "in_list_view", shown.has(fn) ? 1 : 0));
	layout.forEach(([fn, w]) => {
		cz_si_prop(grid, fn, "columns", w);
		cz_si_prop(grid, fn, "in_list_view", 1);
		cz_si_prop(grid, fn, "hidden", 0);
	});
}

function cz_si_prop(grid, fieldname, prop, value) {
	try {
		grid.update_docfield_property(fieldname, prop, value);
	} catch (e) {
		/* field not installed on this site */
	}
}

frappe.ui.form.on("Sales Invoice", {
	refresh(frm) {
		if (frm.is_new() && !frm.doc.cz_travel_voucher) {
			const so = (frm.doc.items || []).map((i) => i.sales_order).find((x) => x);
			if (so) frm.set_value("cz_travel_voucher", so);
		}
		cz_si_columns(frm);
	},
	cz_travel_voucher(frm) {
		if (!frm.doc.cz_travel_voucher) return;
		frappe.db.get_value("Sales Order", frm.doc.cz_travel_voucher, "service_type").then((r) => {
			frm.set_value("cz_service_type", r.message && r.message.service_type);
			cz_si_columns(frm);
		});
	},
	cz_service_type(frm) { cz_si_columns(frm); },
});

function cz_si_columns(frm) {
	const grid = frm.fields_dict.items && frm.fields_dict.items.grid;
	if (!grid) return;
	const service = frm.doc.cz_service_type;
	const show = CZ_SI_COLS[service] || [];
	CZ_SI_ALL.forEach((fn) => {
		const on = show.includes(fn);
		cz_si_prop(grid, fn, "hidden", on ? 0 : 1);
		cz_si_prop(grid, fn, "in_list_view", on ? 1 : 0);
	});
	CZ_SI_EXISTING.forEach((fn) => cz_si_prop(grid, fn, "hidden", 0));
	cz_si_prop(grid, "cz_tax_rate", "hidden", 1);
	if (service) cz_si_layout(grid, service);
	grid.reset_grid();
}
