/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Power parameters directive.
 */

/* @ngInject */
export function cachePowerParameters($templateCache) {
  // Inject the power-parameters.html into the template cache.
  $templateCache.put(
    "directive/templates/power-parameters.html",
    `<div class="p-form__group row">
            <label for="power-type"
                class="p-form__label col-2"
                data-ng-class="{'is-disabled': !ngModel.editing }">
                Power type
            </label>
            <div class="p-form__control col-4">
                <select name="power-type" id="power-type"
                    data-ng-disabled="ngDisabled || ngModel.in_pod"
                    data-ng-class="{ invalid: !ngModel.type }"
                    data-ng-model="ngModel.type"
                    data-ng-options="type as type.description
                        for type in maasPowerParameters track by type.name">
                    <option value="" disabled selected>
                        Select your power type
                    </option>
                </select>
            </div>
        </div>
        <div class="p-form__group row"
            data-ng-repeat="field in ngModel.type.fields"
            data-ng-if="field.name !== 'default_storage_pool'
                && (field.scope !== 'bmc' || !ngModel.in_pod)">
            <label for="{$ field.name $}"
                class="p-form__label col-2"
                data-ng-class="{'is-disabled': !ngModel.editing }">
                {$ field.label $}
            </label>
            <div class="p-form__control col-4">
                <maas-power-input field="field"
                    data-ng-disabled="ngDisabled ||
                        (field.scope === 'bmc' && ngModel.in_pod)"
                    data-ng-model="ngModel.parameters[field.name]">
            </div>
        </div>`
  );
}

/* @ngInject */
export function maasPowerInput($compile) {
  return {
    restrict: "E",
    require: "ngModel",
    scope: {
      field: "=",
      ngModel: "="
    },
    link: function(scope, element, attrs) {
      var type = scope.field.field_type;
      var req = scope.field.required ? 'required="required" ' : "";
      var html = "";
      if (type === "string" || type === "mac_address" || type === "password") {
        // Build an input element with the correct attributes.
        var input_type = 'type="text"';
        if (type === "password") {
          // If the input field is a password field, display it
          // as text or password depending on if we're editing
          // the fields.
          input_type =
            'data-ng-type="ngModel.editing && ' + "'text' || 'password'\"";
        }
        html =
          "<input " +
          input_type +
          " " +
          'name="' +
          scope.field.name +
          '" ' +
          req +
          'data-ng-model="' +
          attrs.ngModel +
          '" ' +
          'data-ng-disabled="' +
          attrs.ngDisabled +
          '" ';

        // Add mac address validation.
        if (type === "mac_address") {
          html +=
            'data-ng-pattern="' + '/^([0-9A-Fa-f]{2}:){5}([0-9A-Fa-f]{2})$/"';
        }
        html += ">";

        // Set the default value for the input on the model.
        if (angular.isUndefined(scope.ngModel)) {
          scope.ngModel = scope.field["default"];
        }
      } else if (type === "choice") {
        // Build a select element with the correct attributes.
        html =
          '<select name="' +
          scope.field.name +
          '"' +
          req +
          'data-ng-model="' +
          attrs.ngModel +
          '" ' +
          'data-ng-disabled="' +
          attrs.ngDisabled +
          '" ' +
          'data-ng-options="' +
          "choice[0] as choice[1] for choice in field.choices" +
          '">';
        html += "</select>";

        // Set the default choice on the model.
        if (angular.isUndefined(scope.ngModel)) {
          if (scope.field["default"]) {
            scope.ngModel = scope.field["default"];
          }
        }
      } else {
        throw new Error("Unknown power_type: " + type);
      }

      // Replace the element with the compiled html using the parents
      // scope. The parent scope is used because we want to build the
      // element as if it was in the parent scope, not the scope that
      // is defined in this directive.
      element.replaceWith($compile(html)(scope.$parent));
    }
  };
}

export function maasPowerParameters() {
  return {
    restrict: "A",
    require: "ngModel",
    scope: {
      maasPowerParameters: "=",
      ngModel: "=",
      ngDisabled: "="
    },
    templateUrl: "directive/templates/power-parameters.html"
  };
}
