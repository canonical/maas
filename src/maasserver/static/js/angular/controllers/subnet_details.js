/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Subnet Details Controller
 */

angular.module('MAAS').controller('SubnetDetailsController', [
    '$scope', '$rootScope', '$routeParams', '$filter', '$location',
    'SubnetsManager', 'IPRangesManager', 'ManagerHelperService',
    'ErrorService',
    function(
        $scope, $rootScope, $routeParams, $filter, $location,
        SubnetsManager, IPRangesManager, ManagerHelperService, ErrorService) {

        var filterBySubnet = $filter('filterBySubnet');

        // Set title and page.
        $rootScope.title = "Loading...";

        // Note: this value must match the top-level tab, in order for
        // highlighting to occur properly.
        $rootScope.page = "networks";

        // Initial values.
        $scope.loaded = false;
        $scope.subnet = null;
        $scope.ipranges = IPRangesManager.getItems();
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

        function updateRelatedIPRanges() {
            var subnet = $scope.subnet;
            if(!angular.isObject(subnet)) {
                return;
            }
            $scope.relatedIPRanges = filterBySubnet($scope.ipranges, subnet);
        }

        // Called when the subnet has been loaded.
        function subnetLoaded(subnet) {
            $scope.subnet = subnet;
            $scope.loaded = true;

            updateTitle();
            updateRelatedIPRanges();
        }

        // Load all the required managers.
        ManagerHelperService.loadManagers([
            SubnetsManager, IPRangesManager
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
            $scope.$watchCollection("ipranges", updateRelatedIPRanges);
        });
    }]);
