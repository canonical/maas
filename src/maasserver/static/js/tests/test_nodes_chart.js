/* Copyright 2012 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 */

YUI({ useBrowserConsole: true }).add('maas.nodes_chart.tests', function(Y) {

Y.log('loading maas.nodes_chart.tests');
var namespace = Y.namespace('maas.nodes_chart.tests');

var module = Y.maas.nodes_chart;
var suite = new Y.Test.Suite("maas.nodes_chart Tests");

var initialStats = {
    allocated: 5,
    commissioned: 6,
    queued: 2,
    offline: 3,
    added: 10
};

suite.add(new Y.maas.testing.TestCase({
    name: 'test-nodes-chart-widget-creation',

    setUp : function () {
        var stats = new Y.maas.node.NodeStats(initialStats);
        this.chart = new module.NodesChartWidget(
            {node_id: 'chart', width: 300, stats: stats});
    },

    testCreation: function() {
        Y.assert(
            Y.one('#chart').get('text'),
            'The target node should be populated with the chart');
        // Check we created the svg nodes
        Y.assert(this.chart._outer_paths[0].node);
        Y.assert(this.chart._outer_paths[1].node);
        Y.assert(this.chart._outer_paths[2].node);
        Y.assert(this.chart._offline_circle[0].node);
        Y.assert(this.chart._added_circle[0].node);
    },

    tearDown : function () {
        Y.one('#chart').empty();
    }
}));

suite.add(new Y.maas.testing.TestCase({
    name: 'test-nodes-chart-events',

    setUp : function () {
        var stats = new Y.maas.node.NodeStats(initialStats);
        this.chart = new module.NodesChartWidget(
            {node_id: 'chart', width: 300, stats: stats});
    },

    testWidgetHover: function() {
        var events = [
            {
                event: 'hover.allocated.over',
                action: 'mouseover',
                fired: false,
                nodes: initialStats.allocated,
                node: this.chart._outer_paths[0].node
                },
            {
                event: 'hover.allocated.out',
                action: 'mouseout',
                fired: false,
                node: this.chart._outer_paths[0].node
                },
            {
                event: 'hover.commissioned.over',
                action: 'mouseover',
                fired: false,
                nodes: initialStats.commissioned,
                node: this.chart._outer_paths[1].node
                },
            {
                event: 'hover.commissioned.out',
                action: 'mouseout',
                fired: false,
                node: this.chart._outer_paths[1].node
                },
            {
                event: 'hover.queued.over',
                action: 'mouseover',
                fired: false,
                nodes: initialStats.queued,
                node: this.chart._outer_paths[2].node
                },
            {
                event: 'hover.queued.out',
                action: 'mouseout',
                fired: false,
                node: this.chart._outer_paths[2].node
                },
            {
                event: 'hover.offline.over',
                action: 'mouseover',
                fired: false,
                nodes: initialStats.offline,
                node: this.chart._offline_circle[0].node
                },
            {
                event: 'hover.offline.out',
                action: 'mouseout',
                fired: false,
                node: this.chart._offline_circle[0].node
                },
            {
                event: 'hover.added.over',
                action: 'mouseover',
                fired: false,
                nodes: initialStats.added,
                node: this.chart._added_circle[0].node
                },
            {
                event: 'hover.added.out',
                action: 'mouseout',
                fired: false,
                node: this.chart._added_circle[0].node
                }
            ];

        Y.Array.each(events, function(event) {
            this.chart.on(event.event, function(e, event) {
                event.fired = true;
                event.e = e;
            }, null, event);
            Y.one(event.node).simulate(event.action);
            Y.Assert.isTrue(
                event.fired,
                'Event ' + event.event + ' should have fired');
            if (event.nodes) {
                Y.Assert.areEqual(event.e.nodes, event.nodes);
            }
        }, this);
    },

    tearDown : function () {
        Y.one('#chart').empty();
    }
}));

namespace.suite = suite;

}, '0.1', {'requires': [
    'node-event-simulate', 'test', 'maas.testing', 'maas.nodes_chart',
    'maas.node']}
);
