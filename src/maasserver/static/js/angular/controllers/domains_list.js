/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Domains List Controller
 */

angular.module('MAAS').controller('DomainsListController', [
    '$scope', '$rootScope', '$routeParams', '$filter', 'DomainsManager',
    'UsersManager', 'ManagerHelperService',
    function($scope, $rootScope, $routeParams, $filter, DomainsManager,
        UsersManager, ManagerHelperService) {

        // Load the filters that are used inside the controller.

        // Set title and page.
        $rootScope.title = "DNS";
        $rootScope.page = "domains";

        // Set initial values.
        $scope.domains = DomainsManager.getItems();
        $scope.currentpage = "domains";
        $scope.predicate = "name";
        $scope.reverse = false;
        $scope.loading = true;

        // This will hold the AddDomainController once it's initialized.  The
        // controller will set this variable as it's always a child of this
        // scope.
        $scope.addDomainScope = null;

        // Called when the add domain button is pressed.
        $scope.addDomain = function() {
            $scope.addDomainScope.show();
        };

        // Called when the cancel add domain button is pressed.
        $scope.cancelAddDomain = function() {
            $scope.addDomainScope.cancel();
        };

        // Return true if the authenticated user is super user.
        $scope.isSuperUser = function() {
            return UsersManager.isSuperUser();
        };

        ManagerHelperService.loadManagers(
            $scope, [DomainsManager, UsersManager]).then(
            function() {
                $scope.loading = false;
            });
        }
    ]);
