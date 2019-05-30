/* Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for contenteditable.
 */

import { makeName } from "testing/utils";

describe("contenteditable", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Create a new scope before each test.
  var $scope;
  beforeEach(inject(function($rootScope) {
    $scope = $rootScope.$new();
  }));

  // Return the compiled directive with the osinfo from the scope.
  function compileDirective(ngModel, ngDisabled, maasEditing) {
    var directive;
    var html =
      '<div><span contenteditable="true" data-ng-model="' +
      ngModel +
      '" data-ng-disabled="' +
      ngDisabled +
      '" ' +
      'data-maas-editing="' +
      maasEditing +
      '"></span></div>';

    // Compile the directive.
    inject(function($compile) {
      directive = $compile(html)($scope);
    });

    // Perform the digest cycle to finish the compile.
    $scope.$digest();
    return directive.find("span");
  }

  it("sets the content of span to the value of model", function() {
    var name = makeName("name");
    $scope.name = name;
    var directive = compileDirective("name");
    expect(directive.text()).toBe(name);
  });

  it("change event on the span will change the value", function() {
    var name = makeName("name");
    $scope.name = makeName("name");
    var directive = compileDirective("name");
    directive.text(name);
    directive.triggerHandler("change");
    $scope.$digest();
    expect($scope.name).toBe(name);
  });

  it("blur event on the span will change the value", function() {
    var name = makeName("name");
    $scope.name = makeName("name");
    var directive = compileDirective("name");
    directive.text(name);
    directive.triggerHandler("blur");
    $scope.$digest();
    expect($scope.name).toBe(name);
  });

  it("keyup event on the span will change the value", function() {
    var name = makeName("name");
    $scope.name = makeName("name");
    var directive = compileDirective("name");
    directive.text(name);
    directive.keyup();
    $scope.$digest();
    expect($scope.name).toBe(name);
  });

  it("cannot gain focus if disabled", function() {
    $scope.name = makeName("name");
    $scope.disabled = function() {
      return true;
    };
    var directive = compileDirective("name", "disabled()");
    directive.triggerHandler("focus");
    $scope.$digest();
    expect(directive.is(":focus")).toBe(false);
  });

  it("calls maasEditing on focus if enabled", function() {
    $scope.name = makeName("name");
    $scope.disabled = function() {
      return false;
    };
    $scope.nowEditing = jasmine.createSpy("nowEditing");
    var directive = compileDirective("name", "disabled()", "nowEditing()");
    directive.triggerHandler("focus");
    $scope.$digest();
    expect($scope.nowEditing).toHaveBeenCalled();
  });
});
