/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Node Storage Controller
 */

angular.module('MAAS').controller('NodeStorageController', [
    '$scope', function($scope) {
        $scope.editing = false;
        $scope.column = 'model';
        $scope.disks = [];

        // Give $parent which is the NodeDetailsController access to this scope
        // it will call `nodeLoaded` once the node has been fully loaded.
        $scope.$parent.storageController = $scope;

        // Updates the disks list.
        function updateDisks() {
            // Do not update the items, when editing this would
            // cause the users changes to change.
            // Only update if node is available
            if($scope.editing || $scope.node === null) {
                return;
            }

            $scope.disks = angular.copy(
                $scope.node.disks);

            // Fix tags so they are stored correctly for the ngTagsInput.
            angular.forEach($scope.disks, function(disk) {
                var tags = [];
                angular.forEach(disk.tags, function(tag) {
                    tags.push({ text: tag });
                });
                disk.tags = tags;
            });
        }

        // Called by $parent when the node has been loaded.
        $scope.nodeLoaded = function() {
            $scope.$watch("node.disks", updateDisks);
        };

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
