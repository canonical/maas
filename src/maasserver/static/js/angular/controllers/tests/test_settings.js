/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for SettingsController.
 */

import { makeName } from "testing/utils";
import MockWebSocket from "testing/websocket";

describe("SettingsController", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Grab the needed angular pieces.
  var $controller, $rootScope, $scope, $q;
  beforeEach(inject(function($injector) {
    $controller = $injector.get("$controller");
    $rootScope = $injector.get("$rootScope");
    $q = $injector.get("$q");
    $scope = $rootScope.$new();
  }));

  // Load the required dependencies for the SettingsController and
  // mock the websocket connection.
  var DHCPSnippetsManager, SubnetsManager, MachinesManager, GeneralManager;
  var DevicesManager, ControllersManager, ManagerHelperService;
  var PackageRepositoriesManager, RegionConnection, webSocket;
  beforeEach(inject(function($injector) {
    PackageRepositoriesManager = $injector.get("PackageRepositoriesManager");
    DHCPSnippetsManager = $injector.get("DHCPSnippetsManager");
    SubnetsManager = $injector.get("SubnetsManager");
    MachinesManager = $injector.get("MachinesManager");
    DevicesManager = $injector.get("DevicesManager");
    ControllersManager = $injector.get("ControllersManager");
    ManagerHelperService = $injector.get("ManagerHelperService");
    RegionConnection = $injector.get("RegionConnection");
    GeneralManager = $injector.get("GeneralManager");

    // Mock buildSocket so an actual connection is not made.
    webSocket = new MockWebSocket();
    spyOn(RegionConnection, "buildSocket").and.returnValue(webSocket);
    spyOn(RegionConnection, "callMethod").and.returnValue($q.defer().promise);
  }));

  // Setup the routeParams.
  var $routeParams;
  beforeEach(function() {
    $routeParams = {};
  });

  // Make a fake repository.
  var _nextRepoId = 0;
  function makeRepo() {
    return {
      id: _nextRepoId++,
      name: makeName("repo"),
      enabled: true,
      url: makeName("url"),
      key: makeName("key"),
      arches: [makeName("arch"), makeName("arch")],
      distributions: [makeName("dist"), makeName("dist")],
      components: [makeName("comp"), makeName("comp")]
    };
  }

  // Makes the SettingsController
  function makeController(loadManagersDefer) {
    var loadManagers = spyOn(ManagerHelperService, "loadManagers");
    if (angular.isObject(loadManagersDefer)) {
      loadManagers.and.returnValue(loadManagersDefer.promise);
    } else {
      loadManagers.and.returnValue($q.defer().promise);
    }

    return $controller("SettingsController", {
      $scope: $scope,
      $rootScope: $rootScope,
      $routeParams: $routeParams,
      PackageRepositoriesManager: PackageRepositoriesManager,
      DHCPSnippetsManager: DHCPSnippetsManager,
      SubnetsManager: SubnetsManager,
      MachinesManager: MachinesManager,
      DevicesManager: DevicesManager,
      ControllersManager: ControllersManager,
      GeneralManager: GeneralManager,
      ManagerHelperService: ManagerHelperService
    });
  }

  it("sets title to loading and page to settings", function() {
    makeController();
    expect($rootScope.title).toBe("Loading...");
    expect($rootScope.page).toBe("settings");
  });

  it("sets initial values", function() {
    makeController();
    expect($scope.loading).toBe(true);
    expect($scope.loading).toBe(true);
    expect($scope.snippets).toBe(DHCPSnippetsManager.getItems());
    expect($scope.subnets).toBe(SubnetsManager.getItems());
    expect($scope.machines).toBe(MachinesManager.getItems());
    expect($scope.devices).toBe(DevicesManager.getItems());
    expect($scope.controllers).toBe(ControllersManager.getItems());
    expect($scope.known_architectures).toBe(
      GeneralManager.getData("known_architectures")
    );
    expect($scope.pockets_to_disable).toBe(
      GeneralManager.getData("pockets_to_disable")
    );
    expect($scope.components_to_disable).toBe(
      GeneralManager.getData("components_to_disable")
    );
    expect($scope.packageRepositoriesManager).toBe(PackageRepositoriesManager);
    expect($scope.repositories).toBe(PackageRepositoriesManager.getItems());
    expect($scope.newRepository).toBeNull();
    expect($scope.editRepository).toBeNull();
    expect($scope.deleteRepository).toBeNull();
  });

  it("sets the values for 'dhcp' section", function() {
    $routeParams.section = "dhcp";
    makeController();
    expect($scope.title).toBe("DHCP snippets");
    expect($scope.currentpage).toBe("dhcp");
  });

  it("sets the values for 'repositories' section", function() {
    $routeParams.section = "repositories";
    makeController();
    expect($scope.title).toBe("Package repositories");
    expect($scope.currentpage).toBe("repositories");
  });

  it("calls loadManagers with all needed managers", function() {
    makeController();
    expect(ManagerHelperService.loadManagers).toHaveBeenCalledWith($scope, [
      PackageRepositoriesManager,
      DHCPSnippetsManager,
      MachinesManager,
      DevicesManager,
      ControllersManager,
      SubnetsManager,
      GeneralManager
    ]);
  });

  it("sets loading to false", function() {
    var defer = $q.defer();
    makeController(defer);
    defer.resolve();
    $scope.$digest();
    expect($scope.loading).toBe(false);
  });

  describe("repositoryEnabledToggle", function() {
    it("calls updateItem", function() {
      makeController();
      var repository = makeRepo();
      spyOn(PackageRepositoriesManager, "updateItem");
      $scope.repositoryEnabledToggle(repository);
      expect(PackageRepositoriesManager.updateItem).toHaveBeenCalledWith(
        repository
      );
    });
  });

  describe("repositoryEnterRemove", function() {
    it("clears new and edit and sets delete", function() {
      makeController();
      var repository = makeRepo();
      $scope.newRepository = {};
      $scope.editRepository = {};
      $scope.repositoryEnterRemove(repository);
      expect($scope.newRepository).toBeNull();
      expect($scope.editRepository).toBeNull();
      expect($scope.deleteRepository).toBe(repository);
    });
  });

  describe("repositoryExitRemove", function() {
    it("clears deleteRepository", function() {
      makeController();
      $scope.deleteRepository = {};
      $scope.repositoryExitRemove();
      expect($scope.deleteRepository).toBeNull();
    });
  });

  describe("repositoryConfirmRemove", function() {
    it("calls deleteItem and then repositoryExitRemove", function() {
      makeController();
      var repository = makeRepo();
      var defer = $q.defer();
      spyOn(PackageRepositoriesManager, "deleteItem").and.returnValue(
        defer.promise
      );
      spyOn($scope, "repositoryExitRemove");
      $scope.deleteRepository = repository;
      $scope.repositoryConfirmRemove();
      expect(PackageRepositoriesManager.deleteItem).toHaveBeenCalledWith(
        repository
      );
      defer.resolve();
      $scope.$digest();
      expect($scope.repositoryExitRemove).toHaveBeenCalled();
    });
  });

  describe("isPPA", function() {
    it("false when not object", function() {
      makeController();
      expect($scope.isPPA(null)).toBe(false);
    });

    it("false when no url", function() {
      makeController();
      expect(
        $scope.isPPA({
          url: null
        })
      ).toBe(false);
    });

    it("true when url startswith", function() {
      makeController();
      expect(
        $scope.isPPA({
          url: "ppa:"
        })
      ).toBe(true);
    });

    it("true when url contains ppa.launchpad.net", function() {
      makeController();
      expect(
        $scope.isPPA({
          url: "http://ppa.launchpad.net/"
        })
      ).toBe(true);
    });
  });

  describe("isMirror", function() {
    it("false when not object", function() {
      makeController();
      expect($scope.isMirror(null)).toBe(false);
    });

    it("false when no name", function() {
      makeController();
      expect(
        $scope.isMirror({
          name: null
        })
      ).toBe(false);
    });

    it("true when name is 'main_archive'", function() {
      makeController();
      expect(
        $scope.isMirror({
          name: "main_archive"
        })
      ).toBe(true);
    });

    it("true when name is 'ports_archive'", function() {
      makeController();
      expect(
        $scope.isMirror({
          name: "ports_archive"
        })
      ).toBe(true);
    });
  });

  describe("repositoryEnterEdit", function() {
    it("clears new and delete and sets edit", function() {
      makeController();
      var repository = makeRepo();
      $scope.newRepository = {};
      $scope.deleteRepository = {};
      $scope.repositoryEnterEdit(repository);
      expect($scope.editRepository).toBe(repository);
      expect($scope.newRepository).toBeNull();
      expect($scope.deleteRepository).toBeNull();
    });
  });

  describe("repositoryExitEdit", function() {
    it("clears edit", function() {
      makeController();
      $scope.editRepository = {};
      $scope.repositoryExitEdit();
      expect($scope.editRepository).toBeNull();
    });
  });

  describe("repositoryAdd", function() {
    it("sets newRepository for ppa", function() {
      makeController();
      $scope.repositoryAdd(true);
      expect($scope.newRepository).toEqual({
        name: "",
        enabled: true,
        url: "ppa:",
        key: "",
        arches: ["i386", "amd64"],
        distributions: [],
        components: []
      });
    });

    it("sets newRepository not for ppa", function() {
      makeController();
      $scope.repositoryAdd(false);
      expect($scope.newRepository).toEqual({
        name: "",
        enabled: true,
        url: "",
        key: "",
        arches: ["i386", "amd64"],
        distributions: [],
        components: []
      });
    });
  });

  describe("repositoryAddCancel", function() {
    it("newRepository gets cleared", function() {
      makeController();
      $scope.newRepository = {};
      $scope.repositoryAddCancel();
      expect($scope.newRepository).toBeNull();
    });
  });
});
