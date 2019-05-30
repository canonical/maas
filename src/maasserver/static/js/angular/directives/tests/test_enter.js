/* Copyright 2017 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for enter directive.
 */

describe("maasEnter", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Create a new scope before each test. Not used in this test, but
  // required to compile the directive.
  var $scope;
  beforeEach(inject(function($rootScope) {
    $scope = $rootScope.$new();
  }));

  // Return the compiled directive with the items from the scope.
  function compileDirective(ng_enter) {
    var directive;
    var html = '<div><button maas-enter="' + ng_enter + '"></button></div>';

    // Compile the directive.
    inject(function($compile) {
      directive = $compile(html)($scope);
    });

    // Perform the digest cycle to finish the compile.
    $scope.$digest();
    return directive.find("button");
  }

  it("Enter keydown on button will fire ng-enter", function() {
    $scope.enter = jasmine.createSpy("enter");
    var directive = compileDirective("enter()");
    var evt = angular.element.Event("keydown");
    evt.which = 13;

    directive.trigger(evt);
    expect($scope.enter).toHaveBeenCalled();
  });

  it("Space keydown on button will not fire ng-enter", function() {
    $scope.enter = jasmine.createSpy("enter");
    var directive = compileDirective("enter()");
    var evt = angular.element.Event("keydown");
    evt.which = 32;

    directive.trigger(evt);
    expect($scope.enter).not.toHaveBeenCalled();
  });
});
