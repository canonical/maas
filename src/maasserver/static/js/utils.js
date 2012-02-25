/* Copyright 2012 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MaaS utilities.
 *
 * @module Y.mass.utils
 */

YUI.add('maas.utils', function(Y) {

Y.log('loading mass.utils');
var module = Y.namespace('maas.utils');

/**
 * Return a valid tab (integer) index if the string 'index' contains a valid
 * tab index for the given 'tabview'.  Otherwise, return 'null'.
 *
 * @method getTabIndex
 */
module.getTabIndex = function(index, tabview) {
    var tab_index = parseInt(index, 10);
    var valid_tab_index = (
        Y.Lang.isValue(tab_index) &&
        tab_index >= 0 &&
        tab_index < tabview.size());
    if (valid_tab_index) {
        return tab_index;
    }
    else {
        return null;
    }
};

}, '0.1', {'requires': ['base']}
);
