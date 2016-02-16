/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Controller Details Controller
 */

angular.module('MAAS').controller('ControllerDetailsController', [
    '$scope', '$rootScope', '$routeParams', '$location',
    'ControllersManager', 'ZonesManager', 'GeneralManager',
    'UsersManager', 'TagsManager', 'ManagerHelperService', 'ErrorService',
    'ValidationService', function(
        $scope, $rootScope, $routeParams, $location,
        ControllersManager, ZonesManager, GeneralManager,
        UsersManager, TagsManager, ManagerHelperService, ErrorService,
        ValidationService) {

        // Set title and page.
        $rootScope.title = "Loading...";
        $rootScope.page = "nodes";

        // Initial values.
        $scope.loaded = false;
        $scope.node = null;

        // Controller name header section.
        $scope.nameHeader = {
            editing: false,
            value: ""
        };

        // Summary section.
        $scope.summary = {
            editing: false,
            zone: {
                selected: null,
                options: ZonesManager.getItems()
            },
            tags: []
        };

        // Updates the page title.
        function updateTitle() {
            if($scope.node && $scope.node.fqdn) {
                $rootScope.title = $scope.node.fqdn;
            }
        }

        function updateName() {
            // Don't update the value if in editing mode. As this would
            // overwrite the users changes.
            if($scope.nameHeader.editing) {
                return;
            }
            $scope.nameHeader.value = $scope.node.fqdn;
        }

        // Updates the currently selected items in the summary section.
        function updateSummary() {
            // Do not update the selected items, when editing this would
            // cause the users selection to change.
            if($scope.summary.editing) {
                return;
            }

            $scope.summary.zone.selected = ZonesManager.getItemFromList(
                $scope.node.zone.id);
            $scope.summary.tags = angular.copy($scope.node.tags);
        }

        // Starts the watchers on the scope.
        function startWatching() {
            // Update the title and name when the node fqdn changes.
            $scope.$watch("node.fqdn", function() {
                updateTitle();
                updateName();
            });

            // Update the summary when the node or zone list is
            // updated.
            $scope.$watch("node.zone.id", updateSummary);
            $scope.$watchCollection(
                $scope.summary.zone.options, updateSummary);
        }

        // Update the node with new data on the region.
        $scope.updateNode = function(node) {
            return ControllersManager.updateItem(node).then(function(node) {
                updateName();
                updateSummary();
            }, function(error) {
                console.log(error);
                updateName();
                updateSummary();
            });
        };

        // Called when the node has been loaded.
        function nodeLoaded(node) {
            $scope.node = node;
            $scope.loaded = true;

            updateTitle();
            updateSummary();
            startWatching();

            // Tell the networkingController that the node has been loaded.
            if(angular.isObject($scope.networkingController)) {
                $scope.networkingController.nodeLoaded();
            }
        }

        // Called for autocomplete when the user is typing a tag name.
        $scope.tagsAutocomplete = function(query) {
            return TagsManager.autocomplete(query);
        };

        // Return true if the authenticated user is super user.
        $scope.isSuperUser = function() {
            var authUser = UsersManager.getAuthUser();
            if(!angular.isObject(authUser)) {
                return false;
            }
            return authUser.is_superuser;
        };

        // Return true when the edit buttons can be clicked.
        $scope.canEdit = function() {
            return $scope.isSuperUser();
        };

        // Called to edit the node name.
        $scope.editName = function() {
            if(!$scope.canEdit()) {
                return;
            }

            // Do nothing if already editing because we don't want to reset
            // the current value.
            if($scope.nameHeader.editing) {
                return;
            }
            $scope.nameHeader.editing = true;

            // Set the value to the hostname, as that is what can be changed
            // not the fqdn.
            $scope.nameHeader.value = $scope.node.hostname;
        };

        // Return true when the value in nameHeader is invalid.
        $scope.editNameInvalid = function() {
            // Not invalid unless editing.
            if(!$scope.nameHeader.editing) {
                return false;
            }

            // The value cannot be blank.
            var value = $scope.nameHeader.value;
            if(value.length === 0) {
                return true;
            }
            return !ValidationService.validateHostname(value);
        };

        // Called to cancel editing of the node name.
        $scope.cancelEditName = function() {
            $scope.nameHeader.editing = false;
            updateName();
        };

        // Called to save editing of node name.
        $scope.saveEditName = function() {
            // Does nothing if invalid.
            if($scope.editNameInvalid()) {
                return;
            }
            $scope.nameHeader.editing = false;

            // Copy the node and make the changes.
            var node = angular.copy($scope.node);
            node.hostname = $scope.nameHeader.value;

            // Update the node.
            $scope.updateNode(node);
        };

        // Called to enter edit mode in the summary section.
        $scope.editSummary = function() {
            if(!$scope.canEdit()) {
                return;
            }
            $scope.summary.editing = true;
        };

        // Called to cancel editing in the summary section.
        $scope.cancelEditSummary = function() {
            updateSummary();
        };

        // Called to save the changes made in the summary section.
        $scope.saveEditSummary = function() {
            $scope.summary.editing = false;

            // Copy the node and make the changes.
            var node = angular.copy($scope.node);
            node.zone = angular.copy($scope.summary.zone.selected);
            node.tags = [];
            angular.forEach($scope.summary.tags, function(tag) {
                node.tags.push(tag.text);
            });

            // Update the node.
            $scope.updateNode(node);
        };

        // Load all the required managers.
        ManagerHelperService.loadManagers([
            ControllersManager,
            ZonesManager,
            GeneralManager,
            UsersManager,
            TagsManager
        ]).then(function() {
            // Possibly redirected from another controller that already had
            // this node set to active. Only call setActiveItem if not already
            // the activeItem.
            var activeNode = ControllersManager.getActiveItem();
            if(angular.isObject(activeNode) &&
                activeNode.system_id === $routeParams.system_id) {
                nodeLoaded(activeNode);
            } else {
                ControllersManager.setActiveItem(
                    $routeParams.system_id).then(function(node) {
                        nodeLoaded(node);
                    }, function(error) {
                        ErrorService.raiseError(error);
                    });
            }
        });
    }]);
