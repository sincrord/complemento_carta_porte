# -*- coding: utf-8 -*-

from odoo import models, fields, api

class CveClaveProdStcc(models.Model):
    _name = 'cve.clave.prod.stcc'
    _rec_name = "descripcion"

    clave = fields.Char(string='Clave')
    descripcion = fields.Char(string='Descripción')