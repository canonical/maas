/* Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Node model.
 *
 * @module Y.maas.node
 */

YUI.add('maas.node', function(Y) {

Y.log('loading maas.node');
var module = Y.namespace('maas.node');

/**
 * A Y.Model to represent a Node.
 *
 */
module.Node = Y.Base.create('nodeModel', Y.Model, [], {
    idAttribute: 'system_id'
}, {
    ATTRS: {
        system_id: {
        },
        hostname: {
        },
        status: {
        }
    }
});

/**
 * A Y.ModelList that is meant to contain instances of Y.maas.node.Node.
 *
 */
module.NodeList = Y.Base.create('nodeList', Y.ModelList, [], {
    model: module.Node
});

/**
 * An object that can contain aggregate information about nodes.
 */
module.NodeStats = Y.Base.create('nodeStats', Y.Base, [], {

    update: function(name, delta) {
        var value = this.get(name) + delta;
        this.set(name, value);
        return value;
    }

}, {

    ATTRS: {
        /**
         * The number of allocated nodes.
         *
         * @attribute allocated
         * @type integer
         */
        allocated: {
            value: 0
        },
        /**
         * The number of commissioned nodes.
         *
         * @attribute commissioned
         * @type integer
         */
        commissioned: {
            value: 0
        },
        /**
         * The number of queued nodes.
         *
         * @attribute queued
         * @type integer
         */
        queued: {
            value: 0
        },
        /**
         * The number of reserved nodes.
         *
         * @attribute reserved
         * @type integer
         */
        reserved: {
            value: 0
        },
        /**
         * The number of offline nodes.
         *
         * @attribute offline
         * @type integer
         */
        offline: {
            value: 0
        },
        /**
         * The number of added nodes.
         *
         * @attribute added
         * @type integer
         */
        added: {
            value: 0
        },
        /**
         * The number of retired nodes.
         *
         * @attribute retired
         * @type integer
         */
        retired: {
            value: 0
        }
    }

});

}, '0.1', {'requires': ['model', 'model-list']}
);
