/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Domains List Controller
 */

/* @ngInject */
function DomainsListController(
  $scope,
  $rootScope,
  DomainsManager,
  UsersManager,
  ManagerHelperService,
  GeneralManager
) {
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
  $scope.confirmSetDefaultRow = null;

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

  $scope.confirmSetDefault = function(domain) {
    $scope.confirmSetDefaultRow = domain;
  };

  $scope.cancelSetDefault = function() {
    $scope.confirmSetDefaultRow = null;
  };

  $scope.setDefault = function(domain) {
    DomainsManager.setDefault(domain);
    $scope.confirmSetDefaultRow = null;
  };

  ManagerHelperService.loadManagers($scope, [
    DomainsManager,
    UsersManager
  ]).then(function() {
    $scope.loading = false;

    // Set flag for RSD navigation item.
    if (!$rootScope.showRSDLink) {
      GeneralManager.getNavigationOptions().then(
        res => ($rootScope.showRSDLink = res.rsd)
      );
    }
  });
}

export default DomainsListController;
