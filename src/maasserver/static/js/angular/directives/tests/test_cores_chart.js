/* Copyright 2019 Canonical Ltd.  This software is lecensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for cores chart directive.
 */

describe("maasCoresChart", () => {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Create a new scope before each test.
  let $scope;
  beforeEach(inject($rootScope => {
    $scope = $rootScope.$new();
  }));

  // Return the compiled directive.
  function compileDirective(scope) {
    let directive;
    let html = [
      "<div>",
      "<maas-cores-chart ",
      "used='" + scope.used + "' ",
      "total='" + scope.total + "' ",
      "overcommit='" + scope.overcommit + "'",
      ">",
      "</maas-cores-chart>",
      "</div>"
    ].join("");

    // Compile the directive.
    inject($compile => {
      directive = $compile(html)($scope);
    });

    // Perform the digest cycle to finish the compile.
    $scope.$digest();
    return angular.element(directive.find("maas-cores-chart"));
  }

  describe("maasCoresChart", () => {
    it("renders the chart", () => {
      $scope.used = 4;
      $scope.total = 8;
      $scope.overcommit = 1;
      let directive = compileDirective($scope);
      expect(directive.find(".p-cores-chart").length).toBe(1);
      expect(directive.find(".p-cores-chart--overcommit").length).toBe(0);
      expect(directive.find(".p-cores-chart--undercommit").length).toBe(0);
    });

    it("renders correct chart if overcommit", () => {
      $scope.used = 4;
      $scope.total = 8;
      $scope.overcommit = 1.5;
      let directive = compileDirective($scope);
      expect(directive.find(".p-cores-chart--overcommit").length).toBe(1);
      expect(directive.find(".p-cores-chart--undercommit").length).toBe(0);
    });

    it("renders correct chart if undercommit", () => {
      $scope.used = 4;
      $scope.total = 8;
      $scope.overcommit = 0.75;
      let directive = compileDirective($scope);
      expect(directive.find(".p-cores-chart--undercommit").length).toBe(1);
      expect(directive.find(".p-cores-chart--overcommit").length).toBe(0);
    });

    it("renders correct border if overcommit === 1", () => {
      $scope.used = 4;
      $scope.total = 8;
      $scope.overcommit = 1;
      let directive = compileDirective($scope);
      expect(directive.find(".p-cores-chart__border").length).toBe(1);
      expect(directive.find(".p-cores-chart__border--overcommit").length).toBe(
        0
      );
    });

    it("renders correct border if overcommit < 1", () => {
      $scope.used = 4;
      $scope.total = 8;
      $scope.overcommit = 0.75;
      let directive = compileDirective($scope);
      expect(directive.find(".p-cores-chart__border").length).toBe(1);
      expect(directive.find(".p-cores-chart__border--overcommit").length).toBe(
        0
      );
      expect(directive.find(".p-cores-chart__border--undercommit").length).toBe(
        1
      );
    });

    it("renders correct border if overcommit > 1", () => {
      $scope.used = 4;
      $scope.total = 8;
      $scope.overcommit = 1.5;
      let directive = compileDirective($scope);
      expect(directive.find(".p-cores-chart__border").length).toBe(1);
      expect(directive.find(".p-cores-chart__border--overcommit").length).toBe(
        1
      );
      expect(directive.find(".p-cores-chart__border--undercommit").length).toBe(
        0
      );
    });

    it("has a total attribute", () => {
      $scope.used = 4;
      $scope.total = 8;
      $scope.overcommit = 1;
      let directive = compileDirective($scope);
      expect(directive.attr("total")).toBeDefined();
      expect(directive.attr("total")).toBe($scope.total.toString());
    });

    it("has a used attribute", () => {
      $scope.used = 4;
      $scope.total = 8;
      $scope.overcommit = 1;
      let directive = compileDirective($scope);
      expect(directive.attr("used")).toBeDefined();
      expect(directive.attr("used")).toBe($scope.used.toString());
    });

    it("has an overcommit attribute", () => {
      $scope.used = 4;
      $scope.total = 8;
      $scope.overcommit = 1;
      let directive = compileDirective($scope);
      expect(directive.attr("overcommit")).toBeDefined();
      expect(directive.attr("overcommit")).toBe($scope.overcommit.toString());
    });

    it("renders single row if within cores per row limit", () => {
      $scope.used = 8;
      $scope.total = 16;
      $scope.overcommit = 1;
      let directive = compileDirective($scope);
      expect(directive.find(".p-cores-chart--single-row").length).toBe(1);
    });

    it("renders correct number of total cores if single row", () => {
      $scope.used = 8;
      $scope.total = 16;
      $scope.overcommit = 1;
      let directive = compileDirective($scope);
      expect(directive.find(".p-core--total").length).toEqual($scope.total);
    });

    it("renders correct number of used cores if single row", () => {
      $scope.used = 8;
      $scope.total = 16;
      $scope.overcommit = 1;
      let directive = compileDirective($scope);
      expect(directive.find(".p-core--used").length).toEqual($scope.used);
    });

    it("renders double row if within total cores limit", () => {
      $scope.used = 24;
      $scope.total = 32;
      $scope.overcommit = 1;
      let directive = compileDirective($scope);
      expect(directive.find(".p-cores-chart--double-row").length).toBe(1);
    });

    it("renders correct number of total cores if double row", () => {
      $scope.used = 24;
      $scope.total = 32;
      $scope.overcommit = 1;
      let directive = compileDirective($scope);
      expect(directive.find(".p-core--total").length).toEqual($scope.total);
    });

    it("renders correct number of used cores if double row", () => {
      $scope.used = 24;
      $scope.total = 32;
      $scope.overcommit = 1;
      let directive = compileDirective($scope);
      expect(directive.find(".p-core--used").length).toEqual($scope.used);
    });

    it("renders bars if above total cores limit", () => {
      $scope.used = 68;
      $scope.total = 128;
      $scope.overcommit = 1;
      let directive = compileDirective($scope);
      expect(directive.find(".p-cores-chart__used-bar").length).toBe(1);
      expect(directive.find(".p-cores-chart__total-bar").length).toBe(1);
    });
  });
});
