# Copyright 2026 Vesta AI (https://vestaai.ir)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestVestaPaymentBank(TransactionCase):
    def test_catalog_lists_the_five_banks(self):
        banks = self.env["vesta.payment.bank"].search([])
        self.assertEqual(set(banks.mapped("code")), {"mellat", "saman", "parsian", "sadad", "pasargad"})

    def test_missing_module_state(self):
        bank = self.env["vesta.payment.bank"].create(
            {
                "name": "Unknown Bank",
                "code": "unknown",
                "module_name": "vesta_payment_unknown",
            }
        )
        self.assertEqual(bank.module_state, "missing")
        self.assertEqual(bank.state, "missing")
        with self.assertRaises(UserError):
            bank.action_install()
        with self.assertRaises(UserError):
            bank.action_set_live()

    def test_statistics_do_not_fail_without_provider(self):
        bank = self.env.ref("vesta_payment.bank_saman")
        if bank.provider_id:
            self.skipTest("Bank Saman is installed")
        self.assertEqual(bank.transaction_count, 0)
        self.assertEqual(bank.pending_count, 0)
