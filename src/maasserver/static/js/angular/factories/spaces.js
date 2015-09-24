/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Space Manager
 *
 * Manages all of the spaces in the browser. The manager uses the
 * RegionConnection to load the spaces, update the spaces, and listen for
 * notification events about spaces.
 */

angular.module('MAAS').factory(
    'SpacesManager',
    ['$q', '$rootScope', 'RegionConnection', 'Manager', 'SubnetsManager',
    function($q, $rootScope, RegionConnection, Manager, SubnetsManager) {

        function SpacesManager() {
            Manager.call(this);

            this._pk = "id";
            this._handler = "space";

            // Listen for notify events for the space object.
            var self = this;
            RegionConnection.registerNotifier("space",
                function(action, data) {
                    self.onNotify(action, data);
                });
        }

        SpacesManager.prototype = new Manager();

        // Return the Subnet objects that are part of this space. The returned
        // array is calculated on each call, you should not watch this array,
        // instead you should watch this function.
        SpacesManager.prototype.getSubnets = function(space) {
            var subnets = [];
            angular.forEach(space.subnet_ids, function(subnet_id) {
                var subnet = SubnetsManager.getItemFromList(subnet_id);
                if(angular.isObject(subnet)) {
                    subnets.push(subnet);
                }
            });
            return subnets;
        };

        return new SpacesManager();
    }]);
