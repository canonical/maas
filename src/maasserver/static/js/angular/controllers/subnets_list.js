/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Subnets List Controller
 */

angular.module('MAAS').controller('SubnetsListController', [
    '$scope', '$rootScope', '$routeParams', '$filter', 'SubnetsManager',
    'FabricsManager', 'SpacesManager', 'VLANsManager', 'ManagerHelperService',
    function($scope, $rootScope, $routeParams, $filter, SubnetsManager,
        FabricsManager, SpacesManager, VLANsManager, ManagerHelperService) {

        // Load the filters that are used inside the controller.
        var filterByVLAN = $filter('filterByVLAN');
        var filterByFabric = $filter('filterByFabric');
        var filterBySpace = $filter('filterBySpace');

        // Set title and page.
        $rootScope.title = "Fabrics";
        $rootScope.page = "subnets";

        // Set initial values.
        $scope.subnets = SubnetsManager.getItems();
        $scope.fabrics = FabricsManager.getItems();
        $scope.spaces = SpacesManager.getItems();
        $scope.vlans = VLANsManager.getItems();
        $scope.currentpage = "fabrics";
        $scope.loading = true;

        $scope.tabs = {};
        // Fabrics tab.
        $scope.tabs.fabrics = {};
        $scope.tabs.fabrics.pagetitle = "Fabrics";
        $scope.tabs.fabrics.currentpage = "fabrics";
        $scope.tabs.fabrics.data = [];

        // Spaces tab.
        $scope.tabs.spaces = {};
        $scope.tabs.spaces.pagetitle = "Spaces";
        $scope.tabs.spaces.currentpage = "spaces";
        $scope.tabs.spaces.data = [];

        // Update the data that is displayed on the fabrics tab.
        function updateFabricsData() {
            var data = [];
            angular.forEach($scope.fabrics, function(fabric) {
                var rows = [];
                var vlans = filterByFabric($scope.vlans, fabric);
                angular.forEach(vlans, function(vlan) {
                    var subnets = filterByVLAN($scope.subnets, vlan);
                    if(subnets.length > 0) {
                        angular.forEach(subnets, function(subnet) {
                            var space = SpacesManager.getItemFromList(
                                subnet.space);
                            var row = {
                                vlan: vlan,
                                space: space,
                                subnet: subnet
                            };
                            rows.push(row);
                        });
                    } else {
                        rows.push({
                            vlan: vlan,
                            space: null,
                            subnet: null
                        });
                    }
                });

                data.push({
                    fabric: fabric,
                    rows: rows
                });
            });
            $scope.tabs.fabrics.data = data;
        }

        // Update the data that is displayed on the spaces tab.
        function updateSpacesData() {
            var data = [];
            angular.forEach($scope.spaces, function(space) {
                var rows = [];
                var subnets = filterBySpace($scope.subnets, space);
                angular.forEach(subnets, function(subnet) {
                    var vlan = VLANsManager.getItemFromList(subnet.vlan);
                    var fabric = FabricsManager.getItemFromList(vlan.fabric);
                    var row = {
                        fabric: fabric,
                        vlan: vlan,
                        subnet: subnet
                    };
                    rows.push(row);
                });

                data.push({
                    space: space,
                    rows: rows
                });
            });
            $scope.tabs.spaces.data = data;
        }

        // Return the name name for the VLAN.
        function getVLANName(vlan) {
            var name = vlan.vid;
            if(vlan.vid === 0) {
                name = "untagged";
            } else if(angular.isString(vlan.name) && vlan.name !== "") {
                name += " (" + vlan.name + ")";
            }
            return name;
        }

        // Toggles between the current tab.
        $scope.toggleTab = function(tab) {
            $rootScope.title = $scope.tabs[tab].pagetitle;
            $scope.currentpage = tab;
        };

        // Get the name of the fabric. Will return empty if the previous
        // row already included the same fabric.
        $scope.getFabricName = function(row, sortedData) {
            if(!angular.isObject(row.fabric)) {
                return "";
            }

            var idx = sortedData.indexOf(row);
            if(idx === 0) {
                return row.fabric.name;
            } else {
                var prevRow = sortedData[idx - 1];
                if(prevRow.fabric === row.fabric) {
                    return "";
                } else {
                    return row.fabric.name;
                }
            }
        };

        // Get the name of the VLAN. Will return empty if the previous
        // row already included the same VLAN unless the fabric is different.
        $scope.getVLANName = function(row, sortedData) {
            if(!angular.isObject(row.vlan)) {
                return "";
            }

            var idx = sortedData.indexOf(row);
            if(idx === 0) {
                return getVLANName(row.vlan);
            } else {
                var prevRow = sortedData[idx - 1];
                var differentFabric = false;
                if(angular.isObject(row.fabric) &&
                    angular.isObject(prevRow.fabric)) {
                    differentFabric = prevRow.fabric !== row.fabric;
                }
                if(prevRow.vlan === row.vlan && !differentFabric) {
                    return "";
                } else {
                    return getVLANName(row.vlan);
                }
            }
        };

        // Get the name of the space. Will return empty if the previous
        // row already included the same space unless the vlan is different.
        $scope.getSpaceName = function(row, sortedData) {
            if(!angular.isObject(row.space)) {
                return "";
            }

            var idx = sortedData.indexOf(row);
            if(idx === 0) {
                return row.space.name;
            } else {
                var prevRow = sortedData[idx - 1];
                if(prevRow.vlan === row.vlan && prevRow.space === row.space) {
                    return "";
                } else {
                    return row.space.name;
                }
            }
        };

        // Return the name of the subnet. Will include the name of the subnet
        // in '(', ')' if it exists and not the same as the cidr.
        $scope.getSubnetName = function(subnet) {
            if(!angular.isObject(subnet)) {
                return "";
            }

            var name = subnet.cidr;
            if(angular.isString(subnet.name) &&
                subnet.name !== "" &&
                subnet.name !== subnet.cidr) {
                name += " (" + subnet.name + ")";
            }
            return name;
        };

        ManagerHelperService.loadManagers([
            SubnetsManager, FabricsManager, SpacesManager, VLANsManager]).then(
            function() {
                $scope.loading = false;

                // Fabrics
                $scope.$watchCollection("fabrics", updateFabricsData);
                $scope.$watchCollection("vlans", updateFabricsData);
                $scope.$watchCollection("subnets", updateFabricsData);
                $scope.$watchCollection("spaces", updateFabricsData);

                // Spaces
                $scope.$watchCollection("fabrics", updateSpacesData);
                $scope.$watchCollection("vlans", updateSpacesData);
                $scope.$watchCollection("subnets", updateSpacesData);
                $scope.$watchCollection("spaces", updateSpacesData);
            });

        // Switch to the specified tab, if specified.
        if($routeParams.tab === "fabrics" || $routeParams.tab === "spaces") {
            $scope.toggleTab($routeParams.tab);
        }
    }]);
