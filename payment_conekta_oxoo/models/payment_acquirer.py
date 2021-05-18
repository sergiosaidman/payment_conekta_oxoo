# -*- coding: utf-8 -*-

import logging
import pprint
from odoo import models, fields, api, _, SUPERUSER_ID
from odoo.addons.payment.models.payment_acquirer import ValidationError
from datetime import datetime
_logger = logging.getLogger(__name__)
from odoo.tools.float_utils import float_compare
import base64, requests

try:
    import conekta
except (ImportError, IOError) as err:
    _logger.debug(err)
    
def create_missing_journal_for_conekta_acquirers(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['payment.acquirer']._create_missing_journal_for_conekta_acquirers()
    
class PaymentAcquirer(models.Model):

    _inherit = 'payment.acquirer'

    provider = fields.Selection(selection_add=[('conekta', 'Conekta'), ('conekta_oxxo', 'Conekta oxxo')])
    conekta_secret_key = fields.Char(string="Conekta Secret Key") #required_if_provider='conekta', 
    conekta_publishable_key = fields.Char(string="Conekta Public Key") #required_if_provider='conekta', 
    conekta_secret_key_test = fields.Char(string="Conekta Secret Key Test") #required_if_provider='conekta', 
    conekta_publishable_key_test = fields.Char(string="Conekta Public Key Test") #required_if_provider='conekta', 
    conekta_image = fields.Char('Conekta', help='Visita linkaform.com')
    
    @api.model
    def _create_missing_journal_for_conekta_acquirers(self, company=None):
        '''Create the journal for conekta acquirers.
        We want one journal per acquirer. However, we can't create them during the 'create' of the payment.acquirer
        because every acquirers are defined on the 'payment' module but is active only when installing their own module
        (e.g. payment_paypal for Paypal). We can't do that in such modules because we have no guarantee the chart template
        is already installed.
        '''
        # Search for installed acquirers modules.
        # If this method is triggered by a post_init_hook, the module is 'to install'.
        # If the trigger comes from the chart template wizard, the modules are already installed.
        acquirer_names = ['conekta','conekta_oxxo']

        # Search for acquirers having no journal
        company = company or self.env.company
        acquirers = self.env['payment.acquirer'].search(
            [('provider', 'in', acquirer_names), ('journal_id', '=', False), ('company_id', '=', company.id)])

        journals = self.env['account.journal']
        for acquirer in acquirers.filtered(lambda l: not l.journal_id and l.company_id.chart_template_id):
            acquirer.journal_id = self.env['account.journal'].create(acquirer._prepare_account_journal_vals())
            journals += acquirer.journal_id
        return journals
    
    def conekta_oxxo_get_form_action_url(self):
        return '/payment/conekta_oxxo/feedback'
    
    def conekta_oxxo_form_generate_values(self, tx_values):
        self.ensure_one()
        conekta_tx_values = dict(tx_values)
        conekta_tx_values.update({'phone': tx_values.get('partner_phone'),})
        return conekta_tx_values
    
    def conekta_form_generate_values(self, tx_values):
        self.ensure_one()
        conekta_tx_values = dict(tx_values)
        temp_conekta_tx_values = {
            'company': self.company_id.name,
            'amount': tx_values['amount'],  # Mandatory
            'currency': tx_values['currency'].name,  # Mandatory anyway
            'currency_id': tx_values['currency'].id,  # same here
            'address_line1': tx_values.get('partner_address'),  # Any info of the partner is not mandatory
            'address_city': tx_values.get('partner_city'),
            'address_country': tx_values.get('partner_country') and tx_values.get('partner_country').name or '',
            'email': tx_values.get('partner_email'),
            'address_zip': tx_values.get('partner_zip'),
            'name': tx_values.get('partner_name'),
            'phone': tx_values.get('partner_phone'),
        }

        temp_conekta_tx_values['returndata'] = conekta_tx_values.pop('return_url', '')
        conekta_tx_values.update(temp_conekta_tx_values)
        return conekta_tx_values
    
#     @api.multi
#     def conekta_get_form_action_url(self):
#         return '/payment/square/feedback'
    
    @api.model
    def conekta_s2s_form_process(self, data):
        payment_token = self.env['payment.token'].sudo().create({
        'cc_number': data['cc_number'],
        'cc_holder_name': data['cc_holder_name'],
        'cc_expiry': data['cc_expiry'],
        'cc_brand': data['cc_brand'],
        'cc_cvc': data['cvc'],
        'acquirer_id': int(data['acquirer_id']),
        'partner_id': int(data['partner_id']),
        'conekta_token' : data.get('conekta_token'),
        'acquirer_ref' : data.get('conekta_token'),
        'name': 'XXXXXXXXXXXX%s - %s' % (data['cc_number'][-4:], data['cc_holder_name']),
        #'active': False,
        })
        return payment_token
        
    
    def conekta_s2s_form_validate(self, data):
        self.ensure_one()
        # mandatory fields
        for field_name in ["cc_number", "cvc", "cc_holder_name", "cc_expiry", "cc_brand"]:
            if not data.get(field_name):
                return False
        return True

    def _get_feature_support(self):
        """Get advanced feature support by provider.

        Each provider should add its technical in the corresponding
        key for the following features:
            * fees: support payment fees computations
            * authorize: support authorizing payment (separates
                    authorization and capture)
            * tokenize: support saving payment data in a payment.tokenize
                    object
        """
        res = super(PaymentAcquirer, self)._get_feature_support()
        res['tokenize'].append('conekta')
        return res


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'
    
    conekta_oxxo_reference = fields.Char("Oxxo Payment Reference")
    conekta_oxxo_barcode = fields.Binary(string='Oxxo Barcode')
    conekta_oxxo_expire_date = fields.Date(string="Oxxo expire date")
    
    
    def get_transaction_report_url(self, suffix=None, report_type=None, download=None, query_string=None, anchor=None):
        """
            Get a portal url for this model, including access_token.
            The associated route must handle the flags for them to have any effect.
            - suffix: string to append to the url, before the query string
            - report_type: report_type query string, often one of: html, pdf, text
            - download: set the download query string to true
            - query_string: additional query string
            - anchor: string to append after the anchor #
        """
        self.ensure_one()
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        if base_url[-1]!='/':
            base_url += '/'
            
        url = base_url+'print_payment_transaction/'+str(self.id) + '%s?%s%s%s%s' % (
            suffix if suffix else '',
            '&report_type=%s' % report_type if report_type else '',
            '&download=true' if download else '',
            query_string if query_string else '',
            '#%s' % anchor if anchor else ''
        )
        return url
    
    
    def _get_report_base_filename(self):
        self.ensure_one()
        return self.conekta_oxxo_reference  or self.reference
        
    
    @api.model
    def get_oxxopay_brand_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        if base_url[-1]=='/':
            base_url += 'payment_conekta_oxoo/static/src/img/oxxopay_brand.png'
        else:
            base_url += '/payment_conekta_oxoo/static/src/img/oxxopay_brand.png'
        return base_url
    
    @api.model
    def _conekta_oxxo_form_get_tx_from_data(self, data):
        reference, amount, currency_name = data.get('reference'), data.get('amount'), data.get('currency_name')
        tx = self.search([('reference', '=', reference)])

        if not tx or len(tx) > 1:
            error_msg = _('received data for reference %s') % (pprint.pformat(reference))
            if not tx:
                error_msg += _('; no order found')
            else:
                error_msg += _('; multiple order found')
            _logger.info(error_msg)
            raise ValidationError(error_msg)

        return tx

    def _conekta_oxxo_form_get_invalid_parameters(self, data):
        invalid_parameters = []
        if float_compare(float(data.get('amount', '0.0')), self.amount, 2) != 0:
            invalid_parameters.append(('amount', data.get('amount'), '%.2f' % self.amount))
        if data.get('currency') != self.currency_id.name or data.get('currency') not in ['MXN', 'USD']:
            invalid_parameters.append(('currency', data.get('currency'), self.currency_id.name))
        if 'phone' in data and len(data['phone']) < 10:
            invalid_parameters.append(('phone', data.get('phone'), self.partner_id.phone))    
        return invalid_parameters

    def _conekta_oxxo_form_validate(self, data):
        _logger.info('Validated conekta_oxxo payment for tx %s: set as pending' % (self.reference))
        conekta.api_key = self.acquirer_id.conekta_secret_key_test if self.acquirer_id.state=='test' else self.acquirer_id.conekta_secret_key 
        params = self.create_params('conekta_oxxo')
        try:
            response = conekta.Order.create(params)
        except conekta.ConektaError as error:
            err_val = ''
            for err in error.error_json.get('details'):
                err_val += err.get('message')+'\n'
            self._set_transaction_error(err_val)
            _logger.info(err_val)
            
            return False
            #raise Warning(err_val)
        
        return self._conekta_s2s_validate_tree(response)
    
    def create_params(self, acquirer):
        params = {}
        partner = self.partner_id
        
        if not hasattr(self,'sale_order_ids') and not hasattr(self,'invoice_ids'):
            raise Warning("Can't create payment without Sale order or Invoice in conekta.")
        if hasattr(self,'sale_order_ids') and not self.sale_order_ids and hasattr(self,'invoice_ids') and not self.invoice_ids:
            raise Warning("Can't create payment without Sale order or Invoice in conekta.")
            
        if not partner and self.sale_order_ids:
            partner = self.sale_order_ids[0].partner_id
        if not partner and self.invoice_ids:
            partner = self.invoice_ids[0].partner_id
        
        #params['description'] = _('%s Order %s' % (company_name, self.reference))
        params['amount'] = int(self.amount)
        if self.currency_id.name not in ['MXN', 'USD']:
            raise Warning("Only MXN and USD currency supported.")
        
        params['currency'] = self.currency_id.name
        params['metadata'] = { "reference": self.reference }
        #params['reference_id'] = self.reference
        
        
        if acquirer == 'conekta':
            params['charges'] = [{
                "payment_method": {
                    "type": "card",
                    "token_id": self.payment_token_id and self.payment_token_id.conekta_token
                    }
                }] 
        if acquirer == 'conekta_oxxo':
            params['charges'] = [{
                "payment_method": {
                    "type": "oxxo_cash",
                    }
                }]
            #params['charges'] = {'type': 'oxxo'}
            # TODO: ADD expires_at
        partner_name = partner.name or self.partner_name or ''
        details = params['customer_info'] = {}
        details['name'] = partner_name.replace('_',' ')
        details['phone'] = partner.phone or partner.mobile or ''
        details['email'] = partner.email or self.partner_email or ''
        
        line_items = params['line_items'] = []
        tax_lines = {}
        if hasattr(self,'sale_order_ids'):
            total_amount = 0
            total_amount_untaxed = 0
            for order in self.sale_order_ids:
                total_amount += order.amount_total
                total_amount_untaxed += order.amount_untaxed
                for line in order.order_line:
                    price_reduce = line.price_unit * (1.0 - line.discount / 100.0)
                    if line.tax_id:
                        res = line.tax_id.compute_all(price_reduce, quantity=line.product_uom_qty, product=line.product_id, partner=order.partner_shipping_id)
                        taxes = res['taxes']
                        price_unit = res.get('total_excluded')/line.product_uom_qty
                        for tax in taxes:
                            if (tax['id'],tax['name']) not in tax_lines:
                                tax_lines[(tax['id'],tax['name'])] = tax['amount'] 
                            else:
                                tax_lines[(tax['id'],tax['name'])] = tax_lines[(tax['id'],tax['name'])] + tax['amount']
                    else:
                        price_unit = price_reduce
                    item = {}
                    line_items.append(item)
                    item['name'] = line.product_id.name or ''
                    item['description'] = line.product_id.description_sale or line.product_id.name or ''
                    item['unit_price'] = int(price_unit * 100) or 1
                    item['quantity'] = int(line.product_uom_qty) or 1
                    #item['sku'] = line.product_id.default_code or ''
                    item['category'] = line.product_id.categ_id.name or ''
                    if line.product_id.default_code:
                        item['sku'] = line.product_id.default_code or ''
            #If price include taxes, than Amount need to pass untaxed amount
            if self.amount==total_amount and tax_lines:
                params['amount'] = int(total_amount_untaxed)            
        if hasattr(self,'invoice_ids'):    
            total_amount_invoice = 0
            total_amount_untaxed_invoice = 0
            
            for invoice in self.invoice_ids:
                total_amount_invoice += invoice.amount_total
                total_amount_untaxed_invoice += invoice.amount_untaxed
                for line in invoice.invoice_line_ids:
                    item = {}
                    line_items.append(item)
                    item['name'] = line.product_id.name or ''
                    item['description'] = line.product_id.description_sale or line.product_id.name or ''
                    item['unit_price'] = int((line.price_subtotal/line.quantity) * 100) or 1
                    item['quantity'] = int(line.quantity) or 1
                    item['category'] = line.product_id.categ_id.name or ''
                    if line.product_id.default_code:
                        item['sku'] = line.product_id.default_code or ''
                
                
                        
                for tax_line in invoice.line_ids.filtered(lambda line: line.tax_line_id):
                    if (tax_line.tax_line_id.id, tax_line.tax_line_id.name) not in tax_lines:
                        tax_lines[(tax_line.tax_line_id.id, tax_line.tax_line_id.name)] = tax_line.price_subtotal 
                    else:
                        tax_lines[(tax_line.tax_line_id.id, tax_line.tax_line_id.name)] = tax_lines[(tax_line.tax_line_id.id, tax_line.tax_line_id.name)] + tax_line.price_subtotal
            #If price include taxes, than Amount need to pass untaxed amount
            if self.amount == total_amount_invoice and tax_lines:
                params['amount'] = int(total_amount_untaxed_invoice) 
        if tax_lines:
            tax_lines_conekta = params['tax_lines'] = []
            for tax_name,amount in tax_lines.items():
                item = {'description': tax_name[1], 'amount' : int(amount*100)}
                tax_lines_conekta.append(item)
    
        return params
    
    def _create_conekta_charge(self, acquirer_ref=None, tokenid=None, email=None):
        conekta.api_key = self.acquirer_id.conekta_secret_key_test if self.acquirer_id.state=='test' else self.acquirer_id.conekta_secret_key 
        params = self.create_params('conekta')
        try:
            #response = conekta.Charge.create(params)
            response = conekta.Order.create(params)
        except conekta.ConektaError as error:
            err_val = ''
            for err in error.error_json.get('details'):
                err_val += err.get('message')+'\n'
            #raise Warning(err_val)
            return self._conekta_s2s_validate_tree({'error' : err_val})
            #return error.message['message_to_purchaser']
        return response

    
    def conekta_s2s_do_transaction(self, **kwargs):
        self.ensure_one()
        result = self._create_conekta_charge(acquirer_ref=self.payment_token_id.acquirer_ref, email=self.partner_email)
        return self._conekta_s2s_validate_tree(result)


    @api.model
    def _conekta_form_get_tx_from_data(self, data):
        """ Given a data dict coming from conekta, verify it and find the related
        transaction record. """
        reference = data.metadata.get('reference') #data.get('metadata', {}).get('reference')
        if not reference:
            conekta_error = "No reference found in conekta transaction.." #data.get('error', {}).get('message', '')
            _logger.error('Conekta: invalid reply received from Conekta API, looks like '
            'the transaction failed. (error: %s)', conekta_error  or 'n/a')
            error_msg = _("We're sorry to report that the transaction has failed.")
            if conekta_error:
                error_msg += " " + (_("Conekta gave us the following info about the problem: '%s'") %
                                    conekta_error)
            error_msg += " " + _("Perhaps the problem can be solved by double-checking your "
                                    "credit card details, or contacting your bank?")
            raise ValidationError(error_msg)

        tx = self.search([('reference', '=', reference)])
        if not tx:
            error_msg = (_('Conekta: no order found for reference %s') % reference)
            _logger.error(error_msg)
            raise ValidationError(error_msg)
        elif len(tx) > 1:
            error_msg = (_('Conekta: %s orders found for reference %s') % (len(tx), reference))
            _logger.error(error_msg)
            raise ValidationError(error_msg)
        return tx[0]

    
    def _conekta_s2s_validate_tree(self, tree):
        self.ensure_one()
        if self.state not in ('draft', 'pending', 'refunding'):
            _logger.info('Conekta: trying to validate an already validated tx (ref %s)', self.reference)
            return True
        if type(tree)==dict and tree.get('error'):
            self._set_transaction_error(msg=tree.get('error'))
            return False
        
        status = tree.payment_status
        
        payment_tokens = self.mapped('payment_token_id')
        if payment_tokens:
            payment_tokens.sudo().write({'active': False,})
        if status == 'paid':
            #new_state = 'refunded' if self.state == 'refunding' else 'done'
            self.write({
                #'state': new_state,
                'date': fields.datetime.now(),
                'acquirer_reference': tree.id,
            })
            self._set_transaction_done()
            self.execute_callback()
            if self.payment_token_id:
                self.payment_token_id.verified = True
            return True
        elif status == 'pending_payment':
            date = datetime.fromtimestamp(int(tree.charges[0].payment_method['expires_at'])).strftime('%Y-%m-%d')            
            self.write({
                'acquirer_reference': tree.id,
                'conekta_oxxo_reference': tree.charges[0].payment_method.reference, 
                'conekta_oxxo_barcode': base64.encodestring(
                    requests.get(tree.charges[0].payment_method['barcode_url']).content),
                'conekta_oxxo_expire_date': date,                
            })
            self._set_transaction_pending()
            self.execute_callback()
            if self.payment_token_id:
                self.payment_token_id.verified = True
            return True
        else:
            #error = tree['error']['message']
            #_logger.warn(error)
            self.sudo().write({
                'state_message': 'error',
                'acquirer_reference': tree.id,
                'date': fields.datetime.now(),
            })
            self._set_transaction_cancel()
            return False

    
    def _conekta_form_get_invalid_parameters(self, data):
        invalid_parameters = []
        reference = data['metadata']['reference']
        if reference != self.reference:
            invalid_parameters.append(('Reference', reference, self.reference))
        return invalid_parameters

    
    def _conekta_form_validate(self,  data):
        return self._conekta_s2s_validate_tree(data)

class PaymentToken(models.Model):

    _inherit = 'payment.token'
    
    conekta_token = fields.Char('Conekta token', help='payment token from Conekta')
    
    def conekta_create(self, values):
        if values.get('cc_number'):
            # create a alias via batch
            values['cc_number'] = values['cc_number'].replace(' ', '')
        return {}    
            
