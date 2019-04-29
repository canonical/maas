/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Intro Controller
 */

/* @ngInject */
function IntroController(
  $rootScope,
  $scope,
  $window,
  $location,
  ConfigsManager,
  PackageRepositoriesManager,
  BootResourcesManager,
  ManagerHelperService
) {
  $rootScope.page = "intro";
  $rootScope.title = "Welcome";

  $scope.loading = true;
  $scope.configManager = ConfigsManager;
  $scope.repoManager = PackageRepositoriesManager;
  $scope.bootResources = BootResourcesManager.getData();
  $scope.hasImages = false;
  $scope.maasName = null;
  $scope.upstreamDNS = null;
  $scope.mainArchive = null;
  $scope.portsArchive = null;
  $scope.httpProxy = null;

  // Set the skip function on the rootScope to allow skipping the
  // intro view.
  $rootScope.skip = function() {
    $scope.clickContinue(true);
  };

  // Return true if the welcome section is not in error.
  $scope.welcomeInError = function() {
    var form = $scope.maasName.$maasForm;
    if (angular.isObject(form)) {
      return form.hasErrors();
    } else {
      return false;
    }
  };

  // Return true if the network section is in error.
  $scope.networkInError = function() {
    var inError = false;
    var objs = [
      $scope.upstreamDNS,
      $scope.mainArchive,
      $scope.portsArchive,
      $scope.httpProxy
    ];
    angular.forEach(objs, function(obj) {
      var form = obj.$maasForm;
      if (angular.isObject(form) && form.hasErrors()) {
        inError = true;
      }
    });
    return inError;
  };

  // Return true if continue can be clicked.
  $scope.canContinue = function() {
    return (
      !$scope.welcomeInError() && !$scope.networkInError() && $scope.hasImages
    );
  };

  // Called when continue button is clicked.
  $scope.clickContinue = function(force) {
    if (angular.isUndefined(force)) {
      force = false;
    }
    if (force || $scope.canContinue()) {
      ConfigsManager.updateItem({
        name: "completed_intro",
        value: true
      }).then(function() {
        // Reload the whole page so that the MAAS_config will be
        // set to the new value.
        $window.location.reload();
      });
    }
  };

  // If intro has been completed redirect to '/'.
  if (MAAS_config.completed_intro) {
    $location.path("/");
  } else {
    // Load the required managers.
    var managers = [ConfigsManager, PackageRepositoriesManager];
    ManagerHelperService.loadManagers($scope, managers).then(function() {
      $scope.loading = false;
      $scope.maasName = ConfigsManager.getItemFromList("maas_name");
      $scope.upstreamDNS = ConfigsManager.getItemFromList("upstream_dns");
      $scope.httpProxy = ConfigsManager.getItemFromList("http_proxy");
      $scope.mainArchive = PackageRepositoriesManager.getItems().filter(
        function(repo) {
          return repo["default"] && repo.name === "main_archive";
        }
      )[0];
      $scope.portsArchive = PackageRepositoriesManager.getItems().filter(
        function(repo) {
          return repo["default"] && repo.name === "ports_archive";
        }
      )[0];
    });

    // Don't load the boot resources as the boot-images directive
    // performs that action. Just watch and make sure that
    // at least one resource exists before continuing.
    $scope.$watch("bootResources.resources", function() {
      if (
        angular.isArray($scope.bootResources.resources) &&
        $scope.bootResources.resources.length > 0
      ) {
        $scope.hasImages = true;
      } else {
        $scope.hasImages = false;
      }
    });
  }
}

export default IntroController;
