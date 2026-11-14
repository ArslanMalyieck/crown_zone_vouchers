// Crown Zone Vouchers - Sales Order (= travel voucher) client script
const CZ_ITEM_COLS = {
	Airline: ["cz_passenger", "cz_ticket_no", "cz_airline", "cz_sector", "cz_travel_date"],
	Hotel: ["cz_hotel_city", "cz_room_type", "cz_lead_guest", "cz_rooms", "cz_nights", "cz_unit_rate", "cz_other_fees"],
};
const CZ_ITEM_ALL = ["cz_passenger", "cz_ticket_no", "cz_airline", "cz_sector", "cz_travel_date",
	"cz_hotel_city", "cz_room_type", "cz_lead_guest", "cz_rooms", "cz_nights", "cz_unit_rate", "cz_other_fees"];

window.cz_item_columns = function (frm, service) {
	const grid = frm.fields_dict.items && frm.fields_dict.items.grid;
	if (!grid) return;
	const show = CZ_ITEM_COLS[service] || [];
	CZ_ITEM_ALL.forEach((fn) => {
		const on = show.includes(fn);
		grid.update_docfield_property(fn, "hidden", on ? 0 : 1);
		grid.update_docfield_property(fn, "in_list_view", on ? 1 : 0);
	});
	grid.reset_grid();
};

function cz_roles_ok() {
	const r = frappe.user_roles;
	return r.includes("Travel Accounts") || r.includes("Travel Manager") || r.includes("System Manager");
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
		t.commission_amount = (flt(t.supplier_fare) * flt(t.commission_percent)) / 100;
		t.wht_amount = (t.commission_amount * flt(t.wht_percent)) / 100;
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
		cz_item_columns(frm, frm.doc.service_type);
		if (frm.doc.docstatus === 1 && cz_roles_ok() && frm.doc.service_type) {
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
		cz_item_columns(frm, frm.doc.service_type);
		if (!frm.doc.service_type) return;
		frappe.db.get_value("Travel Service Type", frm.doc.service_type, "voucher_prefix").then((r) => {
			const p = r.message && r.message.voucher_prefix;
			if (p) frm.set_value("naming_series", p + "-.YYYY.-.#####");
		});
	},
	cz_check_in(frm) { frm.set_value("cz_total_nights", cz_nights(frm.doc.cz_check_in, frm.doc.cz_check_out)); },
	cz_check_out(frm) { frm.set_value("cz_total_nights", cz_nights(frm.doc.cz_check_in, frm.doc.cz_check_out)); },
	cz_purchase_amount(frm) { cz_recalc_purchase(frm); },
	cz_exchange_rate(frm) { cz_recalc_purchase(frm); },
	cz_purchase_currency(frm) { cz_recalc_purchase(frm); },
	cz_air_taxes_remove(frm) { cz_recalc_tickets(frm); },
	cz_air_tickets_remove(frm) { cz_recalc_tickets(frm); },
});

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


// ---- voucher item table: auto-built from service lines
function cz_apply_item_table_mode(frm) {
	if (!frm.fields_dict || !frm.fields_dict.items) return;
	const is_voucher = !!frm.doc.service_type;
	frm.set_df_property("items", "read_only", 0);
	frm.set_df_property("items", "reqd", is_voucher ? 0 : 1);
}

frappe.ui.form.on("Sales Order", {
	refresh(frm) {
		cz_apply_item_table_mode(frm);
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
	},
	service_type(frm) { cz_apply_item_table_mode(frm); },
});
