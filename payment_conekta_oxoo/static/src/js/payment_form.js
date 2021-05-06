odoo.define('payment_conekta_oxoo.payment_form', function (require) {
"use strict";

var core = require('web.core');
var PaymentForm = require('payment.payment_form');

var _t = core._t;

PaymentForm.include({
	_createConektaToken: function (ev, $checkedRadio, addPmEvent) {
        var self = this;
        if (ev.type === 'submit') {
            var button = $(ev.target).find('*[type="submit"]')[0]
        } else {
            var button = ev.target;
        }
        var form = this.el
        
        this.disableButton(button);
        $checkedRadio = $checkedRadio[0];
        var acquirerID = this.getAcquirerIdFromRadio($checkedRadio);
        var acquirerForm = this.$('#o_payment_add_token_acq_' + acquirerID);
        var inputsForm = $('input', acquirerForm);
        var formData = self.getFormData(inputsForm);
        var ds = $('input[name="data_set"]', acquirerForm)[0];
        if (this.options.partnerId === undefined) {
            console.warn('payment_form: unset partner_id when adding new token; things could go wrong');
        }
        
        var conektaSuccessResponseHandler = function(token) {
    		
            formData['conekta_token'] = token.id
            //var button = "#o_payment_form_pay";
            
            return self._rpc({
                route: ds.dataset.createRoute,
                params: formData,
            }).then(function (data) {
                // if the server has returned true
                if (data.result) {
                    // and it need a 3DS authentication
                    if (data['3d_secure'] !== false) {
                        // then we display the 3DS page to the user
                        $("body").html(data['3d_secure']);
                    }
                    else {
                    	$checkedRadio.value = data.id; // set the radio value to the new card id
                        debugger;
                        form.submit();
                        return new Promise(function () {});
                    }
                }
                // if the server has returned false, we display an error
                else {
                    if (data.error) {
                        self.displayError(
                            '',
                            data.error);
                    } else { // if the server doesn't provide an error message
                        self.displayError(
                            _t('Server Error'),
                            _t('e.g. Your credit card details are wrong. Please verify.'));
                    }
                }
                // here we remove the 'processing' icon from the 'add a new payment' button
                self.enableButton(button);
            }).guardedCatch(function (error) {
                error.event.preventDefault();
                // if the rpc fails, pretty obvious
                self.enableButton(button);

                self.displayError(
                    _t('Server Error'),
                    _t("We are not able to add your payment method at the moment.") +
                        self._parseError(error)
                );
            });
            //###########################
            
    	};
    	var conektaErrorResponseHandler = function(response) {
        	self.displayError('',response.message);
        };
        
        var month_year = formData.cc_expiry.split(" / ")
    	var exp_year = new Date().getFullYear().toString().substr(0,2) + month_year[1]
    	var tokenParams = {
    			  "card": {
    			    "number": formData.cc_number,
    			    "name": formData.cc_holder_name,
    			    "exp_year": exp_year,
    			    "exp_month": month_year[0],
    			    "cvc": formData.cvc,
    			  }
    			};
    	Conekta.setPublicKey(formData.conekta_public_key);
    	Conekta.Token.create(tokenParams, conektaSuccessResponseHandler, conektaErrorResponseHandler);
    	
    },
	
    payEvent: function (ev) {
        ev.preventDefault();
        var $checkedRadio = this.$('input[type="radio"]:checked');

        // first we check that the user has selected a conekta as s2s payment method
        if ($checkedRadio.length === 1 && this.isNewPaymentRadio($checkedRadio) && $checkedRadio.data('provider') === 'conekta') {
            this._createConektaToken(ev, $checkedRadio);
        }else if ($checkedRadio.length === 1 && this.isFormPaymentRadio($checkedRadio) && $checkedRadio.data('provider') === 'conekta_oxxo') {    
			var self = this;
			if (ev.type === 'submit') {
	            var button = $(ev.target).find('*[type="submit"]')[0]
	        } else {
	            var button = ev.target;
	        }
			var checked_radio = $checkedRadio[0];
			var acquirer_id = this.getAcquirerIdFromRadio(checked_radio);
            var acquirer_form = false;
            if (this.isNewPaymentRadio(checked_radio)) {
                acquirer_form = this.$('#o_payment_add_token_acq_' + acquirer_id);
            } else {
                acquirer_form = this.$('#o_payment_form_acq_' + acquirer_id);
            }
            
			this.disableButton(button);
            var $tx_url = this.$el.find('input[name="prepare_tx_url"]');
            // if there's a prepare tx url set
            if ($tx_url.length === 1) {
                // if the user wants to save his credit card info
                var form_save_token = acquirer_form.find('input[name="o_payment_form_save_token"]').prop('checked');
                // then we call the route to prepare the transaction
                return this._rpc({
                    route: $tx_url[0].value,
                    params: {
                        'acquirer_id': parseInt(acquirer_id),
                        'save_token': form_save_token,
                        'access_token': self.options.accessToken,
                        'success_url': self.options.successUrl,
                        'error_url': self.options.errorUrl,
                        'callback_method': self.options.callbackMethod,
                        'order_id': self.options.orderId,
                    },
                }).then(function (result) {
                    if (result) {
                        // if the server sent us the html form, we create a form element
                        var newForm = document.createElement('form');
                        newForm.setAttribute("method", "post"); // set it to post
                        newForm.setAttribute("provider", checked_radio.dataset.provider);
                        newForm.hidden = true; // hide it
                        newForm.innerHTML = result; // put the html sent by the server inside the form
						
						var phone = $(newForm).find('input[name="phone"]')
						if (phone.length > 0  & phone.val().length < 10){
							self.displayError(
	                            _t('Server Error'),
	                            _t("Please enter valid phone number. Length of phone number must be 10 digits. ")
	                        );
							self.enableButton(button);
						}
						else{
							var action_url = $(newForm).find('input[name="data_set"]').data('actionUrl');
                            newForm.setAttribute("action", action_url); // set the action url
                            $(document.getElementsByTagName('body')[0]).append(newForm); // append the form to the body
                            $(newForm).find('input[data-remove-me]').remove(); // remove all the input that should be removed
                            if(action_url) {
                                newForm.submit(); // and finally submit the form
								return new Promise(function () {});
                            }	
						}
                    }
                    else {
                        self.displayError(
                            _t('Server Error'),
                            _t("We are not able to redirect you to the payment form.")
                        );
                        self.enableButton(button);
                    }
                }).guardedCatch(function (error) {
                    error.event.preventDefault();
                    self.displayError(
                        _t('Server Error'),
                        _t("We are not able to redirect you to the payment form.") + " " +
                            self._parseError(error)
                    );
                });
            }
            else {
                // we append the form to the body and send it.
                this.displayError(
                    _t("Cannot setup the payment"),
                    _t("We're unable to process your payment.")
                );
                self.enableButton(button);
            }
		} else {
            this._super.apply(this, arguments);
        }
    },
    addPmEvent: function (ev) {
        ev.stopPropagation();
        ev.preventDefault();
        var $checkedRadio = this.$('input[type="radio"]:checked');

        // first we check that the user has selected a conekta as add payment method
        if ($checkedRadio.length === 1 && this.isNewPaymentRadio($checkedRadio) && $checkedRadio.data('provider') === 'conekta') {
            this._createConektaToken(ev, $checkedRadio, true);
        } else {
            this._super.apply(this, arguments);
        }
    },
});

});