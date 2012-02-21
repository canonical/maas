/* Copyright 2012 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Widget to show user options.
 *
 * @module Y.maas.user_panel
 */

YUI.add('maas.user_panel', function(Y) {

Y.log('loading maas.user_panel');

var module = Y.namespace('maas.user_panel');

module._user_panel_singleton = null;

/**
 * Initialise a widget to display user options.
 *
 * @method createUserPanelWidget
 */
module.createUserPanelWidget = function(event) {
    Y.Base.mix(Y.Overlay, [Y.WidgetAutohide]);
    
    var cfg = {
        srcNode: '#user-options',
        align: {node:'#global-header',
                points: [Y.WidgetPositionAlign.TR, Y.WidgetPositionAlign.BR]},
        width: '150px',
        zIndex: 2,
        hideOn: [{eventName: 'clickoutside'}],
        visible: false,
        render: true
        };
    module._user_panel_singleton = new Y.Overlay(cfg);
    Y.one(cfg.srcNode).removeClass('hidden');
};

/**
 * Show a widget to display user options.
 *
 * @method showUserPanelWidget
 */
module.showUserPanelWidget = function(event) {
    // Cope with manual calls as well as event calls.
    if (Y.Lang.isValue(event)) {
        event.preventDefault();
    }
    module._user_panel_singleton.show();
};

}, '0.1', {'requires': ['overlay', 'base-build', 'widget-autohide']}
);
