/* Copyright 2014 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 */

YUI({ useBrowserConsole: true }).add('maas.image.tests', function(Y) {

Y.log('loading maas.image.tests');
var namespace = Y.namespace('maas.image.tests');

var module = Y.maas.image;
var suite = new Y.Test.Suite("maas.image Tests");

suite.add(new Y.Test.Case({
    name: 'test-image',

    testImageList: function() {
        var image_list = new module.ImageList();
        Y.Assert.areSame(module.Image, image_list.model);
    },

    testImageListSortsByTitle: function() {
        var image_list = new module.ImageList();
        image_list.add({title: 'b_image'});
        image_list.add({title: 'a_image'});
        image_list.add({title: 'c_image'});
        title_list = [];
        image_list.each(function(model) {
            title_list.push(model.get('title'));
        });
        Y.ArrayAssert.itemsAreEqual(
            ['a_image', 'b_image', 'c_image'], title_list);
    }

}));

namespace.suite = suite;

}, '0.1', {'requires': [
    'node-event-simulate', 'test', 'maas.image']}
);
