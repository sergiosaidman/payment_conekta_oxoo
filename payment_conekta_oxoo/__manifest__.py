# -*- coding: utf-8 -*-
{
    'name': "Conekta Payment Acquirer",
    'summary': """Payment Acquirer: Conekta / OXOO Cash Payment""",

    'description': """
Conekta payment gatway, online payment, card payment, cash payment, oxoo payment, connector payment, payments in Mexico,payment connector, Pagos con OXXO PAY,integrate Conekta
Conekta’s payment,Oxoo store, payment solution, OXXO PAY cash payments, accept payments, accept payment online,sync payment,conekta payment gateway integration, Conekta Offline Payments
Conekta payments: OXXO, SPEI, Credit and Debit cards, Configuración de Conekta, Websites using Conekta, conekta_payments, Corredor de pago conekta,Conekta – Solução em Integração
Conekta Payment Acquirer, konekta, conecta, konecta, konekta
This module depends on External dependensies of Conekta. To install this dependency run on you system
pip3 install conekta
    """,
    'author': "Nilesh Sheliya",
    "live_test_url": "https://odoo.sheliyainfotech.com/contactus?description=demo:payment_conekta_oxoo&odoo_version=13.0",
    'category': 'Accounting',
    'version': '13.0.2.2',
    'depends': ['payment','website_sale'],
    'external_dependencies' : {"python": ["conekta"]},
    "price": 189.00,
    "currency": "EUR",
    "website": "https://apps.odoo.com/apps/modules/13.0/payment_conekta_oxoo/",
    'data': [
        'views/payment_views.xml',
        'views/assets.xml',
        'report/transaction_report.xml',
        'report/transaction_report_template.xml',
        'views/payment_conekta_templates.xml',
        'data/payment_acquirer_data.xml',
        'views/payment_portal_templates.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        
    ],
    'images': ['static/description/icon.jpg'],
    'license': 'OPL-1',
    'support': 'sheliyanilesh@gmail.com',
    'installable': True,
    "auto_install": False,
    "application": True,
    'post_init_hook': 'create_missing_journal_for_conekta_acquirers',
}
