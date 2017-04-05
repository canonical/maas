/* Copyright 2015-2017 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Commissioning Script Controller
 */

angular.module('MAAS').controller('NodeResultController', [
    '$scope', '$rootScope', '$routeParams', '$location',
    'MachinesManager', 'ControllersManager', 'ManagerHelperService',
    'ErrorService', function($scope, $rootScope, $routeParams, $location,
        MachinesManager, ControllersManager, ManagerHelperService,
        ErrorService) {

        // Set the title and page.
        $rootScope.title = "Loading...";
        $rootScope.page = "nodes";

        // Initial values.
        $scope.loaded = false;
        $scope.node = null;
        $scope.filename = $routeParams.filename;

        // Called once the node is loaded.
        function nodeLoaded(node) {
            $scope.node = node;
            $scope.loaded = true;

            // Update the title when the fqdn of the node changes.
            $scope.$watch("node.fqdn", function() {
                $rootScope.title = $scope.node.fqdn + " - " + $scope.filename;
            });
        }

        // Returns the result data for the requested filename.
        $scope.getResultData = function() {
            if(!angular.isObject($scope.node)) {
                return "";
            }

            var i, output, result, results;
            results = $scope.node.commissioning_results;
            results = results.concat($scope.node.testing_results);
            for(i = 0; i < results.length; i++) {
                result = results[i];
                if (result.name === $scope.filename) {
                    // <code> tags require the content to start on a newline.
                    output = result.output.trim();
                    if (output.length === 0) {
                        return "Empty file.";
                    } else {
                        return output;
                    }
                }
            }

            // If we made it this far then the filename from the routeParams,
            // was incorrect. Redirect the user back to the node details page.
            $location.path('/node/' + $scope.node.system_id);
            return "";
        };

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
