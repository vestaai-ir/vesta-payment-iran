# Copyright 2026 Vesta AI (https://vestaai.ir)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from datetime import timedelta

from odoo import fields
from odoo.addons.payment.tests.common import PaymentCommon
from odoo.tests import tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestVestaRouting(PaymentCommon):
    """The routing algorithm, on generic providers standing for three banks."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Router = cls.env["vesta.payment.router"]
        cls.bank_a = cls.dummy_provider
        cls.bank_b = cls.dummy_provider.copy({"name": "Bank B", "sequence": 2})
        cls.bank_c = cls.dummy_provider.copy({"name": "Bank C", "sequence": 3})
        cls.bank_a.sequence = 1
        cls.banks = cls.bank_a | cls.bank_b | cls.bank_c

    def _usage(self, a=0, b=0, c=0):
        return {
            bank.id: {"attempts": attempts, "done": 0, "failed": 0, "amount": 0.0}
            for bank, attempts in zip(self.banks, (a, b, c), strict=True)
        }

    def _simulate(self, mode, count, usage=None):
        usage = usage or self._usage()
        picks = []
        for _i in range(count):
            chosen = self.Router._pick(self.Router._candidates(self.banks, usage), usage, mode)
            picks.append(chosen)
            usage[chosen.id]["attempts"] += 1
        return picks

    def test_weighted_follows_weights(self):
        self.bank_a.vesta_routing_weight, self.bank_b.vesta_routing_weight, self.bank_c.vesta_routing_weight = (
            60,
            30,
            10,
        )
        picks = self._simulate("weighted", 100)
        self.assertEqual([picks.count(bank) for bank in self.banks], [60, 30, 10])
        # Smooth: in any 10 consecutive payments, the first bank takes about 6
        self.assertIn(picks[:10].count(self.bank_a), (5, 6, 7))

    def test_weighted_catches_up(self):
        """A bank that took too little today goes first until it reaches its share."""
        self.banks.vesta_routing_weight = 10
        picks = self._simulate("weighted", 3, usage=self._usage(a=10, b=10, c=0))
        self.assertEqual(picks, [self.bank_c] * 3)

    def test_zero_weights_share_equally(self):
        self.banks.vesta_routing_weight = 0
        picks = self._simulate("weighted", 9)
        self.assertEqual([picks.count(bank) for bank in self.banks], [3, 3, 3])

    def test_rotation_batches(self):
        self.bank_a.vesta_routing_batch, self.bank_b.vesta_routing_batch, self.bank_c.vesta_routing_batch = 3, 1, 2
        picks = self._simulate("rotation", 12)
        a, b, c = self.bank_a, self.bank_b, self.bank_c
        self.assertEqual(picks, [a, a, a, b, c, c, a, a, a, b, c, c])

    def test_priority_and_failover(self):
        self.assertEqual(self._simulate("priority", 3), [self.bank_a] * 3)
        self.bank_a.vesta_paused_until = fields.Datetime.now() + timedelta(minutes=5)
        self.assertEqual(self._simulate("priority", 2), [self.bank_b] * 2, "A paused bank is skipped")

    def test_daily_limits(self):
        usage = self._usage()
        usage[self.bank_a.id].update(done=5, amount=2_000_000)
        self.bank_a.vesta_daily_count_limit = 5
        self.assertEqual(self.Router._blocked_reason(self.bank_a, usage[self.bank_a.id]), "count_limit")
        self.bank_a.vesta_daily_count_limit = 0
        self.bank_a.vesta_daily_amount_limit = 1_000_000
        self.assertEqual(self.Router._blocked_reason(self.bank_a, usage[self.bank_a.id]), "amount_limit")
        self.assertNotIn(self.bank_a, self.Router._candidates(self.banks, usage))

    def test_every_bank_blocked_falls_back_to_all(self):
        self.banks.vesta_paused_until = fields.Datetime.now() + timedelta(minutes=5)
        self.assertEqual(self.Router._candidates(self.banks, self._usage()), self.banks)

    @mute_logger("odoo.addons.vesta_payment.models.payment_provider")
    def test_health_pauses_after_failures(self):
        for _i in range(2):
            self.bank_b._vesta_register_failure()
        self.assertFalse(self.bank_b.vesta_paused_until)
        self.bank_b._vesta_register_failure()
        self.assertTrue(self.bank_b.vesta_paused_until > fields.Datetime.now())
        self.bank_b._vesta_register_success()
        self.assertFalse(self.bank_b.vesta_paused_until)
        self.assertEqual(self.bank_b.vesta_failure_streak, 0)

    def test_target_shares(self):
        Bank = self.env["vesta.payment.bank"]
        self.bank_a.vesta_routing_weight, self.bank_b.vesta_routing_weight, self.bank_c.vesta_routing_weight = (
            50,
            30,
            20,
        )
        self.assertEqual(
            Bank._target_shares(self.banks, "weighted"),
            {self.bank_a.id: 50, self.bank_b.id: 30, self.bank_c.id: 20},
        )
        self.assertEqual(Bank._target_shares(self.banks, "priority")[self.bank_a.id], 100)
        self.assertEqual(Bank._target_shares(self.banks, "customer"), {})

    def test_usage_counts_today_only(self):
        tx = self._create_transaction("redirect", provider_id=self.bank_b.id, reference="R-1")
        self.assertEqual(self.Router._usage(self.banks)[self.bank_b.id]["attempts"], 1)
        self._update_transaction(tx, state="done")
        self.env.cr.execute(
            "UPDATE payment_transaction SET create_date = %s WHERE id = %s",
            [fields.Datetime.now() - timedelta(days=2), tx.id],
        )
        self.env.invalidate_all()
        self.assertEqual(self.Router._usage(self.banks)[self.bank_b.id]["attempts"], 0)
        week = self.Router._usage(self.banks, self.Router._day_start(6))[self.bank_b.id]
        self.assertEqual((week["attempts"], week["done"]), (1, 1))

    def _payments(self, bank, done=0, failed=0):
        for index in range(done + failed):
            tx = self._create_transaction("redirect", provider_id=bank.id, reference=f"{bank.name}-{index}")
            self._update_transaction(tx, state="done" if index < done else "error")

    def test_low_success_rate_fails_over(self):
        """A bank below the minimum success rate is skipped; the next bank takes its payments."""
        self.company.write({"vesta_route_min_success": 60, "vesta_alert_min_payments": 4, "vesta_alert_window": 60})
        self._payments(self.bank_a, done=1, failed=3)
        self._payments(self.bank_b, done=4)
        usage = self.Router._add_health(self.banks, self.Router._usage(self.banks), self.company)
        self.assertEqual(self.Router._blocked_reason(self.bank_a, usage[self.bank_a.id]), "low_success")
        self.assertEqual(self.Router._pick(self.Router._candidates(self.banks, usage), usage, "priority"), self.bank_b)

    def test_too_few_payments_are_not_judged(self):
        self.company.write({"vesta_route_min_success": 60, "vesta_alert_min_payments": 10})
        self._payments(self.bank_a, failed=3)
        usage = self.Router._add_health(self.banks, self.Router._usage(self.banks), self.company)
        self.assertFalse(self.Router._blocked_reason(self.bank_a, usage[self.bank_a.id]))


@tagged("post_install", "-at_install")
class TestVestaLog(PaymentCommon):
    def test_log_diagnoses_and_groups(self):
        Event = self.env["vesta.payment.event"]
        first = Event._log(
            "payment_request", "Bank refused the payment: Invalid server IP (421)", provider=self.provider
        )
        second = Event._log(
            "payment_request", "Bank refused the payment: Invalid server IP (421)", provider=self.provider
        )
        self.assertEqual(first, second, "The same open problem is grouped")
        self.assertEqual(first.occurrences, 2)
        self.assertEqual((first.category, first.code), ("ip", "421"))
        self.assertIn("IP", first.advice)
        first.action_resolve()
        third = Event._log(
            "payment_request", "Bank refused the payment: Invalid server IP (421)", provider=self.provider
        )
        self.assertNotEqual(third, first, "A resolved problem that comes back is a new entry")

    def test_unknown_code_keeps_category_advice(self):
        event = self.env["vesta.payment.event"]._log("double_spend", "Receipt reused", level="critical")
        self.assertEqual(event.category, "double_spend")
        self.assertTrue(event.advice)
