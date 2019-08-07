/* Copyright 2015-2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for GeneralManager.
 */

import { makeName } from "testing/utils";
import MockWebSocket from "testing/websocket";

describe("GeneralManager", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Grab the needed angular pieces.
  var $rootScope, $timeout, $q;
  beforeEach(inject(function($injector) {
    $rootScope = $injector.get("$rootScope");
    $timeout = $injector.get("$timeout");
    $q = $injector.get("$q");
  }));

  // Load the GeneralManager, RegionConnection, and ErrorService factory.
  var GeneralManager, RegionConnection, ErrorService, webSocket;
  beforeEach(inject(function($injector) {
    GeneralManager = $injector.get("GeneralManager");
    RegionConnection = $injector.get("RegionConnection");
    ErrorService = $injector.get("ErrorService");

    // Mock buildSocket so an actual connection is not made.
    webSocket = new MockWebSocket();
    spyOn(RegionConnection, "buildSocket").and.returnValue(webSocket);
  }));

  // Open the connection to the region before each test.
  beforeEach(function(done) {
    RegionConnection.registerHandler("open", function() {
      done();
    });
    RegionConnection.connect("");
  });

  it("sets timeout values", function() {
    expect(GeneralManager._pollTimeout).toBe(10000);
    expect(GeneralManager._pollErrorTimeout).toBe(3000);
    expect(GeneralManager._pollEmptyTimeout).toBe(3000);
  });

  it("autoReload off by default", function() {
    expect(GeneralManager._autoReload).toBe(false);
  });

  it("_data has expected keys", function() {
    expect(Object.keys(GeneralManager._data)).toEqual([
      "machine_actions",
      "device_actions",
      "region_controller_actions",
      "rack_controller_actions",
      "region_and_rack_controller_actions",
      "architectures",
      "known_architectures",
      "pockets_to_disable",
      "components_to_disable",
      "hwe_kernels",
      "min_hwe_kernels",
      "default_min_hwe_kernel",
      "osinfo",
      "bond_options",
      "version",
      "power_types",
      "release_options"
    ]);
  });

  it("_data.machine_actions has correct data", function() {
    var machine_actions = GeneralManager._data.machine_actions;
    expect(machine_actions.method).toBe("general.machine_actions");
    expect(machine_actions.data).toEqual([]);
    expect(machine_actions.loaded).toBe(false);
    expect(machine_actions.polling).toEqual([]);
    expect(machine_actions.nextPromise).toBeNull();
  });

  it("_data.device_actions has correct data", function() {
    var device_actions = GeneralManager._data.device_actions;
    expect(device_actions.method).toBe("general.device_actions");
    expect(device_actions.data).toEqual([]);
    expect(device_actions.loaded).toBe(false);
    expect(device_actions.polling).toEqual([]);
    expect(device_actions.nextPromise).toBeNull();
  });

  it("_data.region_controller_actions has correct data", function() {
    var region_controller_actions =
      GeneralManager._data.region_controller_actions;
    expect(region_controller_actions.method).toBe(
      "general.region_controller_actions"
    );
    expect(region_controller_actions.data).toEqual([]);
    expect(region_controller_actions.loaded).toBe(false);
    expect(region_controller_actions.polling).toEqual([]);
    expect(region_controller_actions.nextPromise).toBeNull();
  });

  it("_data.rack_controller_actions has correct data", function() {
    var rack_controller_actions = GeneralManager._data.rack_controller_actions;
    expect(rack_controller_actions.method).toBe(
      "general.rack_controller_actions"
    );
    expect(rack_controller_actions.data).toEqual([]);
    expect(rack_controller_actions.loaded).toBe(false);
    expect(rack_controller_actions.polling).toEqual([]);
    expect(rack_controller_actions.nextPromise).toBeNull();
  });

  it("_data.region_and_rack_controller_actions has correct data", function() {
    var region_and_rack_controller_actions =
      GeneralManager._data.region_and_rack_controller_actions;
    expect(region_and_rack_controller_actions.method).toBe(
      "general.region_and_rack_controller_actions"
    );
    expect(region_and_rack_controller_actions.data).toEqual([]);
    expect(region_and_rack_controller_actions.loaded).toBe(false);
    expect(region_and_rack_controller_actions.polling).toEqual([]);
    expect(region_and_rack_controller_actions.nextPromise).toBeNull();
  });

  it("_data.architectures has correct data", function() {
    var architectures = GeneralManager._data.architectures;
    expect(architectures.method).toBe("general.architectures");
    expect(architectures.data).toEqual([]);
    expect(architectures.loaded).toBe(false);
    expect(architectures.polling).toEqual([]);
    expect(architectures.nextPromise).toBeNull();
  });

  it("_data.known_architectures has correct data", function() {
    var ka = GeneralManager._data.known_architectures;
    expect(ka.method).toBe("general.known_architectures");
    expect(ka.data).toEqual([]);
    expect(ka.loaded).toBe(false);
    expect(ka.polling).toEqual([]);
    expect(ka.nextPromise).toBeNull();
  });

  it("_data.pockets_to_disable has correct data", function() {
    var ptd = GeneralManager._data.pockets_to_disable;
    expect(ptd.method).toBe("general.pockets_to_disable");
    expect(ptd.data).toEqual([]);
    expect(ptd.loaded).toBe(false);
    expect(ptd.polling).toEqual([]);
    expect(ptd.nextPromise).toBeNull();
  });

  it("_data.components_to_disable has correct data", function() {
    var ptd = GeneralManager._data.components_to_disable;
    expect(ptd.method).toBe("general.components_to_disable");
    expect(ptd.data).toEqual([]);
    expect(ptd.loaded).toBe(false);
    expect(ptd.polling).toEqual([]);
    expect(ptd.nextPromise).toBeNull();
  });

  it("_data.hwe_kernels has correct data", function() {
    var hwe_kernels = GeneralManager._data.hwe_kernels;
    expect(hwe_kernels.method).toBe("general.hwe_kernels");
    expect(hwe_kernels.data).toEqual([]);
    expect(hwe_kernels.loaded).toBe(false);
    expect(hwe_kernels.polling).toEqual([]);
    expect(hwe_kernels.nextPromise).toBeNull();
  });

  it("_data.default_min_hwe_kernels has correct data", function() {
    var default_min_hwe_kernel = GeneralManager._data.default_min_hwe_kernel;
    expect(default_min_hwe_kernel.method).toBe(
      "general.default_min_hwe_kernel"
    );
    expect(default_min_hwe_kernel.data).toEqual({ text: "" });
    expect(default_min_hwe_kernel.loaded).toBe(false);
    expect(default_min_hwe_kernel.polling).toEqual([]);
    expect(default_min_hwe_kernel.nextPromise).toBeNull();
  });

  it("_data.osinfo has correct data", function() {
    var osinfo = GeneralManager._data.osinfo;
    expect(osinfo.method).toBe("general.osinfo");
    expect(osinfo.data).toEqual({});
    expect(osinfo.loaded).toBe(false);
    expect(osinfo.polling).toEqual([]);
    expect(osinfo.nextPromise).toBeNull();
    expect(angular.isFunction(osinfo.isEmpty)).toBe(true);
    expect(angular.isFunction(osinfo.replaceData)).toBe(true);
  });

  it("_data.bond_options has correct data", function() {
    var bond_options = GeneralManager._data.bond_options;
    expect(bond_options.method).toBe("general.bond_options");
    expect(bond_options.data).toEqual({});
    expect(bond_options.loaded).toBe(false);
    expect(bond_options.polling).toEqual([]);
    expect(bond_options.nextPromise).toBeNull();
    expect(angular.isFunction(bond_options.replaceData)).toBe(true);
  });

  it("_data.version has correct data", function() {
    var version = GeneralManager._data.version;
    expect(version.method).toBe("general.version");
    expect(version.data).toEqual({ text: null });
    expect(version.loaded).toBe(false);
    expect(version.polling).toEqual([]);
    expect(version.nextPromise).toBeNull();
    expect(angular.isFunction(version.replaceData)).toBe(true);
  });

  it("_data.power_types has correct data", function() {
    var power_types = GeneralManager._data.power_types;
    expect(power_types.method).toBe("general.power_types");
    expect(power_types.data).toEqual([]);
    expect(power_types.loaded).toBe(false);
    expect(power_types.polling).toEqual([]);
    expect(power_types.nextPromise).toBeNull();
    expect(angular.isFunction(power_types.replaceData)).toBe(true);
  });

  it("_data.release_options has correct data", function() {
    var release_options = GeneralManager._data.release_options;
    expect(release_options.method).toBe("general.release_options");
    expect(release_options.data).toEqual({});
    expect(release_options.loaded).toBe(false);
    expect(release_options.polling).toEqual([]);
    expect(release_options.nextPromise).toBeNull();
    expect(angular.isFunction(release_options.replaceData)).toBe(true);
  });

  describe("_data.power_types.replaceData", function() {
    var power_types, data, replaceData;
    beforeEach(function() {
      power_types = GeneralManager._data.power_types;
      data = power_types.data;
      replaceData = power_types.replaceData;
    });

    it("adds new power_type to array", function() {
      var newPowerType = {
        name: makeName("power")
      };
      replaceData(data, [newPowerType]);
      expect(data).toEqual([newPowerType]);
    });

    it("doesnt update power_type in array to be same object", function() {
      var oldPowerType = {
        name: makeName("power"),
        fields: [
          {
            name: makeName("field")
          }
        ]
      };
      replaceData(data, [oldPowerType]);
      var newPowerType = {
        name: oldPowerType.name,
        fields: [
          {
            name: makeName("field")
          }
        ]
      };
      replaceData(data, [newPowerType]);
      expect(data).not.toEqual([newPowerType]);
      expect(data[0]).toEqual(oldPowerType);
      expect(data[0]).toBe(oldPowerType);
    });

    it("removes missing power_types from array", function() {
      var oldPowerType = {
        name: makeName("power"),
        fields: [
          {
            name: makeName("field")
          }
        ]
      };
      replaceData(data, [oldPowerType]);
      replaceData(data, []);
      expect(data).toEqual([]);
    });
  });

  describe("_getInternalData", function() {
    it("raises error for unknown data", function() {
      var name = makeName("name");
      expect(function() {
        GeneralManager._getInternalData(name);
      }).toThrow(new Error("Unknown data: " + name));
    });

    it("returns data object", function() {
      expect(GeneralManager._getInternalData("machine_actions")).toBe(
        GeneralManager._data.machine_actions
      );
    });
  });

  describe("getData", function() {
    it("returns data from internal data", function() {
      expect(GeneralManager.getData("machine_actions")).toBe(
        GeneralManager._data.machine_actions.data
      );
    });
  });

  describe("isLoaded", function() {
    it("returns false if all false", function() {
      expect(GeneralManager.isLoaded()).toBe(false);
    });

    it("returns false if one false", function() {
      GeneralManager._data.machine_actions.loaded = true;
      GeneralManager._data.device_actions.loaded = true;
      GeneralManager._data.rack_controller_actions.loaded = true;
      GeneralManager._data.region_controller_actions.loaded = true;
      GeneralManager._data.region_and_rack_controller_actions.loaded = true;
      GeneralManager._data.architectures.loaded = true;
      GeneralManager._data.known_architectures.loaded = true;
      GeneralManager._data.pockets_to_disable.loaded = true;
      GeneralManager._data.components_to_disable.loaded = true;
      GeneralManager._data.hwe_kernels.loaded = true;
      GeneralManager._data.osinfo.loaded = true;
      GeneralManager._data.bond_options.loaded = true;
      GeneralManager._data.version.loaded = true;
      GeneralManager._data.power_types.loaded = true;
      GeneralManager._data.release_options.loaded = false;
      expect(GeneralManager.isLoaded()).toBe(false);
    });

    it("returns true if all true", function() {
      GeneralManager._data.machine_actions.loaded = true;
      GeneralManager._data.device_actions.loaded = true;
      GeneralManager._data.rack_controller_actions.loaded = true;
      GeneralManager._data.region_controller_actions.loaded = true;
      GeneralManager._data.region_and_rack_controller_actions.loaded = true;
      GeneralManager._data.architectures.loaded = true;
      GeneralManager._data.known_architectures.loaded = true;
      GeneralManager._data.pockets_to_disable.loaded = true;
      GeneralManager._data.components_to_disable.loaded = true;
      GeneralManager._data.hwe_kernels.loaded = true;
      GeneralManager._data.min_hwe_kernels.loaded = true;
      GeneralManager._data.default_min_hwe_kernel.loaded = true;
      GeneralManager._data.osinfo.loaded = true;
      GeneralManager._data.bond_options.loaded = true;
      GeneralManager._data.version.loaded = true;
      GeneralManager._data.power_types.loaded = true;
      GeneralManager._data.release_options.loaded = true;
      expect(GeneralManager.isLoaded()).toBe(true);
    });
  });

  describe("isDataLoaded", function() {
    it("returns loaded from internal data", function() {
      var loaded = {};
      GeneralManager._data.machine_actions.loaded = loaded;
      expect(GeneralManager.isDataLoaded("machine_actions")).toBe(loaded);
    });
  });

  describe("isPolling", function() {
    it("returns false if all false", function() {
      expect(GeneralManager.isPolling()).toBe(false);
    });

    it("returns true if one true", function() {
      var scope = $rootScope.$new();
      GeneralManager._data.machine_actions.polling = [scope];
      GeneralManager._data.architectures.polling = [];
      GeneralManager._data.known_architectures.polling = [];
      GeneralManager._data.pockets_to_disable.polling = [];
      GeneralManager._data.components_to_disable.polling = [];
      GeneralManager._data.hwe_kernels.polling = [];
      GeneralManager._data.osinfo.polling = [];
      expect(GeneralManager.isPolling()).toBe(true);
    });

    it("returns true if all true", function() {
      var scope = $rootScope.$new();
      GeneralManager._data.machine_actions.polling = [scope];
      GeneralManager._data.architectures.polling = [scope];
      GeneralManager._data.known_architectures.polling = [scope];
      GeneralManager._data.pockets_to_disable.polling = [scope];
      GeneralManager._data.components_to_disable.polling = [scope];
      GeneralManager._data.hwe_kernels.polling = [scope];
      GeneralManager._data.osinfo.polling = [scope];
      expect(GeneralManager.isPolling()).toBe(true);
    });
  });

  describe("isDataPolling", function() {
    it("returns polling from internal data", function() {
      var polling = {};
      GeneralManager._data.machine_actions.polling = polling;
      expect(GeneralManager.isDataPolling("machine_actions")).toBe(polling);
    });
  });

  describe("startPolling", function() {
    it("sets polling to true and calls _poll", function() {
      spyOn(GeneralManager, "_poll");
      var scope = $rootScope.$new();
      GeneralManager.startPolling(scope, "machine_actions");
      expect(GeneralManager._data.machine_actions.polling).toEqual([scope]);
      expect(GeneralManager._poll).toHaveBeenCalledWith(
        GeneralManager._data.machine_actions
      );
    });

    it("does nothing if already polling", function() {
      spyOn(GeneralManager, "_poll");
      var scope = $rootScope.$new();
      GeneralManager._data.machine_actions.polling = [scope];
      GeneralManager.startPolling(scope, "machine_actions");
      expect(GeneralManager._data.machine_actions.polling).toEqual([scope]);
      expect(GeneralManager._poll).not.toHaveBeenCalled();
    });
  });

  describe("stopPolling", function() {
    it("sets polling to false and cancels promise", function() {
      spyOn($timeout, "cancel");
      var nextPromise = {};
      var scope = $rootScope.$new();
      GeneralManager._data.machine_actions.polling = [scope];
      GeneralManager._data.machine_actions.nextPromise = nextPromise;
      GeneralManager.stopPolling(scope, "machine_actions");
      expect(GeneralManager._data.machine_actions.polling).toEqual([]);
      expect($timeout.cancel).toHaveBeenCalledWith(nextPromise);
    });
  });

  describe("_loadData", function() {
    it("calls callMethod with method", function() {
      spyOn(RegionConnection, "callMethod").and.returnValue($q.defer().promise);
      GeneralManager._loadData(GeneralManager._data.machine_actions);
      expect(RegionConnection.callMethod).toHaveBeenCalledWith(
        GeneralManager._data.machine_actions.method
      );
    });

    it("sets loaded to true", function() {
      var defer = $q.defer();
      spyOn(RegionConnection, "callMethod").and.returnValue(defer.promise);
      GeneralManager._loadData(GeneralManager._data.machine_actions);
      defer.resolve([]);
      $rootScope.$digest();
      expect(GeneralManager._data.machine_actions.loaded).toBe(true);
    });

    it("sets machine_actions data without changing reference", function() {
      var defer = $q.defer();
      spyOn(RegionConnection, "callMethod").and.returnValue(defer.promise);
      var actionsData = GeneralManager._data.machine_actions.data;
      var newData = [makeName("action")];
      GeneralManager._loadData(GeneralManager._data.machine_actions);
      defer.resolve(newData);
      $rootScope.$digest();
      expect(GeneralManager._data.machine_actions.data).toEqual(newData);
      expect(GeneralManager._data.machine_actions.data).toBe(actionsData);
    });

    it("sets osinfo data without changing reference", function() {
      var defer = $q.defer();
      spyOn(RegionConnection, "callMethod").and.returnValue(defer.promise);
      var osinfoData = GeneralManager._data.osinfo.data;
      var newData = { data: makeName("action") };
      GeneralManager._loadData(GeneralManager._data.osinfo);
      defer.resolve(newData);
      $rootScope.$digest();
      expect(GeneralManager._data.osinfo.data).toEqual(newData);
      expect(GeneralManager._data.osinfo.data).toBe(osinfoData);
    });

    it("calls raiseError if raiseError is true", function() {
      var defer = $q.defer();
      spyOn(RegionConnection, "callMethod").and.returnValue(defer.promise);
      spyOn(ErrorService, "raiseError");
      var error = makeName("error");
      GeneralManager._loadData(GeneralManager._data.machine_actions, true);
      defer.reject(error);
      $rootScope.$digest();
      expect(ErrorService.raiseError).toHaveBeenCalledWith(error);
    });

    it("doesnt calls raiseError if raiseError is false", function() {
      var defer = $q.defer();
      spyOn(RegionConnection, "callMethod").and.returnValue(defer.promise);
      spyOn(ErrorService, "raiseError");
      var error = makeName("error");
      GeneralManager._loadData(GeneralManager._data.machine_actions, false);
      defer.reject(error);
      $rootScope.$digest();
      expect(ErrorService.raiseError).not.toHaveBeenCalled();
    });

    it("doesnt calls raiseError if raiseError is undefined", function() {
      var defer = $q.defer();
      spyOn(RegionConnection, "callMethod").and.returnValue(defer.promise);
      spyOn(ErrorService, "raiseError");
      var error = makeName("error");
      GeneralManager._loadData(GeneralManager._data.machine_actions);
      defer.reject(error);
      $rootScope.$digest();
      expect(ErrorService.raiseError).not.toHaveBeenCalled();
    });
  });

  describe("_pollAgain", function() {
    it("sets nextPromise on data", function() {
      GeneralManager._pollAgain(GeneralManager._data.machine_actions);
      expect(GeneralManager._data.machine_actions.nextPromise).not.toBeNull();
    });
  });

  describe("_poll", function() {
    it("calls _pollAgain with error timeout if not connected", function() {
      spyOn(RegionConnection, "isConnected").and.returnValue(false);
      spyOn(GeneralManager, "_pollAgain");
      GeneralManager._poll(GeneralManager._data.machine_actions);
      expect(GeneralManager._pollAgain).toHaveBeenCalledWith(
        GeneralManager._data.machine_actions,
        GeneralManager._pollErrorTimeout
      );
    });

    it("calls _loadData with raiseError false", function() {
      spyOn(GeneralManager, "_loadData").and.returnValue($q.defer().promise);
      GeneralManager._poll(GeneralManager._data.machine_actions);
      expect(GeneralManager._loadData).toHaveBeenCalledWith(
        GeneralManager._data.machine_actions,
        false
      );
    });

    it("calls _pollAgain with empty timeout for machine_actions", function() {
      var defer = $q.defer();
      spyOn(GeneralManager, "_pollAgain");
      spyOn(GeneralManager, "_loadData").and.returnValue(defer.promise);
      GeneralManager._poll(GeneralManager._data.machine_actions);
      defer.resolve([]);
      $rootScope.$digest();
      expect(GeneralManager._pollAgain).toHaveBeenCalledWith(
        GeneralManager._data.machine_actions,
        GeneralManager._pollEmptyTimeout
      );
    });

    it("calls _pollAgain with empty timeout for osinfo", function() {
      var defer = $q.defer();
      spyOn(GeneralManager, "_pollAgain");
      spyOn(GeneralManager, "_loadData").and.returnValue(defer.promise);
      GeneralManager._poll(GeneralManager._data.osinfo);
      defer.resolve({});
      $rootScope.$digest();
      expect(GeneralManager._pollAgain).toHaveBeenCalledWith(
        GeneralManager._data.osinfo,
        GeneralManager._pollEmptyTimeout
      );
    });

    it("calls _pollAgain with timeout for machine_actions", function() {
      var defer = $q.defer();
      spyOn(GeneralManager, "_pollAgain");
      spyOn(GeneralManager, "_loadData").and.returnValue(defer.promise);
      var machine_actions = [makeName("action")];
      GeneralManager._data.machine_actions.data = machine_actions;
      GeneralManager._poll(GeneralManager._data.machine_actions);
      defer.resolve(machine_actions);
      $rootScope.$digest();
      expect(GeneralManager._pollAgain).toHaveBeenCalledWith(
        GeneralManager._data.machine_actions,
        GeneralManager._pollTimeout
      );
    });

    it("calls _pollAgain with error timeout on reject", function() {
      var defer = $q.defer();
      spyOn(GeneralManager, "_pollAgain");
      spyOn(GeneralManager, "_loadData").and.returnValue(defer.promise);
      var error = makeName("error");
      spyOn(console, "log");
      GeneralManager._poll(GeneralManager._data.machine_actions);
      defer.reject(error);
      $rootScope.$digest();
      // eslint-disable-next-line no-console
      expect(console.log).toHaveBeenCalledWith(error);
      expect(GeneralManager._pollAgain).toHaveBeenCalledWith(
        GeneralManager._data.machine_actions,
        GeneralManager._pollErrorTimeout
      );
    });
  });

  describe("loadItems", function() {
    it("doesnt call _loadData without request", function() {
      spyOn(GeneralManager, "_loadData").and.returnValue($q.defer().promise);
      GeneralManager.loadItems();
      expect(GeneralManager._loadData.calls.count()).toBe(0);
    });

    it("only call _loadData for requested data", function() {
      spyOn(GeneralManager, "_loadData").and.returnValue($q.defer().promise);
      GeneralManager.getData("osinfo");
      GeneralManager.loadItems();
      expect(GeneralManager._loadData.calls.count()).toBe(1);
    });

    it("calls _loadData for specified data only", function() {
      spyOn(GeneralManager, "_loadData").and.returnValue($q.defer().promise);
      GeneralManager.loadItems(["osinfo"]);
      expect(GeneralManager._loadData.calls.count()).toBe(1);
    });

    it("resolve defer once all resolve", function(done) {
      var defers = [$q.defer(), $q.defer()];
      var i = 0;
      spyOn(GeneralManager, "_loadData").and.callFake(function() {
        return defers[i++].promise;
      });
      GeneralManager.loadItems(["osinfo", "hwe_kernels"]).then(function() {
        done();
      });
      angular.forEach(defers, function(defer) {
        defer.resolve();
        $rootScope.$digest();
      });
    });
  });

  describe("enableAutoReload", function() {
    it("does nothing if already enabled", function() {
      spyOn(RegionConnection, "registerHandler");
      GeneralManager._autoReload = true;
      GeneralManager.enableAutoReload();
      expect(RegionConnection.registerHandler).not.toHaveBeenCalled();
    });

    it("adds handler and sets autoReload to true", function() {
      spyOn(RegionConnection, "registerHandler");
      GeneralManager.enableAutoReload();
      expect(RegionConnection.registerHandler).toHaveBeenCalled();
      expect(GeneralManager._autoReload).toBe(true);
    });
  });

  describe("disableAutoReload", function() {
    it("does nothing if already disabled", function() {
      spyOn(RegionConnection, "unregisterHandler");
      GeneralManager._autoReload = false;
      GeneralManager.disableAutoReload();
      expect(RegionConnection.unregisterHandler).not.toHaveBeenCalled();
    });

    it("removes handler and sets autoReload to false", function() {
      spyOn(RegionConnection, "unregisterHandler");
      GeneralManager._autoReload = true;
      GeneralManager.disableAutoReload();
      expect(RegionConnection.unregisterHandler).toHaveBeenCalled();
      expect(GeneralManager._autoReload).toBe(false);
    });
  });

  describe("getNavigationOptions", () => {
    it("calls callMethod with action parameter", () => {
      spyOn(RegionConnection, "callMethod");
      GeneralManager.getNavigationOptions();
      expect(RegionConnection.callMethod).toHaveBeenCalledWith(
        "general.navigation_options"
      );
    });
  });
});
