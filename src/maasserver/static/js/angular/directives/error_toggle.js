/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Error toggle.
 *
 * Hides the element if an error occurs or no connection to the region
 * is present.
 */

/* @ngInject */
function maasErrorToggle($timeout, RegionConnection, ErrorService) {
  return {
    restrict: "A",
    link: function(scope, element, attrs) {
      // Holds timeout promise for setting ng-hide when
      // connection is lost.
      var disconnectedPromise;

      // Cancel the disconnected timeout.
      var cancelTimeout = function() {
        if (angular.isDefined(disconnectedPromise)) {
          $timeout.cancel(disconnectedPromise);
          disconnectedPromise = undefined;
        }
      };

      // Called to when the connection status of the region
      // changes or the error on the ErrorService is set.
      // The element is shown when connected and no errors.
      var watchConnectionAndError = function() {
        var connected = RegionConnection.isConnected();
        var error = ErrorService._error;
        if (connected && !angular.isString(error)) {
          cancelTimeout();
          element.removeClass("ng-hide");
        } else if (angular.isString(error)) {
          cancelTimeout();
          element.addClass("ng-hide");
        } else if (!connected) {
          // Hide the element after 1/2 second. This stops
          // flickering when the connection goes down and
          // reconnects quickly.
          cancelTimeout();
          disconnectedPromise = $timeout(function() {
            element.addClass("ng-hide");
          }, 500);
        }
      };

      // Watch the RegionConnection.isConnected() and
      // ErrorService._error value.
      scope.$watch(function() {
        return RegionConnection.isConnected();
      }, watchConnectionAndError);
      scope.$watch(function() {
        return ErrorService._error;
      }, watchConnectionAndError);

      // Cancel disconnect timeout on destroy.
      scope.$on("$destroy", function() {
        cancelTimeout();
      });
    }
  };
}

export default maasErrorToggle;
