/* Copyright 2017 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 */

function maasEnter() {
  return {
    restrict: "A",
    link: function(scope, element, attrs) {
      element.bind("keydown keypress", function(evt) {
        if (evt.which === 13) {
          scope.$apply(function() {
            scope.$eval(attrs.maasEnter);
          });
          evt.preventDefault();
        }
      });
    }
  };
}

export default maasEnter;
