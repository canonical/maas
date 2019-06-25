/* Copyright 2019 Canonical Ltd.  This software is lecensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for cores chart directive.
 */

describe("maasCoresChart", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Create a new scope before each test.
  var $scope;
  beforeEach(inject(function($rootScope) {
    $scope = $rootScope.$new();
  }));

  // Return the compiled directive.
  function compileDirective(scope) {
    var directive;
    var html = [
      "<div>",
      "<maas-cores-chart ",
      "used='" + scope.used + "' ",
      "total='" + scope.total + "' ",
      ">",
      "</maas-cores-chart>",
      "</div>"
    ].join("");

    // Compile the directive.
    inject(function($compile) {
      directive = $compile(html)($scope);
    });

    // Perform the digest cycle to finish the compile.
    $scope.$digest();
    return angular.element(directive.find("maas-cores-chart"));
  }

  describe("maasCoresChart", function() {
    it("renders the chart", function() {
      $scope.used = 4;
      $scope.total = 8;
      var directive = compileDirective($scope);
      expect(directive.attr("used")).toBe("4");
      expect(directive.attr("total")).toBe("8");
      expect(directive.find(".p-cores-chart").length).toBe(1);
    });

    it("renders single row if within cores per row limit", function() {
      $scope.used = 8;
      $scope.total = 16;
      var directive = compileDirective($scope);
      expect(directive.find(".p-cores-chart--single-row").length).toBe(1);
    });

    it("renders double row if within total cores limit", function() {
      $scope.used = 24;
      $scope.total = 32;
      var directive = compileDirective($scope);
      expect(directive.find(".p-cores-chart--double-row").length).toBe(1);
    });

    it("renders bars if above total cores limit", function() {
      $scope.used = 68;
      $scope.total = 128;
      var directive = compileDirective($scope);
      expect(directive.find(".p-cores-chart__used-bar").length).toBe(1);
      expect(directive.find(".p-cores-chart__total-bar").length).toBe(1);
    });
  });
});
