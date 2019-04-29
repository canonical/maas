/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Controller status icon. Used in the controllers listing on the nodes page.
 */

/* @ngInject */
export function cacheControllerStatus($templateCache) {
  // Inject the controller-status.html into the template cache.
  $templateCache.put(
    "directive/templates/controller-status.html",
    [
      "<span>",
      '<span class="p-icon--{$ serviceClass $}" data-ng-if="!textOnly">',
      "</span>",
      '<span data-ng-if="textOnly" data-ng-bind="serviceText"></span>',
      "</span>"
    ].join("")
  );
}

/* @ngInject */
export function maasControllerStatus(ControllersManager, ServicesManager) {
  return {
    /* @ngInject */
    restrict: "A",
    scope: {
      controller: "=maasControllerStatus",
      textOnly: "=?maasTextOnly"
    },
    templateUrl: "directive/templates/controller-status.html",
    controller: maasControllerStatusController
  };

  /* @ngInject */
  function maasControllerStatusController($scope) {
    $scope.serviceClass = "unknown";
    $scope.services = ServicesManager.getItems();
    $scope.serviceText = "";
    if ($scope.textOnly) {
      $scope.textOnly = true;
    } else {
      $scope.textOnly = false;
    }

    // Return the status class for the service.
    function getClass(service) {
      if (service.status === "running") {
        return "success";
      } else if (service.status === "degraded") {
        return "warning";
      } else if (service.status === "dead") {
        return "error";
      } else {
        return "unknown";
      }
    }

    // Return the number of times class is displayed.
    function countClass(classes, class_name) {
      var counter = 0;
      angular.forEach(classes, function(name) {
        if (name === class_name) {
          counter++;
        }
      });
      return counter;
    }

    // Update the class based on status of the services on the
    // controller.
    function updateStatusClass() {
      $scope.serviceClass = "unknown";
      if (angular.isObject($scope.controller)) {
        var services = ControllersManager.getServices($scope.controller);
        if (services.length > 0) {
          var classes = services.map(getClass);
          if (classes.indexOf("error") !== -1) {
            $scope.serviceClass = "power-error";
            $scope.serviceText = countClass(classes, "error") + " dead";
          } else if (classes.indexOf("warning") !== -1) {
            $scope.serviceClass = "warning";
            $scope.serviceText = countClass(classes, "warning") + " degraded";
          } else {
            $scope.serviceClass = "success";
            $scope.serviceText = countClass(classes, "success") + " running";
          }
        }
      }
    }

    // Watch the services array and the services on the controller,
    // if any changes then update the status.
    $scope.$watch("controller.service_ids", updateStatusClass);
    $scope.$watch("services", updateStatusClass, true);

    // Update on creation.
    updateStatusClass();
  }
}
