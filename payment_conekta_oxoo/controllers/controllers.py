# -*- coding: utf-8 -*-
import logging
import werkzeug
import pprint

from odoo import http
from odoo.http import request

from odoo.addons.portal.controllers.portal import _build_url_w_params
from odoo.addons.payment.controllers.portal import PaymentProcessing
from odoo.addons.portal.controllers.portal import CustomerPortal

_logger = logging.getLogger(__name__)

from odoo.addons.website_sale.controllers.main import WebsiteSale
try:
    import phonenumbers
except ImportError:
    phonenumbers=None
    
class WebsiteSaleConekta(WebsiteSale):
    def checkout_form_validate(self, mode, all_form_values, data):
        error, error_message = super(WebsiteSaleConekta,self).checkout_form_validate(mode, all_form_values, data)
        if 'phone' not in error and all_form_values.get('phone'):
            phone = all_form_values.get('phone')
            if len(phone) < 10:
                error['phone'] = 'error'
                error_message.append('Please enter valid phone number. Length of phone number must be 10 digits')
                
            
        return error, error_message
    
class PortalConekta(CustomerPortal):
    
    @http.route(['/print_payment_transaction/<int:transaction_id>'], type='http', auth="public", website=True)
    def portal_payment_transaction_detail(self, transaction_id, report_type=None, download=False, **kw):
        document = request.env['payment.transaction'].sudo().browse(transaction_id)
        document_sudo = document.exists()
        if not document_sudo:
            #raise MissingError("This document does not exist.")
            return request.redirect('/my')
        #if report_type in ('html', 'pdf', 'text'):
        return self._show_report(model=document_sudo, report_type=report_type, report_ref='payment_conekta_oxoo.action_report_payment_transaction', download=download)

    
class Conekta(http.Controller):
    _accept_url = '/payment/transfer/feedback'

    @http.route([
        '/payment/conekta_oxxo/feedback',
    ], type='http', auth='none', csrf=False)
    def conekta_oxxo_form_feedback(self, **post):
        _logger.info('Beginning form_feedback with post data %s', pprint.pformat(post)) 
        request.env['payment.transaction'].sudo().form_feedback(post, 'conekta_oxxo')
        return werkzeug.utils.redirect('/payment/process')

    @http.route(['/payment/conekta/oxoo_pay/create'], type='json', auth='public')
    def conekta_oxoo_pay_create_charge(self, **post):
        _logger.info('post : '+str(post))
        json_data = request.jsonrequest
        _logger.info("json_data :"+str(json_data))
        data = json_data.get('data')
        if json_data and json_data.get('type','')=='charge.paid' and data:
            tx_obj = request.env['payment.transaction']
            order_id = data.get('object', {}).get('order_id')
            payment_reference = data.get('object', {}).get('payment_method',{}).get('reference')
            tx = None
            if order_id:
                tx = tx_obj.sudo().search([('acquirer_reference', '=', order_id)], limit=1)
            if not tx and payment_reference:
                tx = tx_obj.sudo().search([('conekta_oxxo_reference', '=', payment_reference)], limit=1)
            if tx:
                if tx.state in ['pending', 'draft']:
                    tx._set_transaction_done()
                try:
                    tx._post_process_after_done()
                except Exception as e:
                    pass
        return "<Response></Response>"
    
    @http.route(['/payment/conekta/s2s/create_json'], type='json', auth='public')
    def conekta_s2s_create_json(self, **kwargs):
        acquirer_id = int(kwargs.get('acquirer_id'))
        acquirer = request.env['payment.acquirer'].browse(acquirer_id)
        if not kwargs.get('partner_id'):
            kwargs = dict(kwargs, partner_id=request.env.user.partner_id.id)
        return acquirer.s2s_process(kwargs).id

    @http.route(['/payment/conekta/s2s/create'], type='http', auth='public')
    def conekta_s2s_create(self, **post):
        acquirer_id = int(post.get('acquirer_id'))
        acquirer = request.env['payment.acquirer'].browse(acquirer_id)
        error = None
        try:
            acquirer.s2s_process(post)
        except Exception as e:
            error = e.message

        return_url = post.get('return_url', '/')
        if error:
            separator = '?' if werkzeug.urls.url_parse(return_url).query == '' else '&'
            return_url += '{}{}'.format(separator, werkzeug.urls.url_encode({'error': error}))

        return werkzeug.utils.redirect(return_url)

    @http.route(['/payment/conekta/s2s/create_json_3ds'], type='json', auth='public', csrf=False)
    def conekta_s2s_create_json_3ds(self, verify_validity=False, **kwargs):
        if not kwargs.get('partner_id'):
            kwargs = dict(kwargs, partner_id=request.env.user.partner_id.id)
        token = request.env['payment.acquirer'].browse(int(kwargs.get('acquirer_id'))).s2s_process(kwargs)

        if not token:
            res = {
				'result': False,
			}
            return res
        res = {
			'result': True,
			'id': token.id,
			'short_name': token.short_name,
			'3d_secure': False,
			'verified': False,
		}

        if verify_validity != False:
            token.validate()
            res['verified'] = token.verified

        return res

