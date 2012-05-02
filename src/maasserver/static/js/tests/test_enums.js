/* Copyright 2012 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 */

YUI({ useBrowserConsole: true }).add('maas.enums.tests', function(Y) {

Y.log('loading maas.enums.tests');
var namespace = Y.namespace('maas.enums.tests');

var module = Y.maas.enums;
var suite = new Y.Test.Suite("maas.enums Tests");

suite.add(new Y.maas.testing.TestCase({
    name: 'test-enums',

    testDefinesEnums: function() {
        Y.Assert.isObject(Y.maas.enums.NODE_STATUS);
    },

    testHasEnumValues: function() {
        Y.Assert.isNotUndefined(Y.maas.enums.NODE_STATUS.READY);
        Y.Assert.isNotNull(Y.maas.enums.NODE_STATUS.READY);
    },

    testDistinguishesValues: function() {
        Y.Assert.areNotEqual(
            Y.maas.enums.NODE_STATUS.READY,
            Y.maas.enums.NODE_STATUS.RETIRED,
            "Different values of an enum were equal somehow.")
    }
}));

namespace.suite = suite;

}, '0.1', {'requires': [
    'node-event-simulate', 'test', 'maas.testing', 'maas.enums']}
);
