/* Copyright 2015-2017 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Commissioning Script Controller
 */

angular.module('MAAS').controller('NodeResultController', [
    '$scope', '$rootScope', '$routeParams', '$location',
    'MachinesManager', 'ControllersManager', 'NodeResultsManagerFactory',
    'ManagerHelperService', 'ErrorService',
    function($scope, $rootScope, $routeParams, $location, MachinesManager,
             ControllersManager, NodeResultsManagerFactory,
             ManagerHelperService, ErrorService) {

        // Set the title and page.
        $rootScope.title = "Loading...";
        $rootScope.page = "nodes";

        // Initial values.
        $scope.loaded = false;
        $scope.resultLoaded = false;
        $scope.node = null;
        $scope.output = 'combined';
        $scope.result = null;

        $scope.get_result_data = function(output) {
            $scope.output = output;
            $scope.data = "Loading...";
            var nodeResultsManager = NodeResultsManagerFactory.getManager(
                $scope.node.system_id);
            nodeResultsManager.get_result_data(
                $scope.result.id, $scope.output).then(
                    function(data) {
                        if(data === '') {
                            $scope.data = "Empty file.";
                        }else{
                            $scope.data = data;
                        }
                    });
        };

        // Called once the node is loaded.
        function nodeLoaded(node) {
            $scope.node = node;
            $scope.loaded = true;

            // Get the NodeResultsManager and load it.
            var nodeResultsManager = NodeResultsManagerFactory.getManager(
                $scope.node.system_id);
            nodeResultsManager.loadItems().then(function() {
                var i;
                items = nodeResultsManager.getItems();
                for(i = 0; i < items.length; i++) {
                    if(String(items[i].id) === $routeParams.id) {
                        $scope.result = items[i];
                        break;
                    }
                }
                $scope.get_result_data($scope.output);
                $scope.resultLoaded = true;
                $rootScope.title = $scope.node.fqdn + " - " +
                    $scope.result.name;
            });
        }

        // Update the title when the fqdn of the node changes.
        $scope.$watch("node.fqdn", function() {
            if(angular.isObject($scope.node) &&
               angular.isObject($scope.result)) {
                $rootScope.title = $scope.node.fqdn + " - " +
                    $scope.result.name;
            }
        });

        if($routeParams.type === 'controller') {
            $scope.nodesManager = ControllersManager;
            $scope.type_name = 'controller';
        }else{
            $scope.nodesManager = MachinesManager;
            $scope.type_name = 'machine';
        }
        // Load nodes manager.
        ManagerHelperService.loadManager(
            $scope, $scope.nodesManager).then(function() {
            // If redirected from the NodeDetailsController then the node
            // will already be active. No need to set it active again.
            var activeNode = $scope.nodesManager.getActiveItem();
            if(angular.isObject(activeNode) &&
                activeNode.system_id === $routeParams.system_id) {
                nodeLoaded(activeNode);
            } else {
                $scope.nodesManager.setActiveItem(
                    $routeParams.system_id).then(function(node) {
                        nodeLoaded(node);
                    }, function(error) {
                        ErrorService.raiseError(error);
                    });
            }
        });
    }]);
