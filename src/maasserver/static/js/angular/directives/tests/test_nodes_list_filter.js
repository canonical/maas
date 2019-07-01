/* Copyright 2019 Canonical Ltd.  This software is lecensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for nodes list filter directive.
 */

describe("nodesListFilter", () => {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Preload the $templateCache with empty contents. We only test the
  // controller of the directive, not the template.
  let $templateCache;
  beforeEach(inject($injector => {
    $templateCache = $injector.get("$templateCache");
    $templateCache.put("static/partials/nodelist/nodes-list-filter.html", "");
  }));

  // Create a new scope before each test.
  let $scope;
  beforeEach(inject($rootScope => {
    $scope = $rootScope.$new();
    $scope.currentPage = "machines";
    $scope.options = {};
    $scope.order = [];
    $scope.isDisabled = false;
  }));

  // Return the compiled directive.
  const compileDirective = () => {
    let directive;
    const html = [
      "<div>",
      "<nodes-list-filter ",
      "current-page='currentPage'",
      "options='options'",
      "order='order'",
      "is-disabled='isDisabled'",
      "toggle-filter='toggleFilter'",
      "is-filter-active='isFilterActive'",
      "></nodes-list-filter>",
      "</div>"
    ].join("");

    // Compile the directive.
    inject($compile => {
      directive = $compile(html)($scope);
    });

    // Perform the digest cycle to finish the compile.
    $scope.$digest();
    return angular.element(directive.find("nodes-list-filter"));
  };

  describe("toggleOpenFilter", () => {
    it("toggles the filter being open", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();
      scope.openFilter = false;

      scope.toggleOpenFilter();
      expect(scope.openFilter).toEqual(true);
      scope.toggleOpenFilter();
      expect(scope.openFilter).toEqual(false);
    });
  });

  describe("toggleOpenOption", () => {
    it("toggles the currently opened option accordion", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();
      scope.openOption = "";

      scope.toggleOpenOption("option");
      expect(scope.openOption).toEqual("option");
      scope.toggleOpenOption("option");
      expect(scope.openOption).toEqual("");
    });
  });

  describe("orderOptions", () => {
    it("converts options object to array and orders correctly", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();
      scope.options = {
        architecture: [
          { name: "arch1", count: 1 },
          { name: "arch2", count: 2 }
        ],
        status: [{ name: "status1", count: 3 }]
      };
      scope.order = ["status", "architecture"];
      const orderedOptions = scope.orderOptions();

      expect(orderedOptions[0].name).toEqual(scope.order[0]);
      expect(orderedOptions[0].entries.length).toEqual(
        scope.options[orderedOptions[0].name].length
      );
      expect(orderedOptions[1].name).toEqual(scope.order[1]);
      expect(orderedOptions[1].entries.length).toEqual(
        scope.options[orderedOptions[1].name].length
      );
    });
  });
});
