/* Copyright 2017-2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for script select directive.
 */

import { makeInteger, makeName } from "testing/utils";
import MockWebSocket from "testing/websocket";

import template from "../../../../partials/add-scripts.html";

describe("maasScriptSelect", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Create a new scope before each test.
  var $rootScope, $scope, $q, $templateCache;
  beforeEach(inject(function($injector) {
    $rootScope = $injector.get("$rootScope");
    $scope = $rootScope.$new();
    $q = $injector.get("$q");
    $templateCache = $injector.get("$templateCache");
    $templateCache.put("static/partials/add-scripts.html", template);
  }));

  var ScriptsManager, ManagerHelperService;
  beforeEach(inject(function($injector) {
    ScriptsManager = $injector.get("ScriptsManager");
    ManagerHelperService = $injector.get("ManagerHelperService");
  }));

  // Mock the websocket connection to the region
  var RegionConnection, webSocket;
  beforeEach(inject(function($injector) {
    RegionConnection = $injector.get("RegionConnection");
    // Mock buildSocket so an actual connection is not made.
    webSocket = new MockWebSocket();
    spyOn(RegionConnection, "buildSocket").and.returnValue(webSocket);
  }));

  function makeScript(script_type, tags, for_hardware) {
    const script = {
      id: makeInteger(0, 100),
      name: makeName("script_name"),
      description: makeName("description"),
      script_type: script_type,
      tags: tags,
      for_hardware: for_hardware
    };
    ScriptsManager._items.push(script);
    return script;
  }

  // Return the compiled directive with the items from the scope.
  function compileDirective(script_type, ngModel) {
    var directive;
    var html =
      "<div><span data-maas-script-select " +
      'data-script-type="' +
      script_type +
      '" data-ng-model="' +
      ngModel +
      '"></span></div>';

    // Compile the directive.
    inject(function($compile) {
      directive = $compile(html)($scope);
    });

    // Perform the digest cycle to finish the compile.
    $scope.$digest();
    return directive.find("[data-maas-script-select]");
  }

  it("creates entry for commissioning scripts", function() {
    // Create a commissioning script to be displayed.
    var script = makeScript(0, [], []);
    // Create a commissiong script which uses the for_hardware field
    // which should not be autoselected.
    var for_hardware_script = makeScript(0, [], [makeName("for_hardware")]);
    // Add a test script to ensure its not shown.
    makeScript(2, [], []);
    var defer = $q.defer();
    var spy = spyOn(ManagerHelperService, "loadManager");
    spy.and.returnValue(defer.promise);
    var directive = compileDirective(0, "scripts");
    script.parameters = {};
    defer.resolve();
    $scope.$digest();

    var isolateScope = directive.isolateScope();
    isolateScope.getScripts("");

    // Verify the commissioning script was added and is autoselected.
    expect(isolateScope.ngModel.length).toBe(1);
    expect(isolateScope.ngModel[0].name).toBe(script.name);
    expect(isolateScope.ngModel[0].description).toBe(script.description);
    expect(isolateScope.scripts).toEqual([script, for_hardware_script]);
  });

  it("creates entry for testing scripts", function() {
    // Create a test script for user selection.
    var script = makeScript(2, [], []);
    // Create a test script which uses the for_hardware field
    // which should not be autoselected.
    var for_hardware_script = makeScript(
      2,
      ["commissioning"],
      [makeName("for_hardware")]
    );
    // Create a test script which is autoselected.
    var selected_script = makeScript(2, ["commissioning"], []);
    // Commissioning script which should be ignored
    makeScript(0, [], []);
    var defer = $q.defer();
    var spy = spyOn(ManagerHelperService, "loadManager");
    spy.and.returnValue(defer.promise);
    var directive = compileDirective(2, "selected_scripts");
    selected_script.parameters = {};
    defer.resolve();
    $scope.$digest();

    var isolateScope = directive.isolateScope();
    isolateScope.getScripts("");

    expect(isolateScope.ngModel.length).toBe(1);
    expect(isolateScope.ngModel[0].name).toBe(selected_script.name);
    expect(isolateScope.ngModel[0].description).toBe(
      selected_script.description
    );
    expect(isolateScope.scripts).toEqual([
      script,
      for_hardware_script,
      selected_script
    ]);
  });
});
