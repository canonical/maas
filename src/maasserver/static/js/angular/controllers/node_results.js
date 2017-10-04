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

        // Initial values.
        $scope.loaded = false;
        $scope.resultsLoaded = false;
        $scope.node = null;
        // Store as an array to preserve order.
        $scope.commissioning_results = [
            {
                title: "CPU",
                hardware_type: 1,
                results: {}
            },
            {
                title: "Memory",
                hardware_type: 2,
                results: {}
            },
            {
                title: "Storage",
                hardware_type: 3,
                results: {}
            },
            {
                title: "Other Results",
                hardware_type: 0,
                results: {}
            }
        ];
        $scope.testing_results = [
            {
                title: "CPU",
                hardware_type: 1,
                results: {}
            },
            {
                title: "Memory",
                hardware_type: 2,
                results: {}
            },
            {
                title: "Storage",
                hardware_type: 3,
                results: {}
            },
            {
                title: "Other Results",
                hardware_type: 0,
                results: {}
            }
        ];
        $scope.installation_result = {};

        function _getSubtext(result) {
            if(result.hardware_type === 3 &&
               result.physical_blockdevice !== null) {
                var i;
                for(i = 0; i < $scope.node.disks.length; i++) {
                    if($scope.node.disks[i].id === result.physical_blockdevice)
                    {
                        var subtext = '';
                        if($scope.node.disks[i].model !== '') {
                            subtext += $scope.node.disks[i].model;
                        }
                        if($scope.node.disks[i].serial !== '') {
                            if(subtext !== '') {
                                subtext += ' ';
                            }
                            subtext += $scope.node.disks[i].serial;
                        }
                        if(subtext !== '') {
                            subtext += ' - ';
                        }
                        subtext += '/dev/' + $scope.node.disks[i].name;
                        return subtext;
                    }
                }
            }
            return null;
        }

        function _storeResult(result) {
            var results;
            result.showing_results = false;
            result.showing_history = false;
            result.showing_menu = false;
            if(result.result_type === 0) {
                results = $scope.commissioning_results;
            }else if(result.result_type === 1) {
                // A node will only store one result at a time.
                $scope.installation_result = result;
                return;
            }else{
                // Store all remaining result type as test results incase
                // another result type is ever added.
                results = $scope.testing_results;
            }
            var i;
            // Fallback to storing results in other results incase a new type
            // is added
            var hardware_type_results = results[3];
            for(i = 0; i < results.length; i++) {
                if(results[i].hardware_type === result.hardware_type) {
                    hardware_type_results = results[i].results;
                    break;
                }
            }
            var subtext = _getSubtext(result);
            if(!angular.isArray(hardware_type_results[subtext])) {
                hardware_type_results[subtext] = [];
            }
            hardware_type_results[subtext].push(result);
        }

        // Called once the node has loaded.
        function nodeLoaded(node) {
            $scope.node = node;
            $scope.loaded = true;
            // Get the NodeResultsManager and load it.
            nodeResultsManager = NodeResultsManagerFactory.getManager(
                node.system_id);
            nodeResultsManager.loadItems().then(function() {
                angular.forEach(nodeResultsManager.getItems(), _storeResult);
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
    }]);
