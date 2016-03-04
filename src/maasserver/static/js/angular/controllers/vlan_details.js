/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS VLAN Details Controller
 */

angular.module('MAAS').controller('VLANDetailsController', [
    '$scope', '$rootScope', '$routeParams', '$filter', '$location',
    'VLANsManager', 'SubnetsManager', 'SpacesManager', 'FabricsManager',
    'ControllersManager', 'UsersManager', 'ManagerHelperService',
    'ErrorService', function(
        $scope, $rootScope, $routeParams, $filter, $location,
        VLANsManager, SubnetsManager, SpacesManager, FabricsManager,
        ControllersManager, UsersManager, ManagerHelperService, ErrorService) {
        var vm = this;

        var filterByVLAN = $filter('filterByVLAN');
        var filterSpacesByVLAN = $filter('filterSpacesByVLAN');
        var filterControllersByVLAN = $filter('filterControllersByVLAN');

        // Set title and page.
        $rootScope.title = "Loading...";

        // Note: this value must match the top-level tab, in order for
        // highlighting to occur properly.
        $rootScope.page = "networks";

        // Initial values.
        vm.PROVIDE_DHCP_ACTION = {name:"provide_dhcp", title:"Provide DHCP"};
        vm.DELETE_ACTION = {name:"delete", title:"Delete"};

        vm.loaded = false;
        vm.vlan = null;
        vm.title = null;
        vm.actionOption = null;
        vm.actionOptions = [];
        vm.subnets = SubnetsManager.getItems();
        vm.spaces = SpacesManager.getItems();
        vm.controllers = ControllersManager.getItems();
        vm.actionError = null;
        vm.relatedSubnets = [];
        vm.relatedSpaces = [];
        vm.relatedControllers = [];
        vm.provideDHCPAction = {};
        vm.primaryRack = null;
        vm.secondaryRack = null;

        // Get the aciton structure for the action with the specified name.
        vm.getActionByName = function(name) {
            var i;
            for(i = 0 ; i < vm.actionOptions.length ; i++) {
                if(vm.actionOptions[i].name === name) {
                    return vm.actionOptions[i];
                }
            }
            return null;
        };

        // Initialize the provideDHCPAction structure with the current primary
        // and secondary rack, plus an indication regarding whether or not
        // adding a dynamic IP range is required.
        vm.initProvideDHCP = function() {
            vm.provideDHCPAction = {};
            var dhcp = vm.provideDHCPAction;
            dhcp.subnet = null;
            if (angular.isObject(vm.primaryRack)) {
                dhcp.primaryRack = vm.primaryRack.system_id;
            }
            if (angular.isObject(vm.secondaryRack)) {
                dhcp.secondaryRack = vm.secondaryRack.system_id;
            }
            dhcp.maxIPs = 0;
            dhcp.startIP = null;
            dhcp.endIP = null;
            dhcp.gatewayIP = "";
            if (angular.isObject(vm.relatedSubnets)) {
                dhcp.needsDynamicRange = true;
                var i, subnet;
                for (i = 0; i < vm.relatedSubnets.length; i++) {
                    subnet = vm.relatedSubnets[i].subnet;
                    // If any related subnet already has a dynamic range, we
                    // cannot prompt the user to enter one here.
                    if (SubnetsManager.hasDynamicRange(subnet)) {
                        dhcp.needsDynamicRange = false;
                        break;
                    }
                }
                // We must prompt the user for a subnet and a gateway IP
                // address if any subnet does not yet contain a gateway IP
                // address.
                dhcp.needsGatewayIP = false;
                dhcp.subnetMissingGatewayIP = true;
                for (i = 0; i < vm.relatedSubnets.length; i++) {
                    subnet = vm.relatedSubnets[i].subnet;
                    if(subnet.gateway_ip === null ||
                        subnet.gateway_ip === '') {
                        dhcp.needsGatewayIP = true;
                        break;
                    }
                }
            }
        };

        // Called when the actionOption has changed.
        vm.actionOptionChanged = function() {
            if(vm.actionOption.name === "provide_dhcp") {
                vm.initProvideDHCP();
            }
            // Clear the action error.
            vm.actionError = null;
        };

        // Cancel the action.
        vm.actionCancel = function() {
            // When the user wants to cancel an action, we need to clear out
            // both the actionOption (so that the action screen will not be
            // presented again) and the actionError (so that the error screen
            // is hidden).
            vm.actionOption = null;
            vm.actionError = null;
        };

        // Called from the Provide DHCP form when the primary rack changes.
        vm.updatePrimaryRack = function() {
            var dhcp = vm.provideDHCPAction;
            if(dhcp.primaryRack === dhcp.secondaryRack) {
                dhcp.secondaryRack = null;
            }
        };

        // Called from the Provide DHCP form when the secondary rack changes.
        vm.updateSecondaryRack = function() {
            var dhcp = vm.provideDHCPAction;
            if(dhcp.primaryRack === dhcp.secondaryRack) {
                dhcp.primaryRack = null;
            }
        };

        // Called from the Provide DHCP form when the subnet selection changes.
        vm.updateSubnet = function() {
            var dhcp = vm.provideDHCPAction;
            var subnet = SubnetsManager.getItemFromList(dhcp.subnet);
            dhcp.subnetMissingGatewayIP = !angular.isString(subnet.gateway_ip);
            if(dhcp.needsDynamicRange === true) {
                var iprange = SubnetsManager.getLargestRange(subnet);
                if(iprange.num_addresses > 0) {
                    dhcp.maxIPs = iprange.num_addresses;
                    dhcp.startIP = iprange.start;
                    dhcp.endIP = iprange.end;
                    dhcp.gatewayIP = iprange.start;
                } else {
                    // Need to add a dynamic range, but according to our data,
                    // there is no room on the subnet for a dynamic range.
                    dhcp.maxIPs = 0;
                    dhcp.startIP = "";
                    dhcp.endIP = "";
                    dhcp.gatewayIP = "";
                }
            } else {
                // Don't need to add a dynamic range, so ensure these fields
                // are cleared out.
                dhcp.maxIPs = 0;
                dhcp.startIP = null;
                dhcp.endIP = null;
                dhcp.gatewayIP = "";
            }
            if(dhcp.subnetMissingGatewayIP === false) {
                dhcp.gatewayIP = null;
            }
       };

        vm.actionRetry = function() {
            // When we clear actionError, the HTML will be re-rendered to
            // hide the error message (and the user will be taken back to
            // the previous action they were performing, since we reset
            // the actionOption in the error handler.
            vm.actionError = null;
        };

        // Perform the action.
        vm.actionGo = function() {
            if(vm.actionOption.name === "provide_dhcp") {
                var dhcp = vm.provideDHCPAction;
                var controllers = [];
                // These will be undefined if they don't exist, and the region
                // will simply get an empty dictionary.
                var extra = {};
                extra.subnet = dhcp.subnet;
                extra.start = dhcp.startIP;
                extra.end = dhcp.endIP;
                extra.gateway = dhcp.gatewayIP;
                if(angular.isString(dhcp.primaryRack)) {
                    controllers.push(dhcp.primaryRack);
                }
                if(angular.isString(dhcp.secondaryRack)) {
                    controllers.push(dhcp.secondaryRack);
                }
                VLANsManager.configureDHCP(
                    vm.vlan, controllers, extra).then(
                    function() {
                        vm.actionOption = null;
                        vm.actionError = null;
                    }, function(result) {
                        vm.actionError = result.error;
                        vm.actionOption = vm.PROVIDE_DHCP_ACTION;
                    });

            } else if(vm.actionOption.name === "delete") {
                VLANsManager.deleteVLAN(vm.vlan).then(
                    function() {
                        $location.path("/networks");
                        vm.actionOption = null;
                        vm.actionError = null;
                    }, function(result) {
                        vm.actionError = result.error;
                        vm.actionOption = vm.DELETE_ACTION;
                    });
            }
        };

        // Return true if there is an action error.
        vm.isActionError = function() {
            return vm.actionError !== null;
        };

        // Updates the page title.
        function updateTitle() {
            var vlan = vm.vlan;
            var fabric = vm.fabric;
            if(angular.isObject(vlan) && angular.isObject(fabric)) {
                if (!vlan.name) {
                    if(vlan.vid === 0) {
                        vm.title = "Default VLAN";
                    } else {
                        vm.title = "VLAN " + vlan.vid;
                    }
                } else {
                    vm.title = vlan.name;
                }
                vm.title += " in " + fabric.name;
                $rootScope.title = vm.title;
            }
        }

        // Called from a $watch when the management racks are updated.
        function updateManagementRacks() {
            var vlan = vm.vlan;
            if(!angular.isObject(vlan)) {
                return;
            }
            if(vlan.primary_rack_sid) {
                vm.primaryRack = ControllersManager.getItemFromList(
                    vlan.primary_rack_sid);
            } else {
                vm.primaryRack = null;
            }
            if(vlan.secondary_rack_sid) {
                vm.secondaryRack = ControllersManager.getItemFromList(
                    vlan.secondary_rack_sid);
            } else {
                vm.secondaryRack = null;
            }
        }

        // Called from a $watch when the related controllers may have changed.
        function updateRelatedControllers() {
            var vlan = vm.vlan;
            if(!angular.isObject(vlan)) {
                return;
            }
            vm.relatedControllers =
                filterControllersByVLAN(vm.controllers, vlan);
        }

        // Called from a $watch when the related subnets or spaces may have
        // changed.
        function updateRelatedSubnetsAndSpaces() {
            var vlan = vm.vlan;
            if(!angular.isObject(vlan)) {
                return;
            }
            var subnets = [];
            var spaces = [];
            angular.forEach(
                    filterSpacesByVLAN(vm.spaces, vlan),
                    function(space) {
                spaces.push(space);
            });
            vm.relatedSpaces = spaces;
            angular.forEach(
                    filterByVLAN(vm.subnets, vlan), function(subnet) {
                var space = SpacesManager.getItemFromList(subnet.space);
                if(!angular.isObject(space)) {
                    space = {name: ""};
                }
                var row = {
                    subnet: subnet,
                    space: space
                };
                subnets.push(row);
            });
            vm.relatedSubnets = subnets;
        }

        // Called when the vlan has been loaded.
        function vlanLoaded(vlan) {
            vm.vlan = vlan;
            vm.fabric = FabricsManager.getItemFromList(vlan.fabric);

            if(UsersManager.isSuperUser()) {
                vm.actionOptions = [vm.PROVIDE_DHCP_ACTION, vm.DELETE_ACTION];
            }

            vm.loaded = true;

            updateTitle();
            updateManagementRacks();
            updateRelatedControllers();
            updateRelatedSubnetsAndSpaces();
        }

        // Load all the required managers.
        ManagerHelperService.loadManagers([
            VLANsManager, SubnetsManager, SpacesManager, FabricsManager,
            ControllersManager, UsersManager
        ]).then(function() {
            // Possibly redirected from another controller that already had
            // this vlan set to active. Only call setActiveItem if not
            // already the activeItem.
            var activeVLAN = VLANsManager.getActiveItem();
            var requestedVLAN = parseInt($routeParams.vlan_id, 10);
            if(isNaN(requestedVLAN)) {
                ErrorService.raiseError("Invalid VLAN identifier.");
            } else if(angular.isObject(activeVLAN) &&
                activeVLAN.id === requestedVLAN) {
                vlanLoaded(activeVLAN);
            } else {
                VLANsManager.setActiveItem(
                    requestedVLAN).then(function(vlan) {
                        vlanLoaded(vlan);
                    }, function(error) {
                        ErrorService.raiseError(error);
                    });
            }

            $scope.$watch("vlanDetails.vlan.name", updateTitle);
            $scope.$watch("vlanDetails.vlan.vid", updateTitle);
            $scope.$watch("vlanDetails.fabric.name", updateTitle);
            $scope.$watch(
                "vlanDetails.vlan.primary_rack", updateManagementRacks);
            $scope.$watch(
                "vlanDetails.vlan.secondary_rack", updateManagementRacks);

            $scope.$watchCollection(
                "vlanDetails.subnets", updateRelatedSubnetsAndSpaces);
            $scope.$watchCollection(
                "vlanDetails.spaces", updateRelatedSubnetsAndSpaces);
            $scope.$watchCollection(
                "vlanDetails.controllers", updateRelatedControllers);
        });
    }]);
