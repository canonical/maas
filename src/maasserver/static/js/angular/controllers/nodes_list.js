/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Nodes List Controller
 */

angular.module('MAAS').controller('NodesListController', [
    '$scope', '$rootScope', 'NodesManager', 'DevicesManager',
    'RegionConnection', 'SearchService', function($scope,
        $rootScope, NodesManager, DevicesManager, RegionConnection,
        SearchService) {

        // Set title and page.
        $rootScope.title = "Nodes";
        $rootScope.page = "nodes";

        // Set initial values.
        $scope.search = "";
        $scope.searchValid = true;
        $scope.nodes = NodesManager.getItems();
        $scope.devices = DevicesManager.getItems();
        $scope.selectedNodes = NodesManager.getSelectedItems();
        $scope.filtered_nodes = [];
        $scope.predicate = 'fqdn';
        $scope.allViewableChecked = false;
        $scope.metadata = NodesManager.getMetadata();
        $scope.filters = SearchService.emptyFilter;
        $scope.column = 'fqdn';
        $scope.actionOption = null;
        $scope.takeActionOptions = [];
        $scope.actionError = false;

        // Options for add hardware dropdown.
        $scope.addHardwareOption = {
            name: "hardware",
            title: "Add Hardware"
        };
        $scope.addHardwareOptions = [
            $scope.addHardwareOption,
            {
                name: "chassis",
                title: "Add Chassis"
            }
        ];

        // This will hold the AddHardwareController once it is initialized.
        // The controller will set this variable as it's always a child or
        // this scope.
        $scope.addHardwareScope = null;

        // Called to update `allViewableChecked`.
        function updateAllViewableChecked() {
            // Not checked when the filtered nodes are empty.
            if($scope.filtered_nodes.length === 0) {
                $scope.allViewableChecked = false;
                return;
            }

            // Loop through all filtered nodes an see if all checked.
            var i;
            for(i = 0; i < $scope.filtered_nodes.length; i++) {
                if(!$scope.filtered_nodes[i].$selected) {
                    $scope.allViewableChecked = false;
                    return;
                }
            }
            $scope.allViewableChecked = true;
        }

        // Clear the action if required.
        function shouldClearAction() {
            if($scope.selectedNodes.length === 0) {
                if($scope.search === "in:selected") {
                    $scope.search = "";
                }
                $scope.actionOption = null;
            }
        }

        // Mark a node as selected or unselected.
        $scope.toggleChecked = function(node) {
            if(NodesManager.isSelected(node.system_id)) {
                NodesManager.unselectItem(node.system_id);
            } else {
                NodesManager.selectItem(node.system_id);
            }
            updateAllViewableChecked();
            shouldClearAction();
        };

        // Select all viewable nodes or deselect all viewable nodes.
        $scope.toggleCheckAll = function() {
            if($scope.allViewableChecked) {
                angular.forEach($scope.filtered_nodes, function(node) {
                    NodesManager.unselectItem(node.system_id);
                });
            } else {
                angular.forEach($scope.filtered_nodes, function(node) {
                    NodesManager.selectItem(node.system_id);
                });
            }
            updateAllViewableChecked();
            shouldClearAction();
        };

        // When the filtered nodes change update if the all check button
        // should be checked or not.
        $scope.$watchCollection("filtered_nodes", function() {
            updateAllViewableChecked();
        });

        // Adds or removes a filter the search.
        $scope.toggleFilter = function(type, value) {
            $scope.filters = SearchService.toggleFilter(
                $scope.filters, type, value);
            $scope.search = SearchService.filtersToString($scope.filters);
        };

        // Return True if the filter is active.
        $scope.isFilterActive = function(type, value) {
            return SearchService.isFilterActive($scope.filters, type, value);
        };

        // Update the filters object when the search bar is updated.
        $scope.updateFilters = function() {
            var filters = SearchService.getCurrentFilters($scope.search);
            if(filters === null) {
                $scope.filters = SearchService.emptyFilter;
                $scope.searchValid = false;
            } else {
                $scope.filters = filters;
                $scope.searchValid = true;
            }
        };

        // Return True if the node supports the action.
        $scope.supportsAction = function(node) {
            if(!$scope.actionOption) {
                return true;
            }
            return node.actions.indexOf($scope.actionOption.name) >= 0;
        };

        // Called when the action option gets changed.
        $scope.actionOptionSelected = function() {
            var i;
            $scope.actionError = false;
            for(i = 0; i < $scope.selectedNodes.length; i++) {
                if(!$scope.supportsAction($scope.selectedNodes[i])) {
                    $scope.actionError = true;
                    break;
                }
            }
            $scope.search = "in:selected";

            // Hide the add hardware section.
            if(angular.isObject($scope.addHardwareScope)) {
                $scope.addHardwareScope.hide();
            }
        };

        // Called when the current action is cancelled.
        $scope.actionCancel = function() {
            if($scope.search === "in:selected") {
                $scope.search = "";
            }
            $scope.actionOption = null;
        };

        // Perform the action on all nodes.
        $scope.actionGo = function() {
            angular.forEach($scope.selectedNodes, function(node) {
                NodesManager.performAction(
                    node, $scope.actionOption.name).then(function() {
                        NodesManager.unselectItem(node.system_id);
                        shouldClearAction();
                    }, function(error) {
                        // Report error loading. This is simple handlng for
                        // now but this should show a nice error dialog or
                        // something.
                        console.log(error);
                    });
            });
        };

        // Called to show the add hardware view.
        $scope.showAddHardware = function() {
            $scope.addHardwareScope.show($scope.addHardwareOption.name);
        };

        // Make sure connected to region then load all the nodes.
        RegionConnection.defaultConnect().then(function() {
            if(!NodesManager.isLoaded()) {
                // Load the initial nodes.
                NodesManager.loadItems().then(null, function(error) {
                    // Report error loading. This is simple handlng for now
                    // but this should show a nice error dialog or something.
                    console.log(error);
                });
            }
            NodesManager.enableAutoReload();

            if(!DevicesManager.isLoaded()) {
                // Load the initial nodes.
                DevicesManager.loadItems().then(null, function(error) {
                    // Report error loading. This is simple handlng for now
                    // but this should show a nice error dialog or something.
                    console.log(error);
                });
            }
            DevicesManager.enableAutoReload();

            // Load all of the available actions.
            RegionConnection.callMethod("general.actions", {}).then(
                function(actions) {
                    $scope.takeActionOptions = actions;
                });
        });
    }]);
