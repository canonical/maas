/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Node Storage Controller
 */

angular.module('MAAS').controller('NodeStorageController', [
    '$scope', function($scope) {
        var MIN_PARTITION_SIZE = 2 * 1024 * 1024;

        $scope.editing = false;
        $scope.column = 'model';
        $scope.has_disks = false;
        $scope.filesystems = [];
        $scope.available = [];
        $scope.used = [];

        // Give $parent which is the NodeDetailsController access to this scope
        // it will call `nodeLoaded` once the node has been fully loaded.
        $scope.$parent.storageController = $scope;

        // Return True if the item has a filesystem and it mounted.
        function hasMountedFilesystem(item) {
            return angular.isObject(item.filesystem) &&
                angular.isString(item.filesystem.mount_point) &&
                item.filesystem.mount_point !== "";
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
                        "mount_point": disk.filesystem.mount_point
                    });
                }
                angular.forEach(disk.partitions, function(partition) {
                    if(hasMountedFilesystem(partition)) {
                        filesystems.push({
                            "name": partition.name,
                            "size_human": partition.size_human,
                            "fstype": partition.filesystem.fstype,
                            "mount_point": partition.filesystem.mount_point
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
                        "tags": getTags(disk)
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
                            "tags": []
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
            // Only update if node is available
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

        // Called to return the list

        // Called to enter edit mode.
        $scope.edit = function() {
            if(!$scope.$parent.canEdit()) {
                return;
            }
            $scope.editing = true;
        };

        // Called to cancel editing.
        $scope.cancel = function() {
            $scope.editing = false;
            updateDisks();
        };

        // Called to save the changes.
        $scope.save = function() {
            $scope.editing = false;

            // Copy the node and make the changes.
            var node = angular.copy($scope.node);
            node.disks = $scope.disks;

            // Fix the tags as ngTagsInput stores the tags as an object with
            // a text field.
            angular.forEach(node.disks, function(disk) {
                var tags = [];
                angular.forEach(disk.tags, function(tag) {
                    tags.push(tag.text);
                });
                disk.tags = tags;
            });

            $scope.$parent.updateNode(node);
            updateDisks();
        };
    }]);
