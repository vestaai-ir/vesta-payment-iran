# Copyright 2026 Vesta AI (https://vestaai.ir)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import pprint

from odoo import http
from odoo.addons.payment.logging import get_payment_logger
from odoo.addons.vesta_payment import const
from odoo.http import request

_logger = get_payment_logger(__name__, const.SENSITIVE_KEYS)

# Page answered to the bank's form post. It sends the customer to /payment/status from Odoo's own
# origin: browsers don't send the session cookie (SameSite=Lax) on a redirect that follows a
# cross-site POST, but they do on a navigation started by a same-site page, so the status page
# finds the customer's transaction again.
RETURN_PAGE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="robots" content="noindex">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="0;url=/payment/status">
<title>Vesta Gateway</title></head>
<body style="font-family: Tahoma, sans-serif; text-align: center; padding: 4em 1em; color: #333;">
<p dir="rtl">در حال بازگشت به فروشگاه…</p><p>Returning to the shop…</p>
<p><a href="/payment/status">ادامه · Continue</a></p>
</body></html>"""


class VestaPaymentController(http.Controller):
    @http.route(
        const.RETURN_ROUTE,
        type="http",
        auth="public",
        methods=["GET", "POST"],
        csrf=False,
        save_session=False,
    )
    def vesta_return_from_bank(self, provider_code, order_id, access_token, **data):
        """Verify the payment after the customer comes back from the bank.

        The data posted by the bank is never trusted on its own: the URL must carry a valid HMAC of
        the order id, the token must be the one the bank issued for the transaction, and the payment
        is confirmed with a server-to-server call before the transaction is updated.

        The route is flagged with `save_session=False` because the bank posts the form from its own
        site: the browser doesn't send the session cookie with that POST, and Odoo must not replace
        the customer's session with a new one. The page returned then opens /payment/status from
        Odoo's origin, which carries the cookie again.

        :param str provider_code: The code of the bank, e.g. "mellat".
        :param str order_id: The numeric order id sent to the bank.
        :param str access_token: The HMAC of the provider code and the order id.
        :param dict data: The data sent by the bank.
        """
        _logger.info(
            "Handling return from %s for order %s with data:\n%s",
            provider_code,
            order_id,
            pprint.pformat(data),
        )
        tx_sudo = (
            request.env["payment.transaction"].sudo()._vesta_find_from_return(provider_code, order_id, access_token)
        )
        if tx_sudo:
            tx_sudo._vesta_handle_return(data)
        return request.make_response(
            RETURN_PAGE,
            headers=[
                ("Content-Type", "text/html; charset=utf-8"),
                ("Cache-Control", "no-store"),
                ("Referrer-Policy", "no-referrer"),
            ],
        )
