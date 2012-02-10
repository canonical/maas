/* Copyright 2012 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Utilities for the user preferences page.
 *
 * @module Y.mass.prefs
 */

YUI.add('maas.prefs', function(Y) {

Y.log('loading mass.prefs');
var module = Y.namespace('maas.prefs');

// Only used to mockup io in tests.
module._io = Y;

var TokenWidget = function() {
    TokenWidget.superclass.constructor.apply(this, arguments);
};

TokenWidget.NAME = 'profile-widget';

Y.extend(TokenWidget, Y.Widget, {

    displayError: function(message) {
        this.status_node.set('text', message);
    },

    initializer: function(cfg) {
        this.regenerate_link = Y.Node.create('<a />')
            .set('href', '#')
            .set('id','regenerate_tokens')
            .set('text', "Regenerate the tokens");
        this.status_node = Y.Node.create('<span />')
            .set('id','regenerate_error');
        this.spinnerNode = Y.Node.create('<img />')
            .set('src', MAAS_config.uris.statics + 'img/spinner.gif');
        this.get('srcNode').one('#tokens_regeneration_placeholder')
            .append(this.regenerate_link)
            .append(this.status_node);
    },

    bindUI: function() {
        var self = this;
        this.regenerate_link.on('click', function(e) {
            e.preventDefault();
            self.regenerateTokens();
        });
    },

    showSpinner: function() {
        this.displayError('');
        this.status_node.insert(this.spinnerNode, 'after');
    },

    hideSpinner: function() {
        this.spinnerNode.remove();
    },

    regenerateTokens: function() {
        var self = this;
        var cfg = {
            method: 'POST',
            data: 'op=reset_authorisation_token',
            sync: false,
            on: {
                start: Y.bind(self.showSpinner, self),
                end: Y.bind(self.hideSpinner, self),
                success: function(id, out) {
                    var token;
                    try {
                        token = JSON.parse(out.response);
                    }
                    catch(e) {
                        // Parsing error.
                        displayError('Unable to regenerate the tokens.');
                    }
                    // Update the 3 tokens (consumer key, token key and
                    // token secret).
                    self.get(
                        'srcNode').one(
                            '#token_key').set('text', token.token_key);
                    self.get(
                        'srcNode').one(
                            '#token_secret').set('text', token.token_secret);
                    self.get(
                        'srcNode').one(
                            '#consumer_key').set('text', token.consumer_key);
                 },
                failure: function(id, out) {
                    displayError('Unable to regenerate the tokens.');
                }
            }
        };
        var request = module._io.io(
            MAAS_config.uris.account_handler, cfg);
    }
});

module.TokenWidget = TokenWidget;

}, '0.1', {'requires': ['widget', 'io']}
);
