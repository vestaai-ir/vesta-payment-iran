# Copyright 2026 Vesta AI (https://vestaai.ir)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo.addons.payment.const import SENSITIVE_KEYS as PAYMENT_SENSITIVE_KEYS

# Provider codes of the Iranian bank gateways managed by Vesta Gateway. Each code is added to the
# `code` selection of `payment.provider` by its own module (vesta_payment_<code>).
BANK_CODES = ("mellat", "saman", "parsian", "sadad", "pasargad")

# Path prefix of each bank on the sandbox server (https://sandbox.banktest.ir/<prefix>/<host>/...).
SANDBOX_PREFIXES = {
    "mellat": "mellat",
    "saman": "saman",
    "parsian": "parsian",
    "sadad": "melli",
    "pasargad": "pasargad",
}
DEFAULT_SANDBOX_URL = "https://sandbox.banktest.ir"

# Currencies accepted by Shaparak gateways. Banks always charge in Rials; Toman (IRT, a custom
# currency in many Iranian databases) is converted at 1 Toman = 10 Rials.
SUPPORTED_CURRENCIES = ("IRR", "IRT")
RIALS_PER_UNIT = {"IRR": 1, "IRT": 10}

# Time zone used by the banks for local dates and times sent in requests.
BANK_TIMEZONE = "Asia/Tehran"

# Return route of every bank: /payment/vesta/<provider_code>/return/<order_id>/<access_token>.
# The order id and an HMAC access token sit in the path because some banks (Pasargad) call the
# return URL with a GET form, which drops any query string of the URL.
RETURN_ROUTE = "/payment/vesta/<string:provider_code>/return/<string:order_id>/<string:access_token>"

# Minutes after which a draft transaction that never came back from the bank is cancelled. The
# bank reverses any unconfirmed payment by itself, so nothing is lost.
ABANDONED_AFTER_MINUTES = 120

# Credentials and signatures that must never reach the logs.
SENSITIVE_KEYS = {
    "userPassword",
    "password",
    "LoginAccount",
    "SignData",
    "TerminalKey",
    "Authorization",
}
PAYMENT_SENSITIVE_KEYS.update(SENSITIVE_KEYS)

# XML elements masked in logged SOAP envelopes.
SENSITIVE_XML_TAGS = ("userPassword", "LoginAccount", "password")

# Verification states shared by all banks.
VERIFY_STATES = [
    ("new", "Waiting for payment"),
    ("pending", "Verification retry"),
    ("verified", "Verified"),
    ("settled", "Settled"),
    ("failed", "Failed"),
    ("reversed", "Reversed"),
]

# Automatic routing of payments between the banks.
ROUTING_MODES = [
    ("customer", "Customer choice"),
    ("weighted", "Weighted distribution"),
    ("rotation", "Rotation"),
    ("priority", "Priority with failover"),
]
# A bank that failed to issue a payment token this many times in a row is paused for a while, so
# that routing sends customers to the other banks.
HEALTH_FAILURE_THRESHOLD = 3
HEALTH_PAUSE_MINUTES = 10
# Minutes between two uptime probes of a bank, when the company enables them.
UPTIME_PROBE_MINUTES = 10
# Number of upcoming routing decisions shown in the control center.
ROUTING_PREVIEW_SIZE = 24
