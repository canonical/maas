/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for IntroUserController.
 */

describe("IntroUserController", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Grab the needed angular pieces.
  var $controller, $rootScope, $location, $scope, $q, $window;
  beforeEach(inject(function($injector) {
    $controller = $injector.get("$controller");
    $rootScope = $injector.get("$rootScope");
    $location = $injector.get("$location");
    $scope = $rootScope.$new();
    $q = $injector.get("$q");
    $window = {
      location: {
        reload: jasmine.createSpy("reload")
      }
    };
  }));

  // Load any injected managers and services.
  var UsersManager, ManagerHelperService;
  beforeEach(inject(function($injector) {
    UsersManager = $injector.get("UsersManager");
    ManagerHelperService = $injector.get("ManagerHelperService");
  }));

  // Before the test mark it as not complete, after each test mark
  // it as complete.
  beforeEach(function() {
    window.MAAS_config.user_completed_intro = false;
  });
  afterEach(function() {
    window.MAAS_config.user_completed_intro = true;
  });

  // Makes the IntroUserController
  function makeController(loadManagerDefer) {
    var loadManager = spyOn(ManagerHelperService, "loadManager");
    if (angular.isObject(loadManagerDefer)) {
      loadManager.and.returnValue(loadManagerDefer.promise);
    } else {
      loadManager.and.returnValue($q.defer().promise);
    }

    // Create the controller.
    var controller = $controller("IntroUserController", {
      $scope: $scope,
      $rootScope: $rootScope,
      $window: $window,
      $location: $location,
      UsersManager: UsersManager,
      ManagerHelperService: ManagerHelperService
    });

    return controller;
  }

  it("sets title and page on $rootScope", function() {
    makeController();
    expect($rootScope.title).toBe("Welcome");
    expect($rootScope.page).toBe("intro");
  });

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
    expect($scope.user).toBeNull();
  });

  it("clears loading", function() {
    var defer = $q.defer();
    makeController(defer);
    defer.resolve();
    $scope.$digest();
    expect($scope.loading).toBe(false);
  });

  it("calls $location.path if already completed", function() {
    window.MAAS_config.user_completed_intro = true;
    spyOn($location, "path");
    makeController();
    expect($location.path).toHaveBeenCalledWith("/");
  });

  it("sets user on resolve", function() {
    var defer = $q.defer();
    makeController(defer);
    var user = {};
    spyOn(UsersManager, "getAuthUser").and.returnValue(user);

    defer.resolve();
    $scope.$digest();
    expect($scope.user).toBe(user);
  });

  describe("$rootScope.skip", function() {
    it("calls markIntroComplete and reloads", function() {
      makeController();
      var defer = $q.defer();
      spyOn(UsersManager, "markIntroComplete").and.returnValue(defer.promise);
      $rootScope.skip();

      expect(UsersManager.markIntroComplete).toHaveBeenCalled();
      defer.resolve();
      $scope.$digest();
      expect($window.location.reload).toHaveBeenCalled();
    });
  });

  describe("canContinue", function() {
    it("returns false when no sshkeys", function() {
      makeController();
      $scope.user = {
        sshkeys_count: 0
      };
      expect($scope.canContinue()).toBe(false);
    });

    it("returns true when sshkeys", function() {
      makeController();
      $scope.user = {
        sshkeys_count: 1
      };
      expect($scope.canContinue()).toBe(true);
    });
  });

  describe("clickContinue", function() {
    it("does nothing if cannot continue", function() {
      makeController();
      spyOn($scope, "canContinue").and.returnValue(false);
      spyOn(UsersManager, "markIntroComplete");
      $scope.clickContinue();
      expect(UsersManager.markIntroComplete).not.toHaveBeenCalled();
    });

    it("forces ignores canContinue", function() {
      makeController();
      spyOn($scope, "canContinue").and.returnValue(false);
      spyOn(UsersManager, "markIntroComplete").and.returnValue(
        $q.defer().promise
      );
      $scope.clickContinue(true);
      expect(UsersManager.markIntroComplete).toHaveBeenCalled();
    });

    it("calls updateItem and reloads", function() {
      makeController();
      var defer = $q.defer();
      spyOn(UsersManager, "markIntroComplete").and.returnValue(defer.promise);
      $scope.clickContinue(true);

      expect(UsersManager.markIntroComplete).toHaveBeenCalled();
      defer.resolve();
      $scope.$digest();
      expect($window.location.reload).toHaveBeenCalled();
    });
  });
});
