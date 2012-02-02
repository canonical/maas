/* Copyright 2012 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Widget to add a Node.
 *
 * @module Y.mass.add_node
 */

YUI.add('maas.add_node', function(Y) {

Y.log('loading mass.add_node');

var module = Y.namespace('maas.add_node');

module.NODE_ADDED_EVENT = 'nodeAdded';

// Only used to mockup io in tests.
module._io = Y;

var AddNodeWidget = function() {
    AddNodeWidget.superclass.constructor.apply(this, arguments);
};

AddNodeWidget.NAME = 'add-node-widget';

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

Y.extend(AddNodeWidget, Y.Overlay, {

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
        var addnode_button = Y.Node.create('<button />')
            .addClass('add-node-button')
            .set('text', "Add node");
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
            .append(Y.Node.create(this.add_node))
            .append(addnode_button);
        return addnodeform;
    },

    displayFormError: function(error_message) {
        this.get(
            'srcNode').one('.form-global-errors').set('text', error_message);
     },

   /**
     * Show the spinner.
     *
     * @method showSpinner
     */
    showSpinner: function() {
        var button = this.get('srcNode').one('.add-node-button');
        button.insert(this.spinnerNode, 'after');
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
        // Create overlay's content.
        var closenode = Y.Node.create('<a />')
            .set('href', '#')
            .addClass('overlay-close')
            .set('text', "Close");
        this.headernode = Y.Node.create('<div />')
            .addClass('overlay-header')
            .set('text', "Add Node")
            .append(closenode)
            .append(Y.Node.create('<div />')
                .addClass('clear'));
        this.set('headerContent', this.headernode);
        this.set('bodyContent', this.createForm());
        this.set('footerContent', "");
       // Center overlay.
        this.set(
            'align',
            {points: [
              Y.WidgetPositionAlign.CC,
              Y.WidgetPositionAlign.CC]
            });
       // Prepare spinnerNode.
        this.spinnerNode = Y.Node.create('<img />')
            .set('src', MAAS_config.uris.statics + 'img/spinner.gif');
    },

    bindUI: function() {
        var self = this;
        this.get(
            'headerContent').one('.overlay-close').on('click', function(e) {
            e.preventDefault();
            self.destroy();
        });
        this.get(
            'bodyContent').one('.add-mac-form').on('click', function(e) {
            e.preventDefault();
            self.addMacField();
        });
        this.get(
            'bodyContent').one('.add-node-button').on('click', function(e) {
            e.preventDefault();
            self.sendAddNodeRequest();
        });
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
                    self.destroy();
                },
                failure: function(id, out) {
                    if (out.status === 400) {
                        try {
                            // Validation error: display the errors in the
                            // form.
                            self.displayFieldErrors(JSON.parse(out.response));
                        }
                        catch (e) {
                            self.displayFormError('Unable to create Node.');
                        }
                    }
                    else {
                        // Unexpected error.
                        self.displayFormError('Unable to create Node.');
                    }
                },
                end: Y.bind(self.hideSpinner, self)
            },
            form: {
                id: self.get('srcNode').one('form'),
                useDisabled: true
            }
        };
        var request = module._io.io(
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
    module._add_node_singleton = new AddNodeWidget();
    module._add_node_singleton.render();
};

}, '0.1', {'requires': ['io', 'node', 'overlay', 'event', 'event-custom']}
);
