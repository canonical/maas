/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS VLAN Manager
 *
 * Manages all of the VLANs in the browser. The manager uses the
 * RegionConnection to load the VLANs, update the VLANs, and listen for
 * notification events about VLANs.
 */

angular.module('MAAS').factory(
    'VLANsManager',
    ['$q', '$rootScope', 'RegionConnection', 'Manager', 'SubnetsManager',
    function($q, $rootScope, RegionConnection, Manager, SubnetsManager) {

        function VLANsManager() {
            Manager.call(this);

            this._pk = "id";
            this._handler = "vlan";

            // Listen for notify events for the vlan object.
            var self = this;
            RegionConnection.registerNotifier("vlan",
                function(action, data) {
                    self.onNotify(action, data);
                });
        }

        VLANsManager.prototype = new Manager();

        // Return the Subnet objects that are part of this VLAN. The returned
        // array is calculated on each call, you should not watch this array,
        // instead you should watch this function.
        VLANsManager.prototype.getSubnets = function(vlan) {
            var subnets = [];
            angular.forEach(vlan.subnet_ids, function(subnet_id) {
                var subnet = SubnetsManager.getItemFromList(subnet_id);
                if(angular.isObject(subnet)) {
                    subnets.push(subnet);
                }
            });
            return subnets;
        };

        return new VLANsManager();
    }]);
