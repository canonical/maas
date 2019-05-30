/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for IntroController.
 */

describe("IntroController", function() {
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
  var ConfigsManager, PackageRepositoriesManager, BootResourcesManager;
  var ManagerHelperService;
  beforeEach(inject(function($injector) {
    ConfigsManager = $injector.get("ConfigsManager");
    PackageRepositoriesManager = $injector.get("PackageRepositoriesManager");
    BootResourcesManager = $injector.get("BootResourcesManager");
    ManagerHelperService = $injector.get("ManagerHelperService");
  }));

  // Before the test mark it as not complete, after each test mark
  // it as complete.
  beforeEach(function() {
    window.MAAS_config.completed_intro = false;
  });
  afterEach(function() {
    window.MAAS_config.completed_intro = true;
  });

  // Makes the IntroController
  function makeController(loadManagerDefer) {
    var loadManagers = spyOn(ManagerHelperService, "loadManagers");
    if (angular.isObject(loadManagerDefer)) {
      loadManagers.and.returnValue(loadManagerDefer.promise);
    } else {
      loadManagers.and.returnValue($q.defer().promise);
    }

    // Create the controller.
    var controller = $controller("IntroController", {
      $scope: $scope,
      $rootScope: $rootScope,
      $window: $window,
      $location: $location,
      ConfigsManager: ConfigsManager,
      PackageRepositoriesManager: PackageRepositoriesManager,
      BootResourcesManager: BootResourcesManager,
      ManagerHelperService: ManagerHelperService
    });

    return controller;
  }

  it("sets title and page on $rootScope", function() {
    makeController();
    expect($rootScope.title).toBe("Welcome");
    expect($rootScope.page).toBe("intro");
  });

  it("calls loadManagers with correct managers", function() {
    makeController();
    expect(ManagerHelperService.loadManagers).toHaveBeenCalledWith($scope, [
      ConfigsManager,
      PackageRepositoriesManager
    ]);
  });

  it("sets initial $scope", function() {
    makeController();
    expect($scope.loading).toBe(true);
    expect($scope.configManager).toBe(ConfigsManager);
    expect($scope.repoManager).toBe(PackageRepositoriesManager);
    expect($scope.bootResources).toBe(BootResourcesManager.getData());
    expect($scope.hasImages).toBe(false);
    expect($scope.maasName).toBeNull();
    expect($scope.upstreamDNS).toBeNull();
    expect($scope.mainArchive).toBeNull();
    expect($scope.portsArchive).toBeNull();
    expect($scope.httpProxy).toBeNull();
  });

  it("clears loading", function() {
    var defer = $q.defer();
    makeController(defer);
    defer.resolve();
    $scope.$digest();
    expect($scope.loading).toBe(false);
  });

  it("calls $location.path if already completed", function() {
    window.MAAS_config.completed_intro = true;
    spyOn($location, "path");
    makeController();
    expect($location.path).toHaveBeenCalledWith("/");
  });

  it("sets required objects on resolve", function() {
    var defer = $q.defer();
    makeController(defer);
    var maasName = { name: "maas_name" };
    var upstreamDNS = { name: "upstream_dns" };
    var httpProxy = { name: "http_proxy" };
    var mainArchive = {
      default: true,
      name: "main_archive"
    };
    var portsArchive = {
      default: true,
      name: "ports_archive"
    };
    ConfigsManager._items = [maasName, upstreamDNS, httpProxy, mainArchive];
    PackageRepositoriesManager._items = [mainArchive, portsArchive];

    defer.resolve();
    $scope.$digest();
    expect($scope.maasName).toBe(maasName);
    expect($scope.upstreamDNS).toBe(upstreamDNS);
    expect($scope.httpProxy).toBe(httpProxy);
    expect($scope.mainArchive).toBe(mainArchive);
    expect($scope.portsArchive).toBe(portsArchive);
  });

  describe("$rootScope.skip", function() {
    it("calls updateItem and reloads", function() {
      makeController();
      var defer = $q.defer();
      spyOn(ConfigsManager, "updateItem").and.returnValue(defer.promise);
      $rootScope.skip();

      expect(ConfigsManager.updateItem).toHaveBeenCalledWith({
        name: "completed_intro",
        value: true
      });
      defer.resolve();
      $scope.$digest();
      expect($window.location.reload).toHaveBeenCalled();
    });
  });

  describe("welcomeInError", function() {
    it("returns false without form", function() {
      makeController();
      $scope.maasName = {};
      expect($scope.welcomeInError()).toBe(false);
    });

    it("returns hasErrors from form", function() {
      makeController();
      var sentinel = {};
      var hasErrors = jasmine.createSpy("hasErrors");
      hasErrors.and.returnValue(sentinel);
      $scope.maasName = {
        $maasForm: {
          hasErrors: hasErrors
        }
      };
      expect($scope.welcomeInError()).toBe(sentinel);
    });
  });

  describe("networkInError", function() {
    it("returns false when no forms", function() {
      makeController();
      $scope.upstreamDNS = {};
      $scope.mainArchive = {};
      $scope.portsArchive = {};
      $scope.httpProxy = {};
      expect($scope.networkInError()).toBe(false);
    });

    it("returns false when none have errors", function() {
      makeController();
      var hasErrors = jasmine.createSpy("hasErrors");
      hasErrors.and.returnValue(false);
      var obj = {
        $maasForm: {
          hasErrors: hasErrors
        }
      };
      $scope.upstreamDNS = obj;
      $scope.mainArchive = obj;
      $scope.portsArchive = obj;
      $scope.httpProxy = obj;
      expect($scope.networkInError()).toBe(false);
    });

    it("returns true when one has error", function() {
      makeController();
      var hasErrorsFalse = jasmine.createSpy("hasErrors");
      hasErrorsFalse.and.returnValue(false);
      var objFalse = {
        $maasForm: {
          hasErrors: hasErrorsFalse
        }
      };
      var hasErrorsTrue = jasmine.createSpy("hasErrors");
      hasErrorsTrue.and.returnValue(true);
      var objTrue = {
        $maasForm: {
          hasErrors: hasErrorsTrue
        }
      };
      $scope.upstreamDNS = objTrue;
      $scope.mainArchive = objFalse;
      $scope.portsArchive = objFalse;
      $scope.httpProxy = objFalse;
      expect($scope.networkInError()).toBe(true);
    });
  });

  describe("canContinue", function() {
    it("returns false when welcome has error", function() {
      makeController();
      spyOn($scope, "welcomeInError").and.returnValue(true);
      expect($scope.canContinue()).toBe(false);
    });

    it("returns false when network has error", function() {
      makeController();
      spyOn($scope, "welcomeInError").and.returnValue(false);
      spyOn($scope, "networkInError").and.returnValue(true);
      expect($scope.canContinue()).toBe(false);
    });

    it("returns false when no images", function() {
      makeController();
      spyOn($scope, "welcomeInError").and.returnValue(false);
      spyOn($scope, "networkInError").and.returnValue(false);
      $scope.hasImages = false;
      expect($scope.canContinue()).toBe(false);
    });

    it("returns true", function() {
      makeController();
      spyOn($scope, "welcomeInError").and.returnValue(false);
      spyOn($scope, "networkInError").and.returnValue(false);
      $scope.hasImages = true;
      expect($scope.canContinue()).toBe(true);
    });
  });

  describe("clickContinue", function() {
    it("does nothing if cannot continue", function() {
      makeController();
      spyOn($scope, "canContinue").and.returnValue(false);
      spyOn(ConfigsManager, "updateItem");
      $scope.clickContinue();
      expect(ConfigsManager.updateItem).not.toHaveBeenCalled();
    });

    it("forces ignores canContinue", function() {
      makeController();
      spyOn($scope, "canContinue").and.returnValue(false);
      spyOn(ConfigsManager, "updateItem").and.returnValue($q.defer().promise);
      $scope.clickContinue(true);
      expect(ConfigsManager.updateItem).toHaveBeenCalledWith({
        name: "completed_intro",
        value: true
      });
    });

    it("calls updateItem and reloads", function() {
      makeController();
      var defer = $q.defer();
      spyOn(ConfigsManager, "updateItem").and.returnValue(defer.promise);
      $scope.clickContinue(true);

      expect(ConfigsManager.updateItem).toHaveBeenCalledWith({
        name: "completed_intro",
        value: true
      });
      defer.resolve();
      $scope.$digest();
      expect($window.location.reload).toHaveBeenCalled();
    });
  });
});
