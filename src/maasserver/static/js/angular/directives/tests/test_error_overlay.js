/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for error overlay.
 */

import { makeName } from "testing/utils";

describe("maasErrorOverlay", function() {
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
    var html =
      "<div><div data-maas-error-overlay>" +
      '<div id="content"></div>' +
      "</div></div>";

    // Compile the directive.
    inject(function($compile) {
      directive = $compile(html)($scope);
    });

    // Perform the digest cycle to finish the compile.
    $scope.$digest();
    return directive.find("span");
  }

  it("sets connected to value of isConnected", function() {
    spyOn(RegionConnection, "isConnected").and.returnValue(true);
    var directive = compileDirective();
    expect(directive.scope().connected).toBe(true);
  });

  it("sets wasConnected to true once connected", function() {
    spyOn(RegionConnection, "isConnected").and.returnValue(true);
    var directive = compileDirective();
    expect(directive.scope().wasConnected).toBe(true);
  });

  it("keeps wasConnected to true if becomes disconnected", function() {
    var spy = spyOn(RegionConnection, "isConnected");
    spy.and.returnValue(true);
    var directive = compileDirective();
    spy.and.returnValue(false);
    $scope.$digest();
    expect(directive.scope().wasConnected).toBe(true);
  });

  it("keeps clientError to true if error in ErrorService", function() {
    ErrorService._error = makeName("error");
    var directive = compileDirective();
    expect(directive.scope().clientError).toBe(true);
  });

  it("sets error to error in ErrorService", function() {
    var error = makeName("error");
    ErrorService._error = error;
    var directive = compileDirective();
    expect(directive.scope().error).toBe(error);
  });

  it("sets error to error in RegionConnection", function() {
    var error = makeName("error");
    RegionConnection.error = error;
    var directive = compileDirective();
    expect(directive.scope().error).toBe(error);
  });

  it(
    "doesnt sets error to error in RegionConnection if already error in " +
      "ErrorService",
    function() {
      var error = makeName("error");
      ErrorService._error = error;
      RegionConnection.error = makeName("error");
      var directive = compileDirective();
      expect(directive.scope().error).toBe(error);
    }
  );

  describe("show", function() {
    it("returns true if not connected", function() {
      spyOn(RegionConnection, "isConnected").and.returnValue(false);
      var directive = compileDirective();
      expect(directive.scope().show()).toBe(true);
    });

    it("returns true if error in ErrorService", function() {
      ErrorService._error = makeName("error");
      var directive = compileDirective();
      expect(directive.scope().show()).toBe(true);
    });

    it("returns false if connected and no error", function() {
      spyOn(RegionConnection, "isConnected").and.returnValue(true);
      var directive = compileDirective();
      expect(directive.scope().show()).toBe(false);
    });

    it("returns false if disconnected less than 1/2 second", function() {
      var spy = spyOn(RegionConnection, "isConnected");
      spy.and.returnValue(true);
      var directive = compileDirective();
      spy.and.returnValue(false);
      $scope.$digest();
      expect(directive.scope().show()).toBe(false);
    });

    it("returns true if disconnected more than 1/2 second", function() {
      var spy = spyOn(RegionConnection, "isConnected");
      spy.and.returnValue(true);
      var directive = compileDirective();
      spy.and.returnValue(false);
      $scope.$digest();
      $timeout.flush(500);
      expect(directive.scope().show()).toBe(true);
    });
  });

  describe("getTitle", function() {
    it("returns error title", function() {
      ErrorService._error = makeName("error");
      var directive = compileDirective();
      expect(directive.scope().getTitle()).toBe("Error occurred");
    });

    it("returns connection lost error", function() {
      var spy = spyOn(RegionConnection, "isConnected");
      spy.and.returnValue(true);
      var directive = compileDirective();
      spy.and.returnValue(false);
      $scope.$digest();
      expect(directive.scope().getTitle()).toBe(
        "Connection lost, reconnecting..."
      );
    });

    it("returns connecting", function() {
      spyOn(RegionConnection, "isConnected").and.returnValue(false);
      var directive = compileDirective();
      expect(directive.scope().getTitle()).toBe("Connecting...");
    });
  });
});
