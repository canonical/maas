/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Creates the auto-formatting for MAC address inputs.
 */

function macAddress() {
  return {
    restrict: "A",
    require: "ngModel",
    link: function(scope, ele, attr, ngModelCtrl) {
      if (!ngModelCtrl) {
        return;
      }

      var macAddressParse = function(value) {
        return value.toUpperCase();
      };

      var macAddressFormat = function(value) {
        if (!value) {
          return undefined;
        }

        var numbers = value.replace(/:/g, "");

        if (value.length % 3 === 0) {
          return numbers.replace(/([0-9A-Za-z]{2})/g, "$1:");
        }
      };

      ngModelCtrl.$parsers.push(macAddressParse);
      ngModelCtrl.$formatters.push(macAddressFormat);

      ele.on("input", function() {
        var value = macAddressFormat(ele.val());

        if (angular.isDefined(value)) {
          ngModelCtrl.$setViewValue(value);
          ngModelCtrl.$render();
        }
        scope.$apply();
      });
    }
  };
}

export default macAddress;
