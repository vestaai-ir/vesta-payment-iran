# Copyright 2026 Vesta AI (https://vestaai.ir)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import api, fields, models
from odoo.addons.vesta_payment import const
from odoo.exceptions import UserError
from odoo.fields import Domain


class VestaPaymentBank(models.Model):
    _name = "vesta.payment.bank"
    _description = "Iranian Bank Gateway"
    _order = "sequence, id"

    name = fields.Char(string="Bank", required=True, translate=True)
    code = fields.Char(string="Provider Code", required=True, help="Technical code of the payment provider.")
    module_name = fields.Char(string="Technical Module", required=True)
    sequence = fields.Integer(default=10)
    image_128 = fields.Image(string="Logo", max_width=128, max_height=128)
    color = fields.Char(string="Brand Color")
    psp_name = fields.Char(string="Payment Switch", translate=True)
    protocol = fields.Char(string="API")
    edition = fields.Selection(
        string="Edition",
        selection=[("community", "Open Source"), ("pro", "Pro")],
        default="pro",
        required=True,
    )
    description = fields.Text(translate=True)
    sandbox_note = fields.Text(string="Test Mode Notes", translate=True)

    module_id = fields.Many2one(comodel_name="ir.module.module", compute="_compute_module_id")
    module_state = fields.Selection(
        string="Module State",
        selection=[
            ("missing", "Not Available"),
            ("uninstalled", "Not Installed"),
            ("installed", "Installed"),
            ("to upgrade", "To Upgrade"),
            ("to remove", "To Remove"),
            ("to install", "To Install"),
            ("uninstallable", "Not Installable"),
        ],
        compute="_compute_module_id",
    )
    provider_id = fields.Many2one(
        string="Payment Provider", comodel_name="payment.provider", compute="_compute_provider_id"
    )
    state = fields.Selection(
        string="Status",
        selection=[
            ("missing", "Get Pro"),
            ("uninstalled", "Not Installed"),
            ("disabled", "Disabled"),
            ("test", "Test Mode"),
            ("live", "Live"),
        ],
        compute="_compute_provider_id",
    )
    is_configured = fields.Boolean(compute="_compute_provider_id")
    check_ok = fields.Boolean(compute="_compute_provider_id")
    check_message = fields.Char(compute="_compute_provider_id")
    check_date = fields.Datetime(compute="_compute_provider_id")
    transaction_count = fields.Integer(string="Payments (30 days)", compute="_compute_statistics")
    amount_total = fields.Monetary(string="Collected (30 days)", compute="_compute_statistics")
    failure_count = fields.Integer(string="Failed (30 days)", compute="_compute_statistics")
    pending_count = fields.Integer(string="Awaiting Bank", compute="_compute_statistics")
    currency_id = fields.Many2one(comodel_name="res.currency", compute="_compute_statistics")

    _code_uniq = models.Constraint("UNIQUE(code)", "Each bank can only be listed once.")

    # === COMPUTE METHODS === #

    def _compute_module_id(self):
        modules = self.env["ir.module.module"].sudo().search(Domain("name", "in", self.mapped("module_name")))
        by_name = {module.name: module for module in modules}
        for bank in self:
            module = by_name.get(bank.module_name, self.env["ir.module.module"])
            bank.module_id = module
            bank.module_state = module.state if module else "missing"

    @api.depends_context("company")
    def _compute_provider_id(self):
        providers = self.env["payment.provider"].search(
            Domain("code", "in", self.mapped("code"))
            & Domain("company_id", "in", (self.env.company | self.env.company.parent_ids).ids)
        )
        for bank in self:
            provider = providers.filtered(lambda p, b=bank: p.code == b.code)[:1]
            bank.provider_id = provider
            if bank.module_state == "missing":
                bank.state = "missing"
            elif bank.module_state != "installed" or not provider:
                bank.state = "uninstalled"
            elif not provider.is_published:
                bank.state = "disabled"
            else:
                bank.state = "live" if provider.is_live else "test"
            bank.is_configured = bool(provider) and bank._is_provider_configured(provider)
            bank.check_ok = provider.vesta_check_ok
            bank.check_message = provider.vesta_check_message
            bank.check_date = provider.vesta_check_date

    def _is_provider_configured(self, provider):
        """Check that every credential required in live mode is filled in."""
        required = [
            name
            for name, field in provider._fields.items()
            if getattr(field, "required_if_provider", None) == provider.code
        ]
        return all(provider.sudo()[name] for name in required)

    @api.depends_context("company")
    def _compute_statistics(self):
        since = fields.Datetime.subtract(fields.Datetime.now(), days=30)
        Transaction = self.env["payment.transaction"]
        provider_ids = self.provider_id.ids
        done_groups = Transaction._read_group(
            Domain("provider_id", "in", provider_ids)
            & Domain("state", "=", "done")
            & Domain("operation", "!=", "refund")
            & Domain("create_date", ">=", since),
            groupby=["provider_id", "currency_id"],
            aggregates=["__count", "amount:sum"],
        )
        failed_groups = Transaction._read_group(
            Domain("provider_id", "in", provider_ids)
            & Domain("state", "in", ("error", "cancel"))
            & Domain("create_date", ">=", since),
            groupby=["provider_id"],
            aggregates=["__count"],
        )
        pending_groups = Transaction._read_group(
            Domain("provider_id", "in", provider_ids) & Domain("vesta_verify_state", "=", "pending"),
            groupby=["provider_id"],
            aggregates=["__count"],
        )
        done = {}
        for provider, currency, count, amount in done_groups:  # Totals in Rials, Toman included
            total_count, total_amount = done.get(provider.id, (0, 0.0))
            done[provider.id] = (
                total_count + count,
                total_amount + amount * const.RIALS_PER_UNIT.get(currency.name, 1),
            )
        failed = {provider.id: count for provider, count in failed_groups}
        pending = {provider.id: count for provider, count in pending_groups}
        currency = self.env.ref("base.IRR", raise_if_not_found=False) or self.env.company.currency_id
        for bank in self:
            count, amount = done.get(bank.provider_id.id, (0, 0.0))
            bank.transaction_count = count
            bank.amount_total = amount
            bank.failure_count = failed.get(bank.provider_id.id, 0)
            bank.pending_count = pending.get(bank.provider_id.id, 0)
            bank.currency_id = currency

    # === ACTION METHODS === #

    def action_install(self):
        self.ensure_one()
        if not self.module_id:
            raise UserError(
                self.env._(
                    "The module %(module)s is not in the addons path. %(bank)s is part of Vesta"
                    " Gateway Pro: copy its folder next to vesta_payment, restart Odoo and update the"
                    " apps list.",
                    module=self.module_name,
                    bank=self.name,
                )
            )
        return self.module_id.button_immediate_install()

    def action_open_provider(self):
        self.ensure_one()
        self._ensure_provider()
        return {
            "type": "ir.actions.act_window",
            "res_model": "payment.provider",
            "res_id": self.provider_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_set_live(self):
        return self._ensure_provider().action_vesta_set_live()

    def action_set_test(self):
        return self._ensure_provider().action_vesta_set_test()

    def action_disable(self):
        return self._ensure_provider().action_vesta_disable()

    def action_test_connection(self):
        return self._ensure_provider().action_vesta_test_connection()

    def action_view_transactions(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("vesta_payment.action_vesta_payment_transaction")
        action["domain"] = [("provider_id", "=", self._ensure_provider().id)]
        action["context"] = {"create": False}
        return action

    def _ensure_provider(self):
        self.ensure_one()
        if not self.provider_id:
            raise UserError(self.env._("Install %s first.", self.name))
        return self.provider_id
