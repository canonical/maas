/* Copyright 2012 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 */

YUI({ useBrowserConsole: true }).add('maas.utils.tests', function(Y) {

Y.log('loading mass.utils.tests');
var namespace = Y.namespace('maas.utils.tests');

var module = Y.maas.utils;
var suite = new Y.Test.Suite("maas.utils Tests");

var tabs_template = Y.one('#tabs_template').getContent();

suite.add(new Y.maas.testing.TestCase({
    name: 'test-utils',

    createTabs: function() {
        // Create a tab with 2 tabs (valid indexes: 0 or 1).
        Y.one("body").append(Y.Node.create(tabs_template));
        var tabs = new Y.TabView({srcNode: '#tabs'});
        tabs.render();
        return tabs;
    },

    testgetTabIndex_index_empty: function() {
        var tabs = this.createTabs();
        var index = module.getTabIndex('', tabs);
        Y.Assert.isNull(index);
    },

    testgetTabIndex_index_invalid: function() {
        var tabs = this.createTabs();
        var index = module.getTabIndex('invalid!', tabs);
        Y.Assert.isNull(index);
    },

    testgetTabIndex_index_too_big: function() {
        var tabs = this.createTabs();
        var index = module.getTabIndex('2', tabs);
        Y.Assert.isNull(index);
    },

    testgetTabIndex_index_neg: function() {
        var tabs = this.createTabs();
        var index = module.getTabIndex('-1', tabs);
        Y.Assert.isNull(index);
    },

    testgetTabIndex_index_ok: function() {
        var tabs = this.createTabs();
        var index = module.getTabIndex('0', tabs);
        Y.Assert.areEqual(0, index);
    }

}));

namespace.suite = suite;

}, '0.1', {'requires': [
    'tabview', 'node', 'test', 'maas.testing', 'maas.utils']}
);
