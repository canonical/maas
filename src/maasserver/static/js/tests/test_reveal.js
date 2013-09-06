/* Copyright 2012, 2013 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 */

YUI({ useBrowserConsole: true }).add('maas.reveal.tests', function(Y) {

Y.log('loading maas.reveal.tests');
var namespace = Y.namespace('maas.reveal.tests');

var module = Y.maas.reveal;
var suite = new Y.Test.Suite("maas.reveal Tests");

suite.add(new Y.maas.testing.TestCase({
    name: 'test-revealing',

    setUp: function() {
        Y.one('#placeholder').setHTML('');
    },

    // Create a content div (in its visible state).
    make_div: function(html_content) {
        if (html_content === undefined) {
            html_content = "<pre>Arbitrary content</pre>";
        }
        // Hook this new DOM node into the document, so that it has proper
        // display attributes.  Otherwise we can't simulate and verify its
        // appearing or disappearing.
        return Y.one('#placeholder').appendChild(
            '<div>' + html_content + '</div>');
    },

    // Create a button link.
    make_link: function(link_content) {
        if (link_content === undefined) {
            link_content = "Arbitrary link text";
        }
        return Y.Node.create('<a href="#">' + link_content + '</a>');
    },

    // Make a content div look to the widget as if it's been hidden.
    hide_div: function(node) {
        node.setStyle('height', '0');
    },

    get_reveal: function() {
        var cfg = {
            linkNode: Y.one('.link'),
            targetNode: Y.one('.panel'),
            showText: 'View log',
            hideText: 'Hide log',
            quick: true
        };
        return new module.Reveal(cfg);
    },

    test_is_visible_returns_true_for_nonzero_height: function() {
        var revealer = new module.Reveal({
            linkNode: this.make_link(),
            targetNode: this.make_div(),
            quick: true
        });
        revealer.render();

        Y.assert(
            revealer.is_visible(),
            "is_visible() fails to recognize div as visible.");
    },

    test_is_visible_returns_false_for_zero_height: function() {
        var div = this.make_div();
        var revealer = new module.Reveal({
            linkNode: this.make_link(),
            targetNode: div,
            quick: true
        });
        revealer.render();

        div.setStyle('height', '0');

        Y.assert(
            !revealer.is_visible(),
            "is_visible() thinks that div is visible when it isn't.");
    },

    test_get_animation_duration_defaults_to_suggested_duration: function() {
        var revealer = new module.Reveal({
            linkNode: this.make_link(),
            targetNode: this.make_div()
        });

        Y.Assert.areEqual(5, revealer.get_animation_duration(5));
    },

    test_get_animation_duration_returns_mere_wink_if_quick_is_set: function() {
        var revealer = new module.Reveal({
            linkNode: this.make_link(),
            targetNode: this.make_div(),
            quick: true
        });
        var suggested_duration = 5;
        var duration = revealer.get_animation_duration(suggested_duration);

        Y.Assert.areNotEqual(suggested_duration, duration);
        Y.assert(duration < suggested_duration, "'Quick' duration is longer.");
        Y.assert(duration < 0.1, "'Quick' duration is still fairly long.");
    },

    test_set_hidden_link_sets_show_text: function() {
        var link = this.make_link("Original link");
        var revealer = new module.Reveal({
            linkNode: link,
            targetNode: this.make_div(),
            showText: "Show content",
            hideText: "Hide content",
            quick: true
        });

        revealer.set_hidden_link(link);

        Y.Assert.areEqual("Show content", link.get('text'));
    },

    test_set_hidden_link_does_nothing_if_show_text_not_set: function() {
        var link = this.make_link("Original link");
        var revealer = new module.Reveal({
            linkNode: link,
            targetNode: this.make_div(),
            hideText: "Hide content",
            quick: true
        });

        revealer.set_hidden_link(link);

        Y.Assert.areEqual("Original link", link.get('text'));
    },

    test_set_visible_link_sets_hide_text: function() {
        var link = this.make_link("Original link");
        var revealer = new module.Reveal({
            linkNode: link,
            targetNode: this.make_div(),
            showText: "Show content",
            hideText: "Hide content",
            quick: true
        });

        revealer.set_visible_link(link);

        Y.Assert.areEqual("Hide content", link.get('text'));
    },

    test_set_visible_link_does_nothing_if_hide_text_not_set: function() {
        var link = this.make_link("Original link");
        var revealer = new module.Reveal({
            linkNode: link,
            targetNode: this.make_div(),
            showText: "Show content",
            quick: true
        });

        revealer.set_visible_link(link);

        Y.Assert.areEqual("Original link", link.get('text'));
    },

    test_slides_out: function() {
        var original_height = (
            parseInt(Y.one('.panel .content').getStyle('height')) +
            parseInt(Y.one('.panel .content').getStyle('marginTop')) +
            parseInt(Y.one('.panel .content').getStyle('marginBottom')) +
            parseInt(Y.one('.panel .content').getStyle('paddingTop')) +
            parseInt(Y.one('.panel .content').getStyle('paddingBottom')));
        Y.one('.panel').setStyle('height', '0');
        Y.one('.link').set('text', 'View log');
        Y.Assert.areEqual('View log', Y.one('.link').get('text'));
        Y.Assert.areEqual(0, parseInt(Y.one('.panel').getStyle('height')));
        var revealer = this.get_reveal(true);
        var self = this;
        revealer.on('revealed', function () {
            self.resume(function() {
                Y.assert(
                    parseInt(Y.one('.panel').getStyle('height')) > 0, 
                    'The panel should be revealed'
                    );
                Y.Assert.areEqual(
                    original_height,
                    parseInt(Y.one('.panel').getStyle('height')), 
                    'The panel has not been resized properly'
                    );
                Y.Assert.areEqual('Hide log', Y.one('.link').get('text'));
            });
        });
        revealer.reveal();
        this.wait();
    },

    test_slides_in: function() {
        Y.one('.panel').setStyle('height', '20');
        Y.one('.link').set('text', 'Hide log');
        Y.Assert.areEqual('Hide log', Y.one('.link').get('text'));
        Y.Assert.areEqual(20, parseInt(Y.one('.panel').getStyle('height')));
        var revealer = this.get_reveal(true);
        var self = this;
        revealer.on('hidden', function () {
            self.resume(function() {
                Y.Assert.areEqual(
                    0,
                    parseInt(Y.one('.panel').getStyle('height')), 
                    'The panel should be hidden'
                    );
                Y.Assert.areEqual('View log', Y.one('.link').get('text'));
            });
        });
        revealer.reveal();
        this.wait();
    }
}));

namespace.suite = suite;

}, '0.1', {'requires': [
    'test', 'maas.testing', 'maas.reveal']}
);
