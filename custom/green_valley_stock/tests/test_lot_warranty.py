from datetime import date, datetime, time

from dateutil.relativedelta import relativedelta
from psycopg2 import IntegrityError

from odoo import Command, fields
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestLotWarranty(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.warehouse = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.env.company.id)], limit=1
        )
        cls.stock_location = cls.warehouse.lot_stock_id
        cls.customer_location = cls.env.ref("stock.stock_location_customers")
        cls.template = cls._create_template("Warranty Bike", 24)
        cls.product = cls.template.product_variant_id

    @classmethod
    def _create_template(cls, name, warranty_months):
        return cls.env["product.template"].create(
            {
                "name": name,
                "type": "consu",
                "is_storable": True,
                "tracking": "serial",
                "warranty_months": warranty_months,
            }
        )

    def _create_lot(self, product, name):
        lot = self.env["stock.lot"].create(
            {
                "name": name,
                "product_id": product.id,
                "company_id": self.env.company.id,
            }
        )
        self.env["stock.quant"]._update_available_quantity(
            product, self.stock_location, 1.0, lot_id=lot
        )
        return lot

    def _transfer(self, lot, picking_type, source, destination, date_done):
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": picking_type.id,
                "location_id": source.id,
                "location_dest_id": destination.id,
                "move_ids": [
                    Command.create(
                        {
                            "product_id": lot.product_id.id,
                            "product_uom_qty": 1.0,
                            "product_uom": lot.product_id.uom_id.id,
                            "location_id": source.id,
                            "location_dest_id": destination.id,
                        }
                    )
                ],
            }
        )
        picking.action_confirm()
        picking.action_assign()
        # Set the lot explicitly: returns from the customer location reserve no quant.
        picking.move_line_ids.write({"lot_id": lot.id, "quantity": 1.0})
        picking.move_ids.picked = True
        picking.button_validate()
        picking.date_done = date_done
        return picking

    def _deliver(self, lot, date_done):
        return self._transfer(
            lot,
            self.warehouse.out_type_id,
            self.stock_location,
            self.customer_location,
            date_done,
        )

    def _return(self, lot, date_done):
        return self._transfer(
            lot,
            self.warehouse.in_type_id,
            self.customer_location,
            self.stock_location,
            date_done,
        )

    def test_warranty_months_field(self):
        """AC-1: The product stores a warranty length and rejects negative values."""
        self.assertEqual(self.template.warranty_months, 24)
        with (
            mute_logger("odoo.sql_db"),
            self.assertRaises(IntegrityError),
            self.cr.savepoint(),
        ):
            self._create_template("Negative Warranty Bike", -1)

    def test_warranty_end_date_after_delivery(self):
        """AC-2: The warranty ends the product warranty length after the delivery date."""
        lot = self._create_lot(self.product, "GVB-SN-001")
        self._deliver(lot, datetime(2024, 3, 15, 10, 0))
        self.assertEqual(lot.last_delivery_date, date(2024, 3, 15))
        self.assertEqual(lot.warranty_end_date, date(2026, 3, 15))

    def test_no_warranty_end_date(self):
        """AC-2: No end date without a delivery or without a warranty length, and it follows later changes."""
        undelivered_lot = self._create_lot(self.product, "GVB-SN-002")
        self.assertFalse(undelivered_lot.last_delivery_date)
        self.assertFalse(undelivered_lot.warranty_end_date)

        no_warranty_template = self._create_template("No Warranty Bike", 0)
        no_warranty_lot = self._create_lot(
            no_warranty_template.product_variant_id, "GVB-SN-003"
        )
        self._deliver(no_warranty_lot, datetime(2024, 3, 15, 10, 0))
        self.assertEqual(no_warranty_lot.last_delivery_date, date(2024, 3, 15))
        self.assertFalse(no_warranty_lot.warranty_end_date)

        no_warranty_template.warranty_months = 12
        self.assertEqual(no_warranty_lot.warranty_end_date, date(2025, 3, 15))

    def test_return_clears_and_redelivery_sets_dates(self):
        """AC-2: A return from the customer clears the dates and a new delivery sets them again."""
        lot = self._create_lot(self.product, "GVB-SN-004")
        self._deliver(lot, datetime(2024, 1, 10, 9, 0))
        self.assertEqual(lot.warranty_end_date, date(2026, 1, 10))

        self._return(lot, datetime(2024, 2, 10, 9, 0))
        self.assertFalse(lot.last_delivery_date)
        self.assertFalse(lot.warranty_end_date)

        self._deliver(lot, datetime(2024, 6, 20, 9, 0))
        self.assertEqual(lot.last_delivery_date, date(2024, 6, 20))
        self.assertEqual(lot.warranty_end_date, date(2026, 6, 20))

    def test_expiring_in_30_days_filter(self):
        """AC-3: The filter returns only serials whose warranty ends within the next 30 days."""
        today = fields.Date.context_today(self.env["stock.lot"])
        template = self._create_template("Twelve Month Bike", 12)
        product = template.product_variant_id
        lots_by_offset = {}
        for offset in (10, -1, 40):
            lot = self._create_lot(product, "GVB-SN-EXP-%s" % offset)
            target_end_date = today + relativedelta(days=offset)
            delivery_day = target_end_date - relativedelta(months=12)
            self._deliver(lot, datetime.combine(delivery_day, time(12, 0)))
            # Month arithmetic may shift the end date by a day around Feb 29.
            self.assertLessEqual(abs((lot.warranty_end_date - target_end_date).days), 1)
            lots_by_offset[offset] = lot
        no_warranty_template = self._create_template("Unwarranted Bike", 0)
        no_warranty_lot = self._create_lot(
            no_warranty_template.product_variant_id, "GVB-SN-EXP-NONE"
        )
        self._deliver(no_warranty_lot, datetime.combine(today, time(12, 0)))

        all_lots = self.env["stock.lot"].browse(
            [*(lot.id for lot in lots_by_offset.values()), no_warranty_lot.id]
        )
        domain = [
            ("id", "in", all_lots.ids),
            ("warranty_end_date", ">=", today),
            ("warranty_end_date", "<=", today + relativedelta(days=30)),
        ]
        self.assertEqual(self.env["stock.lot"].search(domain), lots_by_offset[10])

        views = self.env["stock.lot"].get_views([(False, "search")])
        self.assertIn("warranty_expiring_30_days", views["views"]["search"]["arch"])
