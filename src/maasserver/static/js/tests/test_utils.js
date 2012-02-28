/* Copyright 2012 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 */

YUI({ useBrowserConsole: true }).add('maas.utils.tests', function(Y) {

Y.log('loading mass.utils.tests');
var namespace = Y.namespace('maas.utils.tests');

var module = Y.maas.utils;
var suite = new Y.Test.Suite("maas.utils Tests");

suite.add(new Y.maas.testing.TestCase({
    name: 'test-utils'

}));

namespace.suite = suite;

}, '0.1', {'requires': [
    'node', 'test', 'maas.testing', 'maas.utils']}
);
