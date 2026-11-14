// Crown Zone Vouchers - Sales Invoice (manual invoice by Accounts)
frappe.ui.form.on("Sales Invoice", {
	refresh(frm) {
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
	cz_invoice_tax_type(frm) {
		if (frm.doc.cz_invoice_tax_type === "Without Tax") {
			frm.set_value("taxes_and_charges", "");
			frm.clear_table("taxes");
			frm.refresh_field("taxes");
			frm.trigger("calculate_taxes_and_totals");
		} else if (frm.doc.cz_invoice_tax_type === "With Tax" && !(frm.doc.taxes || []).length && frm.doc.cz_service_type) {
			frappe.db.get_value("Travel Service Type", frm.doc.cz_service_type, "default_tax_template").then((r) => {
				const t = r.message && r.message.default_tax_template;
				if (t) frm.set_value("taxes_and_charges", t);
			});
		}
	},
});

function cz_si_columns(frm) {
	const COLS = {
		Airline: ["cz_passenger", "cz_ticket_no", "cz_airline", "cz_sector", "cz_travel_date"],
		Hotel: ["cz_hotel_city", "cz_room_type", "cz_lead_guest", "cz_rooms", "cz_nights", "cz_unit_rate", "cz_other_fees"],
	};
	const ALL = [].concat(COLS.Airline, COLS.Hotel);
	const grid = frm.fields_dict.items && frm.fields_dict.items.grid;
	if (!grid) return;
	const show = COLS[frm.doc.cz_service_type] || [];
	ALL.forEach((fn) => {
		const on = show.includes(fn);
		grid.update_docfield_property(fn, "hidden", on ? 0 : 1);
		grid.update_docfield_property(fn, "in_list_view", on ? 1 : 0);
	});
	grid.reset_grid();
}
