/* Copyright 2015-2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for AddDeviceController.
 */

import { makeName } from "testing/utils";
import MockWebSocket from "testing/websocket";

describe("AddDeviceController", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Grab the needed angular pieces.
  var $controller, $rootScope, $q;
  beforeEach(inject(function($injector) {
    $controller = $injector.get("$controller");
    $rootScope = $injector.get("$rootScope");
    $q = $injector.get("$q");
  }));

  // Load the required dependencies for the AddDeviceController
  // and mock the websocket connection.
  var SubnetsManager, DevicesManager, DomainsManager, ManagerHelperService;
  var ValidationService, RegionConnection, webSocket;
  beforeEach(inject(function($injector) {
    SubnetsManager = $injector.get("SubnetsManager");
    DevicesManager = $injector.get("DevicesManager");
    DomainsManager = $injector.get("DomainsManager");
    ManagerHelperService = $injector.get("ManagerHelperService");
    ValidationService = $injector.get("ValidationService");
    RegionConnection = $injector.get("RegionConnection");

    // Mock buildSocket so an actual connection is not made.
    webSocket = new MockWebSocket();
    spyOn(RegionConnection, "buildSocket").and.returnValue(webSocket);
  }));

  // Create the parent scope and the scope for the controller.
  var parentScope, $scope;
  beforeEach(function() {
    parentScope = $rootScope.$new();
    parentScope.addDeviceScope = null;
    $scope = parentScope.$new();
  });

  // Makes the AddDeviceController
  function makeController(loadManagersDefer) {
    var loadManagers = spyOn(ManagerHelperService, "loadManagers");
    if (angular.isObject(loadManagersDefer)) {
      loadManagers.and.returnValue(loadManagersDefer.promise);
    } else {
      loadManagers.and.returnValue($q.defer().promise);
    }
    // Start the connection so a valid websocket is created in the
    // RegionConnection.
    RegionConnection.connect("");

    return $controller("AddDeviceController", {
      $scope: $scope,
      SubnetsManager: SubnetsManager,
      DevicesManager: DevicesManager,
      DomainsManager: DomainsManager,
      ValidationService: ValidationService,
      ManagerHelperService: ManagerHelperService
    });
  }

  // Make the AddDeviceController with the $scope.device already initialized.
  function makeControllerWithDevice() {
    var defer = $q.defer();
    var controller = makeController(defer);
    $scope.show();
    defer.resolve();
    $rootScope.$digest();
    return controller;
  }

  // Generating random subnets is difficult, so we just use an array
  // of random subnets and select one from it.
  var subnets = [
    {
      cidr: "192.168.1.0/24",
      name: "192.168.1.0/24",
      first_ip: "192.168.1.1"
    },
    {
      cidr: "192.168.2.0/24",
      name: "192.168.2.0/24",
      first_ip: "192.168.2.1"
    },
    {
      cidr: "172.16.0.0/16",
      name: "172.16.0.0/16",
      first_ip: "172.16.1.1"
    },
    {
      cidr: "172.17.0.0/16",
      name: "172.17.0.0/16",
      first_ip: "172.17.1.1"
    }
  ];
  var _nextSubnet = 0;
  beforeEach(function() {
    // Reset the next network before each test.
    _nextSubnet = 0;
  });

  // Make a subnet.
  var _subnetId = 0;
  function makeSubnet() {
    if (_nextSubnet >= subnets.length) {
      throw new Error("Out of fake subnets.");
    }
    var subnet = subnets[_nextSubnet++];
    subnet.id = _subnetId++;
    return subnet;
  }

  // Make a interface
  function makeInterface(mac, ipAssignment, subnetId, ipAddress) {
    if (angular.isUndefined(mac)) {
      mac = "";
    }
    if (angular.isUndefined(ipAssignment)) {
      ipAssignment = null;
    }
    if (angular.isUndefined(subnetId)) {
      subnetId = null;
    }
    if (angular.isUndefined(ipAddress)) {
      ipAddress = "";
    }
    return {
      mac: mac,
      ipAssignment: ipAssignment,
      subnetId: subnetId,
      ipAddress: ipAddress
    };
  }

  it("sets addDeviceScope on $scope.$parent", function() {
    makeController();
    expect(parentScope.addDeviceScope).toBe($scope);
  });

  it("sets initial values on $scope", function() {
    makeController();
    expect($scope.viewable).toBe(false);
    expect($scope.error).toBe(null);
    expect($scope.ipAssignments).toEqual([
      {
        name: "external",
        title: "External"
      },
      {
        name: "dynamic",
        title: "Dynamic"
      },
      {
        name: "static",
        title: "Static"
      }
    ]);
  });

  it("doesn't call loadManagers when initialized", function() {
    // add_hardware is loaded on the listing and details page. Managers
    // should be loaded when shown. Otherwise all Zones and Domains are
    // loaded and updated even though they are not needed.
    makeController();
    expect(ManagerHelperService.loadManagers).not.toHaveBeenCalled();
  });

  describe("show", function() {
    it("does nothing if already viewable", function() {
      var defer = $q.defer();
      makeController(defer);
      $scope.viewable = true;
      var name = makeName("name");
      $scope.device = { name: name };
      $scope.show();

      defer.resolve();
      $rootScope.$digest();
      // The device name should have stayed the same, showing that
      // the call did nothing.
      expect($scope.device.name).toBe(name);
    });

    it("clears device and sets viewable to true", function() {
      var defer = $q.defer();
      makeController(defer);
      $scope.device = { name: makeName("name") };
      $scope.show();

      defer.resolve();
      $rootScope.$digest();
      expect($scope.device).toEqual({
        name: "",
        domain: undefined,
        interfaces: [
          {
            mac: "",
            ipAssignment: null,
            subnetId: null,
            ipAddress: ""
          }
        ]
      });
      expect($scope.domains).toBe(DomainsManager.getItems());
      expect($scope.viewable).toBe(true);
    });

    it("calls loadManagers for Subnets/Domains Manager", function() {
      var defer = $q.defer();
      makeController(defer);
      $scope.show();

      defer.resolve();
      $rootScope.$digest();
      expect(ManagerHelperService.loadManagers).toHaveBeenCalledWith($scope, [
        SubnetsManager,
        DomainsManager
      ]);
    });
  });

  describe("hide", function() {
    it("sets viewable to false", function() {
      makeController();
      $scope.viewable = true;
      $scope.hide();
      expect($scope.viewable).toBe(false);
    });

    it("emits event addDeviceHidden", function(done) {
      makeController();
      $scope.viewable = true;
      $scope.$on("addDeviceHidden", function() {
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
        SubnetsManager,
        DomainsManager
      ]);
    });
  });

  describe("nameHasError", function() {
    it("returns false if name is empty", function() {
      makeController();
      expect($scope.nameHasError()).toBe(false);
    });

    it("returns false if valid name", function() {
      makeControllerWithDevice();
      $scope.device.name = "abc";
      expect($scope.nameHasError()).toBe(false);
    });

    it("returns true if invalid name", function() {
      makeControllerWithDevice();
      $scope.device.name = "a_bc.local";
      expect($scope.nameHasError()).toBe(true);
    });
  });

  describe("macHasError", function() {
    it("returns false if mac is empty", function() {
      makeController();
      var nic = makeInterface();
      expect($scope.macHasError(nic)).toBe(false);
    });

    it("returns false if valid mac", function() {
      makeControllerWithDevice();
      var nic = makeInterface("00:00:11:22:33:44");
      expect($scope.macHasError(nic)).toBe(false);
    });

    it("returns false if not repeat mac", function() {
      makeControllerWithDevice();
      var nic = makeInterface("00:00:11:22:33:44");
      var nic2 = makeInterface("00:00:11:22:33:55");
      $scope.device.interfaces = [nic, nic2];
      expect($scope.macHasError(nic)).toBe(false);
      expect($scope.macHasError(nic2)).toBe(false);
    });

    it("returns true if invalid mac", function() {
      makeController();
      var nic = makeInterface("00:00:11:22:33");
      expect($scope.macHasError(nic)).toBe(true);
    });

    it("returns true if repeat mac", function() {
      makeControllerWithDevice();
      var nic = makeInterface("00:00:11:22:33:44");
      var nic2 = makeInterface("00:00:11:22:33:44");
      $scope.device.interfaces = [nic, nic2];
      expect($scope.macHasError(nic)).toBe(true);
      expect($scope.macHasError(nic2)).toBe(true);
    });
  });

  describe("ipHasError", function() {
    it("returns false if ip is empty", function() {
      makeController();
      var nic = makeInterface();
      expect($scope.ipHasError(nic)).toBe(false);
    });

    it("returns false if valid ipv4", function() {
      makeController();
      var nic = makeInterface();
      nic.ipAddress = "192.168.1.1";
      expect($scope.ipHasError(nic)).toBe(false);
    });

    it("returns false if valid ipv6", function() {
      makeController();
      var nic = makeInterface();
      nic.ipAddress = "2001:db8::1";
      expect($scope.ipHasError(nic)).toBe(false);
    });

    it("returns true if invalid ipv4", function() {
      makeController();
      var nic = makeInterface();
      nic.ipAddress = "192.168.1";
      expect($scope.ipHasError(nic)).toBe(true);
    });

    it("returns true if invalid ipv6", function() {
      makeController();
      var nic = makeInterface();
      nic.ipAddress = "2001::db8::1";
      expect($scope.ipHasError(nic)).toBe(true);
    });

    it("returns false if external ip out of managed network", function() {
      makeController();
      var subnet = makeSubnet();
      SubnetsManager._items = [subnet];
      $scope.subnets = [subnet];
      // No class A address is in the fake networks.
      var deviceInterface = makeInterface();
      deviceInterface.ipAddress = "10.0.1.1";
      deviceInterface.ipAssignment = {
        name: "external"
      };
      expect($scope.ipHasError(deviceInterface)).toBe(false);
    });

    it("returns true if external ip in managed network", function() {
      makeController();
      var subnet = makeSubnet();
      SubnetsManager._items = [subnet];
      $scope.subnets = [subnet];
      var deviceInterface = makeInterface();
      deviceInterface.ipAddress = subnet.first_ip;
      deviceInterface.ipAssignment = {
        name: "external"
      };
      expect($scope.ipHasError(deviceInterface)).toBe(true);
    });

    it("returns false if static in managed network", function() {
      makeController();
      var subnet = makeSubnet();
      SubnetsManager._items = [subnet];
      $scope.subnets = [subnet];
      var deviceInterface = makeInterface();
      deviceInterface.ipAddress = subnet.first_ip;
      deviceInterface.ipAssignment = {
        name: "static"
      };
      expect($scope.ipHasError(deviceInterface)).toBe(false);
    });

    it("returns false if static ip in select network", function() {
      makeController();
      var subnet = makeSubnet();
      SubnetsManager._items = [subnet];
      $scope.subnets = [subnet];
      var deviceInterface = makeInterface();
      deviceInterface.ipAddress = subnet.first_ip;
      deviceInterface.subnetId = subnet.id;
      deviceInterface.ipAssignment = {
        name: "static"
      };
      expect($scope.ipHasError(deviceInterface)).toBe(false);
    });

    it("returns true if static ip out of select network", function() {
      makeController();
      var subnet = makeSubnet();
      SubnetsManager._items = [subnet];
      $scope.subnets = [subnet];
      var deviceInterface = makeInterface();
      deviceInterface.ipAddress = "120.22.22.1";
      deviceInterface.subnetId = subnet.id;
      deviceInterface.ipAssignment = {
        name: "static"
      };
      expect($scope.ipHasError(deviceInterface)).toBe(true);
    });
  });

  describe("deviceHasError", function() {
    it("returns true if name empty", function() {
      makeControllerWithDevice();
      $scope.device.interfaces[0].mac = "00:11:22:33:44:55";
      $scope.device.interfaces[0].ipAssignment = {
        name: "dynamic"
      };
      expect($scope.deviceHasError()).toBe(true);
    });

    it("returns true if mac empty", function() {
      makeControllerWithDevice();
      $scope.device.name = "abc";
      $scope.device.interfaces[0].ipAssignment = {
        name: "dynamic"
      };
      expect($scope.deviceHasError()).toBe(true);
    });

    it("returns true if name invalid", function() {
      makeControllerWithDevice();
      $scope.device.name = "ab_c.local";
      $scope.device.interfaces[0].mac = "00:11:22:33:44:55";
      $scope.device.interfaces[0].ipAssignment = {
        name: "dynamic"
      };
      expect($scope.deviceHasError()).toBe(true);
    });

    it("returns true if mac invalid", function() {
      makeControllerWithDevice();
      $scope.device.name = "abc";
      $scope.device.interfaces[0].mac = "00:11:22:33:44";
      $scope.device.interfaces[0].ipAssignment = {
        name: "dynamic"
      };
      expect($scope.deviceHasError()).toBe(true);
    });

    it("returns true if missing ip assignment selection", function() {
      makeControllerWithDevice();
      $scope.device.name = "abc";
      $scope.device.interfaces[0].mac = "00:11:22:33:44:55";
      expect($scope.deviceHasError()).toBe(true);
    });

    it("returns false if dynamic ip assignment selection", function() {
      makeControllerWithDevice();
      $scope.device.name = "abc";
      $scope.device.interfaces[0].mac = "00:11:22:33:44:55";
      $scope.device.interfaces[0].ipAssignment = {
        name: "dynamic"
      };
      expect($scope.deviceHasError()).toBe(false);
    });

    it("returns true if external ip assignment and ip empty", function() {
      makeControllerWithDevice();
      $scope.device.name = "abc";
      $scope.device.interfaces[0].mac = "00:11:22:33:44:55";
      $scope.device.interfaces[0].ipAssignment = {
        name: "external"
      };
      $scope.device.interfaces[0].ipAddress = "";
      expect($scope.deviceHasError()).toBe(true);
    });

    it("returns true if external ip assignment and ip invalid", function() {
      makeControllerWithDevice();
      $scope.device.name = "abc";
      $scope.device.interfaces[0].mac = "00:11:22:33:44:55";
      $scope.device.interfaces[0].ipAssignment = {
        name: "external"
      };
      $scope.device.interfaces[0].ipAddress = "192.168";
      expect($scope.deviceHasError()).toBe(true);
    });

    it("returns false if external ip assignment and ip valid", function() {
      makeControllerWithDevice();
      $scope.device.name = "abc";
      $scope.device.interfaces[0].mac = "00:11:22:33:44:55";
      $scope.device.interfaces[0].ipAssignment = {
        name: "external"
      };
      $scope.device.interfaces[0].ipAddress = "192.168.1.1";
      expect($scope.deviceHasError()).toBe(false);
    });

    it(`returns true if static ip assignment
        and no cluster interface`, function() {
      makeControllerWithDevice();
      $scope.device.name = "abc";
      $scope.device.interfaces[0].mac = "00:11:22:33:44:55";
      $scope.device.interfaces[0].ipAssignment = {
        name: "static"
      };
      expect($scope.deviceHasError()).toBe(true);
    });

    it("returns false if static ip assignment and subnet", function() {
      makeControllerWithDevice();
      var subnet = makeSubnet();
      SubnetsManager._items = [subnet];
      $scope.subnets = [subnet];
      $scope.device.name = "abc";
      $scope.device.interfaces[0].mac = "00:11:22:33:44:55";
      $scope.device.interfaces[0].ipAssignment = {
        name: "static"
      };
      $scope.device.interfaces[0].subnetId = subnet.id;
      expect($scope.deviceHasError()).toBe(false);
    });

    it(
      "returns true if static ip assignment, subnet, and " +
        "invalid ip address",
      function() {
        makeControllerWithDevice();
        var subnet = makeSubnet();
        SubnetsManager._items = [subnet];
        $scope.subnets = [subnet];
        $scope.device.name = "abc";
        $scope.device.interfaces[0].mac = "00:11:22:33:44:55";
        $scope.device.interfaces[0].ipAssignment = {
          name: "static"
        };
        $scope.device.interfaces[0].subnetId = subnet.id;
        $scope.device.interfaces[0].ipAddress = "192.168";
        expect($scope.deviceHasError()).toBe(true);
      }
    );

    it(
      "returns true if static ip assignment, subnet, and " +
        "ip address out of network",
      function() {
        makeControllerWithDevice();
        var subnet = makeSubnet();
        SubnetsManager._items = [subnet];
        $scope.subnets = [subnet];
        $scope.device.name = "abc";
        $scope.device.interfaces[0].mac = "00:11:22:33:44:55";
        $scope.device.interfaces[0].ipAssignment = {
          name: "static"
        };
        $scope.device.interfaces[0].subnetId = subnet.id;
        $scope.device.interfaces[0].ipAddress = "122.10.1.0";
        expect($scope.deviceHasError()).toBe(true);
      }
    );

    it(
      "returns false if static ip assignment, subnet, and " +
        "ip address in network",
      function() {
        makeControllerWithDevice();
        var subnet = makeSubnet();
        SubnetsManager._items = [subnet];
        $scope.subnets = [subnet];
        $scope.device.name = "abc";
        $scope.device.interfaces[0].mac = "00:11:22:33:44:55";
        $scope.device.interfaces[0].ipAssignment = {
          name: "static"
        };
        $scope.device.interfaces[0].subnetId = subnet.id;
        $scope.device.interfaces[0].ipAddress = subnet.first_ip;
        expect($scope.deviceHasError()).toBe(false);
      }
    );
  });

  describe("addInterface", function() {
    it("adds another interface", function() {
      makeControllerWithDevice();
      $scope.addInterface();
      expect($scope.device.interfaces.length).toBe(2);
    });
  });

  describe("isPrimaryInterface", function() {
    it("returns true for first interface", function() {
      makeControllerWithDevice();
      $scope.addInterface();
      expect($scope.isPrimaryInterface($scope.device.interfaces[0])).toBe(true);
    });

    it("returns false for second interface", function() {
      makeControllerWithDevice();
      $scope.addInterface();
      expect($scope.isPrimaryInterface($scope.device.interfaces[1])).toBe(
        false
      );
    });
  });

  describe("deleteInterface", function() {
    it("doesnt remove primary interface", function() {
      makeControllerWithDevice();
      var nic = $scope.device.interfaces[0];
      $scope.deleteInterface(nic);
      expect($scope.device.interfaces[0]).toBe(nic);
    });

    it("removes interface", function() {
      makeControllerWithDevice();
      $scope.addInterface();
      var nic = $scope.device.interfaces[1];
      $scope.deleteInterface(nic);
      expect($scope.device.interfaces.indexOf(nic)).toBe(-1);
    });
  });

  describe("cancel", function() {
    it("clears device", function() {
      makeControllerWithDevice();
      $scope.device.name = makeName("name");
      $scope.cancel();
      expect($scope.device.name).toBe("");
    });

    it("calls hide", function() {
      makeController();
      spyOn($scope, "hide");
      $scope.cancel();
      expect($scope.hide).toHaveBeenCalled();
    });
  });

  describe("save", function() {
    it("doest nothing if device in error", function() {
      makeController();
      var error = makeName("error");
      $scope.error = error;
      spyOn($scope, "deviceHasError").and.returnValue(true);
      $scope.save();
      // Error would have been cleared if save did anything.
      expect($scope.error).toBe(error);
    });

    it("clears error before calling create", function() {
      makeControllerWithDevice();
      $scope.error = makeName("error");
      spyOn($scope, "deviceHasError").and.returnValue(false);
      spyOn(DevicesManager, "create").and.returnValue($q.defer().promise);
      $scope.device.interfaces[0].ipAssignment = {
        name: "dynamic"
      };
      $scope.save();
      expect($scope.error).toBeNull();
    });

    it("calls create with converted device", function() {
      makeController();
      $scope.error = makeName("error");
      spyOn($scope, "deviceHasError").and.returnValue(false);
      spyOn(DevicesManager, "create").and.returnValue($q.defer().promise);
      var name = makeName("name");
      var domain = makeName("domain");
      var mac = makeName("mac");
      var assignment = "static";
      var ipAddress = makeName("ip");
      var subnet = makeSubnet();
      $scope.device = {
        name: name,
        domain: domain,
        interfaces: [
          {
            mac: mac,
            ipAssignment: {
              name: assignment
            },
            subnetId: subnet.id,
            ipAddress: ipAddress
          }
        ]
      };
      $scope.save();
      expect(DevicesManager.create).toHaveBeenCalledWith({
        hostname: name,
        domain: domain,
        primary_mac: mac,
        extra_macs: [],
        interfaces: [
          {
            mac: mac,
            ip_assignment: assignment,
            ip_address: ipAddress,
            subnet: subnet.id
          }
        ]
      });
    });

    it("on create resolve device is cleared", function() {
      makeControllerWithDevice();
      $scope.error = makeName("error");
      spyOn($scope, "deviceHasError").and.returnValue(false);
      var defer = $q.defer();
      spyOn(DevicesManager, "create").and.returnValue(defer.promise);
      $scope.device.name = makeName("name");
      $scope.device.interfaces[0].ipAssignment = {
        name: "dynamic"
      };
      $scope.save();
      defer.resolve();
      $rootScope.$digest();
      expect($scope.device.name).toBe("");
    });

    it("on create resolve hide is called when addAnother is false", function() {
      makeControllerWithDevice();
      $scope.error = makeName("error");
      spyOn($scope, "deviceHasError").and.returnValue(false);
      var defer = $q.defer();
      spyOn(DevicesManager, "create").and.returnValue(defer.promise);
      $scope.device.name = makeName("name");
      $scope.device.interfaces[0].ipAssignment = {
        name: "dynamic"
      };
      spyOn($scope, "hide");
      $scope.save(false);
      defer.resolve();
      $rootScope.$digest();
      expect($scope.hide).toHaveBeenCalled();
    });

    it(`on create resolve hide is not called
        when addAnother is true`, function() {
      makeControllerWithDevice();
      $scope.error = makeName("error");
      spyOn($scope, "deviceHasError").and.returnValue(false);
      var defer = $q.defer();
      spyOn(DevicesManager, "create").and.returnValue(defer.promise);
      $scope.device.name = makeName("name");
      $scope.device.interfaces[0].ipAssignment = {
        name: "dynamic"
      };
      spyOn($scope, "hide");
      $scope.save(true);
      defer.resolve();
      $rootScope.$digest();
      expect($scope.hide).not.toHaveBeenCalled();
    });

    it("on create reject error is set", function() {
      makeControllerWithDevice();
      $scope.error = makeName("error");
      spyOn($scope, "deviceHasError").and.returnValue(false);
      var defer = $q.defer();
      spyOn(DevicesManager, "create").and.returnValue(defer.promise);
      $scope.device.name = makeName("name");
      $scope.device.interfaces[0].ipAssignment = {
        name: "dynamic"
      };
      $scope.save();
      var errorMsg = makeName("error");
      var error = '{"hostname": ["' + errorMsg + '"]}';
      defer.reject(error);
      $rootScope.$digest();
      expect($scope.error).toBe(errorMsg);
    });
  });
});
