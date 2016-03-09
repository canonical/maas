/* Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Subnets List Controller
 */

angular.module('MAAS').controller('NetworksListController', [
    '$scope', '$rootScope', '$routeParams', '$filter', '$location',
    'SubnetsManager', 'FabricsManager', 'SpacesManager', 'VLANsManager',
    'ManagerHelperService',
    function($scope, $rootScope, $routeParams, $filter, $location,
             SubnetsManager, FabricsManager, SpacesManager, VLANsManager,
             ManagerHelperService) {

        // Load the filters that are used inside the controller.
        var filterByVLAN = $filter('filterByVLAN');
        var filterByFabric = $filter('filterByFabric');
        var filterBySpace = $filter('filterBySpace');

        // Set title and page.
        $rootScope.title = "Networks";
        $rootScope.page = "networks";

        // Set the initial value of $scope.groupBy based on the URL
        // parameters, but default to the 'fabric' groupBy if it's not found.
        $scope.getURLParameters = function() {
            if(angular.isString($location.search().by)) {
                $scope.groupBy = $location.search().by;
            } else {
                $scope.groupBy = 'fabric';
            }
        };

        $scope.getURLParameters();

        // Set initial values.
        $scope.subnets = SubnetsManager.getItems();
        $scope.fabrics = FabricsManager.getItems();
        $scope.spaces = SpacesManager.getItems();
        $scope.vlans = VLANsManager.getItems();
        $scope.loading = true;

        $scope.group = {};
        // Used when grouping by fabrics.
        $scope.group.fabrics = {};
        // User when grouping by spaces.
        $scope.group.spaces = {};

        // Generate a table that can be easily rendered in the view.
        // Traverses the fabrics and VLANs in-order so that if previous
        // fabrics and VLANs' names are identical, they can be hidden from
        // the table cell.
        function updateFabricsGroupBy() {
            var rows = [];
            var previous_fabric = {id:-1};
            var previous_vlan = {id:-1};
            var fabrics = $filter('orderBy')($scope.fabrics, ['name']);
            angular.forEach(fabrics, function(fabric) {
                var vlans = filterByFabric($scope.vlans, fabric);
                vlans = $filter('orderBy')(vlans, ['vid']);
                angular.forEach(vlans, function(vlan) {
                    var subnets = filterByVLAN($scope.subnets, vlan);
                    if(subnets.length > 0) {
                        angular.forEach(subnets, function(subnet) {
                            var space = SpacesManager.getItemFromList(
                                subnet.space);
                            var row = {
                                fabric: fabric,
                                fabric_name: "",
                                vlan: vlan,
                                vlan_name: "",
                                space: space,
                                subnet: subnet,
                                subnet_name: getSubnetName(subnet)
                            };
                            if(fabric.id !== previous_fabric.id) {
                                previous_fabric.id = fabric.id;
                                row.fabric_name = fabric.name;
                            }
                            if(vlan.id !== previous_vlan.id) {
                                previous_vlan.id = vlan.id;
                                row.vlan_name = getVLANName(vlan);
                            }
                            rows.push(row);
                        });
                    } else {
                        var row = {
                            fabric: fabric,
                            fabric_name: fabric.name,
                            vlan: vlan,
                            vlan_name: getVLANName(vlan)
                        };
                        if(fabric.id !== previous_fabric.id) {
                            previous_fabric.id = fabric.id;
                            row.fabric_name = fabric.name;
                        }
                        rows.push(row);
                    }
                });
            });
            $scope.group.fabrics.rows = rows;
        }

        // Generate a table that can be easily rendered in the view.
        // Traverses the spaces in-order so that if the previous space's name
        // is identical, it can be hidden from the table cell.
        // Note that this view only shows items that can be related to a space.
        // That is, VLANs and fabrics with no corresponding subnets (and
        // therefore spaces) cannot be shown in this table.
        function updateSpacesGroupBy() {
            var rows = [];
            var spaces = $filter('orderBy')($scope.spaces, ['name']);
            var previous_space = {id: -1};
            angular.forEach(spaces, function(space) {
                var subnets = filterBySpace($scope.subnets, space);
                subnets = $filter('orderBy')(subnets, ['cidr']);
                angular.forEach(subnets, function(subnet) {
                    var vlan = VLANsManager.getItemFromList(subnet.vlan);
                    var fabric = FabricsManager.getItemFromList(vlan.fabric);
                    var row = {
                        fabric: fabric,
                        vlan: vlan,
                        vlan_name: getVLANName(vlan),
                        subnet: subnet,
                        subnet_name: getSubnetName(subnet),
                        space: space,
                        space_name: ""
                    };
                    if(space.id !== previous_space.id) {
                        previous_space.id = space.id;
                        row.space_name = space.name;
                    }
                    rows.push(row);
                });
            });
            $scope.group.spaces.rows = rows;
        }

        // Update the "Group by" selection. This is called from a few places:
        // * When the $watch notices data has changed
        // * When the URL bar is updated, after the URL is parsed and
        //   $scope.groupBy is updated
        // * When the drop-down "Group by" selection box changes
        $scope.updateGroupBy = function() {
            var groupBy = $scope.groupBy;
            if(groupBy === 'space') {
                $location.search('by', 'space');
                updateSpacesGroupBy();
            } else {
                // The only other option is 'fabric', but in case the user
                // made a typo on the URL bar we just assume it was 'fabric'
                // as a fallback.
                $location.search('by', 'fabric');
                updateFabricsGroupBy();
            }
        };

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

        // Return the name of the subnet. Will include the name of the subnet
        // in '(', ')' if it exists and not the same as the cidr.
        function getSubnetName(subnet) {
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
        }

        ManagerHelperService.loadManagers([
            SubnetsManager, FabricsManager, SpacesManager, VLANsManager]).then(
            function() {
                $scope.loading = false;

                $scope.$watchCollection("subnets", $scope.updateGroupBy);
                $scope.$watchCollection("fabrics", $scope.updateGroupBy);
                $scope.$watchCollection("spaces", $scope.updateGroupBy);
                $scope.$watchCollection("vlans", $scope.updateGroupBy);

                // If the route has been updated, a new search string must
                // potentially be rendered.
                $scope.$on("$routeUpdate", function() {
                    $scope.getURLParameters();
                    $scope.updateGroupBy();
                });
            });
    }
]);
