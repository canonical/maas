/* Copyright 2012 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Node model.
 *
 * @module Y.maas.node
 */

YUI.add('maas.node_views', function(Y) {

Y.log('loading maas.node_views');
var module = Y.namespace('maas.node_views');

// Only used to mockup io in tests.
module._io = new Y.IO();

var NODE_STATUS = Y.maas.enums.NODE_STATUS;


/**
 * A base view class to display a set of Nodes (Y.maas.node.Node).
 *
 * It will load the list of visible nodes (in this.modelList) when rendered
 * for the first time and be subscribed to 'nodeAdded' events published by
 * Y.maas.node_add.AddNodeDispatcher.  Changes to this.modelList will trigger
 * re-rendering.
 *
 * You can provide your custom rendering method by defining a 'display'
 * method (also, you can provide methods named 'loadNodesStarted' and
 * 'loadNodesEnded' to customize the display during the initial loading of the
 * visible nodes and a method named 'displayGlobalError' to display a message
 * when errors occur during loading).
 *
 */
module.NodeListLoader = Y.Base.create('nodeListLoader', Y.View, [], {

    initializer: function(config) {
        this.modelList = new Y.maas.node.NodeList();
        this.nodes_loaded = false;
    },

    render: function () {
        if (this.nodes_loaded) {
            this.display();
        }
        else {
            this.loadNodesAndRender();
        }
    },

   /**
    * Load visible Nodes (store them in this.modelList) and render this view.
    * to be populated.
    *
    * @method loadNodesAndRender
    */
    loadNodesAndRender: function() {
        var self = this;
        var cfg = {
            method: 'GET',
            data: 'op=list',
            sync: false,
            on: {
                start: Y.bind(self.loadNodesStarted, self),
                success: function(id, out) {
                    var node_data;
                    try {
                        node_data = JSON.parse(out.response);
                    }
                    catch(e) {
                        // Parsing error.
                        self.displayGlobalError('Unable to load nodes.');
                     }
                    self.modelList.add(node_data);
                    self.modelList.after(
                        ['add', 'remove', 'reset'], self.render, self);
                    self.nodes_loaded = true;
                    self.display();
                },
                failure: function(id, out) {
                    // Unexpected error.
                    self.displayGlobalError('Unable to load nodes.');
                },
                end: Y.bind(self.loadNodesEnded, self)
            }
        };
        var request = module._io.send(
            MAAS_config.uris.nodes_handler, cfg);
    },

   /**
    * Function called when rendering occurs.  this.modelList is guaranteed
    * to be populated.
    *
    * @method display
    */
    display: function () {
    },

   /**
    * Function called if an error occurs during the initial node loading.
    * to be populated.
    *
    * @method display
    */
    displayGlobalError: function (error_message) {
    },

   /**
    * Function called when the Node list starts loading.
    *
    * @method loadNodesStarted
    */
    loadNodesStarted: function() {
    },

   /**
    * Function called when the Node list has loaded.
    *
    * @method loadNodesEnded
    */
    loadNodesEnded: function() {
    }

});

/**
 * A customized view based on NodeListLoader that will display a dashboard
 * of the nodes.
 *
 * @method display
 */
module.NodesDashboard = Y.Base.create(
    'nodesDashboard', module.NodeListLoader, [], {
    all_template: ('node{plural} in this MAAS'),
    deployed_template: ('node{plural} deployed'),
    commissioned_template: ('node{plural} commissioned'),
    queued_template: ('node{plural} queued'),
    offline_template: ('node{plural} offline'),
    added_template: ('node{plural} added but never seen'),
    reserved_template:
        ('{nodes} node{plural} reserved for named deployment.'),
    retired_template: ('{nodes} retired node{plural} not represented.'),

    initializer: function(config) {
        this.srcNode = config.srcNode;
        this.summaryNode = Y.one(config.summaryNode);
        this.numberNode = Y.one(config.numberNode);
        this.descriptionNode = Y.one(config.descriptionNode);
        this.reservedNode = Y.one(config.reservedNode);
        /* XXX: GavinPanella 2012-04-17 bug=984117:
         * Hidden until we support reserved nodes. */
        this.reservedNode.hide();
        this.retiredNode = Y.one(config.retiredNode);
        /* XXX: GavinPanella 2012-04-17 bug=984116:
         * Hidden until we support retired nodes. */
        this.retiredNode.hide();
        this.deployed_nodes = 0;
        this.commissioned_nodes = 0;
        this.queued_nodes = 0;
        this.reserved_nodes = 0;
        this.offline_nodes = 0;
        this.added_nodes = 0;
        this.retired_nodes = 0;
        this.data_populated = false;
        this.fade_out = new Y.Anim({
            node: this.summaryNode,
            to: {opacity: 0},
            duration: 0.1,
            easing: 'easeIn'
            });
        this.fade_in = new Y.Anim({
            node: this.summaryNode,
            to: {opacity: 1},
            duration: 0.2,
            easing: 'easeIn'
            });
        // Prepare spinnerNode.
        this.spinnerNode = Y.Node.create('<img />')
            .set('src', MAAS_config.uris.statics + 'img/spinner.gif');
        // Set up the chart
        this.chart = new Y.maas.nodes_chart.NodesChartWidget({
            node_id: 'chart',
            width: 300
            });

        // Set up the hovers for changing the dashboard text
        var events = [
            {event: 'hover.offline.over', template: this.offline_template},
            {event: 'hover.offline.out'},
            {event: 'hover.added.over', template: this.added_template},
            {event: 'hover.added.out'},
            {event: 'hover.deployed.over', template: this.deployed_template},
            {event: 'hover.deployed.out'},
            {
                event: 'hover.commissioned.over',
                template: this.commissioned_template
                },
            {event: 'hover.commissioned.out'},
            {event: 'hover.queued.over', template: this.queued_template},
            {event: 'hover.queued.out'}
            ];
        Y.Array.each(events, function(event) {
            this.chart.on(event.event, function(e, template, widget) {
                if (Y.Lang.isValue(e.nodes)) {
                    widget.setSummary(true, e.nodes, template, true);
                }
                else {
                    // Set the text to the default
                    widget.setSummary(true);
                }
            }, null, event.template, this);
        }, this);
    },

   /**
    * Display a dashboard of the nodes.
    *
    * @method display
    */
    display: function () {
        /* Set up the initial node/status counts. This needs to happen here
           so that this.modelList exists.
        */
        if (!this.data_populated) {
            var i;
            for (i=0; i<this.modelList.size(); i++) {
                var node = this.modelList.item(i);
                var status = node.get('status');
                this.updateStatus('add', status);
            }
            this.data_populated = true;

            // Set up the event listeners for node changes
            Y.on('Node.updated', function(e, widget) {
                widget.updateNode('updated', e.instance);
            }, null, this);

            Y.on('Node.created', function(e, widget) {
                widget.updateNode('created', e.instance);
            }, null, this);

            Y.on('Node.deleted', function(e, widget) {
                widget.updateNode('deleted', e.instance);
            }, null, this);
        }
        // Update the chart with the new node/status counts
        this.chart.updateChart();
        // Set the default text on the dashboard
        this.setSummary(false);
        this.setNodeText(
            this.reservedNode, this.reserved_template, this.reserved_nodes);
        this.setNodeText(
            this.retiredNode, this.retired_template, this.retired_nodes);
    },

    loadNodesStarted: function() {
        Y.one(this.srcNode).insert(this.spinnerNode, 0);
    },

    loadNodesEnded: function() {
        this.spinnerNode.remove();
    },

   /**
    * Update the nodes in the chart.
    */
    updateNode: function(action, node) {
        var model_node;
        var update_chart = false;
        if (action === 'created') {
            this.modelList.add(node);
            update_chart = this.updateStatus('add', node.status);
        }
        else if (action === 'deleted') {
            model_node = this.modelList.getById(node.system_id);
            this.modelList.remove(model_node);
            update_chart = this.updateStatus('remove', node.status);
        }
        else if (action === 'updated') {
            model_node = this.modelList.getById(node.system_id);
            var previous_status = model_node.get('status');
            model_node.set('status', node.status);
            var update_remove = this.updateStatus('remove', previous_status);
            var update_add = this.updateStatus('add', node.status);
            if (update_remove || update_add) {
                update_chart = true;
            }
        }

        if (update_chart) {
            // Update the chart with the new node/status counts
            this.chart.updateChart();
        }

        if (action !== 'updated') {
            /* Set the default text on the dashboard. We only need to do this
               if the total number of nodes has changed.
            */
            this.setSummary(true);
        }
    },

   /**
    * Update the number of nodes for a status.
    */
    updateStatus: function(action, status) {
        var update_chart = false;
        var node_counter;

        /* This seems like an ugly way to calculate the change, but it stops
           duplication of checking for the action for each status.
        */
        if (action === 'add') {
            node_counter = 1;
        }
        else if (action === 'remove') {
            node_counter = -1;
        }

        switch (status) {
        case NODE_STATUS.DECLARED:
            // Added nodes
            this.added_nodes += node_counter;
            this.chart.set('added_nodes', this.added_nodes);
            update_chart = true;
            break;
        case NODE_STATUS.COMMISSIONING:
        case NODE_STATUS.FAILED_TESTS:
        case NODE_STATUS.MISSING:
            // Offline nodes
            this.offline_nodes += node_counter;
            this.chart.set('offline_nodes', this.offline_nodes);
            update_chart = true;
            break;
        case NODE_STATUS.READY:
            // Queued nodes
            this.queued_nodes += node_counter;
            this.chart.set('queued_nodes', this.queued_nodes);
            update_chart = true;
            break;
        case NODE_STATUS.RESERVED:
            // Reserved nodes
            this.reserved_nodes += node_counter;
            this.setNodeText(
                this.reservedNode,
                this.reserved_template,
                this.reserved_nodes
                );
            break;
        case NODE_STATUS.ALLOCATED:
            // Deployed nodes
            this.deployed_nodes += node_counter;
            this.chart.set('deployed_nodes', this.deployed_nodes);
            update_chart = true;
            break;
        case NODE_STATUS.RETIRED:
            // Retired nodes
            this.retired_nodes += node_counter;
            this.setNodeText(
                this.retiredNode, this.retired_template, this.retired_nodes);
            break;
        }

        return update_chart;
    },

   /**
    * Set the text for the number of nodes for a status.
    */
    setSummary: function(animate, nodes, template) {
        // By default we just want to display the total nodes.
        if (!nodes || !template) {
            nodes = this.getNodeCount();
            template = this.all_template;
        }
        var plural = (nodes === 1) ? '' : 's';
        var text = Y.Lang.sub(template, {plural: plural});

        if (animate) {
            this.fade_out.run();
            this.fade_out.on('end', function (e, self, nodes, text) {
                self.numberNode.setContent(nodes);
                self.descriptionNode.setContent(text);
                self.fade_in.run();
            }, null, this, nodes, text);
        }
        else {
            this.numberNode.setContent(nodes);
            this.descriptionNode.setContent(text);
        }
    },

   /**
    * Set the text from a template for a DOM node.
    */
    setNodeText: function(element, template, nodes) {
        var plural = (nodes === 1) ? '' : 's';
        var text = Y.Lang.sub(template, {plural: plural, nodes: nodes});
        element.setContent(text);
    },

   /**
    * Get the number of nodes (excluding retired).
    */
    getNodeCount: function() {
        return Y.Array.filter(this.modelList.toArray(), function (model) {
            return model.get('status') !== 7;
        }).length;
    }
});

}, '0.1', {'requires': [
    'view', 'io', 'maas.enums', 'maas.node', 'maas.node_add',
    'maas.nodes_chart', 'maas.morph', 'anim']}
);
