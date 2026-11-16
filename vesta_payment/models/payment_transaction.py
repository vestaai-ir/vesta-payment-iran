# Copyright 2026 Vesta AI (https://vestaai.ir)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import secrets
import time
from datetime import timedelta

import psycopg2

from odoo import fields, models
from odoo.addons.payment import utils as payment_utils
from odoo.addons.payment.logging import get_payment_logger
from odoo.addons.vesta_payment import const, utils
from odoo.exceptions import ValidationError
from odoo.fields import Domain
from odoo.tools import consteq, float_round
from odoo.tools.urls import urljoin

_logger = get_payment_logger(__name__, const.SENSITIVE_KEYS)


class PaymentTransaction(models.Model):
    _inherit = "payment.transaction"

    vesta_order_id = fields.Char(
        string="Bank Order ID",
        help="Numeric order id sent to the bank. It is unique across databases sharing a terminal.",
        readonly=True,
        copy=False,
        index="btree_not_null",
    )
    vesta_bank_token = fields.Char(
        string="Bank Token",
        help="Token, RefId or URL id issued by the bank for this payment.",
        readonly=True,
        copy=False,
        groups="base.group_system",
    )
    vesta_bank_reference = fields.Char(
        string="Digital Receipt",
        help="Unique receipt of the bank (RefNum, SaleReferenceId, RRN, ...). A receipt can confirm"
        " only one transaction, which blocks double spending.",
        readonly=True,
        copy=False,
    )
    vesta_rrn = fields.Char(string="RRN", help="Retrieval reference number.", readonly=True, copy=False)
    vesta_trace_no = fields.Char(string="Trace Number", readonly=True, copy=False)
    vesta_card_masked = fields.Char(string="Card Number", readonly=True, copy=False)
    vesta_card_hash = fields.Char(string="Card Hash", readonly=True, copy=False, groups="base.group_system")
    vesta_verify_state = fields.Selection(
        string="Bank Verification", selection=const.VERIFY_STATES, readonly=True, copy=False
    )
    vesta_retry_count = fields.Integer(string="Verification Retries", readonly=True, copy=False)
    vesta_callback_data = fields.Json(string="Bank Callback", readonly=True, copy=False, groups="base.group_system")

    _vesta_bank_reference_uniq = models.UniqueIndex(
        "(provider_id, vesta_bank_reference) WHERE vesta_bank_reference IS NOT NULL",
        "This bank receipt already confirmed another payment.",
    )

    # === AMOUNT HELPERS === #

    def _vesta_amount_to_rial(self):
        """Return the amount of the transaction in Rials, as sent to the bank.

        Fractions of a Rial are dropped, like the core amount check does.

        Note: `self.ensure_one()`

        :rtype: int
        """
        self.ensure_one()
        currency = self.currency_id.name
        if currency not in const.RIALS_PER_UNIT:
            raise ValidationError(self.env._("Iranian banks only accept Rial (IRR) or Toman (IRT), not %s.", currency))
        return int(float_round(abs(self.amount) * const.RIALS_PER_UNIT[currency], 0, rounding_method="DOWN"))

    def _vesta_amount_from_rial(self, amount_rial):
        """Return a Rial amount sent by the bank in the currency of the transaction."""
        self.ensure_one()
        return int(amount_rial) / const.RIALS_PER_UNIT.get(self.currency_id.name, 1)

    def _vesta_amount_matches(self, amount_rial):
        """Check that the amount confirmed by the bank is the amount of the transaction."""
        self.ensure_one()
        try:
            return int(str(amount_rial).replace(",", "")) == self._vesta_amount_to_rial()
        except (TypeError, ValueError):
            return False

    # === BUSINESS METHODS - PAYMENT FLOW === #

    def _vesta_generate_order_id(self):
        """Return a numeric order id unique across databases sharing the same bank terminal.

        Banks reject a reused order id. A transaction id alone would collide between a test and a
        production database, so the id is made of the current time in milliseconds, the last digits
        of the transaction id and two random digits (18 digits, below the int64 limit).
        """
        self.ensure_one()
        return f"{int(time.time() * 1000)}{self.id % 1000:03d}{secrets.randbelow(100):02d}"

    def _vesta_return_url(self):
        """Return the signed URL to which the bank sends the customer back."""
        self.ensure_one()
        access_token = payment_utils.generate_access_token(self.provider_code, self.vesta_order_id, env=self.env)
        path = f"/payment/vesta/{self.provider_code}/return/{self.vesta_order_id}/{access_token}"
        return urljoin(self.provider_id.get_base_url(), path)

    def _vesta_customer_mobile(self):
        """Return the customer's mobile number as 09XXXXXXXXX, if any."""
        self.ensure_one()
        return utils.normalize_mobile(self.partner_phone or self.partner_id.phone)

    def _get_specific_rendering_values(self, processing_values):
        """Override of `payment` to request a payment token from the bank.

        Note: `self.ensure_one()` from :meth:`_get_processing_values`
        """
        if self.provider_code not in const.BANK_CODES:
            return super()._get_specific_rendering_values(processing_values)

        self.vesta_order_id = self._vesta_generate_order_id()
        self.vesta_verify_state = "new"
        try:
            rendering_values = self._vesta_request_payment()
        except ValidationError as error:
            self.vesta_verify_state = "failed"
            self._set_error(str(error.args[0] if error.args else error))
            return {}
        _logger.info(
            "Bank %s issued a payment token for transaction %s (order %s).",
            self.provider_code,
            self.reference,
            self.vesta_order_id,
        )
        return rendering_values

    def _vesta_request_payment(self):
        """Ask the bank for a payment token and return the values of the redirect form.

        Bank modules override this method. They must store the token in `vesta_bank_token` and use
        `vesta_order_id` and `_vesta_return_url()` in the request.

        Note: `self.ensure_one()`

        :return: The rendering values of `payment.generic_redirect_form`: `api_url`, `url_params`
                 and optionally `http_method`.
        :rtype: dict
        :raise ValidationError: If the bank refuses to issue a token.
        """
        raise ValidationError(self.env._("This bank is not supported."))

    # === BUSINESS METHODS - RETURN FROM THE BANK === #

    def _vesta_find_from_return(self, provider_code, order_id, access_token):
        """Find the transaction of a return URL, after checking the URL's signature.

        :param str provider_code: The provider code in the URL.
        :param str order_id: The bank order id in the URL.
        :param str access_token: The HMAC of the provider code and the order id.
        :return: The transaction, or an empty recordset.
        :rtype: payment.transaction
        """
        if provider_code not in const.BANK_CODES or not order_id.isdigit():
            return self.browse()
        expected_token = payment_utils.generate_access_token(provider_code, order_id, env=self.env)
        if not consteq(access_token or "", expected_token):
            _logger.warning("Rejected a %s return with an invalid signature for order %s.", provider_code, order_id)
            return self.browse()
        tx = self.search(Domain("vesta_order_id", "=", order_id) & Domain("provider_code", "=", provider_code), limit=1)
        if not tx:
            _logger.warning("No %s transaction found for order %s.", provider_code, order_id)
        return tx

    def _vesta_handle_return(self, data):
        """Verify the payment with the bank and record the result.

        The transaction is locked so that two concurrent returns (double click, bank retry) can't
        verify the same payment twice. A return for a transaction that is no longer waiting for the
        bank is ignored.

        Note: `self.ensure_one()`

        :param dict data: The data posted by the bank.
        """
        self.ensure_one()
        tx = self.with_context(payment_safe_write=True)  # The transaction is locked below
        if not tx.try_lock_for_update():
            _logger.info("Transaction %s is already being processed; return ignored.", tx.reference)
            return
        if tx.state not in ("draft", "pending") or tx.vesta_verify_state not in ("new", "pending"):
            _logger.info("Transaction %s was already processed; return ignored.", tx.reference)
            return
        if self.env["payment.data"].search_count(Domain("transaction_id", "=", tx.id), limit=1):
            return

        callback = tx._vesta_parse_callback(data)
        if callback is None:
            return  # Inconsistent data, already logged by the bank module
        tx.vesta_callback_data = callback
        if not callback.get("success"):
            tx.vesta_verify_state = "failed"
            tx._record({"vesta_status": "cancel", "vesta_message": callback.get("message")})
            return
        try:
            tx._vesta_claim_receipt(callback.get("bank_reference"))
        except ValidationError as error:
            tx.vesta_verify_state = "failed"
            tx._record({"vesta_status": "error", "vesta_message": str(error.args[0])})
            return
        tx._vesta_verify_and_record(callback)

    def _vesta_parse_callback(self, data):
        """Read the data posted by the bank and check that it belongs to the transaction.

        Bank modules override this method. No request is sent to the bank here.

        Note: `self.ensure_one()`

        :param dict data: The data posted by the bank.
        :return: None if the data doesn't match the transaction, otherwise a dict with the keys
                 `success` (bool), `message`, and the bank's values needed to verify the payment
                 (`bank_reference`, `token`, `card_masked`, ...). It must be JSON-serializable.
        :rtype: dict|None
        """
        return None

    def _vesta_check_token(self, token):
        """Check, in constant time, that a token sent back by the bank is the one it issued."""
        self.ensure_one()
        return bool(token) and consteq(str(token), self.sudo().vesta_bank_token or "")

    def _vesta_claim_receipt(self, receipt):
        """Attach a bank receipt to the transaction, refusing a receipt already used elsewhere.

        Banks happily confirm the same receipt many times; keeping each receipt on a single
        transaction is the merchant's job (Saman calls it double spending). A unique index backs
        this check against concurrent requests.

        :param str receipt: The receipt (RefNum, SaleReferenceId, RRN, ...).
        :raise ValidationError: If another transaction of the provider holds the receipt.
        """
        self.ensure_one()
        if not receipt or self.vesta_bank_reference == receipt:
            return
        error = self.env._("This bank receipt was already used to confirm another payment.")
        duplicate = self.search_count(
            Domain("provider_id", "=", self.provider_id.id)
            & Domain("vesta_bank_reference", "=", receipt)
            & Domain("id", "!=", self.id),
            limit=1,
        )
        if duplicate:
            _logger.warning("Receipt %s reused on transaction %s.", receipt, self.reference)
            raise ValidationError(error)
        try:
            with self.env.cr.savepoint():
                self.vesta_bank_reference = receipt
                self.flush_recordset(["vesta_bank_reference"])
        except psycopg2.IntegrityError:
            raise ValidationError(error) from None

    def _vesta_verify_and_record(self, callback):
        """Confirm the payment with the bank and queue the result for processing.

        A network failure leaves the transaction pending; the reconciliation cron retries until the
        bank's confirmation window closes.

        :param dict callback: The values returned by :meth:`_vesta_parse_callback`.
        """
        self.ensure_one()
        try:
            payment_data = self._vesta_verify(callback)
        except ValidationError as error:
            self.vesta_retry_count += 1
            self.vesta_verify_state = "pending"
            message = self.env._(
                "The bank could not be reached to confirm the payment; Odoo will retry. (%s)",
                str(error.args[0] if error.args else error),
            )
            _logger.warning("Verification of %s failed, will retry: %s", self.reference, message)
            self._set_pending(state_message=message)
            return
        self._record(payment_data)

    def _vesta_verify(self, callback):
        """Confirm (verify, settle) the payment with the bank.

        Bank modules override this method. Business errors of the bank are returned as a result
        with `vesta_status` "error"; only transport errors raise, so that they are retried.

        Note: `self.ensure_one()`

        :param dict callback: The values returned by :meth:`_vesta_parse_callback`.
        :return: The payment data to record, see :meth:`_apply_updates`.
        :rtype: dict
        :raise ValidationError: If the bank can't be reached or returns garbage.
        """
        raise ValidationError(self.env._("This bank is not supported."))

    def _vesta_reverse(self):
        """Ask the bank to return the money of a confirmed payment to the customer.

        Bank modules that support it override this method.

        Note: `self.ensure_one()`

        :return: Whether the bank accepted the reversal.
        :rtype: bool
        """
        return False

    def _vesta_reject_amount(self, amount_rial, **values):
        """Reverse a payment whose confirmed amount differs from the transaction's amount."""
        self.ensure_one()
        _logger.error(
            "Amount mismatch on %s: bank confirmed %s Rials, expected %s.",
            self.reference,
            amount_rial,
            self._vesta_amount_to_rial(),
        )
        try:
            reversed_ = self._vesta_reverse()
        except ValidationError:
            reversed_ = False
        message = self.env._("The amount confirmed by the bank doesn't match the order.")
        if reversed_:
            message += " " + self.env._("The payment was reversed to the customer's card.")
        else:
            message += " " + self.env._("Reverse it from the bank's merchant panel.")
        return {
            **values,
            "vesta_status": "error",
            "vesta_message": message,
            "vesta_verify_state": "reversed" if reversed_ else "failed",
        }

    # === BUSINESS METHODS - PROCESSING === #

    def _apply_updates(self, payment_data):
        """Override of `payment` to update the transaction from the normalized bank result.

        Every bank module returns the same keys: `vesta_status` (done, pending, cancel or error),
        `vesta_message`, `vesta_amount` (Rials), `vesta_bank_reference`, `vesta_rrn`,
        `vesta_trace_no`, `vesta_card_masked`, `vesta_card_hash` and `vesta_verify_state`.
        """
        if self.provider_code not in const.BANK_CODES:
            return super()._apply_updates(payment_data)

        values = {}
        for key in ("vesta_rrn", "vesta_trace_no", "vesta_card_masked", "vesta_card_hash", "vesta_verify_state"):
            if payment_data.get(key):
                values[key] = str(payment_data[key])
        if receipt := payment_data.get("vesta_bank_reference"):
            values["provider_reference"] = str(receipt)
            if not self.vesta_bank_reference:
                values["vesta_bank_reference"] = str(receipt)
        if values:
            self.write(values)

        status = payment_data.get("vesta_status")
        message = payment_data.get("vesta_message")
        if status == "done":
            self._set_done(state_message=message)
        elif status == "pending":
            self._set_pending(state_message=message)
        elif status == "cancel":
            self._set_canceled(state_message=message or self.env._("The payment was canceled."))
        else:
            self._set_error(message or self.env._("The bank refused the payment."))

    def _extract_amount_data(self, payment_data):
        """Override of `payment` to compare the amount confirmed by the bank, in Rials."""
        if self.provider_code not in const.BANK_CODES:
            return super()._extract_amount_data(payment_data)
        if payment_data.get("vesta_amount") in (None, ""):
            return {}  # A successful payment without amount is refused by the amount check
        return {
            "amount": self._vesta_amount_from_rial(str(payment_data["vesta_amount"]).replace(",", "")),
            "currency_code": self.currency_id.name,
            "precision_digits": 1 if self.currency_id.name == "IRT" else 0,
        }

    def _send_refund_request(self):
        """Override of `payment` to reverse the payment with the bank."""
        if self.provider_code not in const.BANK_CODES:
            return super()._send_refund_request()

        source_tx = self.source_transaction_id.with_context(payment_safe_write=True)
        if not source_tx._vesta_reverse():
            raise ValidationError(self.env._("The bank refused to reverse this payment."))
        source_tx.vesta_verify_state = "reversed"
        self._record(
            {
                "vesta_status": "done",
                "vesta_amount": source_tx._vesta_amount_to_rial(),
                "vesta_bank_reference": f"REV-{source_tx.vesta_bank_reference or source_tx.reference}",
                "vesta_message": self.env._("Reversed by the bank to the customer's card."),
            }
        )

    # === CRON === #

    def _cron_vesta_reconcile(self):
        """Retry pending confirmations and close payments abandoned at the bank."""
        IrCron = self.env["ir.cron"]
        now = fields.Datetime.now()
        pending_txs = self.search(
            Domain("provider_code", "in", const.BANK_CODES)
            & Domain("vesta_verify_state", "=", "pending")
            & Domain("state", "in", ("draft", "pending"))
        )
        abandoned_txs = self.search(
            Domain("provider_code", "in", const.BANK_CODES)
            & Domain("vesta_verify_state", "=", "new")
            & Domain("state", "=", "draft")
            & Domain("create_date", "<", now - timedelta(minutes=const.ABANDONED_AFTER_MINUTES))
        )
        IrCron._commit_progress(remaining=len(pending_txs) + len(abandoned_txs))

        for tx in pending_txs:
            tx = tx.with_context(payment_safe_write=True)
            if not tx.try_lock_for_update() or tx.vesta_verify_state != "pending":
                IrCron._commit_progress(processed=1)
                continue
            window = timedelta(minutes=tx.provider_id._vesta_verify_window())
            if tx.create_date + window < now:
                tx.vesta_verify_state = "failed"
                tx._record(
                    {
                        "vesta_status": "error",
                        "vesta_message": self.env._(
                            "The bank could not confirm the payment in time. If money was taken, the"
                            " bank returns it to the card automatically."
                        ),
                    }
                )
            else:
                tx._vesta_verify_and_record(tx.vesta_callback_data or {})
            if not IrCron._commit_progress(processed=1):
                return

        for tx in abandoned_txs:
            tx = tx.with_context(payment_safe_write=True)
            if tx.try_lock_for_update() and tx.state == "draft" and tx.vesta_verify_state == "new":
                tx.vesta_verify_state = "failed"
                tx._set_canceled(state_message=self.env._("The customer did not complete the payment."))
            if not IrCron._commit_progress(processed=1):
                return
