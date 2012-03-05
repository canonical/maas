/* Copyright 2012 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Utilities for the user preferences page.
 *
 * @module Y.maas.prefs
 */

YUI.add('maas.prefs', function(Y) {

Y.log('loading maas.prefs');
var module = Y.namespace('maas.prefs');

// Only used to mockup io in tests.
module._io = new Y.IO();

var TokenWidget = function() {
    TokenWidget.superclass.constructor.apply(this, arguments);
};

TokenWidget.NAME = 'profile-widget';

TokenWidget.ATTRS = {
    // The number of tokens displayed.
    nb_tokens: {
        readOnly: true,
        getter: function() {
            return this.get('srcNode').all('.bundle').size();
        }
    }
};

Y.extend(TokenWidget, Y.Widget, {

    displayError: function(message) {
        this.status_node.set('text', message);
    },

    initializer: function(cfg) {
        this.create_link = Y.Node.create('<a />')
            .set('href', '#')
            .set('id','create_token')
            .addClass('button')
            .addClass('right')
            .set('text', "+ Add MaaS key");
        this.status_node = Y.Node.create('<div />')
            .set('id','create_error');
        this.spinnerNode = Y.Node.create('<img />')
            .addClass('spinner')
            .set('src', MaaS_config.uris.statics + 'img/spinner.gif');
        this.get('srcNode').one('#token_creation_placeholder')
            .append(this.create_link)
            .append(this.status_node);
    },

    confirm: function(message) {
        return confirm(message);
    },

    bindDeleteRow: function(row) {
        var self = this;
        var delete_link = row.one('a.delete-link');
        delete_link.on('click', function(e) {
            e.preventDefault();
            if (self.confirm("Are you sure you want to delete this key?")) {
                self.deleteToken(row);
            }
        });
    },

    bindUI: function() {
        var self = this;
        this.create_link.on('click', function(e) {
            e.preventDefault();
            self.requestKeys();
        });
        Y.each(this.get('srcNode').all('.bundle'), function(row) {
            self.bindDeleteRow(row);
        });
    },

   /**
    * Delete the token contained in the provided row.
    * Call the API to delete the token and then remove the table row.
    *
    * @method deleteToken
    */
    deleteToken: function(row) {
        var token_key = row.one('input').get('id');
        var self = this;
        var cfg = {
            method: 'POST',
            data: Y.QueryString.stringify({
                op: 'delete_authorisation_token',
                token_key: token_key
                }),
            sync: false,
            on: {
                start: Y.bind(self.showSpinner, self),
                end: Y.bind(self.hideSpinner, self),
                success: function(id, out) {
                    row.remove();
                 },
                failure: function(id, out) {
                    self.displayError('Unable to delete the token.');
                }
            }
        };
        var request = module._io.send(
            MaaS_config.uris.account_handler, cfg);
    },

    showSpinner: function() {
        this.displayError('');
        this.status_node.insert(this.spinnerNode, 'after');
    },

    hideSpinner: function() {
        this.spinnerNode.remove();
    },

   /**
    * Create a single string token from a key set.
    *
    * A key set is composed of 3 keys: consumer_key, token_key, token_secret.
    * For an easy copy and paste experience, the string handed over to the
    * user is a colon separated concatenation of these keys called 'token'.
    *
    * @method createTokenFromKeys
    */
    createTokenFromKeys: function(consumer_key, token_key, token_secret) {
        return consumer_key + ':' + token_key + ':' + token_secret;
    },

   /**
    * Add a token to the list of tokens.
    *
    * @method addToken
    */
    addToken: function(token, token_key) {
        var list = this.get('srcNode').one('ul');
        var row = Y.Node.create('<li />')
            .addClass('bundle')
            .append(Y.Node.create('<a />')
                .set('href', '#')
                .addClass('delete-link')
                .addClass('right')
                .append(Y.Node.create('<img />')
                    .set('title', 'Delete token')
                    .set(
                        'src',
                        MaaS_config.uris.statics + 'img/delete.png')))
            .append(Y.Node.create('<input />')
                .set('type', 'text')
                .addClass('disabled')
                .set('id', token_key)
                .set('value', token));
       list.append(row);
       this.bindDeleteRow(row);
    },

   /**
    * Request a new OAuth key set from the API.
    *
    * @method requestKeys
    */
    requestKeys: function() {
        var self = this;
        var cfg = {
            method: 'POST',
            data: 'op=create_authorisation_token',
            sync: false,
            on: {
                start: Y.bind(self.showSpinner, self),
                end: Y.bind(self.hideSpinner, self),
                success: function(id, out) {
                    var keys;
                    try {
                        keys = JSON.parse(out.response);
                    }
                    catch(e) {
                        // Parsing error.
                        self.displayError('Unable to create a new token.');
                    }
                    // Generate a token from the keys.
                    var token = self.createTokenFromKeys(
                        keys.consumer_key, keys.token_key,
                        keys.token_secret);
                    // Add the new token to the list of tokens.
                    self.addToken(token, keys.token_key);
                 },
                failure: function(id, out) {
                    self.displayError('Unable to create a new token.');
                }
            }
        };
        var request = module._io.send(
            MaaS_config.uris.account_handler, cfg);
    }
});

module.TokenWidget = TokenWidget;

}, '0.1', {'requires': ['widget', 'io']}
);
