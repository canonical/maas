/* Copyright 2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Script expander
 *
 * Expands a scripts content.
 */

function pScriptExpander() {
  return {
    restrict: "C",
    link: function($scope, $element, $attrs) {
      var link = $element.find(".p-script-expander__trigger");
      var target = $element.find(".p-script-expander__content");
      target.addClass("u-hide");

      link.on("click", function(evt) {
        evt.preventDefault();
        target.toggleClass("u-hide");
      });
    }
  };
}

export default pScriptExpander;
