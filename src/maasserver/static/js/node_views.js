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
module._io = Y;

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
        this.handle = this.registerAddNodeDispatcher(
            Y.maas.node_add.AddNodeDispatcher);
    },

    destructor: function() {
        this.handle.detach();
    },

    render: function () {
        if (this.nodes_loaded) {
            this.display();
        }
        else {
            this.loadNodesAndRender();
        }
    },

    registerAddNodeDispatcher: function(dispatcher) {
        return dispatcher.on(
            Y.maas.node_add.NODE_ADDED_EVENT,
            function(e, node) {
                this.modelList.add(node);
            },
            this);
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
        var request = module._io.io(
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

    plural_template: (
      '<h2>{nb_nodes} nodes in this cluster</h2><div id="chart" />'),
    singular_template: (
        '<h2>{nb_nodes} node in this cluster</h2><div id="chart" />'),

    initializer: function(config) {
        this.append = config.append;
       // Prepare spinnerNode.
        this.spinnerNode = Y.Node.create('<img />')
            .set('src', MAAS_config.uris.statics + 'img/spinner.gif');
    },

   /**
    * Display a dashboard of the nodes (right now a simple count).
    *
    * @method display
    */
    display: function () {
        var size = this.modelList.size();
        var template = (size === 1) ?
            this.singular_template : this.plural_template;
        Y.one(this.container).setContent(
            Y.Lang.sub(template, {nb_nodes: size}));

        if (!this.container.inDoc()) {
            Y.one(this.append).empty().append(this.container, 0);
        }
    },

    loadNodesStarted: function() {
        Y.one(this.append).insert(this.spinnerNode, 0);
    },

    loadNodesEnded: function() {
        this.spinnerNode.remove();
    }

});

}, '0.1', {'requires': ['view', 'io', 'maas.node', 'maas.node_add']}
);
