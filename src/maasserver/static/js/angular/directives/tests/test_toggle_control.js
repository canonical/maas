/* Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for toggle control directive.
 */

describe("maastoggleCtrl", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Create a new scope before each test.
  var $scope;
  var $document;

  beforeEach(inject(function($rootScope, _$window_, _$document_) {
    $document = _$document_;
    $scope = $rootScope.$new();
  }));

  // Return the compiled directive with the items from the scope.
  function compileDirective() {
    var directive;
    var html = [
      "<div>",
      "<div toggle-ctrl>",
      '<button data-ng-click="toggleMenu()">View actions</button>',
      '<div role="menu" data-ng-show="isToggled"></div>',
      "</div>",
      "</div>"
    ].join("");

    // Compile the directive.
    inject(function($compile) {
      directive = $compile(html)($scope);
    });

    // Perform the digest cycle to finish the compile.
    $scope.$digest();
    return directive.find("div");
  }

  it("click link sets isToggled to true", function() {
    var directive = compileDirective();
    directive.find("button[data-ng-click]").click();
    expect($scope.isToggled).toBe(true);
  });

  it("click div sets isToggled to true", function() {
    var directive = compileDirective();
    directive.find("button[data-ng-click]").click();
    expect($scope.isToggled).toBe(true);
    $document.find("body").click();
    expect($scope.isToggled).toBe(false);
  });
});
