/* Copyright 2012, 2013 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Widget to expand (make visible) or fold (make invisible) a content div,
 * in response to clicks on a button link.
 *
 * Write your initial HTML for the visible state.  If the client does not
 * execute the script, the content div will be visible.  Upon initialization,
 * the widget immediately goes into its "hidden" state.
 *
 * Once the widget is set up, its reveal() method will toggle it between its
 * visible and invisible states.  The transition is animated with a sliding
 * effect.
 *
 * Synonyms: expander, collapsible, foldable.
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
     * DOM node for the button link that triggers the reveal.
     *
     * @attribute linkNode
     * @type node
     */
    linkNode: {
        value: null
    },

    /**
     * The text the button link should contain when the content div is
     * visible.
     *
     * @attribute hideText
     * @type string
     */
    hideText: {
        value: null
    },

    /**
     * The text the button link should contain when the content div is hidden.
     *
     * @attribute showText
     * @type string
     */
    showText: {
        value: null
    },

    /**
     * Skip animations?
     *
     * Use this when testing, to avoid wasting time on delays.
     *
     * @attribute quick
     * @type bool
     */
    quick: {
        value: false
    }
};

Y.extend(Reveal, Y.Widget, {
    /**
     * Is this widget currently in its visible state?
     *
     * @method is_visible
     */
    is_visible: function() {
        var height = parseInt(this.get('targetNode').getStyle('height'));
        return height > 0;
    },

    /**
     * Set link to its "hidden" state.
     *
     * @method set_hidden_link
     */
    set_hidden_link: function(link) {
        var new_text = this.get('showText');
        if (new_text !== null && new_text !== undefined) {
            link.set('text', new_text);
        }
    },

    /**
     * Set link to its "visible" state.
     *
     * @method set_visible_link
     */
    set_visible_link: function(link) {
        var new_text = this.get('hideText');
        if (new_text !== null && new_text !== undefined) {
            link.set('text', new_text);
        }
    },

    /**
     * Get the desired duration for an animation.
     *
     * Returns the suggested duration, unless the "quick" attribute is set
     * in which case it returns a very brief duration.
     *
     * @method get_animation_duration
     */
    get_animation_duration: function(suggested_duration) {
        if (this.get('quick')) {
            return 0.01;
        }
        else {
            return suggested_duration;
        }
    },

    /**
     * Create the animation for sliding in the content div.
     *
     * @method create_slide_in
     */
    create_slide_in: function(node, publisher) {
        var anim = new Y.Anim({
            node: node,
            duration: this.get_animation_duration(0.3),
            to: {height: 0}
        });
        anim.on('end', function() {
            publisher.fire('hidden');
        });
        return anim;
    },

    /**
     * Create the animation for sliding out the content div.
     *
     * @method create_slide_out
     */
    create_slide_out: function(node, publisher) {
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
            duration: this.get_animation_duration(0.2),
            to: {height: new_height}
        });
        anim.on('end', function() {
            publisher.fire('revealed');
        });
        return anim;
    },

    /**
     * Toggle between the hidden and revealed states.
     *
     * @method reveal
     */
    reveal: function() {
        var target = this.get('targetNode');
        var link = this.get('linkNode');
        if (this.is_visible()) {
            this.create_slide_in(target, this).run();
            this.set_hidden_link(link);
        }
        else {
            this.create_slide_out(target, this).run();
            this.set_visible_link(link);
        }
    }
});

module.Reveal = Reveal;

}, '0.1', {'requires': ['widget', 'node', 'event', 'anim']});
