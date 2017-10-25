/* Copyright 2017 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Node Results Controller
 */

angular.module('MAAS').controller('NodeResultsController', [
    '$scope', '$routeParams', 'MachinesManager', 'ControllersManager',
    'NodeResultsManagerFactory', 'ManagerHelperService', 'ErrorService',
    function($scope, $routeParams, MachinesManager, ControllersManager,
             NodeResultsManagerFactory, ManagerHelperService, ErrorService) {

        // NodeResultsManager that is loaded once the node is loaded.
        var nodeResultsManager = null;
        // References to manager data used in scope.
        $scope.commissioning_results = null;
        $scope.testing_results = null;
        $scope.installation_results = null;
        $scope.results = null;

        // Initial values.
        $scope.loaded = false;
        $scope.resultsLoaded = false;
        $scope.node = null;

        // Called once the node has loaded.
        function nodeLoaded(node) {
            $scope.node = node;
            $scope.loaded = true;
            // Get the NodeResultsManager and load it.
            nodeResultsManager = NodeResultsManagerFactory.getManager(
                node, $scope.section.area);
            nodeResultsManager.loadItems().then(function() {
                $scope.commissioning_results =
                    nodeResultsManager.commissioning_results;
                $scope.testing_results = nodeResultsManager.testing_results;
                $scope.installation_results =
                    nodeResultsManager.installation_results;
                $scope.results = nodeResultsManager.results;
                $scope.resultsLoaded = true;
            });
        }

        if($routeParams.type === 'controller') {
            $scope.nodesManager = ControllersManager;
        }else{
            $scope.nodesManager = MachinesManager;
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
                }else{
                    $scope.nodesManager.setActiveItem(
                        $routeParams.system_id).then(function(node) {
                            nodeLoaded(node);
                        }, function(error) {
                            ErrorService.raiseError(error);
                        });
                }
            });

        // Destroy the NodeResultsManager when the scope is destroyed. This is
        // so the client will not recieve any more notifications about results
        // from this node.
        $scope.$on("$destroy", function() {
            if(angular.isObject(nodeResultsManager)) {
                nodeResultsManager.destroy();
            }
        });
    }]);
