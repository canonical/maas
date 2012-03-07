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
    }
};

Y.extend(AddNodeWidget, Y.Panel, {

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

    /**
     * Hide the panel.
     *
     * @method hidePanel
     */
    hidePanel: function() {
        var self = this;
        this.get('boundingBox').transition({
            duration: 0.5,
            top: '-400px'
        },
        function () {
            self.hide();
            self.destroy();
        });
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
        var macaddress_add_link = Y.Node.create('<a />')
            .addClass('add-link')
            .addClass('add-mac-form')
            .set('href', '#')
            .set('text', "Add additional MAC address");
        var operation = Y.Node.create('<input />')
            .set('type', 'hidden')
            .set('name', 'op')
            .set('value', 'new');
        var global_error = Y.Node.create('<p />')
            .addClass('form-global-errors');
        var addnodeform = Y.Node.create('<form />')
            .set('method', 'post')
            .append(global_error)
            .append(operation)
            .append(Y.Node.create(this.add_macaddress))
            .append(macaddress_add_link)
            .append(Y.Node.create(this.add_node));
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

        this.get(
            'srcNode').one('.form-global-errors').empty().append(error_node);
     },

   /**
    * Show the spinner.
    *
    * @method showSpinner
    */
    showSpinner: function() {
        var buttons = this.get('srcNode').one('.yui3-widget-button-wrapper');
        buttons.append(this.spinnerNode);
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
        // Load form snippets.
        this.add_macaddress = Y.one('#add-macaddress').getContent();
        this.add_node = Y.one('#add-node').getContent();
        // Create panel's content.
        this.set('bodyContent', this.createForm());
        this.initializeNodes();
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
            .set('src', MaaS_config.uris.statics + 'img/spinner.gif');
        // Prepare logged-off error message.
        this.loggedOffNode = Y.Node.create('<span />')
            .set('text', "You have been logged out, please ")
            .append(Y.Node.create('<a />')
                .set('text', 'log in')
                .set('href', MaaS_config.uris.login))
            .append(Y.Node.create('<span />')
                .set('text', ' again.'));
    },

    bindUI: function() {
        var self = this;
        this.get(
            'bodyContent').one('.add-mac-form').on('click', function(e) {
            e.preventDefault();
            self.addMacField();
        });
        this.get('bodyContent').on('key', function() {
            self.sendAddNodeRequest();
        }, 'press:enter');
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
                    self.hidePanel();
                },
                failure: function(id, out) {
                    Y.log(out);
                    if (out.status === 400) {
                        try {
                            // Validation error: display the errors in the
                            // form.
                            self.displayFieldErrors(JSON.parse(out.response));
                        }
                        catch (e) {
                            self.displayFormError("Unable to create Node.");
                        }
                    }
                    else if (out.status === 401) {
                        // Unauthorized error: the user has been logged out.
                        self.displayFormError(self.loggedOffNode);
                    }
                    else {
                        // Unexpected error.
                        self.displayFormError("Unable to create Node.");
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
            MaaS_config.uris.nodes_handler, cfg);
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
module.showAddNodeWidget = function(event) {
    // Cope with manual calls as well as event calls.
    if (Y.Lang.isValue(event)) {
        event.preventDefault();
    }
    // If a widget is already present, destroy it.
    var destroy = (
        Y.Lang.isValue(module._add_node_singleton) &&
        !module._add_node_singleton.destroyed);
    if (destroy) {
        module._add_node_singleton.destroy();
    }
    var cfg = {
        headerContent: "Add node",
        buttons: [
            {
                value: 'Add node',
                section: 'footer',
                action: function (e) {
                    e.preventDefault();
                    this.sendAddNodeRequest();
                }
            },
            {
                value: 'Cancel',
                section: 'footer',
                classNames: 'link-button',
                action: function (e) {
                    e.preventDefault();
                    this.hidePanel();
                }
            }],
        align: {
            node:'',
            points:
                [Y.WidgetPositionAlign.BC, Y.WidgetPositionAlign.TC]
            },
        modal: true,
        zIndex: 2,
        visible: true,
        render: true,
        hideOn: []
        };
    module._add_node_singleton = new AddNodeWidget(cfg);
    module._add_node_singleton.get('boundingBox').transition({
        duration: 0.5,
        top: '0px'
    });
    // We need to set the focus late as the widget wants to set the focus
    // on the bounding box.
    module._add_node_singleton.get(
        'boundingBox').one('input[type=text]').focus();
};

}, '0.1', {'requires': ['io', 'node', 'panel', 'event', 'event-custom',
                        'transition']}
);
