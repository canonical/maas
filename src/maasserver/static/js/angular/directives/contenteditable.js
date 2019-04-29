/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Content editable directive.
 *
 * HTML provides a feature that allows any element to be editable with
 * contenteditable attribute. This directive uses that attribute to link
 * the contents of that element to a model. This directive is not prefixed
 * with maas so Angular can identify all elements with this attribute.
 */

function contenteditable() {
  return {
    restrict: "A",
    require: "ngModel",
    scope: {
      ngDisabled: "&",
      maasEditing: "&"
    },
    link: function(scope, element, attrs, ngModel) {
      // If the element is disabled then make the element lose focus.
      var focusHandler = function() {
        if (scope.ngDisabled()) {
          element.blur();
        } else {
          // Didn't lose focus, so its now editing.
          scope.$apply(scope.maasEditing());
        }
      };
      element.bind("focus", focusHandler);

      // Update the value of the model when events occur that
      // can change the value of the model.
      var changeHandler = function() {
        scope.$apply(ngModel.$setViewValue(element.text()));
      };
      element.bind("blur keyup change", changeHandler);

      // When the model changes set the html content for that element.
      ngModel.$render = function() {
        element.html(ngModel.$viewValue || "");
      };

      // When the model changes this function will be called causing the
      // ngChange directive to be fired.
      ngModel.$viewChangeListeners.push(function() {
        scope.$eval(attrs.ngChange);
      });

      // Remove the event handler on the element when the scope is
      // destroyed.
      scope.$on("$destroy", function() {
        element.unbind("blur keyup change", changeHandler);
        element.unbind("focus", focusHandler);
      });
    }
  };
}

export default contenteditable;
