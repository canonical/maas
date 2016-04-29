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
        $scope.space = null;
        $scope.vlan = null;
        $scope.fabric = null;
        $scope.all_dns_servers = "";
        $scope.ipranges = IPRangesManager.getItems();
        $scope.spaces = SpacesManager.getItems();
        $scope.vlans = VLANsManager.getItems();
        $scope.fabrics = FabricsManager.getItems();
        $scope.relatedIPRanges = [];

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

        // Called when the dns_servers array is updated.
        $scope.updateDNSServers = function() {
            var subnet = $scope.subnet;
            if(angular.isObject(subnet) &&
                angular.isArray(subnet.dns_servers)) {
                $scope.all_dns_servers = subnet.dns_servers.join(" ");
            } else {
                $scope.all_dns_servers = "";
            }
        };

        $scope.getVLANName = function(vlan) {
           return VLANsManager.getName(vlan);
        };

        $scope.getFabricNameById = function(fabric_id) {
            return FabricsManager.getItemFromList(fabric_id).name;
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

        // Called when the subnet has been loaded.
        function subnetLoaded(subnet) {
            $scope.subnet = subnet;
            $scope.space = SpacesManager.getItemFromList(subnet.space);
            $scope.vlan = VLANsManager.getItemFromList(subnet.vlan);
            $scope.fabric = FabricsManager.getItemFromList($scope.vlan.fabric);
            $scope.updateDNSServers();
            $scope.loaded = true;

            updateTitle();
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
            $scope.$watch("subnet.dns_servers", $scope.updateDNSServers, true);
        });
    }]);
