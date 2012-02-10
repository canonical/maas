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

    testInitializer: function() {
        var widget = new module.TokenWidget({srcNode: '#placeholder'});
        this.addCleanup(function() { widget.destroy(); });
        widget.render();
        var regenerate_link = widget.get('srcNode').one('#regenerate_tokens');
        Y.Assert.isNotNull(regenerate_link);
        Y.Assert.areEqual(
            "Regenerate the tokens", regenerate_link.get('text'));
        var status_node = widget.get('srcNode').one('#regenerate_error');
        Y.Assert.isNotNull(status_node);
    },

    testRegenerateTokensCall: function() {
        var mockXhr = Y.Mock();
        Y.Mock.expect(mockXhr, {
            method: 'io',
            args: [MAAS_config.uris.account_handler, Y.Mock.Value.Any]
        });
        this.mockIO(mockXhr, module);
        var widget = new module.TokenWidget({srcNode: '#placeholder'});
        this.addCleanup(function() { widget.destroy(); });
        widget.render();
        var link = widget.get('srcNode').one('#regenerate_tokens');
        link.simulate('click');
        Y.Mock.verify(mockXhr);
    },

    testRegenerateTokensUpdatesTokens: function() {
        var mockXhr = new Y.Base();
        mockXhr.io = function(url, cfg) {
            var response = {
                token_key: 'token_key', token_secret: 'token_secret',
                consumer_key: 'consumer_key'};
            cfg.on.success(3, {response: Y.JSON.stringify(response)});
        };
        this.mockIO(mockXhr, module);
        var widget = new module.TokenWidget({srcNode: '#placeholder'});
        widget.render();
        var link = widget.get('srcNode').one('#regenerate_tokens');
        link.simulate('click');
        var src_node = widget.get('srcNode');
        Y.Assert.areEqual('token_key', src_node.one('#token_key').get('text'));
        Y.Assert.areEqual(
            'token_secret', src_node.one('#token_secret').get('text'));
        Y.Assert.areEqual(
            'consumer_key', src_node.one('#consumer_key').get('text'));
     }

}));

namespace.suite = suite;

}, '0.1', {'requires': [
    'node-event-simulate', 'node', 'test', 'maas.testing', 'maas.prefs']}
);
