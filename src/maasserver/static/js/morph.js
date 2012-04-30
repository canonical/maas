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

Y.extend(Morph, Y.Widget, {
    initializer: function(cfg) {
        if (Y.Lang.isValue(cfg.animate)) {
            this._animate = cfg.animate;
        }
        else {
            this._animate = true;
        }
    },

    morph: function(reverse) {
        var srcNode = this.get(reverse ? 'targetNode' : 'srcNode');
        var targetNode = this.get(reverse ? 'srcNode' : 'targetNode');
        if (this._animate) {
            var target_height = targetNode.getComputedStyle('height');
            var fade_out = new Y.Anim({
                node: targetNode,
                to: {opacity: 0},
                duration: 0.2,
                easing: 'easeOut'
                });
            var self = this;
            fade_out.on('end', function () {
                targetNode.addClass('hidden');
                srcNode.setStyle('opacity', 0);
                srcNode.removeClass('hidden');
                var src_height = srcNode.getComputedStyle('height')
                    .replace('px', '');
                srcNode.setStyle('height', target_height);
                var fade_in = new Y.Anim({
                    node: srcNode,
                    to: {opacity: 1},
                    duration: 1,
                    easing: 'easeIn'
                    });
                var resize = new Y.Anim({
                    node: srcNode,
                    to: {height: src_height},
                    duration: 0.5,
                    easing: 'easeOut'
                    });
                resize.on('end', function () {
                    srcNode.setStyle('height', 'auto');
                    self.fire('morphed');
                });
                fade_in.run();
                resize.run();
            });
            fade_out.run();
        }
        else {
            targetNode.addClass('hidden');
            srcNode.removeClass('hidden');
        }
    }
});

module.Morph = Morph;

}, '0.1', {'requires': ['widget', 'node', 'anim']});
