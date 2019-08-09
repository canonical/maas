/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Zone Details Controller
 */

/* @ngInject */
function ZoneDetailsController(
  $scope,
  $rootScope,
  $routeParams,
  $location,
  ZonesManager,
  UsersManager,
  ManagerHelperService,
  ErrorService,
  GeneralManager
) {
  // Set title and page.
  $rootScope.title = "Loading...";

  // Note: this value must match the top-level tab, in order for
  // highlighting to occur properly.
  $rootScope.page = "zones";

  // Initial values.
  $scope.loaded = false;
  $scope.zone = null;
  $scope.zoneManager = ZonesManager;
  $scope.editSummary = false;
  $scope.predicate = "name";
  $scope.reverse = false;

  // Updates the page title.
  function updateTitle() {
    $rootScope.title = $scope.zone.name;
  }

  // Called when the zone has been loaded.
  function zoneLoaded(zone) {
    $scope.zone = zone;
    $scope.loaded = true;
    updateTitle();
  }

  // Called when the "edit" button is cliked in the zone summary
  $scope.enterEditSummary = function() {
    $scope.editSummary = true;
  };

  // Called when the "cancel" button is cliked in the zone summary
  $scope.exitEditSummary = function() {
    $scope.editSummary = false;
  };

  // Return true if the authenticated user is super user.
  $scope.isSuperUser = function() {
    return UsersManager.isSuperUser();
  };

  // Return true if this is the default zone.
  $scope.isDefaultZone = function() {
    if (angular.isObject($scope.zone)) {
      return $scope.zone.id === 1;
    }
    return false;
  };

  // Called to check if the zone can be deleted.
  $scope.canBeDeleted = function() {
    if (angular.isObject($scope.zone)) {
      return $scope.zone.id !== 0;
    }
    return false;
  };

  // Called when the delete zone button is pressed.
  $scope.deleteButton = function() {
    $scope.error = null;
    $scope.confirmingDelete = true;
  };

  // Called when the cancel delete zone button is pressed.
  $scope.cancelDeleteButton = function() {
    $scope.confirmingDelete = false;
  };

  // Called when the confirm delete space button is pressed.
  $scope.deleteConfirmButton = function() {
    ZonesManager.deleteItem($scope.zone).then(
      function() {
        $scope.confirmingDelete = false;
        $location.path("/zones");
      },
      function(error) {
        $scope.error = ManagerHelperService.parseValidationError(error);
      }
    );
  };

  // Load all the required managers.
  ManagerHelperService.loadManagers($scope, [ZonesManager, UsersManager]).then(
    function() {
      // Possibly redirected from another controller that already had
      // this zone set to active. Only call setActiveItem if not
      // already the activeItem.
      var activeZone = ZonesManager.getActiveItem();
      var requestedZone = parseInt($routeParams.zone_id, 10);
      if (isNaN(requestedZone)) {
        ErrorService.raiseError("Invalid zone identifier.");
      } else if (
        angular.isObject(activeZone) &&
        activeZone.id === requestedZone
      ) {
        zoneLoaded(activeZone);
      } else {
        ZonesManager.setActiveItem(requestedZone).then(
          function(zone) {
            zoneLoaded(zone);

            // Set flag for RSD navigation item.
            if (!$rootScope.showRSDLink) {
              GeneralManager.getNavigationOptions().then(
                res => ($rootScope.showRSDLink = res.rsd)
              );
            }
          },
          function(error) {
            ErrorService.raiseError(error);
          }
        );
      }
    }
  );
}

export default ZoneDetailsController;
