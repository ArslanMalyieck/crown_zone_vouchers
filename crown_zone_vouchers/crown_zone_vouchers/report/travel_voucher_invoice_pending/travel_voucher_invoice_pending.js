frappe.query_reports["Travel Voucher Invoice Pending"] = {
	filters: [
		{ fieldname: "from_date", label: __("Posted From"), fieldtype: "Date", default: frappe.datetime.add_days(frappe.datetime.get_today(), -30) },
		{ fieldname: "to_date", label: __("Posted To"), fieldtype: "Date", default: frappe.datetime.get_today() },
		{ fieldname: "service_type", label: __("Service"), fieldtype: "Link", options: "Travel Service Type" },
		{ fieldname: "customer", label: __("Customer"), fieldtype: "Link", options: "Customer" },
		{ fieldname: "supplier", label: __("Supplier"), fieldtype: "Link", options: "Supplier" },
	],
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "action" && data) {
			const voucher = frappe.utils.escape_html(data.voucher);
			let html = `<a href="/app/sales-order/${encodeURIComponent(data.voucher)}">${__("View Voucher")}</a>`;
			if (data.invoice_status === "Pending" && frappe.user_roles.some((r) =>
				["Travel Accounts", "Travel Manager", "System Manager"].includes(r))) {
				html += ` | <a onclick="cz_pending_make_invoice('${voucher}')" style="cursor:pointer">${__("Create Invoice")}</a>`;
			}
			return html;
		}
		return value;
	},
};

window.cz_pending_make_invoice = function (voucher) {
	frappe.model.open_mapped_doc({
		method: "erpnext.selling.doctype.sales_order.sales_order.make_sales_invoice",
		source_name: voucher,
	});
};
