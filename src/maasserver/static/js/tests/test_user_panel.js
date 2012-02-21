/* Copyright 2012 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 */

YUI({ useBrowserConsole: true }).add('maas.user_panel.tests', function(Y) {

Y.log('loading maas.user_panel.tests');
var namespace = Y.namespace('maas.user_panel.tests');

var module = Y.maas.user_panel;
var suite = new Y.Test.Suite("maas.user_panel Tests");

suite.add(new Y.maas.testing.TestCase({
    name: 'test-user-panel-widget-singleton',

    testSingletonCreation: function() {
        Y.Assert.isNull(
            module._user_panel_singleton,
            'module._user_panel_singleton is originally null.');
        module.createUserPanelWidget();
        Y.Assert.isNotNull(
            module._user_panel_singleton,
            'module._user_panel_singleton is populated after the call to module.showAddNodeWidget.');
    }
}));

suite.add(new Y.maas.testing.TestCase({
    name: 'test-user-panel-widget-visibility',

    testWidgetShowing: function() {
        var overlay = module._user_panel_singleton;
        Y.Assert.isFalse(
        overlay.get('visible'),
            'When created the widget should not be visible');

        module.showUserPanelWidget();
        Y.Assert.isTrue(
            overlay.get('visible'),
            'We should be able to show the panel with showAddNodeWidget');
    },

    testWidgetHiding: function() {
        var overlay = module._user_panel_singleton;
        Y.Assert.isTrue(
            overlay.get('visible'),
            'The widget should current be visible');

        var link = Y.one('#user-options-link');
        link.simulate('click');
        Y.Assert.isFalse(
            overlay.get('visible'),
            'If an element outside the panel is clicked the panel should hide.');
    }
}));

namespace.suite = suite;

}, '0.1', {'requires': [
    'node-event-simulate', 'test', 'maas.testing', 'maas.user_panel']}
);
