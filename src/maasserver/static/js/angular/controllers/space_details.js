/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Space Details Controller
 */

/* @ngInject */
function SpaceDetailsController(
  $scope,
  $rootScope,
  $routeParams,
  $filter,
  $location,
  SpacesManager,
  VLANsManager,
  SubnetsManager,
  FabricsManager,
  UsersManager,
  ManagerHelperService,
  ErrorService
) {
  // Set title and page.
  $rootScope.title = "Loading...";

  // Note: this value must match the top-level tab, in order for
  // highlighting to occur properly.
  $rootScope.page = "networks";

  // Initial values.
  $scope.space = null;
  $scope.spaceManager = SpacesManager;
  $scope.subnets = SubnetsManager.getItems();
  $scope.loaded = false;
  $scope.editSummary = false;

  // Updates the page title.
  function updateTitle() {
    $rootScope.title = $scope.space.name;
  }

  // Called when the space has been loaded.
  function spaceLoaded(space) {
    $scope.space = space;
    updateTitle();
    $scope.predicate = "[subnet_name, vlan_name]";
    $scope.$watch("subnets", updateSubnets, true);
    updateSubnets();
    $scope.loaded = true;
  }

  // Generate a table that can easily be rendered in the view.
  function updateSubnets() {
    var rows = [];
    angular.forEach(
      $filter("filter")($scope.subnets, { space: $scope.space.id }, true),
      function(subnet) {
        var vlan = VLANsManager.getItemFromList(subnet.vlan);
        var fabric = FabricsManager.getItemFromList(vlan.fabric);
        var row = {
          vlan: vlan,
          vlan_name: VLANsManager.getName(vlan),
          subnet: subnet,
          subnet_name: SubnetsManager.getName(subnet),
          fabric: fabric,
          fabric_name: fabric.name
        };
        rows.push(row);
      }
    );
    $scope.rows = rows;
  }

  // Return true if the authenticated user is super user.
  $scope.isSuperUser = function() {
    return UsersManager.isSuperUser();
  };

  // Called when the "edit" button is cliked in the space summary
  $scope.enterEditSummary = function() {
    $scope.editSummary = true;
  };

  // Called when the "cancel" button is cliked in the space summary
  $scope.exitEditSummary = function() {
    $scope.editSummary = false;
  };

  // Return true if this is the default Space
  $scope.isDefaultSpace = function() {
    if (!angular.isObject($scope.space)) {
      return false;
    }
    return $scope.space.id === 0;
  };

  // Called to check if the space can be deleted.
  $scope.canBeDeleted = function() {
    if (angular.isObject($scope.space)) {
      return $scope.space.subnet_ids.length === 0;
    }
    return false;
  };

  // Called when the delete space button is pressed.
  $scope.deleteButton = function() {
    $scope.error = null;
    $scope.confirmingDelete = true;
  };

  // Called when the cancel delete space button is pressed.
  $scope.cancelDeleteButton = function() {
    $scope.confirmingDelete = false;
  };

  // Called when the confirm delete space button is pressed.
  $scope.deleteConfirmButton = function() {
    SpacesManager.deleteSpace($scope.space).then(
      function() {
        $scope.confirmingDelete = false;
        $location.path("/networks");
        $location.search("by", "space");
      },
      function(error) {
        $scope.error = ManagerHelperService.parseValidationError(error);
      }
    );
  };

  // Load all the required managers.
  ManagerHelperService.loadManagers($scope, [
    SpacesManager,
    SubnetsManager,
    VLANsManager,
    FabricsManager,
    UsersManager
  ]).then(function() {
    // Possibly redirected from another controller that already had
    // this space set to active. Only call setActiveItem if not
    // already the activeItem.
    var activeSpace = SpacesManager.getActiveItem();
    var requestedSpace = parseInt($routeParams.space_id, 10);
    if (isNaN(requestedSpace)) {
      ErrorService.raiseError("Invalid space identifier.");
    } else if (
      angular.isObject(activeSpace) &&
      activeSpace.id === requestedSpace
    ) {
      spaceLoaded(activeSpace);
    } else {
      SpacesManager.setActiveItem(requestedSpace).then(
        function(space) {
          spaceLoaded(space);
        },
        function(error) {
          ErrorService.raiseError(error);
        }
      );
    }
  });
}

export default SpaceDetailsController;
