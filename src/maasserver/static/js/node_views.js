/* Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
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

// Header for the event table that is rendered by NodeViewReloader.
var EVENT_TABLE_HEADER =
    '<thead>' +
        '<tr>' +
            '<th width="10%">Level</th>' +
            '<th width="30%">Emitted</th>' +
            '<th>Event</th>' +
        '</tr>' +
    '</thead>';

/**
 * View that will reload information on the node view page, render the
 * event log, and update the sidebar.
 *
 * This view uses data-* attributes to update the elements in the view. See
 * js/utils.js:updateElements for complete description of data-* attributes.
 */
module.NodeView = Y.Base.create('nodeView', Y.View, [], {

    initializer: function(config) {
        this.srcNode = Y.one(config.srcNode);
        this.eventList = Y.one(config.eventList);
        this.actionView = Y.one(config.actionView);
        this.powerChecker = new Y.maas.node_check.PowerCheckWidget({
            srcNode: config.actionView,
            system_id: config.system_id
        });
    },

    /**
     * Add a loader, a Y.IO object. Events fired by this IO object will
     * be followed, and will drive updates to this object's model.
     *
     * @method addLoader
     */
    addLoader: function(loader) {
        loader.on("io:success", function(id, request) {
            this.loadNode(request.responseText);
        }, this);
    },

    /**
     * Load the node from the given data.
     *
     * @method loadNode
     */
    loadNode: function(data) {
        try {
            var node = JSON.parse(data);
            this.node = node;
        }
        catch(e) {
            console.log("Failed to decode node JSON data.");
            return;
        }
        // Record that at least one load has been done.
        this.loaded = true;
        this.render();
    },

   /**
    * Update all of the elements with data-field attributes with the
    * attributes on the given node.
    *
    * @method render
    */
    render: function () {
        var elements = this.srcNode.all('[data-field]');
        Y.maas.utils.updateElements(elements, this.node);
        this.renderEventList();
        this.renderActionView();
        this.powerChecker.render();
    },

   /**
    * Render the event listing table, with the most recent events.
    *
    * @method renderEventList
    */
    renderEventList: function() {
        var self = this;
        var events = this.node.events;

        // Clear the old table.
        this.eventList.get('childNodes').remove();

        // If no events add "No events" div.
        if (!Y.Lang.isValue(events) || events.count === 0) {
            this.eventList.append(
                Y.Node.create('<div />').set('text', 'No events'));
            return;
        }

        // Create the new table.
        var table = Y.Node.create('<table />');
        table.addClass('list');
        table.append(Y.Node.create(EVENT_TABLE_HEADER));

        // Create the tbody, inserting each row.
        var tbody = Y.Node.create('<tbody />');
        Y.Array.each(this.node.events.events, function(evt) {
            tbody.append(self.createEventRow(evt));
        });
        table.append(tbody);

        // Add the table to the dom.
        this.eventList.append(table);

        // Add the link to more event data.
        if (events.count < events.total) {
            var link = Y.Node.create('<a />')
                .set('href', events.more_url)
                .set(
                    'text',
                    'Full node event log (' + events.total + ' events).');
            this.eventList.append(link);
        }
    },

   /**
    * Render the event table row for the given event.
    *
    * @method createEventRow
    */
    createEventRow: function(evt) {
        // Create the row, setting the id and class based on level.
        var tr = Y.Node.create('<tr />');
        tr.set('id', 'node-event-' + evt.id);
        tr.addClass(evt.level.toLowerCase());

        // Add the data to the row
        tr.append(
            Y.Node.create('<td />')
                .set('text', evt.level));
        tr.append(Y.Node.create('<td />')
                .set('text', evt.created));
        var rowText = evt.type;
        if (Y.Lang.isString(evt.description) && evt.description.length > 0) {
            rowText += ' &mdash; ' + evt.description;
        }
        tr.append(
            Y.Node.create('<td />')
                .setHTML(rowText));
        return tr;
    },

   /**
    * Render the updated action view.
    *
    * @method renderActionView
    */
    renderActionView: function() {
        // Clear the old action view.
        this.actionView.get('childNodes').remove();

        // Add the updated action view.
        this.actionView.append(Y.Node.create(this.node.action_view));
    }
});

}, '0.1', {'requires': [
    'view', 'io', 'maas.enums', 'maas.node', 'maas.node_add',
    'maas.nodes_chart', 'maas.node_check', 'maas.morph', 'maas.utils', 'anim']}
);
