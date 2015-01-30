/* Copyright 2012 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Utilities for the node page.
 *
 * @module Y.maas.node_check
 */

YUI.add('maas.node_check', function(Y) {

Y.log('loading maas.node_check');
var module = Y.namespace('maas.node_check');

// Only used to mockup io in tests.
module._io = new Y.IO();

var PowerCheckWidget;

PowerCheckWidget = function() {
    PowerCheckWidget.superclass.constructor.apply(this, arguments);
};

PowerCheckWidget.NAME = 'powercheck-widget';

PowerCheckWidget.ATTRS = {
    // The status text.
    status_text: {
        readOnly: true,
        getter: function() {
            return this.status_check.get('text');
        }
    },

    // The error text.
    error_text: {
        readOnly: true,
        getter: function() {
            return this.error_msg.get('text');
        }
    }
};

Y.extend(PowerCheckWidget, Y.Widget, {

    initializer: function(cfg) {
        this.system_id = cfg.system_id;
        // Create action button.
        this.button = Y.Node.create('<button />')
            .addClass('cta-ubuntu secondary full')
            .setAttribute('type', 'submit')
            .setAttribute('name', 'action')
            .setAttribute('value', 'check-powerstate')
            .set('text', 'Check power state');
        // Store initial conditions.
        this.initial_background = this.button.getStyle('background');
        this.initial_color = this.button.getStyle('color');
        // Initialize widget elements.
        this.status_check = Y.Node.create('<p />')
            .addClass('power-check-ok three-col');
        this.error_msg = Y.Node.create('<p />')
            .addClass('power-check-error three-col');
        this.button.setStyle('position', 'relative');
        this.spinnerNode = Y.Node.create('<span />')
            .addClass('spinner')
            .setStyle('position', 'absolute')
            .setStyle('top', '4px')
            .setStyle('right', '7px')
            .setStyle('margin', '0');
    },

    bindUI: function() {
        var self = this;
        this.button.on('click', function(e) {
            e.preventDefault();
            self.requestPowerState();
        });
    },

   destructor: function() {
        this.button.remove();
        this.status_check.remove();
        this.error_msg.remove();
   },

   extractStateFromResponse: function(out) {
       return 'on';
   },

   /**
    * Request the power state of this node.
    *
    * @method requestPowerState
    */
    requestPowerState: function() {
        var self = this;
        var cfg = {
            method: 'GET',
            data: Y.QueryString.stringify({
                op: 'query_power_state'
                }),
            sync: false,
            on: {
                start: Y.bind(self.showSpinner, self),
                end: Y.bind(self.hideSpinner, self),
                success: function(id, out) {
                    Y.log(out);
                    try {
                        stateResponse = JSON.parse(out.response);
                    }
                    catch(e) {
                        // Parsing error.
                        self.displayErrorMessage('Unable to parse response.');
                    }
                    var state = stateResponse.state;
                    if (state === 'on' || state === 'off') {
                        self.displaySuccessMessage(
                            "Success: node is " + state + ".");
                    }
                    else {
                        self.displayErrorMessage(
                            "Error: " + state + ".");
                    }
                 },
                failure: function(id, out) {
                    Y.log(out.responseText);
                    self.displayErrorMessage(
                        "Error: " + out.responseText + ".");
                }
            }
        };
        var url = MAAS_config.uris.nodes_handler + this.system_id;
        module._io.send(url, cfg);
    },

    displayErrorMessage: function(message) {
        this.error_msg.set('text', message);
    },

    displaySuccessMessage: function(message) {
        this.status_check.set('text', message);
    },

    showSpinner: function() {
        // Reset messages.
        this.displayErrorMessage('');
        this.displaySuccessMessage('');
        // Set in-progress color and background.
        this.button
            .append(this.spinnerNode);
    },

    hideSpinner: function() {
        // Restore color and background.
        this.button
            .setStyle('background', this.initial_background);
        this.button
            .setStyle('color', this.initial_color);
        this.spinnerNode.remove();
    },

    render: function() {
        this.button.remove();
        this.status_check.remove();
        this.error_msg.remove();
        var srcNode = this.get('srcNode');
        var formActions = srcNode.one('form#node_actions');
        if (Y.Lang.isValue(formActions)) {
            formActions.insert(this.button, 'after');
            this.button
                .insert(this.status_check, "after");
            this.button
                .insert(this.error_msg, "after");
        }
        this.bindUI();
    }

});

module.PowerCheckWidget = PowerCheckWidget;

}, '0.1', {'requires': ['widget', 'io']}
);
