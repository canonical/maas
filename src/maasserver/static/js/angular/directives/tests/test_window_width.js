/* Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for window width.
 */

describe("maasWindowWidth", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Create a new scope before each test.
  var $scope;
  var $window;

  beforeEach(inject(function($rootScope, _$window_) {
    $window = _$window_;
    $scope = $rootScope.$new();
  }));

  // Return the compiled directive with the items from the scope.
  function compileDirective() {
    var directive;
    var html = ["<div>", "<div window-width></div>", "</div>"].join("");

    // Compile the directive.
    inject(function($compile) {
      directive = $compile(html)($scope);
    });

    // Perform the digest cycle to finish the compile.
    $scope.$digest();
    return directive.find("div[window-width]");
  }

  it("windowWidth set to initial value", function() {
    $window.innerWidth = 1026;
    compileDirective();
    expect($scope.windowWidth).toEqual($window.innerWidth);
  });

  it("windowWidth set on resize", function() {
    $window.innerWidth = 1026;
    compileDirective();
    $window.innerWidth = 800;
    angular.element($window).triggerHandler("resize");
    expect($scope.windowWidth).toEqual($window.innerWidth);
  });
});
