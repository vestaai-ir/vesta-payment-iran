# Copyright 2026 Vesta AI (https://vestaai.ir)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import models


class PaymentMethod(models.Model):
    _inherit = "payment.method"

    def _sort_by_display_order(self):
        """Override of `payment` to list the bank chosen by the automatic routing first."""
        payment_methods = super()._sort_by_display_order()
        routed_provider_id = self.env.context.get("vesta_routed_provider_id")
        if not routed_provider_id:
            return payment_methods
        return payment_methods.sorted(lambda pm: pm.provider_id.id != routed_provider_id)
