from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    warranty_months = fields.Integer(
        string="Warranty (months)",
        help="Length of the manufacturer warranty in months, counted from the delivery date of each serial number. Leave 0 when the product has no warranty.",
    )

    _warranty_months_positive = models.Constraint(
        "CHECK(warranty_months >= 0)",
        "The warranty length cannot be negative.",
    )
