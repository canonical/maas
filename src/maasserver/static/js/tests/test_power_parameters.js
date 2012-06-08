/* Copyright 2012 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 */

YUI({ useBrowserConsole: true }).add(
    'maas.power_parameters.tests', function(Y) {

Y.log('loading maas.power_parameters.tests');
var namespace = Y.namespace('maas.power_parameters.tests');

var module = Y.maas.power_parameters;
var suite = new Y.Test.Suite("maas.power_parameters Tests");

var select_node_template = Y.one('#select_node').getContent();
var target_node_template = Y.one('#target_node').getContent();

suite.add(new Y.maas.testing.TestCase({
    name: 'test-power_parameters',

    setUp: function () {
        Y.one('#placeholder').empty().append(
            Y.Node.create(select_node_template).append(
                Y.Node.create(target_node_template)));
    },

    testInitializerSetsUpVariables: function() {
        var widget = new Y.maas.power_parameters.LinkedContentWidget({
            srcNode: '.power_parameters',
            driverEnum: ENUM,
            templatePrefix: '#prefix-'
            });
        Y.Assert.areEqual(ENUM, widget.driverEnum);
        Y.Assert.areEqual('#prefix-', widget.templatePrefix);
    },

    testInitializerInitializesTemplates: function() {
        var widget = new Y.maas.power_parameters.LinkedContentWidget({
            srcNode: '.power_parameters',
            driverEnum: ENUM,
            templatePrefix: '#prefix-'
            });
        var key;
        for (key in ENUM) {
            if (ENUM.hasOwnProperty(key)) {
                var value = ENUM[key];
                var template = Y.one('#prefix-' + value).getContent();
                Y.Assert.areEqual(template, widget.templates[value]);
            }
        }
    },

    testBindToSetsVisibility: function() {
        var widget = new Y.maas.power_parameters.LinkedContentWidget({
            srcNode: '.power_parameters',
            driverEnum: ENUM,
            templatePrefix: '#prefix-'
            });
        widget.bindTo(Y.one('.power_type').one('select'), 'change');
        Y.Assert.isTrue(Y.one('.power_parameters').hasClass('hidden'));
    },

    testchangingTheDriversValueUpdatesSrcNode: function() {
        var widget = new Y.maas.power_parameters.LinkedContentWidget({
            srcNode: '.power_parameters',
            driverEnum: ENUM,
            templatePrefix: '#prefix-'
            });
        widget.bindTo(Y.one('.power_type').one('select'), 'change');
        // Simulate setting a new value in the driver's <select> widget.
        var newValue = 'value1';
        var select = Y.one('.power_type').one('select');
        select.set('value', newValue);
        select.simulate('change');
        Y.Assert.isFalse(Y.one('.power_parameters').hasClass('hidden'));
        var template = Y.one('#prefix-' + newValue).getContent();
        Y.Assert.areEqual(
            template, Y.one('.power_parameters').get('innerHTML'));
    }


}));

namespace.suite = suite;

}, '0.1', {'requires': [
    'node-event-simulate', 'test', 'maas.testing', 'maas.power_parameters']}
);
