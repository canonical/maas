/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Node Storage Controller
 */

angular.module('MAAS').controller('NodeStorageController', [
    '$scope', 'NodesManager', function($scope, NodesManager) {
        var MIN_PARTITION_SIZE = 2 * 1024 * 1024;

        $scope.editing = false;
        $scope.editing_tags = false;
        $scope.column = 'model';
        $scope.has_disks = false;
        $scope.filesystems = [];
        $scope.available = [];
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
                // If its a filesystem that is a usable formatted filesystem
                // without a mount point then it is available.
                if(item.filesystem.is_format_fstype &&
                    (item.filesystem.mount_point === null ||
                    (angular.isString(item.filesystem.mount_point) &&
                    item.filesystem.mount_point === ""))) {
                    return false;
                }
                return true;
            }else if(item.type === "partition") {
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

        // Return list of filesystems. Only filesystems with a mount point set
        // go here. If no mount point is set, it goes in available.
        function getFilesystems() {
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
            return filesystems;
        }

        // Return list of all available disks.
        function getAvailable() {
            var available = [];
            angular.forEach($scope.node.disks, function(disk) {
                if(!isInUse(disk)) {
                    available.push({
                        "name": disk.name,
                        "size_human": disk.available_size_human,
                        "type": disk.type,
                        "model": disk.model,
                        "serial": disk.serial,
                        "tags": getTags(disk),
                        "fstype": hasFormattedUnmountedFilesystem(disk),
                        "mount_point": null,
                        "block_id": disk.id,
                        "partition_id": null,
                        "editing_fs": false
                    });
                }
                angular.forEach(disk.partitions, function(partition) {
                    if(!isInUse(partition)) {
                        available.push({
                            "name": partition.name,
                            "size_human": disk.size_human,
                            "type": "partition",
                            "model": "",
                            "serial": "",
                            "tags": [],
                            "fstype":
                                hasFormattedUnmountedFilesystem(partition),
                            "mount_point": null,
                            "block_id": disk.id,
                            "partition_id": partition.id,
                            "editing_fs": false
                        });
                    }
                });
            });
            return available;
        }

        // Return list of all used disks.
        function getUsed() {
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
            return used;
        }

        // Updates the filesystem, available, and used list.
        function updateDisks() {
            // Do not update the items, when editing this would
            // cause the users changes to change.
            if($scope.editing) {
                return;
            }
            $scope.has_disks = $scope.node.disks.length > 0;
            $scope.filesystems = getFilesystems();
            $scope.available = getAvailable();
            $scope.used = getUsed();
        }

        // Called by $parent when the node has been loaded.
        $scope.nodeLoaded = function() {
            $scope.$watch("node.disks", updateDisks);
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
                    $scope.node.system_id, disk.block_id, tags);
            });
        };

        $scope.editFilesystem = function(item) {
            if($scope.$parent.canEdit() && !$scope.editing) {
                $scope.editing = true;
                item.editing_fs = true;
            }
        };

        $scope.cancelFilesystem = function(item) {
            $scope.editing = false;
            item.editing_fs = false;
        };

        $scope.unmountFilesystem = function(block_id, partition_id, fstype) {
            NodesManager.updateFilesystem(
                $scope.node.system_id, block_id, partition_id, fstype, null);
        };

        $scope.updateFilesystem = function(block_id, partition_id, item) {
            $scope.editing = false;
            item.editing_fs = false;
            NodesManager.updateFilesystem(
                $scope.node.system_id, block_id, partition_id,
                item.fstype, item.mount_point);
        };
    }]);
