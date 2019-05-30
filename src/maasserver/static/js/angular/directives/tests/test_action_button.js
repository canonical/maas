/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for action button directive.
 */

describe("maasActionButton", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Create a new scope before each test. Not used in this test, but
  // required to compile the directive.
  var $scope;
  beforeEach(inject(function($rootScope) {
    $scope = $rootScope.$new();
  }));

  // Return the compiled directive with the items from the scope.
  function compileDirective(scope) {
    var directive;
    var html = [
      "<div>",
      "<maas-action-button ",
      "indeterminate-state=" + scope.indeterminateState + " ",
      "done-state=" + scope.doneState + ">",
      "Action",
      "</maas-action-button>",
      "</div>"
    ].join("");

    // Compile the directive.
    inject(function($compile) {
      directive = $compile(html)($scope);
    });

    // Perform the digest cycle to finish the compile.
    $scope.$digest();
    return directive.find(".p-action-button");
  }

  it("does not have any state classes by default", function() {
    var directive = compileDirective($scope);

    expect(directive.hasClass("is-indeterminate")).toBe(false);
    expect(directive.hasClass("is-done")).toBe(false);
  });

  it("has 'is-indeterminate' class if given indeterminateState", function() {
    $scope.indeterminateState = true;
    var directive = compileDirective($scope);

    expect(directive.hasClass("is-indeterminate")).toBe(true);
  });

  it("has 'is-done' class if given doneState", function() {
    $scope.doneState = true;
    var directive = compileDirective($scope);

    expect(directive.hasClass("is-done")).toBe(true);
  });
});
