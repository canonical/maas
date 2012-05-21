/* Copyright 2012 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Widget to fade and resize between two DOM nodes.
 *
 * @module Y.maas.morph
 */

YUI.add('maas.morph', function(Y) {

Y.log('loading maas.morph');

var module = Y.namespace('maas.morph');

var Morph;

Morph = function(config) {
    Morph.superclass.constructor.apply(this, arguments);
};

Morph.NAME = 'morph';

Morph.ATTRS = {
    /**
     * The DOM node to be morphed from.
     *
     * @attribute targetNode
     * @type string
     */
    targetNode: {
        value: null,
        setter: function(val) {
            return Y.one(val);
        }
    }
};

/**
 * Create the animation for morphing out the original content and
 * morphing in the new content.
 *
 * @method _create_morph
 */
module._create_morph = function(srcNode, targetNode, publisher) {
    var self = this;
    var morph = module._create_morph_out(targetNode);
    morph.on('end', function () {
        var anim = module._create_morph_in(srcNode, targetNode);
        anim.on('end', function () {
            publisher.fire('morphed');
        });
        anim.run();
    });
    return morph;
};

/**
 * Create the animation for morphing out the original content.
 *
 * @method _create_morph_out
 */
module._create_morph_out = function(targetNode) {
    var morph_out = new Y.Anim({
        node: targetNode,
        to: {opacity: 0},
        duration: 0.2,
        easing: 'easeOut'
    });
    morph_out.on('end', function () {
        targetNode.addClass('hidden');
    });
    return morph_out;
};

/**
 * Create an animation for morphing in the new content.
 *
 * @method _create_morph_in
 */
module._create_morph_in = function(srcNode, targetNode) {
    var self = this;
    srcNode.setStyle('opacity', 0);
    srcNode.removeClass('hidden');
    var src_height = srcNode.getComputedStyle('height')
        .replace('px', '');
    var target_height = targetNode.getComputedStyle('height');
    srcNode.setStyle('height', target_height);
    var morph_in = new Y.Anim({
        node: srcNode,
        to: {opacity: 1},
        duration: 1,
        easing: 'easeIn'
    });
    // Resize the srcNode to its original size.
    var resize_anim = module._create_resize(srcNode, src_height);
    morph_in.on('start', function () {
        resize_anim.run();
    });
    return morph_in;
};

/**
 * Create an animation for resizing the given node.
 *
 * @method _create_resize
 */
module._create_resize = function(srcNode, height) {
    var resize = new Y.Anim({
        node: srcNode,
        to: {height: height},
        duration: 0.5,
        easing: 'easeOut'
        });
    resize.on('end', function () {
        srcNode.setStyle('height', 'auto');
        resize.fire('resized');
    });
    return resize;
};

Y.extend(Morph, Y.Widget, {
    initializer: function(cfg) {
        if (Y.Lang.isValue(cfg.animate)) {
            this._animate = cfg.animate;
        }
        else {
            this._animate = true;
        }
    },

    /**
     * Animate between the original and new content.
     *
     * @method morph
     * @param {Boolean} reverse: whether or not the widget should morph in the
            new content or return to the original content.
     */
    morph: function(reverse) {
        if (!Y.Lang.isValue(reverse)) {
            reverse = false;
        }
        var srcNode = this.get(reverse ? 'targetNode' : 'srcNode');
        var targetNode = this.get(reverse ? 'srcNode' : 'targetNode');
        if (this._animate) {
            module._create_morph(srcNode, targetNode, this).run();
        }
        else {
            targetNode.addClass('hidden');
            srcNode.removeClass('hidden');
        }
    }

});

module.Morph = Morph;

}, '0.1', {'requires': ['widget', 'node', 'anim']});
