from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestGreenValleyStockSmoke(TransactionCase):
    def test_module_loads(self):
        self.assertIn("stock.lot", self.env)
