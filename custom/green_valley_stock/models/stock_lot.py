from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class StockLot(models.Model):
    _inherit = "stock.lot"

    move_line_ids = fields.One2many(
        "stock.move.line",
        "lot_id",
        string="Move Lines",
        readonly=True,
        help="Stock move lines of this lot or serial number. Used to compute the delivery date.",
    )
    last_delivery_date = fields.Date(
        string="Last Delivery Date",
        compute="_compute_last_delivery_date",
        store=True,
        help="Date of the most recent delivery of this serial number to a customer. It is cleared when the serial was returned afterwards and not delivered again.",
    )
    warranty_end_date = fields.Date(
        string="Warranty End Date",
        compute="_compute_warranty_end_date",
        store=True,
        help="Date the manufacturer warranty ends, calculated as the last delivery date plus the product's warranty length in months.",
    )

    @api.depends(
        "move_line_ids.state",
        "move_line_ids.picking_id.date_done",
        "move_line_ids.location_id.usage",
        "move_line_ids.location_dest_id.usage",
    )
    def _compute_last_delivery_date(self):
        """Set the date of the latest done customer move if it was a delivery, otherwise clear it."""
        for lot in self:
            customer_lines = lot.move_line_ids.filtered(
                lambda line: (
                    line.state == "done"
                    and line.picking_id.date_done
                    and "customer"
                    in (line.location_id.usage, line.location_dest_id.usage)
                )
            )
            if not customer_lines:
                lot.last_delivery_date = False
                continue
            latest_line = max(
                customer_lines, key=lambda line: (line.picking_id.date_done, line.id)
            )
            if latest_line.location_dest_id.usage == "customer":
                lot.last_delivery_date = latest_line.picking_id.date_done.date()
            else:
                lot.last_delivery_date = False

    @api.depends("last_delivery_date", "product_id.product_tmpl_id.warranty_months")
    def _compute_warranty_end_date(self):
        """Add the product warranty length to the last delivery date when both are set."""
        for lot in self:
            months = lot.product_id.product_tmpl_id.warranty_months
            if lot.last_delivery_date and months > 0:
                lot.warranty_end_date = lot.last_delivery_date + relativedelta(
                    months=months
                )
            else:
                lot.warranty_end_date = False
