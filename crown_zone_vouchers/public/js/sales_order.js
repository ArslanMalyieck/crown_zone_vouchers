// Crown Zone Vouchers - Sales Order (= travel voucher) client script
const CZ_ITEM_COLS = {
	Airline: ["cz_passenger", "cz_ticket_no", "cz_airline", "cz_sector", "cz_travel_date"],
	Ticketing: ["cz_passenger", "cz_ticket_no", "cz_airline", "cz_flight_no", "cz_class", "cz_sector", "cz_travel_date"],
	Hotel: ["cz_hotel_city", "cz_room_type", "cz_lead_guest", "cz_rooms", "cz_nights", "cz_unit_rate", "cz_other_fees"],
};
const CZ_ITEM_ALL = ["cz_passenger", "cz_ticket_no", "cz_airline", "cz_sector", "cz_travel_date",
	"cz_flight_no", "cz_class", "cz_hotel_city", "cz_room_type", "cz_lead_guest", "cz_rooms",
	"cz_nights", "cz_unit_rate", "cz_other_fees"];
const CZ_EXISTING_ITEM_FIELDS = ["custom_item_code", "final_price", "government_fee", "taxed_price", "vat",
	"supplier", "supplier_name", "purchase_price", "purchase_tax_rate"];
const CZ_TICKET_TAX = ["cz_tax_sp", "cz_tax_rg", "cz_tax_psf", "cz_tax_srb", "cz_tax_yq", "cz_tax_other"];
const CZ_GRID_ALL = ["item_code", "description", "qty", "rate", "amount", "price_list_rate",
	"final_price", "government_fee", "taxed_price", "vat", "supplier", "supplier_name",
	"purchase_price", "purchase_tax_rate", "cz_tax_rate", "cz_taxes_total", "cz_passenger",
	"cz_ticket_no", "cz_airline", "cz_sector", "cz_travel_date", "cz_flight_no", "cz_class",
	"cz_hotel_city", "cz_room_type", "cz_lead_guest", "cz_rooms", "cz_nights", "cz_unit_rate", "cz_other_fees"];
const CZ_GRID_LAYOUT = {
	Ticketing: [["item_code", 1], ["cz_passenger", 1], ["cz_ticket_no", 1], ["cz_sector", 1],
		["cz_travel_date", 1], ["final_price", 1], ["cz_tax_rate", 1], ["cz_taxes_total", 1],
		["purchase_price", 1], ["supplier", 1]],
	Airline: [["item_code", 1], ["cz_passenger", 1], ["cz_ticket_no", 1], ["cz_sector", 1],
		["cz_travel_date", 1], ["final_price", 1], ["cz_tax_rate", 1], ["purchase_price", 1], ["supplier", 1]],
	Hotel: [["item_code", 1], ["cz_hotel_city", 1], ["cz_room_type", 1], ["cz_rooms", 1],
		["cz_nights", 1], ["final_price", 1], ["cz_tax_rate", 1], ["purchase_price", 1], ["supplier", 1]],
	default: [["item_code", 1], ["description", 2], ["final_price", 1], ["government_fee", 1],
		["cz_tax_rate", 1], ["purchase_price", 1], ["supplier", 1], ["vat", 1]],
};

function cz_apply_grid_layout(grid, service) {
	const layout = CZ_GRID_LAYOUT[service] || CZ_GRID_LAYOUT.default;
	const shown = new Set(layout.map((x) => x[0]));
	CZ_GRID_ALL.forEach((fn) => cz_grid_prop(grid, fn, "in_list_view", shown.has(fn) ? 1 : 0));
	layout.forEach(([fn, w]) => {
		cz_grid_prop(grid, fn, "columns", w);
		cz_grid_prop(grid, fn, "in_list_view", 1);
		cz_grid_prop(grid, fn, "hidden", 0);
	});
}

function cz_grid_prop(grid, fieldname, prop, value) {
	try {
		grid.update_docfield_property(fieldname, prop, value);
	} catch (e) {
		/* field not installed on this site */
	}
}

window.cz_item_columns = function (frm) {
	const grid = frm.fields_dict.items && frm.fields_dict.items.grid;
	if (!grid) return;
	const service = frm.doc.service_type;
	const show = CZ_ITEM_COLS[service] || [];
	CZ_ITEM_ALL.forEach((fn) => {
		const on = show.includes(fn);
		cz_grid_prop(grid, fn, "hidden", on ? 0 : 1);
		cz_grid_prop(grid, fn, "in_list_view", on ? 1 : 0);
	});
	CZ_EXISTING_ITEM_FIELDS.forEach((fn) => cz_grid_prop(grid, fn, "hidden", 0));
	CZ_TICKET_TAX.forEach((fn) => cz_grid_prop(grid, fn, "hidden", service === "Ticketing" ? 0 : 1));
	cz_grid_prop(grid, "cz_taxes_total", "hidden", service === "Ticketing" ? 0 : 1);
	cz_grid_prop(grid, "cz_tax_rate", "hidden", service ? 0 : 1);
	if (service) cz_apply_grid_layout(grid, service);
	grid.reset_grid();
};

