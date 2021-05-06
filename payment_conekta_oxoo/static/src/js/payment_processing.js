odoo.define('payment_conekta_oxoo.processing', function (require) {
    'use strict';

var publicWidget = require('web.public.widget');
    

var PaymentProcessing = publicWidget.registry.PaymentProcessing;
return PaymentProcessing.include({
	processPolledData: function(transactions) {
		//Condition Added by Nilesh for conekta_oxxo
        if (transactions.length > 0 && ['conekta_oxxo'].indexOf(transactions[0].acquirer_provider) >= 0) {
            window.location = transactions[0].return_url;
            return;
        }
		else{
			return this._super.apply(this, arguments);
		}
	},
});
    
});
