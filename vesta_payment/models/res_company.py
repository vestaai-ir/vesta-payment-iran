# Copyright 2026 Vesta AI (https://vestaai.ir)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models
from odoo.addons.vesta_payment import const


class ResCompany(models.Model):
    _inherit = "res.company"

    vesta_routing_mode = fields.Selection(
        string="Bank Routing",
        selection=const.ROUTING_MODES,
        default="customer",
        required=True,
        help="Customer choice: every live bank is listed and the customer picks one.\n"
        "Weighted distribution: each payment goes to the bank furthest below its share.\n"
        "Rotation: the banks take turns, each for its batch of consecutive payments.\n"
        "Priority with failover: the first available bank in the order takes every payment.",
    )
    vesta_route_min_success = fields.Integer(
        string="Minimum Success Rate (%)",
        default=0,
        help="Routing skips a bank whose success rate over the alert window falls below this"
        " percentage, and sends the payments to the next bank. 0 disables the check.",
    )
    vesta_uptime_check = fields.Boolean(
        string="Uptime Probes",
        help="Every 10 minutes, ask each published bank for a payment token that is never used. A bank"
        " that doesn't answer three times in a row is paused in routing until it answers again.",
    )
    vesta_alert_failure_rate = fields.Integer(
        string="Alert Above Failure Rate (%)",
        default=30,
        help="Log a critical alert when this share of a bank's payments failed in the alert window. 0 disables alerts.",
    )
    vesta_alert_window = fields.Integer(
        string="Alert Window (minutes)", default=60, help="Period over which failure and success rates are measured."
    )
    vesta_alert_min_payments = fields.Integer(
        string="Alert Minimum Payments",
        default=10,
        help="Rates are only judged once a bank handled this many payments in the window.",
    )
    vesta_routing_show_all = fields.Boolean(
        string="Offer Other Banks",
        help="With automatic routing, still list the other banks under the chosen one.",
    )
