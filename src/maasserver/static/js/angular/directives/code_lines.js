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

        const lines = element.html().split("\n");
        let insert = "";
        let newLine = "";

        // Add copy button
        insert +=
          "<button " +
          'class="p-code-numbered__copy-button p-button has-icon" ' +
          '><i class="p-icon--copy">Copy</i></button>';

        // Each line is to be wrapped by a span which is style & given
        // its appropriate line number
        insert += "<code>";
        lines.forEach(
          line =>
            (insert +=
              newLine +
              '<span class="p-code-numbered__line">' +
              line +
              "</span>")
        );
        insert += "</code>";

        // Re-insert the contents
        element.html(insert);
      }

      scope.copyToClipboard = () => {
        const el = document.createElement("textarea");
        el.value = scope.maasCodeLines();
        document.body.appendChild(el);
        el.select();
        document.execCommand("copy");
        document.body.removeChild(el);
      };

      // Watch the contents of the element so when it changes to
      // re-add the line numbers.
      scope.$watch(scope.maasCodeLines, () => {
        insertContent();
        element
          .find(".p-code-numbered__copy-button")
          .bind("click", scope.copyToClipboard);
      });

      // Remove the handlers when the scope is destroyed.
      scope.$on("$destroy", () => {
        element
          .find(".p-code-numbered__copy-button")
          .off("click", scope.copyToClipboard);
      });
    }
  };
}

export default maasCodeLines;