function cz_roles_ok() {
	const r = frappe.user_roles;
	return r.includes("Travel Accounts") || r.includes("Travel Manager") || r.includes("System Manager");
}

function cz_service_filter(frm) {
	if (!frm || !frm.set_query) return;
	const roles = frappe.user_roles || [];
	const restricted = !roles.includes("Travel Manager") && !roles.includes("System Manager")
		&& !roles.includes("Travel Accounts")
		&& (roles.includes("Booking Voucher User") || roles.includes("Travel Sales"));
	if (!restricted) {
		frm.set_query("service_type", () => ({}));
		return;
	}
	frappe.db.get_list("Booking Service Assignment", {
		filters: { parent: frappe.session.user, enabled: 1 },
		fields: ["service_type"],
		limit: 0,
	}).then((rows) => {
		const names = (rows || []).map((r) => r.service_type).filter(Boolean);
		frm.set_query("service_type", () => ({ filters: { name: ["in", names.length ? names : ["__none__"]] } }));
	});
}

function cz_hold(frm, hold) {
	frappe.call({
		method: "crown_zone_vouchers.api.set_hold",
		args: { voucher: frm.doc.name, hold: hold },
		callback: () => frm.reload_doc(),
	});
}

function cz_base_rate(frm) {
	const cur = frm.doc.cz_purchase_currency;
	const base = frappe.boot.sysdefaults && frappe.boot.sysdefaults.currency;
	return !cur || cur === base ? 1 : flt(frm.doc.cz_exchange_rate);
}

function cz_recalc_purchase(frm) {
	if (frm.doc.service_type === "Airline") cz_recalc_tickets(frm);
	frm.set_value("cz_purchase_amount_pkr", flt(frm.doc.cz_purchase_amount) * cz_base_rate(frm));
}

function cz_recalc_tickets(frm) {
	const taxes = {};
	(frm.doc.cz_air_taxes || []).forEach((t) => {
		const k = cint(t.ticket_row_no) || 1;
		taxes[k] = (taxes[k] || 0) + flt(t.amount);
	});
	const rate = cz_base_rate(frm);
	let total = 0;
	(frm.doc.cz_air_tickets || []).forEach((t) => {
		t.taxes_total = taxes[t.idx] || 0;
		t.ticket_gross = flt(t.supplier_fare) + t.taxes_total;
		t.commission_amount = flt(t.supplier_fare) * flt(t.commission_percent) / 100;
		t.wht_amount = t.commission_amount * flt(t.wht_percent) / 100;
		t.supplier_amount_foreign = t.ticket_gross - t.commission_amount + t.wht_amount;
		t.supplier_amount_pkr = t.supplier_amount_foreign * rate;
		total += t.supplier_amount_foreign;
	});
	frm.doc.cz_purchase_amount = total;
	frm.refresh_field("cz_air_tickets");
	frm.refresh_field("cz_purchase_amount");
}

function cz_nights(a, b) {
	return a && b ? Math.max(frappe.datetime.get_diff(b, a), 0) : 0;
}

frappe.ui.form.on("Sales Order", {
	refresh(frm) {
		cz_item_columns(frm);
		cz_service_filter(frm);
		if (frm.doc.service_type && !frm.is_new()) {
			frm.add_custom_button(__("Rebuild Items"), function () {
				frappe.call({
					method: "crown_zone_vouchers.events.sales_order.rebuild_items",
					args: { docname: frm.doc.name },
					freeze: true,
					freeze_message: __("Rebuilding items..."),
					callback: function () { frm.reload_doc(); },
				});
			}, __("Actions"));
		}
		if (frm.doc.docstatus === 1 && cz_roles_ok() && frm.doc.service_type
			&& (!frm.doc.workflow_state || frm.doc.workflow_state === "Approved")) {
			const st = frm.doc.cz_invoice_status;
			if (["Pending", "Void"].includes(st)) {
				frm.add_custom_button(__("Create Invoice"), () =>
					frappe.model.open_mapped_doc({
						method: "erpnext.selling.doctype.sales_order.sales_order.make_sales_invoice",
						frm: frm,
					}), __("Accounts"));
				frm.add_custom_button(__("Put On Hold"), () => cz_hold(frm, 1), __("Accounts"));
			} else if (st === "On Hold") {
				frm.add_custom_button(__("Release Hold"), () => cz_hold(frm, 0), __("Accounts"));
			}
		}
	},
	service_type(frm) {
		cz_item_columns(frm);
		if (!frm.doc.service_type) return;
		frappe.db.get_value("Travel Service Type", frm.doc.service_type, "voucher_prefix").then((r) => {
			const p = r.message && r.message.voucher_prefix;
			if (p) frm.set_value("naming_series", p + "-.YYYY.-.#####");
		});
	},
	items_add(frm, cdt, cdn) {
		if (!frm.doc.service_type) return;
		const row = locals[cdt] && locals[cdt][cdn];
		if (!row) return;
		row.cz_manual = 1;
		if (!row.cz_tax_rate) {
			frappe.db.get_value("Travel Service Type", frm.doc.service_type, "default_tax_rate").then((r) => {
				const d = r.message && r.message.default_tax_rate;
				frappe.model.set_value(cdt, cdn, "cz_tax_rate", d || "0");
			});
		}
		if (frm.doc.cz_supplier) frappe.model.set_value(cdt, cdn, "supplier", frm.doc.cz_supplier);
	},
	cz_check_in(frm) { frm.set_value("cz_total_nights", cz_nights(frm.doc.cz_check_in, frm.doc.cz_check_out)); },
	cz_check_out(frm) { frm.set_value("cz_total_nights", cz_nights(frm.doc.cz_check_in, frm.doc.cz_check_out)); },
	cz_purchase_amount(frm) { cz_recalc_purchase(frm); },
	cz_exchange_rate(frm) { cz_recalc_purchase(frm); },
	cz_purchase_currency(frm) { cz_recalc_purchase(frm); },
	cz_air_taxes_remove(frm) { cz_recalc_tickets(frm); },
	cz_air_tickets_remove(frm) { cz_recalc_tickets(frm); },
});

