# Copyright 2026 Vesta AI (https://vestaai.ir)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import re
from datetime import datetime
from zoneinfo import ZoneInfo

from lxml import etree

from odoo.addons.vesta_payment import const
from odoo.exceptions import ValidationError

SOAP_ENV_NS = "http://schemas.xmlsoap.org/soap/envelope/"
_XML_PARSER = etree.XMLParser(resolve_entities=False, no_network=True, remove_comments=True)
_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def bank_now():
    """Return the current date and time in the banks' time zone (Asia/Tehran)."""
    return datetime.now(ZoneInfo(const.BANK_TIMEZONE))


def bank_message(env, table, code, fallback=None):
    """Return the human-readable message of a bank result code in the user's language.

    :param env: The environment, used for the language and the fallback translation.
    :param dict table: The code table of the bank: {code: (english, persian)}.
    :param code: The result code returned by the bank.
    :param str fallback: The message to use when the code is unknown.
    :return: The message followed by the code, e.g. "Canceled by the user (17)".
    :rtype: str
    """
    entry = table.get(str(code).strip())
    if entry:
        text = entry[1] if (env.lang or "").startswith("fa") else entry[0]
    else:
        text = fallback or env._("Unknown response from the bank")
    return f"{text} ({code})"


def normalize_mobile(phone):
    """Return an Iranian mobile number as 09XXXXXXXXX, or None if the number is not one.

    :param str phone: A phone number in any common format (+98, 0098, 98, 09, Persian digits).
    :rtype: str|None
    """
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone.translate(_DIGITS))
    for prefix in ("0098", "98"):
        if digits.startswith(prefix) and len(digits) == len(prefix) + 10:
            digits = digits[len(prefix) :]
    if len(digits) == 10 and digits.startswith("9"):
        digits = "0" + digits
    return digits if re.fullmatch(r"09\d{9}", digits) else None


def mask_card(pan):
    """Keep only the first six and last four digits of a card number."""
    digits = re.sub(r"\D", "", pan or "")
    if len(digits) < 12:
        return pan or ""
    return f"{digits[:6]}******{digits[-4:]}"


def build_soap_envelope(namespace, operation, values, wrapper=None, qualified=True):
    """Build a SOAP 1.1 request envelope.

    :param str namespace: The target namespace of the operation.
    :param str operation: The name of the operation.
    :param dict values: The parameters of the operation, in order.
    :param str wrapper: The name of the element that wraps the parameters, if any.
    :param bool qualified: Whether the parameters belong to the target namespace (document/literal
                           with elementFormDefault="qualified") or are unqualified (rpc style).
    :return: The envelope, UTF-8 encoded.
    :rtype: bytes
    """
    envelope = etree.Element(f"{{{SOAP_ENV_NS}}}Envelope", nsmap={"soap": SOAP_ENV_NS})
    body = etree.SubElement(envelope, f"{{{SOAP_ENV_NS}}}Body")
    if qualified:
        parent = etree.SubElement(body, f"{{{namespace}}}{operation}", nsmap={None: namespace})
    else:
        parent = etree.SubElement(body, f"{{{namespace}}}{operation}", nsmap={"ns": namespace})

    def qname(name):
        return f"{{{namespace}}}{name}" if qualified else name

    if wrapper:
        parent = etree.SubElement(parent, qname(wrapper))
    for key, value in values.items():
        etree.SubElement(parent, qname(key)).text = "" if value is None else str(value)
    return etree.tostring(envelope, xml_declaration=True, encoding="utf-8")


def parse_soap_response(env, content):
    """Return the result of a SOAP response.

    The parser neither resolves entities nor reaches the network, so that a malicious response
    can't read local files or trigger requests (XXE).

    :param env: The environment, used for translations.
    :param bytes content: The raw response.
    :return: The children of the result element as a {local name: text} dict, or the text of the
             result element when it has no children.
    :rtype: dict|str
    :raise ValidationError: If the response is not a SOAP envelope or is a SOAP fault.
    """
    try:
        root = etree.fromstring(content, _XML_PARSER)
    except etree.XMLSyntaxError:
        raise ValidationError(env._("The bank returned an invalid response.")) from None

    def children(element):
        return [child for child in element if isinstance(child.tag, str)]

    body = next((el for el in children(root) if etree.QName(el).localname == "Body"), None)
    if body is None or not children(body):
        raise ValidationError(env._("The bank returned an empty response."))
    response = children(body)[0]
    if etree.QName(response).localname == "Fault":
        fault = next(
            (
                el.text
                for el in response.iter()
                if isinstance(el.tag, str) and etree.QName(el).localname in ("faultstring", "Text")
            ),
            "",
        )
        raise ValidationError(env._("The bank rejected the request: %s", (fault or "").strip()))
    result = children(response)[0] if children(response) else response
    if children(result):
        return {etree.QName(child).localname: (child.text or "").strip() for child in children(result)}
    return (result.text or "").strip()


def mask_xml(payload):
    """Mask the credentials of a SOAP envelope before logging it."""
    text = payload.decode("utf-8", "replace") if isinstance(payload, bytes) else payload
    for tag in const.SENSITIVE_XML_TAGS:
        text = re.sub(rf"(<(?:\w+:)?{tag}>)[^<]*(</)", r"\1[REDACTED]\2", text)
    return text
