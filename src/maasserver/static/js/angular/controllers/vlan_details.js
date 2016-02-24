/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS VLAN Details Controller
 */

angular.module('MAAS').controller('VLANDetailsController', [
    '$scope', '$rootScope', '$routeParams', '$filter', '$location',
    'VLANsManager', 'SubnetsManager', 'SpacesManager', 'FabricsManager',
    'ControllersManager', 'ManagerHelperService', 'ErrorService',
    function(
        $scope, $rootScope, $routeParams, $filter, $location,
        VLANsManager, SubnetsManager, SpacesManager, FabricsManager,
        ControllersManager, ManagerHelperService, ErrorService) {

        var filterByVLAN = $filter('filterByVLAN');
        var filterSpacesByVLAN = $filter('filterSpacesByVLAN');
        var filterControllersByVLAN = $filter('filterControllersByVLAN');

        // Set title and page.
        $rootScope.title = "Loading...";

        // Note: this value must match the top-level tab, in order for
        // highlighting to occur properly.
        $rootScope.page = "networks";

        // Initial values.
        $scope.loaded = false;
        $scope.vlan = null;
        $scope.subnets = SubnetsManager.getItems();
        $scope.spaces = SpacesManager.getItems();
        $scope.fabrics = FabricsManager.getItems();
        $scope.controllers = ControllersManager.getItems();
        $scope.related_subnets = [];
        $scope.related_spaces = [];
        $scope.related_controllers = [];

        // Updates the page title.
        function updateTitle() {
            var vlan = $scope.vlan;
            var fabric = $scope.fabric;
            if(vlan) {
                vlan.title = vlan.name;
                if(vlan.vid !== 0 && vlan.name &&
                        vlan.name !== "VLAN " + vlan.vid) {
                    vlan.title += " (VLAN " + vlan.vid + ")";
                } else if(vlan.vid === 0) {
                    vlan.title = "Default VLAN";
                } else if(vlan.vid !== 0) {
                    vlan.title = "VLAN " + vlan.vid;
                }
            }
            vlan.title += " in " + fabric.name;
            $rootScope.title = vlan.title;
        }

        function updateRelatedObjects() {
            var subnets = [];
            var spaces = [];
            var controllers = [];
            var vlan = $scope.vlan;
            angular.forEach(
                    filterSpacesByVLAN($scope.spaces, vlan), function(space) {
                spaces.push(space);
            });
            $scope.related_spaces = spaces;
            angular.forEach(
                    filterControllersByVLAN($scope.controllers, vlan),
                    function(controller) {
                controllers.push(controller);
            });
            $scope.related_controllers = controllers;
            angular.forEach(
                    filterByVLAN($scope.subnets, vlan), function(subnet) {
                var space = SpacesManager.getItemFromList(subnet.space);
                // XXX mpontillo fabric is redundant here and should
                // probably not be shown.
                var fabric = FabricsManager.getItemFromList(vlan.fabric);
                if(!space) {
                    space = {name: ""};
                }
                if(!fabric) {
                    space = {name: ""};
                }
                var row = {
                    subnet: subnet,
                    space: space,
                    fabric: fabric
                };
                subnets.push(row);
            });
            $scope.related_subnets = subnets;
        }


        // Called when the vlan has been loaded.
        function vlanLoaded(vlan) {
            $scope.vlan = vlan;
            $scope.fabric = FabricsManager.getItemFromList(vlan.fabric);
            $scope.loaded = true;

            updateTitle();
            updateRelatedObjects();
        }

        // Load all the required managers.
        ManagerHelperService.loadManagers([
            VLANsManager, SubnetsManager, SpacesManager, FabricsManager,
            ControllersManager
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
            $scope.$watchCollection("subnets", updateRelatedObjects);
            $scope.$watchCollection("spaces", updateRelatedObjects);
            $scope.$watchCollection("fabrics", updateRelatedObjects);
        });
    }]);
