/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Node Storage Controller
 */


// Filter that is specific to the NodeStorageController. Remove the available
// disks from the list if being used in the availableNew.
angular.module('MAAS').filter('removeAvailableByNew', function() {
    return function(disks, availableNew) {
        if(!angular.isObject(availableNew) || (
            !angular.isObject(availableNew.device) &&
            !angular.isArray(availableNew.devices))) {
            return disks;
        }

        var filtered = [];
        var single = true;
        if(angular.isArray(availableNew.devices)) {
            single = false;
        }
        angular.forEach(disks, function(disk) {
            if(single) {
                if(disk !== availableNew.device) {
                    filtered.push(disk);
                }
            } else {
                var i, found = false;
                for(i = 0; i < availableNew.devices.length; i++) {
                    if(disk === availableNew.devices[i]) {
                        found = true;
                        break;
                    }
                }
                if(!found) {
                    filtered.push(disk);
                }
            }
        });
        return filtered;
    };
});

angular.module('MAAS').controller('NodeStorageController', [
    '$scope', 'NodesManager', 'ConverterService',
    function($scope, NodesManager, ConverterService) {
        var MIN_PARTITION_SIZE = 2 * 1024 * 1024;
        var PARTITION_TABLE_EXTRA_SPACE = 3 * 1024 * 1024;

        // Different selection modes.
        var SELECTION_MODE = {
            NONE: null,
            SINGLE: "single",
            MUTLI: "multi",
            UNMOUNT: "unmount",
            UNFORMAT: "unformat",
            DELETE: "delete",
            FORMAT_AND_MOUNT: "format-mount",
            PARTITION: "partition",
            BCACHE: "bcache"
        };

        $scope.editing = false;
        $scope.editing_tags = false;
        $scope.column = 'model';
        $scope.has_disks = false;
        $scope.filesystems = [];
        $scope.filesystemsMap = {};
        $scope.filesystemMode = SELECTION_MODE.NONE;
        $scope.filesystemAllSelected = false;
        $scope.cachesets = [];
        $scope.cachesetsMap = {};
        $scope.cachesetsMode = SELECTION_MODE.NONE;
        $scope.cachesetsAllSelected = false;
        $scope.available = [];
        $scope.availableMap = {};
        $scope.availableMode = SELECTION_MODE.NONE;
        $scope.availableAllSelected = false;
        $scope.availableNew = {};
        $scope.used = [];

        // Give $parent which is the NodeDetailsController access to this scope
        // it will call `nodeLoaded` once the node has been fully loaded.
        $scope.$parent.storageController = $scope;

        // Return True if the item has a filesystem and its mounted.
        function hasMountedFilesystem(item) {
            return angular.isObject(item.filesystem) &&
                angular.isString(item.filesystem.mount_point) &&
                item.filesystem.mount_point !== "";
        }

        // Returns the fstype if the item has a filesystem and its unmounted.
        function hasFormattedUnmountedFilesystem(item) {
            if(angular.isObject(item.filesystem) &&
                angular.isString(item.filesystem.fstype) &&
                item.filesystem.fstype !== '' &&
                (angular.isString(item.filesystem.mount_point) === false ||
                    item.filesystem.mount_point === '')) {
                return item.filesystem.fstype;
            }else{
                return null;
            }
        }

        // Return True if the item is in use.
        function isInUse(item) {
            if(item.type === "cache-set") {
                return true;
            } else if(angular.isObject(item.filesystem)) {
                if(item.filesystem.is_format_fstype &&
                    angular.isString(item.filesystem.mount_point) &&
                    item.filesystem.mount_point !== "") {
                    return true;
                } else if(!item.filesystem.is_format_fstype) {
                    return true;
                }
                return false;
            }
            return item.available_size < MIN_PARTITION_SIZE;
        }

        // Return the tags formatted for ngTagInput.
        function getTags(disk) {
            var tags = [];
            angular.forEach(disk.tags, function(tag) {
                tags.push({ text: tag });
            });
            return tags;
        }

        // Return a unique key that will never change.
        function getUniqueKey(disk) {
            if(disk.type === "cache-set") {
                return "cache-set-" + disk.cache_set_id;
            } else {
                var key = disk.type + "-" + disk.block_id;
                if(angular.isNumber(disk.partition_id)) {
                    key += "-" + disk.partition_id;
                }
                return key;
            }
        }

        // Update the list of filesystems. Only filesystems with a mount point
        // set go here. If no mount point is set, it goes in available.
        function updateFilesystems() {
            // Create the new list of filesystems.
            var filesystems = [];
            angular.forEach($scope.node.disks, function(disk) {
                if(hasMountedFilesystem(disk)) {
                    filesystems.push({
                        "type": "filesystem",
                        "name": disk.name,
                        "size_human": disk.size_human,
                        "fstype": disk.filesystem.fstype,
                        "mount_point": disk.filesystem.mount_point,
                        "block_id": disk.id,
                        "partition_id": null
                    });
                }
                angular.forEach(disk.partitions, function(partition) {
                    if(hasMountedFilesystem(partition)) {
                        filesystems.push({
                            "type": "filesystem",
                            "name": partition.name,
                            "size_human": partition.size_human,
                            "fstype": partition.filesystem.fstype,
                            "mount_point": partition.filesystem.mount_point,
                            "block_id": disk.id,
                            "partition_id": partition.id
                        });
                    }
                });
            });

            // Update the selected filesystems with the currently selected
            // filesystems.
            angular.forEach(filesystems, function(filesystem) {
                var key = getUniqueKey(filesystem);
                var oldFilesystem = $scope.filesystemsMap[key];
                if(angular.isObject(oldFilesystem)) {
                    filesystem.$selected = oldFilesystem.$selected;
                } else {
                    filesystem.$selected = false;
                }
            });

            // Update the filesystems and filesystemsMap on the scope.
            $scope.filesystems = filesystems;
            $scope.filesystemsMap = {};
            angular.forEach(filesystems, function(filesystem) {
                $scope.filesystemsMap[getUniqueKey(filesystem)] = filesystem;
            });

            // Update the selection mode.
            $scope.updateFilesystemSelection(false);
        }

        // Update the list of cache sets.
        function updateCacheSets() {
            // Create the new list of cache sets.
            var cachesets = [];
            angular.forEach($scope.node.disks, function(disk) {
                if(disk.type === "cache-set") {
                    cachesets.push({
                        "type": "cache-set",
                        "name": disk.name,
                        "size_human": disk.size_human,
                        "cache_set_id": disk.id,
                        "used_by": disk.used_for
                    });
                }
            });

            // Update the selected cache sets with the currently selected
            // cache sets.
            angular.forEach(cachesets, function(cacheset) {
                var key = getUniqueKey(cacheset);
                var oldCacheSet = $scope.cachesetsMap[key];
                if(angular.isObject(oldCacheSet)) {
                    cacheset.$selected = oldCacheSet.$selected;
                } else {
                    cacheset.$selected = false;
                }
            });

            // Update the cachesets and cachesetsMap on the scope.
            $scope.cachesets = cachesets;
            $scope.cachesetsMap = {};
            angular.forEach(cachesets, function(cacheset) {
                $scope.cachesetsMap[getUniqueKey(cacheset)] = cacheset;
            });

            // Update the selection mode.
            $scope.updateCacheSetsSelection(false);
        }

        // Update list of all available disks.
        function updateAvailable() {
            var available = [];
            angular.forEach($scope.node.disks, function(disk) {
                if(!isInUse(disk)) {
                    var has_partitions = false;
                    if(angular.isArray(disk.partitions) &&
                        disk.partitions.length > 0) {
                        has_partitions = true;
                    }
                    var data = {
                        "name": disk.name,
                        "size_human": disk.available_size_human,
                        "used_size_human": disk.used_size_human,
                        "type": disk.type,
                        "model": disk.model,
                        "serial": disk.serial,
                        "tags": getTags(disk),
                        "fstype": hasFormattedUnmountedFilesystem(disk),
                        "mount_point": null,
                        "block_id": disk.id,
                        "partition_id": null,
                        "has_partitions": has_partitions,
                        "original": disk
                    };
                    if(disk.type === "virtual") {
                        data.parent_type = disk.parent.type;
                    }
                    available.push(data);
                }
                angular.forEach(disk.partitions, function(partition) {
                    if(!isInUse(partition)) {
                        available.push({
                            "name": partition.name,
                            "size_human": partition.size_human,
                            "used_size_human": partition.used_size_human,
                            "type": "partition",
                            "model": "",
                            "serial": "",
                            "tags": [],
                            "fstype":
                                hasFormattedUnmountedFilesystem(partition),
                            "mount_point": null,
                            "block_id": disk.id,
                            "partition_id": partition.id,
                            "has_partitions": false,
                            "original": partition
                        });
                    }
                });
            });

            // Update the selected available disks with the currently selected
            // available disks. Also copy the $options so they are not lost
            // for the current action.
            angular.forEach(available, function(disk) {
                var key = getUniqueKey(disk);
                var oldDisk = $scope.availableMap[key];
                if(angular.isObject(oldDisk)) {
                    disk.$selected = oldDisk.$selected;
                    disk.$options = oldDisk.$options;
                } else {
                    disk.$selected = false;
                    disk.$options = {};
                }
            });

            // Update available and availableMap on the scope.
            $scope.available = available;
            $scope.availableMap = {};
            angular.forEach(available, function(disk) {
                $scope.availableMap[getUniqueKey(disk)] = disk;
            });

            // Update device or devices on the availableNew object to be
            // there new objects.
            if(angular.isObject($scope.availableNew)) {
                // Update device.
                if(angular.isObject($scope.availableNew.device)) {
                    var key = getUniqueKey($scope.availableNew.device);
                    $scope.availableNew.device = $scope.availableMap[key];
                // Update devices.
                } else if(angular.isArray($scope.availableNew.devices)) {
                    var newDevices = [];
                    angular.forEach(
                        $scope.availableNew.devices, function(device) {
                            var key = getUniqueKey(device);
                            var newDevice = $scope.availableMap[key];
                            if(angular.isObject(newDevice)) {
                                newDevices.push(newDevice);
                            }
                        });
                    $scope.availableNew.devices = newDevices;
                }
            }

            // Update the selection mode.
            $scope.updateAvailableSelection(false);
        }

        // Update list of all used disks.
        function updateUsed() {
            var used = [];
            angular.forEach($scope.node.disks, function(disk) {
                if(isInUse(disk) && disk.type !== "cache-set") {
                    var data = {
                        "name": disk.name,
                        "type": disk.type,
                        "model": disk.model,
                        "serial": disk.serial,
                        "tags": getTags(disk),
                        "used_for": disk.used_for
                    };
                    if(disk.type === "virtual") {
                        data.parent_type = disk.parent.type;
                    }
                    used.push(data);
                }
                angular.forEach(disk.partitions, function(partition) {
                    if(isInUse(partition) && partition.type !== "cache-set") {
                        used.push({
                            "name": partition.name,
                            "type": "partition",
                            "model": "",
                            "serial": "",
                            "tags": [],
                            "used_for": partition.used_for
                        });
                    }
                });
            });
            $scope.used = used;
        }

        // Updates the filesystem, available, and used list.
        function updateDisks() {
            if(angular.isArray($scope.node.disks)) {
                $scope.has_disks = $scope.node.disks.length > 0;
                updateFilesystems();
                updateCacheSets();
                updateAvailable();
                updateUsed();
            } else {
                $scope.has_disks = false;
                $scope.filesystems = [];
                $scope.filesystemsMap = {};
                $scope.filesystemMode = SELECTION_MODE.NONE;
                $scope.filesystemAllSelected = false;
                $scope.cachesets = [];
                $scope.cachesetsMap = {};
                $scope.cachesetsMode = SELECTION_MODE.NONE;
                $scope.cachesetsAllSelected = false;
                $scope.available = [];
                $scope.availableMap = {};
                $scope.availableMode = SELECTION_MODE.NONE;
                $scope.availableAllSelected = false;
                $scope.availableNew = {};
                $scope.used = [];
            }
        }

        // Deselect all items in the array.
        function deselectAll(items) {
            angular.forEach(items, function(item) {
                item.$selected = false;
            });
        }

        // Capitalize the first letter of the string.
        function capitalizeFirstLetter(string) {
            return string.charAt(0).toUpperCase() + string.slice(1);
        }

        // Return true if the string is a number.
        function isNumber(string) {
            var pattern = /^-?\d+\.?\d*$/;
            return pattern.test(string);
        }

        // Extract the index from the bcache name.
        function getBcacheIndexFromName(name) {
            var pattern = /^bcache([0-9]+)$/;
            var match = pattern.exec(name);
            if(angular.isArray(match) && match.length === 2) {
                return parseInt(match[1], 10);
            }
        }

        // Get the next bcache device name.
        function getNextBcacheName() {
            var idx = -1;
            angular.forEach($scope.node.disks, function(disk) {
                var bcacheIdx = getBcacheIndexFromName(disk.name);
                if(angular.isNumber(bcacheIdx)) {
                    idx = Math.max(idx, bcacheIdx);
                }
                angular.forEach(disk.partitions, function(partition) {
                    bcacheIdx = getBcacheIndexFromName(partition.name);
                    if(angular.isNumber(bcacheIdx)) {
                        idx = Math.max(idx, bcacheIdx);
                    }
                });
            });
            return "bcache" + (idx + 1);
        }

        // Called by $parent when the node has been loaded.
        $scope.nodeLoaded = function() {
            $scope.$watch("node.disks", updateDisks);
        };

        // Return array of selected filesystems.
        $scope.getSelectedFilesystems = function() {
            var filesystems = [];
            angular.forEach($scope.filesystems, function(filesystem) {
                if(filesystem.$selected) {
                    filesystems.push(filesystem);
                }
            });
            return filesystems;
        };

        // Update the currect mode for the filesystem section and the all
        // selected value.
        $scope.updateFilesystemSelection = function(force) {
            if(angular.isUndefined(force)) {
                force = false;
            }
            var filesystems = $scope.getSelectedFilesystems();
            if(filesystems.length === 0) {
                $scope.filesystemMode = SELECTION_MODE.NONE;
            } else if(filesystems.length === 1 && force) {
                $scope.filesystemMode = SELECTION_MODE.SINGLE;
            } else if(force) {
                $scope.filesystemMode = SELECTION_MODE.MUTLI;
            }

            if($scope.filesystems.length === 0) {
                $scope.filesystemAllSelected = false;
            } else if(filesystems.length === $scope.filesystems.length) {
                $scope.filesystemAllSelected = true;
            } else {
                $scope.filesystemAllSelected = false;
            }
        };

        // Toggle the selection of the filesystem.
        $scope.toggleFilesystemSelect = function(filesystem) {
            filesystem.$selected = !filesystem.$selected;
            $scope.updateFilesystemSelection(true);
        };

        // Toggle the selection of all filesystems.
        $scope.toggleFilesystemAllSelect = function() {
            angular.forEach($scope.filesystems, function(filesystem) {
                if($scope.filesystemAllSelected) {
                    filesystem.$selected = false;
                } else {
                    filesystem.$selected = true;
                }
            });
            $scope.updateFilesystemSelection(true);
        };

        // Return true if checkboxes in the filesystem section should be
        // disabled.
        $scope.isFilesystemsDisabled = function() {
            return (
                $scope.filesystemMode !== SELECTION_MODE.NONE &&
                $scope.filesystemMode !== SELECTION_MODE.SINGLE &&
                $scope.filesystemMode !== SELECTION_MODE.MUTLI);
        };

        // Cancel the current filesystem operation.
        $scope.filesystemCancel = function() {
            $scope.updateFilesystemSelection(true);
        };

        // Enter unmount mode.
        $scope.filesystemUnmount = function() {
            $scope.filesystemMode = SELECTION_MODE.UNMOUNT;
        };

        // Quickly enter unmount by selecting the filesystem first.
        $scope.quickFilesystemUnmount = function(filesystem) {
            deselectAll($scope.filesystems);
            filesystem.$selected = true;
            $scope.updateFilesystemSelection(true);
            $scope.filesystemUnmount();
        };

        // Confirm the unmount action for filesystem.
        $scope.filesystemConfirmUnmount = function(filesystem) {
            NodesManager.updateFilesystem(
                $scope.node,
                filesystem.block_id, filesystem.partition_id,
                filesystem.fstype, null);

            var idx = $scope.filesystems.indexOf(filesystem);
            $scope.filesystems.splice(idx, 1);
            $scope.updateFilesystemSelection();
        };

        // Return true if the disk has an unmouted filesystem.
        $scope.hasUnmountedFilesystem = function(disk) {
            if(angular.isString(disk.fstype) && disk.fstype !== "") {
                if(!angular.isString(disk.mount_point) ||
                    disk.mount_point === "") {
                    return true;
                }
            }
            return false;
        };

        // Return the size to show the user based on the disk.
        $scope.getSize = function(disk) {
            if($scope.hasUnmountedFilesystem(disk)) {
                return disk.used_size_human;
            } else {
                return disk.size_human;
            }
        };

        // Return the device type for the disk.
        $scope.getDeviceType = function(disk) {
            if(angular.isUndefined(disk)) {
                return "";
            }

            if(disk.type === "virtual") {
                if(disk.parent_type === "lvm-vg") {
                    return "Logical Volume";
                } else {
                    return capitalizeFirstLetter(disk.parent_type);
                }
            } else if(disk.type === "lvm-vg") {
                return "Volume Group";
            } else {
                return capitalizeFirstLetter(disk.type);
            }
        };

        // Return array of selected available disks.
        $scope.getSelectedAvailable = function() {
            var available = [];
            angular.forEach($scope.available, function(disk) {
                if(disk.$selected) {
                    available.push(disk);
                }
            });
            return available;
        };

        // Update the currect mode for the available section and the all
        // selected value.
        $scope.updateAvailableSelection = function(force) {
            if(angular.isUndefined(force)) {
                force = false;
            }
            var available = $scope.getSelectedAvailable();
            if(available.length === 0) {
                $scope.availableMode = SELECTION_MODE.NONE;
            } else if(available.length === 1 && force) {
                $scope.availableMode = SELECTION_MODE.SINGLE;
            } else if(force) {
                $scope.availableMode = SELECTION_MODE.MUTLI;
            }

            if($scope.available.length === 0) {
                $scope.availableAllSelected = false;
            } else if(available.length === $scope.available.length) {
                $scope.availableAllSelected = true;
            } else {
                $scope.availableAllSelected = false;
            }
        };

        // Toggle the selection of the available disk.
        $scope.toggleAvailableSelect = function(disk) {
            disk.$selected = !disk.$selected;
            $scope.updateAvailableSelection(true);
        };

        // Toggle the selection of all available disks.
        $scope.toggleAvailableAllSelect = function() {
            angular.forEach($scope.available, function(disk) {
                if(!$scope.availableAllSelected) {
                    disk.$selected = true;
                } else {
                    disk.$selected = false;
                }
            });
            $scope.updateAvailableSelection(true);
        };

        // Return true if checkboxes in the avaiable section should be
        // disabled.
        $scope.isAvailableDisabled = function() {
            return (
                $scope.availableMode !== SELECTION_MODE.NONE &&
                $scope.availableMode !== SELECTION_MODE.SINGLE &&
                $scope.availableMode !== SELECTION_MODE.MUTLI);
        };

        // Return true if the disk can be formatted and mounted.
        $scope.canFormatAndMount = function(disk) {
            if(disk.type === "lvm-vg" || disk.has_partitions) {
                return false;
            } else {
                return true;
            }
        };

        // Return the text for the format and mount button.
        $scope.getFormatAndMountButtonText = function(disk) {
            if($scope.hasUnmountedFilesystem(disk)) {
                return "Mount";
            } else {
                return "Format";
            }
        };

        // Return the text for the partition button.
        $scope.getPartitionButtonText = function(disk) {
            if(disk.has_partitions) {
                return "Add Partition";
            } else {
                return "Partition";
            }
        };

        // Return true if a partition can be added to disk.
        $scope.canAddPartition = function(disk) {
            if(disk.type === "partition" || disk.type === "lvm-vg") {
                return false;
            } else if(disk.type === "virtual" &&
                disk.parent_type === "lvm-vg") {
                return false;
            } else if(angular.isString(disk.fstype) && disk.fstype !== "") {
                return false;
            } else if(!angular.isString(disk.original.partition_table_type)
                || disk.original.partition_table_type === "") {
                // Has no partition table on the disk, so the available size
                // needs to be able to hold both the partition and partition
                // table extra space.
                if(disk.original.available_size <
                    ConverterService.roundByBlockSize(
                        PARTITION_TABLE_EXTRA_SPACE + MIN_PARTITION_SIZE,
                        disk.original.block_size)) {
                    return false;
                }
            } else {
                // Needs to have enough space for one partition. The extra
                // partition header space is already being taken into account.
                if(disk.original.available_size <
                    ConverterService.roundByBlockSize(
                        MIN_PARTITION_SIZE,
                        disk.original.block_size)) {
                    return false;
                }
            }
            return true;
        };

        // Cancel the current available operation.
        $scope.availableCancel = function() {
            $scope.updateAvailableSelection(true);
            $scope.availableNew = {};
        };

        // Enter unformat mode.
        $scope.availableUnformat = function(disk) {
            $scope.availableMode = SELECTION_MODE.UNFORMAT;
        };

        // Confirm the unformat action.
        $scope.availableConfirmUnformat = function(disk) {
            NodesManager.updateFilesystem(
                $scope.node,
                disk.block_id, disk.partition_id,
                null, null);

            // Clear the fstype and update the size_human to match
            // used_size_human so that the UI does not flicher why the new
            // object is received.
            disk.fstype = null;
            disk.size_human = disk.used_size_human;
            $scope.updateAvailableSelection(true);
        };

        // Enter format and mount mode.
        $scope.availableFormatAndMount = function(disk) {
            disk.$options = {
                fstype: disk.fstype || "ext4",
                mount_point: disk.mount_point || ""
            };
            $scope.availableMode = SELECTION_MODE.FORMAT_AND_MOUNT;
        };

        // Quickly enter the format and mount mode.
        $scope.availableQuickFormatAndMount = function(disk) {
            deselectAll($scope.available);
            disk.$selected = true;
            $scope.updateAvailableSelection(true);
            $scope.availableFormatAndMount(disk);
        };

        // Return the text for the submit button in the format and mount mode.
        $scope.getAvailableFormatSubmitText = function(disk) {
            if(angular.isString(disk.$options.mount_point) &&
                disk.$options.mount_point !== "") {
                return "Format & Mount";
            } else {
                return "Format";
            }
        };

        // Confirm the format and mount action.
        $scope.availableConfirmFormatAndMount = function(disk) {
            // Do nothing if its invalid.
            if($scope.isMountPointInvalid(disk.$options.mount_point)) {
                return;
            }

            // Update the filesystem.
            NodesManager.updateFilesystem(
                $scope.node,
                disk.block_id, disk.partition_id,
                disk.$options.fstype, disk.$options.mount_point);

            // Set the options on the object so no flicker occurs while waiting
            // for the new object to be received.
            disk.fstype = disk.$options.fstype;
            disk.mount_point = disk.$options.mount_point;
            disk.size_human = disk.used_size_human;
            $scope.updateAvailableSelection(true);

            // If the mount_point is set the we need to transition this to
            // the filesystem section.
            if(angular.isString(disk.mount_point) && disk.mount_point !== "") {
                $scope.filesystems.push({
                    "name": disk.name,
                    "size_human": disk.size_human,
                    "fstype": disk.fstype,
                    "mount_point": disk.mount_point,
                    "block_id": disk.block_id,
                    "partition_id": disk.partition_id
                });

                // Remove the selected disk from available.
                var idx = $scope.available.indexOf(disk);
                $scope.available.splice(idx, 1);
                $scope.updateAvailableSelection(true);
            }
        };

        // Return true if the mount point is invalid.
        $scope.isMountPointInvalid = function(mount_point) {
            if(angular.isUndefined(mount_point) || mount_point === "") {
                return false;
            } else if(mount_point[0] !== "/") {
                return true;
            } else {
                return false;
            }
        };

        // Return true if the disk can be deleted.
        $scope.canDelete = function(disk) {
            if(!disk.has_partitions && (
                !angular.isString(disk.fstype) || disk.fstype === "")) {
                return true;
            } else {
                return false;
            }
        };

        // Enter delete mode.
        $scope.availableDelete = function() {
            $scope.availableMode = SELECTION_MODE.DELETE;
        };

        // Quickly enter delete mode. If the disk has a filesystem it will
        // enter unformat mode.
        $scope.availableQuickDelete = function(disk) {
            deselectAll($scope.available);
            disk.$selected = true;
            $scope.updateAvailableSelection(true);
            if($scope.hasUnmountedFilesystem(disk)) {
                $scope.availableUnformat(disk);
            } else {
                $scope.availableDelete();
            }
        };

        // Return the text for remove confirmation message.
        $scope.getRemoveTypeText = function(disk) {
            if(disk.type === "physical") {
                return "physical disk";
            } else if(disk.type === "partition") {
                return "partition";
            } else if(disk.type === "lvm-vg") {
                return "volume group";
            } else if(disk.type === "virtual") {
                if(disk.parent_type === "lvm-vg") {
                    return "logical volume";
                } else {
                    return disk.parent_type + " disk";
                }
            }
        };

        // Delete the disk, partition, or volume group.
        $scope.availableConfirmDelete = function(disk) {
            if(disk.type === "lvm-vg") {
                // Delete the volume group.
                NodesManager.deleteVolumeGroup(
                    $scope.node, disk.block_id);
            } else if(disk.type === "partition") {
                // Delete the partition.
                NodesManager.deletePartition(
                    $scope.node, disk.partition_id);
            } else {
                // Delete the disk.
                NodesManager.deleteDisk(
                    $scope.node, disk.block_id);
            }

            // Remove the selected disk from available.
            var idx = $scope.available.indexOf(disk);
            $scope.available.splice(idx, 1);
            $scope.updateAvailableSelection(true);
        };

        // Enter partition mode.
        $scope.availablePartiton = function(disk) {
            $scope.availableMode = SELECTION_MODE.PARTITION;
            // Set starting size to the maximum available space.
            var size_and_units = disk.size_human.split(" ");
            disk.$options = {
                size: size_and_units[0],
                sizeUnits: size_and_units[1]
            };
        };

        // Quickly enter partition mode.
        $scope.availableQuickPartition = function(disk) {
            deselectAll($scope.available);
            disk.$selected = true;
            $scope.updateAvailableSelection(true);
            $scope.availablePartiton(disk);
        };

        // Get the new name of the partition.
        $scope.getAddPartitionName = function(disk) {
            var length, partitions = disk.original.partitions;
            if(angular.isArray(partitions)) {
                length = partitions.length;
            } else {
                length = 0;
            }
            if(disk.original.partition_table_type === "mbr" &&
                length > 2) {
                return disk.name + "-part" + (length + 2);
            } else {
                return disk.name + "-part" + (length + 1);
            }
        };

        // Return true if the size is invalid.
        $scope.isAddPartitionSizeInvalid = function(disk) {
            if(disk.$options.size === "" || !isNumber(disk.$options.size)) {
                return true;
            } else {
                var bytes = ConverterService.unitsToBytes(
                    disk.$options.size, disk.$options.sizeUnits);
                if(bytes < MIN_PARTITION_SIZE) {
                    return true;
                } else if(bytes > disk.original.available_size) {
                    // Round the size down to the lowest tolerance for that
                    // to see if it now fits.
                    var rounded = ConverterService.roundUnits(
                        disk.$options.size, disk.$options.sizeUnits);
                    if(rounded > disk.original.available_size) {
                        return true;
                    } else {
                        return false;
                    }
                } else {
                    return false;
                }
            }
        };

        // Confirm the partition creation.
        $scope.availableConfirmPartition = function(disk) {
            // Do nothing if not valid.
            if($scope.isAddPartitionSizeInvalid(disk)) {
                return;
            }

            // Get the bytes to create the partition. Round down to the
            // total available on the disk.
            var removeDisk = false;
            var bytes = ConverterService.unitsToBytes(
                disk.$options.size, disk.$options.sizeUnits);
            if(bytes > disk.original.available_size) {
                bytes = disk.original.available_size;

                // Remove the disk as its going to use all the remaining space.
                removeDisk = true;
            }

            // If the disk does not have any partition table yet the extra
            // partition table space needs to be removed from the size if the
            // remaining space is less than the required extra.
            if(!angular.isString(disk.original.partition_table_type) ||
                disk.original.partition_table_type === "") {
                var diff = disk.original.available_size - bytes;
                diff -= ConverterService.roundByBlockSize(
                    PARTITION_TABLE_EXTRA_SPACE, disk.original.block_size);
                if(diff < 0) {
                    // Add because diff is a negative number.
                    bytes += diff;
                }
            }

            // Create the partition.
            NodesManager.createPartition($scope.node, disk.block_id, bytes);

            // Remove the disk if needed.
            if(removeDisk) {
                var idx = $scope.available.indexOf(disk);
                $scope.available.splice(idx, 1);
            }
            $scope.updateAvailableSelection(true);
        };

        // Return array of selected cache sets.
        $scope.getSelectedCacheSets = function() {
            var cachesets = [];
            angular.forEach($scope.cachesets, function(cacheset) {
                if(cacheset.$selected) {
                    cachesets.push(cacheset);
                }
            });
            return cachesets;
        };

        // Update the currect mode for the cache sets section and the all
        // selected value.
        $scope.updateCacheSetsSelection = function(force) {
            if(angular.isUndefined(force)) {
                force = false;
            }
            var cachesets = $scope.getSelectedCacheSets();
            if(cachesets.length === 0) {
                $scope.cachesetsMode = SELECTION_MODE.NONE;
            } else if(cachesets.length === 1 && force) {
                $scope.cachesetsMode = SELECTION_MODE.SINGLE;
            } else if(force) {
                $scope.cachesetsMode = SELECTION_MODE.MUTLI;
            }

            if($scope.cachesets.length === 0) {
                $scope.cachesetsAllSelected = false;
            } else if(cachesets.length === $scope.cachesets.length) {
                $scope.cachesetsAllSelected = true;
            } else {
                $scope.cachesetsAllSelected = false;
            }
        };

        // Toggle the selection of the filesystem.
        $scope.toggleCacheSetSelect = function(cacheset) {
            cacheset.$selected = !cacheset.$selected;
            $scope.updateCacheSetsSelection(true);
        };

        // Toggle the selection of all filesystems.
        $scope.toggleCacheSetAllSelect = function() {
            angular.forEach($scope.cachesets, function(cacheset) {
                if($scope.cachesetsAllSelected) {
                    cacheset.$selected = false;
                } else {
                    cacheset.$selected = true;
                }
            });
            $scope.updateCacheSetsSelection(true);
        };

        // Return true if checkboxes in the cache sets section should be
        // disabled.
        $scope.isCacheSetsDisabled = function() {
            return (
                $scope.cachesetsMode !== SELECTION_MODE.NONE &&
                $scope.cachesetsMode !== SELECTION_MODE.SINGLE &&
                $scope.cachesetsMode !== SELECTION_MODE.MUTLI);
        };

        // Cancel the current cache set operation.
        $scope.cacheSetCancel = function() {
            $scope.updateCacheSetsSelection(true);
        };

        // Can delete the cache set.
        $scope.canDeleteCacheSet = function(cacheset) {
            return cacheset.used_by === "";
        };

        // Enter delete mode.
        $scope.cacheSetDelete = function() {
            $scope.cachesetsMode = SELECTION_MODE.DELETE;
        };

        // Quickly enter delete by selecting the cache set first.
        $scope.quickCacheSetDelete = function(cacheset) {
            deselectAll($scope.cachesets);
            cacheset.$selected = true;
            $scope.updateCacheSetsSelection(true);
            $scope.cacheSetDelete();
        };

        // Confirm the delete action for cache set.
        $scope.cacheSetConfirmDelete = function(cacheset) {
            NodesManager.deleteCacheSet(
                $scope.node, cacheset.cache_set_id);

            var idx = $scope.cachesets.indexOf(cacheset);
            $scope.cachesets.splice(idx, 1);
            $scope.updateCacheSetsSelection();
        };

        // Return true if a cache set can be created.
        $scope.canCreateCacheSet = function() {
            if($scope.isAvailableDisabled()) {
                return false;
            }

            var selected = $scope.getSelectedAvailable();
            if(selected.length === 1) {
                return !$scope.hasUnmountedFilesystem(selected[0]);
            }
            return false;
        };

        // Called to create a cache set.
        $scope.createCacheSet = function() {
            if(!$scope.canCreateCacheSet()) {
                return;
            }

            // Create cache set.
            var disk = $scope.getSelectedAvailable()[0];
            NodesManager.createCacheSet(
                $scope.node, disk.block_id, disk.partition_id);

            // Remove from available.
            var idx = $scope.available.indexOf(disk);
            $scope.available.splice(idx, 1);
        };

        // Return true if a bcache can be created.
        $scope.canCreateBcache = function() {
            if($scope.isAvailableDisabled()) {
                return false;
            }

            var selected = $scope.getSelectedAvailable();
            if(selected.length === 1) {
                var allowed = !$scope.hasUnmountedFilesystem(selected[0]);
                return allowed && $scope.cachesets.length > 0;
            }
            return false;
        };

        // Enter bcache mode.
        $scope.createBcache = function() {
            if(!$scope.canCreateBcache()) {
                return;
            }
            $scope.availableMode = SELECTION_MODE.BCACHE;
            $scope.availableNew = {
                name: getNextBcacheName(),
                device: $scope.getSelectedAvailable()[0],
                cacheset: $scope.cachesets[0],
                cacheMode: "writeback",
                fstype: null,
                mountPoint: ""
            };
        };

        // Return true when the name of the new disk is invalid.
        $scope.isNewDiskNameInvalid = function() {
            if(!angular.isObject($scope.node) ||
                !angular.isArray($scope.node.disks)) {
                return true;
            }

            if($scope.availableNew.name === "") {
                return true;
            } else {
                var i, j;
                for(i = 0; i < $scope.node.disks.length; i++) {
                    var disk = $scope.node.disks[i];
                    if($scope.availableNew.name === disk.name) {
                        return true;
                    }
                    if(angular.isArray(disk.partitions)) {
                        for(j = 0; j < disk.partitions.length; j++) {
                            var partition = disk.partitions[j];
                            if($scope.availableNew.name === partition.name) {
                                return true;
                            }
                        }
                    }
                }
            }
            return false;
        };

        // Return true if bcache can be saved.
        $scope.createBcacheCanSave = function() {
            return (
                !$scope.isNewDiskNameInvalid() &&
                !$scope.isMountPointInvalid($scope.availableNew.mountPoint));
        };

        // Confirm and create the bcache device.
        $scope.availableConfirmCreateBcache = function() {
            if(!$scope.createBcacheCanSave()) {
                return;
            }

            // Create the bcache.
            var params = {
                name: $scope.availableNew.name,
                cache_set: $scope.availableNew.cacheset.cache_set_id,
                cache_mode: $scope.availableNew.cacheMode
            };
            if($scope.availableNew.device.type === "partition") {
                params.partition_id = $scope.availableNew.device.partition_id;
            } else {
                params.block_id = $scope.availableNew.device.block_id;
            }
            if(angular.isString($scope.availableNew.fstype) &&
                $scope.availableNew.fstype !== "") {
                params.fstype = $scope.availableNew.fstype;
                if($scope.availableNew.mountPoint !== "") {
                    params.mount_point = $scope.availableNew.mountPoint;
                }
            }
            NodesManager.createBcache($scope.node, params);

            // Remove device from available.
            var idx = $scope.available.indexOf($scope.availableNew.device);
            $scope.available.splice(idx, 1);
            $scope.availableNew = {};

            // Update the selection.
            $scope.updateAvailableSelection(true);
        };

        // Called to enter tag editing mode
        $scope.editTags = function() {
            if($scope.$parent.canEdit() && !$scope.editing) {
                $scope.editing = true;
                $scope.editing_tags = true;
            }
        };

        // Called to cancel editing.
        $scope.cancelTags = function() {
            $scope.editing = false;
            $scope.editing_tags = false;
            updateDisks();
        };

        // Called to save the changes.
        $scope.saveTags = function() {
            $scope.editing = false;
            $scope.editing_tags = false;

            angular.forEach($scope.available, function(disk) {
                var tags = [];
                angular.forEach(disk.tags, function(tag) {
                    tags.push(tag.text);
                });
                NodesManager.updateDiskTags(
                    $scope.node, disk.block_id, tags);
            });
        };
    }]);
