# Copyright 2026 Vesta AI (https://vestaai.ir)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from datetime import timedelta

from odoo import api, fields, models
from odoo.addons.vesta_payment import const
from odoo.exceptions import AccessError, UserError
from odoo.fields import Domain

PERIOD_DAYS = {"today": 0, "week": 6, "month": 29}
BANK_FIELDS = {
    "weight": "vesta_routing_weight",
    "batch": "vesta_routing_batch",
    "count_limit": "vesta_daily_count_limit",
    "amount_limit": "vesta_daily_amount_limit",
}


class VestaPaymentBank(models.Model):
    """Data and actions of the Vesta Gateway control center (client action)."""

    _inherit = "vesta.payment.bank"

    # === DATA === #

    @api.model
    def get_control_center(self, period="today"):
        """Return everything the control center shows, for the current company.

        :param str period: "today", "week" (7 days) or "month" (30 days).
        :rtype: dict
        """
        Router = self.env["vesta.payment.router"]
        company = self.env.company
        days = PERIOD_DAYS.get(period, 0)
        banks = self._control_center_banks()
        providers = banks.provider_id
        today = Router._add_health(providers, Router._usage(providers), company)
        window_start = fields.Datetime.now() - timedelta(minutes=company.vesta_alert_window or 60)
        window = self.env["vesta.payment.event"]._failure_stats(providers, window_start)
        stats = Router._usage(providers, Router._day_start(days)) if days else today
        pending = dict(
            self.env["payment.transaction"]
            .sudo()
            ._read_group(
                Domain("provider_id", "in", providers.ids) & Domain("vesta_verify_state", "=", "pending"),
                groupby=["provider_id"],
                aggregates=["__count"],
            )
        )
        published = providers.filtered("is_published")
        candidates = Router._candidates(published, today) if published else published
        mode = company.vesta_routing_mode
        targets = self._target_shares(candidates, mode)
        total_today = sum(today[p.id]["attempts"] for p in published) or 0
        upcoming = Router._preview(published, mode, company=company)
        next_provider = upcoming[0] if upcoming else providers.browse()

        bank_rows = []
        for bank in banks:
            provider = bank.provider_id
            row_today = today.get(provider.id, {"attempts": 0, "done": 0, "failed": 0, "amount": 0.0})
            row = stats.get(provider.id, {"attempts": 0, "done": 0, "failed": 0, "amount": 0.0})
            finished = row["done"] + row["failed"]
            in_routing = provider in candidates
            bank_rows.append(
                {
                    "id": bank.id,
                    "code": bank.code,
                    "name": bank.name,
                    "psp": bank.psp_name,
                    "protocol": bank.protocol,
                    "color": bank.color or "#714B67",
                    "logo": f"/web/image/vesta.payment.bank/{bank.id}/image_128",
                    "state": bank.state,
                    "edition": bank.edition,
                    "configured": bank.is_configured,
                    "provider_id": provider.id,
                    "weight": max(provider.vesta_routing_weight, 0) if provider else 0,
                    "batch": provider.vesta_routing_batch if provider else 1,
                    "count_limit": provider.vesta_daily_count_limit if provider else 0,
                    "amount_limit": provider.vesta_daily_amount_limit if provider else 0,
                    "today_attempts": row_today["attempts"],
                    "today_done": row_today["done"],
                    "today_amount": row_today["amount"],
                    "attempts": row["attempts"],
                    "done": row["done"],
                    "failed": row["failed"],
                    "amount": row["amount"],
                    "pending": pending.get(provider, 0),
                    "success_rate": round(100 * row["done"] / finished) if finished else None,
                    "target_share": targets.get(provider.id),
                    "actual_share": round(100 * row_today["attempts"] / total_today) if total_today and provider else 0,
                    "in_routing": in_routing,
                    "blocked": provider and Router._blocked_reason(provider, row_today) or False,
                    "paused_until": provider.vesta_paused_until
                    and fields.Datetime.to_string(provider.vesta_paused_until),
                    "failure_streak": provider.vesta_failure_streak if provider else 0,
                    "check_ok": bank.check_ok,
                    "check_message": bank.check_message or "",
                    "is_next": bool(provider) and provider == next_provider,
                    "window_done": window.get(provider.id, [0, 0])[0],
                    "window_failed": window.get(provider.id, [0, 0])[1],
                    "window_rate": self._rate(window.get(provider.id, [0, 0])),
                    "fallback": self._fallback_name(provider, candidates)
                    if provider and provider not in candidates
                    else "",
                }
            )

        totals = {key: sum(stats[p.id][key] for p in providers) for key in ("attempts", "done", "failed", "amount")}
        finished = totals["done"] + totals["failed"]
        return {
            "company": company.name,
            "period": period,
            "mode": mode,
            "show_all": company.vesta_routing_show_all,
            "modes": [{"key": key, "label": label} for key, label in self._routing_mode_labels()],
            "kpis": {
                **totals,
                "pending": sum(pending.values()),
                "success_rate": round(100 * totals["done"] / finished) if finished else None,
                "live_banks": len(providers.filtered(lambda p: p.is_published and p.is_live)),
                "test_banks": len(providers.filtered(lambda p: p.is_published and not p.is_live)),
            },
            "banks": bank_rows,
            "preview": [{"code": p.code, "provider_id": p.id} for p in upcoming],
            "timeline": self._control_center_timeline(providers, days),
            "can_edit": self.env.user.has_group("base.group_system"),
            "monitoring": {
                "alert_rate": company.vesta_alert_failure_rate,
                "window": company.vesta_alert_window,
                "min_payments": company.vesta_alert_min_payments,
                "min_success": company.vesta_route_min_success,
                "uptime": company.vesta_uptime_check,
            },
            "events": self._control_center_events(),
        }

    @api.model
    def _target_shares(self, candidates, mode):
        """Return the share of the payments each candidate should take in the routing mode, in %."""
        if not candidates or mode == "customer":
            return {}
        if mode == "priority":
            return {p.id: 100 if p == candidates[:1] else 0 for p in candidates}
        if mode == "rotation":
            sizes = {p.id: max(p.vesta_routing_batch, 1) for p in candidates}
        else:
            sizes = {p.id: max(p.vesta_routing_weight, 0) for p in candidates}
            if not any(sizes.values()):  # Every weight is zero: the banks share equally
                sizes = dict.fromkeys(sizes, 1)
        total = sum(sizes.values())
        return {provider_id: round(100 * size / total) for provider_id, size in sizes.items()}

    @staticmethod
    def _rate(done_failed):
        done, failed = done_failed
        return round(100 * done / (done + failed)) if done + failed else None

    def _fallback_name(self, provider, candidates):
        """Return the bank that takes the payments of a skipped bank."""
        following = candidates.filtered(lambda p: (p.sequence, p.id) > (provider.sequence, provider.id))
        return (following or candidates)[:1].name or ""

    @api.model
    def _control_center_events(self, limit=12):
        Event = self.env["vesta.payment.event"]
        domain = Domain("company_id", "in", self.env.companies.ids)
        open_domain = domain & Domain("resolved", "=", False)
        counts = dict(Event._read_group(open_domain, groupby=["level"], aggregates=["__count"]))
        level_labels = dict(Event._fields["level"]._description_selection(self.env))
        category_labels = dict(Event._fields["category"]._description_selection(self.env))
        rows = []
        for event in Event.search(open_domain, limit=limit):
            rows.append(
                {
                    "id": event.id,
                    "name": event.name,
                    "level": event.level,
                    "level_label": level_labels[event.level],
                    "category": category_labels.get(event.category, event.category),
                    "code": event.code or "",
                    "advice": event.advice or "",
                    "bank": event.provider_id.name or "",
                    "bank_id": event.provider_id.id,
                    "occurrences": event.occurrences,
                    "last_seen": fields.Datetime.to_string(event.last_seen),
                }
            )
        return {
            "rows": rows,
            "critical": counts.get("critical", 0),
            "error": counts.get("error", 0),
            "warning": counts.get("warning", 0),
        }

    def _control_center_banks(self):
        """Return the banks of the catalog in the order customers see them."""
        banks = self.search([])
        return banks.sorted(
            lambda b: (not b.provider_id, b.provider_id.sequence if b.provider_id else b.sequence, b.sequence)
        )

    def _routing_mode_labels(self):
        return self.env["res.company"]._fields["vesta_routing_mode"]._description_selection(self.env)

    @api.model
    def _control_center_timeline(self, providers, days):
        """Return the payments per bank and per hour (today) or per day (week, month)."""
        Router = self.env["vesta.payment.router"]
        granularity = "hour" if not days else "day"
        groups = (
            self.env["payment.transaction"]
            .sudo()
            .with_context(tz=const.BANK_TIMEZONE)
            ._read_group(
                Domain("provider_id", "in", providers.ids)
                & Domain("operation", "in", ("online_redirect", "online_direct", "online_token"))
                & Domain("create_date", ">=", Router._day_start(days)),
                groupby=[f"create_date:{granularity}", "provider_id"],
                aggregates=["__count"],
            )
        )
        buckets = {}
        for bucket, provider, count in groups:
            label = bucket.strftime("%H:00") if granularity == "hour" else bucket.strftime("%m-%d")
            buckets.setdefault(label, {})[provider.code] = count
        return [{"label": label, "counts": counts} for label, counts in sorted(buckets.items())]

    # === ACTIONS === #

    def _check_manager(self):
        if not self.env.user.has_group("base.group_system"):
            raise AccessError(self.env._("Only administrators can change the bank gateways."))

    @api.model
    def set_monitoring(self, values):
        """Change the alert thresholds and the automatic failover of the current company."""
        self._check_manager()
        fields_map = {
            "alert_rate": "vesta_alert_failure_rate",
            "window": "vesta_alert_window",
            "min_payments": "vesta_alert_min_payments",
            "min_success": "vesta_route_min_success",
        }
        updates = {
            fields_map[key]: min(max(int(value or 0), 0), 100000) for key, value in values.items() if key in fields_map
        }
        for key in ("alert_rate", "min_success"):
            if fields_map[key] in updates:
                updates[fields_map[key]] = min(updates[fields_map[key]], 100)
        if "uptime" in values:
            updates["vesta_uptime_check"] = bool(values["uptime"])
        self.env.company.write(updates)
        return True

    @api.model
    def resolve_events(self, event_ids=None):
        """Mark problems as resolved; all open problems of the company when no id is given."""
        self._check_manager()
        Event = self.env["vesta.payment.event"]
        events = (
            Event.browse(event_ids)
            if event_ids
            else Event.search(Domain("company_id", "in", self.env.companies.ids) & Domain("resolved", "=", False))
        )
        events.action_resolve()
        return True

    @api.model
    def set_routing(self, mode, show_all=False):
        """Change the routing mode of the current company."""
        self._check_manager()
        if mode not in dict(const.ROUTING_MODES):
            raise UserError(self.env._("Unknown routing mode: %s", mode))
        self.env.company.write({"vesta_routing_mode": mode, "vesta_routing_show_all": bool(show_all)})
        return True

    def update_bank(self, values):
        """Change the routing settings of a bank (weight, batch, daily limits)."""
        self.ensure_one()
        self._check_manager()
        provider = self._ensure_provider()
        provider.write(
            {BANK_FIELDS[key]: max(int(value or 0), 0) for key, value in values.items() if key in BANK_FIELDS}
        )
        return True

    def move_bank(self, direction):
        """Move a bank up or down in the order of the checkout page and of the routing."""
        self.ensure_one()
        self._check_manager()
        banks = list(self._control_center_banks())
        index = banks.index(self)
        target = index - 1 if direction == "up" else index + 1
        if 0 <= target < len(banks):
            banks[index], banks[target] = banks[target], banks[index]
        for position, bank in enumerate(banks, start=1):
            bank.sequence = position * 10
            if bank.provider_id:
                bank.provider_id.sequence = position * 10
        return True

    def run_bank_action(self, action):
        """Run a dashboard action on a bank and return a notification for the control center.

        :param str action: "live", "test", "disable", "test_connection" or "resume".
        :return: {"type": ..., "title": ..., "message": ...}
        :rtype: dict
        """
        self.ensure_one()
        self._check_manager()
        provider = self._ensure_provider()
        methods = {
            "live": provider.action_vesta_set_live,
            "test": provider.action_vesta_set_test,
            "disable": provider.action_vesta_disable,
            "test_connection": provider.action_vesta_test_connection,
            "resume": provider.action_vesta_resume,
        }
        if action not in methods:
            raise UserError(self.env._("Unknown action: %s", action))
        result = methods[action]()
        params = (result or {}).get("params", {})
        return {
            "type": params.get("type", "success"),
            "title": params.get("title", ""),
            "message": params.get("message") or self.env._("%s is back in the routing.", self.name),
        }
