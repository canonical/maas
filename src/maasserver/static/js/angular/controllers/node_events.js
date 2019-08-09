/* Copyright 2015-2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Node Events Controller
 */

/* @ngInject */
function NodeEventsController(
  $scope,
  $rootScope,
  $routeParams,
  $location,
  MachinesManager,
  ControllersManager,
  EventsManagerFactory,
  ManagerHelperService,
  ErrorService,
  GeneralManager
) {
  // Events manager that is loaded once the node is loaded.
  var eventsManager = null;

  // Set the title and page.
  $rootScope.title = "Loading...";

  // Initial values.
  $scope.loaded = false;
  $scope.node = null;
  $scope.events = [];
  $scope.eventsLoaded = false;
  $scope.days = 1;

  // Called once the node is loaded.
  function nodeLoaded(node) {
    $scope.node = node;
    $scope.loaded = true;

    // Get the events manager and load it.
    eventsManager = EventsManagerFactory.getManager(node.id);
    $scope.events = eventsManager.getItems();
    $scope.days = eventsManager.getMaximumDays();
    eventsManager.loadItems().then(function() {
      $scope.eventsLoaded = true;
    });

    // Update the title when the fqdn of the node changes.
    $scope.$watch("node.fqdn", function() {
      $rootScope.title = $scope.node.fqdn + " - events";
    });
  }

  // Return the nice text for the given event.
  $scope.getEventText = function(event) {
    var text = event.type.description;
    if (angular.isString(event.description) && event.description.length > 0) {
      text += " - " + event.description;
    }
    return text;
  };

  // Called to load more events.
  $scope.loadMore = function() {
    $scope.days += 1;
    eventsManager.loadMaximumDays($scope.days);
  };

  if ($location.path().indexOf("/controller") !== -1) {
    $scope.nodesManager = ControllersManager;
    $scope.type_name = "controller";
    $rootScope.page = "controllers";
  } else {
    $scope.nodesManager = MachinesManager;
    $scope.type_name = "machine";
    $rootScope.page = "machines";
  }
  // Load nodes manager.
  ManagerHelperService.loadManager($scope, $scope.nodesManager).then(
    function() {
      // If redirected from the NodeDetailsController then the node
      // will already be active. No need to set it active again.
      var activeNode = $scope.nodesManager.getActiveItem();
      if (
        angular.isObject(activeNode) &&
        activeNode.system_id === $routeParams.system_id
      ) {
        nodeLoaded(activeNode);
      } else {
        $scope.nodesManager.setActiveItem($routeParams.system_id).then(
          function(node) {
            nodeLoaded(node);

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

  // Destroy the events manager when the scope is destroyed. This is so
  // the client will not recieve any more notifications about events
  // for this node.
  $scope.$on("$destroy", function() {
    if (angular.isObject(eventsManager)) {
      eventsManager.destroy();
    }
  });
}

export default NodeEventsController;
