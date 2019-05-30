/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for PreferencesController.
 */

describe("PreferencesController", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Grab the needed angular pieces.
  var $controller, $rootScope, $scope, $q;
  beforeEach(inject(function($injector) {
    $controller = $injector.get("$controller");
    $rootScope = $injector.get("$rootScope");
    $scope = $rootScope.$new();
    $q = $injector.get("$q");
  }));

  // Load any injected managers and services.
  var UsersManager, ManagerHelperService;
  beforeEach(inject(function($injector) {
    UsersManager = $injector.get("UsersManager");
    ManagerHelperService = $injector.get("ManagerHelperService");
  }));

  // Makes the PreferencesController
  function makeController(loadManagerDefer) {
    var loadManager = spyOn(ManagerHelperService, "loadManager");
    if (angular.isObject(loadManagerDefer)) {
      loadManager.and.returnValue(loadManagerDefer.promise);
    } else {
      loadManager.and.returnValue($q.defer().promise);
    }

    // Create the controller.
    var controller = $controller("PreferencesController", {
      $scope: $scope,
      UsersManager: UsersManager,
      ManagerHelperService: ManagerHelperService
    });

    return controller;
  }

  it("calls loadManager with correct managers", function() {
    makeController();
    expect(ManagerHelperService.loadManager).toHaveBeenCalledWith(
      $scope,
      UsersManager
    );
  });

  it("sets initial $scope", function() {
    makeController();
    expect($scope.loading).toBe(true);
  });

  it("clears loading", function() {
    var defer = $q.defer();
    makeController(defer);
    defer.resolve();
    $scope.$digest();
    expect($scope.loading).toBe(false);
  });
});
