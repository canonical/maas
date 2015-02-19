/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Nodes List Controller
 */

angular.module('MAAS').controller('NodesListController', [
    '$scope', '$rootScope', 'NodesManager', 'RegionConnection',
    'SearchService', function($scope, $rootScope, NodesManager,
        RegionConnection, SearchService) {

        // Set title and page.
        $rootScope.title = "Nodes";
        $rootScope.page = "nodes";

        // Set initial values.
        $scope.search = "";
        $scope.searchValid = true;
        $scope.nodes = NodesManager.getItems();
        $scope.selectedNodes = NodesManager.getSelectedItems();
        $scope.filtered_nodes = [];
        $scope.predicate = 'fqdn';
        $scope.allViewableChecked = false;
        $scope.metadata = NodesManager.getMetadata();
        $scope.filters = SearchService.emptyFilter;
        $scope.column = 'fqdn';

        // Take action dropdown options.
        $scope.actionOption = null;
        $scope.takeActionOptions = [
            {
                title: "Commission"
            },
            {
                title: "Allocate"
            },
            {
                title: "Deploy"
            },
            {
                title: "Release"
            },
            {
                title: "Mark broken"
            },
            {
                title: "Delete"
            },
            {
                title: "Set physical zone"
            }
        ];
        $scope.actionOptionSelected = function() {
            // XXX blake_r - TODO
        };

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

        // Mark a node as selected or unselected.
        $scope.toggleChecked = function(node) {
            if(NodesManager.isSelected(node.system_id)) {
                NodesManager.unselectItem(node.system_id);
            } else {
                NodesManager.selectItem(node.system_id);
            }
            updateAllViewableChecked();
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
        });
    }]);
