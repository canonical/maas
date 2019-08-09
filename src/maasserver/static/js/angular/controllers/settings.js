/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Settings Controller
 */

/* @ngInject */
function SettingsController(
  $scope,
  $rootScope,
  $routeParams,
  PackageRepositoriesManager,
  DHCPSnippetsManager,
  MachinesManager,
  ControllersManager,
  DevicesManager,
  SubnetsManager,
  GeneralManager,
  ManagerHelperService
) {
  // Set the title and page.
  $rootScope.title = "Loading...";
  $rootScope.page = "settings";

  // Initial values.
  $scope.loading = true;
  $scope.snippets = DHCPSnippetsManager.getItems();
  $scope.subnets = SubnetsManager.getItems();
  $scope.machines = MachinesManager.getItems();
  $scope.devices = DevicesManager.getItems();
  $scope.controllers = ControllersManager.getItems();
  $scope.known_architectures = GeneralManager.getData("known_architectures");
  $scope.pockets_to_disable = GeneralManager.getData("pockets_to_disable");
  $scope.components_to_disable = GeneralManager.getData(
    "components_to_disable"
  );
  $scope.packageRepositoriesManager = PackageRepositoriesManager;
  $scope.repositories = PackageRepositoriesManager.getItems();
  $scope.newRepository = null;
  $scope.editRepository = null;
  $scope.deleteRepository = null;

  // Called when the enabled toggle is changed.
  $scope.repositoryEnabledToggle = function(repository) {
    PackageRepositoriesManager.updateItem(repository);
  };

  // Called to enter remove mode for a repository.
  $scope.repositoryEnterRemove = function(repository) {
    $scope.newRepository = null;
    $scope.editRepository = null;
    $scope.deleteRepository = repository;
  };

  // Called to exit remove mode for a repository.
  $scope.repositoryExitRemove = function() {
    $scope.deleteRepository = null;
  };

  // Called to confirm the removal of a repository.
  $scope.repositoryConfirmRemove = function() {
    PackageRepositoriesManager.deleteItem($scope.deleteRepository).then(
      function() {
        $scope.repositoryExitRemove();
      }
    );
  };

  // Return true if the repository is a PPA.
  $scope.isPPA = function(data) {
    if (!angular.isObject(data)) {
      return false;
    }
    if (!angular.isString(data.url)) {
      return false;
    }
    return (
      data.url.indexOf("ppa:") === 0 ||
      data.url.indexOf("ppa.launchpad.net") > -1
    );
  };

  // Return true if the repository is a mirror.
  $scope.isMirror = function(data) {
    if (!angular.isObject(data)) {
      return false;
    }
    if (!angular.isString(data.name)) {
      return false;
    }
    return data.name === "main_archive" || data.name === "ports_archive";
  };

  // Called to enter edit mode for a repository.
  $scope.repositoryEnterEdit = function(repository) {
    $scope.newRepository = null;
    $scope.deleteRepository = null;
    $scope.editRepository = repository;
  };

  // Called to exit edit mode for a repository.
  $scope.repositoryExitEdit = function() {
    $scope.editRepository = null;
  };

  // Called to start adding a new repository.
  $scope.repositoryAdd = function(isPPA) {
    var repo = {
      name: "",
      enabled: true,
      url: "",
      key: "",
      arches: ["i386", "amd64"],
      distributions: [],
      components: []
    };
    if (isPPA) {
      repo.url = "ppa:";
    }
    $scope.newRepository = repo;
  };

  // Called to cancel addind a new repository.
  $scope.repositoryAddCancel = function() {
    $scope.newRepository = null;
  };

  // Setup page variables based on section.
  if ($routeParams.section === "dhcp") {
    $rootScope.title = "DHCP snippets";
    $scope.currentpage = "dhcp";
  } else if ($routeParams.section === "repositories") {
    $rootScope.title = "Package repositories";
    $scope.currentpage = "repositories";
  }

  // Load the required managers.
  ManagerHelperService.loadManagers($scope, [
    PackageRepositoriesManager,
    DHCPSnippetsManager,
    MachinesManager,
    DevicesManager,
    ControllersManager,
    SubnetsManager,
    GeneralManager
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

export default SettingsController;
