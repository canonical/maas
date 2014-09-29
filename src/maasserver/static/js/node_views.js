/* Copyright 2012 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Node model.
 *
 * @module Y.maas.node_views
 */

YUI.add('maas.node_views', function(Y) {

Y.log('loading maas.node_views');
var module = Y.namespace('maas.node_views');

var NODE_STATUS = Y.maas.enums.NODE_STATUS;


/**
 * A base view class to display a set of Nodes (Y.maas.node.Node).
 *
 * It will load the list of visible nodes (in this.modelList) when rendered
 * for the first time and be subscribed to 'nodeAdded' events published by
 * Y.maas.node_add.AddNodeDispatcher.  Changes to this.modelList will trigger
 * re-rendering.
 *
 * You can provide your custom rendering method by defining a 'render'
 * method (also, you can provide methods named 'loadNodesStarted' and
 * 'loadNodesEnded' to customize the display during the initial loading of the
 * visible nodes and a method named 'displayGlobalError' to display a message
 * when errors occur during loading).
 *
 */
module.NodeListLoader = Y.Base.create('nodeListLoader', Y.View, [], {

    initializer: function(config) {
        this.modelList = new Y.maas.node.NodeList();
        this.loaded = false;
    },

    render: function () {
    },

    /**
     * Add a loader, a Y.IO object. Events fired by this IO object will
     * be followed, and will drive updates to this object's model.
     *
     * It may be wiser to remodel this to consume a YUI DataSource. That
     * would make testing easier, for one, but it would also mean we can
     * eliminate our polling code: DataSource has support for polling
     * via the datasource-polling module.
     *
     * @method addLoader
     */
    addLoader: function(loader) {
        loader.on("io:start", this.loadNodesStarted, this);
        loader.on("io:end", this.loadNodesEnded, this);
        loader.on("io:failure", this.loadNodesFailed, this);
        loader.on("io:success", function(id, request) {
            this.loadNodes(request.responseText);
        }, this);
    },

    /**
     * Load the nodes from the given data.
     *
     * @method loadNodes
     */
    loadNodes: function(data) {
        try {
            var nodes = JSON.parse(data);
            this.mergeNodes(nodes);
        }
        catch(e) {
            this.loadNodesFailed();
        }
        // Record that at least one load has been done.
        this.loaded = true;
    },

    /**
     * Process an array of nodes, merging them into modelList with the
     * fewest modifications possible.
     *
     * @method mergeNodes
     */
    mergeNodes: function(nodes) {
        var self = this;  // JavaScript sucks.

        // Attributes that we're checking for changes.
        var attrs = ["hostname", "status"];

        var nodesBySystemID = {};
        Y.Array.each(nodes, function(node) {
            nodesBySystemID[node.system_id] = node;
        });
        var modelsBySystemID = {};
        this.modelList.each(function(model) {
            modelsBySystemID[model.get("system_id")] = model;
        });

        Y.each(nodesBySystemID, function(node, system_id) {
            var model = modelsBySystemID[system_id];
            if (Y.Lang.isValue(model)) {
                // Compare the node and the model.
                var modelAttrs = model.getAttrs(attrs);
                var modelChanges = {};
                Y.each(modelAttrs, function(value, key) {
                    if (node[key] !== value) {
                        modelChanges[key] = node[key];
                    }
                });
                // Update the node.
                model.setAttrs(modelChanges);
            }
            else {
                // Add the node.
                self.modelList.add(node);
            }
        });

        Y.each(modelsBySystemID, function(model, system_id) {
            // Remove models that don't correspond to a node.
            if (!Y.Object.owns(nodesBySystemID, system_id)) {
                self.modelList.remove(model);
            }
        });
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
    * @method displayGlobalError
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
    },

    /**
     * Function called when the Node list failed to load.
     *
     * @method loadNodesFailed
     */
    loadNodesFailed: function() {
        this.displayGlobalError('Unable to load nodes.');
    }

});

/**
 * A customized view based on NodeListLoader that will display a dashboard
 * of the nodes.
 */
module.NodesDashboard = Y.Base.create(
    'nodesDashboard', module.NodeListLoader, [], {

    // Templates.
    added_template: 'node{plural} added but never seen',
    all_template: 'node{plural} in this MAAS',
    allocated_template: 'node{plural} allocated',
    commissioned_template: 'node{plural} commissioned',
    offline_template: 'node{plural} offline',
    queued_template: 'node{plural} queued',
    reserved_template: '{nodes} node{plural} reserved for named deployment.',
    retired_template: '{nodes} retired node{plural} not represented.',

    initializer: function(config) {
        this.srcNode = Y.one(config.srcNode);
        this.summaryNode = this.srcNode.one(config.summaryNode);
        this.numberNode = this.srcNode.one(config.numberNode);
        this.descriptionNode = this.srcNode.one(config.descriptionNode);
        this.reservedNode = this.srcNode.one(config.reservedNode);
        // XXX: GavinPanella 2012-04-17 bug=984117:
        // Hidden until we support reserved nodes.
        this.reservedNode.hide();
        this.retiredNode = this.srcNode.one(config.retiredNode);
        // XXX: GavinPanella 2012-04-17 bug=984116:
        // Hidden until we support retired nodes.
        this.retiredNode.hide();

        this.stats = new Y.maas.node.NodeStats();

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
        this.chart = new Y.maas.nodes_chart.NodesChartWidget(
            {node_id: 'chart', width: 300, stats: this.stats});

        // Set up the hovers for changing the dashboard text
        var events = [
            {event: 'hover.offline.over', template: this.offline_template},
            {event: 'hover.offline.out'},
            {event: 'hover.added.over', template: this.added_template},
            {event: 'hover.added.out'},
            {event: 'hover.allocated.over', template: this.allocated_template},
            {event: 'hover.allocated.out'},
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

        var self = this;  // JavaScript sucks.

        // Wire up the model list to the chart and summary.
        this.modelList.after("add", function(e) {
            self.updateStatus('add', e.model.get("status"));
            self.setSummary(self.loaded);
        });
        this.modelList.after("remove", function(e) {
            self.updateStatus('remove', e.model.get("status"));
            self.setSummary(self.loaded);
        });
        this.modelList.after("*:change", function(e) {
            var status_change = e.changed.status;
            if (Y.Lang.isValue(status_change)) {
                self.updateStatus('remove', status_change.prevVal);
                self.updateStatus('add', status_change.newVal);
            }
        });
        this.modelList.after("reset", function(e) {
            self.stats.reset();
            self.modelList.each(function(model) {
                self.updateStatus("add", model.get("status"));
            });
            self.render();
        });
    },

   /**
    * Display a dashboard of the nodes.
    *
    * @method render
    */
    render: function () {
        // Set the default text on the dashboard
        this.setSummary(this.loaded);
        this.setNodeText(
            this.reservedNode, this.reserved_template,
            this.stats.get("reserved"));
        this.setNodeText(
            this.retiredNode, this.retired_template,
            this.stats.get("retired"));
    },

    loadNodesStarted: function() {
        this.srcNode.insert(this.spinnerNode, 0);
    },

    loadNodesEnded: function() {
        this.spinnerNode.remove();
    },

   /**
    * Update the number of nodes for a status, one node at a time.
    *
    * @method updateStatus
    */
    updateStatus: function(action, status) {
        var node_counter = 0;

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
        case NODE_STATUS.NEW:
            // Added nodes
            this.stats.update("added", node_counter);
            break;
        case NODE_STATUS.COMMISSIONING:
        case NODE_STATUS.FAILED_COMMISSIONING:
        case NODE_STATUS.MISSING:
            // Offline nodes
            this.stats.update("offline", node_counter);
            break;
        case NODE_STATUS.READY:
            // Queued nodes
            this.stats.update("queued", node_counter);
            break;
        case NODE_STATUS.RESERVED:
            // Reserved nodes
            this.setNodeText(
                this.reservedNode, this.reserved_template,
                this.stats.update("reserved", node_counter));
            break;
        case NODE_STATUS.ALLOCATED:
        case NODE_STATUS.DEPLOYING:
        case NODE_STATUS.DEPLOYED:
            // Allocated/Deploying/Deployed nodes
            this.stats.update("allocated", node_counter);
            break;
        case NODE_STATUS.RETIRED:
            // Retired nodes
            this.setNodeText(
                this.retiredNode, this.retired_template,
                this.stats.update("retired", node_counter));
            break;
        }
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
            this.fade_out.on('end', function (e, self, nodes, text) {
                self.numberNode.setContent(nodes);
                self.descriptionNode.setContent(text);
                self.fade_in.run();
            }, null, this, nodes, text);
            this.fade_out.run();
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
            return model.get('status') !== NODE_STATUS.RETIRED;
        }).length;
    }
});

}, '0.1', {'requires': [
    'view', 'io', 'maas.enums', 'maas.node', 'maas.node_add',
    'maas.nodes_chart', 'maas.morph', 'anim']}
);
