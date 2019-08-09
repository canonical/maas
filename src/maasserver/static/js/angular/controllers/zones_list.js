/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Zones List Controller
 */

/* @ngInject */
function ZonesListController(
  $scope,
  $rootScope,
  ZonesManager,
  UsersManager,
  ManagerHelperService,
  GeneralManager
) {
  // Set title and page.
  $rootScope.title = "Zones";
  $rootScope.page = "zones";

  // Set initial values.
  $scope.zoneManager = ZonesManager;
  $scope.zones = ZonesManager.getItems();
  $scope.currentpage = "zones";
  $scope.predicate = "name";
  $scope.reverse = false;
  $scope.loading = true;
  $scope.action = {
    open: false,
    obj: {}
  };

  // Open add zone view.
  $scope.addZone = function() {
    $scope.action.open = true;
  };

  // Saving has completed.
  $scope.closeZone = function() {
    $scope.action.open = false;
    $scope.action.obj = {};
  };

  // Return true if the authenticated user is super user.
  $scope.isSuperUser = function() {
    return UsersManager.isSuperUser();
  };

  ManagerHelperService.loadManagers($scope, [ZonesManager, UsersManager]).then(
    function() {
      $scope.loading = false;

      // Set flag for RSD navigation item.
      if (!$rootScope.showRSDLink) {
        GeneralManager.getNavigationOptions().then(
          res => ($rootScope.showRSDLink = res.rsd)
        );
      }
    }
  );
}

export default ZonesListController;
