/* Copyright 2012 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 */

YUI({ useBrowserConsole: true }).add('maas.add_node.tests', function(Y) {

Y.log('loading mass.add_node.tests');
var namespace = Y.namespace('maas.add_node.tests');

var module = Y.maas.add_node;
var suite = new Y.Test.Suite("maas.add_node Tests");

suite.add(new Y.Test.Case({
    name: 'test-add-node-widget-singleton',

    setUp: function() {
        // Silence io.
        var mockXhr = Y.Mock();
        Y.Mock.expect(mockXhr, {
            method: 'io',
            args: [MAAS_config.uris.nodes_handler, Y.Mock.Value.Any]
        });
        this.old_io = module._io;
        module._io = mockXhr;
    },

    tearDown: function() {
        module._io = this.old_io;
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
        var overlay = module._add_node_singleton;

        // Make sure that a second call to showAddNodeWidget destroys
        // the old widget and creates a new one.
        var destroyed = false;
        overlay.on("destroy", function(){
            destroyed = true;
        });
        module.showAddNodeWidget();
        Y.Assert.isTrue(destroyed);
        Y.Assert.isNotNull(module._add_node_singleton);
        Y.Assert.areNotSame(overlay, namespace._add_node_singleton);
    }

}));

suite.add(new Y.Test.Case({
    name: 'test-add-node-widget-add-node',

    mockIO: function(mock) {
        this.old_io = module._io;
        module._io = mock;
    },

    tearDown: function() {
        if (Y.Lang.isValue(this.old_io)) {
            module._io = this.old_io;
        }
    },

    testAddNodeAPICall: function() {
        var mockXhr = Y.Mock();
        Y.Mock.expect(mockXhr, {
            method: 'io',
            args: [MAAS_config.uris.nodes_handler, Y.Mock.Value.Any]
        });
        this.mockIO(mockXhr);
        module.showAddNodeWidget();
        var overlay = module._add_node_singleton;
        overlay.get('srcNode').one('#id_hostname').set('value', 'host');
        var button = overlay.get('srcNode').one('button');
        button.simulate('click');
        Y.Mock.verify(mockXhr);
    },

    testNodeidPopulation: function() {
        var mockXhr = new Y.Base();
        mockXhr.io = function(url, cfg) {
            cfg.on.success(
               3,
               {response: Y.JSON.stringify({system_id: 3})});
        };
        this.mockIO(mockXhr);
        module.showAddNodeWidget();
        var overlay = module._add_node_singleton;
        overlay.get('srcNode').one('#id_hostname').set('value', 'host');
        var button = overlay.get('srcNode').one('button');

        var fired = false;
        var handle = module.AddNodeDispatcher.on(
            module.NODE_ADDED_EVENT, function(e, node){
            Y.Assert.areEqual(3, node.system_id);
            fired = true;
        });
        try {
            button.simulate('click');
        }
        finally {
            handle.detach();
        }
        Y.Assert.isTrue(fired);
    }

}));

namespace.suite = suite;

}, '0.1', {'requires': [
    'node-event-simulate', 'test', 'maas.add_node']}
);
