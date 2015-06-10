/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 */

YUI({ useBrowserConsole: true }).add(
    'maas.os_distro_select.tests', function(Y) {

Y.log('loading maas.os_distro_select.tests');
var namespace = Y.namespace('maas.os_distro_select.tests');

var module = Y.maas.os_distro_select;
var suite = new Y.Test.Suite("maas.os_distro_select Tests");

var select_node_template = Y.one('#select_node').getContent();
var target_node_template = Y.one('#target_node').getContent();

suite.add(new Y.maas.testing.TestCase({
    name: 'test-os_distro_select',

    setUp: function () {
        Y.one('#placeholder').empty().append(
            Y.Node.create(select_node_template).append(
                Y.Node.create(target_node_template)));
        this.widget = new Y.maas.os_distro_select.OSReleaseWidget({
            srcNode: '#id_distro_series'
            });
    },

    testBindCallsSwitchTo: function() {
        var called = false;
        this.widget.switchTo = function() {
            called = true;
        };
        this.widget.bindTo(Y.one('#id_osystem'), 'change');
        Y.Assert.isTrue(called);
    },

    testSwitchToCalledModifyOptionOnAll: function() {
        var options = [];
        this.widget.modifyOption = function(option, value) {
            options.push(option);
        };
        this.widget.bindTo(Y.one('#id_osystem'), 'change');
        var expected = Y.one('#id_distro_series').all('option');
        Y.ArrayAssert.containsItems(expected, options);
    },

    testSwitchToTogglesInitialSkip: function() {
        this.widget.bindTo(Y.one('#id_osystem'), 'change');
        Y.Assert.isFalse(this.widget.initialSkip);
    },

    testSwitchToCallsSelectVisableOption: function() {
        var called = false;
        this.widget.selectVisableOption = function() {
            called = true;
        };
        this.widget.initialSkip = false;
        this.widget.bindTo(Y.one('#id_osystem'), 'change');
        Y.Assert.isTrue(called);
    },

    testModifyOptionSelectsDefault: function() {
        var option = Y.Mock();
        Y.Mock.expect(option, {
            method: "get",
            args: ["value"],
            returns: ""
            });
        Y.Mock.expect(option, {
            method: "removeClass",
            args: ["hidden"]
            });
        Y.Mock.expect(option, {
            method: "set",
            args: ["selected", "selected"]
            });
        var selected = this.widget.modifyOption(option, '');
        Y.Mock.verify(option);
        Y.Assert.isFalse(selected);
    },

    testModifyOptionHidesNonDefault: function() {
        var option = Y.Mock();
        Y.Mock.expect(option, {
            method: "get",
            args: ["value"],
            returns: "value1"
            });
        Y.Mock.expect(option, {
            method: "addClass",
            args: ["hidden"]
            });
        var selected = this.widget.modifyOption(option, '');
        Y.Mock.verify(option);
        Y.Assert.isFalse(selected);
    },

    testModifyOptionShowsOSMatch: function() {
        var option = Y.Mock();
        Y.Mock.expect(option, {
            method: "get",
            args: ["value"],
            returns: "os/release"
            });
        Y.Mock.expect(option, {
            method: "removeClass",
            args: ["hidden"]
            });
        var selected = this.widget.modifyOption(option, 'os');
        Y.Mock.verify(option);
        Y.Assert.isFalse(selected);
    },

    testModifyOptionSelectsOSDefault: function() {
        var option = Y.Mock();
        Y.Mock.expect(option, {
            method: "get",
            args: ["value"],
            returns: "os/"
            });
        Y.Mock.expect(option, {
            method: "removeClass",
            args: ["hidden"]
            });
        Y.Mock.expect(option, {
            method: "set",
            args: ["selected", "selected"]
            });
        this.widget.initialSkip = false;
        var selected = this.widget.modifyOption(option, 'os');
        Y.Mock.verify(option);
        Y.Assert.isTrue(selected);
    },

    testModifyOptionSelectsOSDefaultSkippedOnInitial: function() {
        var option = Y.Mock();
        Y.Mock.expect(option, {
            method: "get",
            args: ["value"],
            returns: "os/"
            });
        Y.Mock.expect(option, {
            method: "removeClass",
            args: ["hidden"]
            });
        var selected = this.widget.modifyOption(option, 'os');
        Y.Mock.verify(option);
        Y.Assert.isFalse(selected);
    },

    testModifyOptionHidesOSMismatch: function() {
        var option = Y.Mock();
        Y.Mock.expect(option, {
            method: "get",
            args: ["value"],
            returns: "os/release"
            });
        Y.Mock.expect(option, {
            method: "addClass",
            args: ["hidden"]
            });
        var selected = this.widget.modifyOption(option, 'other');
        Y.Mock.verify(option);
        Y.Assert.isFalse(selected);
    },

    testSelectVisableOptionShowsFirstVisable: function() {
        var option = Y.Mock();
        var option2 = Y.Mock();
        Y.Mock.expect(option, {
            method: "hasClass",
            args: ["hidden"],
            returns: true
            });
        Y.Mock.expect(option2, {
            method: "hasClass",
            args: ["hidden"],
            returns: false
            });
        Y.Mock.expect(option2, {
            method: "set",
            args: ["selected", "selected"]
            });

        var options = Y.Array([option, option2]);
        this.widget.selectVisableOption(options);
        Y.Mock.verify(option);
        Y.Mock.verify(option2);
    }

}));

namespace.suite = suite;

}, '0.1', {'requires': [
    'node-event-simulate', 'test', 'maas.testing', 'maas.os_distro_select']}
);
