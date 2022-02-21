# -*- coding: utf-8 -*-

import base64
import json
import requests
import datetime
from lxml import etree

from odoo import fields, models, api,_
import odoo.addons.decimal_precision as dp
from odoo.exceptions import UserError, Warning
from odoo.tools import float_is_zero, float_compare
from reportlab.graphics.barcode import createBarcodeDrawing, getCodes
from reportlab.lib.units import mm
import pytz

import logging
_logger = logging.getLogger(__name__)

class CfdiTrasladoLine(models.Model):
    _name = "cp.traslado.line"
    
    cfdi_traslado_id= fields.Many2one('account.move',string="CFDI Traslado")
    product_id = fields.Many2one('product.product',string='Producto',required=True)
    name = fields.Text(string='Descripción',required=True,)
    quantity = fields.Float(string='Cantidad', digits=dp.get_precision('Unidad de medida del producto'),required=True, default=1)
    price_unit = fields.Float(string='Precio unitario', required=True, digits=dp.get_precision('Product Price'))
    invoice_line_tax_ids = fields.Many2many('account.tax',string='Taxes')
    currency_id = fields.Many2one('res.currency', related='cfdi_traslado_id.currency_id', store=True, related_sudo=False, readonly=False)
    price_subtotal = fields.Monetary(string='Subtotal',
        store=True, readonly=True, compute='_compute_price', help="Subtotal")
    price_total = fields.Monetary(string='Cantidad (con Impuestos)',
        store=True, readonly=True, compute='_compute_price', help="Cantidad total con impuestos")
    pesoenkg = fields.Float(string='Peso Kg', digits=dp.get_precision('Product Price'))
    pedimento = fields.Many2many('stock.production.lot', string='Pedimentos', copy=False)
    guiaid_numero = fields.Char(string=_('No. Guia'))
    guiaid_descrip = fields.Char(string=_('Descr. guia'))
    guiaid_peso = fields.Float(string='Peso guia')

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if not self.product_id:
            return
        self.name = self.product_id.partner_ref
        company_id = self.env.user.company_id
        taxes = self.product_id.taxes_id.filtered(lambda r: r.company_id == company_id)
        self.invoice_line_tax_ids = fp_taxes = taxes
        fix_price = self.env['account.tax']._fix_tax_included_price
        self.price_unit = fix_price(self.product_id.lst_price, taxes, fp_taxes)
        self.pesoenkg = self.product_id.weight

    @api.depends('price_unit', 'invoice_line_tax_ids', 'quantity',
        'product_id', 'cfdi_traslado_id.partner_id', 'cfdi_traslado_id.currency_id',)
    def _compute_price(self):
        for line in self:
            currency = line.cfdi_traslado_id and line.cfdi_traslado_id.currency_id or None
            price = line.price_unit
            taxes = False
            if line.invoice_line_tax_ids:
                taxes = line.invoice_line_tax_ids.compute_all(price, currency, line.quantity, product=line.product_id, partner=line.cfdi_traslado_id.partner_id)
            line.price_subtotal = taxes['total_excluded'] if taxes else line.quantity * price
            line.price_total = taxes['total_included'] if taxes else line.price_subtotal

    @api.onchange('quantity')
    def _onchange_quantity(self):
        self.pesoenkg = self.product_id.weight * self.quantity

class CCPUbicacionesLine(models.Model):
    _name = "cp.ubicaciones.line"
    
    cfdi_traslado_id= fields.Many2one('account.move',string="CFDI Traslado")
    tipoubicacion = fields.Selection(
        selection=[('Origen', 'Origen'), 
                   ('Destino', 'Destino'),],
        string=_('Tipo Ubicación'),
    )
    contacto = fields.Many2one('res.partner',string="Remitente / Destinatario")
    numestacion = fields.Many2one('cve.estaciones',string='Número de estación')
    fecha = fields.Datetime(string=_('Fecha Salida / Llegada'))
    tipoestacion = fields.Many2one('cve.estacion',string='Tipo estación')
    distanciarecorrida = fields.Float(string='Distancia recorrida')
    tipo_transporte = fields.Selection(
        selection=[('01', 'Autotransporte'), 
                  # ('02', 'Marítimo'), 
                   ('03', 'Aereo'),
                   #('04', 'Ferroviario')
                  ],
        string=_('Tipo de transporte')
    )
    idubicacion = fields.Char(string=_('ID Ubicacion'))

