/* Copyright 2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Navigation directive.
 *
 * Provides the navigation interactions on all screen sizes
 */

function maasNavigationMobile() {
  return {
    restrict: "A",
    link: function(scope, element, attrs) {
      element.on("click", function(e) {
        e.stopPropagation();
        var mobileNavMenu = element
          .parent()
          .parent()
          .find("#mobile-nav-menu");
        mobileNavMenu.toggleClass("u-show");
      });
    }
  };
}

export default maasNavigationMobile;
