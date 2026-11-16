# Copyright 2026 Vesta AI (https://vestaai.ir)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import re
from datetime import timedelta

from odoo import api, fields, models
from odoo.addons.vesta_payment import const
from odoo.fields import Domain

# Bank result codes whose cause is known, with the fix to apply: {code: (category, english, persian)}.
KNOWN_CAUSES = {
    # Server IP not registered with the bank
    "421": ("ip", "Register the server's public IP address with the bank.", "IP عمومی سرور را نزد بانک ثبت کنید."),
    "8": ("ip", "Register the server's public IP address with the bank.", "IP عمومی سرور را نزد بانک ثبت کنید."),
    "-18": ("ip", "Register the server's public IP address with the bank.", "IP عمومی سرور را نزد بانک ثبت کنید."),
    "-106": ("ip", "Register the server's public IP address with the bank.", "IP عمومی سرور را نزد بانک ثبت کنید."),
    "1003": ("ip", "Register the server's public IP address with the bank.", "IP عمومی سرور را نزد بانک ثبت کنید."),
    "-127": ("ip", "Register the server's public IP address with the bank.", "IP عمومی سرور را نزد بانک ثبت کنید."),
    # Credentials
    "21": ("credentials", "Check the terminal ID given by the bank.", "شناسه ترمینال دریافتی از بانک را بررسی کنید."),
    "24": (
        "credentials",
        "Check the username and password of the terminal.",
        "نام کاربری و رمز ترمینال را بررسی کنید.",
    ),
    "401": ("credentials", "Check the username, password and server IP.", "نام کاربری، رمز و IP سرور را بررسی کنید."),
    "-126": ("credentials", "Check the merchant PIN given by the bank.", "پین پذیرنده‌ی دریافتی از بانک را بررسی کنید."),
    "1012": ("credentials", "Check the terminal key and the server clock.", "کلید تراکنش و ساعت سرور را بررسی کنید."),
    "-105": (
        "credentials",
        "The bank doesn't know this terminal; check its ID.",
        "بانک این ترمینال را نمی‌شناسد؛ شناسه را بررسی کنید.",
    ),
    "-104": (
        "credentials",
        "The terminal is disabled at the bank; call the bank.",
        "ترمینال نزد بانک غیرفعال است؛ با بانک تماس بگیرید.",
    ),
    # Domain and clock
    "62": (
        "domain",
        "Set web.base.url to the domain registered with the bank.",
        "web.base.url را روی دامنه‌ی ثبت‌شده نزد بانک بگذارید.",
    ),
    "1023": (
        "domain",
        "Set web.base.url to the domain registered with the bank.",
        "web.base.url را روی دامنه‌ی ثبت‌شده نزد بانک بگذارید.",
    ),
    "1018": ("clock", "Synchronize the server clock with NTP.", "ساعت سرور را با NTP هماهنگ کنید."),
    # Bank outage
    "34": (
        "outage",
        "Bank-side error; it usually clears by itself. Routing can use other banks.",
        "خطای سمت بانک است و معمولاً خودش رفع می‌شود؛ مسیریابی می‌تواند از بانک‌های دیگر استفاده کند.",
    ),
    "500": (
        "outage",
        "Bank-side error; it usually clears by itself. Routing can use other banks.",
        "خطای سمت بانک است و معمولاً خودش رفع می‌شود؛ مسیریابی می‌تواند از بانک‌های دیگر استفاده کند.",
    ),
    "13005": (
        "outage",
        "The bank is temporarily unavailable; routing can use other banks.",
        "بانک موقتاً در دسترس نیست؛ مسیریابی می‌تواند از بانک‌های دیگر استفاده کند.",
    ),
    "1056": (
        "outage",
        "The bank is temporarily unavailable; routing can use other banks.",
        "بانک موقتاً در دسترس نیست؛ مسیریابی می‌تواند از بانک‌های دیگر استفاده کند.",
    ),
    "1065": (
        "outage",
        "The bank is temporarily unavailable; routing can use other banks.",
        "بانک موقتاً در دسترس نیست؛ مسیریابی می‌تواند از بانک‌های دیگر استفاده کند.",
    ),
    "1066": (
        "outage",
        "The bank is temporarily unavailable; routing can use other banks.",
        "بانک موقتاً در دسترس نیست؛ مسیریابی می‌تواند از بانک‌های دیگر استفاده کند.",
    ),
    "-32768": ("outage", "Bank-side error; it usually clears by itself.", "خطای سمت بانک است و معمولاً خودش رفع می‌شود."),
}

