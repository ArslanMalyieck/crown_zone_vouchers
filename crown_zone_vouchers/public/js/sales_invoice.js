// Crown Zone Vouchers - Sales Invoice (manual invoice by Accounts)
const CZ_SI_COLS = {
	Airline: ["cz_passenger", "cz_ticket_no", "cz_airline", "cz_sector", "cz_travel_date"],
	Ticketing: ["cz_passenger", "cz_ticket_no", "cz_airline", "cz_flight_no", "cz_class", "cz_sector", "cz_travel_date"],
	Hotel: ["cz_hotel_city", "cz_room_type", "cz_lead_guest", "cz_rooms", "cz_nights", "cz_unit_rate", "cz_other_fees"],
};
const CZ_SI_ALL = [].concat(CZ_SI_COLS.Airline, CZ_SI_COLS.Hotel);
const CZ_SI_PRICING = ["final_price", "government_fee", "cz_tax_rate", "vat", "supplier", "purchase_price"];

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
	CZ_SI_PRICING.forEach((fn) => cz_si_prop(grid, fn, "hidden", service ? 0 : 1));
	cz_si_prop(grid, "cz_tax_rate", "read_only", 0);
	cz_si_prop(grid, "tax_rate", "read_only", 1);
	grid.reset_grid();
}

frappe.ui.form.on("Sales Invoice Item", {
	final_price(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (row) frappe.model.set_value(cdt, cdn, "final_price", flt(row.final_price) || flt(row.rate));
	},
});
