# -*- coding: utf-8 -*-

from odoo import models, fields, _, api
from odoo import tools

class AutoTransporte(models.Model):
    _name = 'cp.autotransporte'
    _description = 'Autotransporte'
    _rec_name = "descripcion"

    name = fields.Char("Name", required=True, copy=False, readonly=True, index=True, default=lambda self: _('New'))

    descripcion = fields.Char(string=_('Nombre del vehículo'))
    confvehicular = fields.Many2one('cve.conf.autotransporte',string='Configuración vehículo')
    placavm = fields.Char(string=_('Placa del vehículo'))
    aniomodelo = fields.Char(string=_('Año del vehículo'))

    nombreaseg = fields.Char(string=_('Nombre de la aseguradora'))
    numpoliza = fields.Char(string=_('Número de póliza'))

    company_id = fields.Many2one('res.company', 'Company', required=True, index=True, default=lambda self: self.env.company)

    @api.model
    def init(self):
        company_id = self.env['res.company'].search([])
        for company in company_id:
            dias_feriados_sequence = self.env['ir.sequence'].search([('code', '=', 'ccp.autotransporte'), ('company_id', '=', company.id)])
            if not dias_feriados_sequence:
                dias_feriados_sequence.create({
                        'name': 'Autotransporte',
                        'code': 'ccp.autotransporte',
                        'padding': 4,
                        'company_id': company.id,
                    })

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            if 'company_id' in vals:
                vals['name'] = self.env['ir.sequence'].with_context(force_company=vals['company_id']).next_by_code('ccp.autotransporte') or _('New')
            else:
                vals['name'] = self.env['ir.sequence'].next_by_code('ccp.autotransporte') or _('New')
        result = super(AutoTransporte, self).create(vals)
        return result
