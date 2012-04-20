/* Copyright 2012 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 */

YUI({ useBrowserConsole: true }).add('maas.morph.tests', function(Y) {

Y.log('loading maas.morph.tests');
var namespace = Y.namespace('maas.morph.tests');

var module = Y.maas.morph;
var suite = new Y.Test.Suite("maas.morph Tests");

suite.add(new Y.maas.testing.TestCase({
    name: 'test-morphing',

    testMorphing: function() {
        var cfg = {
            srcNode: '#panel-two',
            targetNode: '#panel-one'
        };
        var morpher = new module.Morph(cfg);
        Y.Assert.isFalse(
            Y.one('#panel-one').hasClass('hidden'),
            'The target panel should initially be visible');
        Y.Assert.isTrue(
            Y.one('#panel-two').hasClass('hidden'),
            'The source panel should initially be hidden');
        var morphed_fired = false;
        morpher.on('morphed', function() {
            morphed_fired = true;
        });
        morpher.morph();
        this.wait(function() {
            Y.Assert.isTrue(
                Y.one(cfg.targetNode).hasClass('hidden'),
                'The target panel should now be hidden');
            Y.Assert.isFalse(
                Y.one(cfg.srcNode).hasClass('hidden'),
                'The source panel should now be visible');
            Y.Assert.isTrue(
                morphed_fired,
                'The morphed event should have fired');
            Y.Assert.areEqual(
                'auto',
                Y.one(cfg.srcNode).getStyle('height'),
                'The morpher should set the height back to auto');
            /* Fire this morph again, this time for the reverse. */
            morpher.morph(true);
            this.wait(function() {
                Y.Assert.isFalse(
                    Y.one(cfg.targetNode).hasClass('hidden'),
                    'The target panel should now be visible again');
                Y.Assert.isTrue(
                    Y.one(cfg.srcNode).hasClass('hidden'),
                    'The source panel should now be hidden again');
            }, 2000);
        }, 2000);
    }
}));

namespace.suite = suite;

}, '0.1', {'requires': [
    'node-event-simulate', 'test', 'maas.testing', 'maas.morph']}
);
