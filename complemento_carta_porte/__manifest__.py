# -*- coding: utf-8 -*-
##############################################################################
#                 @author IT Admin
#
##############################################################################

{
    'name': 'Complemento Carta porte',
    'version': '14.03',
    'description': ''' Agrega campos para generar CFDI de tipo ingreso con el complemento de carta porte.
    ''',
    'category': 'Accounting',
    'author': 'IT Admin',
    'website': 'www.itadmin.com.mx',
    'depends': [
        'account', 'cdfi_invoice', 'catalogos_cfdi', 'stock'
    ],
    'data': [
        'security/ir.model.access.csv',
        'report/invoice_report.xml',
        'views/account_invoice_view.xml',
        'views/product_view.xml',
        'data/ir_sequence_data.xml',
        'views/res_partner_view.xml',
        'views/autotransporte_view.xml',
	],
    'application': False,
    'installable': True,
}
