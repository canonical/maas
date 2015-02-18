/* Copyright 2012 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 */

YUI({ useBrowserConsole: true }).add('maas.node_views.tests', function(Y) {

Y.log('loading maas.node_views.tests');
var namespace = Y.namespace('maas.node_views.tests');

var module = Y.maas.node_views;
var suite = new Y.Test.Suite("maas.node_views Tests");

suite.add(new Y.maas.testing.TestCase({
    name: 'test-node-views-NodeView',

    setUp : function () {
        Y.one('#placeholder').empty();
        this.data = {
            id: 1,
            system_id: 'sys1',
            fqdn: 'host1.local',
            status: 'Ready',
            owner: '',
            events: {
                total: 5,
                count: 2,
                more_url: '/nodes/sys1/events',
                events: [
                    {
                        id: 5,
                        level: "WARN",
                        type: "Power failure",
                        description: "Failed to power on.",
                        created: "11/12/14"
                    },
                    {
                        id: 4,
                        level: "INFO",
                        type: "Node changed status",
                        description: "Ready to Allocated",
                        created: "11/11/14"
                    }
                ]
            },
            action_view: '<form id="node_actions"></form>'
        };
    },

    /**
     * Create a view, hook the NodeView into it, and arrange for cleanup.
     *
     * The "data" parameter defaults to this.data.
     */
    makeNodeView: function(data) {
        if (data === undefined) {
            data = this.data;
        }

        // Create the main content
        var content = Y.Node.create('<div />')
            .set('id', data.id)
            .setAttribute('data-system-id', data.system_id);
        var fqdn = Y.Node.create('<div />')
            .set('id', 'fqdn')
            .setAttribute('data-field', 'fqdn');
        var status = Y.Node.create('<div />')
            .set('id', 'status')
            .setAttribute('data-field', 'status');
        var owner = Y.Node.create('<div />')
            .set('id', 'owner')
            .setAttribute('data-field', 'owner')
            .setAttribute('data-field-if', 'hidden');
        var action_view = Y.Node.create('<div />')
            .set('id', 'action_view');
        var events_list = Y.Node.create('<div />')
            .set('id', 'events_list');
        content.append(fqdn);
        content.append(status);
        content.append(owner);
        content.append(action_view);
        content.append(events_list);
        Y.one('#placeholder').append(content);

        var response = Y.JSON.stringify(data);
        var view = new Y.maas.node_views.NodeView({
            srcNode: Y.one('#placeholder'),
            eventList: '#events_list',
            actionView: '#action_view'
        });
        view.loadNode(response);
        this.addCleanup(function() { view.destroy(); });
        return view;
    },

    testInitializer: function() {
        var view = this.makeNodeView();
        Y.Assert.areEqual(
            this.data.fqdn,
            view.srcNode.one('#fqdn').get('text'),
            "The fqdn was not set.");
        Y.Assert.areEqual(
            this.data.status,
            view.srcNode.one('#status').get('text'),
            "The status was not set.");
        Y.Assert.isTrue(
            view.srcNode.one('#owner').hasClass('hidden'),
            "The owner div was not hidden.");
        Y.Assert.areEqual(
            1, view.srcNode.one('#action_view').all('form').size(),
            "The content of action_view was not placed.");
        Y.Assert.areEqual(
            1, view.srcNode.one('#events_list').all('table').size(),
            "The table was not created in events_list.");
        Y.Assert.isObject(
            view.powerChecker,
            "Failed to load PowerCheckWidget.");
    },

    testRender_updates_field_data: function() {
        var view = this.makeNodeView();
        view.node.fqdn = 'new-hostname.new';
        view.node.status = 'allocated';
        view.render();
        Y.Assert.areEqual(
            view.node.fqdn,
            view.srcNode.one('#fqdn').get('text'),
            "The fqdn was not set.");
        Y.Assert.areEqual(
            view.node.status,
            view.srcNode.one('#status').get('text'),
            "The status was not set.");
    },

    testRender_shows_owner_field: function() {
        var view = this.makeNodeView();
        view.node.owner = 'owner';
        view.render();
        Y.Assert.isFalse(
            view.srcNode.one('#owner').hasClass('hidden'),
            "The owner div was not shown.");
    },

    testRender_updates_action_view: function() {
        var view = this.makeNodeView();
        view.node.action_view = '<div id="new-action-div">new</div>';
        view.render();
        Y.Assert.areEqual(
            'new',
            view.srcNode.one('#action_view').one('#new-action-div').get('text'),
            "The content of action_view was not replaced.");
    },

    testRender_shows_no_events_for_empty_events: function() {
        var view = this.makeNodeView();
        view.node.events = {
            total: 0,
            count: 0,
            events: []
        };
        view.render();
        Y.Assert.areEqual(
            'No events',
            view.srcNode.one('#events_list').one('div').get('text'),
            "The event list didn't render 'No events'.");
    },

    testRender_creates_event_rows_for_all_events: function() {
        var view = this.makeNodeView();
        view.render();
        Y.Assert.areEqual(
            view.node.events.count,
            view.srcNode.one('#events_list').one('tbody').all('tr').size(),
            "The event list didn't contain the correct number of rows.");
    },

    testRender_adds_event_list_table_header: function() {
        var view = this.makeNodeView();
        view.render();
        Y.Assert.isObject(
            view.srcNode.one('#events_list').one('thead'),
            "The event list is missing the table header.");
    },

    testRender_creates_event_row: function() {
        var view = this.makeNodeView();
        view.node.events = {
            total: 1,
            count: 1,
            events: [
                {
                    id: 1,
                    level: "WARN",
                    type: "Power failure",
                    description: "Failed to power on.",
                    created: "11/12/14"
                }
            ]
        };
        view.render();

        tableRow = view.srcNode.one('#events_list').one('tbody').one('tr');
        tableCols = tableRow.all('td');
        Y.Assert.areEqual(
            "node-event-1", tableRow.get('id'),
            "The event row is missing the correct id.");
        Y.Assert.isTrue(
            tableRow.hasClass("warn"),
            "The event row is missing the level class.");
        Y.Assert.areEqual(
            "WARN", tableCols.item(0).get('text'),
            "The event row level column doesn't match event data.");
        Y.Assert.areEqual(
            "11/12/14", tableCols.item(1).get('text'),
            "The event row created column doesn't match event data.");
        Y.Assert.areEqual(
            "Power failure \u2014 Failed to power on.",
            tableCols.item(2).get('text'),
            "The event row description column doesn't match event data.");
    },

    testRender_shows_more_events_link: function() {
        var view = this.makeNodeView();
        view.render();
        Y.Assert.areEqual(
            view.node.events.more_url,
            view.srcNode.one('#events_list').one('a').getAttribute('href'),
            "The event list more link has incorrect href.");
        Y.Assert.areEqual(
            'Full node event log (' + view.node.events.total + ' events).',
            view.srcNode.one('#events_list').one('a').get('text'),
            "The event list more link has incorrect text.");
    },

    testRender_renders_PowerCheckWidget: function() {
        var view = this.makeNodeView();
        view.render();
        Y.Assert.isObject(
            view.actionView.one('button[value="check-powerstate"]'),
            "Failed to render the PowerCheckWidget.");
    }

}));

function create_dashboard_view(data, self, root_node_descriptor) {
    var response = Y.JSON.stringify(data);
    var view = new Y.maas.node_views.NodesDashboard({
        srcNode: root_node_descriptor,
        summaryNode: '#summary',
        numberNode: '#nodes-number',
        descriptionNode: '#nodes-description',
        reservedNode: '#reserved-nodes',
        retiredNode: '#retired-nodes'});
    view.loadNodes(response);
    return view;
}


namespace.suite = suite;

}, '0.1', {'requires': [
    'node-event-simulate', 'test', 'maas.testing', 'maas.enums',
    'maas.node_views']}
);
