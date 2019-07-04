/* Copyright 2015-2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for AddHardwareController.
 */

import { makeName } from "testing/utils";
import MockWebSocket from "testing/websocket";

describe("AddHardwareController", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Grab the needed angular pieces.
  var $controller, $rootScope, $timeout, $http, $q;
  beforeEach(inject(function($injector) {
    $controller = $injector.get("$controller");
    $rootScope = $injector.get("$rootScope");
    $timeout = $injector.get("$timeout");
    $http = $injector.get("$http");
    $q = $injector.get("$q");
  }));

  // Load the ZonesManager, ResourcePoolsManager, MachinesManager,
  // RegionConnection, DomainManager, and mock the websocket connection.
  var ZonesManager,
    ResourcePoolsManager,
    MachinesManager,
    GeneralManager,
    DomainsManager;
  var RegionConnection, ManagerHelperService, webSocket;
  beforeEach(inject(function($injector) {
    ZonesManager = $injector.get("ZonesManager");
    ResourcePoolsManager = $injector.get("ResourcePoolsManager");
    MachinesManager = $injector.get("MachinesManager");
    GeneralManager = $injector.get("GeneralManager");
    DomainsManager = $injector.get("DomainsManager");
    RegionConnection = $injector.get("RegionConnection");
    ManagerHelperService = $injector.get("ManagerHelperService");

    // Mock buildSocket so an actual connection is not made.
    webSocket = new MockWebSocket();
    spyOn(RegionConnection, "buildSocket").and.returnValue(webSocket);
  }));

  // Create the parent scope and the scope for the controller.
  var parentScope, $scope;
  beforeEach(function() {
    parentScope = $rootScope.$new();
    parentScope.addHardwareScope = null;
    $scope = parentScope.$new();
  });

  // Makes the AddHardwareController
  function makeController(loadManagersDefer, loadItemsDefer) {
    var loadManagers = spyOn(ManagerHelperService, "loadManagers");
    if (angular.isObject(loadManagersDefer)) {
      loadManagers.and.returnValue(loadManagersDefer.promise);
    } else {
      loadManagers.and.returnValue($q.defer().promise);
    }

    var loadItems = spyOn(GeneralManager, "loadItems");
    if (angular.isObject(loadItemsDefer)) {
      loadItems.and.returnValue(loadItemsDefer.promise);
    } else {
      loadItems.and.returnValue($q.defer().promise);
    }

    // Start the connection so a valid websocket is created in the
    // RegionConnection.
    RegionConnection.connect("");

    var controller = $controller("AddHardwareController", {
      $scope: $scope,
      $timeout: $timeout,
      $http: $http,
      ZonesManager: ZonesManager,
      ResourcePoolsManager: ResourcePoolsManager,
      MachinesManager: MachinesManager,
      GeneralManager: GeneralManager,
      DomainsManager: DomainsManager,
      RegionConnection: RegionConnection,
      ManagerHelperService: ManagerHelperService
    });
    return controller;
  }

  // Makes the AddHardwareController with the $scope.machine already
  // initialized.
  function makeControllerWithMachine() {
    var loadManagers_defer = $q.defer();
    var loadItems_defer = $q.defer();
    var controller = makeController(loadManagers_defer, loadItems_defer);
    $scope.show();
    loadManagers_defer.resolve();
    loadItems_defer.resolve();
    $rootScope.$digest();
    return controller;
  }

  it("sets addHardwareScope on $scope.$parent", function() {
    makeController();
    expect(parentScope.addHardwareScope).toBe($scope);
  });

  it("sets initial values on $scope", function() {
    makeController();
    expect($scope.viewable).toBe(false);
    expect($scope.zones).toBe(ZonesManager.getItems());
    expect($scope.pools).toBe(ResourcePoolsManager.getItems());
    expect($scope.domains).toBe(DomainsManager.getItems());
    expect($scope.architectures).toEqual(["Choose an architecture"]);
    expect($scope.hwe_kernels).toEqual([]);
    expect($scope.power_types).toEqual([]);
    expect($scope.error).toBeNull();
    expect($scope.machine).toBeNull();
    expect($scope.chassis).toBeNull();
  });

  it("doesn't call loadManagers when initialized", function() {
    // add_hardware is loaded on the listing and details page. Managers
    // should be loaded when shown. Otherwise all Zones and Domains are
    // loaded and updated even though they are not needed.
    makeController();
    expect(ManagerHelperService.loadManagers).not.toHaveBeenCalled();
  });

  it("initializes machine architecture with first arch", function() {
    var loadManagers_defer = $q.defer();
    var loadItems_defer = $q.defer();
    makeController(loadManagers_defer, loadItems_defer);
    var arch = makeName("arch");
    $scope.architectures = [arch];
    $scope.machine = {
      architecture: "",
      power: { type: makeName("power_type") }
    };
    $scope.show();

    loadManagers_defer.resolve();
    loadItems_defer.resolve();
    $scope.$digest();
    expect($scope.machine.architecture).toEqual(arch);
  });

  it("initializes machine arch with amd64 arch", function() {
    var loadManagers_defer = $q.defer();
    var loadItems_defer = $q.defer();
    makeController(loadManagers_defer, loadItems_defer);
    var arch = makeName("arch");
    $scope.architectures = [arch, "amd64/generic"];
    $scope.machine = {
      architecture: "",
      power: { type: makeName("power_type") }
    };
    $scope.show();

    loadManagers_defer.resolve();
    loadItems_defer.resolve();
    $scope.$digest();
    expect($scope.machine.architecture).toEqual("amd64/generic");
  });

  it("doesnt initializes machine architecture if set", function() {
    var loadManagers_defer = $q.defer();
    var loadItems_defer = $q.defer();
    makeController(loadManagers_defer, loadItems_defer);
    var arch = makeName("arch");
    var newArch = makeName("arch");
    $scope.architectures = [newArch];
    $scope.machine = {
      architecture: arch,
      power: { type: makeName("power_type") }
    };
    $scope.show();

    loadManagers_defer.resolve();
    loadItems_defer.resolve();
    $scope.$digest();
    expect($scope.machine.architecture).toEqual(arch);
  });

  it("initializes machine min_hwe_kernel with hwe-t", function() {
    var loadManagers_defer = $q.defer();
    var loadItems_defer = $q.defer();
    makeController(loadManagers_defer, loadItems_defer);
    var arch = makeName("arch");
    var min_hwe_kernel = "hwe-t";
    $scope.architectures = [arch];
    $scope.machine = {
      architecture: "",
      min_hwe_kernel: min_hwe_kernel,
      power: { type: makeName("power_type") }
    };
    $scope.show();

    loadManagers_defer.resolve();
    loadItems_defer.resolve();
    $scope.$digest();
    expect($scope.machine.min_hwe_kernel).toEqual(min_hwe_kernel);
  });

  describe("show", function() {
    it("sets viewable to true", function() {
      var loadItems_defer = $q.defer();
      var loadManagers_defer = $q.defer();
      makeController(loadManagers_defer, loadItems_defer);
      $scope.show();

      loadItems_defer.resolve();
      loadManagers_defer.resolve();
      $rootScope.$digest();
      expect($scope.viewable).toBe(true);
    });

    it("reloads arches and kernels", function() {
      var loadItems_defer = $q.defer();
      var loadManagers_defer = $q.defer();
      makeController(loadManagers_defer, loadItems_defer);
      $scope.show();

      loadItems_defer.resolve();
      loadManagers_defer.resolve();
      $rootScope.$digest();
      expect(GeneralManager.loadItems).toHaveBeenCalledWith([
        "architectures",
        "hwe_kernels",
        "default_min_hwe_kernel"
      ]);
    });

    it("calls loadManagers with ZonesManager, DomainsManager", function() {
      var loadItems_defer = $q.defer();
      var loadManagers_defer = $q.defer();
      makeController(loadManagers_defer, loadItems_defer);
      $scope.show();

      loadItems_defer.resolve();
      loadManagers_defer.resolve();
      $rootScope.$digest();
      expect(ManagerHelperService.loadManagers).toHaveBeenCalledWith($scope, [
        ZonesManager,
        DomainsManager
      ]);
    });

    it(`initializes machine/chassis when
        Zones/Domains manager loaded`, function() {
      var loadItems_defer = $q.defer();
      var loadManagers_defer = $q.defer();
      makeController(loadManagers_defer, loadItems_defer);
      $scope.show();

      loadItems_defer.resolve();
      loadManagers_defer.resolve();
      $rootScope.$digest();
      expect($scope.machine).not.toBeNull();
      expect($scope.chassis).not.toBeNull();
    });
  });

  describe("hide", function() {
    it("sets viewable to false", function() {
      makeController();
      $scope.viewable = true;
      $scope.hide();
      expect($scope.viewable).toBe(false);
    });

    it("emits addHardwareHidden event", function(done) {
      makeController();
      $scope.$on("addHardwareHidden", function() {
        done();
      });
      $scope.hide();
    });

    it("unloadManagers", function() {
      var unloadManagers = spyOn(ManagerHelperService, "unloadManagers");
      makeController();
      $scope.viewable = true;
      $scope.hide();
      expect(unloadManagers).toHaveBeenCalledWith($scope, [
        ZonesManager,
        DomainsManager
      ]);
    });
  });

  describe("addMac", function() {
    it("adds mac address object to machine", function() {
      makeControllerWithMachine();
      $scope.addMac();
      expect($scope.machine.macs.length).toBe(2);
    });
  });

  describe("removeMac", function() {
    it("removes mac address object from machine", function() {
      makeControllerWithMachine();
      $scope.addMac();
      var mac = $scope.machine.macs[1];
      $scope.removeMac(mac);
      expect($scope.machine.macs.length).toBe(1);
    });

    it("ignores second remove if mac object removed again", function() {
      makeControllerWithMachine();
      $scope.addMac();
      var mac = $scope.machine.macs[1];
      $scope.removeMac(mac);
      $scope.removeMac(mac);
      expect($scope.machine.macs.length).toBe(1);
    });
  });

  describe("invalidName", function() {
    it("return false if machine name empty", function() {
      makeControllerWithMachine();
      expect($scope.invalidName($scope.machine)).toBe(false);
    });

    it("return false if machine name valid", function() {
      makeControllerWithMachine();
      $scope.machine.name = "abc";
      expect($scope.invalidName($scope.machine)).toBe(false);
    });

    it("return true if machine name invalid", function() {
      makeControllerWithMachine();
      $scope.machine.name = "ab_c.local";
      expect($scope.invalidName($scope.machine)).toBe(true);
    });
  });

  describe("validateMac", function() {
    it("sets error to false if blank", function() {
      makeController();
      var mac = {
        mac: "",
        error: true
      };
      $scope.validateMac(mac);
      expect(mac.error).toBe(false);
    });

    it("sets error to true if invalid", function() {
      makeController();
      var mac = {
        mac: "00:11:22",
        error: false
      };
      $scope.validateMac(mac);
      expect(mac.error).toBe(true);
    });

    it("sets error to false if valid", function() {
      makeController();
      var mac = {
        mac: "00:11:22:33:44:55",
        error: true
      };
      $scope.validateMac(mac);
      expect(mac.error).toBe(false);
    });
  });

  describe("machineHasError", function() {
    it("returns true if machine is null", function() {
      makeControllerWithMachine();
      $scope.machine = null;
      expect($scope.machineHasError()).toBe(true);
    });

    it("returns true if zone is null", function() {
      makeControllerWithMachine();
      $scope.machine.zone = null;
      $scope.machine.pool = null;
      $scope.machine.architecture = makeName("arch");
      $scope.machine.power.type = {};
      $scope.machine.macs[0].mac = "00:11:22:33:44:55";
      $scope.machine.macs[0].error = false;
      expect($scope.machineHasError()).toBe(true);
    });

    it("returns true if architecture is not chosen", function() {
      makeControllerWithMachine();
      $scope.machine.zone = {};
      $scope.machine.pool = {};
      $scope.machine.architecture = "Choose an architecture";
      $scope.machine.power.type = {};
      $scope.machine.macs[0].mac = "00:11:22:33:44:55";
      $scope.machine.macs[0].error = false;
      expect($scope.machineHasError()).toBe(true);
    });

    it("returns true if power.type is null", function() {
      makeControllerWithMachine();
      $scope.machine.zone = {};
      $scope.machine.architecture = makeName("arch");
      $scope.machine.power.type = null;
      $scope.machine.macs[0].mac = "00:11:22:33:44:55";
      $scope.machine.macs[0].error = false;
      expect($scope.machineHasError()).toBe(true);
    });

    it("returns true if machine.name invalid", function() {
      makeControllerWithMachine();
      $scope.machine.zone = {};
      $scope.machine.architecture = makeName("arch");
      $scope.machine.name = "ab_c.local";
      $scope.machine.power.type = {};
      $scope.machine.macs[0].mac = "00:11:22:33:44:55";
      $scope.machine.macs[0].error = false;
      expect($scope.machineHasError()).toBe(true);
    });

    it("returns true if mac[0] is empty", function() {
      makeControllerWithMachine();
      $scope.machine.zone = {};
      $scope.machine.architecture = makeName("arch");
      $scope.machine.power.type = {};
      $scope.machine.macs[0].mac = "";
      $scope.machine.macs[0].error = false;
      expect($scope.machineHasError()).toBe(true);
    });

    it("returns true if mac[0] is in error", function() {
      makeControllerWithMachine();
      $scope.machine.zone = {};
      $scope.machine.architecture = makeName("arch");
      $scope.machine.power.type = {};
      $scope.machine.macs[0].mac = "00:11:22:33:44";
      $scope.machine.macs[0].error = true;
      expect($scope.machineHasError()).toBe(true);
    });

    it("returns true if mac[1] is in error", function() {
      makeControllerWithMachine();
      $scope.machine.zone = {};
      $scope.machine.architecture = makeName("arch");
      $scope.machine.power.type = {};
      $scope.machine.macs[0].mac = "00:11:22:33:44:55";
      $scope.machine.macs[0].error = false;
      $scope.machine.macs.push({
        mac: "00:11:22:33:55",
        error: true
      });
      expect($scope.machineHasError()).toBe(true);
    });

    it("returns false if all is correct", function() {
      makeControllerWithMachine();
      $scope.machine.zone = {};
      $scope.machine.pool = {};
      $scope.machine.architecture = makeName("arch");
      $scope.machine.power.type = {};
      $scope.machine.macs[0].mac = "00:11:22:33:44:55";
      $scope.machine.macs[0].error = false;
      expect($scope.machineHasError()).toBe(false);
    });

    it("returns false if all is correct and mac[1] is blank", function() {
      makeControllerWithMachine();
      $scope.machine.zone = {};
      $scope.machine.pool = {};
      $scope.machine.architecture = makeName("arch");
      $scope.machine.power.type = {};
      $scope.machine.macs[0].mac = "00:11:22:33:44:55";
      $scope.machine.macs[0].error = false;
      $scope.machine.macs.push({
        mac: "",
        error: false
      });
      expect($scope.machineHasError()).toBe(false);
    });
  });

  describe("chassisHasErrors", function() {
    it("returns true if chassis is null", function() {
      makeController();
      $scope.chassis = null;
      expect($scope.chassisHasErrors()).toBe(true);
    });

    it("returns true if power.type is null", function() {
      makeController();
      $scope.chassis = {
        power: {
          type: null,
          parameters: {}
        }
      };
      expect($scope.chassisHasErrors()).toBe(true);
    });

    it("returns true if power.parameters is invalid", function() {
      makeController();
      $scope.chassis = {
        power: {
          type: {
            fields: [
              {
                name: "test",
                required: true
              }
            ]
          },
          parameters: {
            test: ""
          }
        }
      };
      expect($scope.chassisHasErrors()).toBe(true);
    });

    it("returns false if all valid", function() {
      makeController();
      $scope.chassis = {
        power: {
          type: {
            fields: [
              {
                name: "test",
                required: true
              }
            ]
          },
          parameters: {
            test: "data"
          }
        }
      };
      expect($scope.chassisHasErrors()).toBe(false);
    });
  });

  describe("cancel", function() {
    it("clears error", function() {
      makeControllerWithMachine();
      $scope.error = makeName("error");
      $scope.cancel();

      expect($scope.showErrors).toEqual(false);
    });

    it("clears machine and adds a new one", function() {
      makeControllerWithMachine();
      $scope.machine.name = makeName("name");
      $scope.cancel();
      expect($scope.machine.name).toBe("");
    });

    it("clears chassis and adds a new one", function() {
      makeControllerWithMachine();
      $scope.chassis.power.type = makeName("type");
      $scope.cancel();
      expect($scope.chassis.power.type).toBeNull();
    });

    it("calls hide", function() {
      makeControllerWithMachine();
      spyOn($scope, "hide");
      $scope.cancel();
      expect($scope.hide).toHaveBeenCalled();
    });
  });

  describe("saveMachine", function() {
    // Setup a valid machine before each test.
    beforeEach(function() {
      makeControllerWithMachine();

      $scope.addMac();
      $scope.machine.name = makeName("name").replace("_", "");
      $scope.machine.domain = makeName("domain").replace("_", "");
      $scope.machine.zone = {
        id: 1,
        name: makeName("zone")
      };
      $scope.machine.pool = {
        id: 2,
        name: makeName("pool")
      };
      $scope.machine.architecture = makeName("arch");
      $scope.machine.power.type = {
        name: "virsh"
      };
      $scope.machine.power.parameters = {
        mac_address: "00:11:22:33:44:55"
      };
      $scope.machine.macs[0].mac = "00:11:22:33:44:55";
      $scope.machine.macs[0].error = false;
      $scope.machine.macs[1].mac = "00:11:22:33:44:66";
      $scope.machine.macs[1].error = false;
    });

    it("Converts power and macs to machine protocol", function() {
      $scope.saveMachine(false);
      $rootScope.$digest();

      expect($scope.newMachineObj).toEqual({
        name: $scope.machine.name,
        domain: $scope.machine.domain,
        architecture: $scope.machine.architecture,
        min_hwe_kernel: $scope.machine.min_hwe_kernel,
        pxe_mac: $scope.machine.macs[0].mac,
        extra_macs: [$scope.machine.macs[1].mac],
        power_type: $scope.machine.power.type.name,
        power_parameters: $scope.machine.power.parameters,
        zone: $scope.machine.zone,
        pool: $scope.machine.pool
      });
    });

    it("calls hide once the maas-form's after-save is called", function() {
      spyOn($scope, "hide");
      $scope.afterSaveMachine();
      $rootScope.$digest();

      expect($scope.hide).toHaveBeenCalled();
    });

    it("resets machine once the maas-form's after-save is called", function() {
      $scope.afterSaveMachine();
      $rootScope.$digest();

      expect($scope.machine.name).toBe("");
    });

    it("clones machine once after-save is called with addAnother", function() {
      $scope.saveMachine(true);
      $rootScope.$digest();
      $scope.afterSaveMachine();
      $rootScope.$digest();

      expect($scope.machine.name).toBe("");
    });

    it("doesn't call hide if addAnother is true", function() {
      spyOn($scope, "hide");
      $scope.saveMachine(true);
      $rootScope.$digest();
      $scope.afterSaveMachine();
      $rootScope.$digest();

      expect($scope.hide).not.toHaveBeenCalled();
    });
  });

  describe("saveChassis", function() {
    // Setup a valid chassis before each test.
    var httpDefer;
    beforeEach(function() {
      httpDefer = $q.defer();

      // Mock $http.
      $http = jasmine.createSpy("$http");
      $http.and.returnValue(httpDefer.promise);

      // Create the controller and the valid chassis.
      makeController();
      $scope.chassis = {
        domain: makeName("domain"),
        power: {
          type: {
            name: makeName("model"),
            fields: [
              {
                name: "one",
                required: true
              },
              {
                name: "one",
                required: true
              }
            ]
          },
          parameters: {
            one: makeName("one"),
            two: makeName("two")
          }
        }
      };
    });

    it("does nothing if errors", function() {
      var error = makeName("error");
      $scope.error = error;
      spyOn($scope, "chassisHasErrors").and.returnValue(true);
      $scope.saveChassis(false);
      expect($scope.error).toBe(error);
    });

    it("calls $http with correct parameters", function() {
      $scope.saveChassis(false);

      var parameters = $scope.chassis.power.parameters;
      parameters.chassis_type = $scope.chassis.power.type.name;
      parameters.domain = $scope.chassis.domain.name;
      expect($http).toHaveBeenCalledWith({
        method: "POST",
        url: "api/2.0/machines/?op=add_chassis",
        data: $.param(parameters),
        headers: {
          "Content-Type": "application/x-www-form-urlencoded"
        }
      });
    });

    it("creates new chassis when $http resolves", function() {
      $scope.saveChassis(false);
      httpDefer.resolve();
      $rootScope.$digest();

      expect($scope.chassis.power.type).toBeNull();
    });

    it("calls hide if addAnother false when $http resolves", function() {
      spyOn($scope, "hide");
      $scope.saveChassis(false);
      httpDefer.resolve();
      $rootScope.$digest();

      expect($scope.hide).toHaveBeenCalled();
    });

    it("doesnt call hide if addAnother true when $http resolves", function() {
      spyOn($scope, "hide");
      $scope.saveChassis(true);
      httpDefer.resolve();
      $rootScope.$digest();

      expect($scope.hide).not.toHaveBeenCalled();
    });

    it("sets error when $http rejects", function() {
      $scope.saveChassis(false);
      var error = { data: makeName("error") };
      httpDefer.reject(error);
      $rootScope.$digest();

      expect($scope.error).toBe(error.data);
    });
  });
});
