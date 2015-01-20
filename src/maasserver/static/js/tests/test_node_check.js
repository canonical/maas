/* Copyright 2014 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 */

YUI({ useBrowserConsole: true }).add('maas.node_check.tests', function(Y) {

Y.log('loading maas.node_check.tests');
var namespace = Y.namespace('maas.node_check.tests');

var module = Y.maas.node_check;
var suite = new Y.Test.Suite("maas.node_check Tests");

var template = Y.one('#template').getContent();

suite.add(new Y.maas.testing.TestCase({
    name: 'test-node_check',

    setUp: function() {
        Y.one("body").append(Y.Node.create(template));
    },

    createWidget: function(system_id) {
        var selector = '#placeholder';
        var widget = new module.PowerCheckWidget(
            {srcNode: selector, system_id: system_id});
        this.addCleanup(function() { widget.destroy(); });
        return widget;
    },

    testInitializer: function() {
        var widget = this.createWidget('system_id');
        widget.render();
        // The placeholders for errors and status have been created.
        var error_msg = Y.one('#placeholder').one('p.power-check-error');
        var status_check = Y.one('#placeholder').one('p.power-check-ok');
        Y.Assert.isNotNull(error_msg);
        Y.Assert.isNotNull(status_check);
    },

    testClickPowerCheckCall: function() {
        // A click on the button calls the API to query the power state.
        var log = this.logIO(module);
        var widget = this.createWidget('system_id');
        widget.render();
        var button = widget.button;
        button.simulate('click');
        Y.Assert.areEqual(1, log.length);
        var request_info = log.pop();
        Y.Assert.areEqual(
            MAAS_config.uris.nodes_handler + 'system_id', request_info[0]);
        Y.Assert.areEqual(
            "op=query_power_state", request_info[1].data);
    },

    testPowerCheckDisplaysOnResults: function() {
        // If the API call to check the power state returns
        // 'on', this is considered a success.
        var response = {
            state: 'on'
        };
        var log = this.mockSuccess(Y.JSON.stringify(response), module);
        var widget = this.createWidget('system_id');
        widget.render();
        var button = widget.button;
        button.simulate('click');
        Y.Assert.areEqual("", widget.get('error_text'));
        Y.Assert.areEqual(
            "Success: node is on.",
            widget.get('status_text'));
    },

    testPowerCheckDisplaysOffResults: function() {
        // If the API call to check the power state returns
        // 'off', this is considered a success.
        var response = {
            state: 'off'
        };
        var log = this.mockSuccess(Y.JSON.stringify(response), module);
        var widget = this.createWidget('system_id');
        widget.render();
        var button = widget.button;
        button.simulate('click');
        Y.Assert.areEqual(1, log.length);
        Y.Assert.areEqual("", widget.get('error_text'));
        Y.Assert.areEqual(
            "Success: node is off.",
            widget.get('status_text'));
    },

    testPowerCheckErrorDisplaysErrors: function() {
        // If the API call to check the power state errors, the error is
        // displayed.
        this.mockFailure('error message', module, 500);
        var widget = this.createWidget('system_id');
        widget.render();
        var button = widget.button;
        button.simulate('click');
        Y.Assert.areEqual(
            "Error: error message.",
            widget.get('error_text'));
        Y.Assert.areEqual("", widget.get('status_text'));
    },

    testPowerCheckDisplaysUnknownResults: function() {
        // If the API call to check the power state returns
        // something different than 'on' or 'off',
        // this is considered an error.
        var response = {
            state: 'unknown error'
        };
        var log = this.mockSuccess(Y.JSON.stringify(response), module);
        var widget = this.createWidget('system_id');
        widget.render();
        var button = widget.button;
        button.simulate('click');
        Y.Assert.areEqual(1, log.length);
        Y.Assert.areEqual(
            "Error: unknown error.", widget.get('error_text'));
        Y.Assert.areEqual("", widget.get('status_text'));
    }

}));

namespace.suite = suite;

}, '0.1', {'requires': [
    'node-event-simulate', 'node', 'test', 'maas.testing', 'maas.node_check']}
);
