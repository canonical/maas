/* Copyright 2012 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 */

YUI({ useBrowserConsole: true }).add('maas.node_views.tests', function(Y) {

Y.log('loading maas.node_views.tests');
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
            method: 'send',
            args: [MAAS_config.uris.nodes_handler, Y.Mock.Value.Any]
        });
        this.mockIO(mockXhr, module);

        var base_view = new Y.maas.node_views.NodeListLoader();
        this.addCleanup(function() { base_view.destroy(); });
        base_view.render();
        Y.Mock.verify(mockXhr);
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

    setUp : function () {
        this.data = [
            {system_id: 'sys1', hostname: 'host1', status: 0},
            {system_id: 'sys2', hostname: 'host2', status: 0},
            {system_id: 'sys3', hostname: 'host3', status: 1},
            {system_id: 'sys4', hostname: 'host4', status: 2},
            {system_id: 'sys5', hostname: 'host5', status: 2},
            {system_id: 'sys6', hostname: 'host6', status: 3},
            {system_id: 'sys7', hostname: 'host7', status: 4},
            {system_id: 'sys8', hostname: 'host8', status: 4},
            {system_id: 'sys9', hostname: 'host9', status: 5},
            {system_id: 'sys10', hostname: 'host10', status: 5},
            {system_id: 'sys11', hostname: 'host11', status: 5},
            {system_id: 'sys12', hostname: 'host12', status: 6},
            {system_id: 'sys13', hostname: 'host13', status: 7}
        ];
    },

    testInitializer: function() {
        var view = create_dashboard_view(this.data, this);
        this.addCleanup(function() { view.destroy(); });
        view.render();
        Y.Assert.areNotEqual(
            '',
            Y.one('#chart').get('text'),
            'The chart node should have been populated');
    },

    testHoverMouseover: function() {
        var view = create_dashboard_view(this.data, this);
        this.addCleanup(function() { view.destroy(); });
        view.render();

        // Chart hovers should be set up
        Y.one(view.chart._offline_circle[0].node).simulate('mouseover');
        this.wait(function() {
            Y.Assert.areEqual(
                '4',
                Y.one('#nodes-number').get('text'),
                'The total number of offline nodes should be set');
            Y.Assert.areEqual(
                'nodes offline',
                Y.one('#nodes-description').get('text'),
                'The text should be set with nodes as a plural');
        }, 500);
    },

    testHoverMouseout: function() {
        var view = create_dashboard_view(this.data, this);
        this.addCleanup(function() { view.destroy(); });
        view.render();

        Y.one(view.chart._offline_circle[0].node).simulate('mouseout');
        this.wait(function() {
            Y.Assert.areEqual(
                '12',
                Y.one('#nodes-number').get('text'),
                'The total number of nodes should be set');
            Y.Assert.areEqual(
                'nodes in this MAAS',
                Y.one('#nodes-description').get('text'),
                'The default text should be set');
        }, 500);
    },

    testDisplay: function() {
        var view = create_dashboard_view(this.data, this);
        this.addCleanup(function() { view.destroy(); });
        view.render();
        // The number of nodes for each status should have been set
        Y.Assert.areEqual(
            1,
            view.deployed_nodes,
            'The number of deployed nodes should have been set');
        Y.Assert.areEqual(
            2,
            view.queued_nodes,
            'The number of queued nodes should have been set');
        Y.Assert.areEqual(
            3,
            view.reserved_nodes,
            'The number of reserved nodes should have been set');
        Y.Assert.areEqual(
            4,
            view.offline_nodes,
            'The number of offline nodes should have been set');
        Y.Assert.areEqual(
            2,
            view.added_nodes,
            'The number of added nodes should have been set');
        Y.Assert.areEqual(
            1,
            view.retired_nodes,
            'The number of retired nodes should have been set');
        Y.Assert.areEqual(
            '12',
            Y.one('#nodes-number').get('text'),
            'The total number of nodes should be set');
        Y.Assert.areEqual(
            'nodes in this MAAS',
            Y.one('#nodes-description').get('text'),
            'The summary text should be set');
        Y.Assert.areEqual(
            '3 nodes reserved for named deployment.',
            Y.one('#reserved-nodes').get('text'),
            'The reserved text should be set');
        /* XXX: GavinPanella 2012-04-17 bug=984117:
         * Hidden until we support reserved nodes. */
        Y.Assert.areEqual("none", view.reservedNode.getStyle("display"));
        Y.Assert.areEqual(
            '1 retired node not represented.',
            Y.one('#retired-nodes').get('text'),
            'The retired text should be set');
        /* XXX: GavinPanella 2012-04-17 bug=984116:
         * Hidden until we support retired nodes. */
        Y.Assert.areEqual("none", view.retiredNode.getStyle("display"));
    },

    testUpdateNodeCreation: function() {
        var view = create_dashboard_view(this.data, this);
        var node = {system_id: 'sys14', hostname: 'host14', status: 0};
        this.addCleanup(function() { view.destroy(); });
        view.render();
        Y.Assert.areEqual(
            '12',
            Y.one('#nodes-number').get('text'),
            'The total number of nodes should be set');
        // Check node creation
        Y.Assert.areEqual(
            2,
            view.added_nodes,
            'Check the initial number of nodes for the status');
        Y.fire('Node.created', {instance: node});
        Y.Assert.areEqual(
            'host14',
            view.modelList.getById('sys14').get('hostname'),
            'The node should exist in the modellist');
        Y.Assert.areEqual(
            3,
            view.added_nodes,
            'The status should have one extra node');
        Y.Assert.areEqual(
            3,
            view.chart.get('added_nodes'),
            'The chart status number should also be updated');
        var self = this;
        this.wait(function() {
            Y.Assert.areEqual(
                '13',
                Y.one('#nodes-number').get('text'),
                'The total number of nodes should have been updated');
        }, 500);
    },

    testUpdateNodeUpdating: function() {
        var view = create_dashboard_view(this.data, this);
        var node = this.data[0];
        this.addCleanup(function() { view.destroy(); });
        view.render();
        node.status = 6;
        Y.Assert.areEqual(
            1,
            view.deployed_nodes,
            'Check the initial number of nodes for the new status');
        Y.fire('Node.updated', {instance: node});
        Y.Assert.areEqual(
            6,
            view.modelList.getById('sys1').get('status'),
            'The node should have been updated');
        Y.Assert.areEqual(
            2,
            view.deployed_nodes,
            'The new status should have one extra node');
        Y.Assert.areEqual(
            2,
            view.chart.get('deployed_nodes'),
            'The new chart status number should also be updated');
        Y.Assert.areEqual(
            1,
            view.added_nodes,
            'The old status count should have one less node');
        Y.Assert.areEqual(
            1,
            view.chart.get('added_nodes'),
            'The old chart status number should also be updated');
        /* XXX: Bug: 963090 This is timing dependant and causes spurious
           failures from time to time.

        this.wait(function() {
            Y.Assert.areEqual(
                Y.one('#nodes-number').get('text'),
                '12',
                'The total number of nodes should not have been updated');
        }, 500);
        */
    },

    testUpdateNodeDeleting: function() {
        var view = create_dashboard_view(this.data, this);
        var node = this.data[12];
        this.addCleanup(function() { view.destroy(); });
        view.render();
        Y.fire('Node.deleted', {instance: node});
        Y.Assert.isNull(
            view.modelList.getById('sys14'),
            'The node should have been deleted');
        Y.Assert.areEqual(
            1,
            view.deployed_nodes,
            'The status should have one less node');
        Y.Assert.areEqual(
            1,
            view.chart.get('deployed_nodes'),
            'The chart status number should also be updated');
        this.wait(function() {
            Y.Assert.areEqual(
                '12',
                Y.one('#nodes-number').get('text'),
                'The total number of nodes should have been updated');
        }, 500);
    },

    testUpdateStatus: function() {
        var view = create_dashboard_view(this.data, this);
        this.addCleanup(function() { view.destroy(); });
        view.render();
        // Add a node to a status that also updates the chart
        Y.Assert.areEqual(
            2,
            view.added_nodes,
            'Check the initial number of nodes for the status');
        var result = view.updateStatus('add', 0);
        Y.Assert.areEqual(
            3,
            view.added_nodes,
            'The status should have one extra node');
        Y.Assert.areEqual(
            3,
            view.chart.get('added_nodes'),
            'The chart status number should also be updated');
        Y.Assert.isTrue(
            result,
            'This status needs to update the chart, so it should return true');
        // Remove a node from a status
        result = view.updateStatus('remove', 0);
        Y.Assert.areEqual(
            2,
            view.added_nodes,
            'The status should have one less node');
        Y.Assert.areEqual(
            2,
            view.chart.get('added_nodes'),
            'The chart status number should also be updated');
        // Check a status that also updates text
        Y.Assert.areEqual(
            3,
            view.reserved_nodes,
            'Check the initial number of nodes for the reserved status');
        result = view.updateStatus('add', 5);
        Y.Assert.areEqual(
            4,
            view.reserved_nodes,
            'The status should have one extra node');
        Y.Assert.areEqual(
            '4 nodes reserved for named deployment.',
            Y.one('#reserved-nodes').get('text'),
            'The dashboard reserved text should be updated');
        Y.Assert.isFalse(
            result,
            'This status should not to update the chart');
    },

    testSetSummary: function() {
        // Test the default summary, with more than one node
        var data = [
            {system_id: 'sys9', hostname: 'host9', status: 5}
        ];
        var view = create_dashboard_view(data, this);
        this.addCleanup(function() { view.destroy(); });
        view.render();
        view.setSummary(false);
        Y.Assert.areEqual(
            '1',
            Y.one('#nodes-number').get('text'),
            'The total number of nodes should be set');
        Y.Assert.areEqual(
            'node in this MAAS',
            Y.one('#nodes-description').get('text'),
            'The text should be set with nodes as singular');

        // Test the default summary, with one node
        view = create_dashboard_view(this.data, this);
        view.render();
        view.setSummary(false);
        Y.Assert.areEqual(
            '12',
            Y.one('#nodes-number').get('text'),
            'The total number of nodes should be set');
        Y.Assert.areEqual(
            'nodes in this MAAS',
            Y.one('#nodes-description').get('text'),
            'The text should be set with nodes as a plural');

        // Test we can set the summary for a particular status (multiple nodes)
        view = create_dashboard_view(this.data, this);
        view.render();
        view.setSummary(false, 1, view.queued_template);
        Y.Assert.areEqual(
            '1',
            Y.one('#nodes-number').get('text'),
            'The total number of nodes should be set');
        Y.Assert.areEqual(
            'node queued',
            Y.one('#nodes-description').get('text'),
            'The text should be set with nodes as a plural');

        // Test the animation doesn't run if we have set it to run
        var fade_out_anim = false;
        var fade_in_anim = false;
        view.setSummary(false);
        this.wait(function() {
            Y.Assert.isFalse(
                fade_out_anim,
                'The fade out animation should not have run');
            Y.Assert.isFalse(
                fade_in_anim,
                'The fade in animation should not have run');
        }, 500);
    },

    testSetSummaryAnimation: function() {
        var view = create_dashboard_view(this.data, this);
        this.addCleanup(function() { view.destroy(); });
        view.render();
        var fade_out_anim = false;
        var fade_in_anim = false;
        view.fade_out.on('end', function() {
            fade_out_anim = true;
        });
        view.fade_in.on('end', function() {
            fade_in_anim = true;
        });
        view.setSummary(true);
        this.wait(function() {
            Y.Assert.isTrue(
                fade_out_anim,
                'The fade out animation should have run');
            Y.Assert.isTrue(
                fade_in_anim,
                'The fade in animation should have run');
        }, 500);
    },

    testSetNodeText: function() {
        var view = create_dashboard_view(this.data, this);
        this.addCleanup(function() { view.destroy(); });
        view.render();
        view.setNodeText(
            view.reservedNode, view.reserved_template, view.reserved_nodes);
        Y.Assert.areEqual(
            '3 nodes reserved for named deployment.',
            Y.one('#reserved-nodes').get('text'),
            'The text should be set with nodes as a plural');

        var data = [
            {system_id: 'sys9', hostname: 'host9', status: 5}
        ];
        view = create_dashboard_view(data, this);
        view.render();
        view.setNodeText(
            view.reservedNode, view.reserved_template, view.reserved_nodes);
        Y.Assert.areEqual(
            '1 node reserved for named deployment.',
            Y.one('#reserved-nodes').get('text'),
            'The text should be set with nodes as singular');
    },

    testGetNodeCount: function() {
        var view = create_dashboard_view(this.data, this);
        this.addCleanup(function() { view.destroy(); });
        view.render();
        Y.Assert.areEqual(
            12,
            view.getNodeCount(),
            'The total nodes should not return retired nodes');
    },

    tearDown : function () {
        Y.one('#chart').set('text', '');
    }
}));

function create_dashboard_view(data, self) {
    var response = Y.JSON.stringify(data);
    self.mockSuccess(response, module);
    var view = new Y.maas.node_views.NodesDashboard({
        srcNode: '#dashboard',
        summaryNode: '#summary',
        numberNode: '#nodes-number',
        descriptionNode: '#nodes-description',
        reservedNode: '#reserved-nodes',
        retiredNode: '#retired-nodes'});
    return view;
}


namespace.suite = suite;

}, '0.1', {'requires': [
    'node-event-simulate', 'test', 'maas.testing', 'maas.node_views']}
);
