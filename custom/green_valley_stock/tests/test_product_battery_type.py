from lxml import etree

from odoo.tests.common import TransactionCase, tagged

PARAM_KEY = "green_valley_stock.ebike_category_xmlid"


@tagged("post_install", "-at_install")
class TestProductBatteryType(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Category = cls.env["product.category"]
        cls.ebike_category = Category.create({"name": "E-Bikes"})
        cls.env["ir.model.data"].create(
            {
                "module": "__export__",
                "name": "test_ebike_category",
                "model": "product.category",
                "res_id": cls.ebike_category.id,
            }
        )
        cls.env["ir.config_parameter"].set_param(
            PARAM_KEY, "__export__.test_ebike_category"
        )
        cls.other_category = Category.create({"name": "Accessories"})
        cls.child_category = Category.create(
            {"name": "E-Bikes Child", "parent_id": cls.ebike_category.id}
        )
        cls.Template = cls.env["product.template"]

    def _arch_node(self, view_type):
        arch = self.Template.get_view(view_type=view_type)["arch"]
        nodes = etree.fromstring(arch).xpath("//field[@name='battery_type']")
        return nodes[0] if nodes else None

    def test_battery_type_selection(self):
        """AC-1: battery_type is a 'Battery Type' selection with 36V and 48V."""
        field = self.Template._fields["battery_type"]
        self.assertEqual(field.type, "selection")
        self.assertEqual(field.string, "Battery Type")
        self.assertEqual(field.selection, [("36v", "36V"), ("48v", "48V")])

    def test_form_view_contains_battery_type(self):
        """AC-1: the product form view contains the battery_type field."""
        self.assertIsNotNone(self._arch_node("form"))

    def test_flag_true_for_ebike_category(self):
        """AC-2: a product in the E-Bikes category has is_ebike_category True."""
        product = self.Template.create(
            {"name": "Trail E-Bike", "categ_id": self.ebike_category.id}
        )
        self.assertTrue(product.is_ebike_category)

    def test_flag_false_for_other_and_child_category(self):
        """AC-2: products in another or a child category have is_ebike_category False."""
        other = self.Template.create(
            {"name": "Helmet", "categ_id": self.other_category.id}
        )
        child = self.Template.create(
            {"name": "Cargo E-Bike", "categ_id": self.child_category.id}
        )
        self.assertFalse(other.is_ebike_category)
        self.assertFalse(child.is_ebike_category)

    def test_flag_false_without_valid_parameter(self):
        """AC-2: a missing or unresolvable parameter gives False without error."""
        product = self.Template.create(
            {"name": "Trail E-Bike", "categ_id": self.ebike_category.id}
        )
        ConfigParameter = self.env["ir.config_parameter"]
        ConfigParameter.set_param(PARAM_KEY, "__export__.does_not_exist")
        self.assertFalse(product.is_ebike_category)
        ConfigParameter.set_param(PARAM_KEY, "no_dot_xmlid")
        self.assertFalse(product.is_ebike_category)
        ConfigParameter.set_param(PARAM_KEY, False)
        self.assertFalse(product.is_ebike_category)
        self.assertFalse(self.Template._get_ebike_category())

    def test_value_kept_when_category_changes(self):
        """AC-2: moving a product out of E-Bikes keeps battery_type and hides the field."""
        product = self.Template.create(
            {
                "name": "Trail E-Bike",
                "categ_id": self.ebike_category.id,
                "battery_type": "48v",
            }
        )
        product.categ_id = self.other_category
        self.assertEqual(product.battery_type, "48v")
        self.assertFalse(product.is_ebike_category)

    def test_form_battery_type_invisible_expression(self):
        """AC-2: the battery_type form node is invisible unless the category is E-Bikes."""
        node = self._arch_node("form")
        self.assertIsNotNone(node)
        self.assertEqual(node.get("invisible"), "not is_ebike_category")

    def test_list_view_contains_battery_type(self):
        """AC-3: the product list view has a battery_type column."""
        self.assertIsNotNone(self._arch_node("list"))
