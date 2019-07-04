/* Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for mac address directive.
 */

describe("maasmacAddress", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Create a new scope before each test.
  var $scope;

  beforeEach(inject(function($rootScope, _$window_, _$document_) {
    $scope = $rootScope.$new();
  }));

  // Return the compiled directive with the items from the scope.
  function compileDirective() {
    var directive;
    var html = [
      '<form name="TestForm">',
      '<input type="text"',
      'id="mac"',
      'value=""',
      'name="mac"',
      'maxlength="17"',
      'data-ng-model="mac"',
      'data-ng-pattern="macAddressRegex"',
      "mac-address>",
      "</form>"
    ].join("");

    $scope.mac = "";
    $scope.macAddressRegex = /^([0-9A-F]{2}[::]){5}([0-9A-F]{2})$/gim;

    // Compile the directive.
    inject(function($compile) {
      directive = $compile(html)($scope);
    });

    // Perform the digest cycle to finish the compile.
    $scope.$digest();
    return directive.find("form");
  }

  it("MAC address formatting to be valid", function() {
    compileDirective();
    // set an invalid value
    $scope.TestForm.mac.$setViewValue("00:00:00:00:00:00");
    $scope.$digest();
    expect($scope.TestForm.mac.$valid).toBe(true);
  });

  it("MAC address formatting to be invalid", function() {
    compileDirective();
    // set an invalid value
    $scope.TestForm.mac.$setViewValue('!"#$%^&*(!"#")"');
    $scope.$digest();
    expect($scope.TestForm.mac.$valid).toBe(false);
  });
});
