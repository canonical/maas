/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for power parameters directive.
 */

import { makeName } from "testing/utils";

describe("maasPowerParameters", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Make field for directive.
  function makeField(name, type, required, defaultValue, choices) {
    if (angular.isUndefined(type)) {
      type = "string";
    }
    if (angular.isUndefined(required)) {
      required = false;
    }
    if (angular.isUndefined(defaultValue)) {
      defaultValue = "";
    }
    if (angular.isUndefined(choices)) {
      choices = [];
    }
    return {
      name: name,
      label: name,
      field_type: type,
      required: required,
      default: defaultValue,
      choices: choices
    };
  }

  // Make power type for directive.
  function makePowerType(name, description, fields) {
    if (angular.isUndefined(fields)) {
      fields = [];
    }
    return {
      name: name,
      description: description,
      fields: fields
    };
  }

  // Create a new scope before each test.
  var $scope;
  beforeEach(inject(function($rootScope) {
    $scope = $rootScope.$new();
  }));

  describe("maas-power-input", function() {
    // Return the compiled directive with the items from the scope.
    function compileDirective(maas_power_input, ng_model, ng_disabled) {
      var directive;
      var html =
        '<div><maas-power-input field="' +
        maas_power_input +
        '" ' +
        'data-ng-model="' +
        ng_model +
        '" ' +
        'data-ng-disabled="' +
        ng_disabled +
        '"></div>';

      // Compile the directive.
      inject(function($compile) {
        directive = $compile(html)($scope);
      });

      // Perform the digest cycle to finish the compile.
      $scope.$digest();
      return directive;
    }

    it("creates input for field_type of string", function() {
      $scope.field = makeField("test", "string");
      var directive = compileDirective("field", "value");
      var input = directive.find("input");
      expect(input.attr("type")).toBe("text");
      expect(input.attr("name")).toBe("test");
      expect(input.attr("data-ng-model")).toBe("value");
    });

    it("creates input with required", function() {
      $scope.field = makeField("test", "string", true);
      var directive = compileDirective("field", "value");
      var input = directive.find("input");
      expect(input.attr("required")).toBe("required");
    });

    it("creates input and sets defaultValue on ng-model", function() {
      var defaultValue = makeName("default");
      $scope.field = makeField("test", "string", false, defaultValue);
      var directive = compileDirective("field", "value");
      var input = directive.find("input");
      expect(input.attr("type")).toBe("text");
      expect($scope.value).toBe(defaultValue);
    });

    it("creates input with ng-pattern for mac address", function() {
      $scope.field = makeField("test", "mac_address");
      var directive = compileDirective("field", "value");
      var input = directive.find("input");
      expect(input.attr("data-ng-pattern")).toBe(
        "/^([0-9A-Fa-f]{2}:){5}([0-9A-Fa-f]{2})$/"
      );
    });

    it("creates select for field_type of choice", function() {
      $scope.field = makeField("test", "choice");
      var directive = compileDirective("field", "value");
      var select = directive.find("select");
      expect(select.attr("name")).toBe("test");
      expect(select.attr("data-ng-model")).toBe("value");
      expect(select.attr("data-ng-options")).toBe(
        "choice[0] as choice[1] for choice in field.choices"
      );
    });

    it("creates select with required", function() {
      $scope.field = makeField("test", "choice", true);
      var directive = compileDirective("field", "value");
      var select = directive.find("select");
      expect(select.attr("required")).toBe("required");
    });

    it("creates select and sets defaultValue on ng-model", function() {
      var choice1 = ["name1", "title1"];
      var choice2 = ["name2", "title2"];
      var choices = [choice1, choice2];
      $scope.field = makeField("test", "choice", false, "name2", choices);
      var directive = compileDirective("field", "value");
      var select = directive.find("select");
      expect(select.attr("name")).toBe("test");
      expect($scope.value).toBe("name2");
    });

    it("creates input with ng-disabled", function() {
      $scope.field = makeField("test", "string");
      $scope.disabled = true;
      var directive = compileDirective("field", "value", "disabled");
      var input = directive.find("input");
      expect(input.attr("data-ng-disabled")).toBe("disabled");
    });

    it("creates select with ng-disabled", function() {
      $scope.field = makeField("test", "choice");
      $scope.disabled = true;
      var directive = compileDirective("field", "value", "disabled");
      var select = directive.find("select");
      expect(select.attr("data-ng-disabled")).toBe("disabled");
    });

    it("creates password for field_type of password", function() {
      $scope.field = makeField("test", "password");
      var directive = compileDirective("field", "value");
      var input = directive.find("input");
      expect(input.attr("name")).toBe("test");
      expect(input.attr("data-ng-model")).toBe("value");
      expect(input.attr("data-ng-type")).toBe(
        "ngModel.editing && 'text' || 'password'"
      );
    });
  });

  describe("maas-power-parameters", function() {
    // Return the compiled directive with the items from the scope.
    function compileDirective(maas_power_parameters, ng_model, ng_disabled) {
      var directive;
      var html =
        "<div><fieldset " +
        'data-maas-power-parameters="' +
        maas_power_parameters +
        '" ' +
        'data-ng-model="' +
        ng_model +
        '" ' +
        'data-ng-disabled="' +
        ng_disabled +
        '"></fieldset></div>';

      // Compile the directive.
      inject(function($compile) {
        directive = $compile(html)($scope);
      });

      // Perform the digest cycle to finish the compile.
      $scope.$digest();
      return directive;
    }

    it("creates select with ng-model, ng-options and ng-disabled", function() {
      var fields = [makeField("test1"), makeField("test2")];
      var powerType = makePowerType("test", "Test Title", fields);
      $scope.powerTypes = [powerType];
      var directive = compileDirective("powerTypes", "value");
      var select = directive.find("select");
      expect(select.attr("data-ng-model")).toBe("ngModel.type");
      expect(select.attr("data-ng-options")).toBe(
        `type as type.description
                        for type in maasPowerParameters track by type.name`
      );
      expect(select.attr("data-ng-disabled")).toBe(
        "ngDisabled || ngModel.in_pod"
      );
    });

    it("creates option with description", function() {
      var fields = [makeField("test1"), makeField("test2")];
      var powerType = makePowerType("test", "Test Title", fields);
      $scope.powerTypes = [powerType];
      var directive = compileDirective("powerTypes", "value");
      var select = directive.find("select");
      var option = select.find('option[value="test"]');
      expect(option.text()).toBe("Test Title");
    });

    it("creates fields on power type select", function() {
      var fields = [makeField("test1"), makeField("test2")];
      var powerType = makePowerType("test", "Test Title", fields);
      $scope.powerTypes = [powerType];
      $scope.power = { type: null, parameters: {} };
      var directive = compileDirective("powerTypes", "power");
      var select = directive.find("select");

      // Set the power type on the select scopes.
      select.scope().ngModel.type = powerType;
      $scope.$digest();

      // Should have the two field show now.
      expect(directive.find("input").length).toBe(2);
    });
  });
});
