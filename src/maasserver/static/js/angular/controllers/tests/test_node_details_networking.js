/* Copyright 2015-2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for NodeNetworkingController.
 */

import { makeInteger, makeName } from "testing/utils";
import MockWebSocket from "testing/websocket";

describe("filterByUnusedForInterface", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Load the filterByUnusedForInterface.
  var filterByUnusedForInterface;
  beforeEach(inject(function($filter) {
    filterByUnusedForInterface = $filter("filterByUnusedForInterface");
  }));

  it("returns empty if undefined nic", function() {
    var i,
      vlan,
      vlans = [];
    for (i = 0; i < 3; i++) {
      vlan = {
        fabric: 0
      };
      vlans.push(vlan);
    }
    expect(filterByUnusedForInterface(vlans)).toEqual([]);
  });

  it("returns only free vlans", function() {
    var i,
      vlan,
      used_vlans = [],
      free_vlans = [],
      all_vlans = [];
    for (i = 0; i < 3; i++) {
      vlan = {
        id: i,
        fabric: 0
      };
      used_vlans.push(vlan);
      all_vlans.push(vlan);
    }
    for (i = 3; i < 6; i++) {
      vlan = {
        id: i,
        fabric: 0
      };
      free_vlans.push(vlan);
      all_vlans.push(vlan);
    }

    var nic = {
      id: 0
    };
    var originalInterfaces = {
      0: {
        type: "vlan",
        parents: [0],
        vlan_id: used_vlans[0].id
      },
      1: {
        type: "vlan",
        parents: [0],
        vlan_id: used_vlans[1].id
      },
      2: {
        type: "vlan",
        parents: [0],
        vlan_id: used_vlans[2].id
      },
      3: {
        type: "physical",
        vlan_id: free_vlans[0].id
      }
    };

    expect(
      filterByUnusedForInterface(all_vlans, nic, originalInterfaces)
    ).toEqual(free_vlans);
  });
});

describe("removeInterfaceParents", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Load the removeInterfaceParents.
  var removeInterfaceParents;
  beforeEach(inject(function($filter) {
    removeInterfaceParents = $filter("removeInterfaceParents");
  }));

  it("returns empty if undefined bondInterface", function() {
    var i,
      nic,
      interfaces = [];
    for (i = 0; i < 3; i++) {
      nic = {
        id: i,
        link_id: i
      };
      interfaces.push(nic);
    }
    expect(removeInterfaceParents(interfaces)).toEqual(interfaces);
  });

  it("removes parents from interfaces", function() {
    var vlan = {
      id: makeInteger(0, 100)
    };
    var nic1 = {
      id: makeInteger(0, 100),
      link_id: makeInteger(0, 100),
      type: "physical",
      vlan: vlan
    };
    var nic2 = {
      id: makeInteger(0, 100),
      link_id: makeInteger(0, 100),
      type: "physical",
      vlan: vlan
    };
    var interfaces = [nic1, nic2];
    var bondInterface = {
      parents: interfaces
    };
    expect(removeInterfaceParents(interfaces, bondInterface, false)).toEqual(
      []
    );
  });

  it("does not remove parents from interfaces when skipping", function() {
    var vlan = {
      id: makeInteger(0, 100)
    };
    var nic1 = {
      id: makeInteger(0, 100),
      link_id: makeInteger(0, 100),
      type: "physical",
      vlan: vlan
    };
    var nic2 = {
      id: makeInteger(0, 100),
      link_id: makeInteger(0, 100),
      type: "physical",
      vlan: vlan
    };
    var interfaces = [nic1, nic2];
    var bondInterface = {
      parents: interfaces
    };
    expect(removeInterfaceParents(interfaces, bondInterface, true)).toEqual(
      interfaces
    );
  });
});

describe("filterVLANNotOnFabric", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Load the filter
  var filterVLANNotOnFabric;
  beforeEach(inject(function($filter) {
    filterVLANNotOnFabric = $filter("filterVLANNotOnFabric");
  }));

  it("returns VLANs if undefined type", function() {
    var vlans = [{ id: 3 }, { id: 4 }];
    expect(filterVLANNotOnFabric(vlans, null)).toEqual(vlans);
  });

  it("removes VLANs from a different fabric", function() {
    var vlans = [{ id: 3 }, { id: 4 }];
    var vlanIDs = [3];
    expect(filterVLANNotOnFabric(vlans, vlanIDs)).toEqual([{ id: 3 }]);
  });

  it("returns all VLANs in fabric", function() {
    var vlans = [{ id: 3 }, { id: 4 }];
    var vlanIDs = [3, 4];
    expect(filterVLANNotOnFabric(vlans, vlanIDs)).toEqual(vlans);
  });
});

describe("filterEditInterface", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Load the filter
  var filterEditInterface;
  beforeEach(inject(function($filter) {
    filterEditInterface = $filter("filterEditInterface");
  }));

  it("returns interfaces if undefined type", function() {
    var interfaces = [{ id: 36, name: "eth-AMPnu0" }];
    expect(filterEditInterface(interfaces, "foo")).toEqual(interfaces);
  });

  it("removes editInterface", function() {
    var editInterface = {
      id: 36,
      name: "eth-AMPnu0",
      fabric: {
        name: "fabric-1"
      },
      vlan: {
        id: 2
      }
    };

    var interfaces = [
      {
        id: 37,
        name: "eth-AMPnu1",
        fabric: {
          name: "fabric-1"
        },
        vlan: {
          id: 2
        }
      }
    ];

    interfaces.push(editInterface);

    expect(filterEditInterface(interfaces, editInterface)).toEqual([
      {
        id: 37,
        name: "eth-AMPnu1",
        fabric: {
          name: "fabric-1"
        },
        vlan: {
          id: 2
        }
      }
    ]);
  });

  it("removes item on different fabric", function() {
    var interfaces = [
      { id: 36, name: "eth=AMPnu0", fabric: { name: "fabric-1" } }
    ];
    var editInterface = { fabric: { name: "fabric-2" } };

    expect(filterEditInterface(interfaces, editInterface)).toEqual([]);
  });
});

describe("removeDefaultVLANIfVLAN", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Load the removeDefaultVLANIfVLAN.
  var removeDefaultVLANIfVLAN;
  beforeEach(inject(function($filter) {
    removeDefaultVLANIfVLAN = $filter("removeDefaultVLANIfVLAN");
  }));

  it("returns vlans if undefined type", function() {
    var i,
      vlan,
      vlans = [];
    for (i = 0; i < 3; i++) {
      vlan = {
        id: i,
        vid: i,
        fabric: 0
      };
      vlans.push(vlan);
    }
    expect(removeDefaultVLANIfVLAN(vlans)).toEqual(vlans);
  });

  it("removes default vlans from vlans", function() {
    var i,
      vlan,
      vlans = [];
    for (i = 0; i < 3; i++) {
      vlan = {
        id: i,
        vid: i,
        fabric: 0
      };
      vlans.push(vlan);
    }

    expect(removeDefaultVLANIfVLAN(vlans, "vlan")).toEqual([
      vlans[1],
      vlans[2]
    ]);
  });
});

describe("filterSelectedInterfaces", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Load the filterSelectedInterfaces.
  var filterSelectedInterfaces;
  beforeEach(inject(function($filter) {
    filterSelectedInterfaces = $filter("filterSelectedInterfaces");
  }));

  it("removes selected items from interfaces", function() {
    var interfaces = [
      {
        id: 36,
        name: "eth-AMPnu0",
        link_id: -1,
        fabric: {
          name: "fabric-1"
        }
      }
    ];
    var selectedInterfaces = ["36/-1"];
    var newBondInterface = { fabric: { name: "fabric-1" } };

    expect(
      filterSelectedInterfaces(interfaces, selectedInterfaces, newBondInterface)
    ).toEqual([]);
  });

  it("does not remove interface if not selected", function() {
    var interfaces = [
      {
        id: 36,
        name: "eth-AMPnu0",
        link_id: -1,
        fabric: {
          name: "fabric-1"
        },
        vlan: {
          id: 2
        }
      }
    ];
    var selectedInterfaces = ["37/-1"];
    var newBondInterface = { fabric: { name: "fabric-1" }, vlan: { id: 2 } };

    expect(
      filterSelectedInterfaces(interfaces, selectedInterfaces, newBondInterface)
    ).toEqual(interfaces);
  });

  it("removes interface if not on same fabric as new bond", function() {
    var interfaces = [
      {
        id: 36,
        name: "eth-AMPnu0",
        link_id: -1,
        fabric: {
          name: "fabric-1"
        }
      }
    ];
    var selectedInterfaces = ["37/-1"];
    var newBondInterface = { fabric: { name: "fabric-2" } };

    expect(
      filterSelectedInterfaces(interfaces, selectedInterfaces, newBondInterface)
    ).toEqual([]);
  });
});

describe("filterLinkModes", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Load the filterLinkModes.
  var filterLinkModes;
  beforeEach(inject(function($filter) {
    filterLinkModes = $filter("filterLinkModes");
  }));

  // Load the modes before each test.
  var modes;
  beforeEach(function() {
    modes = [
      {
        mode: "auto",
        text: "Auto assign"
      },
      {
        mode: "static",
        text: "Static assign"
      },
      {
        mode: "dhcp",
        text: "DHCP"
      },
      {
        mode: "link_up",
        text: "Unconfigured"
      }
    ];
  });

  it("only link_up when no subnet", function() {
    var nic = {
      subnet: null
    };
    expect(filterLinkModes(modes, nic)).toEqual([
      {
        mode: "link_up",
        text: "Unconfigured"
      }
    ]);
  });

  it("honors getValue()", function() {
    var nic = {
      getValue: function() {
        return null;
      }
    };
    expect(filterLinkModes(modes, nic)).toEqual([
      {
        mode: "link_up",
        text: "Unconfigured"
      }
    ]);
  });

  it("all modes if only one link", function() {
    var nic = {
      subnet: {},
      links: [{}]
    };
    expect(filterLinkModes(modes, nic)).toEqual([
      {
        mode: "auto",
        text: "Auto assign"
      },
      {
        mode: "static",
        text: "Static assign"
      },
      {
        mode: "dhcp",
        text: "DHCP"
      },
      {
        mode: "link_up",
        text: "Unconfigured"
      }
    ]);
  });

  it("auto, static, and dhcp modes if more than one link", function() {
    var nic = {
      subnet: {},
      links: [{}, {}]
    };
    expect(filterLinkModes(modes, nic)).toEqual([
      {
        mode: "auto",
        text: "Auto assign"
      },
      {
        mode: "static",
        text: "Static assign"
      },
      {
        mode: "dhcp",
        text: "DHCP"
      }
    ]);
  });

  it("auto and static modes if interface is alias", function() {
    var nic = {
      type: "alias",
      subnet: {}
    };
    expect(filterLinkModes(modes, nic)).toEqual([
      {
        mode: "auto",
        text: "Auto assign"
      },
      {
        mode: "static",
        text: "Static assign"
      }
    ]);
  });
});

