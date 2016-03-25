/* Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
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

        VLANsManager.prototype.getName = function(vlan) {
            var name = vlan.vid;
            if(vlan.vid === 0) {
                name = "untagged";
            } else if(angular.isString(vlan.name) && vlan.name !== "") {
                name += " (" + vlan.name + ")";
            }
            return name;
        };

        // Delete the VLAN.
        VLANsManager.prototype.deleteVLAN = function(vlan) {
            return RegionConnection.callMethod(
                "vlan.delete", { "id": vlan.id }, true);
        };

        // This is needed for testing: in the normal course of things,
        // rack_sids is generated entirely by the websocket handler.
        VLANsManager.prototype.addRackController = function(vlan, rack) {
            vlan.rack_sids.push(rack.system_id);
        };

        // Configure DHCP on the VLAN
        VLANsManager.prototype.configureDHCP = function(
           vlan, controllers, extra) {
           return RegionConnection.callMethod(
                "vlan.configure_dhcp", {
                    "id": vlan.id,
                    "controllers": controllers,
                    "extra": extra
                }, true);
        };

        // Disable DHCP on the VLAN
        VLANsManager.prototype.disableDHCP = function(vlan) {
            return RegionConnection.callMethod(
                "vlan.configure_dhcp", {
                    "id": vlan.id,
                    "controllers": []
                }, true);
        };

        // Create a VLAN.
        VLANsManager.prototype.create = function(vlan) {
            // We don't add the item to the list because a NOTIFY event will
            // add the domain to the list. Adding it here will cause angular to
            // complain because the same object exist in the list.
            return RegionConnection.callMethod("vlan.create", vlan);
        };

        return new VLANsManager();
    }]);
