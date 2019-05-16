/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Accordion directive.
 *
 * Provides an accordion effect to an element with maas-accordion class and
 * all child elements with maas-accordion-tab. Only one accordion tab is open
 * at a time, selecting another accordion will set "active" on that
 * accordion tab.
 */

function maasAccordion() {
  return {
    restrict: "C",
    link: function(scope, element) {
      // Called when accordion tabs are clicked. Removes active on
      // all other tabs except to the tab that was clicked.
      var clickHandler = function(evt) {
        var tab = evt.data.tab;
        angular.element(tab).toggleClass("is-selected");
      };

      // Listen for the click event on all tabs in the accordion.
      var tabs = element.find(".maas-accordion-tab");
      angular.forEach(tabs, function(tab) {
        tab = angular.element(tab);
        tab.on(
          "click",
          {
            tab: tab
          },
          clickHandler
        );
      });

      // Remove the handlers when the scope is destroyed.
      scope.$on("$destroy", function() {
        angular.forEach(tabs, function(tab) {
          angular.element(tab).off("click", clickHandler);
        });
      });
    }
  };
}

export default maasAccordion;
