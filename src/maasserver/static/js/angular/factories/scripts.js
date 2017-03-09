/* Copyright 2017 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS ScriptsManager Manager
 *
 * Manages all of the DHCPSnippets in the browser. The manager uses the
 * RegionConnection to load the DHCPSnippets, update the DHCPSnippets, and
 * listen for notification events about DHCPSnippets.
 */

angular.module('MAAS').factory(
    'ScriptsManager',
    ['$q', '$rootScope', 'RegionConnection', 'Manager',
    function($q, $rootScope, RegionConnection, Manager) {

        function ScriptsManager() {
            Manager.call(this);

            this._pk = "id";
            this._handler = "script";

            // Listen for notify events for the Script object.
            var self = this;
            RegionConnection.registerNotifier("script",
                function(action, data) {
                    self.onNotify(action, data);
                });
        }

        ScriptsManager.prototype = new Manager();

        return new ScriptsManager();
    }]);
