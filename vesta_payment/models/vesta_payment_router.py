# Copyright 2026 Vesta AI (https://vestaai.ir)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from odoo import api, fields, models
from odoo.addons.vesta_payment import const
from odoo.fields import Domain


class VestaPaymentRouter(models.AbstractModel):
    """Decide which bank takes the next payment.

    The decision only depends on the database: today's payments per bank, their weights, batches,
    limits and health. It is the same for the checkout page and for the control center preview,
    and two customers opening the checkout at the same time simply get the same bank.
    """

    _name = "vesta.payment.router"
    _description = "Vesta Gateway Routing"

    # === USAGE === #

    @api.model
    def _day_start(self, days=0):
        """Return the start of today (minus `days`) in the banks' time zone, as naive UTC."""
        tz = ZoneInfo(const.BANK_TIMEZONE)
        today = datetime.now(tz).date() - timedelta(days=days)
        return datetime.combine(today, time.min, tzinfo=tz).astimezone(ZoneInfo("UTC")).replace(tzinfo=None)

    @api.model
    def _usage(self, providers, since=None):
        """Return the payments of each provider since a date (today by default).

        :return: {provider_id: {"attempts": int, "done": int, "failed": int, "amount": float}}
                 where `attempts` counts every payment sent to the bank and `amount` sums the
                 successful payments, in Rials.
        :rtype: dict
        """
        since = since or self._day_start()
        usage = {provider.id: {"attempts": 0, "done": 0, "failed": 0, "amount": 0.0} for provider in providers}
        if not providers:
            return usage
        groups = (
            self.env["payment.transaction"]
            .sudo()
            ._read_group(
                Domain("provider_id", "in", providers.ids)
                & Domain("operation", "in", ("online_redirect", "online_direct", "online_token"))
                & Domain("create_date", ">=", since),
                groupby=["provider_id", "state", "currency_id"],
                aggregates=["__count", "amount:sum"],
            )
        )
        for provider, state, currency, count, amount in groups:
            stats = usage[provider.id]
            stats["attempts"] += count
            if state == "done":
                stats["done"] += count
                stats["amount"] += amount * const.RIALS_PER_UNIT.get(currency.name, 1)
            elif state in ("error", "cancel"):
                stats["failed"] += count
        return usage

    # === ELIGIBILITY === #

    @api.model
    def _blocked_reason(self, provider, stats, now=None):
        """Return why routing skips a provider right now, or False.

        `stats` may carry the success rate of the alert window (`success_rate`, set by
        :meth:`_add_health`) when the company asks for a minimum success rate.
        """
        now = now or fields.Datetime.now()
        if provider.vesta_paused_until and provider.vesta_paused_until > now:
            return "paused"
        if stats.get("low_success"):
            return "low_success"
        if provider.vesta_daily_count_limit and stats["done"] >= provider.vesta_daily_count_limit:
            return "count_limit"
        if provider.vesta_daily_amount_limit and stats["amount"] >= provider.vesta_daily_amount_limit:
            return "amount_limit"
        return False

    @api.model
    def _candidates(self, providers, usage):
        """Return the providers routing may use, best priority first.

        If every bank is paused or over its limit, all of them are returned: the bank itself then
        decides, rather than leaving the customer without any way to pay.
        """
        providers = providers.sorted(lambda p: (p.sequence, p.id))
        eligible = providers.filtered(lambda p: not self._blocked_reason(p, usage[p.id]))
        return eligible or providers

    @api.model
    def _add_health(self, providers, usage, company):
        """Flag in `usage` the providers whose recent success rate is below the company's minimum."""
        minimum = company.vesta_route_min_success
        if not minimum or not providers:
            return usage
        since = fields.Datetime.now() - timedelta(minutes=company.vesta_alert_window or 60)
        stats = self.env["vesta.payment.event"]._failure_stats(providers, since)
        for provider in providers:
            done, failed = stats[provider.id]
            total = done + failed
            rate = round(100 * done / total) if total else None
            usage[provider.id]["success_rate"] = rate
            usage[provider.id]["low_success"] = (
                rate is not None and total >= max(company.vesta_alert_min_payments, 1) and rate < minimum
            )
        return usage

    # === DECISION === #

    @api.model
    def _pick(self, candidates, usage, mode):
        """Return the provider that takes the next payment.

        - weighted: smooth weighted distribution; the bank furthest below its target share of
          today's payments goes next, so the shares converge to the weights at any time of day.
        - rotation: the banks take turns in their order, each for `vesta_routing_batch`
          consecutive payments.
        - priority: the first candidate; the next one only when it is paused or over a limit.

        :param payment.provider candidates: The candidates, best priority first.
        :param dict usage: The usage returned by :meth:`_usage`.
        :param str mode: The routing mode.
        :rtype: payment.provider
        """
        if not candidates or mode == "customer":
            return candidates.browse()
        if mode == "priority":
            return candidates[:1]
        if mode == "rotation":
            batches = [(provider, max(provider.vesta_routing_batch, 1)) for provider in candidates]
            cycle = sum(batch for _provider, batch in batches)
            position = sum(usage[p.id]["attempts"] for p in candidates) % cycle
            for provider, batch in batches:
                if position < batch:
                    return provider
                position -= batch
            return candidates[:1]
        weighted = candidates.filtered(lambda p: p.vesta_routing_weight > 0)
        weights = {p.id: p.vesta_routing_weight for p in weighted}
        if not weighted:  # Every weight is zero: share equally
            weighted, weights = candidates, {p.id: 1 for p in candidates}
        total_weight = sum(weights.values())
        total = sum(usage[p.id]["attempts"] for p in weighted)
        deficits = {p.id: weights[p.id] / total_weight * (total + 1) - usage[p.id]["attempts"] for p in weighted}
        best = max(deficits.values())
        return weighted.filtered(lambda p: deficits[p.id] == best)[:1]

    @api.model
    def _route(self, providers, company=None):
        """Apply the company's routing to the providers available for a payment.

        :param payment.provider providers: The providers available for the payment.
        :param res.company company: The company of the payment.
        :return: The providers to show and the provider chosen by routing (empty for customer
                 choice).
        :rtype: tuple(payment.provider, payment.provider)
        """
        company = company or self.env.company
        banks = providers.filtered("is_vesta_bank")
        mode = company.vesta_routing_mode
        if not banks:
            return providers, banks.browse()
        usage = self._add_health(banks, self._usage(banks), company)
        candidates = self._candidates(banks, usage)
        if mode == "customer":  # Unhealthy banks are hidden, the others keep their order
            return (providers - banks) | candidates, banks.browse()
        chosen = self._pick(candidates, usage, mode)
        shown = candidates if company.vesta_routing_show_all else chosen
        return (providers - banks) | shown, chosen

    @api.model
    def _preview(self, providers, mode, size=const.ROUTING_PREVIEW_SIZE, company=None):
        """Simulate the next routing decisions from today's usage.

        :return: The providers that would take the next `size` payments, in order.
        :rtype: list[payment.provider]
        """
        if mode == "customer" or not providers:
            return []
        usage = self._add_health(providers, self._usage(providers), company or self.env.company)
        candidates = self._candidates(providers, usage)
        upcoming = []
        for _i in range(size):
            chosen = self._pick(candidates, usage, mode)
            if not chosen:
                break
            upcoming.append(chosen)
            usage[chosen.id]["attempts"] += 1
        return upcoming
