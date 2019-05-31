/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for type directive.
 */

import { makeName } from "testing/utils";

describe("ngType", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Create a new scope before each test.
  var $scope;
  beforeEach(inject(function($rootScope) {
    $scope = $rootScope.$new();
  }));

  // Return the compiled directive with the items from the scope.
  function compileDirective(ngType) {
    var directive;
    var html = [
      "<div>",
      '<input data-ng-type="' + ngType + '" />',
      "</div>"
    ].join("");
    // Compile the directive.
    inject(function($compile) {
      directive = $compile(html)($scope);
    });
    // Perform the digest cycle to finish the compile.
    $scope.$digest();
    return directive.find("input");
  }

  it("sets type attribute on input", function() {
    var type = "text";
    $scope.type = type;
    var directive = compileDirective("type");
    expect(directive[0].type).toEqual(type);
  });

  it("sets type attribute on input when changed", function() {
    var type = "text";
    $scope.type = type;
    var directive = compileDirective("type");
    // Change the type.
    type = "password";
    $scope.type = type;
    $scope.$digest();
    expect(directive[0].type).toEqual(type);
  });

  it("rejects invalid input type", function() {
    var type = "text";
    $scope.type = type;
    compileDirective("type");
    // Change the type to something invalid.
    type = makeName("type");
    $scope.type = type;
    expect(function() {
      $scope.$digest();
    }).toThrow(new Error("Invalid input type: " + type));
  });
});
