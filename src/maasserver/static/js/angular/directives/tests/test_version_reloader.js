/* Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for version reloader.
 */

import { makeName } from "testing/utils";
import MockWebSocket from "testing/websocket";

describe("maasVersionReloader", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Grab the needed angular pieces.
  var $q;
  beforeEach(inject(function($injector) {
    $q = $injector.get("$q");
  }));

  // Load the GeneralManager, ManagerHelperService, RegionConnection and
  // mock the websocket connection.
  var GeneralManager, ManagerHelperService, RegionConnection, webSocket;
  beforeEach(inject(function($injector) {
    GeneralManager = $injector.get("GeneralManager");
    RegionConnection = $injector.get("RegionConnection");
    ManagerHelperService = $injector.get("ManagerHelperService");

    // Mock buildSocket so an actual connection is not made.
    webSocket = new MockWebSocket();
    spyOn(RegionConnection, "buildSocket").and.returnValue(webSocket);
  }));

  // Create a new scope before each test.
  var $scope;
  beforeEach(inject(function($rootScope) {
    $scope = $rootScope.$new();
  }));

  // Prevent console.log messages in tests.
  beforeEach(function() {
    spyOn(console, "log");
  });

  // Return the compiled directive with the items from the scope.
  function compileDirective() {
    var directive;
    var html = [
      "<div>",
      "<div data-maas-version-reloader></div>",
      "</div>"
    ].join("");
    // Compile the directive.
    inject(function($compile) {
      directive = $compile(html)($scope);
    });
    // Perform the digest cycle to finish the compile.
    $scope.$digest();
    return directive.find("div[data-maas-version-reloader]");
  }

  it("sets version from GeneralManager", function() {
    compileDirective();
    expect($scope.version).toBe(GeneralManager.getData("version"));
  });

  it("watches version.test onces ManagerHelperService resolves", function() {
    var defer = $q.defer();
    spyOn(ManagerHelperService, "loadManager").and.returnValue(defer.promise);
    compileDirective();
    spyOn($scope, "$watch");

    defer.resolve();
    $scope.$digest();

    expect($scope.$watch.calls.argsFor(0)[0]).toBe("version.text");
  });

  it("calls reloadPage when version.text changes", function() {
    var defer = $q.defer();
    spyOn(ManagerHelperService, "loadManager").and.returnValue(defer.promise);

    compileDirective();
    spyOn($scope, "reloadPage");
    defer.resolve();
    $scope.$digest();

    $scope.version.text = makeName("new");
    $scope.$digest();

    expect($scope.reloadPage).toHaveBeenCalled();
  });
});
