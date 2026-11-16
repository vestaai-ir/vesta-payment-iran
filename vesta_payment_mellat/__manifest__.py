# Copyright 2026 Vesta AI (https://vestaai.ir)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
{
    "name": "Vesta Gateway: Bank Mellat",
    "summary": "Bank Mellat (Behpardakht) payment gateway for Odoo: pay, verify and settle over REST or SOAP",
    "version": "20.0.1.1.0",
    "category": "Accounting/Payment Providers",
    "website": "https://github.com/vestaai-ir/vesta-payment-iran",
    "author": "Vesta AI",
    "license": "LGPL-3",
    "installable": True,
    "depends": ["vesta_payment"],
    "data": [
        "data/payment_provider_data.xml",
        "views/payment_provider_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
}
