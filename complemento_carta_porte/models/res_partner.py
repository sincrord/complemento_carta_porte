# -*- coding: utf-8 -*-


from odoo import fields, models, api,_


class ResPartner(models.Model):
    _inherit = 'res.partner'

    cce_clave_colonia = fields.Many2one('catalogos.colonias', string='Clave Colonia')
    cce_clave_municipio = fields.Many2one('catalogos.municipio', string='Clave Municipio')
    cce_clave_estado = fields.Many2one('catalogos.estados', string='Clave Estado')
    cce_clave_pais = fields.Many2one('catalogos.paises', string='Clave de Pais')
    cce_calle = fields.Char(string=_('Calle'))
    cce_no_exterior = fields.Char(string=_('Numero exterior'))
    cce_no_interior = fields.Char(string=_('Numero interior'))
    cce_clave_localidad = fields.Many2one('catalogos.localidades', string='Clave Localidad')
    codigotransportista = fields.Many2one('cve.codigo.transporte.aereo',string='Código transportista')
    cce_licencia = fields.Char(string=_('No. licencia'))
