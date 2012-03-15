/* Copyright 2012 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 */

YUI({ useBrowserConsole: true }).add('maas.prefs.tests', function(Y) {

Y.log('loading maas.prefs.tests');
var namespace = Y.namespace('maas.prefs.tests');

var module = Y.maas.prefs;
var suite = new Y.Test.Suite("maas.prefs Tests");

var api_template = Y.one('#api-template').getContent();

suite.add(new Y.maas.testing.TestCase({
    name: 'test-prefs',

    setUp: function() {
        Y.one("body").append(Y.Node.create(api_template));
    },

    createWidget: function() {
        var widget = new module.TokenWidget({srcNode: '#placeholder'});
        this.addCleanup(function() { widget.destroy(); });
        this.patchWidgetConfirm(widget, true);
        return widget;
    },

    patchWidgetConfirm: function(widget, result) {
        // Monkey patch widget.confirm.
        widget.confirm = function(message) {
            return result;
        };
    },

    testInitializer: function() {
        var widget = this.createWidget();
        widget.render();
        // The "create a new API token" has been created.
        var create_link = widget.get('srcNode').one('#create_token');
        Y.Assert.isNotNull(create_link);
        Y.Assert.areEqual(
            "+ Add MAAS key", create_link.get('text'));
        // The placeholder node for errors has been created.
        var status_node = widget.get('srcNode').one('#create_error');
        Y.Assert.isNotNull(status_node);
        Y.Assert.areEqual(
            '',
            widget.get('srcNode').one('#create_error').get('text'));
    },

    test_nb_tokens: function() {
        var widget = this.createWidget();
        widget.render();
        Y.Assert.areEqual(2, widget.get('nb_tokens'));
     },

    testDeleteTokenCall: function() {
        // A click on the delete link calls the API to delete a token.
        var mockXhr = new Y.Base();
        var fired = false;
        mockXhr.send = function(url, cfg) {
            fired = true;
            Y.Assert.areEqual(MAAS_config.uris.account_handler, url);
            Y.Assert.areEqual(
                "op=delete_authorisation_token&token_key=tokenkey1",
                cfg.data);
        };
        this.mockIO(mockXhr, module);
        var widget = this.createWidget();
        widget.render();
        var link = widget.get('srcNode').one('.delete-link');
        link.simulate('click');
        Y.Assert.isTrue(fired);
    },

    testDeleteTokenCallsAPI: function() {
        var log = this.logIO(module);
        var widget = this.createWidget();
        widget.render();
        var link = widget.get('srcNode').one('.delete-link');
        link.simulate('click');
        Y.Assert.areEqual(1, log.length);
    },

    testDeleteTokenFail404DisplaysErrorMessage: function() {
        // If the API call to delete a token fails with a 404 error,
        // an error saying that the key has already been deleted is displayed.
        var mockXhr = new Y.Base();
        mockXhr.send = function(url, cfg) {
            cfg.on.failure(3, {status: 404});
        };
        this.mockIO(mockXhr, module);
        var widget = this.createWidget();
        widget.render();
        var link = widget.get('srcNode').one('.delete-link');
        link.simulate('click');
        Y.Assert.areEqual(
            "The key has already been deleted.",
            widget.get('srcNode').one('#create_error').get('text'));
    },

    testDeleteTokenFailDisplaysErrorMessage: function() {
        // If the API call to delete a token fails, an error is displayed.
        var mockXhr = new Y.Base();
        mockXhr.send = function(url, cfg) {
            cfg.on.failure(3, {status: 500});
        };
        this.mockIO(mockXhr, module);
        var widget = this.createWidget();
        widget.render();
        var link = widget.get('srcNode').one('.delete-link');
        link.simulate('click');
        Y.Assert.areEqual(
            "Unable to delete the key.",
            widget.get('srcNode').one('#create_error').get('text'));
    },

    testDeleteTokenDisplay: function() {
        // When the token is successfully deleted by the API, the
        // corresponding row is deleted.
        var mockXhr = new Y.Base();
        var fired = false;
        mockXhr.send = function(url, cfg) {
            fired = true;
            cfg.on.success(3);
        };
        this.mockIO(mockXhr, module);
        var widget = this.createWidget();
        widget.render();
        var link = widget.get('srcNode').one('.delete-link');
        Y.Assert.isNotNull(Y.one('#tokenkey1'));
        link.simulate('click');
        Y.Assert.isTrue(fired);
        Y.Assert.isNull(Y.one('#tokenkey1'));
        Y.Assert.isNotNull(Y.one('#tokenkey2'));
        Y.Assert.areEqual(1, widget.get('nb_tokens'));
    },

    testDontDeleteIfConfirmReturnsFalse: function() {
        var mockXhr = new Y.Base();
        var widget = this.createWidget();
        this.patchWidgetConfirm(widget, false);
        widget.render();
        var link = widget.get('srcNode').one('.delete-link');
        Y.Assert.isNotNull(Y.one('#tokenkey1'));
        link.simulate('click');
        Y.Assert.isNotNull(Y.one('#tokenkey1'));
        Y.Assert.areEqual(2, widget.get('nb_tokens'));
    },

    test_createTokenFromKeys: function() {
        var widget = this.createWidget();
        var token = widget.createTokenFromKeys(
            'consumer_key', 'token_key', 'token_secret');
        Y.Assert.areEqual('consumer_key:token_key:token_secret', token);
    },

    testCreateTokenCall: function() {
        // A click on the "create a new token" link calls the API to
        // create a token.
        var mockXhr = new Y.Base();
        var fired = false;
        mockXhr.send = function(url, cfg) {
            fired = true;
            Y.Assert.areEqual(MAAS_config.uris.account_handler, url);
            Y.Assert.areEqual(
                "op=create_authorisation_token",
                cfg.data);
        };
        this.mockIO(mockXhr, module);
        var widget = this.createWidget();
        widget.render();
        var create_link = widget.get('srcNode').one('#create_token');
        create_link.simulate('click');
        Y.Assert.isTrue(fired);
    },

    testCreateTokenFail: function() {
        // If the API call to create a token fails, an error is displayed.
        var mockXhr = new Y.Base();
        var fired = false;
        mockXhr.send = function(url, cfg) {
            fired = true;
            cfg.on.failure(3);
        };
        this.mockIO(mockXhr, module);
        var widget = this.createWidget();
        widget.render();
        var create_link = widget.get('srcNode').one('#create_token');
        create_link.simulate('click');
        Y.Assert.isTrue(fired);
        Y.Assert.areEqual(
            'Unable to create a new token.',
            widget.get('srcNode').one('#create_error').get('text'));
    },

    testCreateTokenDisplay: function() {
        // When a new token is successfully created by the API, a new
        // corresponding row is added.
        var mockXhr = new Y.Base();
        var fired = false;
        mockXhr.send = function(url, cfg) {
            fired = true;
            var response = {
                consumer_key: 'consumer_key',
                token_key: 'token_key',
                token_secret: 'token_secret'
            };
            cfg.on.success(3, {response: Y.JSON.stringify(response)});
        };
        this.mockIO(mockXhr, module);
        var widget = this.createWidget();
        widget.render();
        var create_link = widget.get('srcNode').one('#create_token');
        create_link.simulate('click');
        Y.Assert.isTrue(fired);
        Y.Assert.areEqual(3, widget.get('nb_tokens'));
        Y.Assert.isNotNull(Y.one('#token_key'));
    }

}));

namespace.suite = suite;

}, '0.1', {'requires': [
    'node-event-simulate', 'node', 'test', 'maas.testing', 'maas.prefs']}
);
