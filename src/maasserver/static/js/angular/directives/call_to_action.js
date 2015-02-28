/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Call to action directive.
 */

angular.module('MAAS').run(['$templateCache', function ($templateCache) {
    // Inject the cta.html into the template cache.
    $templateCache.put('directive/templates/cta.html', [
        '<div class="cta-group" data-ng-class="{ secondary: secondary }">',
            '<a class="cta-group__link" data-ng-click="buttonClick()">',
                '{$ getTitle() $}',
            '</a>',
            '<a class="cta-group__link--toggle" ',
                'aria-expanded="false" data-ng-click="shown=!shown">',
                '<span class="chevron"></span>',
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
            keepOrange: '@',
            ngModel: '='
        },
        templateUrl: 'directive/templates/cta.html',
        link : function(scope, element, attrs, ngModelCtrl) {
            // Use the link function to grab the ngModel controller.

            // keepOrange will stop the secondary class from being applied.
            function keepOrange() {
                if(angular.isUndefined(scope.keepOrange)) {
                    return false;
                }
                if(angular.isString(scope.keepOrange)) {
                    if(scope.keepOrange === "true") {
                        return true;
                    } else {
                        return false;
                    }
                }
                return scope.keepOrange;
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
                    if(keepOrange()) {
                        scope.secondary = false;
                    } else {
                        scope.secondary = true;
                    }
                    return ngModelCtrl.$modelValue.title;
                } else {
                    scope.secondary = false;
                    return "Take action";
                }
            };

            // Called only when the button is clicked not the toggle.
            scope.buttonClick = function() {
                if(!angular.isObject(ngModelCtrl.$modelValue)) {
                    // Show the dropdown if no option is currently selected.
                    scope.shown = !scope.shown;
                } else if(scope.shown) {
                    // Now that option is selected and its show, clicking it
                    // again will hide it.
                    scope.shown = false;
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

            // Don't propagate the click of the toggle. This stops the ngClick
            // from firing on the toggle button.
            $element.find('a.cta-group__link--toggle').bind('click',
                function(evt) {
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
