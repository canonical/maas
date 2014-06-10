/* Copyright 2014 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 */

YUI({ useBrowserConsole: true }).add(
    'maas.license_key.tests', function(Y) {

Y.log('loading maas.license_key.tests');
var namespace = Y.namespace('maas.license_key.tests');

var module = Y.maas.license_key;
var suite = new Y.Test.Suite("maas.license_key Tests");

var select_node_template = Y.one('#select_node').getContent();
var target_node_template = Y.one('#target_node').getContent();

suite.add(new Y.maas.testing.TestCase({
    name: 'test-license_key',

    setUp: function () {
        Y.one('#placeholder').empty().append(
            Y.Node.create(select_node_template).append(
                Y.Node.create(target_node_template)));
    },

    testBindToHidesLicenseKey: function() {
        var widget = new Y.maas.license_key.LicenseKeyWidget({
            srcNode: '.license_key',
            });
        widget.bindTo(Y.one('#id_distro_series'), 'change');

        var div = Y.one('.license_key');
        Y.Assert.isFalse(div.hasClass('hidden'));
    },

    testUpdateToNonHideShowsLicenseKey: function() {
        var widget = new Y.maas.license_key.LicenseKeyWidget({
            srcNode: '.license_key',
            });
        widget.bindTo(Y.one('#id_distro_series'), 'change');

        var newValue = 'value1/series2';
        var select = Y.one('#id_distro_series');
        select.set('value', newValue);
        select.simulate('change');

        var div = Y.one('.license_key');
        Y.Assert.isTrue(div.hasClass('hidden'));
    }

}));

namespace.suite = suite;

}, '0.1', {'requires': [
    'node-event-simulate', 'test', 'maas.testing', 'maas.license_key']}
);
