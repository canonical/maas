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
 * The widget fires a "hiding" event before hiding, and "hidden" after.
 * Similarly, it fires "revealing" before revealing and "revealed" after.
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
     * DOM node for the content div.  This is the div that will be hidden
     * or revealed.  It must contain exactly one tag.
     *
     * The widget will add the "slider" class to this node, and the "content"
     * class to its child node.
     *
     * Hiding the content is done by setting the target node's height to zero;
     * it's child node keeps its original size but becomes invisible.
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


// Return a style attribute for a node, as an int.
// Any suffix to the number, such as the typical "px," is ignored.
function get_style_int(node, attribute) {
    return parseInt(node.getStyle(attribute));
}


Y.extend(Reveal, Y.Widget, {
    /**
     * Standard YUI hook: prepare the DOM for the widget.
     *
     * @method renderUI
     */
    renderUI: function() {
        var target = this.get('targetNode');
        target.addClass('slider');
        target.get('children').addClass('content');
    },

    /**
     * Standard YUI hook: install event listeners for the widget.
     *
     * @method bindUI
     */
    bindUI: function() {
        var self = this;
        this.get('linkNode').on('click', function(e) {
            e.preventDefault();
            self.reveal();
        });
    },

    /**
     * Standard YUI hook: update UI to match the widget's state at the time
     * it is rendered.
     *
     * The HTML is written in an expanded state, but during rendering, the
     * widget immediately (and without animation) goes into its hidden state.
     *
     * @method syncUI
     */
    syncUI: function() {
        this.fire("hiding");
        this.get('targetNode').setStyle('height', 0);
        this.set_hidden_link(this.get('linkNode'));
        this.fire("hidden");
    },

    /**
     * Is this widget currently in its visible state?
     *
     * @method is_visible
     */
    is_visible: function() {
        return get_style_int(this.get('targetNode'), 'height') > 0;
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
        // The target node contains exactly one node of content.  Its height
        // is constant.  We calculate the appropriate expanded height for the
        // target node from the height of the content node, plus marings and
        // padding.
        var content_node = node.one('.content');
        var new_height = (
            get_style_int(content_node, 'height') +
            get_style_int(content_node, 'paddingTop') +
            get_style_int(content_node, 'paddingBottom') +
            get_style_int(content_node, 'marginTop') +
            get_style_int(content_node, 'marginBottom'));
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
            this.fire('hiding');
            this.create_slide_in(target, this).run();
            this.set_hidden_link(link);
        }
        else {
            this.fire('revealing');
            this.create_slide_out(target, this).run();
            this.set_visible_link(link);
        }
    }
});

module.Reveal = Reveal;

}, '0.1', {'requires': ['widget', 'node', 'event', 'anim']});
