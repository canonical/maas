/* Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Image model.
 *
 * @module Y.maas.image
 */

YUI.add('maas.image', function(Y) {

Y.log('loading maas.image');
var module = Y.namespace('maas.image');

/**
 * A Y.Model to represent a image.
 *
 */
module.Image = Y.Base.create('imageModel', Y.Model, [], {
    ATTRS: {
        rtype: {
        },
        name: {
        },
        title: {
        },
        arch: {
        },
        size: {
        },
        complete: {
        },
        status: {
        },
        downloading: {
        },
        numberOfNodes: {
        },
        lastUpdate: {
        }
    }
});

/**
 * A Y.ModelList that is meant to contain instances of Y.maas.image.Image.
 *
 */
module.ImageList = Y.Base.create('imageList', Y.ModelList, [], {
    model: module.Image,
    comparator: function (model) {
        return model.get('title');
    }
});

}, '0.1', {'requires': ['model', 'model-list']}
);
