/* Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Window Width.
 *
 * Watches the window width and calculates what the inner width of the window.
 * Applying the attribute window-wdith on the parent element and calling
 * ng-if="width > 768" you can use this to hide / show elements for mobile
 * development.
 *
 */


angular.module('MAAS').directive('windowWidth', [
    '$window',
    function ($window) {
        return {
            restrict: 'A',
            link: function($scope, element, attrs) {
                $scope.windowWidth = $window.innerWidth;
                angular.element($window).on('resize', function() {
                  if ($scope.windowWidth !== $window.innerWidth) {
                      $scope.$apply(function () {
                          $scope.windowWidth = $window.innerWidth;
                      });
                  }
                });
                $scope.$on('$destroy', function() {
                  angular.element($window).off('resize', onResize);
                });
            }
        };
    }]);
