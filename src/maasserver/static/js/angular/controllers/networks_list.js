/* Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Networks List Controller
 */

angular.module('MAAS').controller('NetworksListController', [
    '$scope', '$rootScope', '$routeParams', '$filter', '$location',
    'SubnetsManager', 'FabricsManager', 'SpacesManager', 'VLANsManager',
    'UsersManager', 'ManagerHelperService',
    function($scope, $rootScope, $routeParams, $filter, $location,
             SubnetsManager, FabricsManager, SpacesManager, VLANsManager,
             UsersManager, ManagerHelperService) {

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

        $scope.ADD_FABRIC_ACTION = {
            name: "add_fabric",
            title: "Fabric",
            selectedTitle: "Add fabric",
            form:
            {
                items: [
                    {
                        title: "Name",
                        placeholder: "Fabric name (optional)"
                    }
                ],
                submit: "Add fabric",
                manager: FabricsManager
            }
        };
        $scope.ADD_VLAN_ACTION = {
            name: "add_vlan",
            title: "VLAN",
            selectedTitle: "Add VLAN",
            form:
            {
                items: [
                    {
                        title: "Fabric",
                        placeholder: "Select fabric",
                        manager: FabricsManager
                    },
                    {
                        title: "VID",
                        placeholder: "VID (1-4094)"
                    },
                    {
                        title: "Name",
                        placeholder: "VLAN name (optional)"
                    }
                ],
                submit: "Add VLAN",
                manager: VLANsManager
            }
        };
        $scope.ADD_SPACE_ACTION = {
            name: "add_space",
            title: "Space",
            selectedTitle: "Add space",
            form:
            {
                items: [
                    {
                        title: "Name",
                        placeholder: "Space name (optional)"
                    }
                ],
                submit: "Add space",
                manager: SpacesManager
            }
        };
        $scope.ADD_SUBNET_ACTION = {
            name: "add_subnet",
            title: "Subnet",
            selectedTitle: "Add subnet",
            form:
            {
                items: [
                    {
                        title: "VLAN",
                        placeholder: "Select VLAN",
                        manager: VLANsManager,
                        groupReference: "fabric",
                        group: FabricsManager
                    },
                    {
                        title: "Space",
                        defaultItem: 0,
                        manager: SpacesManager
                    },
                    {
                        title: "CIDR",
                        placeholder: "169.254.0.0/16"
                    },
                    {
                        title: "Name",
                        placeholder: "Subnet name (optional)"
                    },
                    {
                        title: "Gateway IP",
                        placeholder: "169.254.0.1 (optional)"
                    },
                    {
                        title: "DNS Servers",
                        placeholder: "8.8.8.8 8.8.4.4 (optional)"
                    }
                ],
                submit: "Add subnet",
                manager: SubnetsManager
            }

        };

        $scope.getURLParameters();

        // Set initial values.
        $scope.subnets = SubnetsManager.getItems();
        $scope.fabrics = FabricsManager.getItems();
        $scope.spaces = SpacesManager.getItems();
        $scope.vlans = VLANsManager.getItems();
        $scope.loading = true;

        $scope.requesting = false;

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
                            fabric_name: "",
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
                var index = 0;
                angular.forEach(subnets, function(subnet) {
                    index++;
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
                if(index === 0) {
                    rows.push({
                        space: space,
                        space_name: space.name
                    });
                }
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

        // Called when the managers load to populate the actions the user
        // is allowed to perform.
        $scope.updateActions = function() {
            if(UsersManager.isSuperUser()) {
                $scope.actionOptions = [
                    $scope.ADD_FABRIC_ACTION,
                    $scope.ADD_VLAN_ACTION,
                    $scope.ADD_SPACE_ACTION,
                    $scope.ADD_SUBNET_ACTION
                ];
            } else {
                $scope.actionOptions = [];
            }
        };

        // Called to submit the specified action to the server, and then
        // wait for a reply.
        $scope.submitAction = function(option) {
            var data = {};
            // Scan through the items array and look for form fields to submit
            // to the server.
            angular.forEach(option.form.items, function(item) {
                // Note: If the item has a manager, the `current` value is
                // the primary key.
                data[item.name] = item.current;
            });
            // By setting $scope.requesting, we allow the view access to the
            // information it needs to know when to disable the input boxes.
            // This prevents duplicate submissions from clicking multiple
            // times,if the server does not respond quickly.
            $scope.requesting = true;
            option.form.manager.create(data).then(function(){
                // Success.
                $scope.requesting = false;
                $scope.actionOption = null;
            }, function(error){
                // Failure. Try parsing the resulting error message as a JSON
                // string; if that works, it's most likely a Django error,
                // which we can format appropriately. If not, just display
                // the error.
                $scope.requesting = false;
                error = ManagerHelperService.tryParsingJSON(error);
                if(angular.isObject(error)) {
                    fixErrorTitles(option, error);
                    option.error = ManagerHelperService.getPrintableString(
                        error, true);
                } else {
                    option.error = error;
                }
                // If we got this far but still don't have an error string,
                // just display a generic error to the user.
                if(option.error.trim() === "") {
                    option.error = "Unknown error during request.";
                }
            });
        };

        // Deletes the current value from each form field for the specified
        // action option.
        function clearOptionData(option) {
            angular.forEach(option.form.items, function(item){
                delete item.current;
            });
        }

        // Given the specified option and the specified dictionary of errors,
        // fix up the dictionary keys so that they correspond to the form
        // titles.
        function fixErrorTitles(option, errors) {
            angular.forEach(option.form.items, function(item){
                if(angular.isObject(errors[item.name])) {
                    errors[item.title] = errors[item.name];
                    delete errors[item.name];
                }
            });
        }

        // Called when the "Cancel" button is pressed.
        $scope.cancelAction = function(option) {
            clearOptionData(option);
            option.error = null;
            $scope.actionOption = null;
        };

        // Return the name name for the VLAN.
        function getVLANName(vlan) {
            return VLANsManager.getName(vlan);
        }

        // Return the name of the subnet.
        function getSubnetName(subnet) {
            return SubnetsManager.getName(subnet);
        }

        ManagerHelperService.loadManagers([
            SubnetsManager, FabricsManager, SpacesManager, VLANsManager,
            UsersManager]).then(
            function() {
                $scope.loading = false;

                $scope.updateActions();

                $scope.$watch("subnets", $scope.updateGroupBy, true);
                $scope.$watch("fabrics", $scope.updateGroupBy, true);
                $scope.$watch("spaces", $scope.updateGroupBy, true);
                $scope.$watch("vlans", $scope.updateGroupBy, true);

                // If the route has been updated, a new search string must
                // potentially be rendered.
                $scope.$on("$routeUpdate", function() {
                    $scope.getURLParameters();
                    $scope.updateGroupBy();
                });
            });
    }
]);
