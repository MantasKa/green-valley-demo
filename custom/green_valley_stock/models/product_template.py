from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    battery_type = fields.Selection(
        selection=[("36v", "36V"), ("48v", "48V")],
        string="Battery Type",
        help="Nominal voltage of the e-bike battery. Only relevant for products in the E-Bikes category.",
    )
    is_ebike_category = fields.Boolean(
        string="Is E-Bike Category",
        compute="_compute_is_ebike_category",
        help="Technical flag: true when the product category is the configured E-Bikes category. Controls whether Battery Type is shown.",
    )

    @api.depends("categ_id")
    def _compute_is_ebike_category(self):
        """Flag products whose own category is exactly the configured E-Bikes category."""
        ebike_category = self._get_ebike_category()
        for template in self:
            template.is_ebike_category = (
                bool(ebike_category) and template.categ_id == ebike_category
            )

    @api.model
    def _get_ebike_category(self):
        """Return the E-Bikes category configured through its XML ID system parameter, or an empty recordset."""
        # sudo: regular users cannot read system parameters, but the flag must work for them
        xmlid = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("green_valley_stock.ebike_category_xmlid")
        )
        empty_category = self.env["product.category"]
        if not xmlid or "." not in xmlid:
            return empty_category
        category = self.env.ref(xmlid, raise_if_not_found=False)
        if category and category._name == "product.category":
            return category
        return empty_category
