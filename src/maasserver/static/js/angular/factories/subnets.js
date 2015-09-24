/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Subnet Manager
 *
 * Manages all of the subnets in the browser. The manager uses the
 * RegionConnection to load the subnets, update the subnets, and listen for
 * notification events about subnets.
 */

angular.module('MAAS').factory(
    'SubnetsManager',
    ['$q', '$rootScope', 'RegionConnection', 'Manager', function(
            $q, $rootScope, RegionConnection, Manager) {

        function SubnetsManager() {
            Manager.call(this);

            this._pk = "id";
            this._handler = "subnet";

            // Listen for notify events for the subnet object.
            var self = this;
            RegionConnection.registerNotifier("subnet",
                function(action, data) {
                    self.onNotify(action, data);
                });
        }

        SubnetsManager.prototype = new Manager();

        return new SubnetsManager();
    }]);