# Advice per category when the bank code says nothing more: {category: (english, persian)}.
CATEGORY_ADVICE = {
    "connection": (
        "Odoo could not reach the bank. Check the server's internet access to *.shaparak.ir and DNS.",
        "اودو به بانک وصل نشد. دسترسی سرور به ‎*.shaparak.ir و DNS را بررسی کنید.",
    ),
    "verification": (
        "The bank refused to confirm the payment; if money was taken, it returns it to the card.",
        "بانک پرداخت را تأیید نکرد؛ اگر مبلغی کسر شده باشد به کارت برمی‌گردد.",
    ),
    "amount_mismatch": (
        "The confirmed amount differed from the order and was reversed. Check for tampering.",
        "مبلغ تأییدشده با سفارش فرق داشت و برگشت خورد. احتمال دست‌کاری را بررسی کنید.",
    ),
    "double_spend": (
        "A bank receipt was reused for another order. This is an attack attempt; check the customer.",
        "یک رسید بانکی برای سفارش دیگری دوباره استفاده شد. این تلاش برای تقلب است؛ مشتری را بررسی کنید.",
    ),
    "suspicious": (
        "A return from the bank didn't match its payment and was ignored. Repeated cases suggest an attack.",
        "یک بازگشت از بانک با پرداختش جور نبود و نادیده گرفته شد. تکرار آن نشانه‌ی حمله است.",
    ),
    "bank_paused": (
        "The bank failed several times in a row and is paused in routing; it comes back by itself.",
        "بانک چند بار پیاپی خطا داد و در مسیریابی متوقف شد؛ خودکار برمی‌گردد.",
    ),
    "failure_rate": (
        "Failed payments passed the alert threshold. Look at the latest errors of this bank.",
        "پرداخت‌های ناموفق از آستانه‌ی هشدار گذشت. آخرین خطاهای این بانک را بررسی کنید.",
    ),
    "payment_request": (
        "The bank refused to start the payment. Check the error code.",
        "بانک شروع پرداخت را نپذیرفت. کد خطا را بررسی کنید.",
    ),
    "connection_test": (
        "The connection test failed. Fix the cause before going live.",
        "آزمایش اتصال ناموفق بود. پیش از فعال‌سازی عملیاتی علت را برطرف کنید.",
    ),
}

CATEGORIES = [
    ("payment_request", "Payment request"),
    ("verification", "Verification"),
    ("connection", "Connection"),
    ("ip", "Server IP"),
    ("credentials", "Credentials"),
    ("domain", "Return domain"),
    ("clock", "Server clock"),
    ("outage", "Bank outage"),
    ("amount_mismatch", "Amount mismatch"),
    ("double_spend", "Receipt reuse"),
    ("suspicious", "Suspicious return"),
    ("bank_paused", "Bank paused"),
    ("failure_rate", "Failure rate alert"),
    ("connection_test", "Connection test"),
]

# Identical problems within this window are grouped into one log entry.
GROUPING_MINUTES = 60
_CODE_PATTERN = re.compile(r"\((-?\d+)\)")


