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
    vesta_routing_show_all = fields.Boolean(
        string="Offer Other Banks",
        help="With automatic routing, still list the other banks under the chosen one.",
    )
