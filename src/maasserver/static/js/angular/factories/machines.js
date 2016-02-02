/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Machines Manager
 *
 * Manages all of the machines in the browser. This manager is used for the
 * machines listing and the machine view page. The manager uses the
 * RegionConnection to load the machines, update the machines, and listen for
 * notification events about machines.
 */

angular.module('MAAS').factory(
    'MachinesManager',
    ['$q', '$rootScope', 'RegionConnection', 'Manager', function(
            $q, $rootScope, RegionConnection, Manager) {

        function MachinesManager() {
            Manager.call(this);

            this._pk = "system_id";
            this._handler = "machine";
            this._metadataAttributes = {
                "status": null,
                "owner": null,
                "tags": null,
                "zone": function(machine) {
                    return machine.zone.name;
                },
                "subnets": null,
                "fabrics": null,
                "spaces": null,
                "storage_tags": null
            };

            // Listen for notify events for the machine object.
            var self = this;
            RegionConnection.registerNotifier("machine",
                function(action, data) {
                    self.onNotify(action, data);
                });
        }

        MachinesManager.prototype = new Manager();

        // Create a machine.
        MachinesManager.prototype.create = function(machine) {
            // We don't add the item to the list because a NOTIFY event will
            // add the machine to the list. Adding it here will cause angular
            // to complain because the same object exist in the list.
            return RegionConnection.callMethod("machine.create", machine);
        };

        // Perform the action on the machine.
        MachinesManager.prototype.performAction = function(
            machine, action, extra) {
            if(!angular.isObject(extra)) {
                extra = {};
            }
            return RegionConnection.callMethod("machine.action", {
                "system_id": machine.system_id,
                "action": action,
                "extra": extra
                });
        };

        // Check the power state for the machine.
        MachinesManager.prototype.checkPowerState = function(machine) {
            return RegionConnection.callMethod("machine.check_power", {
                "system_id": machine.system_id
                }).then(function(state) {
                    machine.power_state = state;
                    return state;
                }, function(error) {
                    machine.power_state = "error";

                    // Already been logged server side, but log it client
                    // side so if they really care they can see why.
                    console.log(error);

                    // Return the state as error to the remaining callbacks.
                    return "error";
                });
        };

        // Create the physical interface on the machine.
        MachinesManager.prototype.createPhysicalInterface = function(
            machine, params) {
                if(!angular.isObject(params)) {
                    params = {};
                }
                params.system_id = machine.system_id;
                return RegionConnection.callMethod(
                    "machine.create_physical", params);
            };

        // Create the VLAN interface on the machine.
        MachinesManager.prototype.createVLANInterface = function(
            machine, params) {
                if(!angular.isObject(params)) {
                    params = {};
                }
                params.system_id = machine.system_id;
                return RegionConnection.callMethod(
                    "machine.create_vlan", params);
            };

        // Create the bond interface on the machine.
        MachinesManager.prototype.createBondInterface = function(
            machine, params) {
                if(!angular.isObject(params)) {
                    params = {};
                }
                params.system_id = machine.system_id;
                return RegionConnection.callMethod(
                    "machine.create_bond", params);
            };

        // Update the interface for the machine.
        MachinesManager.prototype.updateInterface = function(
            machine, interface_id, params) {
                if(!angular.isObject(params)) {
                    params = {};
                }
                params.system_id = machine.system_id;
                params.interface_id = interface_id;
                return RegionConnection.callMethod(
                    "machine.update_interface", params);
            };

        // Delete the interface for the machine.
        MachinesManager.prototype.deleteInterface = function(
            machine, interface_id) {
                var params = {
                    system_id: machine.system_id,
                    interface_id: interface_id
                };
                return RegionConnection.callMethod(
                    "machine.delete_interface", params);
            };

        // Create or update the link to the subnet for the interface.
        MachinesManager.prototype.linkSubnet = function(
            machine, interface_id, params) {
                if(!angular.isObject(params)) {
                    params = {};
                }
                params.system_id = machine.system_id;
                params.interface_id = interface_id;
                return RegionConnection.callMethod(
                    "machine.link_subnet", params);
            };

        // Remove the link to the subnet for the interface.
        MachinesManager.prototype.unlinkSubnet = function(
            machine, interface_id, link_id) {
                var params = {
                    system_id: machine.system_id,
                    interface_id: interface_id,
                    link_id: link_id
                };
                return RegionConnection.callMethod(
                    "machine.unlink_subnet", params);
            };

        // Send the update information to the region.
        MachinesManager.prototype.updateFilesystem = function(
            machine, block_id, partition_id, fstype, mount_point) {
                var self = this;
                var method = this._handler + ".update_filesystem";
                var params = {
                    system_id: machine.system_id,
                    block_id: block_id,
                    partition_id: partition_id,
                    fstype: fstype,
                    mount_point: mount_point
                };
                return RegionConnection.callMethod(method, params);
            };

        // Update the tags on a disk.
        MachinesManager.prototype.updateDiskTags = function(
            machine, block_id, tags) {
                var self = this;
                var method = this._handler + ".update_disk_tags";
                var params = {
                    system_id: machine.system_id,
                    block_id: block_id,
                    tags: tags
                };
                return RegionConnection.callMethod(method, params);
            };

        // Delete the disk.
        MachinesManager.prototype.deleteDisk = function(
            machine, block_id) {
                var self = this;
                var method = this._handler + ".delete_disk";
                var params = {
                    system_id: machine.system_id,
                    block_id: block_id
                };
                return RegionConnection.callMethod(method, params);
            };

        // Delete the partition.
        MachinesManager.prototype.deletePartition = function(
            machine, partition_id) {
                var self = this;
                var method = this._handler + ".delete_partition";
                var params = {
                    system_id: machine.system_id,
                    partition_id: partition_id
                };
                return RegionConnection.callMethod(method, params);
            };

        // Delete the disk or partition.
        MachinesManager.prototype.deleteVolumeGroup = function(
            machine, volume_group_id) {
                var self = this;
                var method = this._handler + ".delete_volume_group";
                var params = {
                    system_id: machine.system_id,
                    volume_group_id: volume_group_id
                };
                return RegionConnection.callMethod(method, params);
            };

        // Delete a cache set.
        MachinesManager.prototype.deleteCacheSet = function(
            machine, cache_set_id) {
                var self = this;
                var method = this._handler + ".delete_cache_set";
                var params = {
                    system_id: machine.system_id,
                    cache_set_id: cache_set_id
                };
                return RegionConnection.callMethod(method, params);
            };

        // Create a new partition.
        MachinesManager.prototype.createPartition = function(
            machine, block_id, size, params) {
                if(!angular.isObject(params)) {
                    params = {};
                }
                var self = this;
                var method = this._handler + ".create_partition";
                params.system_id = machine.system_id;
                params.block_id = block_id;
                params.partition_size = size;
                return RegionConnection.callMethod(method, params);
            };

        // Create a new cache set.
        MachinesManager.prototype.createCacheSet = function(
            machine, block_id, partition_id) {
                var self = this;
                var method = this._handler + ".create_cache_set";
                var params = {
                    system_id: machine.system_id,
                    block_id: block_id,
                    partition_id: partition_id
                };
                return RegionConnection.callMethod(method, params);
            };

        // Create a new bcache device.
        MachinesManager.prototype.createBcache = function(
            machine, params) {
                if(!angular.isObject(params)) {
                    params = {};
                }
                params.system_id = machine.system_id;
                return RegionConnection.callMethod(
                    "machine.create_bcache", params);
            };

        // Create a new RAID device.
        MachinesManager.prototype.createRAID = function(
            machine, params) {
                if(!angular.isObject(params)) {
                    params = {};
                }
                params.system_id = machine.system_id;
                return RegionConnection.callMethod(
                    "machine.create_raid", params);
            };

        // Create a new volume group.
        MachinesManager.prototype.createVolumeGroup = function(
            machine, params) {
                if(!angular.isObject(params)) {
                    params = {};
                }
                params.system_id = machine.system_id;
                return RegionConnection.callMethod(
                    "machine.create_volume_group", params);
            };

        // Create a new logical volume.
        MachinesManager.prototype.createLogicalVolume = function(
            machine, volume_group_id, name, size, params) {
                if(!angular.isObject(params)) {
                    params = {};
                }
                var self = this;
                var method = this._handler + ".create_logical_volume";
                params.system_id = machine.system_id;
                params.volume_group_id = volume_group_id;
                params.name = name;
                params.size = size;
                return RegionConnection.callMethod(method, params);
            };

        // Update a disk.
        MachinesManager.prototype.updateDisk = function(
            machine, block_id, params) {
                if(!angular.isObject(params)) {
                    params = {};
                }
                params.system_id = machine.system_id;
                params.block_id = block_id;
                return RegionConnection.callMethod(
                    "machine.update_disk", params);
            };

        // Set disk as the boot disk.
        MachinesManager.prototype.setBootDisk = function(
            machine, block_id) {
                var params = {
                    system_id: machine.system_id,
                    block_id: block_id
                };
                return RegionConnection.callMethod(
                    "machine.set_boot_disk", params);
            };

        return new MachinesManager();
    }]);
