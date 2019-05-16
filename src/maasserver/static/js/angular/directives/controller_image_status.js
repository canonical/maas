/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Controller image status directive.
 *
 * Shows the image status for a controller.
 */

/* @ngInject */
export function ControllerImageStatusService(
  $timeout,
  $interval,
  ControllersManager
) {
  var self = this;

  // How often to check the sync status of a controller in seconds.
  var CHECK_INTERVAL = 30;

  // List of controllers that need to have the image status updated.
  this.controllers = [];

  // List of current controller statues.
  this.statuses = {};

  // Interval function that is called to update the statuses.
  this.updateStatuses = function() {
    var controllerIds = [];
    angular.forEach(self.controllers, function(system_id) {
      controllerIds.push({ system_id: system_id });
    });

    // Check the image states.
    ControllersManager.checkImageStates(controllerIds).then(function(results) {
      angular.forEach(controllerIds, function(controller) {
        var status = results[controller.system_id];
        if (status) {
          self.statuses[controller.system_id] = status;
        } else {
          self.statuses[controller.system_id] = "Unknown";
        }
      });
    });
  };

  // Register this controller system_id.
  this.register = function(system_id) {
    var known = self.controllers.indexOf(system_id) >= 0;
    if (!known) {
      self.controllers.push(system_id);
    }

    // When the interval is already running and its a new controller then
    // the interval needs to be reset. When it already exists it doesn't
    // need to be reset.
    if (angular.isDefined(self.runningInterval)) {
      if (known) {
        return;
      } else {
        $interval.cancel(self.runningInterval);
        self.runningInterval = undefined;
      }
    }

    // If its not running and the timeout has been started we re-create
    // the timeout. This delays the start of the interval until the
    // all directives on the page have been fully loaded.
    if (angular.isDefined(self.startTimeout)) {
      $timeout.cancel(self.startTimeout);
    }
    self.startTimeout = $timeout(function() {
      self.startTimeout = undefined;
      self.runningInterval = $interval(function() {
        self.updateStatuses();
      }, CHECK_INTERVAL * 1000);
      self.updateStatuses();
    }, 100);
  };

  // Unregister the controller.
  this.unregister = function(system_id) {
    var idx = self.controllers.indexOf(system_id);
    if (idx > -1) {
      self.controllers.splice(idx, 1);
    }

    // If no controllers are left stop all intervals and timeouts.
    if (self.controllers.length === 0) {
      if (angular.isDefined(self.startTimeout)) {
        $timeout.cancel(self.startTimeout);
        self.startTimeout = undefined;
      }
      if (angular.isDefined(self.runningInterval)) {
        $interval.cancel(self.runningInterval);
        self.runningInterval = undefined;
      }
    }
  };

  // Return true if the spinner should be shown.
  this.showSpinner = function(system_id) {
    var status = self.statuses[system_id];
    if (angular.isString(status) && status !== "Syncing") {
      return false;
    } else {
      return true;
    }
  };

  // Get the image status.
  this.getImageStatus = function(system_id) {
    var status = self.statuses[system_id];
    if (angular.isString(status)) {
      return status;
    } else {
      return "Asking for status...";
    }
  };
}

/* @ngInject */
export function maasControllerImageStatus(ControllerImageStatusService) {
  return {
    restrict: "E",
    scope: {
      systemId: "="
    },
    template: [
      '<i class="p-icon--loading u-animation--spin"',
      'data-ng-if="showSpinner()"></i> ',
      "{$ getImageStatus() $}"
    ].join(""),
    link: function(scope) {
      // Don't register until the systemId is set.
      var unwatch,
        registered = false;
      unwatch = scope.$watch("systemId", function() {
        if (angular.isDefined(scope.systemId) && !registered) {
          ControllerImageStatusService.register(scope.systemId);
          registered = true;
          unwatch();
        }
      });

      scope.showSpinner = function() {
        return ControllerImageStatusService.showSpinner(scope.systemId);
      };
      scope.getImageStatus = function() {
        return ControllerImageStatusService.getImageStatus(scope.systemId);
      };

      // Unregister when destroyed.
      scope.$on("$destroy", function() {
        if (registered) {
          ControllerImageStatusService.unregister(scope.systemId);
        }
      });
    }
  };
}
