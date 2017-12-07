/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Machines Manager
 *
 * Manages all of the machines in the browser. This manager is used for the
 * machine listing and view pages. The manager is a subclass of NodesManager.
 */

angular.module('MAAS').factory(
    'MachinesManager',
    ['$q', '$rootScope', 'RegionConnection', 'NodesManager', function(
            $q, $rootScope, RegionConnection, NodesManager) {

        function MachinesManager() {
            NodesManager.call(this);

            this._pk = "system_id";
            this._handler = "machine";

            this._metadataAttributes = {
                "architecture": null,
                "status": null,
                "owner": null,
                "tags": null,
                "pod": function(machine) {
                    return (machine.pod === undefined) ? '' :machine.pod.name;
                },
                "zone": function(machine) {
                    return machine.zone.name;
                },
                "subnets": null,
                "fabrics": null,
                "spaces": null,
                "storage_tags": null,
                "release": function(machine) {
                    if(machine.status_code === 6 || machine.status_code === 9) {
                        return machine.osystem + "/" + machine.distro_series;
                    } else {
                        return '';
                    }
                }
            };

            // Listen for notify events for the machine object.
            var self = this;
            RegionConnection.registerNotifier("machine",
                function(action, data) {
                    self.onNotify(action, data);
                });

        }
        MachinesManager.prototype = new NodesManager();

        MachinesManager.prototype.mountSpecialFilesystem =
            function(machine, fstype, mount_point, mount_options) {
                var method = this._handler + ".mount_special";
                var params = {
                    system_id: machine.system_id,
                    fstype: fstype,
                    mount_point: mount_point,
                    mount_options: mount_options
                };
                return RegionConnection.callMethod(method, params);
            };

        MachinesManager.prototype.unmountSpecialFilesystem =
            function(machine, mount_point) {
                var method = this._handler + ".unmount_special";
                var params = {
                    system_id: machine.system_id,
                    mount_point: mount_point
                };
                return RegionConnection.callMethod(method, params);
            };

        return new MachinesManager();
    }]);