class CCPRemolqueLine(models.Model):
    _name = "cp.remolques.line"

    cfdi_traslado_id= fields.Many2one('account.move',string="CFDI Traslado")
    subtipo_id = fields.Many2one('cve.remolque.semiremolque',string="Subtipo")
    placa = fields.Char(string=_('Placa'))

class CCPPropietariosLine(models.Model):
    _name = "cp.figura.line"

    cfdi_traslado_id= fields.Many2one('account.move',string="CFDI Traslado")
    figura_id = fields.Many2one('res.partner',string="Contacto")
    tipofigura = fields.Many2one('cve.figura.transporte',string="Tipo figura")
    partetransporte = fields.Many2many('cve.parte.transporte',string="Parte transporte")

class AccountMove(models.Model):
    _inherit = 'account.move'

    factura_line_ids = fields.One2many('cp.traslado.line', 'cfdi_traslado_id', string='CFDI Traslado Line', copy=True)
    tipo_transporte = fields.Selection(
        selection=[('01', 'Autotransporte'), 
                  # ('02', 'Marítimo'), 
                   ('03', 'Aereo'),
                  # ('04', 'Ferroviario')
                  ],
        string=_('Tipo de transporte'),required=True, default='01'
    )
    carta_porte = fields.Boolean('Agregar carta porte', default = False)

    ##### atributos CP 
    transpinternac = fields.Selection(
        selection=[('Sí', 'Si'), 
                   ('No', 'No'),],
        string=_('¿Es un transporte internacional?'),default='No',
    )
    entradasalidamerc = fields.Selection(
        selection=[('Entrada', 'Entrada'), 
                   ('Salida', 'Salida'),],
        string=_('¿Las mercancías ingresan o salen del territorio nacional?'),
    )
    viaentradasalida = fields.Many2one('cve.transporte',string='Vía de ingreso / salida')
    totaldistrec = fields.Float(string='Distancia recorrida')

    ##### ubicaciones CP
    ubicaciones_line_ids = fields.One2many('cp.ubicaciones.line', 'cfdi_traslado_id', string='Ubicaciones', copy=True)

    ##### mercancias CP
    pesobrutototal = fields.Float(string='Peso bruto total', compute='_compute_pesobruto')
    unidadpeso = fields.Many2one('cve.clave.unidad',string='Unidad peso')
    pesonetototal = fields.Float(string='Peso neto total')
    numerototalmercancias = fields.Float(string='Numero total de mercancías', compute='_compute_mercancia')
    cargoportasacion = fields.Float(string='Cargo por tasación')

    #transporte
    permisosct = fields.Many2one('cve.tipo.permiso',string='Permiso SCT')
    numpermisosct = fields.Char(string=_('Número de permiso SCT'))

    #autotransporte
    autotrasporte_ids = fields.Many2one('cp.autotransporte',string='Unidad')
    remolque_line_ids = fields.One2many('cp.remolques.line', 'cfdi_traslado_id', string='Remolque', copy=True)
    nombreaseg_merc = fields.Char(string=_('Nombre de la aseguradora'))
    numpoliza_merc = fields.Char(string=_('Número de póliza'))
    primaseguro_merc = fields.Float(string=_('Prima del seguro'))
    seguro_ambiente = fields.Char(string=_('Nombre aseguradora'))
    poliza_ambiente = fields.Char(string=_('Póliza no.'))

    ##### Aereo CP
    numeroguia = fields.Char(string=_('Número de guía'))
    lugarcontrato = fields.Char(string=_('Lugar de contrato'))
    matriculaaeronave = fields.Char(string=_('Matrícula Aeronave'))
    transportista_id = fields.Many2one('res.partner',string="Transportista")
    embarcador_id = fields.Many2one('res.partner',string="Embarcador")

    uuidcomercioext = fields.Char(string=_('UUID Comercio Exterior'))
    paisorigendestino = fields.Many2one('catalogos.paises', string='País Origen / Destino')

    # figura transporte
    figuratransporte_ids = fields.One2many('cp.figura.line', 'cfdi_traslado_id', string='Seguro mercancías', copy=True)

    @api.onchange('factura_line_ids')
    def _compute_pesobruto(self):
        for invoice in self:
           peso = 0
           if invoice.carta_porte:
              if invoice.factura_line_ids:
                  for line in invoice.factura_line_ids:
                     peso += line.pesoenkg
              invoice.pesobrutototal = peso
           else:
              invoice.pesobrutototal = peso

    @api.onchange('factura_line_ids')
    def _compute_mercancia(self):
        for invoice in self:
           cant = 0
           if invoice.carta_porte:
              if invoice.factura_line_ids:
                  for line in invoice.factura_line_ids:
                      cant += 1
              invoice.numerototalmercancias = cant
           else:
              invoice.numerototalmercancias = cant

    ################################################################################################################
    ###############################  Adicional de Complemento de traslado ##########################################
    ################################################################################################################
    @api.model
    def to_json(self):
        res = super(AccountMove,self).to_json()
        if self.carta_porte:
         self.totaldistrec = 0

         #cartaporte20 = []
         cp_ubicacion = []
         #cp_mercancias = []
         for ubicacion in self.ubicaciones_line_ids:

            #corregir hora
            timezone = self._context.get('tz')
            if not timezone:
               timezone = self.journal_id.tz or self.env.user.partner_id.tz or 'America/Mexico_City'
            local = pytz.timezone(timezone)
            local_dt_from = ubicacion.fecha.replace(tzinfo=pytz.UTC).astimezone(local)
            date_fecha = local_dt_from.strftime ("%Y-%m-%dT%H:%M:%S")
            self.totaldistrec += float(ubicacion.distanciarecorrida)
            _logger.info('totaldistrec %s', self.totaldistrec)

            cp_ubicacion.append({
                            'TipoUbicacion': ubicacion.tipoubicacion,
                          # 'IDUbicacion': ubicacion.origen_id,
                            'RFCRemitenteDestinatario': ubicacion.contacto.vat,
                            'NombreRemitenteDestinatario': ubicacion.contacto.name,
                            'NumRegIdTrib': ubicacion.contacto.registro_tributario,
                            'ResidenciaFiscal': ubicacion.contacto.residencia_fiscal,
                            'NumEstacion': self.tipo_transporte != '01' and ubicacion.numestacion.clave_identificacion or '',
                            'NombreEstacion': self.tipo_transporte != '01' and ubicacion.numestacion.descripcion or '',
                          # 'NavegacionTrafico': self.company_id.zip,
                            'FechaHoraSalidaLlegada': date_fecha,
                            'TipoEstacion': self.tipo_transporte != '01' and ubicacion.tipoestacion.c_estacion or '',
                            'DistanciaRecorrida': ubicacion.distanciarecorrida > 0 and ubicacion.distanciarecorrida or '',
                            'Domicilio': {
                                'Calle': ubicacion.contacto.cce_calle,
                                'NumeroExterior': ubicacion.contacto.cce_no_exterior,
                                'NumeroInterior': ubicacion.contacto.cce_no_interior,
                                'Colonia': ubicacion.contacto.cce_clave_colonia.c_colonia,
                                'Localidad': ubicacion.contacto.cce_clave_localidad.c_localidad,
                          #      'Referencia': self.company_id.cce_clave_estado.c_estado,
                                'Municipio': ubicacion.contacto.cce_clave_municipio.c_municipio,
                                'Estado': ubicacion.contacto.cce_clave_estado.c_estado,
                                'Pais': ubicacion.contacto.cce_clave_pais.c_pais,
                                'CodigoPostal': ubicacion.contacto.zip,
                            },
                         })

        #################  Atributos y Ubicacion ############################
   #     if self.tipo_transporte == '01' or self.tipo_transporte == '04':
         cartaporte20= {'TranspInternac': self.transpinternac,
                       'EntradaSalidaMerc': self.entradasalidamerc,
                       'ViaEntradaSalida': self.viaentradasalida.c_transporte,
                       'TotalDistRec': self.tipo_transporte == '01' and self.totaldistrec or '',
                       'PaisOrigenDestino': self.paisorigendestino.c_pais,
                      }
  #      else:
  #          res.update({
  #                   'cartaporte': {
  #                          'TranspInternac': self.transpinternac,
  #                          'EntradaSalidaMerc': self.entradasalidamerc,
  #                          'ViaEntradaSalida': self.viaentradasalida.c_transporte,
  #                          'TipoTransporte': self.tipo_transporte,
  #                   },
  #              })

         cartaporte20.update({'Ubicaciones': cp_ubicacion})

        #################  Mercancias ############################
         mercancias = { 
                       'PesoBrutoTotal': self.pesobrutototal, #solo si es aereo o ferroviario
                       'UnidadPeso': self.unidadpeso.clave,
                       'PesoNetoTotal': self.pesonetototal if self.pesonetototal > 0 else '',
                       'NumTotalMercancias': self.numerototalmercancias,
                       'CargoPorTasacion': self.cargoportasacion if self.cargoportasacion > 0 else '',
         }

         mercancia = []
         for line in self.factura_line_ids:
            if line.quantity <= 0:
                continue
            mercancia_atributos = {
                            'BienesTransp': line.product_id.clave_producto,
                            'ClaveSTCC': line.product_id.clavestcc.clave,
                            'Descripcion': self.clean_text(line.product_id.name),
                            'Cantidad': line.quantity,
                            'ClaveUnidad': line.product_id.cat_unidad_medida.clave,
                            'Unidad': line.product_id.cat_unidad_medida.descripcion,
                            'Dimensiones': line.product_id.dimensiones,
                            'MaterialPeligroso': line.product_id.materialpeligroso,
                            'CveMaterialPeligroso': line.product_id.clavematpeligroso.clave,
                            'Embalaje': line.product_id.embalaje and line.product_id.embalaje.clave or '',
                            'DescripEmbalaje': line.product_id.desc_embalaje and line.product_id.desc_embalaje or '',
                            'PesoEnKg': line.pesoenkg,
                            'ValorMercancia': line.price_subtotal,
                            'Moneda': self.currency_id.name,
                            'FraccionArancelaria': line.product_id.fraccion_arancelaria and line.product_id.fraccion_arancelaria.c_fraccionarancelaria or '',
                            'UUIDComercioExt': self.uuidcomercioext,
            }
            pedimentos = []
            if line.pedimento:
               for no_pedimento in line.pedimento:
                  pedimentos.append({
                                 'Pedimento': no_pedimento.name[:2] + '  ' + no_pedimento.name[2:4] + '  ' + no_pedimento.name[4:8] + '  ' + no_pedimento.name[8:],
                  })
            guias = [] # soo si tiene un dato
            if line.guiaid_numero:
               guias.append({
                          'NumeroGuiaIdentificacion': line.guiaid_numero,
                          'DescripGuiaIdentificacion': line.guiaid_descrip,
                          'PesoGuiaIdentificacion': line.guiaid_peso,
               })

        #################  CantidadTransporta ############################
        #################  pueden haber varios revisar ############################
   #     mercancia_cantidadt = {
   #                         'Cantidad': merc.product_id.code,
   #                         'IDOrigen': merc.fraccionarancelaria.c_fraccionarancelaria,
   #                         'IDDestino': merc.cantidadaduana,
   #                       #  'CvesTransporte': merc.valorunitarioaduana,
   #     })
		
        #################  DetalleMercancia ############################
      #  mercancia_detalle = {
      #                      'UnidadPesoMerc': merc.product_id.code,
      #                      'PesoBruto': merc.fraccionarancelaria.c_fraccionarancelaria,
      #                      'PesoNeto': merc.cantidadaduana,
      #                      'PesoTara': merc.valorunitarioaduana,
      #                      'NumPiezas': merc.valordolares,
      #  }


