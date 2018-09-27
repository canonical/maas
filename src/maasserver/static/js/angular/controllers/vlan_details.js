/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS VLAN Details Controller
 */

angular.module('MAAS').filter('ignoreSelf', function () {
    return function(objects, self) {
        var filtered = [];
        angular.forEach(objects, function(obj) {
            if(obj !== self) {
                filtered.push(obj);
            }
        });
        return filtered;
    };
});

angular.module('MAAS').controller('VLANDetailsController', [
    '$scope', '$rootScope', '$routeParams', '$filter', '$location',
    'VLANsManager', 'SubnetsManager', 'SpacesManager', 'FabricsManager',
    'ControllersManager', 'UsersManager', 'ManagerHelperService',
    'ErrorService', 'ValidationService', function(
        $scope, $rootScope, $routeParams, $filter, $location,
        VLANsManager, SubnetsManager, SpacesManager, FabricsManager,
        ControllersManager, UsersManager, ManagerHelperService, ErrorService,
        ValidationService) {
        var vm = this;

        var filterByVLAN = $filter('filterByVLAN');
        var filterControllersByVLAN = $filter('filterControllersByVLAN');

        // Set title and page.
        $rootScope.title = "Loading...";

        // Note: this value must match the top-level tab, in order for
        // highlighting to occur properly.
        $rootScope.page = "networks";

        vm.PROVIDE_DHCP_ACTION = {
            // Note: 'title' is set dynamically depending on whether or not
            // DHCP is already enabled on this VLAN.
            name: "enable_dhcp"
        };
        vm.RELAY_DHCP_ACTION = {
            // Note: 'title' is set ndynamically depending on whether or not
            // DHCP relay is already enabled on this VLAN.
            name: "relay_dhcp"
        };
        vm.DISABLE_DHCP_ACTION = {
            name: "disable_dhcp",
            title: "Disable DHCP"
        };
        vm.DELETE_ACTION = {
            name: "delete",
            title: "Delete"
        };

        // Initial values.
        vm.loaded = false;
        vm.vlan = null;
        vm.title = null;
        vm.actionOption = null;
        vm.actionOptions = [];
        vm.vlanManager = VLANsManager;
        vm.vlans = VLANsManager.getItems();
        vm.subnets = SubnetsManager.getItems();
        vm.spaces = SpacesManager.getItems();
        vm.fabrics = FabricsManager.getItems();
        vm.controllers = ControllersManager.getItems();
        vm.actionError = null;
        vm.relatedSubnets = [];
        vm.relatedControllers = [];
        vm.provideDHCPAction = {};
        vm.primaryRack = null;
        vm.secondaryRack = null;
        vm.editSummary = false;


        // Return true if the authenticated user is super user.
        vm.isSuperUser = function() {
            return UsersManager.isSuperUser();
        };

        // Called when the "edit" button is cliked in the vlan summary
        vm.enterEditSummary = function() {
            vm.editSummary = true;
        };

        // Called when the "cancel" button is cliked in the vlan summary
        vm.exitEditSummary = function() {
            vm.editSummary = false;
        };

        // Get the space name for the VLAN.
        vm.getSpaceName = function() {
            var space = SpacesManager.getItemFromList(vm.vlan.space);
            if(space) {
              return space.name;
            } else {
              return "(undefined)";
            }
        };

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
        vm.initProvideDHCP = function(forRelay) {
            vm.provideDHCPAction = {};
            var dhcp = vm.provideDHCPAction;
            dhcp.subnet = null;
            dhcp.relayVLAN = null;
            if (angular.isNumber(vm.vlan.relay_vlan)) {
                dhcp.relayVLAN = VLANsManager.getItemFromList(
                    vm.vlan.relay_vlan);
            }
            if (angular.isObject(vm.primaryRack)) {
                dhcp.primaryRack = vm.primaryRack.system_id;
            } else if(vm.relatedControllers.length > 0) {
                // Select the primary controller arbitrarily by default.
                dhcp.primaryRack = vm.relatedControllers[0].system_id;
            }
            if (angular.isObject(vm.secondaryRack)) {
                dhcp.secondaryRack = vm.secondaryRack.system_id;
            } else if(vm.relatedControllers.length > 1) {
                // Select the secondary controller arbitrarily by default.
                dhcp.secondaryRack = vm.relatedControllers[1].system_id;
            }
            dhcp.maxIPs = 0;
            dhcp.startIP = null;
            dhcp.endIP = null;
            dhcp.gatewayIP = "";
            if (angular.isObject(vm.relatedSubnets)) {
                // Select a subnet arbitrarily by default.
                if (vm.relatedSubnets.length > 0 &&
                        angular.isObject(vm.relatedSubnets[0].subnet)) {
                    dhcp.subnet = vm.relatedSubnets[0].subnet.id;
                }
                dhcp.needsDynamicRange = true;
                var i, subnet;
                for (i = 0; i < vm.relatedSubnets.length; i++) {
                    subnet = vm.relatedSubnets[i].subnet;
                    // If any related subnet already has a dynamic range, we
                    // cannot prompt the user to enter one here. If a
                    // suggestion does not exist, a range does not exist
                    // already.
                    var iprange = subnet.statistics.suggested_dynamic_range;
                    if (!angular.isObject(iprange)) {
                        // If there is already a dynamic range on one of the
                        // subnets, it's the "subnet of least surprise" if
                        // the user is choosing to reconfigure their rack
                        // controllers. (if they want DHCP on *another* subnet,
                        // they should need to be explicit about it.)
                        dhcp.subnet = subnet.id;
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
            // Since we are setting default values for these three options,
            // ensure all the appropriate updates occur.
            if(!forRelay) {
                vm.updatePrimaryRack();
                vm.updateSecondaryRack();
            }
            vm.updateSubnet(forRelay);
        };

        // Called when the actionOption has changed.
        vm.actionOptionChanged = function() {
            if(vm.actionOption.name === "enable_dhcp") {
                vm.initProvideDHCP(false);
            } else if(vm.actionOption.name === "relay_dhcp") {
                vm.initProvideDHCP(true);
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
            // If the user selects the secondary controller to be the primary,
            // then the primary controller needs to be cleared out.
            if(dhcp.primaryRack === dhcp.secondaryRack) {
                dhcp.secondaryRack = null;
            }
            var i;
            for(i = 0 ; i < vm.relatedControllers.length ; i++) {
                if(vm.relatedControllers[i].system_id !== dhcp.primaryRack) {
                    dhcp.secondaryRack = vm.relatedControllers[i].system_id;
                    break;
                }
            }
        };

        // Called from the Provide DHCP form when the secondary rack changes.
        vm.updateSecondaryRack = function() {
            var dhcp = vm.provideDHCPAction;
            // This should no longer be possible due to the filters on the
            // drop-down boxes, but just in case.
            if(dhcp.primaryRack === dhcp.secondaryRack) {
                dhcp.primaryRack = null;
                dhcp.secondaryRack = null;
            }
        };

        // Called from the view to exclude the primary rack when selecting
        // the secondary rack controller.
        vm.filterPrimaryRack = function(rack) {
            var dhcp = vm.provideDHCPAction;
            return rack.system_id !== dhcp.primaryRack;
        };

        // Called from the Provide DHCP form when the subnet selection changes.
        vm.updateSubnet = function(forRelay) {
            var dhcp = vm.provideDHCPAction;
            var subnet = SubnetsManager.getItemFromList(dhcp.subnet);
            if(angular.isObject(subnet)) {
                var suggested_gateway = null;
                var iprange = null;
                if(angular.isObject(subnet.statistics)) {
                    suggested_gateway = subnet.statistics.suggested_gateway;
                    iprange = subnet.statistics.suggested_dynamic_range;
                }
                if(angular.isObject(iprange) && iprange.num_addresses > 0) {
                    dhcp.maxIPs = iprange.num_addresses;
                    if(forRelay) {
                        dhcp.startIP = "";
                        dhcp.endIP = "";
                        dhcp.startPlaceholder = iprange.start + "(optional)";
                        dhcp.endPlaceholder = iprange.end + " (optional)";
                    } else {
                        dhcp.startIP = iprange.start;
                        dhcp.endIP = iprange.end;
                        dhcp.startPlaceholder = iprange.start;
                        dhcp.endPlaceholder = iprange.end;
                    }
                } else {
                    // Need to add a dynamic range, but according to our data,
                    // there is no room on the subnet for a dynamic range.
                    dhcp.maxIPs = 0;
                    dhcp.startIP = "";
                    dhcp.endIP = "";
                    dhcp.startPlaceholder = "(no available IPs)";
                    dhcp.endPlaceholder = "(no available IPs)";
                }
                if(angular.isString(suggested_gateway)) {
                    if(forRelay) {
                      dhcp.gatewayIP = "";
                      dhcp.gatewayPlaceholder = (
                          suggested_gateway + " (optional)");
                    } else {
                        dhcp.gatewayIP = suggested_gateway;
                        dhcp.gatewayPlaceholder = suggested_gateway;
                    }
                } else {
                    // This means the subnet already has a gateway, so don't
                    // bother populating it.
                    dhcp.gatewayIP = "";
                    dhcp.gatewayPlaceholder = "";
                }
            } else {
                // Don't need to add a dynamic range, so ensure these fields
                // are cleared out.
                dhcp.maxIPs = 0;
                dhcp.startIP = null;
                dhcp.endIP = null;
                dhcp.gatewayIP = "";
            }
            if(angular.isObject(subnet)) {
                dhcp.subnetMissingGatewayIP = !angular.isString(
                    subnet.gateway_ip);
            } else {
                dhcp.subnetMissingGatewayIP = false;
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

        // Return True if the current action can be performed.
        vm.canPerformAction = function() {
            if(vm.actionOption.name === "enable_dhcp") {
                return vm.relatedSubnets.length > 0;
            } else if(vm.actionOption.name === "relay_dhcp") {
                return angular.isObject(vm.provideDHCPAction.relayVLAN);
            } else {
                return true;
            }
        };

        // Perform the action.
        vm.actionGo = function() {
            // Do nothing if action cannot be performed.
            if(!vm.canPerformAction()) {
               return;
            }

            if(vm.actionOption.name === "enable_dhcp") {
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
                // Abort the action without calling down to the region if
                // the user didn't select a controller.
                if(controllers.length === 0) {
                    vm.actionError =
                        "A primary rack controller must be specified.";
                    return;
                }
                VLANsManager.configureDHCP(
                    vm.vlan, controllers, extra).then(function() {
                        vm.actionOption = null;
                        vm.actionError = null;
                    }, function(result) {
                        vm.actionError = result.error;
                        vm.actionOption = vm.PROVIDE_DHCP_ACTION;
                    });
            } else if(vm.actionOption.name === "relay_dhcp") {
                // These will be undefined if they don't exist, and the region
                // will simply get an empty dictionary.
                var extraDHCP = {};
                extraDHCP.subnet = vm.provideDHCPAction.subnet;
                extraDHCP.start = vm.provideDHCPAction.startIP;
                extraDHCP.end = vm.provideDHCPAction.endIP;
                extraDHCP.gateway = vm.provideDHCPAction.gatewayIP;
                var relay = vm.provideDHCPAction.relayVLAN.id;
                VLANsManager.configureDHCP(
                    vm.vlan, [], extraDHCP, relay).then(function() {
                        vm.actionOption = null;
                        vm.actionError = null;
                    }, function(result) {
                        vm.actionError = result.error;
                        vm.actionOption = vm.RELAY_DHCP_ACTION;
                    });
            } else if(vm.actionOption.name === "disable_dhcp") {
                VLANsManager.disableDHCP(vm.vlan).then(function() {
                    vm.actionOption = null;
                    vm.actionError = null;
                }, function(result) {
                    vm.actionError = result.error;
                    vm.actionOption = vm.DISABLE_DHCP_ACTION;
                });
            } else if(vm.actionOption.name === "delete") {
                VLANsManager.deleteVLAN(vm.vlan).then(function() {
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

        // Return the name of the VLAN.
        vm.getFullVLANName = function(vlan_id) {
            var vlan = VLANsManager.getItemFromList(vlan_id);
            var fabric = FabricsManager.getItemFromList(vlan.fabric);
            return (
                FabricsManager.getName(fabric) + "." +
                VLANsManager.getName(vlan));
        };

        // Return the current DHCP status.
        vm.getDHCPStatus = function() {
            if(vm.vlan) {
              if(vm.vlan.dhcp_on) {
                return "Enabled";
              } else if(vm.vlan.relay_vlan) {
                return "Relayed via " + vm.getFullVLANName(vm.vlan.relay_vlan);
              } else {
                return "Disabled";
              }
            } else {
              return "";
            }
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
            if(vlan.primary_rack) {
                vm.primaryRack = ControllersManager.getItemFromList(
                    vlan.primary_rack);
            } else {
                vm.primaryRack = null;
            }
            if(vlan.secondary_rack) {
                vm.secondaryRack = ControllersManager.getItemFromList(
                    vlan.secondary_rack);
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
            var racks = [];
            angular.forEach(vlan.rack_sids, function(rack_sid) {
                var rack = ControllersManager.getItemFromList(rack_sid);
                if(angular.isObject(rack)) {
                    racks.push(rack);
                }
            });
            vm.relatedControllers = racks;
        }

        // Called from a $watch when the related subnets or spaces may have
        // changed.
        function updateRelatedSubnets() {
            var vlan = vm.vlan;
            if(!angular.isObject(vlan)) {
                return;
            }
            var subnets = [];
            angular.forEach(
                    filterByVLAN(vm.subnets, vlan), function(subnet) {
                var space = SpacesManager.getItemFromList(subnet.space);
                if(!angular.isObject(space)) {
                    space = {name: "(undefined)"};
                }
                var row = {
                    subnet: subnet,
                    space: space
                };
                subnets.push(row);
            });
            vm.relatedSubnets = subnets;
        }

        function updatePossibleActions() {
            var vlan = vm.vlan;
            if(!angular.isObject(vlan)) {
                return;
            }
            // Clear out the actionOptions array. (this needs to be the same
            // object, since it's watched from $scope.)
            vm.actionOptions.length = 0;
            if(UsersManager.isSuperUser()) {
                if(!vlan.relay_vlan) {
                  if(vlan.dhcp_on === true) {
                      vm.PROVIDE_DHCP_ACTION.title = "Reconfigure DHCP";
                      vm.actionOptions.push(vm.PROVIDE_DHCP_ACTION);
                      vm.actionOptions.push(vm.DISABLE_DHCP_ACTION);
                  } else {
                      vm.PROVIDE_DHCP_ACTION.title = "Provide DHCP";
                      vm.RELAY_DHCP_ACTION.title = "Relay DHCP";
                      vm.actionOptions.push(vm.PROVIDE_DHCP_ACTION);
                      vm.actionOptions.push(vm.RELAY_DHCP_ACTION);
                  }
                } else {
                  vm.actionOptions.push(vm.RELAY_DHCP_ACTION);
                  vm.actionOptions.push(vm.DISABLE_DHCP_ACTION);
                  vm.RELAY_DHCP_ACTION.title = "Reconfigure DHCP relay";
                }
                if(!vm.isFabricDefault) {
                    vm.actionOptions.push(vm.DELETE_ACTION);
                }
            }
        }

        // Called when the vlan has been loaded.
        function vlanLoaded(vlan) {
            vm.vlan = vlan;
            updateVLAN();
            vm.loaded = true;
        }

        function updateVLAN() {
            if(!vm.loaded) {
                return;
            }
            var vlan = vm.vlan;
            vm.fabric = FabricsManager.getItemFromList(vlan.fabric);
            vm.isFabricDefault = vm.fabric.default_vlan_id === vm.vlan.id;

            updateTitle();
            updateManagementRacks();
            updateRelatedControllers();
            updateRelatedSubnets();
            updatePossibleActions();
        }

        // Load all the required managers.
        ManagerHelperService.loadManagers($scope, [
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
            $scope.$watch("vlanDetails.vlan.fabric", updateVLAN);
            $scope.$watch("vlanDetails.vlan.dhcp_on", updatePossibleActions);
            $scope.$watch(
                "vlanDetails.vlan.relay_vlan", updatePossibleActions);
            $scope.$watch("vlanDetails.fabric.name", updateTitle);
            $scope.$watch(
                "vlanDetails.vlan.primary_rack", updateManagementRacks);
            $scope.$watch(
                "vlanDetails.vlan.secondary_rack", updateManagementRacks);

            $scope.$watchCollection(
                "vlanDetails.subnets", updateRelatedSubnets);
            $scope.$watchCollection(
                "vlanDetails.spaces", updateRelatedSubnets);
            $scope.$watchCollection(
                "vlanDetails.controllers", updateRelatedControllers);
        });
    }]);