describe("NodeNetworkingController", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Grab the needed angular pieces.
  var $controller, $rootScope, $parentScope, $scope, $q;
  beforeEach(inject(function($injector) {
    $controller = $injector.get("$controller");
    $rootScope = $injector.get("$rootScope");
    $parentScope = $rootScope.$new();
    $scope = $parentScope.$new();
    $q = $injector.get("$q");
  }));

  // Load the required dependencies for the NodeNetworkingController.
  var FabricsManager, VLANsManager, SubnetsManager;
  var MachinesManager, DevicesManager, GeneralManager, ManagerHelperService;
  var NodeResultsManagerFactory, RegionConnection;
  var webSocket;
  beforeEach(inject(function($injector) {
    FabricsManager = $injector.get("FabricsManager");
    VLANsManager = $injector.get("VLANsManager");
    SubnetsManager = $injector.get("SubnetsManager");
    MachinesManager = $injector.get("MachinesManager");
    DevicesManager = $injector.get("DevicesManager");
    GeneralManager = $injector.get("GeneralManager");
    ManagerHelperService = $injector.get("ManagerHelperService");
    NodeResultsManagerFactory = $injector.get("NodeResultsManagerFactory");
    RegionConnection = $injector.get("RegionConnection");
    // Mock buildSocket so an actual connection is not made.
    webSocket = new MockWebSocket();
    spyOn(RegionConnection, "buildSocket").and.returnValue(webSocket);
    spyOn(RegionConnection, "callMethod").and.returnValue($q.defer().promise);
  }));

  var node;
  beforeEach(function() {
    node = {
      interfaces: []
    };
    $parentScope.node = node;
    $parentScope.isController = false;
    $parentScope.controllerLoaded = jasmine.createSpy("controllerLoaded");
  });

  // Makes the NodeStorageController.
  function makeController(loadManagersDefer) {
    var loadManagers = spyOn(ManagerHelperService, "loadManagers");
    if (angular.isObject(loadManagersDefer)) {
      loadManagers.and.returnValue(loadManagersDefer.promise);
    } else {
      loadManagers.and.returnValue($q.defer().promise);
    }

    var loadItems = spyOn(GeneralManager, "loadItems");
    loadItems.and.returnValue($q.defer().promise);

    $parentScope.nodesManager = MachinesManager;

    // Create the controller.
    var controller = $controller("NodeNetworkingController", {
      $scope: $scope,
      FabricsManager: FabricsManager,
      VLANsManager: VLANsManager,
      SubnetsManager: SubnetsManager,
      MachinesManager: MachinesManager,
      DevicesManager: DevicesManager,
      GeneralManager: GeneralManager,
      ManagerHelperService: ManagerHelperService,
      NodeResultsManagerFactory: NodeResultsManagerFactory,
      RegionConnection: RegionConnection
    });
    return controller;
  }

  it("sets initial values", function() {
    makeController();
    expect($scope.loaded).toBe(false);
    expect($scope.nodeHasLoaded).toBe(false);
    expect($scope.managersHaveLoaded).toBe(false);
    expect($scope.tableInfo.column).toBe("name");
    expect($scope.fabrics).toBe(FabricsManager.getItems());
    expect($scope.vlans).toBe(VLANsManager.getItems());
    expect($scope.subnets).toBe(SubnetsManager.getItems());
    expect($scope.interfaces).toEqual([]);
    expect($scope.interfaceLinksMap).toEqual({});
    expect($scope.originalInterfaces).toEqual({});
    expect($scope.selectedInterfaces).toEqual([]);
    expect($scope.selectedMode).toBeNull();
    expect($scope.newInterface).toEqual({});
    expect($scope.newBondInterface).toEqual({});
    expect($scope.newBridgeInterface).toEqual({});
    expect($scope.editInterface).toBeNull();
    expect($scope.bondOptions).toBe(GeneralManager.getData("bond_options"));
  });

  it("sets loaded once node loaded then managers loaded", function() {
    var defer = $q.defer();
    makeController(defer);

    // All should false.
    expect($scope.loaded).toBe(false);
    expect($scope.nodeHasLoaded).toBe(false);
    expect($scope.managersHaveLoaded).toBe(false);

    // Only nodeHasLoaded should be true.
    $scope.nodeLoaded();
    expect($scope.loaded).toBe(false);
    expect($scope.nodeHasLoaded).toBe(true);
    expect($scope.managersHaveLoaded).toBe(false);

    // All three should be true.
    defer.resolve();
    $rootScope.$digest();
    expect($scope.loaded).toBe(true);
    expect($scope.nodeHasLoaded).toBe(true);
    expect($scope.managersHaveLoaded).toBe(true);
  });

  it("sets loaded once managers loaded then node loaded", function() {
    var defer = $q.defer();
    makeController(defer);

    // All should false.
    expect($scope.loaded).toBe(false);
    expect($scope.nodeHasLoaded).toBe(false);
    expect($scope.managersHaveLoaded).toBe(false);

    // Only managersHaveLoaded should be true.
    defer.resolve();
    $rootScope.$digest();
    expect($scope.loaded).toBe(false);
    expect($scope.nodeHasLoaded).toBe(false);
    expect($scope.managersHaveLoaded).toBe(true);

    // All three should be true.
    $scope.nodeLoaded();
    expect($scope.loaded).toBe(true);
    expect($scope.nodeHasLoaded).toBe(true);
    expect($scope.managersHaveLoaded).toBe(true);
  });

  it("loads bond_options if not yet loaded", function() {
    var defer = $q.defer();
    makeController(defer);

    defer.resolve();
    $rootScope.$digest();

    expect(GeneralManager.loadItems).toHaveBeenCalledWith(["bond_options"]);
  });

  it("watches interfaces and subnets once nodeLoaded called", function() {
    makeController();
    spyOn($scope, "$watch");
    spyOn($scope, "$watchCollection");
    $scope.nodeLoaded();

    var watches = [];
    var i,
      calls = $scope.$watch.calls.allArgs();
    for (i = 0; i < calls.length; i++) {
      watches.push(calls[i][0]);
    }
    var watchCollections = [];
    calls = $scope.$watchCollection.calls.allArgs();
    for (i = 0; i < calls.length; i++) {
      watchCollections.push(calls[i][0]);
    }

    expect(watches).toEqual(["node.interfaces"]);
    expect(watchCollections).toEqual([]);
  });

  it("watches interfaces and subnets once nodeLoaded called", function() {
    makeController();
    spyOn($scope, "$watch");
    spyOn($scope, "$watchCollection");
    $parentScope.isController = true;
    $scope.nodeLoaded();

    var watches = [];
    var i,
      calls = $scope.$watch.calls.allArgs();
    for (i = 0; i < calls.length; i++) {
      watches.push(calls[i][0]);
    }
    var watchCollections = [];
    calls = $scope.$watchCollection.calls.allArgs();
    for (i = 0; i < calls.length; i++) {
      watchCollections.push(calls[i][0]);
    }

    expect(watches).toEqual(["node.interfaces", "subnets"]);
    expect(watchCollections).toEqual([]);
  });

  it("edit device subnet correctly when subnet is set", function() {
    makeController();
    $parentScope.isDevice = true;
    $scope.subnets = [{ id: 0, vlan: 0 }, { id: 1, vlan: 0 }];
    var nic = {
      id: 1,
      name: "eth0",
      ip_assignment: "static",
      tags: [],
      params: {
        bridge_fd: 15,
        bridge_stp: false
      },
      subnet: $scope.subnets[1]
    };
    $scope.edit(nic);
    expect($scope.editInterface.defaultSubnet.id).toEqual(1);
  });

  it("edit device subnet correctly when subnet is not set", function() {
    makeController();
    $parentScope.isDevice = true;
    $scope.subnets = [{ id: 0, vlan: 0 }, { id: 1, vlan: 0 }];
    var nic = {
      id: 1,
      name: "eth0",
      ip_assignment: "static",
      tags: [],
      params: {
        bridge_fd: 15,
        bridge_stp: false
      },
      subnet: null
    };
    $scope.edit(nic);
    expect($scope.editInterface.defaultSubnet.id).toEqual(0);
  });

  describe("updateInterfaces", function() {
    // updateInterfaces is a private method in the controller but we test
    // it by calling nodeLoaded which will setup the watcher which call
    // updateInterfaces and set $scope.interfaces.
    function updateInterfaces(controller) {
      if (!angular.isObject(controller)) {
        controller = makeController();
      }
      $scope.nodeLoaded();
      $scope.$digest();
    }

    it("returns empty list when node.interfaces empty", function() {
      node.interfaces = [];
      updateInterfaces();
      expect($scope.interfaces).toEqual([]);
    });

    it("adds interfaces to originalInterfaces map", function() {
      var nic1 = {
        id: 1,
        name: "eth0",
        type: "physical",
        parents: [],
        children: [],
        links: []
      };
      var nic2 = {
        id: 2,
        name: "eth1",
        type: "physical",
        parents: [],
        children: [],
        links: []
      };
      node.interfaces = [nic1, nic2];
      updateInterfaces();
      expect($scope.originalInterfaces).toEqual({
        1: nic1,
        2: nic2
      });
    });

    it("removes bond parents and places them as members", function() {
      var parent1 = {
        id: 0,
        name: "eth0",
        type: "physical",
        parents: [],
        children: [2],
        links: []
      };
      var parent2 = {
        id: 1,
        name: "eth1",
        type: "physical",
        parents: [],
        children: [2],
        links: []
      };
      var bond = {
        id: 2,
        name: "bond0",
        type: "bond",
        parents: [0, 1],
        children: [],
        links: []
      };
      node.interfaces = [parent1, parent2, bond];
      updateInterfaces();
      expect($scope.interfaces).toEqual([
        {
          id: 2,
          name: "bond0",
          type: "bond",
          parents: [0, 1],
          children: [],
          links: [],
          members: [parent1, parent2],
          vlan: null,
          link_id: -1,
          subnet: null,
          mode: "link_up",
          ip_address: ""
        }
      ]);
    });

    it("removes bridge parents and places them as members", function() {
      var parent1 = {
        id: 0,
        name: "eth0",
        type: "physical",
        parents: [],
        children: [2],
        links: []
      };
      var parent2 = {
        id: 1,
        name: "eth1",
        type: "physical",
        parents: [],
        children: [2],
        links: []
      };
      var bridge = {
        id: 2,
        name: "br0",
        type: "bridge",
        parents: [0, 1],
        children: [],
        links: []
      };
      node.interfaces = [parent1, parent2, bridge];
      updateInterfaces();
      expect($scope.interfaces).toEqual([
        {
          id: 2,
          name: "br0",
          type: "bridge",
          parents: [0, 1],
          children: [],
          links: [],
          members: [parent1, parent2],
          vlan: null,
          link_id: -1,
          subnet: null,
          mode: "link_up",
          ip_address: ""
        }
      ]);
    });

    it("clears editInterface if parent is now in a bond", function() {
      var parent1 = {
        id: 0,
        name: "eth0",
        type: "physical",
        parents: [],
        children: [2],
        links: []
      };
      var parent2 = {
        id: 1,
        name: "eth1",
        type: "physical",
        parents: [],
        children: [2],
        links: []
      };
      var bond = {
        id: 2,
        name: "bond0",
        type: "bond",
        parents: [0, 1],
        children: [],
        links: []
      };
      node.interfaces = [parent1, parent2, bond];
      $scope.editInterface = {
        id: 0,
        link_id: -1
      };
      updateInterfaces();
      expect($scope.editInterface).toBeNull();
    });

    it("clears editInterface if parent is now in a bridge", function() {
      var parent1 = {
        id: 0,
        name: "eth0",
        type: "physical",
        parents: [],
        children: [2],
        links: []
      };
      var parent2 = {
        id: 1,
        name: "eth1",
        type: "physical",
        parents: [],
        children: [2],
        links: []
      };
      var bridge = {
        id: 2,
        name: "br0",
        type: "bridge",
        parents: [0, 1],
        children: [],
        links: []
      };
      node.interfaces = [parent1, parent2, bridge];
      $scope.editInterface = {
        id: 0,
        link_id: -1
      };
      updateInterfaces();
      expect($scope.editInterface).toBeNull();
    });

    it("sets vlan and fabric on interface", function() {
      var fabric = {
        id: 0
      };
      var vlan = {
        id: 0,
        fabric: 0
      };
      var nic = {
        id: 0,
        name: "eth0",
        type: "physical",
        parents: [],
        children: [],
        links: [],
        vlan_id: 0
      };
      FabricsManager._items = [fabric];
      VLANsManager._items = [vlan];
      node.interfaces = [nic];
      updateInterfaces();
      expect($scope.interfaces[0].vlan).toBe(vlan);
      expect($scope.interfaces[0].fabric).toBe(fabric);
    });

    it("sets default to link_up if not links", function() {
      var nic = {
        id: 0,
        name: "eth0",
        type: "physical",
        parents: [],
        children: [],
        links: []
      };
      node.interfaces = [nic];
      updateInterfaces();
      expect($scope.interfaces).toEqual([
        {
          id: 0,
          name: "eth0",
          type: "physical",
          parents: [],
          children: [],
          links: [],
          vlan: null,
          link_id: -1,
          subnet: null,
          mode: "link_up",
          ip_address: ""
        }
      ]);
    });

    it("duplicates links as alias interfaces", function() {
      var subnet0 = { id: 0 },
        subnet1 = { id: 1 },
        subnet2 = { id: 2 };
      SubnetsManager._items = [subnet0, subnet1, subnet2];
      var links = [
        {
          id: 0,
          subnet_id: 0,
          mode: "dhcp",
          ip_address: ""
        },
        {
          id: 1,
          subnet_id: 1,
          mode: "auto",
          ip_address: ""
        },
        {
          id: 2,
          subnet_id: 2,
          mode: "static",
          ip_address: "192.168.122.10"
        }
      ];
      var nic = {
        id: 0,
        name: "eth0",
        type: "physical",
        parents: [],
        children: [],
        links: links
      };
      node.interfaces = [nic];
      updateInterfaces();
      expect($scope.interfaces).toEqual([
        {
          id: 0,
          name: "eth0",
          type: "physical",
          parents: [],
          children: [],
          links: links,
          vlan: null,
          fabric: undefined,
          link_id: 0,
          subnet: subnet0,
          mode: "dhcp",
          ip_address: ""
        },
        {
          id: 0,
          name: "eth0:1",
          type: "alias",
          parents: [],
          children: [],
          links: links,
          vlan: null,
          fabric: undefined,
          link_id: 1,
          subnet: subnet1,
          mode: "auto",
          ip_address: ""
        },
        {
          id: 0,
          name: "eth0:2",
          type: "alias",
          parents: [],
          children: [],
          links: links,
          vlan: null,
          fabric: undefined,
          link_id: 2,
          subnet: subnet2,
          mode: "static",
          ip_address: "192.168.122.10"
        }
      ]);
    });

    it("renders empty vlanTable for non-controllers", function() {
      var fabric0 = {
        id: 0
      };
      var vlan0 = {
        id: 0,
        fabric: 0
      };
      var subnet0 = { id: 0 };
      var nic0 = {
        id: 0,
        name: "eth0",
        type: "physical",
        parents: [],
        children: [],
        links: [],
        vlan_id: 0
      };
      SubnetsManager._items = [subnet0];
      FabricsManager._items = [fabric0];
      VLANsManager._items = [vlan0];
      node.interfaces = [nic0];

      // Should be blank for non-controller.
      updateInterfaces();
      expect($scope.vlanTable).toEqual([]);
    });

    it("renders vlanTable OK when no subnets", function() {
      var fabric0 = {
        id: 0,
        name: "fabric0"
      };
      var vlan0 = {
        id: 0,
        fabric: 0,
        name: "vlan0"
      };
      var nic0 = {
        id: 0,
        name: "eth0",
        type: "physical",
        parents: [],
        children: [],
        links: [],
        vlan_id: 0
      };
      SubnetsManager._items = [];
      FabricsManager._items = [fabric0];
      VLANsManager._items = [vlan0];
      node.interfaces = [nic0];

      $parentScope.isController = true;
      updateInterfaces();
      expect($scope.vlanTable).toEqual([
        {
          fabric: fabric0,
          vlan: vlan0,
          subnets: [],
          primary_rack: null,
          secondary_rack: null,
          sort_key: fabric0.name + "|" + $scope.getVLANText(vlan0)
        }
      ]);
    });

    it("renders single entry vlanTable", function() {
      var subnet0 = { id: 0, vlan: 0 };
      var fabric0 = {
        id: 0
      };
      var vlan0 = {
        id: 0,
        fabric: 0
      };
      var nic0 = {
        id: 0,
        name: "eth0",
        type: "physical",
        parents: [],
        children: [],
        links: [],
        vlan_id: 0
      };
      SubnetsManager._items = [subnet0];
      FabricsManager._items = [fabric0];
      VLANsManager._items = [vlan0];
      node.interfaces = [nic0];

      // Should not blank for a controller.
      $parentScope.isController = true;
      updateInterfaces();
      expect($scope.vlanTable).toEqual([
        {
          fabric: fabric0,
          vlan: vlan0,
          subnets: [subnet0],
          primary_rack: null,
          secondary_rack: null,
          sort_key: fabric0.name + "|" + $scope.getVLANText(vlan0)
        }
      ]);
    });

    var makeInterestingNetwork = function() {
      var net = {};
      net.space0 = { id: 0 };
      net.subnet0 = { id: 0, vlan: 0, cidr: "10.0.0.0/16" };
      net.subnet1 = { id: 1, vlan: 0, cidr: "10.10.0.0/16" };
      net.subnet2 = { id: 2, vlan: 1, cidr: "10.20.0.0/16" };
      net.fabric0 = {
        id: 0
      };
      net.fabric1 = {
        id: 1
      };
      net.vlan0 = {
        id: 0,
        fabric: 0
      };
      net.vlan1 = {
        id: 1,
        fabric: 1
      };
      net.nic0 = {
        id: 0,
        name: "eth0",
        type: "physical",
        parents: [],
        children: [],
        links: [],
        vlan_id: 0
      };
      net.nic1 = {
        id: 1,
        name: "eth1",
        type: "physical",
        parents: [],
        children: [],
        links: [],
        vlan_id: 1
      };
      //SpacesManager._items = [net.space0];
      SubnetsManager._items = [net.subnet0, net.subnet1, net.subnet2];
      FabricsManager._items = [net.fabric0, net.fabric1];
      VLANsManager._items = [net.vlan0, net.vlan1];
      node.interfaces = [net.nic0, net.nic1];
      return net;
    };

    it("renders multi-entry vlanTable", function() {
      var net = makeInterestingNetwork();
      // Should not blank for a controller.
      $parentScope.isController = true;
      updateInterfaces();
      expect($scope.vlanTable).toEqual([
        {
          fabric: net.fabric0,
          vlan: net.vlan0,
          subnets: [net.subnet0, net.subnet1],
          primary_rack: null,
          secondary_rack: null,
          sort_key: net.fabric0.name + "|" + $scope.getVLANText(net.vlan0)
        },
        {
          fabric: net.fabric1,
          vlan: net.vlan1,
          subnets: [net.subnet2],
          primary_rack: null,
          secondary_rack: null,
          sort_key: net.fabric0.name + "|" + $scope.getVLANText(net.vlan1)
        }
      ]);
    });

    it("no duplicate vlans", function() {
      // Regression for https://bugs.launchpad.net/maas/+bug/1559332.
      // Same vlan on two nics shouldn't result in two vlans in table.
      var subnet0 = { id: 0, vlan: 0 };
      var fabric0 = {
        id: 0
      };
      var vlan0 = {
        id: 0,
        fabric: 0
      };
      var nic0 = {
        id: 0,
        name: "eth0",
        type: "physical",
        parents: [],
        children: [],
        links: [],
        vlan_id: 0
      };
      var nic1 = {
        id: 1,
        name: "eth1",
        type: "physical",
        parents: [],
        children: [],
        links: [],
        vlan_id: 0
      };
      SubnetsManager._items = [subnet0];
      FabricsManager._items = [fabric0];
      VLANsManager._items = [vlan0];
      node.interfaces = [nic0, nic1];

      // Should not blank for a controller.
      $parentScope.isController = true;
      updateInterfaces();
      expect($scope.vlanTable).toEqual([
        {
          vlan: vlan0,
          fabric: fabric0,
          subnets: [subnet0],
          primary_rack: null,
          secondary_rack: null,
          sort_key: fabric0.name + "|" + $scope.getVLANText(vlan0)
        }
      ]);
    });

    // Regression for https://bugs.launchpad.net/maas/+bug/1576267.
    it("updates vlanTable when add subnet", function() {
      var net = makeInterestingNetwork();

      // Should not blank for a controller.
      $parentScope.isController = true;
      updateInterfaces();
      expect($scope.vlanTable).toEqual([
        {
          fabric: net.fabric0,
          vlan: net.vlan0,
          subnets: [net.subnet0, net.subnet1],
          primary_rack: null,
          secondary_rack: null,
          sort_key: net.fabric0.name + "|" + $scope.getVLANText(net.vlan0)
        },
        {
          fabric: net.fabric1,
          vlan: net.vlan1,
          subnets: [net.subnet2],
          primary_rack: null,
          secondary_rack: null,
          sort_key: net.fabric0.name + "|" + $scope.getVLANText(net.vlan1)
        }
      ]);

      // Add subnet and make sure it shows up in vlanTable.
      var subnet = {
        id: 3,
        name: "subnet3",
        vlan: 0,
        space: 0,
        cidr: "10.30.0.0/16"
      };
      SubnetsManager._items.push(subnet);
      $scope.$digest();
      expect($scope.vlanTable).toEqual([
        {
          fabric: net.fabric0,
          vlan: net.vlan0,
          subnets: [net.subnet0, net.subnet1, subnet],
          primary_rack: null,
          secondary_rack: null,
          sort_key: net.fabric0.name + "|" + $scope.getVLANText(net.vlan0)
        },
        {
          fabric: net.fabric1,
          vlan: net.vlan1,
          subnets: [net.subnet2],
          primary_rack: null,
          secondary_rack: null,
          sort_key: net.fabric0.name + "|" + $scope.getVLANText(net.vlan1)
        }
      ]);
    });

    // Regression for https://bugs.launchpad.net/maas/+bug/1576267.
    it("updates empty vlanTable when add subnet", function() {
      var fabric0 = {
        id: 0,
        name: "fabric0"
      };
      var vlan0 = {
        id: 0,
        fabric: 0,
        name: "vlan0"
      };
      var nic0 = {
        id: 0,
        name: "eth0",
        type: "physical",
        parents: [],
        children: [],
        links: [],
        vlan_id: 0
      };
      SubnetsManager._items = [];
      FabricsManager._items = [fabric0];
      VLANsManager._items = [vlan0];
      node.interfaces = [nic0];

      $parentScope.isController = true;
      updateInterfaces();
      expect($scope.vlanTable).toEqual([
        {
          fabric: fabric0,
          vlan: vlan0,
          subnets: [],
          primary_rack: null,
          secondary_rack: null,
          sort_key: fabric0.name + "|" + $scope.getVLANText(vlan0)
        }
      ]);
      // Add subnet and make sure it shows up in vlanTable.
      var subnet = {
        id: 3,
        name: "subnet3",
        vlan: 0,
        space: 0,
        cidr: "10.30.0.0/16"
      };
      SubnetsManager._items.push(subnet);
      $scope.$digest();
      expect($scope.vlanTable).toEqual([
        {
          fabric: fabric0,
          vlan: vlan0,
          subnets: [subnet],
          primary_rack: null,
          secondary_rack: null,
          sort_key: fabric0.name + "|" + $scope.getVLANText(vlan0)
        }
      ]);
    });

    it("creates interfaceLinksMap", function() {
      var links = [
        {
          id: 0,
          subnet_id: 0,
          mode: "dhcp",
          ip_address: ""
        },
        {
          id: 1,
          subnet_id: 1,
          mode: "auto",
          ip_address: ""
        },
        {
          id: 2,
          subnet_id: 2,
          mode: "static",
          ip_address: "192.168.122.10"
        }
      ];
      var nic = {
        id: 0,
        name: "eth0",
        type: "physical",
        parents: [],
        children: [],
        links: links
      };
      node.interfaces = [nic];
      updateInterfaces();
      expect($scope.interfaceLinksMap[0][0].link_id).toBe(0);
      expect($scope.interfaceLinksMap[0][1].link_id).toBe(1);
      expect($scope.interfaceLinksMap[0][2].link_id).toBe(2);
    });

    it("clears editInterface if interface no longer exists", function() {
      node.interfaces = [];
      $scope.editInterface = {
        id: 0,
        link_id: -1
      };
      updateInterfaces();
      expect($scope.editInterface).toBeNull();
    });

    it("clears editInterface if link no longer exists", function() {
      var nic = {
        id: 0,
        name: "eth0",
        type: "physical",
        parents: [],
        children: [],
        links: []
      };
      node.interfaces = [nic];
      $scope.editInterface = {
        id: 0,
        link_id: 0
      };
      updateInterfaces();
      expect($scope.editInterface).toBeNull();
    });

    describe("newInterface", function() {
      // Setup the initial data for newInterface to be set.
      function setupNewInterface(controller, newInterface) {
        var links = [
          {
            id: 0,
            subnet_id: 0,
            mode: "dhcp",
            ip_address: ""
          },
          {
            id: 1,
            subnet_id: 1,
            mode: "auto",
            ip_address: ""
          },
          {
            id: 2,
            subnet_id: 2,
            mode: "static",
            ip_address: "192.168.122.10"
          }
        ];
        var nic = {
          id: 0,
          name: "eth0",
          type: "physical",
          parents: [],
          children: [],
          links: links
        };
        node.interfaces = [nic];
        updateInterfaces(controller);

        var parent = $scope.interfaceLinksMap[0][0];
        newInterface.parent = parent;
        $scope.newInterface = newInterface;
      }

      // Cause the updateInterfaces to be called again to perform
      // the logic on newInterface.
      function reloadNewInterface(controller) {
        // Add another nic to interfaces so that updateInterfaces
        // really performs an action.
        node.interfaces.push({
          id: 1,
          name: "eth1",
          type: "physical",
          parents: [],
          children: [],
          links: []
        });
        updateInterfaces(controller);
      }

      it("updates newInterface.parent object", function() {
        var controller = makeController();
        var newInterface = {
          type: "alias"
        };
        setupNewInterface(controller, newInterface);
        var parent = newInterface.parent;
        reloadNewInterface(controller);

        // Should be the same value but a different object.
        expect(newInterface.parent).toEqual(parent);
        expect(newInterface.parent).not.toBe(parent);
      });

      it("changes newInterface.type from alias to VLAN", function() {
        var controller = makeController();
        var newInterface = {
          type: "alias"
        };
        setupNewInterface(controller, newInterface);

        spyOn($scope, "canAddAlias").and.returnValue(false);
        spyOn($scope, "canAddVLAN").and.returnValue(true);
        spyOn($scope, "addTypeChanged");
        reloadNewInterface(controller);
        expect(newInterface.type).toBe("vlan");
        expect($scope.addTypeChanged).toHaveBeenCalled();
      });

      it("changes newInterface.type from VLAN to alias", function() {
        var controller = makeController();
        var newInterface = {
          type: "vlan"
        };
        setupNewInterface(controller, newInterface);

        spyOn($scope, "canAddAlias").and.returnValue(true);
        spyOn($scope, "canAddVLAN").and.returnValue(false);
        spyOn($scope, "addTypeChanged");
        reloadNewInterface(controller);
        expect(newInterface.type).toBe("alias");
        expect($scope.addTypeChanged).toHaveBeenCalled();
      });

      it("clears newInterface if cannot add VLAN or alias", function() {
        var controller = makeController();
        var newInterface = {
          type: "vlan"
        };
        setupNewInterface(controller, newInterface);

        spyOn($scope, "canAddAlias").and.returnValue(false);
        spyOn($scope, "canAddVLAN").and.returnValue(false);
        reloadNewInterface(controller);
        expect($scope.newInterface).toEqual({});
      });

      it("clears newInterface if parent removed", function() {
        var controller = makeController();
        var newInterface = {
          type: "vlan"
        };
        setupNewInterface(controller, newInterface);

        spyOn($scope, "canAddAlias").and.returnValue(false);
        spyOn($scope, "canAddVLAN").and.returnValue(false);
        $scope.selectedMode = "add";
        reloadNewInterface(controller);
        expect($scope.selectedMode).toBeNull();
      });

      it("leaves single selection mode if newInterface is cleared", function() {
        var controller = makeController();
        var newInterface = {
          type: "vlan"
        };
        setupNewInterface(controller, newInterface);

        spyOn($scope, "canAddAlias").and.returnValue(false);
        spyOn($scope, "canAddVLAN").and.returnValue(false);
        $scope.selectedMode = "add";
        node.interfaces = [];
        updateInterfaces(controller);
        expect($scope.newInterface).toEqual({});
        expect($scope.selectedMode).toBeNull();
      });
    });
  });

  describe("isBootInterface", function() {
    it("returns true if is_boot is true", function() {
      makeController();
      var nic = {
        type: "physical",
        is_boot: true
      };
      expect($scope.isBootInterface(nic)).toBe(true);
    });

    it("returns true if is_boot is true and alias", function() {
      makeController();
      var nic = {
        type: "alias",
        is_boot: true
      };
      expect($scope.isBootInterface(nic)).toBe(false);
    });

    it("returns false if is_boot is false", function() {
      makeController();
      var nic = {
        type: "physical",
        is_boot: false
      };
      expect($scope.isBootInterface(nic)).toBe(false);
    });

    it("returns false if bond has no members with is_boot", function() {
      makeController();
      var nic = {
        type: "bond",
        is_boot: false,
        members: [
          {
            is_boot: false
          },
          {
            is_boot: false
          }
        ]
      };
      expect($scope.isBootInterface(nic)).toBe(false);
    });

    it("returns true if bond has member with is_boot", function() {
      makeController();
      var nic = {
        type: "bond",
        is_boot: false,
        members: [
          {
            is_boot: false
          },
          {
            is_boot: true
          }
        ]
      };
      expect($scope.isBootInterface(nic)).toBe(true);
    });
  });

  describe("getInterfaceTypeText", function() {
    var INTERFACE_TYPE_TEXTS = {
      physical: "Physical",
      bond: "Bond",
      vlan: "VLAN",
      alias: "Alias",
      missing_type: "missing_type",
      ovs: "Open vSwitch"
    };

    angular.forEach(INTERFACE_TYPE_TEXTS, function(value, type) {
      it("returns correct value for '" + type + "'", function() {
        makeController();
        var nic = {
          type: type
        };
        expect($scope.getInterfaceTypeText(nic)).toBe(value);
      });
    });

    it("returns correct text if bridge type is OVS", () => {
      makeController();
      const nic = {
        type: "bridge",
        params: { bridge_type: "ovs" }
      };
      expect($scope.getInterfaceTypeText(nic)).toBe("Open vSwitch");
    });

    it(`returns correct text if physical interface
      has a child with bond type`, () => {
      makeController();
      const child = { type: "bond" };
      const parent = { type: "physical" };
      expect($scope.getInterfaceTypeText(child, parent)).toBe(
        "Bonded physical"
      );
    });

    it(`returns correct text if physical interface
      has a child with bridge type`, () => {
      makeController();
      const child = { type: "bridge" };
      const parent = { type: "physical" };
      expect($scope.getInterfaceTypeText(child, parent)).toBe(
        "Bridged physical"
      );
    });
  });

  describe("getLinkModeText", function() {
    var LINK_MODE_TEXTS = {
      auto: "Auto assign",
      static: "Static assign",
      dhcp: "DHCP",
      link_up: "Unconfigured",
      missing_type: "missing_type"
    };

    angular.forEach(LINK_MODE_TEXTS, function(value, mode) {
      it("returns correct value for '" + mode + "'", function() {
        makeController();
        var nic = {
          mode: mode
        };
        expect($scope.getLinkModeText(nic)).toBe(value);
      });
    });
  });

  describe("getVLANText", function() {
    it("returns empty if vlan undefined", function() {
      makeController();
      expect($scope.getVLANText()).toBe("");
    });

    it("returns just vid", function() {
      makeController();
      var vlan = {
        vid: 5
      };
      expect($scope.getVLANText(vlan)).toBe(5);
    });

    it("returns vid + name", function() {
      makeController();
      var name = makeName("vlan");
      var vlan = {
        vid: 5,
        name: name
      };
      expect($scope.getVLANText(vlan)).toBe("5 (" + name + ")");
    });
  });

  describe("getSubnetText", function() {
    it("returns 'Unconfigured' for null", function() {
      makeController();
      expect($scope.getSubnetText(null)).toBe("Unconfigured");
    });

    it("returns just cidr if no name", function() {
      makeController();
      var cidr = makeName("cidr");
      var subnet = {
        cidr: cidr
      };
      expect($scope.getSubnetText(subnet)).toBe(cidr);
    });

    it("returns just cidr if name same as cidr", function() {
      makeController();
      var cidr = makeName("cidr");
      var subnet = {
        cidr: cidr,
        name: cidr
      };
      expect($scope.getSubnetText(subnet)).toBe(cidr);
    });

    it("returns cidr + name", function() {
      makeController();
      var cidr = makeName("cidr");
      var name = makeName("name");
      var subnet = {
        cidr: cidr,
        name: name
      };
      expect($scope.getSubnetText(subnet)).toBe(cidr + " (" + name + ")");
    });
  });

  describe("getSubnet", function() {
    it("calls SubnetsManager.getItemFromList", function() {
      makeController();
      var subnetId = makeInteger(0, 100);
      var subnet = {};
      spyOn(SubnetsManager, "getItemFromList").and.returnValue(subnet);

      expect($scope.getSubnet(subnetId)).toBe(subnet);
      expect(SubnetsManager.getItemFromList).toHaveBeenCalledWith(subnetId);
    });
  });

  describe("saveInterface", function() {
    it("calls MachinesManager.updateInterface if name changed", function() {
      makeController();
      var id = makeInteger(0, 100);
      var name = makeName("nic");
      var vlan = { id: makeInteger(0, 100) };
      var original_nic = {
        id: id,
        name: name,
        vlan_id: vlan.id
      };
      var nic = {
        id: id,
        name: makeName("newName"),
        vlan: vlan,
        tags: []
      };
      $scope.originalInterfaces[id] = original_nic;
      $scope.interfaces = [nic];

      spyOn(MachinesManager, "updateInterface").and.returnValue(
        $q.defer().promise
      );
      $scope.saveInterface(nic);
      expect(MachinesManager.updateInterface).toHaveBeenCalledWith(node, id, {
        name: nic.name,
        mac_address: undefined,
        vlan: vlan.id,
        mode: undefined,
        fabric: null,
        subnet: null,
        tags: []
      });
    });

    it("calls MachinesManager.updateInterface if vlan changed", function() {
      makeController();
      var id = makeInteger(0, 100);
      var name = makeName("nic");
      var vlan = { id: makeInteger(0, 100) };
      var original_nic = {
        id: id,
        name: name,
        vlan_id: makeInteger(200, 300)
      };
      var nic = {
        id: id,
        name: name,
        vlan: vlan,
        tags: []
      };
      $scope.originalInterfaces[id] = original_nic;
      $scope.interfaces = [nic];

      spyOn(MachinesManager, "updateInterface").and.returnValue(
        $q.defer().promise
      );
      $scope.saveInterface(nic);
      expect(MachinesManager.updateInterface).toHaveBeenCalledWith(node, id, {
        name: name,
        mac_address: undefined,
        vlan: vlan.id,
        mode: undefined,
        fabric: null,
        subnet: null,
        tags: []
      });
    });

    it("calls MachinesManager.updateInterface if vlan set", function() {
      makeController();
      var id = makeInteger(0, 100);
      var name = makeName("nic");
      var vlan = { id: makeInteger(0, 100) };
      var original_nic = {
        id: id,
        name: name,
        vlan_id: null
      };
      var nic = {
        id: id,
        name: name,
        vlan: vlan,
        tags: []
      };
      $scope.originalInterfaces[id] = original_nic;
      $scope.interfaces = [nic];

      spyOn(MachinesManager, "updateInterface").and.returnValue(
        $q.defer().promise
      );
      $scope.saveInterface(nic);
      expect(MachinesManager.updateInterface).toHaveBeenCalledWith(node, id, {
        name: name,
        mac_address: undefined,
        vlan: vlan.id,
        mode: undefined,
        fabric: null,
        subnet: null,
        tags: []
      });
    });

    it("calls MachinesManager.updateInterface if vlan unset", function() {
      makeController();
      var id = makeInteger(0, 100);
      var name = makeName("nic");
      var original_nic = {
        id: id,
        name: name,
        vlan_id: makeInteger(200, 300)
      };
      var nic = {
        id: id,
        name: name,
        vlan: null,
        tags: []
      };
      $scope.originalInterfaces[id] = original_nic;
      $scope.interfaces = [nic];

      spyOn(MachinesManager, "updateInterface").and.returnValue(
        $q.defer().promise
      );
      $scope.saveInterface(nic);
      expect(MachinesManager.updateInterface).toHaveBeenCalledWith(node, id, {
        name: name,
        mac_address: undefined,
        mode: undefined,
        fabric: null,
        subnet: null,
        vlan: null,
        tags: []
      });
    });
  });

  describe("isInterfaceNameInvalid", function() {
    it("returns true if name is empty", function() {
      makeController();
      var nic = {
        name: ""
      };
      expect($scope.isInterfaceNameInvalid(nic)).toBe(true);
    });

    it("returns true if name is missing", function() {
      makeController();
      var nic = {};
      expect($scope.isInterfaceNameInvalid(nic)).toBe(true);
    });

    it("returns true if nic is null", function() {
      makeController();
      var nic = null;
      expect($scope.isInterfaceNameInvalid(nic)).toBe(true);
    });

    it("returns true if name is same as another interface", function() {
      makeController();
      var name = makeName("nic");
      var nic = {
        id: 0,
        name: name
      };
      var otherNic = {
        id: 1,
        name: name
      };
      $scope.node.interfaces = [nic, otherNic];
      expect($scope.isInterfaceNameInvalid(nic)).toBe(true);
    });

    it("returns false if name is same name as self", function() {
      makeController();
      var name = makeName("nic");
      var nic = {
        id: 0,
        name: name
      };
      $scope.node.interfaces = [nic];
      expect($scope.isInterfaceNameInvalid(nic)).toBe(false);
    });

    it("returns false if name is different", function() {
      makeController();
      var name = makeName("nic");
      var newName = makeName("newNic");
      var nic = {
        id: 0,
        name: newName
      };
      var otherNic = {
        id: 1,
        name: name
      };
      $scope.node.interfaces = [otherNic];
      expect($scope.isInterfaceNameInvalid(nic)).toBe(false);
    });
  });

  describe("fabricChanged", function() {
    it("sets vlan on interface", function() {
      makeController();
      var fabric = {
        id: 0,
        default_vlan_id: 0,
        vlan_ids: [0]
      };
      var vlan = {
        id: 0,
        fabric: fabric.id
      };
      FabricsManager._items = [fabric];
      VLANsManager._items = [vlan];
      var nic = {
        vlan: null,
        fabric: fabric
      };
      spyOn($scope, "saveInterface");
      $scope.fabricChanged(nic);
      expect(nic.vlan).toBe(vlan);
    });

    it("sets vlan to null", function() {
      makeController();
      var nic = {
        vlan: {},
        fabric: null
      };
      spyOn($scope, "saveInterface");
      $scope.fabricChanged(nic);
      expect(nic.vlan).toBeNull();
    });
  });

  describe("isLinkModeDisabled", function() {
    it("enabled when subnet", function() {
      makeController();
      var nic = {
        subnet: {}
      };
      expect($scope.isLinkModeDisabled(nic)).toBe(false);
    });

    it("disabled when not subnet", function() {
      makeController();
      var nic = {
        subnet: null
      };
      expect($scope.isLinkModeDisabled(nic)).toBe(true);
    });

    it("enabled when subnet with getValue", function() {
      makeController();
      var nic = {
        getValue: function() {
          return {};
        }
      };
      expect($scope.isLinkModeDisabled(nic)).toBe(false);
    });

    it("disabled when not subnet with getValue", function() {
      makeController();
      var nic = {
        getValue: function() {
          return null;
        }
      };
      expect($scope.isLinkModeDisabled(nic)).toBe(true);
    });
  });

  describe("saveInterfaceLink", function() {
    it("calls MachinesManager.linkSubnet with params", function() {
      makeController();
      var nic = {
        id: makeInteger(0, 100),
        mode: "static",
        subnet: { id: makeInteger(0, 100) },
        link_id: makeInteger(0, 100),
        ip_address: "192.168.122.1"
      };
      spyOn(MachinesManager, "linkSubnet").and.returnValue($q.defer().promise);
      $scope.saveInterfaceLink(nic);
      expect(MachinesManager.linkSubnet).toHaveBeenCalledWith(node, nic.id, {
        mode: "static",
        subnet: nic.subnet.id,
        link_id: nic.link_id,
        ip_address: nic.ip_address
      });
    });
  });

  describe("subnetChanged", function() {
    it("sets mode to link_up if set to no subnet", function() {
      makeController();
      var nic = {
        subnet: null
      };
      spyOn($scope, "saveInterfaceLink");
      $scope.subnetChanged(nic);
      expect(nic.mode).toBe("link_up");
    });

    it("doesnt set mode to link_up if set if subnet", function() {
      makeController();
      var nic = {
        mode: "static",
        subnet: {
          statistics: {
            first_address: "172.16.3.1"
          }
        }
      };
      spyOn($scope, "saveInterfaceLink");
      $scope.subnetChanged(nic);
      expect(nic.mode).toBe("static");
    });

    it("clears ip_address", function() {
      makeController();
      var nic = {
        subnet: null,
        ip_address: makeName("ip")
      };
      spyOn($scope, "saveInterfaceLink");
      $scope.subnetChanged(nic);
      expect(nic.ip_address).toBe("");
    });
  });

  describe("subnetChangedForm", function() {
    it("sets mode to link_up if set to no subnet", function() {
      makeController();
      var nic = {
        getValue: function(name) {
          return this["_" + name];
        },
        updateValue: function(name, val) {
          this["_" + name] = val;
        },
        _subnet: null
      };
      spyOn($scope, "saveInterfaceLink");
      $scope.subnetChangedForm("subnet", null, nic);
      expect(nic._mode).toBe("link_up");
    });

    it("doesnt set mode to link_up if set if subnet", function() {
      makeController();
      var nic = {
        getValue: function(name) {
          return this["_" + name];
        },
        updateValue: function(name, val) {
          this["_" + name] = val;
        },
        _mode: "static",
        _subnet: {}
      };
      spyOn($scope, "saveInterfaceLink");
      $scope.subnetChangedForm("subnet", {}, nic);
      expect(nic._mode).toBe("static");
    });

    it("clears ip_address", function() {
      makeController();
      var nic = {
        getValue: function(name) {
          return this["_" + name];
        },
        updateValue: function(name, val) {
          this["_" + name] = val;
        },
        _subnet: null,
        _ip_address: makeName("ip")
      };
      spyOn($scope, "saveInterfaceLink");
      $scope.subnetChangedForm("subnet", null, nic);
      expect(nic._ip_address).toBe("");
    });
  });

  describe("isIPAddressInvalid", function() {
    it("true if empty IP address", function() {
      makeController();
      var nic = {
        ip_address: "",
        mode: "static"
      };
      expect($scope.isIPAddressInvalid(nic)).toBe(true);
    });

    it("true if not valid IP address", function() {
      makeController();
      var nic = {
        ip_address: "192.168.260.5",
        mode: "static"
      };
      expect($scope.isIPAddressInvalid(nic)).toBe(true);
    });

    it("true if IP address not in subnet", function() {
      makeController();
      var nic = {
        ip_address: "192.168.123.10",
        mode: "static",
        subnet: {
          cidr: "192.168.122.0/24"
        }
      };
      expect($scope.isIPAddressInvalid(nic)).toBe(true);
    });

    it("false if IP address in subnet", function() {
      makeController();
      var nic = {
        ip_address: "192.168.122.10",
        mode: "static",
        subnet: {
          cidr: "192.168.122.0/24"
        }
      };
      expect($scope.isIPAddressInvalid(nic)).toBe(false);
    });
  });

  describe("getUniqueKey", function() {
    it("returns id + / + link_id", function() {
      makeController();
      var nic = {
        id: makeInteger(0, 100),
        link_id: makeInteger(0, 100)
      };
      expect($scope.getUniqueKey(nic)).toBe(nic.id + "/" + nic.link_id);
    });
  });

  describe("toggleInterfaceSelect", function() {
    it("selects interface and enters single mode", function() {
      makeController();
      var nic = {
        id: makeInteger(0, 100),
        link_id: makeInteger(0, 100)
      };
      var key = $scope.getUniqueKey(nic);
      $scope.toggleInterfaceSelect(nic);
      expect($scope.selectedInterfaces).toEqual([key]);
      expect($scope.selectedMode).toBe("single");
    });

    it("deselects interface and enters none mode", function() {
      makeController();
      var nic = {
        id: makeInteger(0, 100),
        link_id: makeInteger(0, 100)
      };
      $scope.toggleInterfaceSelect(nic);
      $scope.toggleInterfaceSelect(nic);
      expect($scope.selectedInterfaces).toEqual([]);
      expect($scope.selectedMode).toBeNull();
    });

    it("selecting multiple enters multi mode", function() {
      makeController();
      var nic1 = {
        id: makeInteger(0, 100),
        link_id: makeInteger(0, 100)
      };
      var nic2 = {
        id: makeInteger(100, 200),
        link_id: makeInteger(0, 100)
      };
      var key1 = $scope.getUniqueKey(nic1);
      var key2 = $scope.getUniqueKey(nic2);
      $scope.toggleInterfaceSelect(nic1);
      $scope.toggleInterfaceSelect(nic2);
      expect($scope.selectedInterfaces).toEqual([key1, key2]);
      expect($scope.selectedMode).toBe("multi");
    });
  });

  describe("isInterfaceSelected", function() {
    it("returns true when selected", function() {
      makeController();
      var nic = {
        id: makeInteger(0, 100),
        link_id: makeInteger(0, 100)
      };
      var key = $scope.getUniqueKey(nic);
      $scope.selectedInterfaces = [key];
      expect($scope.isInterfaceSelected(nic)).toBe(true);
    });

    it("returns false when not selected", function() {
      makeController();
      var nic = {
        id: makeInteger(0, 100),
        link_id: makeInteger(0, 100)
      };
      $scope.selectedInterfaces = [];
      expect($scope.isInterfaceSelected(nic)).toBe(false);
    });
  });

  describe("cannotEditInterface", function() {
    it("returns true when only one selected", function() {
      makeController();
      var nic = {
        id: makeInteger(0, 100),
        link_id: makeInteger(0, 100)
      };
      var key = $scope.getUniqueKey(nic);
      $scope.selectedInterfaces = [key];
      expect($scope.cannotEditInterface(nic)).toBe(false);
    });

    it("returns false when multiple selected", function() {
      makeController();
      var nic1 = {
        id: makeInteger(0, 100),
        link_id: makeInteger(0, 100)
      };
      var nic2 = {
        id: makeInteger(100, 200),
        link_id: makeInteger(0, 100)
      };
      var key1 = $scope.getUniqueKey(nic1);
      var key2 = $scope.getUniqueKey(nic2);
      $scope.selectedInterfaces = [key1, key2];
      expect($scope.cannotEditInterface(nic1)).toBe(false);
    });

    it("returns false when not selected", function() {
      makeController();
      var nic = {
        id: makeInteger(0, 100),
        link_id: makeInteger(0, 100)
      };
      $scope.selectedInterfaces = [];
      expect($scope.cannotEditInterface(nic)).toBe(false);
    });
  });

  describe("isShowingDeleteConfirm", function() {
    it("returns true in delete mode", function() {
      makeController();
      $scope.selectedMode = "delete";
      expect($scope.isShowingDeleteConfirm()).toBe(true);
    });

    it("returns false not in delete mode", function() {
      makeController();
      $scope.selectedMode = "single";
      expect($scope.isShowingDeleteConfirm()).toBe(false);
    });
  });

  describe("isShowingAdd", function() {
    it("returns true in add mode", function() {
      makeController();
      $scope.selectedMode = "add";
      expect($scope.isShowingAdd()).toBe(true);
    });

    it("returns false not in add mode", function() {
      makeController();
      $scope.selectedMode = "delete";
      expect($scope.isShowingAdd()).toBe(false);
    });
  });

  describe("canAddAliasOrVLAN", function() {
    it("returns false if isController", function() {
      makeController();
      $parentScope.isController = true;
      spyOn($scope, "isAllNetworkingDisabled").and.returnValue(false);
      spyOn($scope, "canAddAlias").and.returnValue(true);
      spyOn($scope, "canAddVLAN").and.returnValue(true);
      expect($scope.canAddAliasOrVLAN({})).toBe(false);
    });

    it("returns false if no node editing", function() {
      makeController();
      $parentScope.isController = false;
      spyOn($scope, "isAllNetworkingDisabled").and.returnValue(true);
      spyOn($scope, "canAddAlias").and.returnValue(true);
      spyOn($scope, "canAddVLAN").and.returnValue(true);
      expect($scope.canAddAliasOrVLAN({})).toBe(false);
    });

    it("returns true if can edit alias", function() {
      makeController();
      $parentScope.isController = false;
      spyOn($scope, "isAllNetworkingDisabled").and.returnValue(false);
      spyOn($scope, "canAddAlias").and.returnValue(true);
      spyOn($scope, "canAddVLAN").and.returnValue(false);
      expect($scope.canAddAliasOrVLAN({})).toBe(true);
    });

    it("returns true if can edit VLAN", function() {
      makeController();
      $parentScope.isController = false;
      spyOn($scope, "isAllNetworkingDisabled").and.returnValue(false);
      spyOn($scope, "canAddAlias").and.returnValue(false);
      spyOn($scope, "canAddVLAN").and.returnValue(true);
      expect($scope.canAddAliasOrVLAN({})).toBe(true);
    });
  });

  describe("canAddAlias", function() {
    it("returns false if nic undefined", function() {
      makeController();
      expect($scope.canAddAlias()).toBe(false);
    });

    it("returns false if nic type is alias", function() {
      makeController();
      var nic = {
        type: "alias"
      };
      expect($scope.canAddAlias(nic)).toBe(false);
    });

    it("returns false if nic has no links", function() {
      makeController();
      var nic = {
        type: "physical",
        links: []
      };
      expect($scope.canAddAlias(nic)).toBe(false);
    });

    it("returns false if nic has link_up", function() {
      makeController();
      var nic = {
        type: "physical",
        links: [
          {
            mode: "link_up"
          }
        ]
      };
      expect($scope.canAddAlias(nic)).toBe(false);
    });

    it("returns true if nic has dhcp", function() {
      makeController();
      var nic = {
        type: "physical",
        links: [
          {
            mode: "dhcp"
          }
        ]
      };
      expect($scope.canAddAlias(nic)).toBe(true);
    });

    it("returns true if nic has static", function() {
      makeController();
      var nic = {
        type: "physical",
        links: [
          {
            mode: "static"
          }
        ]
      };
      expect($scope.canAddAlias(nic)).toBe(true);
    });

    it("returns true if nic has auto", function() {
      makeController();
      var nic = {
        type: "physical",
        links: [
          {
            mode: "auto"
          }
        ]
      };
      expect($scope.canAddAlias(nic)).toBe(true);
    });
  });

  describe("canAddVLAN", function() {
    it("returns false if nic undefined", function() {
      makeController();
      expect($scope.canAddVLAN()).toBe(false);
    });

    it("returns false if nic type is alias", function() {
      makeController();
      var nic = {
        type: "alias"
      };
      expect($scope.canAddVLAN(nic)).toBe(false);
    });

    it("returns false if nic type is vlan", function() {
      makeController();
      var nic = {
        type: "vlan"
      };
      expect($scope.canAddVLAN(nic)).toBe(false);
    });

    it("returns false if no unused vlans", function() {
      makeController();
      var fabric = {
        id: 0
      };
      var vlans = [
        {
          id: 0,
          fabric: 0
        },
        {
          id: 1,
          fabric: 0
        },
        {
          id: 2,
          fabric: 0
        }
      ];
      var originalInterfaces = [
        {
          id: 0,
          type: "physical",
          parents: [],
          children: [1, 2, 3],
          vlan_id: 0
        },
        {
          id: 1,
          type: "vlan",
          parents: [0],
          children: [],
          vlan_id: 0
        },
        {
          id: 2,
          type: "vlan",
          parents: [0],
          children: [],
          vlan_id: 1
        },
        {
          id: 3,
          type: "vlan",
          parents: [0],
          children: [],
          vlan_id: 2
        }
      ];
      var nic = {
        id: 0,
        type: "physical",
        fabric: fabric
      };
      $scope.originalInterfaces = originalInterfaces;
      $scope.vlans = vlans;
      expect($scope.canAddVLAN(nic)).toBe(false);
    });

    it("returns true if unused vlans", function() {
      makeController();
      var fabric = {
        id: 0
      };
      var vlans = [
        {
          id: 0,
          fabric: 0
        },
        {
          id: 1,
          fabric: 0
        },
        {
          id: 2,
          fabric: 0
        }
      ];
      var originalInterfaces = [
        {
          id: 0,
          type: "physical",
          parents: [],
          children: [1, 2, 3],
          vlan_id: 0
        },
        {
          id: 1,
          type: "vlan",
          parents: [0],
          children: [],
          vlan_id: 0
        },
        {
          id: 2,
          type: "vlan",
          parents: [0],
          children: [],
          vlan_id: 1
        }
      ];
      var nic = {
        id: 0,
        type: "physical",
        fabric: fabric
      };
      $scope.originalInterfaces = originalInterfaces;
      $scope.vlans = vlans;
      expect($scope.canAddVLAN(nic)).toBe(true);
    });
  });

  describe("canAddAnotherVLAN", function() {
    it("returns false if canAddVLAN returns false", function() {
      makeController();
      spyOn($scope, "canAddVLAN").and.returnValue(false);
      expect($scope.canAddAnotherVLAN()).toBe(false);
    });

    it("returns false if only 1 unused vlans", function() {
      makeController();
      var fabric = {
        id: 0
      };
      var vlans = [
        {
          id: 0,
          fabric: 0
        },
        {
          id: 1,
          fabric: 0
        },
        {
          id: 2,
          fabric: 0
        }
      ];
      var originalInterfaces = [
        {
          id: 0,
          type: "physical",
          parents: [],
          children: [1, 2, 3],
          vlan_id: 0
        },
        {
          id: 1,
          type: "vlan",
          parents: [0],
          children: [],
          vlan_id: 0
        },
        {
          id: 2,
          type: "vlan",
          parents: [0],
          children: [],
          vlan_id: 1
        }
      ];
      var nic = {
        id: 0,
        type: "physical",
        fabric: fabric
      };
      $scope.originalInterfaces = originalInterfaces;
      $scope.vlans = vlans;
      expect($scope.canAddAnotherVLAN(nic)).toBe(false);
    });

    it("returns true if more than 1 unused vlans", function() {
      makeController();
      var fabric = {
        id: 0
      };
      var vlans = [
        {
          id: 0,
          fabric: 0
        },
        {
          id: 1,
          fabric: 0
        },
        {
          id: 2,
          fabric: 0
        }
      ];
      var originalInterfaces = [
        {
          id: 0,
          type: "physical",
          parents: [],
          children: [1, 2, 3],
          vlan_id: 0
        },
        {
          id: 1,
          type: "vlan",
          parents: [0],
          children: [],
          vlan_id: 0
        }
      ];
      var nic = {
        id: 0,
        type: "physical",
        fabric: fabric
      };
      $scope.originalInterfaces = originalInterfaces;
      $scope.vlans = vlans;
      expect($scope.canAddAnotherVLAN(nic)).toBe(true);
    });
  });

  describe("getRemoveTypeText", function() {
    it("returns interface for physical interface", function() {
      makeController();
      var nic = {
        type: "physical"
      };
      expect($scope.getRemoveTypeText(nic)).toBe("interface");
    });

    it("returns VLAN for VLAN interface", function() {
      makeController();
      var nic = {
        type: "vlan"
      };
      expect($scope.getRemoveTypeText(nic)).toBe("VLAN");
    });

    it("returns type for other types", function() {
      makeController();
      var type = makeName("type");
      var nic = {
        type: type
      };
      expect($scope.getRemoveTypeText(nic)).toBe(type);
    });
  });

  describe("canBeRemoved", function() {
    it("false if isController", function() {
      makeController();
      $parentScope.isController = true;
      spyOn($scope, "isAllNetworkingDisabled").and.returnValue(false);
      expect($scope.canBeRemoved()).toBe(false);
    });

    it("false if no node editing", function() {
      makeController();
      $parentScope.isController = false;
      spyOn($scope, "isAllNetworkingDisabled").and.returnValue(true);
      expect($scope.canBeRemoved()).toBe(false);
    });

    it("true if node can be edited", function() {
      makeController();
      $parentScope.isController = false;
      spyOn($scope, "isAllNetworkingDisabled").and.returnValue(false);
      expect($scope.canBeRemoved()).toBe(true);
    });
  });

  describe("remove", function() {
    it("sets selectedMode to delete", function() {
      makeController();
      $scope.remove();
      expect($scope.selectedMode).toBe("delete");
    });
  });

  describe("quickRemove", function() {
    it("selects interface and sets selectedMode to delete", function() {
      makeController();
      var nic = {
        id: makeInteger(0, 100),
        link_id: makeInteger(0, 100)
      };
      $scope.quickRemove(nic);
      expect($scope.isInterfaceSelected(nic)).toBe(true);
      expect($scope.selectedMode).toBe("delete");
    });
  });

  describe("cancel", function() {
    it("clears newInterface and sets selectedMode to single", function() {
      makeController();
      var newInterface = {};
      $scope.newInterface = newInterface;
      $scope.selectedMode = "delete";
      $scope.cancel();
      expect($scope.newInterface).not.toBe(newInterface);
      expect($scope.selectedMode).toBe("single");
    });

    it("clears newInterface and create resets to none", function() {
      makeController();
      var newInterface = {};
      $scope.newInterface = newInterface;
      $scope.selectedMode = "create-physical";
      $scope.cancel();
      expect($scope.newInterface).not.toBe(newInterface);
      expect($scope.selectedMode).toBeNull();
    });

    it("clears newBondInterface and sets selectedMode to multi", function() {
      makeController();
      var newBondInterface = {};
      $scope.newBondInterface = newBondInterface;
      $scope.selectedMode = "create-bond";
      $scope.cancel();
      expect($scope.newBondInterface).not.toBe(newBondInterface);
      expect($scope.selectedMode).toBe("multi");
    });

    it("sets isChangingConnectionStatus to false", () => {
      makeController();
      $scope.isChangingConnectionStatus = true;
      $scope.cancel();
      expect($scope.isChangingConnectionStatus).toBe(false);
    });

    it("sets showEditWarning to false", () => {
      makeController();
      $scope.showEditWarning = true;
      $scope.cancel();
      expect($scope.showEditWarning).toBe(false);
    });
  });

  describe("confirmRemove", function() {
    it("sets selectedMode to none", function() {
      makeController();
      var nic = {
        id: makeInteger(0, 100),
        type: "physical",
        link_id: makeInteger(0, 100)
      };
      $scope.toggleInterfaceSelect(nic);
      $scope.selectedMode = "delete";

      spyOn(MachinesManager, "deleteInterface");
      $scope.confirmRemove(nic);

      expect($scope.selectedMode).toBeNull();
      expect($scope.selectedInterfaces).toEqual([]);
    });

    it("calls MachinesManager.deleteInterface", function() {
      makeController();
      var nic = {
        id: makeInteger(0, 100),
        type: "physical",
        link_id: makeInteger(0, 100)
      };
      $scope.toggleInterfaceSelect(nic);
      $scope.selectedMode = "delete";

      spyOn(MachinesManager, "deleteInterface");
      $scope.confirmRemove(nic);

      expect(MachinesManager.deleteInterface).toHaveBeenCalledWith(
        node,
        nic.id
      );
    });

    it("calls MachinesManager.unlinkSubnet", function() {
      makeController();
      var nic = {
        id: makeInteger(0, 100),
        type: "alias",
        link_id: makeInteger(0, 100)
      };
      $scope.toggleInterfaceSelect(nic);
      $scope.selectedMode = "delete";

      spyOn(MachinesManager, "unlinkSubnet");
      $scope.confirmRemove(nic);

      expect(MachinesManager.unlinkSubnet).toHaveBeenCalledWith(
        node,
        nic.id,
        nic.link_id
      );
    });

    it("removes nic from interfaces", function() {
      makeController();
      var nic = {
        id: makeInteger(0, 100),
        type: "alias",
        link_id: makeInteger(0, 100)
      };
      $scope.interfaces = [nic];
      $scope.toggleInterfaceSelect(nic);
      $scope.selectedMode = "delete";

      spyOn(MachinesManager, "unlinkSubnet");
      $scope.confirmRemove(nic);

      expect($scope.interfaces).toEqual([]);
    });
  });

  describe("add", function() {
    it("sets up newInterface for alias", function() {
      makeController();
      var vlan = { id: 0 };
      var subnet = { id: 0, vlan: 0 };
      $scope.subnets = [subnet];
      var nic = {
        id: makeInteger(0, 100),
        type: "physical",
        link_id: makeInteger(0, 100),
        vlan: vlan
      };

      $scope.add("alias", nic);
      expect($scope.newInterface).toEqual({
        type: "alias",
        vlan: vlan,
        subnet: subnet,
        mode: "auto",
        parent: nic,
        tags: []
      });
      expect($scope.newInterface.vlan).toBe(vlan);
      expect($scope.newInterface.subnet).toBe(subnet);
      expect($scope.newInterface.parent).toBe(nic);
      expect($scope.selectedMode).toBe("add");
    });

    it("sets up newInterface for vlan", function() {
      makeController();
      var fabric = {
        id: 0
      };
      var vlans = [
        {
          id: 0,
          fabric: 0
        },
        {
          id: 1,
          fabric: 0
        },
        {
          id: 2,
          fabric: 0
        }
      ];
      var originalInterfaces = [
        {
          id: 0,
          type: "physical",
          parents: [],
          children: [1],
          vlan_id: 0
        },
        {
          id: 1,
          type: "vlan",
          parents: [0],
          children: [],
          vlan_id: 0
        }
      ];
      var nic = {
        id: 0,
        type: "physical",
        link_id: -1,
        fabric: fabric,
        vlan: vlans[0]
      };
      $scope.originalInterfaces = originalInterfaces;
      $scope.vlans = vlans;
      $scope.newInterface = {
        vlan: vlans[1]
      };

      $scope.add("vlan", nic);
      expect($scope.newInterface).toEqual({
        type: "vlan",
        vlan: vlans[2],
        subnet: null,
        mode: "link_up",
        parent: nic,
        tags: []
      });
      expect($scope.newInterface.vlan).toBe(vlans[2]);
      expect($scope.newInterface.parent).toBe(nic);
      expect($scope.selectedMode).toBe("add");
    });
  });

  describe("quickAdd", function() {
    it("selects nic and calls add with alias", function() {
      makeController();
      var nic = {
        id: makeInteger(0, 100),
        link_id: makeInteger(0, 100)
      };

      $scope.selectedInterfaces = [{}, {}, {}];
      spyOn($scope, "canAddAlias").and.returnValue(true);
      spyOn($scope, "add");

      $scope.quickAdd(nic);
      expect($scope.selectedInterfaces).toEqual([$scope.getUniqueKey(nic)]);
      expect($scope.add).toHaveBeenCalledWith("alias", nic);
    });

    it("selects nic and calls add with vlan", function() {
      makeController();
      var nic = {
        id: makeInteger(0, 100),
        link_id: makeInteger(0, 100)
      };

      $scope.selectedInterfaces = [{}, {}, {}];
      spyOn($scope, "canAddAlias").and.returnValue(false);
      spyOn($scope, "add");

      $scope.quickAdd(nic);
      expect($scope.selectedInterfaces).toEqual([$scope.getUniqueKey(nic)]);
      expect($scope.add).toHaveBeenCalledWith("vlan", nic);
    });
  });

  describe("getAddName", function() {
    it("returns alias name based on links length", function() {
      makeController();
      var name = makeName("eth");
      var parent = {
        id: makeInteger(0, 100),
        name: name,
        link_id: makeInteger(0, 100),
        links: [{}, {}, {}]
      };
      $scope.newInterface = {
        type: "alias",
        parent: parent
      };

      expect($scope.getAddName()).toBe(name + ":3");
    });

    it("returns VLAN name based on VLAN vid", function() {
      makeController();
      var name = makeName("eth");
      var vid = makeInteger(0, 100);
      var parent = {
        id: makeInteger(0, 100),
        name: name,
        link_id: makeInteger(0, 100)
      };
      $scope.newInterface = {
        type: "vlan",
        parent: parent,
        vlan: {
          vid: vid
        }
      };

      expect($scope.getAddName()).toBe(name + "." + vid);
    });
  });

  describe("addTypeChanged", function() {
    it("reset properties based on the new type alias", function() {
      makeController();
      var vlan = { id: 0 };
      var subnet = { id: 0, vlan: 0 };
      $scope.subnets = [subnet];
      var parent = {
        id: makeInteger(0, 100),
        name: name,
        link_id: makeInteger(0, 100),
        vlan: vlan
      };
      $scope.newInterface = {
        type: "alias",
        parent: parent
      };
      $scope.addTypeChanged();

      expect($scope.newInterface.vlan).toBe(vlan);
      expect($scope.newInterface.subnet).toBe(subnet);
      expect($scope.newInterface.mode).toBe("auto");
    });

    it("reset properties based on the new type VLAN", function() {
      makeController();
      var fabric = {
        id: 0
      };
      var vlans = [
        {
          id: 0,
          fabric: 0
        },
        {
          id: 1,
          fabric: 0
        },
        {
          id: 2,
          fabric: 0
        }
      ];
      var originalInterfaces = [
        {
          id: 0,
          type: "physical",
          parents: [],
          children: [1],
          vlan_id: 0
        },
        {
          id: 1,
          type: "vlan",
          parents: [0],
          children: [],
          vlan_id: 0
        }
      ];
      var parent = {
        id: 0,
        type: "physical",
        link_id: -1,
        fabric: fabric,
        vlan: vlans[0]
      };

      $scope.originalInterfaces = originalInterfaces;
      $scope.vlans = vlans;
      $scope.newInterface = {
        type: "vlan",
        parent: parent
      };
      $scope.addTypeChanged();

      expect($scope.newInterface.vlan).toBe(vlans[1]);
      expect($scope.newInterface.subnet).toBeNull();
      expect($scope.newInterface.mode).toBe("link_up");
    });
  });

  describe("vlanChanged", function() {
    it("clears subnets on newInterface", function() {
      makeController();
      $scope.newInterface = {
        subnet: {}
      };
      $scope.vlanChanged($scope.newInterface);
      expect($scope.newInterface.subnet).toBeNull();
    });
  });

  describe("vlanChangedForm", function() {
    it("clears subnets on newInterface", function() {
      makeController();
      $scope.newInterface = {
        getValue: function(name) {
          return this["_" + name];
        },
        updateValue: function(name, val) {
          this["_" + name] = val;
        },
        _subnet: {}
      };
      $scope.vlanChangedForm("vlan", {}, $scope.newInterface);
      expect($scope.newInterface._subnet).toBeNull();
    });
  });

  describe("subnetChanged", function() {
    it("sets mode to link_up if no subnet", function() {
      makeController();
      $scope.newInterface = {
        mode: "auto"
      };
      $scope.subnetChanged($scope.newInterface);
      expect($scope.newInterface.mode).toBe("link_up");
    });

    it("leaves mode to alone when subnet", function() {
      makeController();
      $scope.newInterface = {
        mode: "auto",
        subnet: {}
      };
      $scope.subnetChanged($scope.newInterface);
      expect($scope.newInterface.mode).toBe("auto");
    });
  });

  describe("addInterface", function() {
    it("calls saveInterfaceLink with correct params", function() {
      makeController();
      var parent = {
        id: makeInteger(0, 100)
      };
      var subnet = {};
      $scope.newInterface = {
        type: "alias",
        mode: "auto",
        subnet: subnet,
        parent: parent
      };
      $scope.selectedInterfaces = [{}];
      $scope.selectedMode = "add";
      spyOn($scope, "saveInterfaceLink");
      $scope.addInterface();
      expect($scope.saveInterfaceLink).toHaveBeenCalledWith({
        id: parent.id,
        mode: "auto",
        subnet: subnet,
        ip_address: undefined
      });
      expect($scope.selectedMode).toBeNull();
      expect($scope.selectedInterfaces).toEqual([]);
      expect($scope.newInterface).toEqual({});
    });

    it("calls createVLANInterface with correct params", function() {
      makeController();
      var parent = {
        id: makeInteger(0, 100)
      };
      var vlan = {
        id: makeInteger(0, 100)
      };
      var subnet = {
        id: makeInteger(0, 100)
      };
      $scope.newInterface = {
        type: "vlan",
        mode: "auto",
        parent: parent,
        tags: [],
        vlan: vlan,
        subnet: subnet,
        ip_address: undefined
      };
      $scope.selectedInterfaces = [{}];
      $scope.selectedMode = "add";
      spyOn(MachinesManager, "createVLANInterface").and.returnValue(
        $q.defer().promise
      );

      $scope.addInterface();
      expect(MachinesManager.createVLANInterface).toHaveBeenCalledWith(node, {
        parent: parent.id,
        tags: [],
        vlan: vlan.id,
        mode: "auto",
        subnet: subnet.id,
        ip_address: undefined
      });
      expect($scope.selectedMode).toBeNull();
      expect($scope.selectedInterfaces).toEqual([]);
      expect($scope.newInterface).toEqual({});
    });

    it("calls add again with type", function() {
      makeController();
      var parent = {
        id: makeInteger(0, 100)
      };
      $scope.newInterface = {
        type: "alias",
        mode: "auto",
        subnet: {},
        parent: parent
      };
      var selection = [{}];
      $scope.selectedInterfaces = selection;
      $scope.selectedMode = "add";
      spyOn($scope, "saveInterfaceLink");
      spyOn($scope, "add");
      $scope.addInterface("alias");

      expect($scope.add).toHaveBeenCalledWith("alias", parent);
      expect($scope.selectedMode).toBe("add");
      expect($scope.selectedInterfaces).toBe(selection);
    });
  });

  describe("isDisabled", function() {
    it("returns false when in none, single, or multi mode", function() {
      makeController();
      $scope.canEdit = function() {
        return true;
      };
      // Node needs to be Ready or Broken for the mode to be considered.
      $scope.node = { status: "Ready" };
      $scope.selectedMode = null;
      expect($scope.isDisabled()).toBe(false);
      $scope.selectedMode = "single";
      expect($scope.isDisabled()).toBe(false);
      $scope.selectedMode = "multi";
      expect($scope.isDisabled()).toBe(false);
    });

    it("returns true when in delete, add, or create modes", function() {
      makeController();
      $scope.canEdit = function() {
        return true;
      };
      // Node needs to be Ready or Broken for the mode to be considered.
      $scope.node = { status: "Ready" };
      $scope.selectedMode = "create-bond";
      expect($scope.isDisabled()).toBe(true);
      $scope.selectedMode = "add";
      expect($scope.isDisabled()).toBe(true);
      $scope.selectedMode = "delete";
      expect($scope.isDisabled()).toBe(true);
    });

    it(`returns true when the node state
        is not 'Ready' or 'Broken'`, function() {
      makeController();
      $scope.canEdit = function() {
        return true;
      };
      $scope.node = { status: "Ready" };
      expect($scope.isDisabled()).toBe(false);
      $scope.node = { status: "Broken" };
      expect($scope.isDisabled()).toBe(false);
      [
        "New",
        "Commissioning",
        "Failed commissioning",
        "Missing",
        "Reserved",
        "Allocated",
        "Deploying",
        "Deployed",
        "Retired",
        "Failed deployment",
        "Releasing",
        "Releasing failed",
        "Disk erasing",
        "Failed disk erasing"
      ].forEach(function(s) {
        $scope.node = { state: s };
        expect($scope.isDisabled()).toBe(true);
      });
    });

    it("returns true if the user is not a superuser", function() {
      makeController();
      $scope.canEdit = function() {
        return false;
      };
      $scope.node = { status: "Ready" };
      expect($scope.isDisabled()).toBe(true);
      $scope.node = { status: "Broken" };
      expect($scope.isDisabled()).toBe(true);
    });
  });

  describe("isLimitedEditingAllowed", function() {
    it("returns false when not superuser", function() {
      makeController();
      $scope.canEdit = function() {
        return false;
      };
      expect($scope.isLimitedEditingAllowed()).toBe(false);
    });

    it("returns false when isController", function() {
      makeController();
      $scope.canEdit = function() {
        return true;
      };
      $parentScope.isController = true;
      expect($scope.isLimitedEditingAllowed()).toBe(false);
    });

    it("returns true when deployed and not vlan", function() {
      makeController();
      $scope.canEdit = function() {
        return true;
      };
      $parentScope.isController = false;
      $scope.node = {
        status: "Deployed"
      };
      var nic = {
        type: "physical"
      };
      expect($scope.isLimitedEditingAllowed(nic)).toBe(true);
    });
  });

  describe("isAllNetworkingDisabled", function() {
    it(
      "returns true if the user is not a superuser " +
        "and the node is not a device",
      function() {
        makeController();
        $parentScope.isDevice = false;
        $scope.canEdit = function() {
          return false;
        };
        expect($scope.isAllNetworkingDisabled()).toBe(true);
      }
    );

    it(
      "returns false if the user is not a superuser " +
        "and the node is not a device",
      function() {
        makeController();
        $parentScope.isDevice = true;
        $scope.canEdit = function() {
          return false;
        };
        expect($scope.isAllNetworkingDisabled()).toBe(false);
      }
    );

    it(
      "returns false when a non-controller node state " +
        "is 'New', 'Ready', 'Allocated' or 'Broken' and we are a superuser",
      function() {
        makeController();
        $scope.canEdit = function() {
          return true;
        };
        $scope.node = { status: "New" };
        expect($scope.isAllNetworkingDisabled()).toBe(false);
        $scope.node = { status: "Ready" };
        expect($scope.isAllNetworkingDisabled()).toBe(false);
        $scope.node = { status: "Failed testing" };
        expect($scope.isAllNetworkingDisabled()).toBe(false);
        $scope.node = { status: "Allocated" };
        expect($scope.isAllNetworkingDisabled()).toBe(false);
        $scope.node = { status: "Broken" };
        expect($scope.isAllNetworkingDisabled()).toBe(false);
        [
          "Commissioning",
          "Failed commissioning",
          "Missing",
          "Reserved",
          "Allocated",
          "Deploying",
          "Deployed",
          "Retired",
          "Failed deployment",
          "Releasing",
          "Releasing failed",
          "Disk erasing",
          "Failed disk erasing"
        ].forEach(function(s) {
          $scope.node = { state: s };
          expect($scope.isAllNetworkingDisabled()).toBe(true);
        });
      }
    );

    it(`returns false for controllers, in any state,
        even if superuser`, function() {
      makeController();
      $parentScope.isController = true;
      $scope.canEdit = function() {
        return true;
      };
      [
        "Ready",
        "Broken",
        "New",
        "Commissioning",
        "Failed commissioning",
        "Missing",
        "Reserved",
        "Allocated",
        "Deploying",
        "Deployed",
        "Retired",
        "Failed deployment",
        "Releasing",
        "Releasing failed",
        "Disk erasing",
        "Failed disk erasing"
      ].forEach(function(s) {
        $scope.node = { state: s };
        expect($scope.isAllNetworkingDisabled()).toBe(false);
      });
    });
  });

  describe("canCreateBond", function() {
    it("returns false if not in multi mode", function() {
      makeController();
      var modes = [null, "add", "delete", "single", "delete"];
      angular.forEach(modes, function(mode) {
        $scope.selectedMode = mode;
        expect($scope.canCreateBond()).toBe(false);
      });
    });

    it("returns false if selected interface is bond", function() {
      makeController();
      var nic1 = {
        id: makeInteger(0, 100),
        link_id: makeInteger(0, 100),
        type: "bond"
      };
      var nic2 = {
        id: makeInteger(0, 100),
        link_id: makeInteger(0, 100),
        type: "bond"
      };
      $scope.interfaces = [nic1, nic2];
      $scope.interfaceLinksMap = {};
      $scope.interfaceLinksMap[nic1.id] = {};
      $scope.interfaceLinksMap[nic1.id][nic1.link_id] = nic1;
      $scope.interfaceLinksMap[nic2.id] = {};
      $scope.interfaceLinksMap[nic2.id][nic2.link_id] = nic2;
      $scope.toggleInterfaceSelect(nic1);
      $scope.toggleInterfaceSelect(nic2);
      expect($scope.canCreateBond()).toBe(false);
    });

    it("returns false if selected interface is alias", function() {
      makeController();
      var nic1 = {
        id: makeInteger(0, 100),
        link_id: makeInteger(0, 100),
        type: "alias"
      };
      var nic2 = {
        id: makeInteger(101, 200),
        link_id: makeInteger(0, 100),
        type: "alias"
      };
      $scope.interfaces = [nic1, nic2];
      $scope.interfaceLinksMap = {};
      $scope.interfaceLinksMap[nic1.id] = {};
      $scope.interfaceLinksMap[nic1.id][nic1.link_id] = nic1;
      $scope.interfaceLinksMap[nic2.id] = {};
      $scope.interfaceLinksMap[nic2.id][nic2.link_id] = nic2;
      $scope.toggleInterfaceSelect(nic1);
      $scope.toggleInterfaceSelect(nic2);
      expect($scope.canCreateBond()).toBe(false);
    });

    it("returns false if not same selected vlan", function() {
      makeController();
      var nic1 = {
        id: makeInteger(0, 100),
        link_id: makeInteger(0, 100),
        type: "physical",
        vlan: {}
      };
      var nic2 = {
        id: makeInteger(101, 200),
        link_id: makeInteger(0, 100),
        type: "physical",
        vlan: {}
      };
      $scope.interfaces = [nic1, nic2];
      $scope.interfaceLinksMap = {};
      $scope.interfaceLinksMap[nic1.id] = {};
      $scope.interfaceLinksMap[nic1.id][nic1.link_id] = nic1;
      $scope.interfaceLinksMap[nic2.id] = {};
      $scope.interfaceLinksMap[nic2.id][nic2.link_id] = nic2;
      $scope.toggleInterfaceSelect(nic1);
      $scope.toggleInterfaceSelect(nic2);
      expect($scope.canCreateBond()).toBe(false);
    });

    it("returns true if same selected vlan", function() {
      makeController();
      var vlan = {};
      var nic1 = {
        id: makeInteger(0, 100),
        link_id: makeInteger(0, 100),
        type: "physical",
        vlan: vlan
      };
      var nic2 = {
        id: makeInteger(101, 200),
        link_id: makeInteger(0, 100),
        type: "physical",
        vlan: vlan
      };
      $scope.interfaces = [nic1, nic2];
      $scope.interfaceLinksMap = {};
      $scope.interfaceLinksMap[nic1.id] = {};
      $scope.interfaceLinksMap[nic1.id][nic1.link_id] = nic1;
      $scope.interfaceLinksMap[nic2.id] = {};
      $scope.interfaceLinksMap[nic2.id][nic2.link_id] = nic2;
      $scope.toggleInterfaceSelect(nic1);
      $scope.toggleInterfaceSelect(nic2);
      expect($scope.canCreateBond()).toBe(true);
    });
  });

  describe("isShowingCreateBond", function() {
    it("returns true in create-bond mode", function() {
      makeController();
      $scope.selectedMode = "create-bond";
      expect($scope.isShowingCreateBond()).toBe(true);
    });

    it("returns false in multi mode", function() {
      makeController();
      $scope.selectedMode = "multi";
      expect($scope.isShowingCreateBond()).toBe(false);
    });
  });

  describe("showCreateBond", function() {
    it("sets mode to create-bond", function() {
      makeController();
      $scope.selectedMode = "multi";
      spyOn($scope, "canCreateBond").and.returnValue(true);
      $scope.showCreateBond();
      expect($scope.selectedMode).toBe("create-bond");
    });

    it("creates the newBondInterface", function() {
      makeController();
      var vlan = {};
      var nic1 = {
        id: makeInteger(0, 100),
        link_id: makeInteger(0, 100),
        type: "physical",
        vlan: vlan
      };
      var nic2 = {
        id: makeInteger(101, 200),
        link_id: makeInteger(0, 100),
        type: "physical",
        vlan: vlan
      };
      $scope.interfaces = [nic1, nic2];
      $scope.interfaceLinksMap = {};
      $scope.interfaceLinksMap[nic1.id] = {};
      $scope.interfaceLinksMap[nic1.id][nic1.link_id] = nic1;
      $scope.interfaceLinksMap[nic2.id] = {};
      $scope.interfaceLinksMap[nic2.id][nic2.link_id] = nic2;
      $scope.toggleInterfaceSelect(nic1);
      $scope.toggleInterfaceSelect(nic2);
      $scope.showCreateBond();
      expect($scope.newBondInterface).toEqual({
        name: "bond0",
        parents: [nic1, nic2],
        primary: nic1,
        tags: [],
        mac_address: "",
        bond_mode: "active-backup",
        fabric: "",
        vlan: {},
        subnet: "",
        lacpRate: "fast",
        xmitHashPolicy: "layer2",
        bond_updelay: 0,
        bond_downdelay: 0,
        bond_miimon: 100
      });
    });
  });

  describe("toggleInterfaces", function() {
    it("sets isShowingInterfaces to false if showing", function() {
      makeController();
      $scope.isShowingInterfaces = true;
      $scope.toggleInterfaces();
      expect($scope.isShowingInterfaces).toBe(false);
    });

    it("sets isShowingInterfaces to true if not showing", function() {
      makeController();
      $scope.isShowingInterfaces = false;
      $scope.toggleInterfaces();
      expect($scope.isShowingInterfaces).toBe(true);
    });
  });

  describe("isCorrectInterfaceType", function() {
    var bondInterface = {
      id: 35,
      type: "physical"
    };

    var parents = [
      {
        id: 34,
        type: "physical"
      }
    ];

    it("returns true if not parent & type is same as parent", function() {
      makeController();
      expect($scope.isCorrectInterfaceType(bondInterface, parents)).toBe(true);
    });

    it("returns false if parent", function() {
      makeController();

      bondInterface.id = 34;

      expect($scope.isCorrectInterfaceType(bondInterface, parents)).toBe(false);
    });

    it("returns false is type is not same as parent", function() {
      makeController();

      bondInterface.id = 33;
      bondInterface.type = "vlan";

      expect($scope.isCorrectInterfaceType(bondInterface, parents)).toBe(false);
    });
  });

  describe("hasBootInterface", function() {
    it("returns false if bond has no members with is_boot", function() {
      makeController();
      $scope.newBondInterface = {
        parents: [
          {
            is_boot: false
          },
          {
            is_boot: false
          }
        ]
      };
      expect($scope.hasBootInterface($scope.newBondInterface)).toBe(false);
    });

    it("returns true if bond has member with is_boot", function() {
      makeController();
      $scope.newBondInterface = {
        parents: [
          {
            is_boot: false
          },
          {
            is_boot: true
          }
        ]
      };
      expect($scope.hasBootInterface($scope.newBondInterface)).toBe(true);
    });
  });

  describe("getInterfacePlaceholderMACAddress", function() {
    it("returns empty string if primary not set", function() {
      makeController();
      expect($scope.getInterfacePlaceholderMACAddress({})).toBe("");
    });

    it("returns the MAC address of the primary interface", function() {
      makeController();
      var mac_address = makeName("mac");
      $scope.newBondInterface.primary = {
        mac_address: mac_address
      };
      expect(
        $scope.getInterfacePlaceholderMACAddress($scope.newBondInterface)
      ).toBe(mac_address);
    });
  });

  describe("isMACAddressInvalid", function() {
    it(`returns false when the mac_address blank
        and not invalidEmpty`, function() {
      makeController();
      expect($scope.isMACAddressInvalid("")).toBe(false);
    });

    it(`returns true when the mac_address
        is blank and invalidEmpty`, function() {
      makeController();
      expect($scope.isMACAddressInvalid("", true)).toBe(true);
    });

    it("returns false if valid mac_address", function() {
      makeController();
      expect($scope.isMACAddressInvalid("00:11:22:33:44:55")).toBe(false);
    });

    it("returns true if invalid mac_address", function() {
      makeController();
      expect($scope.isMACAddressInvalid("00:11:22:33:44")).toBe(true);
    });
  });

  describe("showLACPRate", function() {
    it("returns true if in 802.3ad mode", function() {
      makeController();
      $scope.newBondInterface.bond_mode = "802.3ad";
      expect($scope.showLACPRate()).toBe(true);
    });

    it("returns false if not in 802.3ad mode", function() {
      makeController();
      $scope.newBondInterface.bond_mode = makeName("otherMode");
      expect($scope.showLACPRate()).toBe(false);
    });
  });

  describe("modeAndPolicyCompliant", function() {
    it("returns true if policy is layer3+4", function() {
      makeController();
      $scope.newBondInterface.bond_mode = "802.3ad";
      $scope.newBondInterface.xmitHashPolicy = "layer3+4";
      expect($scope.showLACPRate()).toBe(true);
    });

    it("returns true if policy is encap3+4", function() {
      makeController();
      $scope.newBondInterface.bond_mode = "802.3ad";
      $scope.newBondInterface.xmitHashPolicy = "encap3+4";
      expect($scope.showLACPRate()).toBe(true);
    });

    it("returns false if 802.3ad compliant", function() {
      makeController();
      $scope.editInterface = {
        id: 0,
        link_id: -1
      };
      $scope.newBondInterface.bond_mode = "802.3ad";
      $scope.newBondInterface.xmitHashPolicy = "layer2+3";
      expect($scope.showLACPRate()).toBe(false);
    });
  });

  describe("showXMITHashPolicy", function() {
    it("returns true if in balance-xor mode", function() {
      makeController();
      $scope.newBondInterface.bond_mode = "balance-xor";
      expect($scope.showXMITHashPolicy()).toBe(true);
    });

    it("returns true if in 802.3ad mode", function() {
      makeController();
      $scope.newBondInterface.bond_mode = "802.3ad";
      expect($scope.showXMITHashPolicy()).toBe(true);
    });

    it("returns true if in balance-tlb mode", function() {
      makeController();
      $scope.newBondInterface.bond_mode = "balance-tlb";
      expect($scope.showXMITHashPolicy()).toBe(true);
    });

    it("returns false if not in other modes", function() {
      makeController();
      $scope.newBondInterface.bond_mode = makeName("otherMode");
      expect($scope.showXMITHashPolicy()).toBe(false);
    });
  });

  describe("cannotAddBond", function() {
    it("returns true when isInterfaceNameInvalid is true", function() {
      makeController();
      spyOn($scope, "isInterfaceNameInvalid").and.returnValue(true);
      expect($scope.cannotAddBond()).toBe(true);
    });

    it("returns true when isMACAddressInvalid is true", function() {
      makeController();
      spyOn($scope, "isInterfaceNameInvalid").and.returnValue(false);
      spyOn($scope, "isMACAddressInvalid").and.returnValue(true);
      expect($scope.cannotAddBond()).toBe(true);
    });

    it("returns false when both are false", function() {
      makeController();
      spyOn($scope, "isInterfaceNameInvalid").and.returnValue(false);
      spyOn($scope, "isMACAddressInvalid").and.returnValue(false);
      expect($scope.cannotAddBond()).toBe(false);
    });
  });

  describe("addBond", function() {
    it("does nothing if cannotAddBond returns true", function() {
      makeController();
      var vlan = {
        id: makeInteger(0, 100)
      };
      var nic1 = {
        id: makeInteger(0, 100),
        link_id: makeInteger(0, 100),
        type: "physical",
        vlan: vlan
      };
      var nic2 = {
        id: makeInteger(101, 200),
        link_id: makeInteger(0, 100),
        type: "physical",
        vlan: vlan
      };
      $scope.interfaces = [nic1, nic2];
      $scope.interfaceLinksMap = {};
      $scope.interfaceLinksMap[nic1.id] = {};
      $scope.interfaceLinksMap[nic1.id][nic1.link_id] = nic1;
      $scope.interfaceLinksMap[nic2.id] = {};
      $scope.interfaceLinksMap[nic2.id][nic2.link_id] = nic2;
      $scope.toggleInterfaceSelect(nic1);
      $scope.toggleInterfaceSelect(nic2);
      $scope.showCreateBond();

      spyOn(MachinesManager, "createBondInterface").and.returnValue(
        $q.defer().promise
      );
      spyOn($scope, "cannotAddBond").and.returnValue(true);
      $scope.newBondInterface.name = "bond0";
      $scope.newBondInterface.mac_address = "00:11:22:33:44:55";

      $scope.addBond();
      expect(MachinesManager.createBondInterface).not.toHaveBeenCalled();
    });

    it("calls createBondInterface and removes selection", function() {
      makeController();
      var vlan = {
        id: makeInteger(0, 100)
      };
      var subnet = {
        id: makeInteger(0, 100)
      };
      var nic1 = {
        id: makeInteger(0, 100),
        link_id: makeInteger(0, 100),
        type: "physical",
        vlan: vlan
      };
      var nic2 = {
        id: makeInteger(101, 200),
        link_id: makeInteger(0, 100),
        type: "physical",
        vlan: vlan
      };
      $scope.interfaces = [nic1, nic2];
      $scope.interfaceLinksMap = {};
      $scope.interfaceLinksMap[nic1.id] = {};
      $scope.interfaceLinksMap[nic1.id][nic1.link_id] = nic1;
      $scope.interfaceLinksMap[nic2.id] = {};
      $scope.interfaceLinksMap[nic2.id][nic2.link_id] = nic2;
      $scope.toggleInterfaceSelect(nic1);
      $scope.toggleInterfaceSelect(nic2);
      $scope.showCreateBond();

      spyOn(MachinesManager, "createBondInterface").and.returnValue(
        $q.defer().promise
      );
      spyOn($scope, "cannotAddBond").and.returnValue(false);
      $scope.newBondInterface.name = "bond0";
      $scope.newBondInterface.mac_address = "00:11:22:33:44:55";
      $scope.newBondInterface.vlan = vlan;
      $scope.newBondInterface.subnet = subnet;
      $scope.newBondInterface.mode = "static";
      $scope.newBondInterface.ip_address = "192.168.1.100";
      $scope.addBond();

      expect(MachinesManager.createBondInterface).toHaveBeenCalledWith(node, {
        name: "bond0",
        mac_address: "00:11:22:33:44:55",
        tags: [],
        parents: [nic1.id, nic2.id],
        bond_mode: "active-backup",
        bond_lacp_rate: "fast",
        bond_xmit_hash_policy: "layer2",
        vlan: vlan.id,
        subnet: subnet.id,
        mode: "static",
        ip_address: "192.168.1.100",
        bond_miimon: 100,
        bond_updelay: 0,
        bond_downdelay: 0
      });
      expect($scope.newBondInterface).toEqual({});
      expect($scope.selectedInterfaces).toEqual([]);
      expect($scope.selectedMode).toBeNull();
    });

    it("calls createBondInterface even when disconnected", function() {
      makeController();
      var nic1 = {
        id: makeInteger(0, 100),
        link_id: makeInteger(0, 100),
        type: "physical",
        vlan: null
      };
      var nic2 = {
        id: makeInteger(101, 200),
        link_id: makeInteger(0, 100),
        type: "physical",
        vlan: null
      };
      $scope.interfaces = [nic1, nic2];
      $scope.interfaceLinksMap = {};
      $scope.interfaceLinksMap[nic1.id] = {};
      $scope.interfaceLinksMap[nic1.id][nic1.link_id] = nic1;
      $scope.interfaceLinksMap[nic2.id] = {};
      $scope.interfaceLinksMap[nic2.id][nic2.link_id] = nic2;
      $scope.toggleInterfaceSelect(nic1);
      $scope.toggleInterfaceSelect(nic2);
      $scope.showCreateBond();

      spyOn(MachinesManager, "createBondInterface").and.returnValue(
        $q.defer().promise
      );
      spyOn($scope, "cannotAddBond").and.returnValue(false);
      $scope.newBondInterface.name = "bond0";
      $scope.newBondInterface.mac_address = "00:11:22:33:44:55";
      $scope.addBond();

      expect(MachinesManager.createBondInterface).toHaveBeenCalledWith(node, {
        name: "bond0",
        mac_address: "00:11:22:33:44:55",
        tags: [],
        parents: [nic1.id, nic2.id],
        bond_mode: "active-backup",
        bond_lacp_rate: "fast",
        bond_xmit_hash_policy: "layer2",
        vlan: undefined,
        subnet: null,
        mode: undefined,
        ip_address: undefined,
        bond_miimon: 100,
        bond_updelay: 0,
        bond_downdelay: 0
      });
      expect($scope.newBondInterface).toEqual({});
      expect($scope.selectedInterfaces).toEqual([]);
      expect($scope.selectedMode).toBeNull();
    });
  });

  describe("canCreateBridge", function() {
    it("returns false if not in single mode", function() {
      makeController();
      var modes = [null, "add", "delete", "multi", "delete"];
      angular.forEach(modes, function(mode) {
        $scope.selectedMode = mode;
        expect($scope.canCreateBridge()).toBe(false);
      });
    });

    it("returns false if selected interface is bridge", function() {
      makeController();
      var nic1 = {
        id: makeInteger(0, 100),
        link_id: makeInteger(0, 100),
        type: "bridge"
      };
      $scope.interfaces = [nic1];
      $scope.interfaceLinksMap = {};
      $scope.interfaceLinksMap[nic1.id] = {};
      $scope.interfaceLinksMap[nic1.id][nic1.link_id] = nic1;
      $scope.toggleInterfaceSelect(nic1);
      expect($scope.canCreateBridge()).toBe(false);
    });

    it("returns false if selected interface is alias", function() {
      makeController();
      var nic1 = {
        id: makeInteger(0, 100),
        link_id: makeInteger(0, 100),
        type: "alias"
      };
      $scope.interfaces = [nic1];
      $scope.interfaceLinksMap = {};
      $scope.interfaceLinksMap[nic1.id] = {};
      $scope.interfaceLinksMap[nic1.id][nic1.link_id] = nic1;
      $scope.toggleInterfaceSelect(nic1);
      expect($scope.canCreateBridge()).toBe(false);
    });

    it("returns false if muliple selected", function() {
      makeController();
      var nic1 = {
        id: makeInteger(0, 100),
        link_id: makeInteger(0, 100),
        type: "physical",
        vlan: {}
      };
      var nic2 = {
        id: makeInteger(101, 200),
        link_id: makeInteger(0, 100),
        type: "physical",
        vlan: {}
      };
      $scope.interfaces = [nic1, nic2];
      $scope.interfaceLinksMap = {};
      $scope.interfaceLinksMap[nic1.id] = {};
      $scope.interfaceLinksMap[nic1.id][nic1.link_id] = nic1;
      $scope.interfaceLinksMap[nic2.id] = {};
      $scope.interfaceLinksMap[nic2.id][nic2.link_id] = nic2;
      $scope.toggleInterfaceSelect(nic1);
      $scope.toggleInterfaceSelect(nic2);
      expect($scope.canCreateBridge()).toBe(false);
    });

    it("returns true if selected", function() {
      makeController();
      var vlan = {};
      var nic1 = {
        id: makeInteger(0, 100),
        link_id: makeInteger(0, 100),
        type: "physical",
        vlan: vlan
      };
      $scope.interfaces = [nic1];
      $scope.interfaceLinksMap = {};
      $scope.interfaceLinksMap[nic1.id] = {};
      $scope.interfaceLinksMap[nic1.id][nic1.link_id] = nic1;
      $scope.toggleInterfaceSelect(nic1);
      expect($scope.canCreateBridge()).toBe(true);
    });
  });

  describe("isShowingCreateBridge", function() {
    it("returns true in create-bridge mode", function() {
      makeController();
      $scope.selectedMode = "create-bridge";
      expect($scope.isShowingCreateBridge()).toBe(true);
    });

    it("returns false in single mode", function() {
      makeController();
      $scope.selectedMode = "single";
      expect($scope.isShowingCreateBridge()).toBe(false);
    });
  });

  describe("isShowingEdit", function() {
    it("returns true in edit mode", function() {
      makeController();
      $scope.selectedMode = "edit";
      expect($scope.isShowingEdit()).toBe(true);
    });

    it("returns false in single mode", function() {
      makeController();
      $scope.selectedMode = "single";
      expect($scope.isShowingEdit()).toBe(false);
    });
  });

  describe("showCreateBridge", function() {
    it("sets mode to create-bridge", function() {
      makeController();
      $scope.selectedMode = "single";
      spyOn($scope, "canCreateBridge").and.returnValue(true);
      $scope.showCreateBridge();
      expect($scope.selectedMode).toBe("create-bridge");
    });

    it("creates the newBridgeInterface", function() {
      makeController();
      var vlan = {};
      var nic1 = {
        id: makeInteger(0, 100),
        link_id: makeInteger(0, 100),
        type: "physical",
        vlan: vlan
      };
      $scope.interfaces = [nic1];
      $scope.interfaceLinksMap = {};
      $scope.interfaceLinksMap[nic1.id] = {};
      $scope.interfaceLinksMap[nic1.id][nic1.link_id] = nic1;
      $scope.toggleInterfaceSelect(nic1);
      $scope.showCreateBridge();
      expect($scope.newBridgeInterface).toEqual({
        name: "br0",
        parents: [nic1],
        primary: nic1,
        tags: [],
        mac_address: "",
        vlan: {},
        fabric: "",
        bridge_stp: false,
        bridge_fd: 15,
        bridge_type: "standard"
      });
    });
  });

  describe("cannotAddBridge", function() {
    it("returns true when isInterfaceNameInvalid is true", function() {
      makeController();
      spyOn($scope, "isInterfaceNameInvalid").and.returnValue(true);
      expect($scope.cannotAddBridge()).toBe(true);
    });

    it("returns true when isMACAddressInvalid is true", function() {
      makeController();
      spyOn($scope, "isInterfaceNameInvalid").and.returnValue(false);
      spyOn($scope, "isMACAddressInvalid").and.returnValue(true);
      expect($scope.cannotAddBridge()).toBe(true);
    });

    it("returns false when both are false", function() {
      makeController();
      spyOn($scope, "isInterfaceNameInvalid").and.returnValue(false);
      spyOn($scope, "isMACAddressInvalid").and.returnValue(false);
      expect($scope.cannotAddBridge()).toBe(false);
    });
  });

  describe("addBridge", function() {
    it("does nothing if cannotAddBridge returns true", function() {
      makeController();
      var vlan = {
        id: makeInteger(0, 100)
      };
      var nic1 = {
        id: makeInteger(0, 100),
        link_id: makeInteger(0, 100),
        type: "physical",
        vlan: vlan
      };
      $scope.interfaces = [nic1];
      $scope.interfaceLinksMap = {};
      $scope.interfaceLinksMap[nic1.id] = {};
      $scope.interfaceLinksMap[nic1.id][nic1.link_id] = nic1;
      $scope.toggleInterfaceSelect(nic1);
      $scope.showCreateBridge();

      spyOn(MachinesManager, "createBridgeInterface").and.returnValue(
        $q.defer().promise
      );
      spyOn($scope, "cannotAddBridge").and.returnValue(true);
      $scope.newBridgeInterface.name = "br0";
      $scope.newBridgeInterface.mac_address = "00:11:22:33:44:55";

      $scope.addBridge();
      expect(MachinesManager.createBridgeInterface).not.toHaveBeenCalled();
    });

    it("calls createBridgeInterface and removes selection", function() {
      makeController();
      var vlan = {
        id: makeInteger(0, 100)
      };
      var subnet = {
        id: makeInteger(0, 100)
      };
      var fabric = {
        id: makeInteger(0, 100)
      };
      var nic1 = {
        id: makeInteger(0, 100),
        link_id: makeInteger(0, 100),
        type: "physical",
        vlan: vlan,
        fabric: fabric
      };

      $scope.interfaces = [nic1];
      $scope.interfaceLinksMap = {};
      $scope.interfaceLinksMap[nic1.id] = {};
      $scope.interfaceLinksMap[nic1.id][nic1.link_id] = nic1;
      $scope.toggleInterfaceSelect(nic1);
      $scope.showCreateBridge();

      spyOn(MachinesManager, "createBridgeInterface").and.returnValue(
        $q.defer().promise
      );
      spyOn($scope, "cannotAddBridge").and.returnValue(false);
      $scope.newBridgeInterface.name = "br0";
      $scope.newBridgeInterface.mac_address = "00:11:22:33:44:55";
      $scope.newBridgeInterface.vlan = vlan;
      $scope.newBridgeInterface.subnet = subnet;
      $scope.newBridgeInterface.mode = "static";
      $scope.newBridgeInterface.ip_address = "192.168.1.100";
      $scope.addBridge();

      expect(MachinesManager.createBridgeInterface).toHaveBeenCalledWith(node, {
        name: "br0",
        mac_address: "00:11:22:33:44:55",
        tags: [],
        parents: [nic1.id],
        bridge_stp: false,
        bridge_fd: 15,
        bridge_type: "standard",
        vlan: vlan.id,
        subnet: subnet.id,
        mode: "static",
        ip_address: "192.168.1.100"
      });
      expect($scope.interfaces).toEqual([]);
      expect($scope.newBridgeInterface).toEqual({});
      expect($scope.selectedInterfaces).toEqual([]);
      expect($scope.selectedMode).toBeNull();
    });
  });

  describe("isShowingCreatePhysical", function() {
    it("returns true in create-physical mode", function() {
      makeController();
      $scope.selectedMode = "create-physical";
      expect($scope.isShowingCreatePhysical()).toBe(true);
    });

    it("returns false in single mode", function() {
      makeController();
      $scope.selectedMode = "single";
      expect($scope.isShowingCreatePhysical()).toBe(false);
    });
  });

  describe("showCreatePhysical", function() {
    it("sets mode to create-physical", function() {
      makeController();
      var vlan = { id: 0, fabric: 0 };
      var fabric = {
        id: 0,
        name: makeName("fabric"),
        default_vlan_id: 0,
        vlan_ids: [0]
      };
      VLANsManager._items = [vlan];
      $scope.fabrics = [fabric];
      $scope.selectedMode = null;
      $scope.showCreatePhysical();
      expect($scope.selectedMode).toBe("create-physical");
    });

    it("creates the newInterface", function() {
      makeController();
      var vlan = { id: 0, fabric: 0 };
      var fabric = {
        id: 0,
        name: makeName("fabric"),
        default_vlan_id: 0,
        vlan_ids: [0]
      };
      VLANsManager._items = [vlan];
      $scope.fabrics = [fabric];
      $scope.selectedMode = null;
      $scope.showCreatePhysical();
      expect($scope.newInterface).toEqual({
        name: "eth0",
        mac_address: "",
        macError: false,
        tags: [],
        errorMsg: null,
        fabric: fabric,
        vlan: vlan,
        subnet: null,
        mode: "link_up"
      });
    });
  });

  describe("fabricChanged", function() {
    it("sets newInterface.vlan with new fabric", function() {
      makeController();
      var vlan = { id: 0, fabric: 0 };
      var fabric = {
        id: 0,
        name: makeName("fabric"),
        default_vlan_id: 0,
        vlan_ids: [0]
      };
      VLANsManager._items = [vlan];
      $scope.newInterface.fabric = fabric;
      $scope.newInterface.subnet = {};
      $scope.newInterface.mode = "auto";
      $scope.fabricChanged($scope.newInterface);
      expect($scope.newInterface.vlan).toBe(vlan);
      expect($scope.newInterface.subnet).toBeNull();
      expect($scope.newInterface.mode).toBe("link_up");
    });
  });

  describe("fabricChangedForm", function() {
    it("sets newInterface.vlan with new fabric", function() {
      makeController();
      var vlan = { id: 0, fabric: 0 };
      var fabric = {
        id: 0,
        name: makeName("fabric"),
        default_vlan_id: 0,
        vlan_ids: [0]
      };
      VLANsManager._items = [vlan];
      $scope.newInterface._fabric = fabric;
      $scope.newInterface._subnet = {};
      $scope.newInterface._mode = "auto";
      $scope.newInterface.getValue = function(name) {
        return this["_" + name];
      };
      $scope.newInterface.updateValue = function(name, val) {
        this["_" + name] = val;
      };
      $scope.fabricChangedForm("fabric", fabric, $scope.newInterface);
      expect($scope.newInterface._vlan).toBe(vlan);
      expect($scope.newInterface._subnet).toBeNull();
      expect($scope.newInterface._mode).toBe("link_up");
    });
  });

  describe("subnetChanged", function() {
    it("sets mode to link_up when no subnet", function() {
      makeController();
      $scope.newInterface.subnet = null;
      $scope.newInterface.mode = "auto";
      $scope.subnetChanged($scope.newInterface);
      expect($scope.newInterface.mode).toBe("link_up");
    });

    it("leaves mode to original when subnet", function() {
      makeController();
      $scope.newInterface.subnet = {};
      $scope.newInterface.mode = "auto";
      $scope.subnetChanged($scope.newInterface);
      expect($scope.newInterface.mode).toBe("auto");
    });
  });

  describe("subnetChangedForm", function() {
    it("sets mode to link_up when no subnet", function() {
      makeController();
      $scope.newInterface = {
        getValue: function(name) {
          return this["_" + name];
        },
        updateValue: function(name, val) {
          this["_" + name] = val;
        },
        _subnet: null,
        _mode: "auto"
      };
      $scope.subnetChangedForm("subnet", null, $scope.newInterface);
      expect($scope.newInterface._mode).toBe("link_up");
    });

    it("leaves mode to original when subnet", function() {
      makeController();
      $scope.newInterface = {
        getValue: function(name) {
          return this["_" + name];
        },
        updateValue: function(name, val) {
          this["_" + name] = val;
        },
        _subnet: {},
        _mode: "auto"
      };
      $scope.subnetChangedForm("subnet", {}, $scope.newInterface);
      expect($scope.newInterface._mode).toBe("auto");
    });
  });

  describe("cannotAddPhysicalInterface", function() {
    it("returns true when isInterfaceNameInvalid is true", function() {
      makeController();
      spyOn($scope, "isInterfaceNameInvalid").and.returnValue(true);
      expect($scope.cannotAddPhysicalInterface()).toBe(true);
    });

    it("returns true when isMACAddressInvalid is true", function() {
      makeController();
      spyOn($scope, "isInterfaceNameInvalid").and.returnValue(false);
      spyOn($scope, "isMACAddressInvalid").and.returnValue(true);
      expect($scope.cannotAddPhysicalInterface()).toBe(true);
    });

    it("returns false when both are false", function() {
      makeController();
      spyOn($scope, "isInterfaceNameInvalid").and.returnValue(false);
      spyOn($scope, "isMACAddressInvalid").and.returnValue(false);
      expect($scope.cannotAddPhysicalInterface()).toBe(false);
    });
  });

  describe("addPhysicalInterface", function() {
    it("does nothing if cannotAddInterface returns true", function() {
      makeController();
      var vlan = {
        id: makeInteger(0, 100)
      };
      var subnet = {
        id: makeInteger(0, 100)
      };
      $scope.newInterface = {
        name: "eth0",
        mac_address: "00:11:22:33:44:55",
        tags: [],
        vlan: vlan,
        subnet: subnet,
        mode: "auto"
      };

      spyOn(MachinesManager, "createPhysicalInterface").and.returnValue(
        $q.defer().promise
      );
      spyOn($scope, "cannotAddPhysicalInterface").and.returnValue(true);
      $scope.addPhysicalInterface();

      expect(MachinesManager.createPhysicalInterface).not.toHaveBeenCalled();
    });

    it("calls createPhysicalInterface and removes selection", function() {
      makeController();
      var vlan = {
        id: makeInteger(0, 100)
      };
      var subnet = {
        id: makeInteger(0, 100)
      };
      $scope.newInterface = {
        name: "eth0",
        mac_address: "00:11:22:33:44:55",
        tags: [],
        vlan: vlan,
        subnet: subnet,
        mode: "auto"
      };
      $scope.selectedMode = "create-physical";

      var defer = $q.defer();
      spyOn(MachinesManager, "createPhysicalInterface").and.returnValue(
        defer.promise
      );
      spyOn($scope, "cannotAddPhysicalInterface").and.returnValue(false);
      $scope.addPhysicalInterface();
      defer.resolve();
      $scope.$digest();

      expect(MachinesManager.createPhysicalInterface).toHaveBeenCalledWith(
        node,
        {
          name: "eth0",
          mac_address: "00:11:22:33:44:55",
          tags: [],
          vlan: vlan.id,
          subnet: subnet.id,
          mode: "auto",
          ip_address: undefined
        }
      );
      expect($scope.newInterface).toEqual({});
      expect($scope.selectedMode).toBeNull();
    });

    it("clears error on call", function() {
      makeController();
      var vlan = {
        id: makeInteger(0, 100)
      };
      var subnet = {
        id: makeInteger(0, 100)
      };
      $scope.newInterface = {
        name: "eth0",
        mac_address: "00:11:22:33:44:55",
        tags: [],
        vlan: vlan,
        subnet: subnet,
        mode: "auto",
        macError: true,
        errorMsg: "error"
      };

      var defer = $q.defer();
      spyOn(MachinesManager, "createPhysicalInterface").and.returnValue(
        defer.promise
      );
      spyOn($scope, "cannotAddPhysicalInterface").and.returnValue(false);
      $scope.addPhysicalInterface();

      expect($scope.newInterface.macError).toBe(false);
      expect($scope.newInterface.errorMsg).toBeNull();
    });

    it("handles mac_address error", function() {
      makeController();
      var vlan = {
        id: makeInteger(0, 100)
      };
      var subnet = {
        id: makeInteger(0, 100)
      };
      $scope.newInterface = {
        name: "eth0",
        mac_address: "00:11:22:33:44:55",
        tags: [],
        vlan: vlan,
        subnet: subnet,
        mode: "auto"
      };

      var defer = $q.defer();
      spyOn(MachinesManager, "createPhysicalInterface").and.returnValue(
        defer.promise
      );
      spyOn($scope, "cannotAddPhysicalInterface").and.returnValue(false);
      $scope.addPhysicalInterface();

      var error = {
        mac_address: ["MACAddress is already in use"]
      };
      defer.reject(angular.toJson(error));
      $scope.$digest();

      expect($scope.newInterface.macError).toBe(true);
      expect($scope.newInterface.errorMsg).toBe("MACAddress is already in use");
    });
  });

  describe("isBond", function() {
    it("returns true if has type of bond", function() {
      makeController();
      var item = { type: "bond" };
      expect($scope.isBond(item)).toBe(true);
    });

    it("returns false if doesn't have type of bond", function() {
      makeController();
      var item = { type: "physical" };
      expect($scope.isBond(item)).toBe(false);
    });
  });

  describe("isBridge", function() {
    it("returns true if has type of bridge", function() {
      makeController();
      var item = { type: "bridge" };
      expect($scope.isBridge(item)).toBe(true);
    });

    it("returns false if doesn't have type of bridge", function() {
      makeController();
      var item = { type: "physical" };
      expect($scope.isBridge(item)).toBe(false);
    });
  });

  describe("isInterface", function() {
    it("returns true if has type of physical", function() {
      makeController();
      var item = { type: "physical" };
      expect($scope.isInterface(item)).toBe(true);
    });

    it("returns false if doesn't have type of physical", function() {
      makeController();
      var item = { type: "bond" };
      expect($scope.isInterface(item)).toBe(false);
    });
  });

  describe("showEditButton", function() {
    it("returns true if all conditions are met", function() {
      makeController();

      var editInterface = {
        id: "foo",
        type: "bond",
        fabric: {
          name: "fabric-1"
        },
        vlan: {
          id: 2
        },
        members: []
      };

      var interfaces = [
        {
          id: "foo",
          fabric: {
            name: "fabric-1"
          },
          vlan: {
            id: 2
          }
        },
        {
          id: "bar",
          fabric: {
            name: "fabric-1"
          },
          vlan: {
            id: 2
          }
        },
        {
          id: "baz",
          fabric: {
            name: "fabric-1"
          },
          vlan: {
            id: 2
          }
        }
      ];

      expect($scope.showEditButton(editInterface, interfaces)).toBe(true);
    });

    it("returns false if editInterface is not bond", function() {
      makeController();
      var editInterface = {
        id: "foo",
        type: "physical",
        fabric: {
          name: "fabric-1"
        }
      };
      var interfaces = [
        { id: "foo", fabric: { name: "fabric-1" } },
        { id: "bar", fabric: { name: "fabric-1" } },
        { id: "baz", fabric: { name: "fabric-1" } }
      ];
      expect($scope.showEditButton(editInterface, interfaces)).toBe(false);
    });

    it("returns false if no interfaces", function() {
      makeController();
      var editInterface = {
        id: "foo",
        type: "bond",
        fabric: {
          name: "fabric-1"
        },
        members: []
      };
      var interfaces = [];
      expect($scope.showEditButton(editInterface, interfaces)).toBe(false);
    });
  });

  describe("showCreateEditButton", function() {
    it("returns true if interfaces exist", function() {
      makeController();
      $scope.selectedInterfaces = [];
      $scope.newBondInterface = {
        id: "bar",
        fabric: {
          name: "fabric-1"
        },
        vlan: {
          id: 2
        }
      };
      $scope.interfaces = [
        { id: "foo", fabric: { name: "fabric-1" }, vlan: { id: 2 } }
      ];
      expect($scope.showCreateEditButton()).toBe(true);
    });

    it("returns false if no interfaces", function() {
      makeController();
      $scope.selectedInterfaces = [];
      $scope.newBondInterface = {
        id: "bar",
        fabric: {
          name: "fabric-1"
        }
      };
      $scope.interfaces = [];
      expect($scope.showCreateEditButton()).toBe(false);
    });
  });

  describe("toggleEditInterfaceSelect", function() {
    it("adds item to selectedInterfaces", function() {
      makeController();
      var nic = {
        id: 1,
        link_id: -1
      };
      $scope.editInterface = {
        id: 2,
        link_id: -1,
        vlan: { id: 2 },
        fabric: { name: "fabric-2" },
        members: [],
        parents: []
      };
      $scope.selectedInterfaces = [];
      $scope.toggleEditInterfaceSelect(nic);
      expect($scope.selectedInterfaces).toEqual(["1/-1"]);
    });

    it("adds item to interfaces", function() {
      makeController();
      var nic = {
        id: 1,
        link_id: -1,
        vlan: { id: 2 },
        fabric: { name: "fabric-2" }
      };
      $scope.editInterface = {
        id: 2,
        link_id: -1,
        vlan: { id: 2 },
        fabric: { name: "fabric-2" },
        members: [],
        parents: [],
        primary: nic
      };
      $scope.selectedInterfaces = ["1/-1"];
      $scope.interfaces = [];
      $scope.toggleEditInterfaceSelect(nic);
      expect($scope.interfaces).toEqual([nic]);
    });

    it("adds item to members", function() {
      makeController();
      var nic = {
        id: 1,
        link_id: -1,
        vlan: { id: 2 },
        fabric: { name: "fabric-2" }
      };
      $scope.editInterface = {
        id: 2,
        link_id: -1,
        vlan: { id: 2 },
        fabric: { name: "fabric-2" },
        members: [],
        parents: []
      };
      $scope.selectedInterfaces = [];
      $scope.toggleEditInterfaceSelect(nic);
      expect($scope.editInterface.members).toEqual([nic]);
    });

    it("adds item to parents", function() {
      makeController();
      var nic = {
        id: 1,
        link_id: -1,
        vlan: { id: 2 },
        fabric: { name: "fabric-2" }
      };
      $scope.editInterface = {
        id: 2,
        link_id: -1,
        vlan: { id: 2 },
        fabric: { name: "fabric-2" },
        members: [],
        parents: []
      };
      $scope.selectedInterfaces = [];
      $scope.toggleEditInterfaceSelect(nic);
      expect($scope.editInterface.parents).toEqual([nic.id]);
    });

    it("removes item from selectedInterfaces", function() {
      makeController();
      var nic = {
        id: 1,
        link_id: -1
      };
      $scope.editInterface = {
        id: 2,
        link_id: -1,
        vlan: { id: 2 },
        fabric: { name: "fabric-2" },
        members: [],
        parents: [],
        primary: nic
      };
      $scope.selectedInterfaces = ["1/-1"];
      $scope.toggleEditInterfaceSelect(nic);
      expect($scope.selectedInterfaces).toEqual([]);
    });

    it("removes item from interfaces", function() {
      makeController();
      var nic = {
        id: 1,
        link_id: -1,
        vlan: { id: 2 },
        fabric: { name: "fabric-2" }
      };
      $scope.editInterface = {
        id: 2,
        link_id: -1,
        vlan: { id: 2 },
        fabric: { name: "fabric-2" },
        members: [],
        parents: []
      };
      $scope.selectedInterfaces = [];
      $scope.interfaces = [nic];
      $scope.toggleEditInterfaceSelect(nic);
      expect($scope.interfaces).toEqual([]);
    });

    it("removes item from members", function() {
      makeController();
      var nic = {
        id: 1,
        link_id: -1,
        vlan: { id: 2 },
        fabric: { name: "fabric-2" }
      };
      $scope.editInterface = {
        id: 2,
        link_id: -1,
        vlan: { id: 2 },
        fabric: { name: "fabric-2" },
        members: [nic],
        parents: [],
        primary: nic
      };
      $scope.selectedInterfaces = ["1/-1"];
      $scope.toggleEditInterfaceSelect(nic);
      expect($scope.editInterface.members).toEqual([]);
    });

    it("removes item from parents", function() {
      makeController();
      var nic = {
        id: 1,
        link_id: -1,
        vlan: { id: 2 },
        fabric: { name: "fabric-2" }
      };
      $scope.editInterface = {
        id: 2,
        link_id: -1,
        vlan: { id: 2 },
        fabric: { name: "fabric-2" },
        members: [],
        parents: [nic.id],
        primary: nic
      };
      $scope.selectedInterfaces = ["1/-1"];
      $scope.toggleEditInterfaceSelect(nic);
      expect($scope.editInterface.parents).toEqual([]);
    });
  });

  describe("getDHCPStatus", () => {
    it("returns correct text if dhcp is provided by MAAS", () => {
      makeController();
      const vlan = { external_dhcp: null, dhcp_on: true };
      expect($scope.getDHCPStatus(vlan)).toEqual("MAAS-provided");
    });

    it("returns correct text if dhcp is provided externally", () => {
      makeController();
      const vlan = { external_dhcp: "127.0.0.1", dhcp_on: true };
      expect($scope.getDHCPStatus(vlan)).toEqual("External (127.0.0.1)");
    });

    it("returns correct text if dhcp is disabled", () => {
      makeController();
      const vlan = { external_dhcp: null, dhcp_on: false };
      expect($scope.getDHCPStatus(vlan)).toEqual("No DHCP");
    });

    it("returns correct text if vlan is null", () => {
      makeController();
      expect($scope.getDHCPStatus(null)).toEqual("No DHCP");
    });
  });

  describe("changeConnectionStatus", () => {
    it("sets isChangingConnectionStatus to true", () => {
      makeController();
      $scope.isChangingConnectionStatus = false;
      $scope.changeConnectionStatus({});
      expect($scope.isChangingConnectionStatus).toBe(true);
    });

    it("sets showEditWarning to false", () => {
      makeController();
      $scope.showEditWarning = true;
      $scope.changeConnectionStatus({});
      expect($scope.showEditWarning).toBe(false);
    });

    it("sets selected interfaces to supplied nic", () => {
      makeController();
      const nic = {
        id: 1,
        link_id: -1,
        vlan: { id: 2 },
        fabric: { name: "fabric-2" }
      };
      $scope.changeConnectionStatus(nic);
      expect($scope.selectedInterfaces).toEqual(["1/-1"]);
    });
  });

  describe("getNetworkTestingStatus", () => {
    it("returns nothing if all tests pass", () => {
      makeController();
      $scope.networkTestingResults = {
        "eth-OoUNoz (e4:4c:80:18:90:15)": [
          { status_name: "Passed", name: "Test script 1" },
          { status_name: "Passed", name: "Test script 2" }
        ]
      };
      expect(
        $scope.getNetworkTestingStatus({
          name: "eth-OoUNoz",
          mac_address: "e4:4c:80:18:90:15"
        })
      ).toBeUndefined();
    });

    it("returns n failed tests if multiple failed", () => {
      makeController();
      $scope.networkTestingResults = {
        "eth-OoUNoz (e4:4c:80:18:90:15)": [
          { status_name: "Passed", name: "Test script 1" },
          { status_name: "Failed", name: "Test script 2" },
          { status_name: "Failed", name: "Test script 3" }
        ]
      };
      expect(
        $scope.getNetworkTestingStatus({
          name: "eth-OoUNoz",
          mac_address: "e4:4c:80:18:90:15"
        })
      ).toEqual("2 failed tests");
    });

    it("returns failed test name if only one failed", () => {
      makeController();
      $scope.networkTestingResults = {
        "eth-OoUNoz (e4:4c:80:18:90:15)": [
          { status_name: "Passed", name: "Test script 1" },
          { status_name: "Passed", name: "Test script 2" },
          { status_name: "Failed", name: "Test script 3" }
        ]
      };
      expect(
        $scope.getNetworkTestingStatus({
          name: "eth-OoUNoz",
          mac_address: "e4:4c:80:18:90:15"
        })
      ).toEqual("Test script 3 failed");
    });
  });

  describe("handleEdit", () => {
    it("calls edit method if connected", () => {
      makeController();
      const nic = {
        id: 1,
        link_id: -1,
        vlan: { id: 2 },
        fabric: { name: "fabric-2" },
        link_connected: true,
        type: "physical"
      };
      spyOn($scope, "edit");
      $scope.handleEdit(nic);
      expect($scope.edit).toHaveBeenCalled();
    });

    it("calls edit method if not a physical interface", () => {
      makeController();
      const nic = {
        id: 1,
        link_id: -1,
        vlan: { id: 2 },
        fabric: { name: "fabric-2" },
        link_connected: false,
        type: "bond"
      };
      spyOn($scope, "edit");
      $scope.handleEdit(nic);
      expect($scope.edit).toHaveBeenCalled();
    });

    it("doesn't call edit method if not connected", () => {
      makeController();
      const nic = {
        id: 1,
        link_id: -1,
        vlan: { id: 2 },
        fabric: { name: "fabric-2" },
        link_connected: false,
        type: "physical"
      };
      spyOn($scope, "edit");
      $scope.handleEdit(nic);
      expect($scope.edit).not.toHaveBeenCalled();
    });

    it("sets selected interfaces to supplied nic", () => {
      makeController();
      const nic = {
        id: 1,
        link_id: -1,
        vlan: { id: 2 },
        fabric: { name: "fabric-2" },
        type: "physical"
      };
      $scope.handleEdit(nic);
      expect($scope.selectedInterfaces).toEqual(["1/-1"]);
    });
  });

  describe("canMarkAsConnected", () => {
    it("returns false if nic type is not physical", () => {
      makeController();
      const nic = {
        type: "bond",
        link_connected: false
      };
      $scope.selectedMode = null;
      expect($scope.canMarkAsConnected(nic)).toBe(false);
    });

    it("returns false if link is connected", () => {
      makeController();
      const nic = {
        type: "physical",
        link_connected: true
      };
      $scope.selectedMode = null;
      expect($scope.canMarkAsConnected(nic)).toBe(false);
    });

    it("returns false if cannotEditInterface is true", () => {
      makeController();
      const nic = {
        type: "physical",
        link_connected: false
      };
      $scope.selectedMode = "multi";
      $scope.selectedInterfaces = [];
      expect($scope.canMarkAsConnected(nic)).toBe(false);
    });

    it("returns true if all conditions are met", () => {
      makeController();
      const nic = {
        type: "physical",
        link_connected: false
      };
      $scope.selectedMode = null;
      expect($scope.canMarkAsConnected(nic)).toBe(true);
    });
  });

  describe("canMarkAsDisconnected", () => {
    it("returns false if nic type is not physical", () => {
      makeController();
      const nic = {
        type: "bond",
        link_connected: true
      };
      $scope.selectedMode = null;
      expect($scope.canMarkAsDisconnected(nic)).toBe(false);
    });

    it("returns false if link is disconnected", () => {
      makeController();
      const nic = {
        type: "physical",
        link_connected: false
      };
      $scope.selectedMode = null;
      expect($scope.canMarkAsDisconnected(nic)).toBe(false);
    });

    it("returns false if cannotEditInterface is true", () => {
      makeController();
      const nic = {
        id: makeInteger(0, 100),
        link_id: makeInteger(0, 100),
        type: "physical",
        link_connected: true
      };
      $scope.selectedMode = "multi";
      $scope.selectedInterfaces = [];
      expect($scope.canMarkAsDisconnected(nic)).toBe(false);
    });

    it("returns true if all conditions are met", () => {
      makeController();
      const nic = {
        type: "physical",
        link_connected: true
      };
      $scope.selectedMode = null;
      expect($scope.canMarkAsDisconnected(nic)).toBe(true);
    });
  });

  describe("validateNetworkConfiguration", () => {
    it("calls $parent.openTestDropdown", () => {
      makeController();
      $scope.$parent.openTestDropdown = () => true;
      spyOn($scope.$parent, "openTestDropdown");
      $scope.validateNetworkConfiguration();
      expect($scope.$parent.openTestDropdown).toHaveBeenCalledWith(
        "validateNetwork"
      );
    });
  });

  describe("formatSpeedUnits", () => {
    it("returns a hyphen if no argument", () => {
      makeController();
      expect($scope.formatSpeedUnits()).toEqual("-");
    });

    it("returns a hyphen if argument is 0", () => {
      makeController();
      expect($scope.formatSpeedUnits(0)).toEqual("-");
    });

    it("returns argument with Mbps if less than GB", () => {
      makeController();
      expect($scope.formatSpeedUnits(999)).toEqual("999 Mbps");
    });

    it("returns argument with Gbps if more than GB and less than TB", () => {
      makeController();
      expect($scope.formatSpeedUnits(1024)).toEqual("1 Gbps");
    });

    it("returns argument with Tbps if more than TB", () => {
      makeController();
      expect($scope.formatSpeedUnits(2000000)).toEqual("2 Tbps");
    });
  });

  describe("getInterfaceNumaNodes", () => {
    it("returns an interface's numa node if it has no parents", () => {
      makeController();
      const iface = {
        numa_node: 2,
        parents: []
      };
      expect($scope.getInterfaceNumaNodes(iface)).toEqual([2]);
    });

    it("returns numa nodes of interface and its parents", () => {
      makeController();
      $scope.originalInterfaces = {
        0: { numa_node: 0 },
        1: { numa_node: 1 }
      };
      const iface = {
        numa_node: 2,
        parents: [0, 1]
      };
      expect($scope.getInterfaceNumaNodes(iface)).toEqual([0, 1, 2]);
    });
  });
});
