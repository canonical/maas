/* Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Call to action directive.
 */

angular.module('MAAS').run(['$templateCache', function ($templateCache) {
    // Inject the cta.html into the template cache.
    $templateCache.put('directive/templates/cta.html', [
      '<div class="p-contextual-menu">',
        '<button ',
          'class="p-button p-contextual-menu__toggle',
          ' p-button--min-margin-bottom" ',
          'aria-controls="#cta-menu" ',
          'aria-expanded="false" ',
          'aria-haspopup="true" ',
          'data-ng-click="shown=!shown"',
        '>',
          '{$ getTitle() $}',
          '<i class="p-icon--chevron on-right"></i>',
        '</button>',
        '<div class="p-contextual-menu__dropdown" ',
          'id="cta-menu" ',
          'aria-hidden="false" ',
          'aria-label="submenu"',
          'data-ng-show="shown"',
        '>',
          '<button ',
            'class="',
              'p-button u-no-margin--left p-contextual-menu__link',
            '" ',
            'data-ng-repeat="select in maasCta" ',
            'data-ng-click="selectItem(select)">',
              '{$ getOptionTitle(select) $}',
          '</button>',
        '</div>',
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
                    option = ngModelCtrl.$modelValue;
                    scope.secondary = true;
                    // Some designs have the requirement that the title of
                    // the menu option change if it is selected.
                    if(angular.isString(option.selectedTitle)) {
                        return option.selectedTitle;
                    }
                    return option.title;
                } else {
                    scope.secondary = false;
                    return defaultTitle;
                }
            };

            // Called to get the title for each option. (Sometimes the title
            // of an option is different when it is selected.)
            scope.getOptionTitle = function(option) {
                if(!scope.secondary) {
                    return option.title;
                } else {
                    if(angular.isString(option.selectedTitle)) {
                        return option.selectedTitle;
                    } else {
                        return option.title;
                    }
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
