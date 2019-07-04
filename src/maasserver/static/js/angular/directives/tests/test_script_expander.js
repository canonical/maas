/* Copyright 2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for script expander.
 */

describe("pScriptExpander", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Get required angular pieces and create a new scope before each test.
  var $scope;
  beforeEach(inject(function($rootScope, $injector) {
    $scope = $rootScope.$new();
  }));

  // Return the compiled directive.
  function compileDirective() {
    var directive;
    var html = [
      "<div>",
      '<div class="p-script-expander">',
      '<a href="#" class="p-script-expander__trigger">Link</a>',
      '<div class="p-script-expander__content">Target</div>',
      "</div>",
      "</div>"
    ].join("");

    // Compile the directive.
    inject(function($compile) {
      directive = $compile(html)($scope);
    });

    // Perform the digest cycle to finish the compile.
    $scope.$digest();
    return directive.find(".p-script-expander");
  }

  it("sets u-hide initially", function() {
    var directive = compileDirective();
    var content = directive.find(".p-script-expander__content");
    expect(content.hasClass("u-hide")).toBe(true);
  });

  it("toggles u-hide on click", function() {
    var directive = compileDirective();
    var link = directive.find(".p-script-expander__trigger");
    var content = directive.find(".p-script-expander__content");
    expect(content.hasClass("u-hide")).toBe(true);
    link.click();
    expect(content.hasClass("u-hide")).toBe(false);
    link.click();
    expect(content.hasClass("u-hide")).toBe(true);
  });
});
