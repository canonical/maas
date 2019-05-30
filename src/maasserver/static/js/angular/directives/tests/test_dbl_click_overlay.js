/* Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for the double click overlay.
 */

describe("maasDblClickOverlay", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Get the BrowserService before each test.
  var BrowserService;
  beforeEach(inject(function($injector) {
    BrowserService = $injector.get("BrowserService");
  }));

  // Create a new scope before each test.
  var $scope;
  beforeEach(inject(function($rootScope) {
    $scope = $rootScope.$new();
  }));

  // Return the compiled directive with the osinfo from the scope.
  function compileDirective(type, dblClickHandler) {
    var directive;
    var html = '<div><div maas-dbl-click-overlay="' + dblClickHandler + '">';
    if (type === "select") {
      html += '<select id="test-element"></select>';
    } else if (type === "input") {
      html += '<input type="text" id="test-element" />';
    } else if (type === "div") {
      html += '<div id="test-element"></div>';
    } else {
      throw new Error("Unknown type: " + type);
    }
    html += "</div></div>";

    // Compile the directive.
    inject(function($compile) {
      directive = $compile(html)($scope);
    });

    // Perform the digest cycle to finish the compile.
    $scope.$digest();
    return directive.find("div[maas-dbl-click-overlay]");
  }

  it("creates directive with class maas-dbl-overlay", function() {
    var directive = compileDirective("select", "");
    expect(directive.hasClass("maas-dbl-overlay")).toBe(true);
  });

  it("creates directive with overlay element", function() {
    var directive = compileDirective("select", "");
    var overlay = directive.find("div.maas-dbl-overlay--overlay");
    expect(overlay.length).toBe(1);
  });

  it("sets overlay cursor to pointer for select element", function() {
    var directive = compileDirective("select", "");
    var overlay = directive.find("div.maas-dbl-overlay--overlay");
    expect(overlay.css("cursor")).toBe("pointer");
  });

  it("sets overlay cursor to text for input element", function() {
    var directive = compileDirective("input", "");
    var overlay = directive.find("div.maas-dbl-overlay--overlay");
    expect(overlay.css("cursor")).toBe("text");
  });

  it("doesnt sets overlay cursor for div element", function() {
    var directive = compileDirective("div", "");
    var overlay = directive.find("div.maas-dbl-overlay--overlay");
    expect(overlay.css("cursor")).toBe("");
  });

  it("triggers mousedown on select when overlay clicked", function(done) {
    var directive = compileDirective("select", "");
    var select = directive.find("select#test-element");
    select.mousedown(function() {
      // Test will timeout if this handler is not called.
      done();
    });
    var overlay = directive.find("div.maas-dbl-overlay--overlay");
    overlay.triggerHandler("click");
  });

  it("sets focus on input when overlay clicked", function(done) {
    var directive = compileDirective("input", "");
    var input = directive.find("input#test-element");
    input.focus(function() {
      // Test will timeout if this handler is not called.
      done();
    });
    var overlay = directive.find("div.maas-dbl-overlay--overlay");
    overlay.triggerHandler("click");
  });

  it("triggers click on div when overlay clicked", function(done) {
    var directive = compileDirective("div", "");
    var div = directive.find("div#test-element");
    div.click(function() {
      // Test will timeout if this handler is not called.
      done();
    });
    var overlay = directive.find("div.maas-dbl-overlay--overlay");
    overlay.triggerHandler("click");
  });

  it(`calls double click handler when
      the overlay is double clicked`, function(done) {
    $scope.doubleClick = function() {
      // Test will timeout if this handler is not called.
      done();
    };
    var directive = compileDirective("div", "doubleClick()");
    var overlay = directive.find("div.maas-dbl-overlay--overlay");
    overlay.triggerHandler("dblclick");
  });

  it("removes all click handlers on $destroy", function() {
    var directive = compileDirective("div", "");
    var overlay = directive.find("div.maas-dbl-overlay--overlay");
    directive.scope().$destroy();
    expect($._data(angular.element(overlay)[0], "events")).toBeUndefined();
  });

  it("hides overlay if on firefox", function() {
    BrowserService.browser = "firefox";
    var directive = compileDirective("div", "");
    var overlay = directive.find("div.maas-dbl-overlay--overlay");
    expect(overlay.hasClass("ng-hide")).toBe(true);
  });

  it("doesnt hide overlay if on firefox", function() {
    BrowserService.browser = "chrome";
    var directive = compileDirective("div", "");
    var overlay = directive.find("div.maas-dbl-overlay--overlay");
    expect(overlay.hasClass("ng-hide")).toBe(false);
  });
});