// ---- item row: selling price is tax inclusive (shaunglobal method)
function cz_row_calc(frm, cdt, cdn) {
	if (!frm.doc.service_type) return;
	const row = locals[cdt][cdn];
	if (!row) return;
	const selling = flt(row.final_price) || flt(row.rate);
	if (selling <= 0) return;
	const non_taxable = Math.min(flt(row.government_fee), selling);
	const gst = flt(row.cz_tax_rate || row.tax_rate);
	const base = Math.max(selling - non_taxable, 0);
	let taxable = base, vat = 0;
	if (gst > 0 && base > 0) {
		taxable = flt(base * 100 / (100 + gst), 2);
		vat = flt(taxable * gst / 100, 2);
	}
	frappe.model.set_value(cdt, cdn, "taxed_price", taxable);
	frappe.model.set_value(cdt, cdn, "vat", vat);
	frappe.model.set_value(cdt, cdn, "final_price", selling);
}
frappe.ui.form.on("Sales Order Item", {
	final_price: cz_row_calc,
	cz_tax_rate: cz_row_calc,
	government_fee: cz_row_calc,
	rate(frm, cdt, cdn) {
		if (!frm.doc.service_type) return;
		const row = locals[cdt][cdn];
		if (row && !flt(row.final_price)) frappe.model.set_value(cdt, cdn, "final_price", flt(row.rate));
	},
	cz_tax_sp(frm, cdt, cdn) { cz_tax_total(frm, cdt, cdn); },
	cz_tax_rg(frm, cdt, cdn) { cz_tax_total(frm, cdt, cdn); },
	cz_tax_psf(frm, cdt, cdn) { cz_tax_total(frm, cdt, cdn); },
	cz_tax_srb(frm, cdt, cdn) { cz_tax_total(frm, cdt, cdn); },
	cz_tax_yq(frm, cdt, cdn) { cz_tax_total(frm, cdt, cdn); },
	cz_tax_other(frm, cdt, cdn) { cz_tax_total(frm, cdt, cdn); },
});

function cz_tax_total(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	if (!row) return;
	const total = CZ_TICKET_TAX.reduce((s, f) => s + flt(row[f]), 0);
	frappe.model.set_value(cdt, cdn, "cz_taxes_total", flt(total, 2));
}

// ---- hotel rows
function cz_hotel_row(frm, cdt, cdn) {
	const r = locals[cdt][cdn];
	const ci = r.check_in || frm.doc.cz_check_in;
	const co = r.check_out || frm.doc.cz_check_out;
	r.nights = cz_nights(ci, co);
	r.amount = flt(r.rooms || 1) * r.nights * flt(r.sale_rate) + flt(r.other_fees);
	frm.refresh_field("cz_hotel_stays");
}
frappe.ui.form.on("Voucher Hotel Stay", {
	check_in: cz_hotel_row, check_out: cz_hotel_row, rooms: cz_hotel_row,
	sale_rate: cz_hotel_row, other_fees: cz_hotel_row,
});

// ---- service lines
function cz_line(frm, cdt, cdn) {
	const r = locals[cdt][cdn];
	r.amount = flt(r.qty) * flt(r.rate);
	frm.refresh_field("cz_service_lines");
}
frappe.ui.form.on("Voucher Service Line", { qty: cz_line, rate: cz_line });

// ---- airline tickets / taxes
frappe.ui.form.on("Voucher Air Ticket", {
	supplier_fare(frm) { cz_recalc_tickets(frm); },
	commission_percent(frm) { cz_recalc_tickets(frm); },
	wht_percent(frm) { cz_recalc_tickets(frm); },
});
frappe.ui.form.on("Voucher Air Tax", {
	amount(frm) { cz_recalc_tickets(frm); },
	ticket_row_no(frm) { cz_recalc_tickets(frm); },
});
