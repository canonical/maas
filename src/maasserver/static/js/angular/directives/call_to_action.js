/* Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Call to action directive.
 */

/* @ngInject */
export function cacheCta($templateCache) {
  // Inject the cta.html into the template cache.
  $templateCache.put(
    "directive/templates/cta.html",
    [
      '<div class="p-cta">',
      '<button class="p-cta__toggle u-no-margin--right" ',
      'aria-controls="#cta-menu" ',
      'aria-expanded="false" aria-haspopup="true" ',
      'data-ng-click="shown=!shown" ',
      'data-ng-class="{',
      "'p-button--positive': getTitle() === 'Take action', ",
      "'is-selected': shown}\"",
      ">",
      "{$ getTitle() $}",
      "</button>",
      '<div class="p-cta__dropdown" id="cta-menu" ',
      'aria-hidden="false" aria-label="submenu" ',
      'data-ng-show="shown"',
      ">",
      '<span class="p-cta__group"',
      'data-ng-repeat="type in getActionTypes()">',
      '<button class="p-cta__link" ',
      'data-ng-repeat="select in maasCta | ',
      'filter:{ type: type }" ',
      'data-ng-if="showAction(select)" ',
      'data-ng-click="selectItem(select)" ',
      "data-ng-class=\"{'is-unavailable': ",
      'selectedItems && select.available == 0}"',
      ">",
      "{$ getOptionTitle(select) $}",
      '<div class="p-cta__count" ',
      'data-ng-if="showCount(select)">',
      "<span>{$ select.available $}</span>",
      "</div>",
      "</button>",
      "</span>",
      "</div>",
      "</div>"
    ].join("")
  );
}

export function maasCta() {
  return {
    restrict: "A",
    replace: true,
    require: "ngModel",
    scope: {
      maasCta: "=",
      ngModel: "=",
      selectedItems: "="
    },
    templateUrl: "directive/templates/cta.html",
    link: link,
    controller: CtaController
  };

  /* @ngInject */
  function link(scope, element, attrs, ngModelCtrl) {
    // Use the link function to grab the ngModel controller.

    // Title of the button when not active.
    var defaultTitle = "Take action";
    if (angular.isString(attrs.defaultTitle) && attrs.defaultTitle !== "") {
      defaultTitle = attrs.defaultTitle;
    }

    // When an item is selected in the list set the title, hide the
    // dropdown, and set the value to the given model.
    scope.selectItem = function(action) {
      scope.shown = false;
      ngModelCtrl.$setViewValue(action);
    };

    // Return the title of the dropdown button.
    scope.getTitle = function() {
      if (angular.isObject(ngModelCtrl.$modelValue)) {
        let option = ngModelCtrl.$modelValue;
        scope.secondary = true;
        // Some designs have the requirement that the title of
        // the menu option change if it is selected.
        if (angular.isString(option.selectedTitle)) {
          return option.selectedTitle;
        }
        return option.title;
      } else {
        scope.secondary = false;
        return defaultTitle;
      }
    };

    // Opens the test dialog
    scope.$on("validate", (e, action) => {
      scope.selectItem(action);
    });

    // Called to get the title for each option. (Sometimes the title
    // of an option is different when it is selected.)
    scope.getOptionTitle = function(option) {
      if (!scope.secondary) {
        return option.title;
      } else {
        if (angular.isString(option.selectedTitle)) {
          return option.selectedTitle;
        } else {
          return option.title;
        }
      }
    };

    scope.getActionTypes = function() {
      var actions = scope.maasCta || [];
      var types = [];
      actions.forEach(function(action) {
        if (types.indexOf(action.type) === -1) {
          types.push(action.type);
        }
      });

      return types;
    };

    scope.showAction = function(action) {
      return !(
        scope.selectedItems &&
        action.available === 0 &&
        action.type !== "lifecycle"
      );
    };

    scope.showCount = function(action) {
      return scope.selectedItems > 1 && action.available > 0;
    };

    // When the model changes in the above selectItem function this
    // function will be called causing the ngChange directive to be
    // fired.
    ngModelCtrl.$viewChangeListeners.push(function() {
      scope.$eval(attrs.ngChange);
    });
  }

  /* @ngInject */
  function CtaController($scope, $rootScope, $element, $document) {
    // Default dropdown is hidden.
    $scope.shown = false;
    $scope.secondary = false;

    // Don't propagate the element click. This stops the click event
    // from firing on the body element.
    $element.bind("click", function(evt) {
      evt.stopPropagation();
    });

    // If a click makes it to the body element then hide the dropdown.
    $document.find("body").bind("click", function() {
      // Use $apply because this function will be called outside
      // of the digest cycle.
      $rootScope.$apply(($scope.shown = false));
    });
  }
}
