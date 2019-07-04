/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for release options directive.
 */

describe("maasReleaseOptions", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Get the required managers.
  var GeneralManager;
  beforeEach(inject(function($injector) {
    GeneralManager = $injector.get("GeneralManager");
  }));

  // Create a new scope before each test.
  var $scope;
  beforeEach(inject(function($rootScope) {
    $scope = $rootScope.$new();
  }));

  // Return the compiled directive with the osinfo from the scope.
  function compileDirective() {
    var directive;
    var html =
      '<div><div data-maas-release-options="options">' + "</div></div>";

    // Compile the directive.
    inject(function($compile) {
      directive = $compile(html)($scope);
    });

    // Perform the digest cycle to finish the compile.
    $scope.$digest();
    return directive.find("div");
  }

  it("sets erase and options from GeneralManager", function() {
    var options = {};
    $scope.options = options;

    var managerOptions = {
      erase: true,
      secure_erase: true,
      quick_erase: true
    };
    spyOn(GeneralManager, "getData").and.returnValue(managerOptions);

    compileDirective();
    expect(options).toEqual({
      erase: true,
      secureErase: true,
      quickErase: true
    });
  });

  it("sets erase and not options from GeneralManager", function() {
    var options = {};
    $scope.options = options;

    var managerOptions = {
      erase: false,
      secure_erase: true,
      quick_erase: true
    };
    spyOn(GeneralManager, "getData").and.returnValue(managerOptions);

    // Since erase is false all other options should be false so the
    // checkboxes are not selected.
    compileDirective();
    expect(options).toEqual({
      erase: false,
      secureErase: false,
      quickErase: false
    });
  });

  it("setting erase sets options from GeneralManager", function() {
    var options = {};
    $scope.options = options;

    var managerOptions = {
      erase: false,
      secure_erase: true,
      quick_erase: true
    };
    spyOn(GeneralManager, "getData").and.returnValue(managerOptions);

    // When erase is set to true by the user the other global options
    // should then be set to the global defaults.
    var directive = compileDirective();
    options.erase = true;
    directive.isolateScope().onEraseChange();
    expect(options).toEqual({
      erase: true,
      secureErase: true,
      quickErase: true
    });
  });

  it("deselecting erase clears options", function() {
    var options = {};
    $scope.options = options;

    var managerOptions = {
      erase: false,
      secure_erase: true,
      quick_erase: true
    };
    spyOn(GeneralManager, "getData").and.returnValue(managerOptions);

    // When erase is deselected the other selected options should go
    // back to false so there checkboxes are not selected.
    var directive = compileDirective();
    options.erase = true;
    directive.isolateScope().onEraseChange();
    options.erase = false;
    directive.isolateScope().onEraseChange();
    expect(options).toEqual({
      erase: false,
      secureErase: false,
      quickErase: false
    });
  });

  it("GeneralManager erase disables erase deselection", function() {
    var options = {};
    $scope.options = options;

    var managerOptions = {
      erase: true,
      secure_erase: true,
      quick_erase: true
    };
    spyOn(GeneralManager, "getData").and.returnValue(managerOptions);

    var directive = compileDirective();
    expect(directive.find("#diskErase").attr("disabled")).toBe("disabled");
  });
});
