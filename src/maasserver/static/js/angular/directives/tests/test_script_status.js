/* Copyright 2017-2019 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for script status icon select directive.
 */

describe("maasScriptStatus", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Create a new scope before each test.
  var $scope;
  beforeEach(inject(function($rootScope) {
    $scope = $rootScope.$new();
    $scope.scriptStatus = null;
    $scope.icon = null;
  }));

  // Return the compiled directive with the maasScriptStatus from the scope.
  function compileDirective(scriptStatus) {
    var directive;
    var html =
      '<div><span data-maas-script-status="script-status"' +
      'data-script_status="' +
      scriptStatus +
      '"></span></div>';

    // Compile the directive.
    inject(function($compile) {
      directive = $compile(html)($scope);
    });

    // Perform the digest cycle to finish the compile.
    $scope.$digest();
    return directive.find("span");
  }

  it("SCRIPT_STATUS.PENDING", function() {
    var directive = compileDirective("0");
    var select = directive.find("span");
    expect(select.attr("class")).toBe("p-icon--pending");
  });

  it("SCRIPT_STATUS.RUNNING", function() {
    var directive = compileDirective("1");
    var select = directive.find("span");
    expect(select.attr("class")).toBe("p-icon--running");
  });

  it("SCRIPT_STATUS.APPLYING_NETCONF", function() {
    var directive = compileDirective("10");
    var select = directive.find("span");
    expect(select.attr("class")).toBe("p-icon--running");
  });

  it("SCRIPT_STATUS.INSTALLING", function() {
    var directive = compileDirective("7");
    var select = directive.find("span");
    expect(select.attr("class")).toBe("p-icon--running");
  });

  it("SCRIPT_STATUS.PASSED", function() {
    var directive = compileDirective("2");
    var select = directive.find("span");
    expect(select.attr("class")).toBe("p-icon--pass");
  });

  it("SCRIPT_STATUS.FAILED", function() {
    var directive = compileDirective("3");
    var select = directive.find("span");
    expect(select.attr("class")).toBe("p-icon--error");
  });

  it("SCRIPT_STATUS.ABORTED", function() {
    var directive = compileDirective("5");
    var select = directive.find("span");
    expect(select.attr("class")).toBe("p-icon--error");
  });

  it("SCRIPT_STATUS.DEGRADED", function() {
    var directive = compileDirective("6");
    var select = directive.find("span");
    expect(select.attr("class")).toBe("p-icon--error");
  });

  it("SCRIPT_STATUS.FAILED_APPLYING_NETCONF", function() {
    var directive = compileDirective("11");
    var select = directive.find("span");
    expect(select.attr("class")).toBe("p-icon--error");
  });

  it("SCRIPT_STATUS.FAILED_INSTALLING", function() {
    var directive = compileDirective("8");
    var select = directive.find("span");
    expect(select.attr("class")).toBe("p-icon--error");
  });

  it("SCRIPT_STATUS.TIMEDOUT", function() {
    var directive = compileDirective("4");
    var select = directive.find("span");
    expect(select.attr("class")).toBe("p-icon--timed-out");
  });

  it("SCRIPT_STATUS.SKIPPED", function() {
    var directive = compileDirective("9");
    var select = directive.find("span");
    expect(select.attr("class")).toBe("p-icon--warning");
  });

  it("NONE", function() {
    var directive = compileDirective("-1");
    var select = directive.find("span");
    expect(select.attr("context")).toBe(undefined);
  });

  it("UNKNOWN", function() {
    var directive = compileDirective("99");
    var select = directive.find("span");
    expect(select.attr("class")).toBe("p-icon--help");
  });
});
