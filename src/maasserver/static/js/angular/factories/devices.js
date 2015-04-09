/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Devices Manager
 *
 * Manages all of the devices in the browser. This manager is used for the
 * device listing and the device view page. The manager uses the
 * RegionConnection to load the devices, update the devices, and listen for
 * notification events about devices.
 */

angular.module('MAAS').factory(
    'DevicesManager',
    ['$q', '$rootScope', 'RegionConnection', 'Manager', function(
            $q, $rootScope, RegionConnection, Manager) {

        function DevicesManager() {
            Manager.call(this);

            this._pk = "system_id";
            this._handler = "device";
            this._metadataAttributes = {
                "owner": null,
                "tags": null,
                "zone": function(device) {
                    return device.zone.name;
                }
            };

            // Listen for notify events for the device object.
            var self = this;
            RegionConnection.registerNotifier("device", function(action, data) {
                self.onNotify(action, data);
            });
        }

        DevicesManager.prototype = new Manager();

        // Create a device.
        DevicesManager.prototype.create = function(node) {
            // We don't add the item to the list because a NOTIFY event will
            // add the device to the list. Adding it here will cause angular to
            // complain because the same object exist in the list.
            return RegionConnection.callMethod("device.create", node);
        };

        // Perform the action on the device.
        DevicesManager.prototype.performAction = function(
            device, action, extra) {

            if(!angular.isObject(extra)) {
                extra = {};
            }
            return RegionConnection.callMethod("device.action", {
                "system_id": device.system_id,
                "action": action,
                "extra": extra
                });
        };

        return new DevicesManager();
    }]);
