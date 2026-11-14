frappe.query_reports["Posted Voucher Queue"] = {
	filters: [
		{ fieldname: "from_date", label: __("From"), fieldtype: "Date", default: frappe.datetime.add_days(frappe.datetime.get_today(), -30) },
		{ fieldname: "to_date", label: __("To"), fieldtype: "Date", default: frappe.datetime.get_today() },
		{ fieldname: "service_type", label: __("Service"), fieldtype: "Link", options: "Travel Service Type" },
		{ fieldname: "voucher_no", label: __("Voucher No."), fieldtype: "Data" },
		{ fieldname: "customer", label: __("Customer"), fieldtype: "Link", options: "Customer" },
		{ fieldname: "supplier", label: __("Supplier"), fieldtype: "Link", options: "Supplier" },
		{ fieldname: "posted_by", label: __("Posted By"), fieldtype: "Link", options: "User" },
		{ fieldname: "invoice_status", label: __("Invoice Status"), fieldtype: "Select",
		  options: "\nPending\nDraft\nIssued\nVoid\nOn Hold\nCancelled", default: "Pending" },
	],
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "action" && data) {
			const v = frappe.utils.escape_html(data.voucher);
			let html = `<a href="/app/sales-order/${encodeURIComponent(data.voucher)}">${__("View Voucher")}</a>`;
			if (["Pending", "Void"].includes(data.invoice_status)) {
				html += ` | <a onclick="cz_make_invoice('${v}')" style="cursor:pointer">${__("Create Invoice")}</a>`;
			}
			return html;
		}
		return value;
	},
};

window.cz_make_invoice = function (voucher) {
	frappe.model.open_mapped_doc({
		method: "erpnext.selling.doctype.sales_order.sales_order.make_sales_invoice",
		source_name: voucher,
	});
};