#           mercancia.update({'mercancia_cantidadt': mercancia_cantidadt})
#           mercancia.update({'mercancia_detalle': mercancia_detalle})
            mercancia.append({'atributos': mercancia_atributos, 'Pedimentos': pedimentos, 'GuiasIdentificacion': guias})
         mercancias.update({'mercancia': mercancia})

         if self.tipo_transporte == '01': #autotransporte
              transpote_detalle = {
                            'PermSCT': self.permisosct.clave,
                            'NumPermisoSCT': self.numpermisosct,
                            'IdentificacionVehicular': {
                                 'ConfigVehicular': self.autotrasporte_ids.confvehicular.clave,
                                 'PlacaVM': self.autotrasporte_ids.placavm,
                                 'AnioModeloVM': self.autotrasporte_ids.aniomodelo,
                            },
                            'Seguros': {
                                 'AseguraRespCivil': self.autotrasporte_ids.nombreaseg,
                                 'PolizaRespCivil': self.autotrasporte_ids.numpoliza,
                                 'AseguraCarga': self.nombreaseg_merc,
                                 'PolizaCarga': self.numpoliza_merc,
                                 'PrimaSeguro': self.primaseguro_merc,
                                 'AseguraMedAmbiente': self.seguro_ambiente,
                                 'PolizaMedAmbiente': self.poliza_ambiente,
                            },
              }
              remolques = []
              if self.remolque_line_ids:
                 for remolque in self.remolque_line_ids:
                     remolques.append({
                            'SubTipoRem': remolque.subtipo_id.clave,
                            'Placa': remolque.placa,
                     })
                 transpote_detalle.update({'Remolques': remolques})

              mercancias.update({'Autotransporte': transpote_detalle})
         elif self.tipo_transporte == '02': # maritimo
              maritimo = []
         elif self.tipo_transporte == '03': #aereo
              transpote_detalle = {
                            'PermSCT': self.permisosct.clave,
                            'NumPermisoSCT': self.numpermisosct,
                            'MatriculaAeronave': self.matriculaaeronave,
                         #   'NombreAseg': self.nombreaseg,  ******
                         #   'NumPolizaSeguro': self.numpoliza, *****
                            'NumeroGuia': self.numeroguia,
                            'LugarContrato': self.lugarcontrato,
                            'CodigoTransportista': self.transportista_id.codigotransportista.clave,
                            'RFCEmbarcador': self.embarcador_id.vat if self.embarcador_id.cce_clave_pais.c_pais == 'MEX' else '',
                            'NumRegIdTribEmbarc': self.embarcador_id.registro_tributario,
                            'ResidenciaFiscalEmbarc': self.embarcador_id.cce_clave_pais.c_pais if self.embarcador_id.cce_clave_pais.c_pais != 'MEX' else '',
                            'NombreEmbarcador': self.embarcador_id.name,
              }
              mercancias.update({'TransporteAereo': transpote_detalle})
         elif self.tipo_transporte == '04': #ferroviario
              ferroviario = []

         cartaporte20.update({'Mercancias': mercancias})

        #################  Figura transporte ############################
         figuratransporte = []
         tipos_figura = []
         for figura in self.figuratransporte_ids:
            tipos_figura = {
                       'TipoFigura': figura.tipofigura.clave,
                       'RFCFigura': figura.figura_id.vat if figura.figura_id.cce_clave_pais.c_pais == 'MEX' else '',
                       'NumLicencia': figura.figura_id.cce_licencia,
                       'NombreFigura': figura.figura_id.name,
                       'NumRegIdTribFigura': figura.figura_id.registro_tributario,
                       'ResidenciaFiscalFigura': figura.figura_id.cce_clave_pais.c_pais if figura.figura_id.cce_clave_pais.c_pais != 'MEX' else '',
                       'Domicilio': {
                                'Calle': figura.figura_id.cce_calle,
                                'NumeroExterior': figura.figura_id.cce_no_exterior,
                                'NumeroInterior': figura.figura_id.cce_no_interior,
                                'Colonia': figura.figura_id.cce_clave_colonia.c_colonia,
                                'Localidad': figura.figura_id.cce_clave_localidad.c_localidad,
                          #      'Referencia': operador.company_id.cce_clave_estado.c_estado,
                                'Municipio': figura.figura_id.cce_clave_municipio.c_municipio,
                                'Estado': figura.figura_id.cce_clave_estado.c_estado,
                                'Pais': figura.figura_id.cce_clave_pais.c_pais,
                                'CodigoPostal': figura.figura_id.zip,
                       },
            }

            partes = []
            for parte in figura.partetransporte:
               partes.append({
                    'ParteTransporte': parte.clave,
               })
            figuratransporte.append({'TiposFigura': tipos_figura, 'PartesTransporte': partes})

         cartaporte20.update({'FiguraTransporte': figuratransporte})
         res.update({'cartaporte20': cartaporte20})

        return res

    def clean_text(self, text):
        clean_text = text.replace('\n', ' ').replace('\\', ' ').replace('-', ' ').replace('/', ' ').replace('|', ' ')
        clean_text = clean_text.replace(',', ' ').replace(';', ' ').replace('>', ' ').replace('<', ' ')
        return clean_text[:1000]
