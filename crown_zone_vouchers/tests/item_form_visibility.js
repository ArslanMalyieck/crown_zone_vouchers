// Run with: node crown_zone_vouchers/tests/item_form_visibility.js
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const existing = ["custom_item_code", "final_price", "government_fee", "taxed_price", "vat",
	"supplier", "purchase_price", "purchase_tax_rate"];

function load(file) {
	const handlers = {};
	const changes = [];
	const grid = {
		update_docfield_property(name, prop, value) { changes.push([name, prop, value]); },
		reset_grid() {},
	};
	const locals = { "Sales Order Item": { row: {} } };
	const frappe = {
		ui: { form: { on(doctype, events) { handlers[doctype] = { ...handlers[doctype], ...events }; } } },
		user_roles: [], session: { user: "test@example.com" },
		model: { set_value() { throw new Error("non-voucher item was changed"); } },
	};
	const globals = { frappe, locals, flt: Number, cint: Number, __: (s) => s };
	globals.window = globals;
	vm.runInNewContext(fs.readFileSync(path.join(__dirname, "..", "public", "js", file), "utf8"), globals);
	return { handlers, changes, grid, locals };
}

function checkFields(changes) {
	for (const name of existing) {
		assert(changes.some(([field, prop, value]) => field === name && prop === "hidden" && value === 0),
			`${name} must be visible`);
		assert(!changes.some(([field, prop, value]) => field === name && prop === "hidden" && value === 1),
			`${name} was hidden`);
	}
	assert(!changes.some(([field, prop]) => field === "tax_rate" && prop === "read_only"),
		"ShaunGlobal tax rate permissions were changed");
}

const invoice = load("sales_invoice.js");
const si = {
	doc: { items: [], cz_service_type: "", docstatus: 0 },
	fields_dict: { items: { grid: invoice.grid } }, is_new: () => false,
};
invoice.handlers["Sales Invoice"].refresh(si);
checkFields(invoice.changes);
assert(!invoice.handlers["Sales Invoice Item"]?.final_price, "Selling Price handler must belong to ShaunGlobal");
invoice.changes.length = 0;
si.doc.cz_service_type = "Ticketing";
invoice.handlers["Sales Invoice"].cz_service_type(si);
checkFields(invoice.changes);
for (const name of ["cz_flight_no", "cz_class"]) {
	assert(invoice.changes.some(([field, prop, value]) => field === name && prop === "hidden" && value === 0));
}

const order = load("sales_order.js");
const so = {
	doc: { service_type: "", items: [], docstatus: 0 },
	fields_dict: { items: { grid: order.grid } }, is_new: () => true,
	set_query() {},
};
order.handlers["Sales Order"].refresh(so);
checkFields(order.changes);
order.handlers["Sales Order"].items_add(so, "Sales Order Item", "row");
assert.equal(order.locals["Sales Order Item"].row.cz_manual, undefined, "plain Sales Order must be untouched");
order.handlers["Sales Order Item"].final_price(so, "Sales Order Item", "row");
assert(order.changes.some(([field, prop, value]) => field === "cz_tax_rate" && prop === "hidden" && value === 1));

console.log("Sales Invoice / Sales Order existing item fields and calculations remain available");
