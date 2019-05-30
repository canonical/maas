/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for placeholder directive.
 */

import { makeName } from "testing/utils";

describe("ngPlaceholder", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Create a new scope before each test.
  var $scope;
  beforeEach(inject(function($rootScope) {
    $scope = $rootScope.$new();
  }));

  // Return the compiled directive with the items from the scope.
  function compileDirective(ngPlaceholder) {
    var directive;
    var html = [
      "<div>",
      '<input ng-placeholder="' + ngPlaceholder + '" />',
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

  it("sets placeholder attribute on input", function() {
    var placeholderText = makeName("placeholder");
    $scope.placeholder = placeholderText;
    var directive = compileDirective("placeholder");
    expect(directive[0].placeholder).toEqual(placeholderText);
  });

  it("sets placeholder attribute on input when changed", function() {
    var placeholderText = makeName("placeholder");
    $scope.placeholder = placeholderText;
    var directive = compileDirective("placeholder");

    // Change the text.
    placeholderText = makeName("placeholder");
    $scope.placeholder = placeholderText;
    $scope.$digest();
    expect(directive[0].placeholder).toEqual(placeholderText);
  });
});
