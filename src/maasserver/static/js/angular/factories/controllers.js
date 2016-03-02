/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Controllers Manager
 *
 * Manages all of the controllers in the browser. This manager is used for the
 * controller listing and view pages. The manager is a subclass of
 * NodesManager.
 */

angular.module('MAAS').factory(
    'ControllersManager',
    ['$q', '$rootScope', 'RegionConnection', 'NodesManager', function(
            $q, $rootScope, RegionConnection, NodesManager) {

        function ControllersManager() {
            NodesManager.call(this);

            this._pk = "system_id";
            this._handler = "controller";

            // Listen for notify events for the machine object.
            var self = this;
            RegionConnection.registerNotifier("controller",
                function(action, data) {
                    self.onNotify(action, data);
                });
        }
        ControllersManager.prototype = new NodesManager();
        return new ControllersManager();
    }]);
