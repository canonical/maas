/* Copyright 2015,2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Domains List Controller
 */

angular.module('MAAS').controller('DomainsListController', [
    '$scope', '$rootScope', '$routeParams', '$filter', 'DomainsManager',
    'ManagerHelperService',
    function($scope, $rootScope, $routeParams, $filter, DomainsManager,
        ManagerHelperService) {

        // Load the filters that are used inside the controller.

        // Set title and page.
        $rootScope.title = "Domains";
        $rootScope.page = "domains";

        // Set initial values.
        $scope.domains = DomainsManager.getItems();
        $scope.currentpage = "domains";
        $scope.predicate = "name";
        $scope.reverse = false;
        $scope.loading = true;

        ManagerHelperService.loadManagers([DomainsManager]).then(
            function() {
                $scope.loading = false;
            });

        }
    ]);
