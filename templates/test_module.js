/* Copyright 2012 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 */

// TODO: Replace "sample" with module name throughout.
YUI({ useBrowserConsole: true }).add('maas.sample.tests', function(Y) {

Y.log('loading maas.sample.tests');
var namespace = Y.namespace('maas.sample.tests');

var module = Y.maas.sample;
var suite = new Y.Test.Suite("maas.sample Tests");

suite.add(new Y.maas.testing.TestCase({
    name: 'test-sample',

    testMe: function() {
        Y.Assert.areTrue(true);
    }

}));

namespace.suite = suite;

}, '0.1', {'requires': [
    'node-event-simulate', 'test', 'maas.testing', 'maas.sample']}
);
