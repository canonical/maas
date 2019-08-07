/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for DomainsListController.
 */

import { makeInteger, makeName } from "testing/utils";
import MockWebSocket from "testing/websocket";

describe("DomainDetailsController", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Make a fake domain
  function makeDomain() {
    var domain = {
      id: makeInteger(1, 10000),
      name: "example.com",
      displayname: "example.com",
      authoritative: true
    };
    DomainsManager._items.push(domain);
    return domain;
  }

  // Grab the needed angular pieces.
  var $controller, $rootScope, $location, $scope, $q, $routeParams;
  beforeEach(inject(function($injector) {
    $controller = $injector.get("$controller");
    $rootScope = $injector.get("$rootScope");
    $location = $injector.get("$location");
    $scope = $rootScope.$new();
    $q = $injector.get("$q");
    $routeParams = {};
  }));

  // Load any injected managers and services.
  var DomainsManager, UsersManager, ManagerHelperService, ErrorService;
  var RegionConnection, webSocket;
  beforeEach(inject(function($injector) {
    DomainsManager = $injector.get("DomainsManager");
    UsersManager = $injector.get("UsersManager");
    ManagerHelperService = $injector.get("ManagerHelperService");
    ErrorService = $injector.get("ErrorService");
    RegionConnection = $injector.get("RegionConnection");

    // Mock buildSocket so an actual connection is not made.
    webSocket = new MockWebSocket();
    spyOn(RegionConnection, "buildSocket").and.returnValue(webSocket);
    spyOn(RegionConnection, "callMethod").and.returnValue($q.defer().promise);
  }));

  var domain;
  beforeEach(function() {
    domain = makeDomain();
  });

  // Makes the NodesListController
  function makeController(loadManagerDefer) {
    spyOn(UsersManager, "isSuperUser").and.returnValue(true);
    var loadManagers = spyOn(ManagerHelperService, "loadManagers");
    if (angular.isObject(loadManagerDefer)) {
      loadManagers.and.returnValue(loadManagerDefer.promise);
    } else {
      loadManagers.and.returnValue($q.defer().promise);
    }

    // Create the controller.
    var controller = $controller("DomainDetailsController", {
      $scope: $scope,
      $rootScope: $rootScope,
      $routeParams: $routeParams,
      $location: $location,
      DomainsManager: DomainsManager,
      UsersManager: UsersManager,
      ManagerHelperService: ManagerHelperService,
      ErrorService: ErrorService
    });

    return controller;
  }

  // Make the controller and resolve the setActiveItem call.
  function makeControllerResolveSetActiveItem() {
    var setActiveDefer = $q.defer();
    spyOn(DomainsManager, "setActiveItem").and.returnValue(
      setActiveDefer.promise
    );
    var defer = $q.defer();
    var controller = makeController(defer);
    $routeParams.domain_id = domain.id;

    defer.resolve();
    $rootScope.$digest();
    setActiveDefer.resolve(domain);
    $rootScope.$digest();

    return controller;
  }

  it("sets title and page on $rootScope", function() {
    makeController();
    expect($rootScope.title).toBe("Loading...");
    expect($rootScope.page).toBe("domains");
  });

  it("raises error if domain identifier is invalid", function() {
    spyOn(DomainsManager, "setActiveItem").and.returnValue($q.defer().promise);
    spyOn(ErrorService, "raiseError").and.returnValue($q.defer().promise);
    var defer = $q.defer();
    makeController(defer);
    $routeParams.domain_id = "xyzzy";

    defer.resolve();
    $rootScope.$digest();

    expect($scope.domain).toBe(null);
    expect($scope.loaded).toBe(false);
    expect(DomainsManager.setActiveItem).not.toHaveBeenCalled();
    expect(ErrorService.raiseError).toHaveBeenCalled();
  });

  it("doesn't call setActiveItem if domain is loaded", function() {
    spyOn(DomainsManager, "setActiveItem").and.returnValue($q.defer().promise);
    var defer = $q.defer();
    makeController(defer);
    DomainsManager._activeItem = domain;
    $routeParams.domain_id = domain.id;

    defer.resolve();
    $rootScope.$digest();

    expect($scope.domain).toBe(domain);
    expect($scope.loaded).toBe(true);
    expect(DomainsManager.setActiveItem).not.toHaveBeenCalled();
  });

  it("calls setActiveItem if domain is not active", function() {
    spyOn(DomainsManager, "setActiveItem").and.returnValue($q.defer().promise);
    var defer = $q.defer();
    makeController(defer);
    $routeParams.domain_id = domain.id;

    defer.resolve();
    $rootScope.$digest();

    expect(DomainsManager.setActiveItem).toHaveBeenCalledWith(domain.id);
  });

  it("sets domain and loaded once setActiveItem resolves", function() {
    makeControllerResolveSetActiveItem();
    expect($scope.domain).toBe(domain);
    expect($scope.loaded).toBe(true);
  });

  it("title is updated once setActiveItem resolves", function() {
    makeControllerResolveSetActiveItem();
    expect($rootScope.title).toBe(domain.displayname);
  });

  describe("canBeDeleted", function() {
    it("returns false if domain is null", function() {
      makeControllerResolveSetActiveItem();
      $scope.domain = null;
      expect($scope.canBeDeleted()).toBe(false);
    });

    it("returns false if domain has resources", function() {
      makeControllerResolveSetActiveItem();
      $scope.domain.rrsets = [makeInteger()];
      expect($scope.canBeDeleted()).toBe(false);
    });

    it("returns true if domain has no resources", function() {
      makeControllerResolveSetActiveItem();
      $scope.domain.rrsets = [];
      expect($scope.canBeDeleted()).toBe(true);
    });
  });

  describe("deleteButton", function() {
    it("confirms delete", function() {
      makeControllerResolveSetActiveItem();
      $scope.deleteButton();
      expect($scope.actionInProgress).toBe(true);
    });

    it("clears error", function() {
      makeControllerResolveSetActiveItem();
      $scope.error = makeName("error");
      $scope.deleteButton();
      expect($scope.error).toBeNull();
    });
  });

  describe("cancelAction", function() {
    it("cancels delete", function() {
      makeControllerResolveSetActiveItem();
      $scope.deleteButton();
      $scope.cancelAction();
      expect($scope.actionInProgress).toBe(false);
    });
  });

  describe("deleteDomain", function() {
    it("calls deleteDomain", function() {
      makeController();
      var deleteDomain = spyOn(DomainsManager, "deleteDomain");
      var defer = $q.defer();
      deleteDomain.and.returnValue(defer.promise);
      $scope.deleteConfirmButton();
      expect(deleteDomain).toHaveBeenCalled();
    });
  });
});
