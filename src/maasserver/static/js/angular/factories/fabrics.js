/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Fabric Manager
 *
 * Manages all of the fabrics in the browser. The manager uses the
 * RegionConnection to load the fabrics, update the fabrics, and listen for
 * notification events about fabrics.
 */

angular.module('MAAS').factory(
    'FabricsManager',
    ['$q', '$rootScope', 'RegionConnection', 'Manager', 'VLANsManager',
    function($q, $rootScope, RegionConnection, Manager, VLANsManager) {

        function FabricsManager() {
            Manager.call(this);

            this._pk = "id";
            this._handler = "fabric";

            // Listen for notify events for the fabric object.
            var self = this;
            RegionConnection.registerNotifier("fabric",
                function(action, data) {
                    self.onNotify(action, data);
                });
        }

        FabricsManager.prototype = new Manager();

        // Return the VLAN objects that are part of this fabric. The returned
        // array is calculated on each call, you should not watch this array,
        // instead you should watch this function.
        FabricsManager.prototype.getVLANs = function(fabric) {
            var vlans = [];
            angular.forEach(fabric.vlan_ids, function(vlan_id) {
                var vlan = VLANsManager.getItemFromList(vlan_id);
                if(angular.isObject(vlan)) {
                    vlans.push(vlan);
                }
            });
            return vlans;
        };

        return new FabricsManager();
    }]);
