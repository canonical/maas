/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Placeholder directive.
 *
 * Allows the placeholder attribute on an element to be dynamic.
 */


angular.module('MAAS').directive('ngPlaceholder', function() {
    return {
        restrict: "A",
        scope: {
            ngPlaceholder: "="
        },
        link: function(scope, element, attrs) {
            scope.$watch('ngPlaceholder', function() {
                element[0].placeholder = scope.ngPlaceholder;
            });
        }
    };
});
