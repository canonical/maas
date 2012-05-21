/* Copyright 2012 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 */

YUI({ useBrowserConsole: true }).add('maas.morph.tests', function(Y) {

Y.log('loading maas.morph.tests');
var namespace = Y.namespace('maas.morph.tests');

var module = Y.maas.morph;
var suite = new Y.Test.Suite("maas.morph Tests");

var panel_one = Y.one('#panel-one-template').getContent();
var panel_two = Y.one('#panel-two-template').getContent();

suite.add(new Y.maas.testing.TestCase({
    name: 'test-morphing',

    setUp: function() {
        Y.one('#placeholder').empty().append(
            Y.Node.create(panel_one)).append(
                Y.Node.create(panel_two));
    },

    get_morph: function(animate) {
        var cfg = {
            srcNode: '#panel-two',
            targetNode: '#panel-one',
            animate: animate
        };
        return new module.Morph(cfg);
    },

    test_morphing_no_animation_sets_visibility_classes: function() {
        var morpher = this.get_morph(false);
        morpher.morph(false);

        Y.Assert.isTrue(Y.one('#panel-one').hasClass('hidden'));
        Y.Assert.isFalse(Y.one('#panel-two').hasClass('hidden'));
    },

    test_morphing_animation_sets_visibility_classes: function() {
        Y.Assert.isFalse(Y.one('#panel-one').hasClass('hidden'));
        Y.Assert.isTrue(Y.one('#panel-two').hasClass('hidden'));
        var morpher = this.get_morph(true);
        var self = this;
        morpher.on('morphed', function () {
            self.resume(function() {
                Y.Assert.isTrue(Y.one('#panel-one').hasClass('hidden'));
                Y.Assert.isFalse(Y.one('#panel-two').hasClass('hidden'));
            });
        });
        morpher.morph();
        this.wait();
    },

    test__create_morph_out_anim_sets_opacity_and_adds_class: function() {
        var targetNode = Y.one('#panel-one');
        targetNode.setStyle('opacity', 0.5);
        var morph = module._create_morph_out(targetNode);
        var self = this;
        morph.on('end', function () {
            self.resume(function() {
                var opacity = targetNode.getComputedStyle('opacity');
                Y.Assert.areEqual(0, opacity);
                Y.Assert.isTrue(targetNode.hasClass('hidden'));
            });
        });
        morph.run();
        this.wait();
    },

    test__create_morph_in_anim_sets_initial_opacity_and_class: function() {
        var srcNode = Y.one('#panel-one');
        srcNode.setStyle('opacity', 0.5);
        var targetNode = Y.one('#panel-two');
        var morph = module._create_morph_in(srcNode, targetNode);

        Y.Assert.areEqual(0, srcNode.getComputedStyle('opacity'));
        Y.Assert.isFalse(srcNode.hasClass('hidden'));
    },

    test__create_morph_in_anim_sets_opacity: function() {
        var srcNode = Y.one('#panel-one');
        srcNode.setStyle('opacity', 0.5);
        var targetNode = Y.one('#panel-two');
        var morph = module._create_morph_in(srcNode, targetNode);
        var self = this;
        morph.on('end', function () {
            self.resume(function() {
                Y.Assert.areEqual(1, srcNode.getComputedStyle('opacity'));
            });
        });
        morph.run();
        this.wait();
    },

    test__create_morph_anim_set_visibility_classes: function() {
        var srcNode = Y.one('#panel-two');
        var targetNode = Y.one('#panel-one');
        var publisher = new Y.Base();
        var morph = module._create_morph(srcNode, targetNode, publisher);
        var self = this;
        publisher.on('morphed', function () {
            self.resume(function() {
                Y.Assert.areEqual(1, srcNode.getComputedStyle('opacity'));
                Y.Assert.isTrue(Y.one('#panel-one').hasClass('hidden'));
                Y.Assert.isFalse(Y.one('#panel-two').hasClass('hidden'));
            });
        });
        morph.run();
        this.wait();
    },

    test__create_resize_animation_resizes: function() {
        var srcNode = Y.one('#panel-one');
        var resize = module._create_resize(srcNode, '29');
        var self = this;
        resize.on('resized', function () {
            self.resume(function() {
                var height_style = srcNode.getStyle('height');
                Y.Assert.areEqual('auto', height_style);
            });
        });
        resize.run();
        this.wait();
    }

}));

namespace.suite = suite;

}, '0.1', {'requires': [
    'node-event-simulate', 'test', 'maas.testing', 'maas.morph']}
);
