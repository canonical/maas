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

function maasCodeLines() {
  return {
    restrict: "A",
    scope: {
      maasCodeLines: "&"
    },
    link: function(scope, element) {
      function insertContent() {
        // Empty the element contents and include again, this assures
        // its the most up-to-date content
        element.empty();
        element.text(scope.maasCodeLines);

        // Count the line contents
        var lines = element.html().split("\n"),
          newLine = "",
          insert = "<code>";

        // Each line is to be wrapped by a span which is style & given
        // its appropriate line number
        angular.forEach(lines, function(line) {
          insert +=
            newLine + '<span class="p-code-numbered__line">' + line + "</span>";
        });
        insert += "</code>";

        // Re-insert the contents
        element.html(insert);
      }

      // Watch the contents of the element so when it changes to
      // re-add the line numbers.
      scope.$watch(scope.maasCodeLines, insertContent);
    }
  };
}

export default maasCodeLines;
