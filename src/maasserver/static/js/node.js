/* Copyright 2012 Canonical Ltd.  This software is licensed under the
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
        },
        after_commissioning_action: {
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

}, '0.1', {'requires': ['model', 'model-list']}
);
