/* Copyright 2012 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Widget to add a Node.
 *
 * @module Y.maas.node_add
 */

YUI.add('maas.node_add', function(Y) {

Y.log('loading maas.node_add');

var module = Y.namespace('maas.node_add');

module.NODE_ADDED_EVENT = 'nodeAdded';

// Only used to mockup io in tests.
module._io = new Y.IO();

var AddNodeWidget = function() {
    AddNodeWidget.superclass.constructor.apply(this, arguments);
};

AddNodeWidget.NAME = 'node-add-widget';

AddNodeWidget.ATTRS = {

   /**
    * The number MAC Addresses fields on the form.
    *
    * @attribute nb_mac_fields
    * @type integer
    */
    nb_mac_fields: {
        getter: function() {
            return this.get(
                'srcNode').all('input[name=mac_addresses]').size();
        }
    },

    /**
     * The DOM node to be morphed from.
     *
     * @attribute targetNode
     * @type string
     */
    targetNode: {
        value: null
    }
};

Y.extend(AddNodeWidget, Y.Widget, {

    /**
     * Create an input field to add a MAC Address.
     *
     * @method _createMacField
     * @private
     * @return Node
     */
     _createMacField: function() {
        var form_nb = this.get('nb_mac_fields') + 1;
        var field = Y.Node.create(this.add_macaddress).one('input');
        field.set('id', field.get('id') + form_nb);
        return Y.Node.create('<p />').append(field);
    },

    addMacField: function() {
        if (this.get('nb_mac_fields') === 1) {
            var label = this.get(
                'srcNode').one('label[for="id_mac_addresses"]');
            label.set('text', "Mac addresses");
        }
        var add_macaddress = this._createMacField();
        var add_mac_link = this.get('srcNode').one('.add-mac-form');
        add_mac_link.insert(add_macaddress, 'before');
    },

    cleanFormErrors: function() {
        this.get('srcNode').all('div.field-error').remove();
    },

    /* Display validation errors on their respective fields.
     *
     * The "errors" argument is an object.  If a field has validation errors,
     * this object will map the field's name to a list of error strings.  Each
     * field's errors will be shown with the label for that field.
     *
     * @method displayFieldErrors
     */
    displayFieldErrors: function(errors) {
        this.cleanFormErrors();
        var key;
        for (key in errors) {
            if (errors.hasOwnProperty(key)) {
                var error = errors[key].join(',');
                var label = this.get(
                    'srcNode').one('label[for="id_' + key + '"]');
                var error_node = Y.Node.create('<div />')
                    .addClass('field-error')
                    .set('text', error);
                label.insert(error_node, 'after');
            }
        }
    },

    createForm: function() {
        var addnode_button = Y.Node.create('<button />')
            .addClass('add-node-button')
            .addClass('right')
            .set('text', "Add node");
        var cancel_button = Y.Node.create('<a />')
            .addClass('cancel-button')
            .set('href', '#')
            .set('text', "Cancel")
            .addClass('link-button');
        var macaddress_add_icon = Y.Node.create('<img />')
            .set('src', MAAS_config.uris.statics + 'img/inline_add.png')
            .set('alt', "+")
            .addClass('icon');
        var macaddress_add_link = Y.Node.create('<a />')
            .addClass('add-link')
            .addClass('add-mac-form')
            .set('href', '#')
            .set('text', "Add additional MAC address")
            .prepend(macaddress_add_icon);
        var operation = Y.Node.create('<input />')
            .set('type', 'hidden')
            .set('name', 'op')
            .set('value', 'new');
        var global_error = Y.Node.create('<p />')
            .addClass('form-errors');
        var buttons = Y.Node.create('<div />')
            .addClass('buttons')
            .append(addnode_button)
            .append(cancel_button);
        var addnodeform = Y.Node.create('<form />')
            .set('method', 'post')
            .append(global_error)
            .append(operation)
            .append(Y.Node.create(this.add_macaddress))
            .append(macaddress_add_link)
            .append(Y.Node.create(this.add_architecture))
            .append(Y.Node.create(this.add_node))
            .append(buttons);
        return addnodeform;
    },

    /**
     * Display an error message.  The passed-in parameter can be a string or
     * a Node (in which case it will be appended to the error node).
     *
     * @method displayFormError
     */
    displayFormError: function(error) {
        var error_node;
        if (typeof error === 'string') {
            // 'error' is a string, create a simple node with the error
            // message in it.
            error_node = Y.Node.create('<span />')
                .set('text', error);
        }
        else {
            // We assume error is a Y.Node.
            error_node = error;
        }

        this.get('srcNode').one('.form-errors').empty().append(error_node);
     },

   /**
    * Show the spinner.
    *
    * @method showSpinner
    */
    showSpinner: function() {
        var buttons = this.get('srcNode').one('.add-node-button');
        buttons.insert(this.spinnerNode, 'after');
    },

    /**
     * Hide the spinner.
     *
     * @method hideSpinner
     */
    hideSpinner: function() {
        this.spinnerNode.remove();
    },

    initializer: function(cfg) {
        if (Y.Lang.isValue(cfg.animate)) {
            this._animate = cfg.animate;
        }
        else {
            this._animate = true;
        }
        this.get('srcNode').addClass('hidden');
        this.morpher = new Y.maas.morph.Morph({
            srcNode: cfg.srcNode,
            targetNode: this.get('targetNode'),
            animate: this._animate
            });
    },

    renderUI: function() {
        // Load form snippets.
        this.add_macaddress = Y.one('#add-macaddress').getContent();
        this.add_architecture = Y.one('#add-architecture').getContent();
        this.add_node = Y.one('#add-node').getContent();
        // Create panel's content.
        var heading = Y.Node.create('<h2 />')
            .set('text', "Add node");
        this.get('srcNode').append(heading).append(this.createForm());
        this.initializeNodes();
    },

    /**
     * Show the widget
     *
     * @method showWidget
     */
    showWidget: function() {
        this.morpher.morph();
        this.morpher.on('morphed', function(e, widget) {
            widget.get('srcNode').one('input[type=text]').focus();
        }, null, this);
    },

    /**
     * Hide the widget
     *
     * @method showWidget
     */
    hideWidget: function() {
        this.morpher.morph(true);
        this.morpher.on('morphed', function(e, widget) {
            widget.destroy();
        }, null, this);
    },

    /**
     * Initialize the nodes this widget will use.
     *
     * @method initializeNodes
     */
    initializeNodes: function() {
        // Prepare spinnerNode.
        this.spinnerNode = Y.Node.create('<img />')
            .addClass('spinner')
            .set('src', MAAS_config.uris.statics + 'img/spinner.gif');
        // Prepare logged-off error message.
        this.loggedOffNode = Y.Node.create('<span />')
            .set('text', "You have been logged out, please ")
            .append(Y.Node.create('<a />')
                .set('text', 'log in')
                .set('href', MAAS_config.uris.login))
            .append(Y.Node.create('<span />')
                .set('text', ' again.'));
    },

    bindUI: function() {
        var self = this;
        var srcNode = this.get('srcNode');
        srcNode.one('.add-mac-form').on('click', function(e) {
            e.preventDefault();
            self.addMacField();
        });
        srcNode.on('key', function() {
            self.sendAddNodeRequest();
        }, 'press:enter');
        srcNode.one('.add-node-button').on('click', function(e) {
            e.preventDefault();
            self.sendAddNodeRequest();
        });
        srcNode.one('.cancel-button').on('click', function(e, widget) {
            e.preventDefault();
            widget.hideWidget();
        }, null, this);
    },

    addNode: function(node) {
        module.AddNodeDispatcher.fire(module.NODE_ADDED_EVENT, {}, node);
    },

    sendAddNodeRequest: function() {
        var self = this;
        this.cleanFormErrors();
        var cfg = {
            method: 'POST',
            sync: false,
            on: {
                start:  Y.bind(self.showSpinner, self),
                success: function(id, out) {
                    self.addNode(JSON.parse(out.response));
                    self.hideWidget();
                },
                failure: function(id, out) {
                    Y.log("Adding a node failed.  Response object follows.");
                    Y.log(out);
                    if (out.status === 400) {
                        try {
                            /* Validation error: display the errors in the
                             * form next to their respective fields.
                             */
                            self.displayFieldErrors(
                                JSON.parse(out.responseText));
                        }
                        catch (e) {
                            Y.log(
                                "Exception while decoding error JSON: " +
                                e.message);
                            self.displayFormError(
                                "Unable to create Node: " + out.responseText);
                        }
                    }
                    else if (out.status === 401) {
                        // Unauthorized error: the user has been logged out.
                        self.displayFormError(self.loggedOffNode);
                    }
                    else {
                        // Unexpected error.
                        self.displayFormError(
                            "Unable to create Node: " + out.responseText);
                    }
                },
                end: Y.bind(self.hideSpinner, self)
            },
            form: {
                id: self.get('srcNode').one('form'),
                useDisabled: true
            }
        };
        var request = module._io.send(
            MAAS_config.uris.nodes_handler, cfg);
    }

});

/**
 * Dispatcher of the Widget's events.
 *
 * One should subscribe to events like this:
 *
 * namespace.AddNodeDispatcher.on(
 *     namespace.NODE_ADDED_EVENT,
 *     function(e, node) {
 *         // do something with node.
 *     });
 *
 * @method showAddNodeWidget
 */
module.AddNodeDispatcher = new Y.Base();

module._add_node_singleton = null;

/**
 * Show a widget to add a Node.
 *
 * @method showAddNodeWidget
 */
module.showAddNodeWidget = function(cfg) {
    // If a widget is already present, destroy it.
    var destroy = (
        Y.Lang.isValue(module._add_node_singleton) &&
        !module._add_node_singleton.destroyed);
    if (destroy) {
        module._add_node_singleton.destroy();
    }

    var srcNode = Y.Node.create('<div />')
        .set('id', 'add-node-widget');
    cfg.srcNode = srcNode;
    Y.one(cfg.targetNode).insert(srcNode, 'after');
    module._add_node_singleton = new AddNodeWidget(cfg);
    module._add_node_singleton.render();
    module._add_node_singleton.showWidget();
};

}, '0.1', {'requires': ['io', 'node', 'widget', 'event', 'event-custom',
                        'maas.morph']}
);
