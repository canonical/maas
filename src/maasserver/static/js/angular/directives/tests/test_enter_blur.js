/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for enter blur directive.
 */

describe("maasEnterBlur", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Create a new scope before each test. Not used in this test, but
  // required to compile the directive.
  var $scope;
  beforeEach(inject(function($rootScope) {
    $scope = $rootScope.$new();
  }));

  // Return the compiled directive with the items from the scope.
  function compileDirective() {
    var directive;
    var html = [
      "<div>",
      '<input type="text" data-maas-enter-blur>',
      "</div>"
    ].join("");

    // Compile the directive.
    inject(function($compile) {
      directive = $compile(html)($scope);
    });

    // Perform the digest cycle to finish the compile.
    $scope.$digest();

    // Attach to document so it can grab focus.
    directive.appendTo(document.body);
    return directive.find("input");
  }

  // Compile the directive.
  var directive;
  beforeEach(function() {
    directive = compileDirective();
  });

  it("removes focus on enter keydown", function() {
    directive.focus();
    expect(document.activeElement).toBe(directive[0]);

    // Send enter.
    var evt = angular.element.Event("keydown");
    evt.which = 13;
    directive.trigger(evt);

    expect(document.activeElement).not.toBe(directive[0]);
  });

  it("removes focus on enter keypress", function() {
    directive.focus();
    expect(document.activeElement).toBe(directive[0]);

    // Send enter.
    var evt = angular.element.Event("keypress");
    evt.which = 13;
    directive.trigger(evt);

    expect(document.activeElement).not.toBe(directive[0]);
  });
});
