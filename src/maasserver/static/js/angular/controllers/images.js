/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Images Controller
 */

/* @ngInject */
function ImagesController(
  $rootScope,
  $scope,
  BootResourcesManager,
  ConfigsManager,
  UsersManager,
  ManagerHelperService,
  GeneralManager
) {
  $rootScope.page = "images";
  $rootScope.title = "Loading...";

  $scope.loading = true;
  $scope.bootResources = BootResourcesManager.getData();
  $scope.configManager = ConfigsManager;
  $scope.autoImport = null;

  // Return true if the user is a super user.
  $scope.isSuperUser = function() {
    return UsersManager.isSuperUser();
  };

  // Load the required managers.
  ManagerHelperService.loadManagers($scope, [
    ConfigsManager,
    UsersManager
  ]).then(function() {
    $scope.autoImport = ConfigsManager.getItemFromList(
      "boot_images_auto_import"
    );
  });

  // The boot-images directive will load the bootResources manager,
  // we just watch until resources is set. That means the page is
  // loaded.
  $scope.$watch("bootResources.resources", function() {
    if (angular.isArray($scope.bootResources.resources)) {
      $scope.loading = false;
      $rootScope.title = "Images";

      // Set flag for RSD navigation item.
      if (!$rootScope.showRSDLink) {
        GeneralManager.getNavigationOptions().then(
          res => ($rootScope.showRSDLink = res.rsd)
        );
      }
    }
  });
}

export default ImagesController;
