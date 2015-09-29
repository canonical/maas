/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Subnets List Controller
 */

angular.module('MAAS').controller('SubnetsListController', [
    '$scope', '$rootScope', '$routeParams', 'SubnetsManager', 'FabricsManager',
    'SpacesManager', 'VLANsManager', 'ManagerHelperService',
    function($scope, $rootScope, $routeParams, SubnetsManager, FabricsManager,
        SpacesManager, VLANsManager, ManagerHelperService) {

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

        // Spaces tab.
        $scope.tabs.spaces = {};
        $scope.tabs.spaces.pagetitle = "Spaces";
        $scope.tabs.spaces.currentpage = "spaces";

        // Toggles between the current tab.
        $scope.toggleTab = function(tab) {
            $rootScope.title = $scope.tabs[tab].pagetitle;
            $scope.currentpage = tab;
        };

        ManagerHelperService.loadManagers([
            SubnetsManager, FabricsManager, SpacesManager, VLANsManager]).then(
            function() {
                $scope.loading = false;
            });

        // Switch to the specified tab, if specified.
        if($routeParams.tab === "fabrics" || $routeParams.tab === "spaces") {
            $scope.toggleTab($routeParams.tab);
        }
    }]);
