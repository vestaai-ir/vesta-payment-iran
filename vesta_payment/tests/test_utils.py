# Copyright 2026 Vesta AI (https://vestaai.ir)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from lxml import etree

from odoo.addons.vesta_payment import utils
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestVestaUtils(TransactionCase):
    def test_normalize_mobile(self):
        for phone in ("09123456789", "+989123456789", "00989123456789", "989123456789", "912 345 6789", "۰۹۱۲۳۴۵۶۷۸۹"):
            self.assertEqual(utils.normalize_mobile(phone), "09123456789", phone)
        for phone in (None, "", "02112345678", "+1 555 0100", "0912345"):
            self.assertIsNone(utils.normalize_mobile(phone), phone)

    def test_mask_card(self):
        self.assertEqual(utils.mask_card("5022291067782928"), "502229******2928")
        self.assertEqual(utils.mask_card("502229******2928"), "502229******2928")
        self.assertEqual(utils.mask_card(None), "")

    def test_bank_message(self):
        self.env["res.lang"]._activate_lang("fa_IR")
        table = {"17": ("Canceled by the customer", "کاربر انصراف داده است")}
        self.assertEqual(utils.bank_message(self.env, table, 17), "Canceled by the customer (17)")
        self.assertEqual(
            utils.bank_message(self.env(context={"lang": "fa_IR"}), table, "17"), "کاربر انصراف داده است (17)"
        )
        self.assertIn("(999)", utils.bank_message(self.env, table, 999))

    def test_soap_envelope_qualified(self):
        envelope = utils.build_soap_envelope(
            "urn:sale", "SaleRequest", {"Amount": 1000, "Note": "<&>"}, wrapper="requestData"
        )
        root = etree.fromstring(envelope)
        values = root.find(".//{urn:sale}requestData")
        self.assertEqual(values.find("{urn:sale}Amount").text, "1000")
        self.assertEqual(values.find("{urn:sale}Note").text, "<&>", "Values must be escaped, not injected")

    def test_soap_envelope_unqualified(self):
        envelope = utils.build_soap_envelope("urn:bps", "bpPayRequest", {"terminalId": 1}, qualified=False)
        root = etree.fromstring(envelope)
        operation = root.find(".//{urn:bps}bpPayRequest")
        self.assertEqual(operation.find("terminalId").text, "1")

    def test_parse_soap_response(self):
        response = (
            b'<?xml version="1.0"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body>'
            b'<R xmlns="urn:x"><Result><Status>0</Status><Token>42</Token></Result></R></s:Body></s:Envelope>'
        )
        self.assertEqual(utils.parse_soap_response(self.env, response), {"Status": "0", "Token": "42"})
        text_response = response.replace(
            b"<Result><Status>0</Status><Token>42</Token></Result>", b"<return>0,ABC</return>"
        )
        self.assertEqual(utils.parse_soap_response(self.env, text_response), "0,ABC")

    def test_parse_soap_fault_and_garbage(self):
        fault = (
            b'<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body><s:Fault>'
            b"<faultcode>s:Client</faultcode><faultstring>Bad PIN</faultstring></s:Fault></s:Body></s:Envelope>"
        )
        with self.assertRaisesRegex(ValidationError, "Bad PIN"):
            utils.parse_soap_response(self.env, fault)
        with self.assertRaises(ValidationError):
            utils.parse_soap_response(self.env, b"<html>Request Rejected</html")

    def test_parse_soap_no_external_entities(self):
        """A malicious response must not read local files (XXE)."""
        xxe = (
            b'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY x SYSTEM "file:///etc/passwd">]>'
            b'<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body><R><return>&x;</return></R>'
            b"</s:Body></s:Envelope>"
        )
        try:
            result = utils.parse_soap_response(self.env, xxe)
        except ValidationError:
            return
        self.assertNotIn("root:", result or "")

    def test_mask_xml(self):
        masked = utils.mask_xml(b"<a><userPassword>secret</userPassword><ns:LoginAccount>PIN</ns:LoginAccount></a>")
        self.assertNotIn("secret", masked)
        self.assertNotIn("PIN<", masked)
