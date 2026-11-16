# Copyright 2026 Vesta AI (https://vestaai.ir)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from unittest.mock import patch

from odoo.addons.vesta_payment.tests.common import VestaPaymentCommon
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

CALL = "odoo.addons.vesta_payment_mellat.models.payment_provider.PaymentProvider._mellat_call"


def bank(answers):
    """Return a fake `_mellat_call` answering each operation from a dict, and recording calls."""
    calls = []

    def call(provider, operation, values, reference=None):
        calls.append(operation)
        answer = answers[operation]
        if isinstance(answer, Exception):
            raise answer
        return answer

    call.calls = calls
    return call


@tagged("post_install", "-at_install")
class TestMellat(VestaPaymentCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mellat = cls._prepare_provider(
            "mellat",
            update_values={"mellat_terminal_id": "1234567", "mellat_username": "user", "mellat_password": "secret"},
        )
        cls.provider = cls.mellat

    def _paid_callback(self, tx, **values):
        return {
            "RefId": tx.vesta_bank_token,
            "ResCode": "0",
            "SaleOrderId": tx.vesta_order_id,
            "SaleReferenceId": "100677",
            "CardHolderPan": "502229******2928",
            "CardHolderInfo": "F6EF76",
            "FinalAmount": str(self.amount),
            **values,
        }

    def test_redirect_form(self):
        tx = self._create_bank_transaction(self.mellat)
        with patch(CALL, new=bank({"bpPayRequest": "0,AF82041A2BF6989"})):
            processing_values = tx._get_processing_values()
        form = self._extract_values_from_html_form(processing_values["redirect_form_html"])
        self.assertEqual(
            form["action"], "https://sandbox.banktest.ir/mellat/bpm.shaparak.ir/pgwchannel/startpay.mellat"
        )
        self.assertEqual(form["inputs"]["RefId"], "AF82041A2BF6989")
        self.assertEqual(form["inputs"]["mobileNo"], "989123456789")
        self.assertEqual(tx.vesta_bank_token, "AF82041A2BF6989")
        self.assertTrue(tx.vesta_order_id.isdigit() and len(tx.vesta_order_id) == 18)

    def test_redirect_form_live_url(self):
        self.mellat.is_live = True
        tx = self._create_bank_transaction(self.mellat)
        with patch(CALL, new=bank({"bpPayRequest": "0,AF82041A2BF6989"})):
            processing_values = tx._get_processing_values()
        form = self._extract_values_from_html_form(processing_values["redirect_form_html"])
        self.assertEqual(form["action"], "https://bpm.shaparak.ir/pgwchannel/startpay.mellat")

    @mute_logger("odoo.addons.vesta_payment.models.payment_transaction")
    def test_refused_payment_request(self):
        tx = self._create_bank_transaction(self.mellat)
        with patch(CALL, new=bank({"bpPayRequest": "421"})):
            tx._get_processing_values()
        self.assertEqual(tx.state, "error")
        self.assertIn("(421)", tx.state_message)

    def test_paid_and_settled(self):
        tx = self._prepare_bank_transaction(self._create_bank_transaction(self.mellat))
        fake = bank({"bpVerifyRequest": "0", "bpSettleRequest": "0"})
        with patch(CALL, new=fake):
            self._return_from_bank(tx, self._paid_callback(tx))
        self.assertEqual(fake.calls, ["bpVerifyRequest", "bpSettleRequest"])
        self.assertEqual(tx.state, "done")
        self.assertEqual(tx.vesta_verify_state, "settled")
        self.assertEqual(tx.provider_reference, "100677")
        self.assertEqual(tx.vesta_card_masked, "502229******2928")

    def test_replayed_return_is_ignored(self):
        tx = self._prepare_bank_transaction(self._create_bank_transaction(self.mellat))
        fake = bank({"bpVerifyRequest": "0", "bpSettleRequest": "0"})
        with patch(CALL, new=fake):
            self._return_from_bank(tx, self._paid_callback(tx))
            self._return_from_bank(tx, self._paid_callback(tx))
        self.assertEqual(fake.calls, ["bpVerifyRequest", "bpSettleRequest"], "The payment is verified only once")

    @mute_logger("odoo.addons.vesta_payment_mellat.models.payment_transaction")
    def test_foreign_refid_is_ignored(self):
        tx = self._prepare_bank_transaction(self._create_bank_transaction(self.mellat))
        fake = bank({})
        with patch(CALL, new=fake):
            self._return_from_bank(tx, self._paid_callback(tx, RefId="ANOTHER"))
            self._return_from_bank(tx, self._paid_callback(tx, SaleOrderId="1"))
        self.assertEqual(fake.calls, [])
        self.assertEqual(tx.state, "draft")

    def test_canceled_by_customer(self):
        tx = self._prepare_bank_transaction(self._create_bank_transaction(self.mellat))
        with patch(CALL, new=bank({})):
            self._return_from_bank(tx, self._paid_callback(tx, ResCode="17", SaleReferenceId=""))
        self.assertEqual(tx.state, "cancel")
        self.assertIn("(17)", tx.state_message)

    def test_settle_failure_reverses(self):
        tx = self._prepare_bank_transaction(self._create_bank_transaction(self.mellat))
        fake = bank({"bpVerifyRequest": "0", "bpSettleRequest": "34", "bpReversalRequest": "0"})
        with patch(CALL, new=fake):
            self._return_from_bank(tx, self._paid_callback(tx))
        self.assertEqual(fake.calls, ["bpVerifyRequest", "bpSettleRequest", "bpReversalRequest"])
        self.assertEqual(tx.state, "error")
        self.assertEqual(tx.vesta_verify_state, "reversed")

    @mute_logger("odoo.addons.vesta_payment.models.payment_transaction")
    def test_network_error_is_retried(self):
        tx = self._prepare_bank_transaction(self._create_bank_transaction(self.mellat))
        with patch(CALL, new=bank({"bpVerifyRequest": ValidationError("timeout")})):
            self._return_from_bank(tx, self._paid_callback(tx))
        self.assertEqual(tx.state, "pending")
        self.assertEqual(tx.vesta_verify_state, "pending")
        self.assertEqual(tx.vesta_retry_count, 1)

        # The bank answers again: the cron verifies (already verified) and settles the payment.
        with patch(CALL, new=bank({"bpVerifyRequest": "43", "bpSettleRequest": "0"})):
            self._run_cron_job("vesta_payment.cron_vesta_reconcile")
            self._run_processing()
        tx.invalidate_recordset()
        self.assertEqual(tx.state, "done")
        self.assertEqual(tx.vesta_verify_state, "settled")

    @mute_logger("odoo.addons.vesta_payment.models.payment_transaction")
    def test_receipt_cannot_confirm_two_payments(self):
        tx1 = self._prepare_bank_transaction(self._create_bank_transaction(self.mellat, reference="TX-1"))
        tx2 = self._prepare_bank_transaction(
            self._create_bank_transaction(self.mellat, reference="TX-2"), token="TOKEN-2"
        )
        with patch(CALL, new=bank({"bpVerifyRequest": "0", "bpSettleRequest": "0"})):
            self._return_from_bank(tx1, self._paid_callback(tx1))
            self._return_from_bank(tx2, self._paid_callback(tx2))
        self.assertEqual(tx1.state, "done")
        self.assertEqual(tx2.state, "error")

    @mute_logger("odoo.addons.vesta_payment.models.payment_transaction")
    def test_return_url_signature(self):
        tx = self._prepare_bank_transaction(self._create_bank_transaction(self.mellat))
        Transaction = self.env["payment.transaction"].sudo()
        token = tx._vesta_return_url().rsplit("/", 1)[1]
        self.assertEqual(Transaction._vesta_find_from_return("mellat", tx.vesta_order_id, token), tx)
        self.assertFalse(Transaction._vesta_find_from_return("mellat", tx.vesta_order_id, "0" * 64))
        self.assertFalse(Transaction._vesta_find_from_return("saman", tx.vesta_order_id, token))

    def test_toman_amount(self):
        toman = self.env["res.currency"].create({"name": "IRT", "symbol": "T", "rounding": 1})
        tx = self._create_bank_transaction(self.mellat, amount=12500, currency_id=toman.id)
        self.assertEqual(tx._vesta_amount_to_rial(), 125000)
        self.assertEqual(tx._vesta_amount_from_rial(125000), 12500)

    def test_test_connection(self):
        with patch(CALL, new=bank({"bpPayRequest": "0,ABC"})):
            action = self.mellat.action_vesta_test_connection()
        self.assertEqual(action["params"]["type"], "success")
        self.assertTrue(self.mellat.vesta_check_ok)
        with patch(CALL, new=bank({"bpPayRequest": "24"})):
            action = self.mellat.action_vesta_test_connection()
        self.assertEqual(action["params"]["type"], "danger")
        self.assertIn("(24)", self.mellat.vesta_check_message)

    def test_go_live_requires_credentials(self):
        self.mellat.mellat_password = False
        with self.assertRaises(ValidationError):
            self.mellat.action_vesta_set_live()
