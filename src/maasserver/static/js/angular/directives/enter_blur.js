/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Enter blur directive.
 *
 * When the enter key is pressed make the element lose focus (aka. blur event).
 */

function maasEnterBlur() {
  return {
    restrict: "A",
    link: function(scope, element, attrs) {
      element.bind("keydown keypress", function(evt) {
        if (evt.which === 13) {
          element.blur();
          evt.preventDefault();
        }
      });
    }
  };
}

export default maasEnterBlur;
