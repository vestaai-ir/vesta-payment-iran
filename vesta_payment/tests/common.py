# Copyright 2026 Vesta AI (https://vestaai.ir)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo.addons.payment.tests.common import PaymentCommon


class VestaPaymentCommon(PaymentCommon):
    """Base class of the bank modules' tests: a Rial transaction waiting for the bank."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.enable_process_patcher = False  # Run the real processing to test `_apply_updates`
        cls.currency = cls._enable_currency("IRR")
        cls.amount = 125000
        cls.partner.phone = "+98 912 345 6789"

    def _create_bank_transaction(self, provider, **values):
        tx = self._create_transaction(
            "redirect", provider_id=provider.id, payment_method_id=provider.payment_method_ids[:1].id, **values
        )
        return tx

    def _prepare_bank_transaction(self, tx, token="TOKEN-1"):
        """Put a transaction in the state it has after the bank issued a payment token."""
        return self._update_transaction(
            tx,
            vesta_order_id=tx._vesta_generate_order_id(),
            vesta_bank_token=token,
            vesta_verify_state="new",
        )

    def _return_from_bank(self, tx, data):
        """Hand the bank's callback to the transaction, then run Odoo's processing."""
        tx._vesta_handle_return(data)
        self._run_processing()
        tx.invalidate_recordset()
        return tx
