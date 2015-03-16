/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Call to action directive.
 */

angular.module('MAAS').run(['$templateCache', function ($templateCache) {
    // Inject the cta.html into the template cache.
    $templateCache.put('directive/templates/cta.html', [
        '<div class="cta-group" data-ng-class="{ secondary: secondary }">',
            '<a class="cta-group__link" data-ng-click="shown=!shown">',
                '{$ getTitle() $}',
            '</a>',
            '<ul class="cta-group__dropdown ng-hide" ',
                'role="menu" data-ng-show="shown">',
                '<li class="cta-group__item" ',
                    'data-ng-repeat="select in maasCta">',
                    '<a data-ng-click="selectItem(select)">',
                        '{$ select.title $}',
                    '</a>',
                '</li>',
            '</ul>',
        '</div>'
    ].join(''));
}]);

angular.module('MAAS').directive('maasCta', function() {
    return {
        restrict: "A",
        replace: true,
        require: "ngModel",
        scope: {
            maasCta: '=',
            ngModel: '='
        },
        templateUrl: 'directive/templates/cta.html',
        link : function(scope, element, attrs, ngModelCtrl) {
            // Use the link function to grab the ngModel controller.

            // Title of the button when not active.
            var defaultTitle = "Take action";
            if(angular.isString(attrs.defaultTitle) &&
                attrs.defaultTitle !== "") {
                defaultTitle = attrs.defaultTitle;
            }

            // When an item is selected in the list set the title, hide the
            // dropdown, and set the value to the given model.
            scope.selectItem = function(select) {
                scope.shown = false;
                ngModelCtrl.$setViewValue(select);
            };

            // Return the title of the dropdown button.
            scope.getTitle = function() {
                if(angular.isObject(ngModelCtrl.$modelValue)) {
                    scope.secondary = true;
                    return ngModelCtrl.$modelValue.title;
                } else {
                    scope.secondary = false;
                    return defaultTitle;
                }
            };

            // When the model changes in the above selectItem function this
            // function will be called causing the ngChange directive to be
            // fired.
            ngModelCtrl.$viewChangeListeners.push(function() {
                scope.$eval(attrs.ngChange);
            });
        },
        controller: function($scope, $rootScope, $element, $document) {
            // Default dropdown is hidden.
            $scope.shown = false;
            $scope.secondary = false;

            // Don't propagate the element click. This stops the click event
            // from firing on the body element.
            $element.bind('click', function (evt) {
                evt.stopPropagation();
            });

            // If a click makes it to the body element then hide the dropdown.
            $document.find('body').bind('click', function () {
                // Use $apply because this function will be called outside
                // of the digest cycle.
                $rootScope.$apply($scope.shown = false);
            });
        }
    };
});