class VestaPaymentEvent(models.Model):
    """Problems of the bank gateways, diagnosed and grouped.

    Each problem is classified (server IP, credentials, outage, attack, ...) from the bank's result
    code, comes with the fix to apply, and repeats of the same problem increase a counter instead
    of flooding the log.
    """

    _name = "vesta.payment.event"
    _description = "Bank Gateway Log"
    _order = "last_seen desc, id desc"

    name = fields.Char(string="Problem", required=True)
    level = fields.Selection(
        string="Level",
        selection=[("warning", "Warning"), ("error", "Error"), ("critical", "Critical")],
        default="error",
        required=True,
        index=True,
    )
    category = fields.Selection(string="Category", selection=CATEGORIES, required=True, index=True)
    code = fields.Char(string="Bank Code")
    advice = fields.Text(string="What to Do")
    provider_id = fields.Many2one(string="Bank", comodel_name="payment.provider", ondelete="cascade", index=True)
    transaction_id = fields.Many2one(string="Last Payment", comodel_name="payment.transaction", ondelete="set null")
    company_id = fields.Many2one(comodel_name="res.company", default=lambda self: self.env.company, required=True)
    occurrences = fields.Integer(string="Occurrences", default=1)
    first_seen = fields.Datetime(string="First Seen", default=fields.Datetime.now, required=True)
    last_seen = fields.Datetime(string="Last Seen", default=fields.Datetime.now, required=True, index=True)
    resolved = fields.Boolean(string="Resolved", index=True)
    resolved_date = fields.Datetime(string="Resolved On", readonly=True)
    resolved_uid = fields.Many2one(string="Resolved By", comodel_name="res.users", readonly=True)

    # === LOGGING === #

    @api.model
    def _log(self, category, message, provider=None, transaction=None, level="error", code=None):
        """Record a problem, grouping it with the same open problem of the last hour.

        :param str category: The category, see `CATEGORIES`; refined from the bank code when known.
        :param str message: The message, usually the bank's message with its code.
        :param payment.provider provider: The bank concerned, if any.
        :param payment.transaction transaction: The payment concerned, if any.
        :param str level: "warning", "error" or "critical".
        :param str code: The bank's result code; read from "(code)" in the message if not given.
        :return: The log entry.
        :rtype: vesta.payment.event
        """
        Event = self.sudo()
        code = code or (_CODE_PATTERN.findall(message or "") or [None])[-1]
        known = KNOWN_CAUSES.get(code or "")
        if known and category in ("payment_request", "verification", "connection_test"):
            category = known[0]
        lang_fa = (self.env.lang or "").startswith("fa")
        if known:
            advice = known[2] if lang_fa else known[1]
        else:
            advice = CATEGORY_ADVICE.get(category, ("", ""))[1 if lang_fa else 0]
        provider = provider or (transaction and transaction.provider_id) or self.env["payment.provider"]
        now = fields.Datetime.now()
        existing = Event.search(
            Domain("category", "=", category)
            & Domain("provider_id", "=", provider.id or False)
            & Domain("code", "=", code or False)
            & Domain("resolved", "=", False)
            & Domain("last_seen", ">=", now - timedelta(minutes=GROUPING_MINUTES)),
            limit=1,
        )
        values = {"name": (message or "")[:500], "last_seen": now, "transaction_id": transaction and transaction.id}
        if existing:
            existing.write(
                {**values, "occurrences": existing.occurrences + 1, "level": max_level(existing.level, level)}
            )
            return existing
        return Event.create(
            {
                **values,
                "category": category,
                "level": level,
                "code": code,
                "advice": advice,
                "provider_id": provider.id,
                "company_id": (provider.company_id or self.env.company).id,
                "first_seen": now,
            }
        )

    # === ALERTS === #

    @api.model
    def _failure_stats(self, providers, since):
        """Return {provider_id: (successful, failed)} for the payments since a date."""
        stats = {provider.id: [0, 0] for provider in providers}
        groups = (
            self.env["payment.transaction"]
            .sudo()
            ._read_group(
                Domain("provider_id", "in", providers.ids)
                & Domain("operation", "in", ("online_redirect", "online_direct", "online_token"))
                & Domain("state", "in", ("done", "error", "cancel"))
                & Domain("create_date", ">=", since),
                groupby=["provider_id", "state"],
                aggregates=["__count"],
            )
        )
        for provider, state, count in groups:
            stats[provider.id][0 if state == "done" else 1] += count
        return stats

    @api.model
    def _check_failure_alerts(self):
        """Raise an alert for each bank whose failure rate passed its company's threshold."""
        providers = (
            self.env["payment.provider"]
            .sudo()
            .search(Domain("code", "in", const.BANK_CODES) & Domain("is_published", "=", True))
        )
        alerts = self.browse()
        for company in providers.company_id:
            if not company.vesta_alert_failure_rate:
                continue
            company_providers = providers.filtered(lambda p, c=company: p.company_id == c)
            since = fields.Datetime.now() - timedelta(minutes=company.vesta_alert_window or 60)
            for provider in company_providers:
                done, failed = self._failure_stats(provider, since)[provider.id]
                total = done + failed
                if total < max(company.vesta_alert_min_payments, 1):
                    continue
                rate = round(100 * failed / total)
                if rate >= company.vesta_alert_failure_rate:
                    alerts |= self.with_company(company)._log(
                        "failure_rate",
                        self.env._(
                            "%(bank)s: %(rate)s%% of the last %(total)s payments failed (threshold %(limit)s%%).",
                            bank=provider.name,
                            rate=rate,
                            total=total,
                            limit=company.vesta_alert_failure_rate,
                        ),
                        provider=provider,
                        level="critical",
                        code=None,
                    )
        return alerts

    # === ACTIONS === #

    def action_resolve(self):
        self.write({"resolved": True, "resolved_date": fields.Datetime.now(), "resolved_uid": self.env.uid})

    def action_reopen(self):
        self.write({"resolved": False, "resolved_date": False, "resolved_uid": False})

    @api.autovacuum
    def _gc_resolved_events(self):
        """Forget resolved problems after 90 days."""
        self.search(
            Domain("resolved", "=", True) & Domain("last_seen", "<", fields.Datetime.now() - timedelta(days=90))
        ).unlink()


LEVEL_ORDER = {"warning": 0, "error": 1, "critical": 2}


def max_level(first, second):
    return first if LEVEL_ORDER[first] >= LEVEL_ORDER[second] else second
