# Copyright 2026 Vesta AI (https://vestaai.ir)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import models
from odoo.addons.payment.logging import get_payment_logger
from odoo.addons.vesta_payment import const as vesta_const
from odoo.addons.vesta_payment import utils
from odoo.addons.vesta_payment_mellat import const
from odoo.exceptions import ValidationError

_logger = get_payment_logger(__name__, vesta_const.SENSITIVE_KEYS)


class PaymentTransaction(models.Model):
    _inherit = "payment.transaction"

    # === BUSINESS METHODS - PAYMENT FLOW === #

    def _vesta_request_payment(self):
        """Override of `vesta_payment` to get a RefId from bpPayRequest."""
        if self.provider_code != "mellat":
            return super()._vesta_request_payment()

        now = utils.bank_now()
        result = self.provider_id._mellat_call(
            "bpPayRequest",
            {
                "orderId": int(self.vesta_order_id),
                "amount": self._vesta_amount_to_rial(),
                "localDate": now.strftime("%Y%m%d"),
                "localTime": now.strftime("%H%M%S"),
                "additionalData": self.reference,
                "callBackUrl": self._vesta_return_url(),
                "payerId": 0,
            },
            reference=self.reference,
        )
        code, _sep, ref_id = result.partition(",")
        if code.strip() != "0" or not ref_id.strip():
            raise ValidationError(
                self.env._(
                    "Bank Mellat refused the payment: %s",
                    utils.bank_message(self.env, const.RESULT_CODES, code.strip()),
                )
            )
        self.vesta_bank_token = ref_id.strip()

        url_params = {"RefId": self.vesta_bank_token}
        if mobile := self._vesta_customer_mobile():
            url_params["mobileNo"] = "98" + mobile[1:]  # Shows the customer's saved cards
        return {"api_url": self.provider_id._vesta_url(const.PAYMENT_URL), "url_params": url_params}

    # === BUSINESS METHODS - RETURN FROM THE BANK === #

    def _vesta_parse_callback(self, data):
        """Override of `vesta_payment` to read Mellat's callback.

        Mellat posts RefId, ResCode, SaleOrderId, SaleReferenceId, CardHolderPan, CardHolderInfo
        and FinalAmount.
        """
        if self.provider_code != "mellat":
            return super()._vesta_parse_callback(data)

        if not self._vesta_check_token(data.get("RefId")):
            _logger.warning("Mellat callback for %s carries a foreign RefId; ignored.", self.reference)
            return None
        sale_order_id = str(data.get("SaleOrderId") or "").strip()
        if sale_order_id and sale_order_id != self.vesta_order_id:
            _logger.warning("Mellat callback for %s carries order %s; ignored.", self.reference, sale_order_id)
            return None

        res_code = str(data.get("ResCode", "")).strip()
        sale_reference_id = str(data.get("SaleReferenceId") or "").strip()
        success = res_code == "0" and sale_reference_id.isdigit() and int(sale_reference_id) > 0
        return {
            "success": success,
            "code": res_code,
            "message": utils.bank_message(self.env, const.RESULT_CODES, res_code or "?"),
            "bank_reference": sale_reference_id if success else None,
            "card_masked": utils.mask_card(data.get("CardHolderPan")),
            "card_hash": data.get("CardHolderInfo"),
            "final_amount": data.get("FinalAmount"),
        }

    def _vesta_verify(self, callback):
        """Override of `vesta_payment` to verify then settle the payment.

        Mellat binds the amount to the RefId when the payment is requested, and bpVerifyRequest
        checks the order id against the sale reference, so the amount confirmed is the amount
        requested. A payment verified but not settled is reversed, so that the customer is never
        charged for an order that isn't confirmed.
        """
        if self.provider_code != "mellat":
            return super()._vesta_verify(callback)

        sale_reference_id = callback["bank_reference"]
        ids = {
            "orderId": int(self.vesta_order_id),
            "saleOrderId": int(self.vesta_order_id),
            "saleReferenceId": int(sale_reference_id),
        }
        result = {
            "vesta_bank_reference": sale_reference_id,
            "vesta_rrn": sale_reference_id,
            "vesta_card_masked": callback.get("card_masked"),
            "vesta_card_hash": callback.get("card_hash"),
        }

        verify_code = self.provider_id._mellat_call("bpVerifyRequest", ids, reference=self.reference).strip()
        if verify_code not in ("0", const.ALREADY_VERIFIED):
            reversed_ = self._mellat_reverse(ids)
            return {
                **result,
                "vesta_status": "error",
                "vesta_message": self.env._(
                    "Bank Mellat did not verify the payment: %s",
                    utils.bank_message(self.env, const.RESULT_CODES, verify_code),
                ),
                "vesta_verify_state": "reversed" if reversed_ else "failed",
            }

        settle_code = self.provider_id._mellat_call("bpSettleRequest", ids, reference=self.reference).strip()
        if settle_code not in ("0", const.ALREADY_SETTLED):
            reversed_ = self._mellat_reverse(ids)
            message = self.env._(
                "Bank Mellat did not settle the payment: %s",
                utils.bank_message(self.env, const.RESULT_CODES, settle_code),
            )
            if reversed_:
                message += " " + self.env._("The payment was reversed to the customer's card.")
            return {
                **result,
                "vesta_status": "error",
                "vesta_message": message,
                "vesta_verify_state": "reversed" if reversed_ else "verified",
            }

        return {
            **result,
            "vesta_status": "done",
            "vesta_amount": self._vesta_amount_to_rial(),
            "vesta_verify_state": "settled",
        }

    def _mellat_reverse(self, ids):
        """Ask Mellat to return an unsettled payment to the card; never raise."""
        try:
            code = self.provider_id._mellat_call("bpReversalRequest", ids, reference=self.reference).strip()
        except ValidationError:
            return False
        return code in ("0", "48")
