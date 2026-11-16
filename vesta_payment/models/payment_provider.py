# Copyright 2026 Vesta AI (https://vestaai.ir)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import json
import re
from datetime import timedelta
from pprint import pformat
from urllib.parse import urlsplit

import requests

from odoo import api, fields, models
from odoo.addons.payment import utils as payment_utils
from odoo.addons.payment.logging import get_payment_logger
from odoo.addons.vesta_payment import const, utils
from odoo.exceptions import UserError, ValidationError

_logger = get_payment_logger(__name__, const.SENSITIVE_KEYS)


class PaymentProvider(models.Model):
    _inherit = "payment.provider"

    is_vesta_bank = fields.Boolean(
        string="Iranian Bank Gateway",
        compute="_compute_is_vesta_bank",
        search="_search_is_vesta_bank",
    )
    vesta_sandbox_url = fields.Char(
        string="Sandbox Server",
        default=const.DEFAULT_SANDBOX_URL,
        help="Server used while the provider is in test mode. Requests to the bank's production"
        " host are sent to <server>/<bank>/<host>/<path> instead, as on banktest.ir.",
    )
    vesta_check_date = fields.Datetime(string="Last Connection Test", readonly=True, copy=False)
    vesta_check_ok = fields.Boolean(string="Last Test Succeeded", readonly=True, copy=False)
    vesta_check_message = fields.Char(string="Last Test Result", readonly=True, copy=False)

    # Automatic routing (see vesta.payment.router)
    vesta_routing_weight = fields.Integer(
        string="Routing Weight",
        default=10,
        help="Share of the payments this bank takes in weighted distribution, relative to the"
        " other banks: with weights 60, 30 and 10, the banks take 60%, 30% and 10%.",
    )
    vesta_routing_batch = fields.Integer(
        string="Rotation Batch",
        default=1,
        help="Number of consecutive payments this bank takes before the next one in rotation.",
    )
    vesta_daily_count_limit = fields.Integer(
        string="Daily Payments Limit",
        help="Stop routing payments to this bank once it confirmed this many payments today. 0 means no limit.",
    )
    vesta_daily_amount_limit = fields.Float(
        string="Daily Amount Limit (Rial)",
        digits=(16, 0),
        help="Stop routing payments to this bank once it collected this amount today, for"
        " instance the daily ceiling of the terminal. 0 means no limit.",
    )
    vesta_failure_streak = fields.Integer(string="Consecutive Failures", readonly=True, copy=False)
    vesta_paused_until = fields.Datetime(
        string="Paused Until",
        readonly=True,
        copy=False,
        help="The bank failed to issue payment tokens several times in a row: routing skips it until this time.",
    )

    # === COMPUTE METHODS === #

    @api.depends("code")
    def _compute_is_vesta_bank(self):
        for provider in self:
            provider.is_vesta_bank = provider.code in const.BANK_CODES

    def _search_is_vesta_bank(self, operator, value):
        if operator not in ("=", "!=") or not isinstance(value, bool):
            raise UserError(self.env._("Unsupported search on Iranian bank gateways."))
        positive = (operator == "=") == value
        return [("code", "in" if positive else "not in", const.BANK_CODES)]

    def _get_supported_currencies(self):
        """Override of `payment` to restrict Iranian banks to Rial and Toman."""
        supported_currencies = super()._get_supported_currencies()
        if self.code in const.BANK_CODES:
            supported_currencies = supported_currencies.filtered(lambda c: c.name in const.SUPPORTED_CURRENCIES)
        return supported_currencies

    # === CONSTRAINT METHODS === #

    @api.constrains(
        "vesta_routing_weight", "vesta_routing_batch", "vesta_daily_count_limit", "vesta_daily_amount_limit"
    )
    def _check_vesta_routing_values(self):
        for provider in self:
            if (
                min(provider.vesta_routing_weight, provider.vesta_daily_count_limit, provider.vesta_daily_amount_limit)
                < 0
            ):
                raise ValidationError(self.env._("Routing weights and limits can't be negative."))
            if provider.vesta_routing_batch < 1:
                raise ValidationError(self.env._("A rotation batch takes at least one payment."))

    @api.constrains("vesta_sandbox_url")
    def _check_vesta_sandbox_url(self):
        for provider in self.filtered("vesta_sandbox_url"):
            if urlsplit(provider.vesta_sandbox_url).scheme != "https":
                raise ValidationError(self.env._("The sandbox server must use HTTPS."))

    # === ACTION METHODS === #

    def action_vesta_set_live(self):
        """Publish the provider in live mode, with the bank's production servers."""
        self._vesta_ensure_installed()
        self.write({"is_live": True, "is_published": True})
        return self._vesta_notify(self.env._("%s is now live.", ", ".join(self.mapped("name"))))

    def action_vesta_set_test(self):
        """Publish the provider in test mode, with the sandbox server."""
        self._vesta_ensure_installed()
        self.write({"is_live": False, "is_published": True})
        return self._vesta_notify(self.env._("%s is in test mode.", ", ".join(self.mapped("name"))), kind="warning")

    def action_vesta_disable(self):
        """Hide the provider from customers. Its settings and transactions are kept."""
        self.write({"is_published": False})
        return self._vesta_notify(self.env._("%s is disabled.", ", ".join(self.mapped("name"))), kind="info")

    def action_vesta_test_connection(self):
        """Check the credentials, the server's IP address and the bank's availability."""
        self.ensure_one()
        self._vesta_ensure_installed()
        try:
            message = self._vesta_test_connection()
            success = True
        except (UserError, ValidationError) as error:
            message = str(error.args[0] if error.args else error)
            success = False
        self.write(
            {
                "vesta_check_date": fields.Datetime.now(),
                "vesta_check_ok": success,
                "vesta_check_message": message[:250],
            }
        )
        mode = self.env._("live") if self.is_live else self.env._("test")
        title = self.env._("%(bank)s (%(mode)s): connection OK", bank=self.name, mode=mode)
        if not success:
            title = self.env._("%(bank)s (%(mode)s): connection failed", bank=self.name, mode=mode)
        return self._vesta_notify(message, title=title, kind="success" if success else "danger")

    def _vesta_ensure_installed(self):
        for provider in self:
            if provider.code not in const.BANK_CODES:
                raise UserError(self.env._("%s is not an Iranian bank gateway of Vesta Gateway.", provider.name))

    def _vesta_notify(self, message, title=None, kind="success"):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": title or self.env._("Vesta Gateway"),
                "message": message,
                "type": kind,
                "sticky": kind == "danger",
                "next": {"type": "ir.actions.client", "tag": "soft_reload"},
            },
        }

    # === BUSINESS METHODS - ROUTING === #

    @api.model
    def _find_available_providers(self, company_id, partner_id, amount, *, is_validation=False, report=None, **kwargs):
        """Override of `payment` to apply the automatic routing between Iranian banks.

        The provider chosen by routing is passed in the context so that its payment method is
        listed first (see `payment.method._sort_by_display_order`).
        """
        providers = super()._find_available_providers(
            company_id, partner_id, amount, is_validation=is_validation, report=report, **kwargs
        )
        if is_validation or kwargs.get("force_tokenization") or not providers.filtered("is_vesta_bank"):
            return providers
        company = self.env["res.company"].browse(company_id).exists() or self.env.company
        shown, chosen = self.env["vesta.payment.router"]._route(providers, company)
        payment_utils.add_to_report(
            report, providers - shown, available=False, reason=self.env._("routed to another bank")
        )
        return shown.with_context(vesta_routed_provider_id=chosen.id)

    def _vesta_register_failure(self):
        """Count a failed token request; pause the bank after several failures in a row."""
        self.ensure_one()
        streak = self.vesta_failure_streak + 1
        values = {"vesta_failure_streak": streak}
        if streak >= const.HEALTH_FAILURE_THRESHOLD:
            values["vesta_paused_until"] = fields.Datetime.now() + timedelta(minutes=const.HEALTH_PAUSE_MINUTES)
            _logger.warning("Pausing %s in routing after %s failures in a row.", self.name, streak)
        self.sudo().write(values)

    def _vesta_register_success(self):
        """Reset the failure streak after the bank issued a payment token."""
        self.ensure_one()
        if self.vesta_failure_streak or self.vesta_paused_until:
            self.sudo().write({"vesta_failure_streak": 0, "vesta_paused_until": False})

    def action_vesta_resume(self):
        """Put a paused bank back in the routing."""
        self.sudo().write({"vesta_failure_streak": 0, "vesta_paused_until": False})

    # === BUSINESS METHODS === #

    def _vesta_test_connection(self):
        """Run a harmless request against the bank with the provider's credentials.

        Bank modules override this method; the request must not move any money (for instance, it
        only asks for a payment token that is never used).

        Note: `self.ensure_one()`

        :return: A message describing the successful test.
        :rtype: str
        :raise ValidationError: If the bank rejects the credentials or can't be reached.
        """
        raise UserError(self.env._("This bank can't be tested yet."))

    def _vesta_verify_window(self):
        """Return the minutes during which the bank accepts the confirmation of a payment.

        After this window the bank reverses the payment by itself and Odoo stops retrying.

        :rtype: int
        """
        return 20

    def _vesta_url(self, url):
        """Return the production URL in live mode, or its sandbox mirror in test mode.

        Note: `self.ensure_one()`

        :param str url: The production URL of the bank, e.g. https://bpm.shaparak.ir/pgwchannel/...
        :return: The URL to call.
        :rtype: str
        """
        self.ensure_one()
        if self.is_live:
            return url
        parts = urlsplit(url)
        base = (self.vesta_sandbox_url or const.DEFAULT_SANDBOX_URL).rstrip("/")
        query = f"?{parts.query}" if parts.query else ""
        return f"{base}/{const.SANDBOX_PREFIXES[self.code]}/{parts.netloc}{parts.path}{query}"

    def _vesta_is_bank_url(self, url, production_host):
        """Check that a URL returned by the bank points to the bank (or the sandbox in test mode).

        :param str url: The URL to check.
        :param str production_host: The production host of the bank, e.g. pep.shaparak.ir.
        :rtype: bool
        """
        parts = urlsplit(url or "")
        if parts.scheme != "https":
            return False
        if self.is_live:
            return parts.netloc == production_host
        return parts.netloc == urlsplit(self.vesta_sandbox_url or const.DEFAULT_SANDBOX_URL).netloc

    def _vesta_soap_request(
        self, url, namespace, operation, values, *, wrapper=None, qualified=True, soap_action=None, reference=None
    ):
        """Call a SOAP operation of the bank and return its result.

        :param str url: The production URL of the service (mapped to the sandbox in test mode).
        :param str namespace: The target namespace of the service.
        :param str operation: The name of the operation.
        :param dict values: The parameters of the operation.
        :param str wrapper: The element wrapping the parameters, if any.
        :param bool qualified: Whether the parameters are namespace-qualified.
        :param str soap_action: The SOAPAction header.
        :param str reference: The transaction reference, for the logs.
        :return: The result, see :func:`utils.parse_soap_response`.
        :rtype: dict|str
        """
        envelope = utils.build_soap_envelope(namespace, operation, values, wrapper=wrapper, qualified=qualified)
        headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": f'"{soap_action or ""}"',
        }
        return self._send_api_request(
            "POST", url, data=envelope, reference=reference, vesta_headers=headers, vesta_format="soap"
        )

    # === REQUEST HELPERS === #

    def _build_request_url(self, endpoint, **kwargs):
        """Override of `payment` to map the bank's production URL to the sandbox in test mode."""
        if self.code not in const.BANK_CODES:
            return super()._build_request_url(endpoint, **kwargs)
        return self._vesta_url(endpoint)

    def _build_request_headers(self, method, endpoint, payload, **kwargs):
        """Override of `payment` to pass the headers given by the bank module."""
        if self.code not in const.BANK_CODES:
            return super()._build_request_headers(method, endpoint, payload, **kwargs)
        return {"Accept": "application/json, text/xml, text/plain", **(kwargs.get("vesta_headers") or {})}

    def _build_request_auth(self, **kwargs):
        """Override of `payment` to pass the HTTP basic auth given by the bank module."""
        if self.code not in const.BANK_CODES:
            return super()._build_request_auth(**kwargs)
        return kwargs.get("vesta_auth") or ()

    def _parse_response_content(self, response, **kwargs):
        """Override of `payment` to parse JSON, SOAP or plain text responses."""
        if self.code not in const.BANK_CODES:
            return super()._parse_response_content(response, **kwargs)
        response_format = kwargs.get("vesta_format", "json")
        if response_format == "soap":
            return utils.parse_soap_response(self.env, response.content)
        if response_format == "text":
            return response.text.strip().strip('"')
        try:
            return response.json()
        except requests.exceptions.JSONDecodeError:
            raise ValidationError(
                self.env._("The bank returned an unexpected response: %s", self._vesta_short_text(response.text))
            ) from None

    def _parse_response_error(self, response):
        """Override of `payment` to keep bank error pages short and readable."""
        if self.code not in const.BANK_CODES:
            return super()._parse_response_error(response)
        return self._vesta_short_text(response.text)

    @staticmethod
    def _vesta_short_text(text):
        text = re.sub(r"<[^>]+>", " ", text or "")
        return re.sub(r"\s+", " ", text).strip()[:300]

    def _log_request(self, method, url, payload, *, reference=None):
        """Override of `payment` to mask the credentials of SOAP envelopes."""
        if self.code in const.BANK_CODES and isinstance(payload, (bytes, str)):
            payload = utils.mask_xml(payload)
        return super()._log_request(method, url, payload, reference=reference)

    def _log_response(self, response, *, reference=None):
        """Override of `payment` to mask tokens and credentials in logged bank responses."""
        if self.code not in const.BANK_CODES:
            return super()._log_response(response, reference=reference)
        text = utils.mask_xml(response.text or "")
        try:
            data = json.loads(text)
            if isinstance(data, dict) and "token" in data and "username" in data:  # Pasargad login
                data["token"] = "[REDACTED]"
            text = pformat(data)
        except ValueError:
            pass
        log_values = {
            "code": response.status_code,
            "status": response.reason,
            "url": response.url,
            "ref": reference or f"provider {self.id}",
            "data": text,
        }
        log = _logger.info if response.ok else _logger.error
        log("Received HTTP %(code)s %(status)s from %(url)s for %(ref)s.\n%(data)s", log_values)
