/* Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Window Width.
 *
 * Watches the window width and calculates what the inner width of the window.
 * Applying the attribute window-wdith on the parent element and calling
 * data-ng-if="width > 772" you can use this to hide / show elements for mobile
 * development.
 *
 */

/* @ngInject */
function windowWidth($window) {
  return {
    restrict: "A",
    link: function(scope, element, attrs) {
      scope.windowWidth = $window.innerWidth;
      function onResize() {
        // uncomment for only fire when $window.innerWidth change
        if (scope.windowWidth !== $window.innerWidth) {
          scope.windowWidth = $window.innerWidth;
          scope.$apply(function() {
            scope.message = "Timeout called!";
          });
        }
      }

      function cleanUp() {
        angular.element($window).off("resize", onResize);
      }

      angular.element($window).on("resize", onResize);
      scope.$on("$destroy", cleanUp);
    }
  };
}

export default windowWidth;
