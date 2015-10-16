/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Node Storage Controller
 */

angular.module('MAAS').controller('NodeStorageController', [
    '$scope', 'NodesManager', function($scope, NodesManager) {
        var MIN_PARTITION_SIZE = 2 * 1024 * 1024;

        // Different selection modes.
        var SELECTION_MODE = {
            NONE: null,
            SINGLE: "single",
            MUTLI: "multi",
            UNMOUNT: "unmount",
            UNFORMAT: "unformat",
            DELETE: "delete",
            FORMAT_AND_MOUNT: "format-mount"
        };

        $scope.editing = false;
        $scope.editing_tags = false;
        $scope.column = 'model';
        $scope.has_disks = false;
        $scope.filesystems = [];
        $scope.filesystemsMap = {};
        $scope.filesystemMode = SELECTION_MODE.NONE;
        $scope.filesystemAllSelected = false;
        $scope.available = [];
        $scope.availableMap = {};
        $scope.availableMode = SELECTION_MODE.NONE;
        $scope.availableAllSelected = false;
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
            if(angular.isObject(item.filesystem)) {
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

        // Update the list of filesystems. Only filesystems with a mount point
        // set go here. If no mount point is set, it goes in available.
        function updateFilesystems() {
            // Create the new list of filesystems.
            var filesystems = [];
            angular.forEach($scope.node.disks, function(disk) {
                if(hasMountedFilesystem(disk)) {
                    filesystems.push({
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
                var oldFilesystem = $scope.filesystemsMap[filesystem.name];
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
                $scope.filesystemsMap[filesystem.name] = filesystem;
            });

            // Update the selection mode.
            $scope.updateFilesystemSelection(false);
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
                        "has_partitions": has_partitions
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
                            "size_human": disk.size_human,
                            "used_size_human": disk.used_size_human,
                            "type": "partition",
                            "model": "",
                            "serial": "",
                            "tags": [],
                            "fstype":
                                hasFormattedUnmountedFilesystem(partition),
                            "mount_point": null,
                            "block_id": disk.id,
                            "partition_id": partition.id,
                            "has_partitions": false
                        });
                    }
                });
            });

            // Update the selected available disks with the currently selected
            // available disks. Also copy the $options so they are not lost
            // for the current action.
            angular.forEach(available, function(disk) {
                var oldDisk = $scope.availableMap[disk.name];
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
                $scope.availableMap[disk.name] = disk;
            });

            // Update the selection mode.
            $scope.updateAvailableSelection(false);
        }

        // Update list of all used disks.
        function updateUsed() {
            var used = [];
            angular.forEach($scope.node.disks, function(disk) {
                if(isInUse(disk)) {
                    used.push({
                        "name": disk.name,
                        "type": disk.type,
                        "model": disk.model,
                        "serial": disk.serial,
                        "tags": getTags(disk),
                        "used_for": disk.used_for
                    });
                }
                angular.forEach(disk.partitions, function(partition) {
                    if(isInUse(partition)) {
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
                updateAvailable();
                updateUsed();
            } else {
                $scope.has_disks = false;
                $scope.filesystems = [];
                $scope.filesystemsMap = {};
                $scope.filesystemMode = SELECTION_MODE.NONE;
                $scope.filesystemAllSelected = false;
                $scope.available = [];
                $scope.availableMap = {};
                $scope.availableMode = SELECTION_MODE.NONE;
                $scope.availableAllSelected = false;
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
            } else if(!angular.isString(disk.fstype) || disk.fstype !== "") {
                return false;
            }
            return true;
        };

        // Cancel the current available operation.
        $scope.availableCancel = function() {
            $scope.updateAvailableSelection(true);
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
            if(!angular.isString(disk.fstype) || disk.fstype === "") {
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
