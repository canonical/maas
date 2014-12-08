/* Copyright 2012 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 */

YUI({ useBrowserConsole: true }).add('maas.node_views.tests', function(Y) {

Y.log('loading maas.node_views.tests');
var namespace = Y.namespace('maas.node_views.tests');

var module = Y.maas.node_views;
var suite = new Y.Test.Suite("maas.node_views Tests");


// Dump this HTML into #placeholder to get DOM hooks for the dashboard.
var dashboard_hooks = Y.one('#dashboard-hooks').getContent();


suite.add(new Y.maas.testing.TestCase({
    name: 'test-node-views-NodeListLoader',

    exampleNodes: [
        {system_id: '3', hostname: 'dan'},
        {system_id: '4', hostname: 'dee'}
    ],

    makeNodeListLoader: function() {
        var view = new Y.maas.node_views.NodeListLoader();
        this.addCleanup(Y.bind(view.destroy, view));
        return view;
    },

    testInitialization: function() {
        var view = this.makeNodeListLoader();
        Y.Assert.areEqual('nodeList', view.modelList.name);
    },

    testRenderDoesNotCallLoad: function() {
        // The initial call to .render() does *not* trigger the loading
        // of the nodes.
        var self = this;

        var mockXhr = Y.Mock();
        Y.Mock.expect(mockXhr, {
            method: 'send',
            args: [MAAS_config.uris.nodes_handler, Y.Mock.Value.Any],
            run: function(uri, cfg) {
                var out = new Y.Base();
                out.response = Y.JSON.stringify(self.exampleNodes);
                cfg.on.success(Y.guid(), out);
            }
        });
        this.mockIO(mockXhr, module);

        var view = this.makeNodeListLoader();

        view.render();
        // The model list has not been populated.
        Y.Assert.areEqual(0, view.modelList.size());
    },

    testAddLoader: function() {
        // A mock loader.
        var loader = new Y.Base();

        // Capture event registrations.
        var events = {};
        loader.on = function(event, callback) {
            events[event] = callback;
        };

        var view = this.makeNodeListLoader();
        view.addLoader(loader);

        // Several events are registered.
        Y.Assert.areSame(view.loadNodesStarted, events["io:start"]);
        Y.Assert.areSame(view.loadNodesEnded, events["io:end"]);
        Y.Assert.areSame(view.loadNodesFailed, events["io:failure"]);
        Y.Assert.isFunction(events["io:success"]);
    },

    testLoadNodes: function() {
        var response = Y.JSON.stringify(this.exampleNodes);
        var view = this.makeNodeListLoader();
        view.loadNodes(response);
        Y.Assert.isTrue(view.loaded);
        Y.Assert.areEqual(2, view.modelList.size());
        Y.Assert.areEqual('dan', view.modelList.item(0).get('hostname'));
        Y.Assert.areEqual('dee', view.modelList.item(1).get('hostname'));
    },

    testLoadNodes_invalid_data: function() {
        var response = "{garbled data}";
        var view = this.makeNodeListLoader();

        var loadNodesFailedCalled = false;
        view.loadNodesFailed = function() {
            loadNodesFailedCalled = true;
        };

        view.loadNodes(response);
        Y.Assert.isTrue(view.loaded);
        Y.Assert.areEqual(0, view.modelList.size());
        Y.Assert.isTrue(loadNodesFailedCalled);
    },

    assertModelListMatchesNodes: function(modelList, nodes) {
        Y.Assert.areEqual(nodes.length, modelList.size());
        Y.Array.each(nodes, function(node) {
            var model = modelList.getById(node.system_id);
            Y.Assert.isObject(model);
            Y.Assert.areEqual(node.hostname, model.get("hostname"));
            Y.Assert.areEqual(node.status, model.get("status"));
        });
    },

    test_mergeNodes_when_modelList_is_empty: function() {
        var view = this.makeNodeListLoader();
        var nodes = [
            {system_id: "1", hostname: "host1", status: 1},
            {system_id: "2", hostname: "host2", status: 2},
            {system_id: "3", hostname: "host3", status: 3}
        ];
        Y.Assert.areEqual(0, view.modelList.size());
        view.mergeNodes(nodes);
        this.assertModelListMatchesNodes(view.modelList, nodes);
    },

    test_mergeNodes_when_modelList_is_not_empty: function() {
        var view = this.makeNodeListLoader();
        var nodes_before = [
            {system_id: "1", hostname: "host1", status: 1},
            {system_id: "3", hostname: "host3", status: 3}
        ];
        var nodes_after = [
            {system_id: "1", hostname: "host1after", status: 11},
            {system_id: "2", hostname: "host2after", status: 22}
        ];
        view.mergeNodes(nodes_before);
        this.assertModelListMatchesNodes(view.modelList, nodes_before);
        view.mergeNodes(nodes_after);
        this.assertModelListMatchesNodes(view.modelList, nodes_after);
    },

    test_mergeNodes_events: function() {
        var view = this.makeNodeListLoader();
        var events = [];
        view.modelList.after(
            ["add", "remove", "*:change", "reset"],
            Y.bind(events.push, events));

        var getEventType = function(e) { return e.type; };

        var nodes_before = [
            {system_id: "1", hostname: "host1", status: 1},
            {system_id: "3", hostname: "host3", status: 3}
        ];
        view.mergeNodes(nodes_before);
        Y.ArrayAssert.itemsAreSame(
            ["nodeList:add", "nodeList:add"],
            Y.Array.map(events, getEventType));

        var nodes_after = [
            {system_id: "1", hostname: "host1after", status: 11},
            {system_id: "2", hostname: "host2after", status: 22}
        ];
        view.mergeNodes(nodes_after);
        Y.ArrayAssert.itemsAreSame(
            ["nodeList:add", "nodeList:add", "nodeModel:change",
             "nodeList:add", "nodeList:remove"],
            Y.Array.map(events, getEventType));
    }

}));

suite.add(new Y.maas.testing.TestCase({
    name: 'test-node-views-NodeDashBoard',

    setUp : function () {
        Y.one('#placeholder').empty();
        var NODE_STATUS = Y.maas.enums.NODE_STATUS;
        this.data = [
            {
                system_id: 'sys1',
                hostname: 'host1',
                status: NODE_STATUS.NEW
            },
            {
                system_id: 'sys2',
                hostname: 'host2',
                status: NODE_STATUS.NEW
            },
            {
                system_id: 'sys3',
                hostname: 'host3',
                status: NODE_STATUS.COMMISSIONING
            },
            {
                system_id: 'sys4',
                hostname: 'host4',
                status: NODE_STATUS.FAILED_COMMISSIONING
            },
            {
                system_id: 'sys5',
                hostname: 'host5',
                status: NODE_STATUS.FAILED_COMMISSIONING
            },
            {
                system_id: 'sys6',
                hostname: 'host6',
                status: NODE_STATUS.MISSING
            },
            {
                system_id: 'sys7',
                hostname: 'host7',
                status: NODE_STATUS.READY
            },
            {
                system_id: 'sys8',
                hostname: 'host8',
                status: NODE_STATUS.READY
            },
            {
                system_id: 'sys9',
                hostname: 'host9',
                status: NODE_STATUS.RESERVED
            },
            {
                system_id: 'sys10',
                hostname: 'host10',
                status: NODE_STATUS.RESERVED
            },
            {
                system_id: 'sys11',
                hostname: 'host11',
                status: NODE_STATUS.RESERVED
            },
            {
                system_id: 'sys12',
                hostname: 'host12',
                status: NODE_STATUS.ALLOCATED
            },
            {
                system_id: 'sys13',
                hostname: 'host13',
                status: NODE_STATUS.RETIRED
            }
        ];
    },

    /**
     * Counter to generate unique numbers.
     */
    counter: 0,

    /**
     * Get next value of this.counter, and increment.
     */
    getNumber: function() {
        return this.counter++;
    },

    /**
     * Create a dashboard view, render it, and arrange for its cleanup.
     *
     * The "data" parameter defaults to this.data.
     */
    makeDashboard: function(data) {
        if (data === undefined) {
            data = this.data;
        }
        var root_node_id = 'widget-' + this.getNumber().toString();
        var new_dash = Y.Node.create('<div />').set('id', root_node_id);
        this.addCleanup(function() { new_dash.remove(); });
        new_dash.append(Y.Node.create(dashboard_hooks));
        Y.one('#placeholder').append(new_dash);
        var view = create_dashboard_view(data, this, '#' + root_node_id);
        this.addCleanup(function() { view.destroy(); });
        return view;
    },

    testInitializer: function() {
        var view = this.makeDashboard();
        Y.Assert.areNotEqual(
            '',
            view.srcNode.one('#chart').get('text'),
            "The chart node should have been populated.");
    },

    testHoverMouseover: function() {
        var self = this;
        var view = this.makeDashboard();
        var number_node = view.srcNode.one('#nodes-number');
        var description_node = view.srcNode.one('#nodes-description');

        // The dashboard sets up hover actions on the chart.  Hovering over a
        // chart segment causes its stats to fade in.
        view.fade_in.on('end', function() {
            self.resume(function() {
                Y.Assert.areEqual(
                    '4',
                    number_node.get('text'),
                    "The total number of offline nodes should be set.");
                Y.Assert.areEqual(
                    'nodes offline',
                    description_node.get('text'),
                    "The text should be set with nodes as a plural.");
            });
        });

        Y.one(view.chart._offline_circle[0].node).simulate(
            'mouseover');
        this.wait();
    },

    testHoverMouseout: function() {
        var self = this;
        var view = this.makeDashboard();
        var number_node = view.srcNode.one('#nodes-number');
        var description_node = view.srcNode.one('#nodes-description');

        view.fade_in.on('end', function() {
            self.resume(function() {
                Y.Assert.areEqual(
                    '12',
                    number_node.get('text'),
                    "The total number of nodes should be set.");
                Y.Assert.areEqual(
                    'nodes in this MAAS',
                    description_node.get('text'),
                    "The default text should be set.");
            });
        });
        Y.one(view.chart._offline_circle[0].node).simulate('mouseout');
        this.wait();
    },

    testDisplay: function() {
        var view = this.makeDashboard();
        // The number of nodes for each status should have been set
        Y.Assert.areEqual(
            1,
            view.stats.get("allocated"),
            "The number of allocated nodes should have been set.");
        Y.Assert.areEqual(
            2,
            view.stats.get("queued"),
            "The number of queued nodes should have been set.");
        Y.Assert.areEqual(
            3,
            view.stats.get("reserved"),
            "The number of reserved nodes should have been set.");
        Y.Assert.areEqual(
            4,
            view.stats.get("offline"),
            "The number of offline nodes should have been set.");
        Y.Assert.areEqual(
            2,
            view.stats.get("added"),
            "The number of added nodes should have been set.");
        Y.Assert.areEqual(
            1,
            view.stats.get("retired"),
            "The number of retired nodes should have been set.");
        Y.Assert.areEqual(
            '12',
            view.srcNode.one('#nodes-number').get('text'),
            "The total number of nodes should be set.");
        Y.Assert.areEqual(
            "nodes in this MAAS",
            view.srcNode.one('#nodes-description').get('text'),
            "The summary text should be set.");
        Y.Assert.areEqual(
            "3 nodes reserved for named deployment.",
            view.srcNode.one('#reserved-nodes').get('text'),
            "The reserved text should be set.");
        // XXX: GavinPanella 2012-04-17 bug=984117:
        // Hidden until we support reserved nodes.
        Y.Assert.areEqual("none", view.reservedNode.getStyle("display"));
        Y.Assert.areEqual(
            "1 retired node not represented.",
            view.srcNode.one('#retired-nodes').get('text'),
            "The retired text should be set.");
        // XXX: GavinPanella 2012-04-17 bug=984116:
        // Hidden until we support retired nodes.
        Y.Assert.areEqual("none", view.retiredNode.getStyle("display"));
    },

    testUpdateWhenNodeAdded: function() {
        var self = this;
        var view = this.makeDashboard();
        var node = {
            system_id: 'sys14',
            hostname: 'host14',
            status: Y.maas.enums.NODE_STATUS.NEW
        };
        var number_node = view.srcNode.one('#nodes-number');
        Y.Assert.areEqual(
            '12',
            number_node.get('text'),
            "The total number of nodes should be set.");

        // Check node creation.
        Y.Assert.areEqual(
            2,
            view.stats.get("added"),
            "Check the initial number of nodes for the status.");

        view.fade_in.on('end', function() { self.resume(function() {
                Y.Assert.areEqual(
                    'host14',
                    view.modelList.getById('sys14').get('hostname'),
                    "The node should exist in the modellist.");
                Y.Assert.areEqual(
                    3,
                    view.stats.get("added"),
                    "The status should have one extra node.");
                Y.Assert.areEqual(
                    '13',
                    number_node.get('text'),
                    "The total number of nodes should have been updated.");
            });
        });

        // Add a node.
        view.modelList.add(node);

        this.wait();
    },

    testUpdateWhenNodeUpdated: function() {
        var self = this;
        var view = this.makeDashboard();
        var node = this.data[0];
        var number_node = view.srcNode.one('#nodes-number');
        node.status = Y.maas.enums.NODE_STATUS.ALLOCATED;
        Y.Assert.areEqual(
            1,
            view.stats.get("allocated"),
            "Check the initial number of nodes for the new status.");

        // Update a node.
        view.modelList.getById('sys1').set(
            'status', Y.maas.enums.NODE_STATUS.DEPLOYED);

        Y.Assert.areEqual(
            Y.maas.enums.NODE_STATUS.DEPLOYED,
            view.modelList.getById('sys1').get('status'),
            "The node should have been updated.");
        Y.Assert.areEqual(
            2,
            view.stats.get("allocated"),
            "The new status should have one extra node.");
        Y.Assert.areEqual(
            1,
            view.stats.get("added"),
            "The old status count should have one less node.");

        Y.Assert.areEqual(
            number_node.get('text'),
            '12',
            "The total number of nodes should not have been updated.");
    },

    testUpdateWhenNodeDeleted: function() {
        var self = this;
        var view = this.makeDashboard();
        var node = this.data[12];
        var number_node = view.srcNode.one('#nodes-number');

        view.fade_in.on('end', function() {
            self.resume(function() {
                Y.Assert.isNull(
                    view.modelList.getById('sys14'),
                    "The node should have been deleted.");
                Y.Assert.areEqual(
                    1,
                    view.stats.get("allocated"),
                    "The status should have one less node.");
                Y.Assert.areEqual(
                    '12',
                    number_node.get('text'),
                    "The total number of nodes should have been updated.");
            });
        });

        // Delete a node.
        var node_model_to_delete = view.modelList.getById(node.system_id);
        view.modelList.remove(node_model_to_delete);

        this.wait();
    },

    testUpdateStatus: function() {
        var view = this.makeDashboard();
        var reserved_node = view.srcNode.one('#reserved-nodes');
        // Add a node to a status that also updates the chart
        Y.Assert.areEqual(
            2,
            view.stats.get("added"),
            "Check the initial number of nodes for the status.");
        view.updateStatus('add', Y.maas.enums.NODE_STATUS.NEW);
        Y.Assert.areEqual(
            3,
            view.stats.get("added"),
            "The status should have one extra node.");
        // Remove a node from a status
        view.updateStatus('remove', Y.maas.enums.NODE_STATUS.NEW);
        Y.Assert.areEqual(
            2,
            view.stats.get("added"),
            "The status should have one less node.");
        // Check a status that also updates text
        Y.Assert.areEqual(
            3,
            view.stats.get("reserved"),
            "Check the initial number of nodes for the reserved status.");
        view.updateStatus('add', Y.maas.enums.NODE_STATUS.RESERVED);
        Y.Assert.areEqual(
            4,
            view.stats.get("reserved"),
            "The status should have one extra node.");
        Y.Assert.areEqual(
            "4 nodes reserved for named deployment.",
            reserved_node.get('text'),
            "The dashboard reserved text should be updated.");
    },

    testSetSummary: function() {
        // Test the default summary, with more than one node
        var data = [{
            system_id: 'sys9',
            hostname: 'host9',
            status: Y.maas.enums.NODE_STATUS.RESERVED
            }];
        var view = this.makeDashboard(data);
        view.setSummary(false);
        Y.Assert.areEqual(
            '1',
            view.srcNode.one('#nodes-number').get('text'),
            "The total number of nodes should be set.");
        Y.Assert.areEqual(
            'node in this MAAS',
            view.srcNode.one('#nodes-description').get('text'),
            "The text should be set with nodes as singular.");

        // Test the default summary, with one node
        view = this.makeDashboard();
        view.setSummary(false);
        Y.Assert.areEqual(
            '12',
            view.srcNode.one('#nodes-number').get('text'),
            "The total number of nodes should be set.");
        Y.Assert.areEqual(
            'nodes in this MAAS',
            view.srcNode.one('#nodes-description').get('text'),
            "The text should be set with nodes as a plural.");

        // Test we can set the summary for a particular status (multiple nodes)
        view = this.makeDashboard();
        view.setSummary(false, 1, view.queued_template);
        Y.Assert.areEqual(
            '1',
            view.srcNode.one('#nodes-number').get('text'),
            "The total number of nodes should be set.");
        Y.Assert.areEqual(
            'node queued',
            view.srcNode.one('#nodes-description').get('text'),
            "The text should be set with nodes as a plural.");
    },

    testSetSummaryAnimation: function() {
        var self = this;
        var view = this.makeDashboard();
        var fade_out_anim = false;
        var fade_in_anim = false;
        view.fade_out.on('end', function() {
            fade_out_anim = true;
        });
        view.fade_in.on('end', function() {
            fade_in_anim = true;
            self.resume(function() {
                Y.Assert.isTrue(
                    fade_out_anim,
                    "The fade-out animation should have run.");
                Y.Assert.isTrue(
                    fade_in_anim,
                    "The fade-in animation should have run.");
            });
        });
        view.setSummary(true);
        this.wait();
    },

    testSetNodeText: function() {
        var view = this.makeDashboard();
        view.setNodeText(
            view.reservedNode, view.reserved_template,
            view.stats.get("reserved"));
        Y.Assert.areEqual(
            "3 nodes reserved for named deployment.",
            view.srcNode.one('#reserved-nodes').get('text'),
            "The text should be set with nodes as a plural.");

        var data = [{
            system_id: 'sys9',
            hostname: 'host9',
            status: Y.maas.enums.NODE_STATUS.RESERVED
            }];
        view = this.makeDashboard(data);
        view.setNodeText(
            view.reservedNode, view.reserved_template,
            view.stats.get("reserved"));
        Y.Assert.areEqual(
            "1 node reserved for named deployment.",
            view.srcNode.one('#reserved-nodes').get('text'),
            "The text should be set with nodes as singular.");
    },

    testGetNodeCount: function() {
        var view = this.makeDashboard();
        Y.Assert.areEqual(
            12,
            view.getNodeCount(),
            "The total nodes should not return retired nodes.");
    }

}));

suite.add(new Y.maas.testing.TestCase({
    name: 'test-node-views-NodeTableReloader',

    setUp : function () {
        Y.one('#placeholder').empty();
        this.data = [
            {
                id: 1,
                system_id: 'sys1',
                url: '/nodes/sys1/view',
                fqdn: 'host1.local',
                status: 'New',
                owner: '',
                power_state: 'off'
            },
            {
                id: 2,
                system_id: 'sys2',
                url: '/nodes/sys2/view',
                fqdn: 'host2.local',
                status: 'Allocated',
                owner: 'admin',
                power_state: 'off'
            },
            {
                id: 3,
                system_id: 'sys3',
                url: '/nodes/sys3/view',
                fqdn: 'host3.local',
                status: 'Deploying',
                owner: 'admin',
                power_state: 'on'
            },
            {
                id: 4,
                system_id: 'sys4',
                url: '/nodes/sys4/view',
                fqdn: 'host4.local',
                status: 'Deployed',
                owner: 'admin',
                power_state: 'off'
            },
            {
                id: 5,
                system_id: 'sys5',
                url: '/nodes/sys5/view',
                fqdn: 'host5.local',
                status: 'Broken',
                owner: '',
                power_state: 'error'
            }
        ];
    },

    /**
     * Create a table, hook it into the reloader, and arrange for cleanup.
     *
     * The "data" parameter defaults to this.data.
     */
    makeTableReloader: function(data) {
        if (data === undefined) {
            data = this.data;
        }
        var table = Y.Node.create('<table />');
        var tbody = Y.Node.create('<tbody />');
        table.append(tbody);
        Y.Array.each(data, function(node) {
            var tableRow = Y.Node.create('<tr />')
                .setAttribute('data-system-id', node.system_id);
            var nameRow = Y.Node.create('<td />')
                .append(Y.Node.create('<a />')
                    .setAttribute('data-field', 'url')
                    .setAttribute('data-field-attr', 'href')
                    .set('href', node.url)
                    .append(Y.Node.create('<span />')
                        .setAttribute('data-field', 'fqdn')
                        .set('text', node.fqdn)));
            var statusRow = Y.Node.create('<td />')
                .setAttribute('data-field', 'status')
                .set('text', node.status);
            var ownerRow = Y.Node.create('<td />')
                .setAttribute('data-field', 'owner')
                .set('text', node.owner);
            var powerStateRow = Y.Node.create('<td />')
                .setAttribute('data-field', 'power_state')
                .setAttribute('data-field-class', 'power-')
                .addClass('power-' + node.power_state);
            tableRow.append(nameRow);
            tableRow.append(statusRow);
            tableRow.append(ownerRow);
            tableRow.append(powerStateRow);
            tbody.append(tableRow);
        });
        Y.one('#placeholder').append(table);

        var response = Y.JSON.stringify(data);
        var view = new Y.maas.node_views.NodesTableReloader({
            srcNode: Y.one('#placeholder').one('table')
        });
        view.loadNodes(response);
        this.addCleanup(function() { view.destroy(); });
        return view;
    },

    testInitializer: function() {
        var view = this.makeTableReloader();
        Y.Assert.areEqual(
            this.data.length,
            view.srcNode.one('tbody').all('tr').size(),
            "The number of table rows should equal the number of nodes.");
    },

    testGetNodesList_returns_all_system_ids: function() {
        var view = this.makeTableReloader();
        var system_ids = [];
        Y.Array.each(this.data, function(node) {
            system_ids.push(node.system_id);
        });
        Y.ArrayAssert.itemsAreEqual(
            system_ids, view.getNodesList(),
            "The node system_id's from the table doesn't match the data.");
    },

    testRender_updates_node: function() {
        var view = this.makeTableReloader();

        // Update a random node.
        var node = view.nodes[Math.floor(Math.random()*view.nodes.length)];
        node.url = 'new/url';
        node.fqdn = 'new-hostname.local';
        node.status = 'updated';
        node.owner = 'new-user';
        node.power_state = 'new-state';
        view.render();

        var row = view.srcNode.one(
            'tr[data-system-id="' + node.system_id + '"]');
        Y.Assert.areSame(
            node.url, row.one('a[data-field="url"]').getAttribute('href'));
        Y.Assert.areSame(
            node.fqdn, row.one('span[data-field="fqdn"]').get('text'));
        Y.Assert.areSame(
            node.status, row.one('td[data-field="status"]').get('text'));
        Y.Assert.areSame(
            node.owner, row.one('td[data-field="owner"]').get('text'));
        Y.Assert.areSame(
            node.power_state,
            row.one('td[data-field="power_state"]').get('text'));
        Y.Assert.isTrue(
            row.one(
                'td[data-field="power_state"]').hasClass('power-new-state'));
    }

}));


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
            action_view: '<div id="action_content"></div>'
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
            1, view.srcNode.one('#action_view').all('div').size(),
            "The content of action_view was not placed.");
        Y.Assert.areEqual(
            1, view.srcNode.one('#events_list').all('table').size(),
            "The table was not created in events_list.");
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
