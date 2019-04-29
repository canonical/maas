/* Copyright 2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Navigation directive.
 *
 * Provides the navigation interactions on all screen sizes
 */

/* @ngInject */
function maasNavigationDropdown($document) {
  return {
    restrict: "A",
    link: function(scope, element, attrs) {
      element.on("click", function(e) {
        e.stopPropagation();
        element
          .parent()
          .find(".p-dropdown__menu")
          .toggleClass("u-hide");
      });

      $document.on("click", function() {
        element
          .parent()
          .find(".p-dropdown__menu")
          .addClass("u-hide");
      });
    }
  };
}

export default maasNavigationDropdown;
