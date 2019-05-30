/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for error toggle.
 */

import { makeName } from "testing/utils";

describe("maasErrorToggle", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Get required angular pieces and create a new scope before each test.
  var $scope, $timeout;
  beforeEach(inject(function($rootScope, $injector) {
    $scope = $rootScope.$new();
    $timeout = $injector.get("$timeout");
  }));

  // Load the RegionConnection and ErrorService.
  var ErrorService, RegionConnection;
  beforeEach(inject(function($injector) {
    RegionConnection = $injector.get("RegionConnection");
    ErrorService = $injector.get("ErrorService");
  }));

  // Return the compiled directive.
  function compileDirective() {
    var directive;
    var html = "<div><span data-maas-error-toggle></span></div>";

    // Compile the directive.
    inject(function($compile) {
      directive = $compile(html)($scope);
    });

    // Perform the digest cycle to finish the compile.
    $scope.$digest();
    return directive.find("span");
  }

  it("doesnt hide element instantly if region not connected", function() {
    spyOn(RegionConnection, "isConnected").and.returnValue(false);
    var directive = compileDirective();
    expect(directive.hasClass("ng-hide")).toBe(false);
  });

  it("hides element if region not connected after 1/2 second", function() {
    spyOn(RegionConnection, "isConnected").and.returnValue(false);
    var directive = compileDirective();
    $timeout.flush(500);
    expect(directive.hasClass("ng-hide")).toBe(true);
  });

  it("hides element if error in ErrorService", function() {
    ErrorService._error = makeName("error");
    var directive = compileDirective();
    expect(directive.hasClass("ng-hide")).toBe(true);
  });

  it("shows element if connected and no error", function() {
    spyOn(RegionConnection, "isConnected").and.returnValue(true);
    var directive = compileDirective();
    expect(directive.hasClass("ng-hide")).toBe(false);
  });

  it("shows element if becomes connected", function() {
    var spy = spyOn(RegionConnection, "isConnected");
    spy.and.returnValue(false);
    var directive = compileDirective();
    spy.and.returnValue(true);
    $scope.$digest();
    expect(directive.hasClass("ng-hide")).toBe(false);
  });
});
