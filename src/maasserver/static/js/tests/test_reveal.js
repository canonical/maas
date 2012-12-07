/* Copyright 2012 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 */

YUI({ useBrowserConsole: true }).add('maas.reveal.tests', function(Y) {

Y.log('loading maas.reveal.tests');
var namespace = Y.namespace('maas.reveal.tests');

var module = Y.maas.reveal;
var suite = new Y.Test.Suite("maas.reveal Tests");

suite.add(new Y.maas.testing.TestCase({
    name: 'test-revealing',

    get_reveal: function() {
        var cfg = {
            linkNode: Y.one('.link'),
            targetNode: Y.one('.panel'),
            showText: 'View log',
            hideText: 'Hide log'
        };
        return new module.Reveal(cfg);
    },

    test_slides_out: function() {
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
