/* Copyright 2012 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Widget to slide in a div.
 *
 * @module Y.maas.reveal
 */

YUI.add('maas.reveal', function(Y) {

Y.log('loading maas.reveal');

var module = Y.namespace('maas.reveal');

var Reveal;

Reveal = function(config) {
    Reveal.superclass.constructor.apply(this, arguments);
};

Reveal.NAME = 'reveal';

Reveal.ATTRS = {
    /**
     * The DOM node to be revealed from.
     *
     * @attribute targetNode
     * @type node
     */
    targetNode: {
        value: null
    },

    /**
     * The DOM node that triggers the reveal.
     *
     * @attribute linkNode
     * @type node
     */
    linkNode: {
        value: null
    },

    /**
     * The text the link should have when the div is visible.
     *
     * @attribute hideText
     * @type string
     */
    hideText: {
        value: null
    },

    /**
     * The text the link should have when the div is hidden.
     *
     * @attribute showText
     * @type string
     */
    showText: {
        value: null
    }
};

/**
 * Create the animation for sliding in the div.
 *
 * @method _create_slide_in
 */
module._create_slide_in = function(node, publisher) {
    var anim = new Y.Anim({
        node: node,
        duration: 0.3,
        to: {height: 0}
    });
    anim.on('end', function () {
        publisher.fire('hidden');
    });
    return anim;
};

/**
 * Create the animation for sliding out the div.
 *
 * @method _create_slide_out
 */
module._create_slide_out = function(node, publisher) {
    var content_node = node.one('.content');
    var height = parseInt(content_node.getStyle('height'));
    var padding_top = parseInt(content_node.getStyle('paddingTop'));
    var padding_bottom = parseInt(content_node.getStyle('paddingBottom'));
    var margin_top = parseInt(content_node.getStyle('marginTop'));
    var margin_bottom = parseInt(content_node.getStyle('marginBottom'));
    var new_height = (
	height + padding_top + padding_bottom + margin_top + margin_bottom);
    var anim = new Y.Anim({
        node: node,
        duration: 0.2,
        to: {height: new_height}
    });
    anim.on('end', function () {
        publisher.fire('revealed');
    });
    return anim;
};

Y.extend(Reveal, Y.Widget, {
    /**
     * Toggle the content.
     *
     * @method reveal
     */
    reveal: function() {
        var target = this.get('targetNode');
        var link = this.get('linkNode');
        if (parseInt(target.getStyle('height')) == 0) {
            module._create_slide_out(target, this).run();
            if (this.get('hideText') !== null) {
                link.set('text', this.get('hideText'));
            }
        }
        else {
            module._create_slide_in(target, this).run();
            if (this.get('showText') !== null) {
                link.set('text', this.get('showText'));
            }
        }
    }
});

module.Reveal = Reveal;

}, '0.1', {'requires': ['widget', 'node', 'event', 'anim']});
