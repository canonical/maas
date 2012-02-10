/* Copyright 2012 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 */

YUI({ useBrowserConsole: true }).add('maas.node.tests', function(Y) {

Y.log('loading maas.node.tests');
var namespace = Y.namespace('maas.node.tests');

var module = Y.maas.node;
var suite = new Y.Test.Suite("maas.node Tests");

suite.add(new Y.Test.Case({
    name: 'test-node',

    testNode: function() {
        var node = new module.Node({'system_id': '5'});
        Y.Assert.areSame(node.idAttribute, 'system_id');
        Y.Assert.areSame('5', node.get('system_id'));
    },

    testNodeList: function() {
        var node_list = new module.NodeList();
        Y.Assert.areSame(module.Node, node_list.model);
    }

}));

namespace.suite = suite;

}, '0.1', {'requires': [
    'node-event-simulate', 'test', 'maas.node']}
);
