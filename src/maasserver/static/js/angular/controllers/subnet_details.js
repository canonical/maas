/* Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Subnet Details Controller
 */

angular.module('MAAS').filter('filterSource', ['ValidationService',
    function() {
        return function(subnets, source) {
            var filtered = [];
            angular.forEach(subnets, function(subnet) {
                if(subnet.id !== source.id &&
                    subnet.version === source.version) {
                    filtered.push(subnet);
                }
            });
            return filtered;
        };
    }]);

angular.module('MAAS').controller('SubnetDetailsController', [
    '$scope', '$rootScope', '$routeParams', '$filter', '$location',
    'SubnetsManager', 'IPRangesManager', 'SpacesManager', 'VLANsManager',
    'UsersManager', 'FabricsManager', 'StaticRoutesManager',
    'ManagerHelperService', 'ErrorService', 'ConverterService',
    function(
        $scope, $rootScope, $routeParams, $filter, $location, SubnetsManager,
        IPRangesManager, SpacesManager, VLANsManager, UsersManager,
        FabricsManager, StaticRoutesManager,
        ManagerHelperService, ErrorService, ConverterService) {

        // Set title and page.
        $rootScope.title = "Loading...";

        // Note: this value must match the top-level tab, in order for
        // highlighting to occur properly.
        $rootScope.page = "networks";

        // Initial values.
        $scope.loaded = false;
        $scope.subnet = null;
        $scope.subnets = SubnetsManager.getItems();
        $scope.subnetManager = SubnetsManager;
        $scope.ipranges = IPRangesManager.getItems();
        $scope.iprangeManager = IPRangesManager;
        $scope.staticRoutes = StaticRoutesManager.getItems();
        $scope.staticRoutesManager = StaticRoutesManager;
        $scope.spaces = SpacesManager.getItems();
        $scope.vlans = VLANsManager.getItems();
        $scope.fabrics = FabricsManager.getItems();
        $scope.actionError = null;
        $scope.actionOption = null;
        $scope.actionOptions = [];
        $scope.reverse = false;
        $scope.newRange = null;
        $scope.editIPRange = null;
        $scope.deleteIPRange = null;
        $scope.newStaticRoute = null;
        $scope.editStaticRoute = null;
        $scope.deleteStaticRoute = null;

        $scope.MAP_SUBNET_ACTION = {
            name: "map_subnet",
            title: "Map Subnet"
        };
        $scope.DELETE_ACTION = {
            name: "delete",
            title: "Delete"
        };

        // Alloc type mapping.
        var ALLOC_TYPES = {
            0: 'Automatic',
            1: 'Static',
            4: 'User reserved',
            5: 'DHCP',
            6: 'Observed'
        };

        // Node type mapping.
        var NODE_TYPES = {
            0: 'Machine',
            1: 'Device',
            2: 'Rack controller',
            3: 'Region controller',
            4: 'Rack and region controller'
        };

        // Updates the page title.
        function updateTitle() {
            subnet = $scope.subnet;
            if(subnet && subnet.cidr) {
                $rootScope.title = subnet.cidr;
                if(subnet.name && subnet.cidr !== subnet.name) {
                    $rootScope.title += " (" +subnet.name + ")";
                }
            }
        }

        // Update the IP version of the CIDR.
        function updateIPVersion() {
            var ip = $scope.subnet.cidr.split('/')[0];
            if(ip.indexOf(':') === -1) {
                $scope.ipVersion = 4;
            } else {
                $scope.ipVersion = 6;
            }
        }

        // Sort for IP address.
        $scope.ipSort = function(ipAddress) {
            if($scope.ipVersion === 4) {
                return ConverterService.ipv4ToInteger(ipAddress.ip);
            } else {
                return ConverterService.ipv6Expand(ipAddress.ip);
            }
        };

        // Set default predicate to the ipSort function.
        $scope.predicate = $scope.ipSort;

        // Return the name of the allocation type.
        $scope.getAllocType = function(allocType) {
            var str = ALLOC_TYPES[allocType];
            if(angular.isString(str)) {
                return str;
            } else {
                return "Unknown";
            }
        };

        $scope.getSubnetCIDR = function(destId) {
            return SubnetsManager.getItemFromList(destId).cidr;
        };

        // Sort based on the name of the allocation type.
        $scope.allocTypeSort = function(ipAddress) {
            return $scope.getAllocType(ipAddress.alloc_type);
        };

        // Return the name of the node type.
        $scope.getNodeType = function(nodeType) {
            var str = NODE_TYPES[nodeType];
            if(angular.isString(str)) {
                return str;
            } else {
                return "Unknown";
            }
        };

        // Sort based on the node type string.
        $scope.nodeTypeSort = function(ipAddress) {
            return $scope.getNodeType(ipAddress.node_summary.node_type);
        };

        // Sort based on the owner name.
        $scope.ownerSort = function(ipAddress) {
            var owner = ipAddress.user;
            if(angular.isString(owner) && owner.length > 0) {
                return owner;
            } else {
                return "MAAS";
            }
        };

        // Called to change the sort order of the IP table.
        $scope.sortIPTable = function(predicate) {
            $scope.predicate = predicate;
            $scope.reverse = !$scope.reverse;
        };

        // Return the name of the VLAN.
        $scope.getVLANName = function(vlan) {
           return VLANsManager.getName(vlan);
        };

        // Return true if the authenticated user is super user.
        $scope.isSuperUser = function() {
            return UsersManager.isSuperUser();
        };

        $scope.actionRetry = function() {
            // When we clear actionError, the HTML will be re-rendered to
            // hide the error message (and the user will be taken back to
            // the previous action they were performing, since we reset
            // the actionOption in the error handler.
            $scope.actionError = null;
        };

        // Perform the action.
        $scope.actionGo = function() {
            if($scope.actionOption.name === "map_subnet") {
                SubnetsManager.scanSubnet($scope.subnet).then(function(result) {
                    if(result && result.scan_started_on.length === 0) {
                        $scope.actionError =
                            ManagerHelperService.parseValidationError(
                                result.result);
                    } else {
                        $scope.actionOption = null;
                        $scope.actionError = null;
                    }
                }, function(error) {
                    $scope.actionError =
                        ManagerHelperService.parseValidationError(error);
                });
            } else if($scope.actionOption.name === "delete") {
                SubnetsManager.deleteSubnet(
                    $scope.subnet).then(function(result) {
                        console.log(result);
                        $scope.actionOption = null;
                        $scope.actionError = null;
                        $location.path("/networks");
                    }, function(error) {
                        $scope.actionError =
                            ManagerHelperService.parseValidationError(error);
                });
            }
        };

        // Called when a action is selected.
        $scope.actionChanged = function() {
            $scope.actionError = null;
        };

        // Called when the "Cancel" button is pressed.
        $scope.cancelAction = function() {
            $scope.actionOption = null;
            $scope.actionError = null;
        };

        // Called when the managers load to populate the actions the user
        // is allowed to perform.
        $scope.updateActions = function() {
            if(UsersManager.isSuperUser()) {
                $scope.actionOptions = [
                    $scope.MAP_SUBNET_ACTION,
                    $scope.DELETE_ACTION
                ];
            } else {
                $scope.actionOptions = [];
            }
        };

        // Called by maas-obj-form before it saves the subnet. The passed
        // subnet is the object right before its sent over the websocket.
        $scope.subnetPreSave = function(subnet, changedFields) {
            // Adjust the subnet object if the fabric changed.
            if(changedFields.indexOf("fabric") !== -1) {
                // Fabric changed, the websocket expects VLAN to be updated, so
                // we set the VLAN to the default VLAN for the new fabric.
                subnet.vlan = FabricsManager.getItemFromList(
                    subnet.fabric).default_vlan_id;
            }
            return subnet;
        };

        // Called to start adding a new IP range.
        $scope.addRange = function(type) {
            $scope.newRange = {
                type: type,
                subnet: $scope.subnet.id,
                start_ip: "",
                end_ip: "",
                comment: ""
            };
            if(type === "dynamic") {
                $scope.newRange.comment = "Dynamic";
            }
        };

        // Cancel adding the new IP range.
        $scope.cancelAddRange = function() {
            $scope.newRange = null;
        };

        // Return true if the IP range can be modified by the
        // authenticated user.
        $scope.ipRangeCanBeModified = function(range) {
            if($scope.isSuperUser()) {
                return true;
            } else {
                // Can only modify reserved and same user.
                return (
                    range.type === "reserved" &&
                    range.user === UsersManager.getAuthUser().id);
            }
        };

        // Return true if the IP range is in edit mode.
        $scope.isIPRangeInEditMode = function(range) {
            return $scope.editIPRange === range;
        };

        // Toggle edit mode for the IP range.
        $scope.ipRangeToggleEditMode = function(range) {
            $scope.deleteIPRange = null;
            if($scope.isIPRangeInEditMode(range)) {
                $scope.editIPRange = null;
            } else {
                $scope.editIPRange = range;
            }
        };

        // Clear edit mode for the IP range.
        $scope.ipRangeClearEditMode = function() {
            $scope.editIPRange = null;
        };

        // Return true if the IP range is in delete mode.
        $scope.isIPRangeInDeleteMode = function(range) {
            return $scope.deleteIPRange === range;
        };

        // Enter delete mode for the IP range.
        $scope.ipRangeEnterDeleteMode = function(range) {
            $scope.editIPRange = null;
            $scope.deleteIPRange = range;
        };

        // Exit delete mode for the IP range.
        $scope.ipRangeCancelDelete = function() {
            $scope.deleteIPRange = null;
        };

        // Perform the delete operation on the IP range.
        $scope.ipRangeConfirmDelete = function() {
            IPRangesManager.deleteItem($scope.deleteIPRange).then(function() {
                $scope.deleteIPRange = null;
            });
        };

        // Called to start adding a new static route.
        $scope.addStaticRoute = function() {
            $scope.editStaticRoute = null;
            $scope.deleteStaticRoute = null;
            $scope.newStaticRoute = {
                source: $scope.subnet.id,
                gateway_ip: "",
                destination: null,
                metric: 0
            };
        };

        // Cancel adding the new static route.
        $scope.cancelAddStaticRoute = function() {
            $scope.newStaticRoute = null;
        };

        // Return true if the static route is in edit mode.
        $scope.isStaticRouteInEditMode = function(route) {
            return $scope.editStaticRoute === route;
        };

        // Toggle edit mode for the static route.
        $scope.staticRouteToggleEditMode = function(route) {
            $scope.newStaticRoute = null;
            $scope.deleteStaticRoute = null;
            if($scope.isStaticRouteInEditMode(route)) {
                $scope.editStaticRoute  = null;
            } else {
                $scope.editStaticRoute = route;
            }
        };

        // Return true if the static route is in delete mode.
        $scope.isStaticRouteInDeleteMode = function(route) {
            return $scope.deleteStaticRoute === route;
        };

        // Enter delete mode for the static route.
        $scope.staticRouteEnterDeleteMode = function(route) {
            $scope.newStaticRoute = null;
            $scope.editStaticRoute = null;
            $scope.deleteStaticRoute = route;
        };

        // Exit delete mode for the statc route.
        $scope.staticRouteCancelDelete = function() {
            $scope.deleteStaticRoute = null;
        };

        // Perform the delete operation on the static route.
        $scope.staticRouteConfirmDelete = function() {
            StaticRoutesManager.deleteItem($scope.deleteStaticRoute).then(
                function() {
                    $scope.deleteStaticRoute = null;
                });
        };

        // Called when the subnet has been loaded.
        function subnetLoaded(subnet) {
            $scope.subnet = subnet;
            $scope.loaded = true;

            updateTitle();

            // Watch the vlan and fabric field so if its changed on the subnet
            // we make sure that the fabric is updated. It is possible that
            // fabric is removed from the subnet since it is injected from this
            // controller, so when it is removed we add it back.
            var updateFabric = function() {
                $scope.subnet.fabric = (
                    VLANsManager.getItemFromList($scope.subnet.vlan).fabric);
            };
            $scope.$watch("subnet.fabric", updateFabric);
            $scope.$watch("subnet.vlan", updateFabric);
            $scope.$watch("subnet.cidr", updateIPVersion);
        }

        // Load all the required managers.
        ManagerHelperService.loadManagers($scope, [
            SubnetsManager, IPRangesManager, SpacesManager, VLANsManager,
            UsersManager, FabricsManager, StaticRoutesManager
        ]).then(function() {

            $scope.updateActions();

            // Possibly redirected from another controller that already had
            // this subnet set to active. Only call setActiveItem if not
            // already the activeItem.
            var activeSubnet = SubnetsManager.getActiveItem();
            var requestedSubnet = parseInt($routeParams.subnet_id, 10);
            if(isNaN(requestedSubnet)) {
                ErrorService.raiseError("Invalid subnet identifier.");
            } else if(angular.isObject(activeSubnet) &&
                activeSubnet.id === requestedSubnet) {
                subnetLoaded(activeSubnet);
            } else {
                SubnetsManager.setActiveItem(
                    requestedSubnet).then(function(subnet) {
                        subnetLoaded(subnet);
                    }, function(error) {
                        ErrorService.raiseError(error);
                    });
            }
        });
    }]);
