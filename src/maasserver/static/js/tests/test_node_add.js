/* Copyright 2012 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 */

YUI({ useBrowserConsole: true }).add('maas.node_add.tests', function(Y) {

Y.log('loading maas.node_add.tests');
var namespace = Y.namespace('maas.node_add.tests');

var module = Y.maas.node_add;
var suite = new Y.Test.Suite("maas.node_add Tests");

suite.add(new Y.maas.testing.TestCase({
    name: 'test-node-add-widget-singleton',

    setUp: function() {
        // Silence io.
        var mockXhr = Y.Mock();
        Y.Mock.expect(mockXhr, {
            method: 'send',
            args: [MaaS_config.uris.nodes_handler, Y.Mock.Value.Any]
        });
        this.mockIO(mockXhr, module);
    },

    testSingletonCreation: function() {
        // module._add_node_singleton is originally null.
        Y.Assert.isNull(module._add_node_singleton);
        module.showAddNodeWidget();
        // module._add_node_singleton is populated after the call to
        // module.showAddNodeWidget.
        Y.Assert.isNotNull(module._add_node_singleton);
    },

    testSingletonReCreation: function() {
        module.showAddNodeWidget();
        var panel = module._add_node_singleton;

        // Make sure that a second call to showAddNodeWidget destroys
        // the old widget and creates a new one.
        var destroyed = false;
        panel.on("destroy", function(){
            destroyed = true;
        });
        module.showAddNodeWidget();
        Y.Assert.isTrue(destroyed);
        Y.Assert.isNotNull(module._add_node_singleton);
        Y.Assert.areNotSame(panel, namespace._add_node_singleton);
    }

}));

suite.add(new Y.maas.testing.TestCase({
    name: 'test-add-node-widget-add-node',

    testAddNodeAPICall: function() {
        var mockXhr = Y.Mock();
        Y.Mock.expect(mockXhr, {
            method: 'send',
            args: [MaaS_config.uris.nodes_handler, Y.Mock.Value.Any]
        });
        this.mockIO(mockXhr, module);
        module.showAddNodeWidget();
        var panel = module._add_node_singleton;
        panel.get('srcNode').one('#id_hostname').set('value', 'host');
        var button = panel.get('srcNode').one('.yui3-button');
        button.simulate('click');
        Y.Mock.verify(mockXhr);
    },

    testAddNodeAPICallEnterPressed: function() {
        var mockXhr = Y.Mock();
        Y.Mock.expect(mockXhr, {
            method: 'send',
            args: [MaaS_config.uris.nodes_handler, Y.Mock.Value.Any]
        });
        this.mockIO(mockXhr, module);
        module.showAddNodeWidget();
        var panel = module._add_node_singleton;
        panel.get('srcNode').one('#id_hostname').set('value', 'host');
        var form = panel.get('srcNode').one('form');
        // Simulate 'Enter' being pressed.
        form.simulate("keypress", { keyCode: 13 });
        Y.Mock.verify(mockXhr);
    },

    testNodeidPopulation: function() {
        var mockXhr = new Y.Base();
        mockXhr.send = function(url, cfg) {
            cfg.on.success(3, {response: Y.JSON.stringify({system_id: 3})});
        };
        this.mockIO(mockXhr, module);
        module.showAddNodeWidget();
        this.addCleanup(
            Y.bind(
                module._add_node_singleton.destroy,
                module._add_node_singleton));
        var panel = module._add_node_singleton;
        panel.get('srcNode').one('#id_hostname').set('value', 'host');
        var button = panel.get('srcNode').one('.yui3-button');

        var fired = false;
        this.registerListener(
            Y.maas.node_add.AddNodeDispatcher, module.NODE_ADDED_EVENT,
            function(e, node){
                Y.Assert.areEqual(3, node.system_id);
                fired = true;
            }
        );
        button.simulate('click');
        Y.Assert.isTrue(fired);
    },

    testGenericErrorMessage: function() {
        var mockXhr = new Y.Base();
        mockXhr.send = function(url, cfg) {
            cfg.on.failure(3, {status: 500});
        };
        this.mockIO(mockXhr, module);
        module.showAddNodeWidget();
        var panel = module._add_node_singleton;
        panel.get('srcNode').one('#id_hostname').set('value', 'host');
        var button = panel.get('srcNode').one('.yui3-button');
        button.simulate('click');
        var error_message = panel.get(
            'srcNode').one('.form-global-errors').get('innerHTML');
        var message_position = error_message.search("Unable to create Node.");
        Y.Assert.areNotEqual(-1, error_message);
    },

    testLoggedOffErrorMessage: function() {
        var mockXhr = new Y.Base();
        mockXhr.send = function(url, cfg) {
            cfg.on.failure(3, {status: 401});
        };
        this.mockIO(mockXhr, module);
        module.showAddNodeWidget();
        var panel = module._add_node_singleton;
        panel.get('srcNode').one('#id_hostname').set('value', 'host');
        var button = panel.get('srcNode').one('.yui3-button');
        button.simulate('click');
        var error_message = panel.get(
            'srcNode').one('.form-global-errors').get('innerHTML');
        // The link to the login page is present in the error message.
        var link_position = error_message.search(MaaS_config.uris.login);
        Y.Assert.areNotEqual(-1, link_position);
    }

}));

namespace.suite = suite;

}, '0.1', {'requires': [
    'node-event-simulate', 'test', 'maas.testing', 'maas.node_add']}
);
