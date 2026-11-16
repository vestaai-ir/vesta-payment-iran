# Copyright 2026 Vesta AI (https://vestaai.ir)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
{
    "name": "Vesta Gateway",
    "summary": "Iranian bank payment gateways: one dashboard to install, test, enable and monitor"
    " Mellat, Saman, Melli (Sadad), Pasargad and Parsian",
    "version": "20.0.1.2.0",
    "category": "Accounting/Payment Providers",
    "website": "https://github.com/vestaai-ir/vesta-payment-iran",
    "author": "Vesta AI",
    "license": "LGPL-3",
    "application": True,
    "installable": True,
    "depends": ["payment"],
    "data": [
        "security/ir.access.csv",
        "data/vesta_payment_bank_data.xml",
        "data/ir_cron_data.xml",
        "views/payment_provider_views.xml",
        "views/payment_transaction_views.xml",
        "views/vesta_payment_bank_views.xml",
        "views/payment_provider_routing_views.xml",
        "views/vesta_payment_event_views.xml",
        "views/vesta_payment_menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "vesta_payment/static/src/control_center/*",
        ],
    },
    "images": ["static/description/banner.png"],
}
