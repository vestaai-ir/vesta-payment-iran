# Copyright 2026 Vesta AI (https://vestaai.ir)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import secrets
import time

from odoo import fields, models
from odoo.addons.vesta_payment import utils
from odoo.addons.vesta_payment_mellat import const
from odoo.exceptions import ValidationError
from odoo.tools.urls import urljoin


class PaymentProvider(models.Model):
    _inherit = "payment.provider"

    code = fields.Selection(selection_add=[("mellat", "Bank Mellat")], ondelete={"mellat": "set default"})
    mellat_terminal_id = fields.Char(
        string="Mellat Terminal ID",
        help="Terminal number given by Behpardakht Mellat.",
        required_if_provider="mellat",
        copy=False,
    )
    mellat_username = fields.Char(string="Mellat Username", required_if_provider="mellat", copy=False)
    mellat_password = fields.Char(
        string="Mellat Password", required_if_provider="mellat", copy=False, groups="base.group_system"
    )
    mellat_api = fields.Selection(
        string="Web Service",
        selection=[("rest", "REST (recommended)"), ("soap", "SOAP")],
        default="rest",
        required=True,
        help="REST is Mellat's newest API. SOAP is the classic web service; both give the same result.",
    )

    # === CRUD METHODS === #

    def _get_default_payment_method_codes(self):
        """Override of `payment` to return the default payment method codes."""
        self.ensure_one()
        if self.code != "mellat":
            return super()._get_default_payment_method_codes()
        return const.DEFAULT_PAYMENT_METHOD_CODES

    # === BUSINESS METHODS === #

    def _vesta_verify_window(self):
        """Override of `vesta_payment` to return Mellat's verification window."""
        if self.code != "mellat":
            return super()._vesta_verify_window()
        return const.VERIFY_WINDOW_MINUTES

    def _vesta_test_connection(self):
        """Override of `vesta_payment` to ask Mellat for a payment token that is never used."""
        if self.code != "mellat":
            return super()._vesta_test_connection()
        now = utils.bank_now()
        result = self._mellat_call(
            "bpPayRequest",
            {
                "orderId": int(f"{int(time.time() * 1000)}{secrets.randbelow(100000):05d}"),
                "amount": 10000,
                "localDate": now.strftime("%Y%m%d"),
                "localTime": now.strftime("%H%M%S"),
                "additionalData": "Vesta Gateway connection test",
                "callBackUrl": urljoin(self.get_base_url(), "/payment/vesta/mellat/return/0/test"),
                "payerId": 0,
            },
        )
        code = result.split(",")[0].strip()
        if code != "0":
            raise ValidationError(utils.bank_message(self.env, const.RESULT_CODES, code))
        return self.env._("Mellat issued a payment token: the credentials and the server IP are accepted.")

    def _mellat_call(self, operation, values, reference=None):
        """Call an operation of Mellat's payment gateway, over REST or SOAP.

        Both APIs take the same parameters and return the same plain result: a result code, or
        "0,<RefId>" for bpPayRequest. The REST API reads the credentials from HTTP basic auth and
        from the body, depending on the operation, so both are sent.

        :param str operation: The operation, e.g. bpPayRequest.
        :param dict values: The parameters of the operation, after the credentials.
        :param str reference: The transaction reference, for the logs.
        :return: The raw result.
        :rtype: str
        """
        self.ensure_one()
        try:
            terminal_id = int(self.mellat_terminal_id)
        except (TypeError, ValueError):
            raise ValidationError(self.env._("The Mellat terminal ID must be a number.")) from None
        password = self.sudo().mellat_password or ""
        payload = {
            "terminalId": terminal_id,
            "userName": self.mellat_username or "",
            "userPassword": password,
            **values,
        }
        if self.mellat_api == "soap":
            result = self._vesta_soap_request(
                const.SOAP_URL, const.SOAP_NAMESPACE, operation, payload, qualified=False, reference=reference
            )
        else:
            result = self._send_api_request(
                "POST",
                const.REST_URL + operation,
                json=payload,
                reference=reference,
                vesta_auth=(self.mellat_username or "", password),
                vesta_format="text",
            )
        if not isinstance(result, str) or not result:
            raise ValidationError(self.env._("Bank Mellat returned an empty response."))
        return result
