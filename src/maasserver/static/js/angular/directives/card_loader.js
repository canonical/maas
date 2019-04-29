/* Copyright 2017 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Controller status icon. Used in the controllers listing on the nodes page.
 */

/* @ngInject */
function maasCardLoader($compile) {
  return {
    restrict: "A",
    link: function(scope, element, attrs) {
      var templateUrl =
        "static/partials/cards/" +
        attrs.maasCardLoader +
        (".html?v=" + MAAS_config.files_version);
      var include = "<ng-include src=\"'" + templateUrl + "'\"></ng-include>";
      element.html(include);
      $compile(element.contents())(scope);
    }
  };
}

export default maasCardLoader;
