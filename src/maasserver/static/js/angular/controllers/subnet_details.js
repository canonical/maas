/* Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Subnet Details Controller
 */

angular.module('MAAS').controller('SubnetDetailsController', [
    '$scope', '$rootScope', '$routeParams', '$filter', '$location',
    'SubnetsManager', 'IPRangesManager', 'SpacesManager', 'VLANsManager',
    'UsersManager', 'FabricsManager', 'ManagerHelperService', 'ErrorService',
    function(
        $scope, $rootScope, $routeParams, $filter, $location, SubnetsManager,
        IPRangesManager, SpacesManager, VLANsManager, UsersManager,
        FabricsManager, ManagerHelperService, ErrorService) {

        // Set title and page.
        $rootScope.title = "Loading...";

        // Note: this value must match the top-level tab, in order for
        // highlighting to occur properly.
        $rootScope.page = "networks";

        // Initial values.
        $scope.loaded = false;
        $scope.subnet = null;
        $scope.subnetManager = SubnetsManager;
        $scope.ipranges = IPRangesManager.getItems();
        $scope.iprangeManager = IPRangesManager;
        $scope.spaces = SpacesManager.getItems();
        $scope.vlans = VLANsManager.getItems();
        $scope.fabrics = FabricsManager.getItems();
        $scope.newRange = null;
        $scope.editIPRange = null;
        $scope.deleteIPRange = null;

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

        $scope.isSuperUser = function() {
            return UsersManager.isSuperUser();
        };

        $scope.getVLANName = function(vlan) {
           return VLANsManager.getName(vlan);
        };

        // Return true if the authenticated user is super user.
        $scope.isSuperUser = function() {
            return UsersManager.isSuperUser();
        };

        // Called when the delete subnet button is pressed.
        $scope.deleteButton = function() {
            $scope.error = null;
            $scope.confirmingDelete = true;
        };

        // Called when the cancel delete subnet button is pressed.
        $scope.cancelDeleteButton = function() {
            $scope.confirmingDelete = false;
        };

        // Called when the confirm delete subnet button is pressed.
        $scope.deleteConfirmButton = function() {
            SubnetsManager.deleteSubnet($scope.subnet).then(function() {
                $scope.confirmingDelete = false;
                $location.path("/networks");
            }, function(error) {
                $scope.error =
                    ManagerHelperService.parseValidationError(error);
            });
        };

        // Called by maas-obj-form before it saves the subnet. The passed
        // subnet is the object right before its sent over the websocket.
        $scope.subnetPreSave = function(subnet, changedFields) {
            // Adjust the subnet object if the fabric changed.
            if(changedFields.indexOf("fabric") !== -1) {
                // Fabric changed, the websocket expects VLAN to be updated, so
                // we set the VLAN to the default VLAN for the new fabric.
                subnet.vlan = FabricsManager.getItemFromList(
                    subnet.fabric).vlan_ids[0];
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
                $scope.editIPRange  = null;
            } else {
                $scope.editIPRange = range;
            }
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
        }

        // Load all the required managers.
        ManagerHelperService.loadManagers([
            SubnetsManager, IPRangesManager, SpacesManager, VLANsManager,
            UsersManager, FabricsManager
        ]).then(function() {
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
