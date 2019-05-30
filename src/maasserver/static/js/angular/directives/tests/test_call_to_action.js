/* Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for Call-To-Action dropdown directive.
 */

import { makeName } from "testing/utils";

describe("maasCta", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Make items for the dropdown.
  function makeItems() {
    var i;
    var items = [];
    for (i = 0; i < 5; i++) {
      items.push({
        title: makeName("option")
      });
    }
    return items;
  }

  // Create a new scope before each test.
  var $scope;
  beforeEach(inject(function($rootScope) {
    $scope = $rootScope.$new();
    $scope.items = makeItems();
    $scope.active = null;
  }));

  // Return the compiled directive with the items from the scope.
  function compileDirective(maas_cta, ng_model, ng_change, ng_click, title) {
    if (!title) {
      title = "";
    }

    var directive;
    var html =
      '<div><div data-maas-cta="' +
      maas_cta +
      '" ' +
      'data-ng-model="' +
      ng_model +
      '" ' +
      'data-ng-change="' +
      ng_change +
      '" ' +
      'data-ng-click="' +
      ng_click +
      '" ' +
      'data-default-title="' +
      title +
      '"></div></div>';

    // Compile the directive.
    inject(function($compile) {
      directive = $compile(html)($scope);
    });

    // Perform the digest cycle to finish the compile.
    $scope.$digest();
    return directive.find("div");
  }

  it("default shown is false", function() {
    var directive = compileDirective("items", "active");
    expect(directive.isolateScope().shown).toBe(false);
  });

  it("default secondary is false", function() {
    var directive = compileDirective("items", "active");
    expect(directive.isolateScope().secondary).toBe(false);
  });

  it("sets default title to 'Take action'", function() {
    var directive = compileDirective("items", "active");
    expect(directive.find("button.p-cta__toggle").text()).toBe("Take action");
  });

  it("sets default title to another name", function() {
    var name = makeName("title");
    var directive = compileDirective("items", "active", null, null, name);
    var selector = "button.p-cta__toggle";
    expect(directive.find(selector).text()).toBe(name);
  });

  it("click link sets shown to true", function() {
    var directive = compileDirective("items", "active");
    directive.find("button.p-cta__toggle").click();
    expect(directive.isolateScope().shown).toBe(true);
  });

  it("dropdown hidden when shown is false", function() {
    var directive = compileDirective("items", "active");
    var dropdown = directive.find("div.p-cta__dropdown");
    expect(dropdown.hasClass("ng-hide")).toBe(true);
  });

  it("dropdown shown when shown is true", function() {
    var directive = compileDirective("items", "active");
    directive.isolateScope().shown = true;
    $scope.$digest();

    var dropdown = directive.find("div.p-cta__dropdown");
    expect(dropdown.hasClass("ng-hide")).toBe(false);
  });

  it("dropdown secondary when secondary is true", function() {
    var directive = compileDirective("items", "active");
    directive.isolateScope().secondary = true;
    $scope.$digest();

    expect(directive.hasClass("secondary")).toBe(false);
  });

  it("dropdown list options", function() {
    var directive = compileDirective("items", "active");
    var links = directive.find("button.p-cta__link");

    var listItems = [];
    angular.forEach(links, function(ele, i) {
      listItems.push(angular.element(ele).text());
    });

    var expectTitles = [];
    angular.forEach($scope.items, function(item) {
      expectTitles.push(item.title);
    });
    expect(expectTitles).toEqual(listItems);
  });

  it("dropdown select sets shown to false", function() {
    var directive = compileDirective("items", "active");
    var links = directive.find("button.p-cta__link");

    // Open the dropdown.
    directive.find("button.p-cta__toggle").click();
    expect(directive.isolateScope().shown).toBe(true);

    // Clicking a link should close the dropdown.
    angular.element(links[0]).click();
    expect(directive.isolateScope().shown).toBe(false);
  });

  it("dropdown select sets model", function() {
    var directive = compileDirective("items", "active");
    var links = directive.find("button.p-cta__link");

    angular.element(links[0]).click();
    expect(directive.scope().active).toBe($scope.items[0]);
  });

  it("dropdown select sets title", function() {
    var directive = compileDirective("items", "active");
    var links = directive.find("button.p-cta__link");

    angular.element(links[0]).click();
    var title = directive.find("button.p-cta__toggle").text();
    expect(title).toBe($scope.items[0].title);
  });

  it("dropdown select sets secondary", function() {
    var directive = compileDirective("items", "active");
    var links = directive.find("button.p-cta__link");

    angular.element(links[0]).click();
    expect(directive.isolateScope().secondary).toBe(true);
  });

  it("dropdown select sets selectedTitle", function() {
    $scope.items[0].selectedTitle = "Different if Selected";
    var directive = compileDirective("items", "active");
    var links = directive.find("button.p-cta__link");

    var iscope = directive.isolateScope();
    expect(iscope.getTitle()).toBe("Take action");
    angular.element(links[0]).click();
    expect(iscope.getTitle()).toBe("Different if Selected");
  });

  it("dropdown select sets other options' selectedTitle", function() {
    $scope.items[1].selectedTitle = "Different if Selected";
    var directive = compileDirective("items", "active");
    var links = directive.find("button.p-cta__link");

    var iscope = directive.isolateScope();
    expect(iscope.getTitle()).toBe("Take action");
    angular.element(links[0]).click();
    var linkOneText = angular
      .element(links[1])
      .text()
      .trim();
    expect(linkOneText).toBe("Different if Selected");
  });

  it("clicking body will set shown to false", function() {
    var directive = compileDirective("items", "active");
    // Open the dropdown.
    directive.find("button.p-cta__toggle").click();
    expect(directive.isolateScope().shown).toBe(true);

    // Click the body.
    var $document;
    inject(function($injector) {
      $document = $injector.get("$document");
    });
    angular.element($document.find("body")).click();

    expect(directive.isolateScope().shown).toBe(false);
  });

  it("clicking button will fire ng-click", function() {
    $scope.clicked = jasmine.createSpy("clicked");
    var directive = compileDirective("items", "active", null, "clicked()");
    // Open the dropdown.
    directive.find("button.p-cta__toggle").click();
    expect($scope.clicked).toHaveBeenCalled();
  });
});
