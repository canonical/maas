/* Copyright 2012 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 */

YUI({ useBrowserConsole: true }).add('maas.node_views.tests', function(Y) {

Y.log('loading mass.node_views.tests');
var namespace = Y.namespace('maas.node_views.tests');

var module = Y.maas.node_views;
var suite = new Y.Test.Suite("maas.node_views Tests");

suite.add(new Y.maas.testing.TestCase({
    name: 'test-node-views-NodeListLoader',

    testInitialization: function() {
        var base_view = new Y.maas.node_views.NodeListLoader();
        this.addCleanup(function() { base_view.destroy(); });
        Y.Assert.areEqual('nodeList', base_view.modelList.name);
        Y.Assert.isFalse(base_view.nodes_loaded);
    },

    testRenderCallsLoad: function() {
        // The initial call to .render() triggers the loading of the
        // nodes.
        var mockXhr = Y.Mock();
        Y.Mock.expect(mockXhr, {
            method: 'io',
            args: [MAAS_config.uris.nodes_handler, Y.Mock.Value.Any]
        });
        this.mockIO(mockXhr, module);

        var base_view = new Y.maas.node_views.NodeListLoader();
        this.addCleanup(function() { base_view.destroy(); });
        base_view.render();
        Y.Mock.verify(mockXhr);
    },

    testDispatcherRegistered: function() {
        // The view listens to Y.maas.node_add.AddNodeDispatcher and
        // adds the published nodes to its internal this.modelList.
        var base_view = new Y.maas.node_views.NodeListLoader();
        this.addCleanup(function() { base_view.destroy(); });
        Y.maas.node_add.AddNodeDispatcher.fire(
            Y.maas.node_add.NODE_ADDED_EVENT, {},
            {system_id: '4', hostname: 'dan'});
        Y.Assert.areEqual(1, base_view.modelList.size());
        Y.Assert.areEqual('dan', base_view.modelList.item(0).get('hostname'));
    },

    testLoadNodes: function() {
        var response = Y.JSON.stringify([
               {system_id: '3', hostname: 'dan'},
               {system_id: '4', hostname: 'dee'}
           ]);
        this.mockSuccess(response, module);
        var base_view = new Y.maas.node_views.NodeListLoader();
        base_view.render();
        Y.Assert.areEqual(2, base_view.modelList.size());
        Y.Assert.areEqual('dan', base_view.modelList.item(0).get('hostname'));
        Y.Assert.areEqual('dee', base_view.modelList.item(1).get('hostname'));
    }

}));

suite.add(new Y.maas.testing.TestCase({
    name: 'test-node-views-NodeDashBoard',

    testDisplay: function() {
        var response = Y.JSON.stringify([
            {system_id: '3', hostname: 'dan'},
            {system_id: '4', hostname: 'dee'}
        ]);
        this.mockSuccess(response, module);
        var view = new Y.maas.node_views.NodesDashboard(
            {append: '#placeholder'});
        this.addCleanup(function() { view.destroy(); });
        view.render();
        Y.Assert.areEqual(
            '2 nodes in this cluster',
            Y.one('#placeholder').get('text'));
    },

    testDisplayUpdate: function() {
        // The display is updated when new nodes are added.
        this.mockSuccess(Y.JSON.stringify([]), module);
        var view = new Y.maas.node_views.NodesDashboard(
            {append: '#placeholder'});
        this.addCleanup(function() { view.destroy(); });
        view.render();
        Y.maas.node_add.AddNodeDispatcher.fire(
            Y.maas.node_add.NODE_ADDED_EVENT, {},
            {system_id: '4', hostname: 'dan'});
        Y.Assert.areEqual(1, view.modelList.size());
        Y.Assert.areEqual(
            '1 node in this cluster',
            Y.one('#placeholder').get('text'));
    }

}));


namespace.suite = suite;

}, '0.1', {'requires': [
    'node-event-simulate', 'test', 'maas.testing', 'maas.node_views']}
);
