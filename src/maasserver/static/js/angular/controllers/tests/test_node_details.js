/* Copyright 2015-2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for NodeDetailsController.
 */

import { makeInteger, makeName } from "testing/utils";
import MockWebSocket from "testing/websocket";

// Make a fake user.
var userId = 0;
function makeUser() {
  return {
    id: userId++,
    username: makeName("username"),
    first_name: makeName("first_name"),
    last_name: makeName("last_name"),
    email: makeName("email"),
    is_superuser: false,
    sshkeys_count: 0
  };
}

describe("NodeDetailsController", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Grab the needed angular pieces.
  var $controller, $rootScope, $location, $scope, $q, $log;
  beforeEach(inject(function($injector) {
    $controller = $injector.get("$controller");
    $rootScope = $injector.get("$rootScope");
    $location = $injector.get("$location");
    $scope = $rootScope.$new();
    $q = $injector.get("$q");
    $log = $injector.get("$log");
  }));

  // Load the required dependencies for the NodeDetails controller and
  // mock the websocket connection.
  var MachinesManager, ControllersManager, ServicesManager, FabricsManager;
  var DevicesManager, GeneralManager, UsersManager, DomainsManager;
  var TagsManager, RegionConnection, ManagerHelperService, ErrorService;
  var ScriptsManager, ResourcePoolsManager, VLANsManager, ZonesManager;
  var webSocket;
  beforeEach(inject(function($injector) {
    MachinesManager = $injector.get("MachinesManager");
    DevicesManager = $injector.get("DevicesManager");
    ControllersManager = $injector.get("ControllersManager");
    ZonesManager = $injector.get("ZonesManager");
    ResourcePoolsManager = $injector.get("ResourcePoolsManager");
    GeneralManager = $injector.get("GeneralManager");
    UsersManager = $injector.get("UsersManager");
    TagsManager = $injector.get("TagsManager");
    DomainsManager = $injector.get("DomainsManager");
    RegionConnection = $injector.get("RegionConnection");
    ManagerHelperService = $injector.get("ManagerHelperService");
    ServicesManager = $injector.get("ServicesManager");
    ErrorService = $injector.get("ErrorService");
    ScriptsManager = $injector.get("ScriptsManager");
    VLANsManager = $injector.get("VLANsManager");
    FabricsManager = $injector.get("FabricsManager");

    // Mock buildSocket so an actual connection is not made.
    webSocket = new MockWebSocket();
    spyOn(RegionConnection, "buildSocket").and.returnValue(webSocket);
    spyOn(RegionConnection, "callMethod").and.returnValue($q.defer().promise);
  }));

  // Make a fake zone.
  function makeZone() {
    var zone = {
      id: makeInteger(0, 10000),
      name: makeName("zone")
    };
    ZonesManager._items.push(zone);
    return zone;
  }

  // Make a fake resource pool.
  function makeResourcePool() {
    var pool = {
      id: makeInteger(0, 10000),
      name: makeName("pool")
    };
    ResourcePoolsManager._items.push(pool);
    return pool;
  }

  // Make a fake node.
  function makeNode() {
    var zone = makeZone();
    var pool = makeResourcePool();
    var node = {
      system_id: makeName("system_id"),
      hostname: makeName("hostname"),
      fqdn: makeName("fqdn"),
      actions: [],
      architecture: "amd64/generic",
      zone: angular.copy(zone),
      pool: angular.copy(pool),
      node_type: 0,
      power_type: "",
      power_parameters: null,
      summary_xml: null,
      summary_yaml: null,
      commissioning_results: [],
      testing_results: [],
      installation_results: [],
      events: [],
      interfaces: [],
      extra_macs: [],
      cpu_count: makeInteger(0, 64),
      commissioning_status: {},
      testing_status: {},
      numa_nodes: [
        {
          index: 0,
          cores: [0, 1],
          memory: 1024
        },
        {
          index: 1,
          cores: [2, 3],
          memory: 1024
        }
      ]
    };
    MachinesManager._items.push(node);
    return node;
  }

  // Make a fake event.
  function makeEvent() {
    return {
      type: {
        description: makeName("type")
      },
      description: makeName("description")
    };
  }

  // Create the node that will be used and set the routeParams.
  var node, $routeParams;
  beforeEach(function() {
    node = makeNode();
    $routeParams = {
      system_id: node.system_id
    };
  });

  // Makes the NodeDetailsController
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

    // Set the authenticated user, and by default make them superuser.
    UsersManager._authUser = {
      is_superuser: true
    };

    // Create the controller.
    var controller = $controller("NodeDetailsController", {
      $scope: $scope,
      $rootScope: $rootScope,
      $routeParams: $routeParams,
      $location: $location,
      MachinesManager: MachinesManager,
      DevicesManager: DevicesManager,
      ControllersManager: ControllersManager,
      ZonesManager: ZonesManager,
      GeneralManager: GeneralManager,
      UsersManager: UsersManager,
      TagsManager: TagsManager,
      DomainsManager: DomainsManager,
      ManagerHelperService: ManagerHelperService,
      ServicesManager: ServicesManager,
      ErrorService: ErrorService,
      ScriptsManager: ScriptsManager,
      ResourcePoolsManager: ResourcePoolsManager
    });

    // Since the osSelection directive is not used in this test the
    // osSelection item on the model needs to have $reset function added
    // because it will be called throughout many of the tests.
    $scope.osSelection.$reset = jasmine.createSpy("$reset");

    return controller;
  }

  // Make the controller and resolve the setActiveItem call.
  function makeControllerResolveSetActiveItem() {
    var setActiveDefer = $q.defer();
    spyOn(MachinesManager, "setActiveItem").and.returnValue(
      setActiveDefer.promise
    );
    var defer = $q.defer();
    var controller = makeController(defer);

    defer.resolve();
    $rootScope.$digest();
    setActiveDefer.resolve(node);
    $rootScope.$digest();

    return controller;
  }

  it("sets title to loading", function() {
    makeController();
    expect($rootScope.title).toBe("Loading...");
  });

  it("sets the initial $scope values", function() {
    makeController();
    expect($scope.loaded).toBe(false);
    expect($scope.node).toBeNull();
    expect($scope.action.option).toBeNull();
    expect($scope.action.allOptions).toBeNull();
    expect($scope.action.availableOptions).toEqual([]);
    expect($scope.action.error).toBeNull();
    expect($scope.action.showing_confirmation).toBe(false);
    expect($scope.action.confirmation_message).toEqual("");
    expect($scope.action.confirmation_details).toEqual([]);
    expect($scope.osinfo).toBe(GeneralManager.getData("osinfo"));
    expect($scope.power_types).toBe(GeneralManager.getData("power_types"));
    expect($scope.osSelection.osystem).toBeNull();
    expect($scope.osSelection.release).toBeNull();
    expect($scope.commissionOptions).toEqual({
      enableSSH: false,
      skipBMCConfig: false,
      skipNetworking: false,
      skipStorage: false,
      updateFirmware: false,
      configureHBA: false
    });
    expect($scope.releaseOptions).toEqual({});
    expect($scope.checkingPower).toBe(false);
    expect($scope.devices).toEqual([]);
    expect($scope.services).toEqual({});
    expect($scope.numaDetails).toEqual([]);
    expect($scope.expandedNumas).toEqual([]);
  });

  it("sets initial values for summary section", function() {
    makeController();
    expect($scope.summary).toEqual({
      editing: false,
      architecture: {
        selected: null,
        options: GeneralManager.getData("architectures")
      },
      min_hwe_kernel: {
        selected: null,
        options: GeneralManager.getData("min_hwe_kernels")
      },
      pool: {
        selected: null,
        options: ResourcePoolsManager.getItems()
      },
      zone: {
        selected: null,
        options: ZonesManager.getItems()
      },
      tags: []
    });
    expect($scope.summary.architecture.options).toBe(
      GeneralManager.getData("architectures")
    );
    expect($scope.summary.min_hwe_kernel.options).toBe(
      GeneralManager.getData("min_hwe_kernels")
    );
    expect($scope.summary.zone.options).toBe(ZonesManager.getItems());
    expect($scope.summary.pool.options).toBe(ResourcePoolsManager.getItems());
  });

  it("sets initial values for power section", function() {
    makeController();
    expect($scope.power).toEqual({
      editing: false,
      type: null,
      bmc_node_count: 0,
      parameters: {},
      in_pod: false
    });
  });

  it("sets initial values for events section", function() {
    makeController();
    expect($scope.events).toEqual({
      limit: 10
    });
  });

  it("sets initial area to routeParams value", function() {
    $routeParams.area = makeName("area");
    makeController();
    expect($scope.section.area).toEqual($routeParams.area);
  });

  it("calls loadManagers for machine", function() {
    $location.path("/machine");
    makeController();
    expect(ManagerHelperService.loadManagers).toHaveBeenCalledWith($scope, [
      ZonesManager,
      GeneralManager,
      UsersManager,
      TagsManager,
      DomainsManager,
      ServicesManager,
      ResourcePoolsManager,
      FabricsManager,
      VLANsManager,
      MachinesManager,
      ScriptsManager
    ]);
  });

  it("calls loadManagers for device", function() {
    $location.path("/device");
    makeController();
    expect(ManagerHelperService.loadManagers).toHaveBeenCalledWith($scope, [
      ZonesManager,
      GeneralManager,
      UsersManager,
      TagsManager,
      DomainsManager,
      ServicesManager,
      ResourcePoolsManager,
      FabricsManager,
      VLANsManager,
      DevicesManager
    ]);
  });

  it("calls loadManagers for controller", function() {
    $location.path("/controller");
    makeController();
    expect(ManagerHelperService.loadManagers).toHaveBeenCalledWith($scope, [
      ZonesManager,
      GeneralManager,
      UsersManager,
      TagsManager,
      DomainsManager,
      ServicesManager,
      ResourcePoolsManager,
      FabricsManager,
      VLANsManager,
      ControllersManager,
      ScriptsManager,
      VLANsManager
    ]);
  });

  it("doesnt call setActiveItem if node is loaded", function() {
    spyOn(MachinesManager, "setActiveItem").and.returnValue($q.defer().promise);
    var defer = $q.defer();
    makeController(defer);
    MachinesManager._activeItem = node;

    defer.resolve();
    $rootScope.$digest();

    expect($scope.node).toBe(node);
    expect($scope.loaded).toBe(true);
    expect(MachinesManager.setActiveItem).not.toHaveBeenCalled();
  });

  it("calls setActiveItem if node is not active", function() {
    spyOn(MachinesManager, "setActiveItem").and.returnValue($q.defer().promise);
    var defer = $q.defer();
    makeController(defer);

    defer.resolve();
    $rootScope.$digest();

    expect(MachinesManager.setActiveItem).toHaveBeenCalledWith(node.system_id);
  });

  it("sets node and loaded once setActiveItem resolves", function() {
    makeControllerResolveSetActiveItem();
    expect($scope.node).toBe(node);
    expect($scope.loaded).toBe(true);
  });

  it("sets machine values on load", function() {
    spyOn(MachinesManager, "setActiveItem").and.returnValue($q.defer().promise);
    var defer = $q.defer();
    makeController(defer);

    defer.resolve();
    $rootScope.$digest();

    expect($scope.nodesManager).toBe(MachinesManager);
    expect($scope.isController).toBe(false);
    expect($scope.type_name).toBe("machine");
    expect($scope.type_name_title).toBe("Machine");
  });

  it("sets controller values on load", function() {
    $location.path("/controller");
    spyOn(MachinesManager, "setActiveItem").and.returnValue($q.defer().promise);
    spyOn(ControllersManager, "setActiveItem").and.returnValue(
      $q.defer().promise
    );
    var defer = $q.defer();
    makeController(defer);

    defer.resolve();
    $rootScope.$digest();

    expect($scope.nodesManager).toBe(ControllersManager);
    expect($scope.isController).toBe(true);
    expect($scope.type_name).toBe("controller");
    expect($scope.type_name_title).toBe("Controller");
  });

  it("updateServices sets $scope.services when node is loaded", function() {
    spyOn(ControllersManager, "getServices").and.returnValue([
      { status: "running", name: "rackd" }
    ]);
    spyOn(ControllersManager, "setActiveItem").and.returnValue(
      $q.defer().promise
    );

    var defer = $q.defer();
    $location.path("/controller");
    makeController(defer);
    ControllersManager._activeItem = node;

    defer.resolve();
    $rootScope.$digest();

    expect($scope.node).toBe(node);
    expect($scope.loaded).toBe(true);

    expect(ControllersManager.getServices).toHaveBeenCalledWith(node);
    expect($scope.services).not.toBeNull();
    expect(Object.keys($scope.services).length).toBe(1);
    expect($scope.services.rackd.status).toBe("running");
  });

  it("loads node actions", function() {
    spyOn(ControllersManager, "setActiveItem").and.returnValue(
      $q.defer().promise
    );
    var called = false;
    spyOn(GeneralManager, "isDataLoaded").and.callFake(function() {
      var tmp = called;
      called = true;
      return tmp;
    });
    var loadManagersDefer = $q.defer();
    var loadItemsDefer = $q.defer();
    $location.path("/controller");
    makeController(loadManagersDefer, loadItemsDefer);
    var myNode = angular.copy(node);
    // Make node a rack controller.
    myNode.node_type = 2;
    ControllersManager._activeItem = myNode;
    loadManagersDefer.resolve();
    loadItemsDefer.resolve();
    $rootScope.$digest();
    expect(GeneralManager.isDataLoaded.calls.count()).toBe(2);
    expect(GeneralManager.isDataLoaded).toHaveBeenCalledWith(
      "rack_controller_actions"
    );
    expect(GeneralManager.loadItems).toHaveBeenCalledWith([
      "rack_controller_actions"
    ]);
  });

  it("title is updated once setActiveItem resolves", function() {
    makeControllerResolveSetActiveItem();
    expect($rootScope.title).toBe(node.fqdn);
  });

  it("summary section placed in edit mode if architecture blank", function() {
    node.architecture = "";
    node.permissions = ["edit"];
    GeneralManager._data.power_types.data = [{}];
    GeneralManager._data.architectures.data = ["amd64/generic"];

    makeControllerResolveSetActiveItem();
    expect($scope.summary.editing).toBe(true);
  });

  it(`summary section not placed in edit mode
      if no usable architectures`, function() {
    node.architecture = "";
    GeneralManager._data.power_types.data = [{}];

    makeControllerResolveSetActiveItem();
    expect($scope.summary.editing).toBe(false);
  });

  it(`summary section not placed in edit mode
      if architecture present`, function() {
    GeneralManager._data.architectures.data = [node.architecture];

    makeControllerResolveSetActiveItem();
    expect($scope.summary.editing).toBe(false);
  });

  it("summary section is updated once setActiveItem resolves", function() {
    makeControllerResolveSetActiveItem();
    expect($scope.summary.zone.selected).toBe(
      ZonesManager.getItemFromList(node.zone.id)
    );
    expect($scope.summary.architecture.selected).toBe(node.architecture);
    expect($scope.summary.tags).toEqual(node.tags);
  });

  it("power section no edit if power_type blank for controller", function() {
    GeneralManager._data.power_types.data = [{}];
    node.node_type = 4;
    makeControllerResolveSetActiveItem();
    expect($scope.power.editing).toBe(false);
  });

  it("power section edit mode if power_type blank for a machine", function() {
    GeneralManager._data.power_types.data = [{}];
    node.permissions = ["edit"];
    makeControllerResolveSetActiveItem();
    expect($scope.power.editing).toBe(true);
  });

  it("power section not placed in edit mode if no power_types", function() {
    makeControllerResolveSetActiveItem();
    expect($scope.power.editing).toBe(false);
  });

  it("power section not placed in edit mode if power_type", function() {
    node.power_type = makeName("power");
    GeneralManager._data.power_types.data = [{}];

    makeControllerResolveSetActiveItem();
    expect($scope.power.editing).toBe(false);
  });

  it("starts watching once setActiveItem resolves", function() {
    var setActiveDefer = $q.defer();
    spyOn(MachinesManager, "setActiveItem").and.returnValue(
      setActiveDefer.promise
    );
    var defer = $q.defer();
    makeController(defer);

    spyOn($scope, "$watch");
    spyOn($scope, "$watchCollection");

    defer.resolve();
    $rootScope.$digest();
    setActiveDefer.resolve(node);
    $rootScope.$digest();

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

    expect(watches).toEqual([
      "node.fqdn",
      "node.devices",
      "node.actions",
      "node.architecture",
      "node.min_hwe_kernel",
      "node.zone.id",
      "node.pool.id",
      "node.power_type",
      "node.power_parameters",
      "node.service_ids"
    ]);
    expect(watchCollections).toEqual([
      $scope.summary.architecture.options,
      $scope.summary.min_hwe_kernel.options,
      $scope.summary.zone.options,
      $scope.summary.pool.options,
      "power_types"
    ]);
  });

  it("updates $scope.devices", function() {
    var setActiveDefer = $q.defer();
    spyOn(MachinesManager, "setActiveItem").and.returnValue(
      setActiveDefer.promise
    );
    var defer = $q.defer();
    makeController(defer);

    node.devices = [
      {
        fqdn: "device1.maas",
        interfaces: []
      },
      {
        fqdn: "device2.maas",
        interfaces: [
          {
            mac_address: "00:11:22:33:44:55",
            links: []
          }
        ]
      },
      {
        fqdn: "device3.maas",
        interfaces: [
          {
            mac_address: "00:11:22:33:44:66",
            links: []
          },
          {
            mac_address: "00:11:22:33:44:77",
            links: [
              {
                ip_address: "192.168.122.1"
              },
              {
                ip_address: "192.168.122.2"
              },
              {
                ip_address: "192.168.122.3"
              }
            ]
          }
        ]
      }
    ];

    defer.resolve();
    $rootScope.$digest();
    setActiveDefer.resolve(node);
    $rootScope.$digest();

    expect($scope.devices).toEqual([
      {
        name: "device1.maas"
      },
      {
        name: "device2.maas",
        mac_address: "00:11:22:33:44:55"
      },
      {
        name: "device3.maas",
        mac_address: "00:11:22:33:44:66"
      },
      {
        name: "",
        mac_address: "00:11:22:33:44:77",
        ip_address: "192.168.122.1"
      },
      {
        name: "",
        mac_address: "",
        ip_address: "192.168.122.2"
      },
      {
        name: "",
        mac_address: "",
        ip_address: "192.168.122.3"
      }
    ]);
  });

  it("reloads osinfo on route update", function() {
    makeController();
    $scope.$emit("$routeUpdate");
    expect(GeneralManager.loadItems).toHaveBeenCalled();
  });

  it("updates $scope.actions", function() {
    var setActiveDefer = $q.defer();
    spyOn(MachinesManager, "setActiveItem").and.returnValue(
      setActiveDefer.promise
    );
    var loadManagersDefer = $q.defer();
    var loadItemsDefer = $q.defer();
    makeController(loadManagersDefer, loadItemsDefer);
    node.node_type = 0;
    node.actions = ["test", "release", "delete"];
    var all_actions = [
      { name: "deploy" },
      { name: "commission" },
      { name: "test" },
      { name: "release" },
      { name: "delete" }
    ];
    loadManagersDefer.resolve();
    $rootScope.$digest();
    setActiveDefer.resolve(node);
    $rootScope.$digest();
    // loadItems normally sets loaded to true and sets data to the items
    // retrieved from the region. The spy prevents that from happening
    // which is needed for GeneralManager.isLoaded to work.
    GeneralManager._data.machine_actions.loaded = true;
    GeneralManager._data.machine_actions.data = all_actions;
    loadItemsDefer.resolve(all_actions);
    $rootScope.$digest();
    expect($scope.action.allOptions).toEqual(all_actions);
    expect($scope.action.availableOptions).toEqual([
      { name: "test" },
      { name: "release" },
      { name: "delete" }
    ]);
  });

  describe("tagsAutocomplete", function() {
    it("calls TagsManager.autocomplete with query", function() {
      makeController();
      spyOn(TagsManager, "autocomplete");
      var query = makeName("query");
      $scope.tagsAutocomplete(query);
      expect(TagsManager.autocomplete).toHaveBeenCalledWith(query);
    });
  });

  describe("isSuperUser", function() {
    it("returns false if no authUser", function() {
      makeController();
      UsersManager._authUser = null;
      expect($scope.isSuperUser()).toBe(false);
    });

    it("returns false if authUser.is_superuser is false", function() {
      makeController();
      UsersManager._authUser.is_superuser = false;
      expect($scope.isSuperUser()).toBe(false);
    });

    it("returns true if authUser.is_superuser is true", function() {
      makeController();
      UsersManager._authUser.is_superuser = true;
      expect($scope.isSuperUser()).toBe(true);
    });
  });

  describe("getPowerStateClass", function() {
    it("returns blank if no node", function() {
      makeController();
      expect($scope.getPowerStateClass()).toBe("");
    });

    it("returns check if checkingPower is true", function() {
      makeController();
      $scope.node = node;
      $scope.checkingPower = true;
      expect($scope.getPowerStateClass()).toBe("checking");
    });

    it("returns power_state from node ", function() {
      makeController();
      var state = makeName("state");
      $scope.node = node;
      node.power_state = state;
      expect($scope.getPowerStateClass()).toBe(state);
    });
  });

  describe("getPowerStateText", function() {
    it("returns blank if no node", function() {
      makeController();
      expect($scope.getPowerStateText()).toBe("");
    });

    it("returns 'Checking' if checkingPower is true", function() {
      makeController();
      $scope.node = node;
      $scope.checkingPower = true;
      node.power_state = "unknown";
      expect($scope.getPowerStateText()).toBe("Checking power");
    });

    it("returns blank if power_state is unknown", function() {
      makeController();
      $scope.node = node;
      node.power_state = "unknown";
      expect($scope.getPowerStateText()).toBe("");
    });

    it("returns power_state prefixed with Power ", function() {
      makeController();
      var state = makeName("state");
      $scope.node = node;
      node.power_state = state;
      expect($scope.getPowerStateText()).toBe("Power " + state);
    });
  });

  describe("canCheckPowerState", function() {
    it("returns false if no node", function() {
      makeController();
      expect($scope.canCheckPowerState()).toBe(false);
    });

    it("returns false if power_state is unknown", function() {
      makeController();
      $scope.node = node;
      node.power_state = "unknown";
      expect($scope.canCheckPowerState()).toBe(false);
    });

    it("returns false if checkingPower is true", function() {
      makeController();
      $scope.node = node;
      $scope.checkingPower = true;
      expect($scope.canCheckPowerState()).toBe(false);
    });

    it(`returns true if not checkingPower and
        power_state not unknown`, function() {
      makeController();
      $scope.node = node;
      expect($scope.canCheckPowerState()).toBe(true);
    });
  });

  describe("checkPowerState", function() {
    it("sets checkingPower to true", function() {
      makeController();
      spyOn(MachinesManager, "checkPowerState").and.returnValue(
        $q.defer().promise
      );
      $scope.checkPowerState();
      expect($scope.checkingPower).toBe(true);
    });

    it("sets checkingPower to false once checkPowerState resolves", function() {
      makeController();
      var defer = $q.defer();
      spyOn(MachinesManager, "checkPowerState").and.returnValue(defer.promise);
      $scope.checkPowerState();
      defer.resolve();
      $rootScope.$digest();
      expect($scope.checkingPower).toBe(false);
    });
  });

  describe("isUbuntuOS", function() {
    it("returns true when ubuntu", function() {
      makeController();
      $scope.node = node;
      node.osystem = "ubuntu";
      node.distro_series = makeName("distro_series");
      expect($scope.isUbuntuOS()).toBe(true);
    });

    it("returns false when otheros", function() {
      makeController();
      $scope.node = node;
      node.osystem = makeName("osystem");
      node.distro_series = makeName("distro_series");
      expect($scope.isUbuntuOS()).toBe(false);
    });
  });

  describe("isUbuntuCoreOS", function() {
    it("returns true when ubuntu-core", function() {
      makeController();
      $scope.node = node;
      node.osystem = "ubuntu-core";
      node.distro_series = makeName("distro_series");
      expect($scope.isUbuntuCoreOS()).toBe(true);
    });

    it("returns false when otheros", function() {
      makeController();
      $scope.node = node;
      node.osystem = makeName("osystem");
      node.distro_series = makeName("distro_series");
      expect($scope.isUbuntuCoreOS()).toBe(false);
    });
  });

  describe("isCentOS", function() {
    it("returns true when CentOS", function() {
      makeController();
      $scope.node = node;
      node.osystem = "centos";
      node.distro_series = makeName("distro_series");
      expect($scope.isCentOS()).toBe(true);
    });

    it("returns true when RHEL", function() {
      makeController();
      $scope.node = node;
      node.osystem = "rhel";
      node.distro_series = makeName("distro_series");
      expect($scope.isCentOS()).toBe(true);
    });

    it("returns false when otheros", function() {
      makeController();
      $scope.node = node;
      node.osystem = makeName("osystem");
      node.distro_series = makeName("distro_series");
      expect($scope.isCentOS()).toBe(false);
    });
  });

  describe("isCustomOS", function() {
    it("returns true when custom OS", function() {
      makeController();
      $scope.node = node;
      node.osystem = "custom";
      node.distro_series = makeName("distro_series");
      expect($scope.isCustomOS()).toBe(true);
    });

    it("returns false when otheros", function() {
      makeController();
      $scope.node = node;
      node.osystem = makeName("osystem");
      node.distro_series = makeName("distro_series");
      expect($scope.isCustomOS()).toBe(false);
    });
  });

  describe("isActionError", function() {
    it("returns true if actionError", function() {
      makeController();
      $scope.action.error = makeName("error");
      expect($scope.isActionError()).toBe(true);
    });

    it("returns false if not actionError", function() {
      makeController();
      $scope.action.error = null;
      expect($scope.isActionError()).toBe(false);
    });
  });

  describe("isDeployError", function() {
    it("returns false if already actionError", function() {
      makeController();
      $scope.action.error = makeName("error");
      expect($scope.isDeployError()).toBe(false);
    });

    it("returns true if deploy action and missing osinfo", function() {
      makeController();
      $scope.action.option = {
        name: "deploy"
      };
      expect($scope.isDeployError()).toBe(true);
    });

    it("returns true if deploy action and no osystems", function() {
      makeController();
      $scope.action.option = {
        name: "deploy"
      };
      $scope.osinfo = {
        osystems: []
      };
      expect($scope.isDeployError()).toBe(true);
    });

    it("returns false if actionOption null", function() {
      makeController();
      expect($scope.isDeployError()).toBe(false);
    });

    it("returns false if not deploy action", function() {
      makeController();
      $scope.action.option = {
        name: "release"
      };
      expect($scope.isDeployError()).toBe(false);
    });

    it("returns false if osystems present", function() {
      makeController();
      $scope.action.option = {
        name: "deploy"
      };
      $scope.osinfo = {
        osystems: [makeName("os")]
      };
      expect($scope.isDeployError()).toBe(false);
    });
  });

  describe("isSSHKeyWarning", function() {
    it("returns true if deploy action and missing ssh keys", function() {
      makeController();
      $scope.action.option = {
        name: "deploy"
      };
      var firstUser = makeUser();
      firstUser.sshkeys_count = 0;
      UsersManager._authUser = firstUser;
      expect($scope.isSSHKeyWarning()).toBe(true);
    });

    it("returns false if actionOption null", function() {
      makeController();
      var firstUser = makeUser();
      firstUser.sshkeys_count = 1;
      UsersManager._authUser = firstUser;
      expect($scope.isSSHKeyWarning()).toBe(false);
    });

    it("returns false if not deploy action", function() {
      makeController();
      $scope.action.option = {
        name: "release"
      };
      var firstUser = makeUser();
      firstUser.sshkeys_count = 1;
      UsersManager._authUser = firstUser;
      expect($scope.isSSHKeyWarning()).toBe(false);
    });

    it("returns false if ssh keys present", function() {
      makeController();
      $scope.action.option = {
        name: "deploy"
      };
      var firstUser = makeUser();
      firstUser.sshkeys_count = 1;
      UsersManager._authUser = firstUser;
      expect($scope.isSSHKeyWarning()).toBe(false);
    });
  });

  describe("actionOptionChanged", function() {
    it("clears actionError", function() {
      makeController();
      $scope.action.error = makeName("error");
      $scope.action.optionChanged();
      expect($scope.action.error).toBeNull();
    });
  });

  describe("actionCancel", function() {
    it("sets actionOption to null", function() {
      makeController();
      $scope.action.option = {};
      $scope.actionCancel();
      expect($scope.action.option).toBeNull();
    });

    it("clears actionError", function() {
      makeController();
      $scope.action.error = makeName("error");
      $scope.actionCancel();
      expect($scope.action.error).toBeNull();
    });

    it("resets showing_confirmation", function() {
      makeController();
      $scope.action.showing_confirmation = true;
      $scope.action.confirmation_message = makeName("message");
      $scope.action.confirmation_details = [
        makeName("detail"),
        makeName("detail"),
        makeName("detail")
      ];
      $scope.actionCancel();
      expect($scope.action.showing_confirmation).toBe(false);
      expect($scope.action.confirmation_message).toEqual("");
      expect($scope.action.confirmation_details).toEqual([]);
    });
  });

  describe("actionGo", function() {
    it("calls performAction with node and actionOption name", function() {
      makeController();
      spyOn(MachinesManager, "performAction").and.returnValue(
        $q.defer().promise
      );
      $scope.node = node;
      $scope.action.option = {
        name: "power_off"
      };
      $scope.actionGo();
      expect(MachinesManager.performAction).toHaveBeenCalledWith(
        node,
        "power_off",
        {}
      );
    });

    it("calls performAction with osystem and distro_series", function() {
      makeController();
      spyOn(MachinesManager, "performAction").and.returnValue(
        $q.defer().promise
      );
      $scope.node = node;
      $scope.action.option = {
        name: "deploy"
      };
      $scope.osSelection.osystem = "ubuntu";
      $scope.osSelection.release = "ubuntu/trusty";
      $scope.actionGo();
      expect(MachinesManager.performAction).toHaveBeenCalledWith(
        node,
        "deploy",
        {
          osystem: "ubuntu",
          distro_series: "trusty",
          install_kvm: false
        }
      );
    });

    it("calls performAction with install_kvm", function() {
      makeController();
      spyOn(MachinesManager, "performAction").and.returnValue(
        $q.defer().promise
      );
      $scope.node = node;
      $scope.action.option = {
        name: "deploy"
      };
      $scope.osSelection.osystem = "debian";
      $scope.osSelection.release = "etch";
      $scope.deployOptions.installKVM = true;
      $scope.actionGo();
      // When deploying KVM, coerce the distro to ubuntu/bionic.
      expect(MachinesManager.performAction).toHaveBeenCalledWith(
        node,
        "deploy",
        {
          osystem: "ubuntu",
          distro_series: "bionic",
          install_kvm: true
        }
      );
    });

    it("calls performAction with hwe kernel", function() {
      makeController();
      spyOn(MachinesManager, "performAction").and.returnValue(
        $q.defer().promise
      );
      $scope.node = node;
      $scope.action.option = {
        name: "deploy"
      };
      $scope.osSelection.osystem = "ubuntu";
      $scope.osSelection.release = "ubuntu/xenial";
      $scope.osSelection.hwe_kernel = "hwe-16.04-edge";
      $scope.actionGo();
      expect(MachinesManager.performAction).toHaveBeenCalledWith(
        node,
        "deploy",
        {
          osystem: "ubuntu",
          distro_series: "xenial",
          hwe_kernel: "hwe-16.04-edge",
          install_kvm: false
        }
      );
    });

    it("calls performAction with ga kernel", function() {
      makeController();
      spyOn(MachinesManager, "performAction").and.returnValue(
        $q.defer().promise
      );
      $scope.node = node;
      $scope.action.option = {
        name: "deploy"
      };
      $scope.osSelection.osystem = "ubuntu";
      $scope.osSelection.release = "ubuntu/xenial";
      $scope.osSelection.hwe_kernel = "ga-16.04";
      $scope.actionGo();
      expect(MachinesManager.performAction).toHaveBeenCalledWith(
        node,
        "deploy",
        {
          osystem: "ubuntu",
          distro_series: "xenial",
          hwe_kernel: "ga-16.04",
          install_kvm: false
        }
      );
    });

    it("calls performAction with commissionOptions", function() {
      makeController();
      spyOn(MachinesManager, "performAction").and.returnValue(
        $q.defer().promise
      );
      $scope.node = node;
      $scope.action.option = {
        name: "commission"
      };
      var commissioning_script_ids = [makeInteger(0, 100), makeInteger(0, 100)];
      var testing_script_ids = [makeInteger(0, 100), makeInteger(0, 100)];
      $scope.commissionOptions.enableSSH = true;
      $scope.commissionOptions.skipBMCConfig = false;
      $scope.commissionOptions.skipNetworking = false;
      $scope.commissionOptions.skipStorage = false;
      $scope.commissionOptions.updateFirmware = true;
      $scope.commissionOptions.configureHBA = true;
      $scope.commissioningSelection = [];
      angular.forEach(commissioning_script_ids, function(script_id) {
        $scope.commissioningSelection.push({
          id: script_id,
          name: makeName("script_name")
        });
      });
      $scope.testSelection = [];
      angular.forEach(testing_script_ids, function(script_id) {
        $scope.testSelection.push({
          id: script_id,
          name: makeName("script_name")
        });
      });
      $scope.actionGo();
      expect(MachinesManager.performAction).toHaveBeenCalledWith(
        node,
        "commission",
        {
          enable_ssh: true,
          skip_bmc_config: false,
          skip_networking: false,
          skip_storage: false,
          commissioning_scripts: commissioning_script_ids.concat([
            "update_firmware",
            "configure_hba"
          ]),
          testing_scripts: testing_script_ids
        }
      );
    });

    it("calls performAction with testOptions", function() {
      makeController();
      spyOn(MachinesManager, "performAction").and.returnValue(
        $q.defer().promise
      );
      $scope.node = node;
      $scope.action.option = {
        name: "test"
      };
      var testing_script_ids = [makeInteger(0, 100), makeInteger(0, 100)];
      $scope.commissionOptions.enableSSH = true;
      $scope.testSelection = [];
      angular.forEach(testing_script_ids, function(script_id) {
        $scope.testSelection.push({
          id: script_id,
          name: makeName("script_name")
        });
      });
      $scope.actionGo();
      expect(MachinesManager.performAction).toHaveBeenCalledWith(node, "test", {
        enable_ssh: true,
        script_input: {},
        testing_scripts: testing_script_ids
      });
    });

    it("sets showing_confirmation with testOptions", function() {
      makeController();
      spyOn(MachinesManager, "performAction").and.returnValue(
        $q.defer().promise
      );
      node.status_code = 6;
      $scope.node = node;
      $scope.action.option = {
        name: "test"
      };
      $scope.actionGo();
      expect($scope.action.showing_confirmation).toBe(true);
      expect(MachinesManager.performAction).not.toHaveBeenCalled();
    });

    it("calls performAction with releaseOptions", function() {
      makeController();
      spyOn(MachinesManager, "performAction").and.returnValue(
        $q.defer().promise
      );
      $scope.node = node;
      $scope.action.option = {
        name: "release"
      };
      var secureErase = makeName("secureErase");
      var quickErase = makeName("quickErase");
      $scope.releaseOptions.erase = true;
      $scope.releaseOptions.secureErase = secureErase;
      $scope.releaseOptions.quickErase = quickErase;
      $scope.actionGo();
      expect(MachinesManager.performAction).toHaveBeenCalledWith(
        node,
        "release",
        {
          erase: true,
          secure_erase: secureErase,
          quick_erase: quickErase
        }
      );
    });

    it("sets showing_confirmation with deleteOptions", function() {
      // Regression test for LP:1793478
      makeController();
      spyOn(ControllersManager, "performAction").and.returnValue(
        $q.defer().promise
      );
      $scope.node = node;
      $scope.type_name = "controller";
      $scope.vlans = [
        {
          id: 0,
          primary_rack: node.system_id,
          name: "Default VLAN"
        }
      ];
      $scope.action.option = {
        name: "delete"
      };
      $scope.actionGo();
      expect($scope.action.showing_confirmation).toBe(true);
      expect($scope.action.confirmation_message).not.toEqual("");
      expect($scope.action.confirmation_details).not.toEqual([]);
      expect(ControllersManager.performAction).not.toHaveBeenCalled();
    });

    it("clears actionOption on resolve", function() {
      makeController();
      var defer = $q.defer();
      spyOn(MachinesManager, "performAction").and.returnValue(defer.promise);
      $scope.node = node;
      $scope.action.option = {
        name: "deploy"
      };
      $scope.actionGo();
      defer.resolve();
      $rootScope.$digest();
      expect($scope.action.option).toBeNull();
    });

    it("clears osSelection on resolve", function() {
      makeController();
      var defer = $q.defer();
      spyOn(MachinesManager, "performAction").and.returnValue(defer.promise);
      $scope.node = node;
      $scope.action.option = {
        name: "deploy"
      };
      $scope.osSelection.osystem = "ubuntu";
      $scope.osSelection.release = "ubuntu/trusty";
      $scope.actionGo();
      defer.resolve();
      $rootScope.$digest();
      expect($scope.osSelection.$reset).toHaveBeenCalled();
    });

    it("clears commissionOptions on resolve", function() {
      makeController();
      var defer = $q.defer();
      spyOn(MachinesManager, "performAction").and.returnValue(defer.promise);
      $scope.node = node;
      $scope.action.option = {
        name: "commission"
      };
      $scope.commissionOptions.enableSSH = true;
      $scope.commissionOptions.skipBMCConfig = true;
      $scope.commissionOptions.skipNetworking = true;
      $scope.commissionOptions.skipStorage = true;
      $scope.commissionOptions.updateFirmware = true;
      $scope.commissionOptions.configureHBA = true;
      $scope.commissioningSelection = [
        {
          id: makeInteger(0, 100),
          name: makeName("script_name")
        }
      ];
      $scope.testSelection = [
        {
          id: makeInteger(0, 100),
          name: makeName("script_name")
        }
      ];
      $scope.actionGo();
      defer.resolve();
      $rootScope.$digest();
      expect($scope.commissionOptions).toEqual({
        enableSSH: false,
        skipBMCConfig: false,
        skipNetworking: false,
        skipStorage: false,
        updateFirmware: false,
        configureHBA: false
      });
      expect($scope.commissioningSelection).toEqual([]);
      expect($scope.testSelection).toEqual([]);
    });

    it("clears actionError on resolve", function() {
      makeController();
      var defer = $q.defer();
      spyOn(MachinesManager, "performAction").and.returnValue(defer.promise);
      $scope.node = node;
      $scope.action.option = {
        name: "deploy"
      };
      $scope.action.error = makeName("error");
      $scope.actionGo();
      defer.resolve();
      $rootScope.$digest();
      expect($scope.action.error).toBeNull();
    });

    it("changes path to node listing on delete", function() {
      makeController();
      var defer = $q.defer();
      spyOn(MachinesManager, "performAction").and.returnValue(defer.promise);
      spyOn($location, "path");
      $scope.node = node;
      $scope.action.option = {
        name: "delete"
      };
      $scope.actionGo();
      defer.resolve();
      $rootScope.$digest();
      expect($location.path).toHaveBeenCalledWith("/machines");
    });

    it("sets actionError when rejected", function() {
      makeController();
      var defer = $q.defer();
      spyOn(MachinesManager, "performAction").and.returnValue(defer.promise);
      $scope.node = node;
      $scope.action.option = {
        name: "deploy"
      };
      var error = makeName("error");
      $scope.actionGo();
      defer.reject(error);
      $rootScope.$digest();
      expect($scope.action.error).toBe(error);
    });
  });

  describe("hasUsableArchitectures", function() {
    it("returns true if architecture available", function() {
      makeController();
      $scope.summary.architecture.options = ["amd64/generic"];
      expect($scope.hasUsableArchitectures()).toBe(true);
    });

    it("returns false if no architecture available", function() {
      makeController();
      $scope.summary.architecture.options = [];
      expect($scope.hasUsableArchitectures()).toBe(false);
    });
  });

  describe("getArchitecturePlaceholder", function() {
    it("returns choose if architecture available", function() {
      makeController();
      $scope.summary.architecture.options = ["amd64/generic"];
      expect($scope.getArchitecturePlaceholder()).toBe(
        "Choose an architecture"
      );
    });

    it("returns error if no architecture available", function() {
      makeController();
      $scope.summary.architecture.options = [];
      expect($scope.getArchitecturePlaceholder()).toBe(
        "-- No usable architectures --"
      );
    });
  });

  describe("hasInvalidArchitecture", function() {
    it("returns false if node is null", function() {
      makeController();
      $scope.node = null;
      $scope.summary.architecture.options = ["amd64/generic"];
      expect($scope.hasInvalidArchitecture()).toBe(false);
    });

    it("returns true if node.architecture is blank", function() {
      makeController();
      $scope.node = {
        architecture: ""
      };
      $scope.summary.architecture.options = ["amd64/generic"];
      expect($scope.hasInvalidArchitecture()).toBe(true);
    });

    it("returns true if node.architecture not in options", function() {
      makeController();
      $scope.node = {
        architecture: "i386/generic"
      };
      $scope.summary.architecture.options = ["amd64/generic"];
      expect($scope.hasInvalidArchitecture()).toBe(true);
    });

    it("returns false if node.architecture in options", function() {
      makeController();
      $scope.node = {
        architecture: "amd64/generic"
      };
      $scope.summary.architecture.options = ["amd64/generic"];
      expect($scope.hasInvalidArchitecture()).toBe(false);
    });
  });

  describe("invalidArchitecture", function() {
    it("returns true if selected architecture empty", function() {
      makeController();
      $scope.summary.architecture.selected = "";
      expect($scope.invalidArchitecture()).toBe(true);
    });

    it("returns true if selected architecture not in options", function() {
      makeController();
      $scope.summary.architecture.options = [makeName("arch")];
      $scope.summary.architecture.selected = makeName("arch");
      expect($scope.invalidArchitecture()).toBe(true);
    });

    it("returns false if selected architecture in options", function() {
      makeController();
      var arch = makeName("arch");
      $scope.summary.architecture.options = [arch];
      $scope.summary.architecture.selected = arch;
      expect($scope.invalidArchitecture()).toBe(false);
    });
  });

  describe("isRackControllerConnected", function() {
    it("returns false no power_types", function() {
      makeController();
      $scope.power_types = [];
      expect($scope.isRackControllerConnected()).toBe(false);
    });

    it("returns true if power_types", function() {
      makeController();
      $scope.power_types = [{}];
      expect($scope.isRackControllerConnected()).toBe(true);
    });
  });

  describe("hasPermission", function() {
    it("returns false no permissions field", function() {
      makeController();
      $scope.node = {};
      expect($scope.hasPermission("edit")).toBe(false);
    });

    it("returns false no permission in field", function() {
      makeController();
      $scope.node = {
        permissions: ["delete"]
      };
      expect($scope.hasPermission("edit")).toBe(false);
    });

    it("returns true permissions", function() {
      makeController();
      $scope.node = {
        permissions: ["edit"]
      };
      expect($scope.hasPermission("edit")).toBe(true);
    });
  });

  describe("canEdit", function() {
    it("returns false if no edit permission", function() {
      makeController();
      $scope.isDevice = false;
      spyOn($scope, "hasPermission").and.returnValue(false);
      spyOn($scope, "isRackControllerConnected").and.returnValue(true);
      expect($scope.canEdit()).toBe(false);
    });

    it("returns true if edit permission but device", function() {
      makeController();
      $scope.isDevice = true;
      spyOn($scope, "hasPermission").and.returnValue(true);
      spyOn($scope, "isRackControllerConnected").and.returnValue(false);
      expect($scope.canEdit()).toBe(true);
    });

    it("returns false if rack disconnected", function() {
      makeController();
      $scope.isDevice = false;
      spyOn($scope, "hasPermission").and.returnValue(true);
      spyOn($scope, "isRackControllerConnected").and.returnValue(false);
      expect($scope.canEdit()).toBe(false);
    });

    it("returns false if machine is locked", function() {
      makeController();
      $scope.isDevice = false;
      spyOn($scope, "hasPermission").and.returnValue(true);
      spyOn($scope, "isRackControllerConnected").and.returnValue(true);
      $scope.node = makeNode();
      $scope.node.locked = true;
      expect($scope.canEdit()).toBe(false);
    });
  });

  describe("editHeaderDomain", function() {
    it(`doesn't set editing false and
        editing_domain true if cannot edit`, function() {
      makeController();
      spyOn($scope, "canEdit").and.returnValue(true);
      $scope.header.editing = true;
      $scope.header.editing_domain = false;
      $scope.editHeaderDomain();
      expect($scope.header.editing).toBe(true);
      expect($scope.header.editing_domain).toBe(false);
    });

    it("sets editing to false and editing_domain to true if able", function() {
      makeController();
      $scope.node = node;
      spyOn($scope, "canEdit").and.returnValue(false);
      $scope.header.editing = true;
      $scope.header.editing_domain = false;
      $scope.editHeaderDomain();
      expect($scope.header.editing).toBe(false);
      expect($scope.header.editing_domain).toBe(true);
    });

    it("sets header.hostname.value to node hostname", function() {
      makeController();
      $scope.node = node;
      spyOn($scope, "canEdit").and.returnValue(false);
      $scope.editHeaderDomain();
      expect($scope.header.hostname.value).toBe(node.hostname);
    });

    it("doesnt reset header.hostname.value on multiple calls", function() {
      makeController();
      $scope.node = node;
      spyOn($scope, "canEdit").and.returnValue(false);
      $scope.editHeaderDomain();
      var updatedName = makeName("name");
      $scope.header.hostname.value = updatedName;
      $scope.editHeaderDomain();
      expect($scope.header.hostname.value).toBe(updatedName);
    });
  });

  describe("editHeader", function() {
    it(`doesn't set editing true and editing_domain
        false if cannot edit`, function() {
      makeController();
      spyOn($scope, "canEdit").and.returnValue(false);
      $scope.header.editing = false;
      $scope.header.editing_domain = true;
      $scope.editHeader();
      expect($scope.header.editing).toBe(false);
      expect($scope.header.editing_domain).toBe(true);
    });

    it("sets editing to true and editing_domain to false if able", function() {
      makeController();
      $scope.node = node;
      spyOn($scope, "canEdit").and.returnValue(true);
      $scope.header.editing = false;
      $scope.header.editing_domain = true;
      $scope.editHeader();
      expect($scope.header.editing).toBe(true);
      expect($scope.header.editing_domain).toBe(false);
    });

    it("sets header.hostname.value to node hostname", function() {
      makeController();
      $scope.node = node;
      spyOn($scope, "canEdit").and.returnValue(true);
      $scope.editHeader();
      expect($scope.header.hostname.value).toBe(node.hostname);
    });

    it("doesnt reset header.hostname.value on multiple calls", function() {
      makeController();
      $scope.node = node;
      spyOn($scope, "canEdit").and.returnValue(true);
      $scope.editHeader();
      var updatedName = makeName("name");
      $scope.header.hostname.value = updatedName;
      $scope.editHeader();
      expect($scope.header.hostname.value).toBe(updatedName);
    });
  });

  describe("editHeaderInvalid", function() {
    it("returns false if not editing and not editing_domain", function() {
      makeController();
      $scope.header.editing = false;
      $scope.header.editing_domain = false;
      $scope.header.hostname.value = "abc_invalid.local";
      expect($scope.editHeaderInvalid()).toBe(false);
    });

    it("returns true for bad values", function() {
      makeController();
      $scope.header.editing = true;
      $scope.header.editing_domain = false;
      var values = [
        {
          input: "aB0-z",
          output: false
        },
        {
          input: "abc_alpha",
          output: true
        },
        {
          input: "ab^&c",
          output: true
        },
        {
          input: "abc.local",
          output: true
        }
      ];
      angular.forEach(values, function(value) {
        $scope.header.hostname.value = value.input;
        expect($scope.editHeaderInvalid()).toBe(value.output);
      });
    });
  });

  describe("cancelEditHeader", function() {
    it(`sets editing and editing_domain to false
        for nameHeader section`, function() {
      makeController();
      $scope.node = node;
      $scope.header.editing = true;
      $scope.header.editing_domain = true;
      $scope.cancelEditHeader();
      expect($scope.header.editing).toBe(false);
      expect($scope.header.editing_domain).toBe(false);
    });

    it("sets header.hostname.value back to fqdn", function() {
      makeController();
      $scope.node = node;
      $scope.header.editing = true;
      $scope.header.hostname.value = makeName("name");
      $scope.cancelEditHeader();
      expect($scope.header.hostname.value).toBe(node.fqdn);
    });
  });

  describe("saveEditHeader", function() {
    it("does nothing if value is invalid", function() {
      makeController();
      $scope.node = node;
      spyOn($scope, "editHeaderInvalid").and.returnValue(true);
      var sentinel = {};
      $scope.header.editing = sentinel;
      $scope.header.editing_domain = sentinel;
      $scope.saveEditHeader();
      expect($scope.header.editing).toBe(sentinel);
      expect($scope.header.editing_domain).toBe(sentinel);
    });

    it("sets editing to false", function() {
      makeController();
      spyOn(MachinesManager, "updateItem").and.returnValue($q.defer().promise);
      spyOn($scope, "editHeaderInvalid").and.returnValue(false);

      $scope.node = node;
      $scope.header.editing = true;
      $scope.header.editing_domain = true;
      $scope.header.hostname.value = makeName("name");
      $scope.saveEditHeader();

      expect($scope.header.editing).toBe(false);
      expect($scope.header.editing_domain).toBe(false);
    });

    it("calls updateItem with copy of node", function() {
      makeController();
      spyOn(MachinesManager, "updateItem").and.returnValue($q.defer().promise);
      spyOn($scope, "editHeaderInvalid").and.returnValue(false);

      $scope.node = node;
      $scope.header.editing = true;
      $scope.header.hostname.value = makeName("name");
      $scope.saveEditHeader();

      var calledWithNode = MachinesManager.updateItem.calls.argsFor(0)[0];
      expect(calledWithNode).not.toBe(node);
    });

    it("calls updateItem with new hostname on node", function() {
      makeController();
      spyOn(MachinesManager, "updateItem").and.returnValue($q.defer().promise);
      spyOn($scope, "editHeaderInvalid").and.returnValue(false);

      var newName = makeName("name");
      $scope.node = node;
      $scope.header.editing = true;
      $scope.header.hostname.value = newName;
      $scope.saveEditHeader();

      var calledWithNode = MachinesManager.updateItem.calls.argsFor(0)[0];
      expect(calledWithNode.hostname).toBe(newName);
    });

    it("calls updateName once updateItem resolves", function() {
      makeController();
      var defer = $q.defer();
      spyOn(MachinesManager, "updateItem").and.returnValue(defer.promise);
      spyOn($scope, "editHeaderInvalid").and.returnValue(false);

      $scope.node = node;
      $scope.header.editing = true;
      $scope.header.hostname.value = makeName("name");
      $scope.saveEditHeader();

      defer.resolve(node);
      $rootScope.$digest();

      // Since updateName is private in the controller, check
      // that the header.hostname.value is set to the nodes fqdn.
      expect($scope.header.hostname.value).toBe(node.fqdn);
    });
  });

  describe("editSummary", function() {
    it("doesnt sets editing to true if cannot edit", function() {
      makeController();
      spyOn($scope, "canEdit").and.returnValue(false);
      $scope.summary.editing = false;
      $scope.editSummary();
      expect($scope.summary.editing).toBe(false);
    });

    it("sets editing to true for summary section", function() {
      makeController();
      spyOn($scope, "canEdit").and.returnValue(true);
      $scope.summary.editing = false;
      $scope.editSummary();
      expect($scope.summary.editing).toBe(true);
    });
  });

  describe("cancelEditSummary", function() {
    it("sets editing to false for summary section", function() {
      makeController();
      $scope.node = node;
      $scope.summary.architecture.options = [node.architecture];
      $scope.summary.editing = true;
      $scope.cancelEditSummary();
      expect($scope.summary.editing).toBe(false);
    });

    it("doesnt set editing to false if invalid architecture", function() {
      makeController();
      $scope.node = node;
      $scope.summary.editing = true;
      $scope.cancelEditSummary();
      expect($scope.summary.editing).toBe(true);
    });

    it("does set editing to true if device", function() {
      makeController();
      $scope.isDevice = true;
      $scope.node = node;
      $scope.summary.editing = true;
      $scope.cancelEditSummary();
      expect($scope.summary.editing).toBe(false);
    });

    it("does set editing to true if controller", function() {
      makeController();
      $scope.isController = true;
      $scope.node = node;
      $scope.summary.editing = true;
      $scope.cancelEditSummary();
      expect($scope.summary.editing).toBe(false);
    });

    it("calls updateSummary", function() {
      makeController();
      $scope.node = node;
      $scope.summary.architecture.options = [node.architecture];
      $scope.summary.editing = true;
      $scope.cancelEditSummary();
    });
  });

  describe("saveEditSummary", function() {
    // Configures the summary area in the scope to have a zone, and
    // architecture.
    function configureSummary() {
      $scope.summary.editing = true;
      $scope.summary.zone.selected = makeZone();
      $scope.summary.pool.selected = makeResourcePool();
      $scope.summary.description = "This is a description";
      $scope.summary.architecture.selected = makeName("architecture");
      $scope.summary.tags = [
        { text: makeName("tag") },
        { text: makeName("tag") }
      ];
    }

    it("does nothing if invalidArchitecture", function() {
      makeController();
      spyOn($scope, "invalidArchitecture").and.returnValue(true);
      $scope.node = node;
      var editing = {};
      $scope.summary.editing = editing;
      $scope.saveEditSummary();

      // Editing remains the same then the method exited early.
      expect($scope.summary.editing).toBe(editing);
    });

    it("sets editing to false", function() {
      makeController();
      spyOn($scope, "invalidArchitecture").and.returnValue(false);
      spyOn(MachinesManager, "updateItem").and.returnValue($q.defer().promise);

      $scope.node = node;
      $scope.summary.editing = true;
      $scope.saveEditSummary();

      expect($scope.summary.editing).toBe(false);
    });

    it("calls updateItem with copy of node", function() {
      makeController();
      spyOn($scope, "invalidArchitecture").and.returnValue(false);
      spyOn(MachinesManager, "updateItem").and.returnValue($q.defer().promise);

      $scope.node = node;
      $scope.summary.editing = true;
      $scope.saveEditSummary();

      var calledWithNode = MachinesManager.updateItem.calls.argsFor(0)[0];
      expect(calledWithNode).not.toBe(node);
    });

    it("calls updateItem with new copied values on node", function() {
      makeController();
      spyOn($scope, "invalidArchitecture").and.returnValue(false);
      spyOn(MachinesManager, "updateItem").and.returnValue($q.defer().promise);

      $scope.node = node;
      configureSummary();
      var newZone = $scope.summary.zone.selected;
      var newPool = $scope.summary.pool.selected;
      var newDescription = $scope.summary.description;
      var newArchitecture = $scope.summary.architecture.selected;
      var newTags = [];
      angular.forEach($scope.summary.tags, function(tag) {
        newTags.push(tag.text);
      });
      $scope.saveEditSummary();

      var calledWithNode = MachinesManager.updateItem.calls.argsFor(0)[0];
      expect(calledWithNode.zone).toEqual(newZone);
      expect(calledWithNode.zone).not.toBe(newZone);
      expect(calledWithNode.pool).not.toBe(newPool);
      expect(calledWithNode.description).toBe(newDescription);
      expect(calledWithNode.architecture).toBe(newArchitecture);
      expect(calledWithNode.tags).toEqual(newTags);
    });

    it("logs error if not disconnected error", function() {
      makeController();
      spyOn($scope, "invalidArchitecture").and.returnValue(false);

      var defer = $q.defer();
      spyOn(MachinesManager, "updateItem").and.returnValue(defer.promise);

      $scope.node = node;
      configureSummary();
      $scope.saveEditSummary();

      spyOn($log, "error");
      var error = makeName("error");
      defer.reject(error);
      $rootScope.$digest();

      expect($log.error).toHaveBeenCalledWith(error);
    });
  });

  describe("invalidPowerType", function() {
    it("returns true if missing power type", function() {
      makeController();
      $scope.power.type = null;
      expect($scope.invalidPowerType()).toBe(true);
    });

    it("returns false if selected power type", function() {
      makeController();
      $scope.power.type = {
        name: makeName("power")
      };
      expect($scope.invalidPowerType()).toBe(false);
    });
  });

  describe("editPower", function() {
    it("doesnt sets editing to true if cannot edit", function() {
      makeController();
      spyOn($scope, "canEdit").and.returnValue(false);
      $scope.power.editing = false;
      $scope.editPower();
      expect($scope.power.editing).toBe(false);
    });

    it("sets editing to true for power section", function() {
      makeController();
      spyOn($scope, "canEdit").and.returnValue(true);
      $scope.power.editing = false;
      $scope.editPower();
      expect($scope.power.editing).toBe(true);
    });
  });

  describe("cancelEditPower", function() {
    it("sets editing to false for power section", function() {
      makeController();
      node.power_type = makeName("power");
      $scope.node = node;
      $scope.power.editing = true;
      $scope.cancelEditPower();
      expect($scope.power.editing).toBe(false);
    });

    it("doesnt sets editing to false when no power_type", function() {
      makeController();
      $scope.node = node;
      $scope.power.editing = true;
      $scope.cancelEditPower();
      expect($scope.power.editing).toBe(true);
    });

    it("sets editing false with no power_type for controller", function() {
      makeController();
      node.node_type = 4;
      $scope.node = node;
      $scope.power.editing = true;
      $scope.cancelEditPower();
      expect($scope.power.editing).toBe(false);
    });

    it("sets in_pod to true for node in pod", function() {
      makeController();
      node.power_type = makeName("power");
      node.pod = makeName("pod");
      $scope.node = node;
      $scope.power.editing = true;
      $scope.cancelEditPower();
      expect($scope.power.in_pod).toBe(true);
    });
  });

  describe("saveEditPower", function() {
    it("does nothing if no selected power_type", function() {
      makeController();
      $scope.node = node;
      var editing = {};
      $scope.power.editing = editing;
      $scope.power.type = null;
      $scope.saveEditPower();
      // Editing should still be true, because the function exitted
      // early.
      expect($scope.power.editing).toBe(editing);
    });

    it("sets editing to false", function() {
      makeController();
      spyOn(MachinesManager, "updateItem").and.returnValue($q.defer().promise);

      $scope.node = node;
      $scope.power.editing = true;
      $scope.power.type = {
        name: makeName("power")
      };
      $scope.saveEditPower();

      expect($scope.power.editing).toBe(false);
    });

    it("calls updateItem with copy of node", function() {
      makeController();
      spyOn(MachinesManager, "updateItem").and.returnValue($q.defer().promise);

      $scope.node = node;
      $scope.power.editing = true;
      $scope.power.type = {
        name: makeName("power")
      };
      $scope.saveEditPower();

      var calledWithNode = MachinesManager.updateItem.calls.argsFor(0)[0];
      expect(calledWithNode).not.toBe(node);
    });

    it("calls updateItem with new copied values on node", function() {
      makeController();
      spyOn(MachinesManager, "updateItem").and.returnValue($q.defer().promise);

      var newPowerType = {
        name: makeName("power")
      };
      var newPowerParameters = {
        foo: makeName("bar")
      };

      $scope.node = node;
      $scope.power.editing = true;
      $scope.power.type = newPowerType;
      $scope.power.parameters = newPowerParameters;
      $scope.saveEditPower();

      var calledWithNode = MachinesManager.updateItem.calls.argsFor(0)[0];
      expect(calledWithNode.power_type).toBe(newPowerType.name);
      expect(calledWithNode.power_parameters).toEqual(newPowerParameters);
      expect(calledWithNode.power_parameters).not.toBe(newPowerParameters);
    });

    it("calls handleSaveError once updateItem is rejected", function() {
      makeController();

      var defer = $q.defer();
      spyOn(MachinesManager, "updateItem").and.returnValue(defer.promise);

      $scope.node = node;
      $scope.power.editing = true;
      $scope.power.type = {
        name: makeName("power")
      };
      $scope.power.parameters = {
        foo: makeName("bar")
      };
      $scope.saveEditPower();

      spyOn($log, "error");
      var error = makeName("error");
      defer.reject(error);
      $rootScope.$digest();

      // If the error message was logged to the console then
      // handleSaveError was called.
      expect($log.error).toHaveBeenCalledWith(error);
    });
  });

  describe("allowShowMoreEvents", function() {
    it("returns false if node is null", function() {
      makeController();
      $scope.node = null;
      expect($scope.allowShowMoreEvents()).toBe(false);
    });

    it("returns false if node.events is not array", function() {
      makeController();
      $scope.node = node;
      $scope.node.events = undefined;
      expect($scope.allowShowMoreEvents()).toBe(false);
    });

    it("returns false if node has no events", function() {
      makeController();
      $scope.node = node;
      expect($scope.allowShowMoreEvents()).toBe(false);
    });

    it("returns false if node events less then the limit", function() {
      makeController();
      $scope.node = node;
      $scope.node.events = [makeEvent(), makeEvent()];
      $scope.events.limit = 10;
      expect($scope.allowShowMoreEvents()).toBe(false);
    });

    it("returns false if events limit greater than 50", function() {
      makeController();
      $scope.node = node;
      var i;
      for (i = 0; i < 50; i++) {
        $scope.node.events.push(makeEvent());
      }
      $scope.events.limit = 50;
      expect($scope.allowShowMoreEvents()).toBe(false);
    });

    it("returns true if more events than limit", function() {
      makeController();
      $scope.node = node;
      var i;
      for (i = 0; i < 20; i++) {
        $scope.node.events.push(makeEvent());
      }
      $scope.events.limit = 10;
      expect($scope.allowShowMoreEvents()).toBe(true);
    });
  });

  describe("showMoreEvents", function() {
    it("increments events limit by 10", function() {
      makeController();
      $scope.showMoreEvents();
      expect($scope.events.limit).toBe(20);
      $scope.showMoreEvents();
      expect($scope.events.limit).toBe(30);
    });
  });

  describe("getEventText", function() {
    it("returns just event type description without dash", function() {
      makeController();
      var evt = makeEvent();
      delete evt.description;
      expect($scope.getEventText(evt)).toBe(evt.type.description);
    });

    it("returns event type description with event description", function() {
      makeController();
      var evt = makeEvent();
      expect($scope.getEventText(evt)).toBe(
        evt.type.description + " - " + evt.description
      );
    });
  });

  describe("getPowerEventError", function() {
    it("returns event if there is a power event error", function() {
      makeController();
      var evt = makeEvent();
      evt.type.level = "warning";
      evt.type.description = "Failed to query node's BMC";
      $scope.node = node;
      $scope.node.events = [makeEvent(), evt];
      expect($scope.getPowerEventError()).toBe(evt);
    });

    it("returns nothing if there is no power event error", function() {
      makeController();
      var evt_info = makeEvent();
      var evt_error = makeEvent();
      evt_info.type.level = "info";
      evt_info.type.description = "Queried node's BMC";
      evt_error.type.level = "warning";
      evt_error.type.description = "Failed to query node's BMC";
      $scope.node = node;
      $scope.node.events = [makeEvent(), evt_info, evt_error];
      expect($scope.getPowerEventError()).toBe();
    });
  });

  describe("hasPowerEventError", function() {
    it("returns true if last event is an error", function() {
      makeController();
      var evt = makeEvent();
      evt.type.level = "warning";
      evt.type.description = "Failed to query node's BMC";
      $scope.node = node;
      $scope.node.events = [evt];
      expect($scope.hasPowerEventError()).toBe(true);
    });

    it("returns false if last event is not an error", function() {
      makeController();
      $scope.node = node;
      $scope.node.events = [makeEvent()];
      expect($scope.hasPowerEventError()).toBe(false);
    });
  });

  describe("getPowerEventErrorText", function() {
    it("returns just empty string", function() {
      makeController();
      $scope.node = node;
      $scope.node.events = [makeEvent()];
      expect($scope.getPowerEventErrorText()).toBe("");
    });

    it("returns event description", function() {
      makeController();
      var evt = makeEvent();
      evt.type.level = "warning";
      evt.type.description = "Failed to query node's BMC";
      $scope.node = node;
      $scope.node.events = [evt];
      expect($scope.getPowerEventErrorText()).toBe(evt.description);
    });
  });

  describe("getServiceClass", function() {
    it("returns 'none' if null", function() {
      makeController();
      expect($scope.getServiceClass(null)).toBe("none");
    });

    it("returns 'success' when running", function() {
      makeController();
      expect(
        $scope.getServiceClass({
          status: "running"
        })
      ).toBe("success");
    });

    it("returns 'power-error' when dead", function() {
      makeController();
      expect(
        $scope.getServiceClass({
          status: "dead"
        })
      ).toBe("error");
    });

    it("returns 'warning' when degraded", function() {
      makeController();
      expect(
        $scope.getServiceClass({
          status: "degraded"
        })
      ).toBe("warning");
    });

    it("returns 'none' for anything else", function() {
      makeController();
      expect(
        $scope.getServiceClass({
          status: makeName("status")
        })
      ).toBe("none");
    });
  });

  describe("hasCustomCommissioningScripts", function() {
    it("returns true with custom commissioning scripts", function() {
      makeController();
      ScriptsManager._items.push({ script_type: 0 });
      expect($scope.hasCustomCommissioningScripts()).toBe(true);
    });

    it("returns false without custom commissioning scripts", function() {
      makeController();
      expect($scope.hasCustomCommissioningScripts()).toBe(false);
    });
  });

  describe("showFailedTestWarning", function() {
    it("returns false when device", function() {
      makeController();
      $scope.node = {
        node_type: 1
      };
      expect($scope.showFailedTestWarning()).toBe(false);
    });

    it("returns false when new, commissioning, or testing", function() {
      makeController();
      $scope.node = node;
      angular.forEach([0, 1, 2, 21, 22], function(status) {
        node.status_code = status;
        expect($scope.showFailedTestWarning()).toBe(false);
      });
    });

    it("returns false when tests havn't been run or passed", function() {
      makeController();
      // READY
      node.status_code = 4;
      $scope.node = node;
      angular.forEach([-1, 2], function(status) {
        node.testing_status.status = status;
        expect($scope.showFailedTestWarning()).toBe(false);
      });
    });

    it("returns true otherwise", function() {
      makeController();
      var i, j;
      $scope.node = node;
      // i < 3 or i > 20 is tested above.
      for (i = 3; i <= 20; i++) {
        for (j = 3; j <= 8; j++) {
          node.status_code = i;
          node.testing_status.status = j;
          expect($scope.showFailedTestWarning()).toBe(true);
        }
      }
    });
  });

  describe("getCPUSubtext", () => {
    function pluraliseCoresText(count) {
      if (count === 1) {
        return "core";
      } else {
        return "cores";
      }
    }

    it("returns only cores when unknown speed", () => {
      makeController();
      $scope.node = node;
      expect($scope.getCPUSubtext()).toEqual(
        node.cpu_count + " " + pluraliseCoresText(node.cpu_count)
      );
    });

    it("returns speed in mhz", () => {
      makeController();
      $scope.node = node;
      $scope.node.cpu_speed = makeInteger(100, 999);
      expect($scope.getCPUSubtext()).toEqual(
        node.cpu_count +
          " " +
          pluraliseCoresText(node.cpu_count) +
          ", " +
          node.cpu_speed +
          " MHz"
      );
    });

    it("returns speed in ghz", () => {
      makeController();
      $scope.node = node;
      $scope.node.cpu_speed = makeInteger(1000, 10000);
      expect($scope.getCPUSubtext()).toEqual(
        node.cpu_count +
          " " +
          pluraliseCoresText(node.cpu_count) +
          ", " +
          node.cpu_speed / 1000 +
          " GHz"
      );
    });
  });

  describe("openSection", function() {
    it("sets section.area to passed argument", function() {
      makeController();
      $scope.node = node;
      $scope.openSection("controllers");
      expect($scope.section.area).toBe("controllers");
    });
  });

  describe("dismissHighAvailabilityNotification", function() {
    it("sets hideHighAvailabilityNotification to true", function() {
      makeController();
      $scope.vlan = { id: 5001 };
      $scope.hideHighAvailabilityNotification = false;
      $scope.dismissHighAvailabilityNotification();
      expect($scope.hideHighAvailabilityNotification).toBe(true);
    });
  });

  describe("showHighAvailabilityNotification", function() {
    it("returns true if hide notification flag not set", function() {
      makeController();
      $scope.hideHighAvailabilityNotification = false;
      $scope.node = {
        dhcp_on: true
      };
      $scope.vlan = {
        rack_sids: ["asd3d", "sd3sd"],
        secondary_rack: ""
      };
      expect($scope.showHighAvailabilityNotification()).toBe(true);
    });

    it("returns false if hide notification flag is set", function() {
      makeController();
      $scope.hideHighAvailabilityNotification = true;
      $scope.node = {
        dhcp_on: true
      };
      $scope.vlan = {
        rack_sids: ["asd3d", "sd3sd"],
        secondary_rack: ""
      };
      expect($scope.showHighAvailabilityNotification()).toBe(false);
    });

    it("returns false if dhcp not enabled", function() {
      makeController();
      $scope.hideHighAvailabilityNotification = false;
      $scope.node = {
        dhcp_on: false
      };
      $scope.vlan = {
        rack_sids: ["asd3d", "sd3sd"],
        secondary_rack: ""
      };
      expect($scope.showHighAvailabilityNotification()).toBe(false);
    });

    it("returns false if one or less rack_sid", function() {
      makeController();
      $scope.hideHighAvailabilityNotification = false;
      $scope.node = {
        dhcp_on: true
      };
      $scope.vlan = {
        rack_sids: ["asd3d"],
        secondary_rack: ""
      };
      expect($scope.showHighAvailabilityNotification()).toBe(false);
    });

    it("returns false if has secondary rack", function() {
      makeController();
      $scope.hideHighAvailabilityNotification = false;
      $scope.node = {
        dhcp_on: false
      };
      $scope.vlan = {
        rack_sids: ["asd3d", "sd3sd"],
        secondary_rack: "sdf3"
      };
      expect($scope.showHighAvailabilityNotification()).toBe(false);
    });
  });

  describe(
    "getHardwareTestErrorText if 'Unable to run destructive" +
      " test while deployed!'",
    function() {
      it("returns correct string", function() {
        makeController();
        expect(
          $scope.getHardwareTestErrorText(
            "Unable to run destructive test while deployed!"
          )
        ).toBe(
          "The selected hardware tests contain one or more destructive tests." +
            " Destructive tests cannot run on deployed machines."
        );
      });

      it(
        "return passed error string if not 'Unable to run destructive test" +
          " while deployed!'",
        function() {
          makeController();
          var errorString = "There was an error";
          expect($scope.getHardwareTestErrorText(errorString)).toBe(
            errorString
          );
        }
      );
    }
  );

  describe("powerParametersValid", function() {
    it("returns false if no power_parameters", function() {
      makeController();
      expect($scope.powerParametersValid()).toBe(false);
    });

    it("returns false if power_parameters are empty", function() {
      makeController();
      expect($scope.powerParametersValid({})).toBe(false);
    });

    it("returns true if power_parameters have values", function() {
      makeController();
      expect(
        $scope.powerParametersValid({
          power_address: "qemu+ssh://ubuntu@172.16.3.247/system",
          power_id: 26
        })
      ).toBe(true);
    });

    it("returns true if optional power_parameters are empty", function() {
      makeController();
      expect(
        $scope.powerParametersValid({
          power_address: "qemu+ssh://ubuntu@172.16.3.247/system",
          power_id: 26,
          mac_address: ""
        })
      ).toBe(true);
    });
  });

  describe("checkTestParameterValues", () => {
    it("disables test button if a parameter has no value", () => {
      makeController();
      $scope.disableTestButton = false;
      $scope.testSelection = [
        {
          name: "foo",
          parameters: {
            url: { type: "url", value: "" },
            bar: { type: "url", value: "https://example.com" }
          }
        }
      ];
      $scope.checkTestParameterValues();
      expect($scope.disableTestButton).toBe(true);
    });

    it("enables test button if all parameters have values", () => {
      makeController();
      $scope.disableTestButton = true;
      $scope.testSelection = [
        {
          name: "foo",
          parameters: {
            url: { type: "url", value: "https://one.example.com" },
            bar: { type: "url", value: "https://example.com" }
          }
        }
      ];
      $scope.checkTestParameterValues();
      expect($scope.disableTestButton).toBe(false);
    });
  });

  describe("setDefaultValues", () => {
    it("sets value to default if no value", () => {
      makeController();
      const parameters = {
        foo: { default: "https://example.com" }
      };
      const updatedParameters = $scope.setDefaultValues(parameters);
      expect(updatedParameters).toEqual({
        foo: { default: "https://example.com", value: "https://example.com" }
      });
    });

    it("sets value to default even if it has a value", () => {
      makeController();
      const parameters = {
        foo: { default: "https://example.com", value: "https://website.com" }
      };
      const updatedParameters = $scope.setDefaultValues(parameters);
      expect(updatedParameters).toEqual({
        foo: { default: "https://example.com", value: "https://example.com" }
      });
    });
  });

  describe("validateNetworkConfiguration", () => {
    it("broadcasts validate event with test action", () => {
      makeController();
      spyOn($rootScope, "$broadcast");
      $scope.action.availableOptions = [{ name: "test" }];
      $scope.validateNetworkConfiguration();
      expect($rootScope.$broadcast).toHaveBeenCalledWith("validate", {
        name: "test"
      });
    });
  });

  describe("getDHCPStatus", () => {
    it("returns correct text if dhcp is provided by MAAS", () => {
      makeController();
      const vlan = { external_dhcp: null, dhcp_on: true, id: 0 };
      const iface = { vlan_id: vlan.id };
      $scope.vlans = [vlan];
      expect($scope.getDHCPStatus(iface)).toEqual("MAAS-provided");
    });

    it("returns correct text if dhcp is provided externally", () => {
      makeController();
      const vlan = { external_dhcp: "127.0.0.1", dhcp_on: true, id: 0 };
      const iface = { vlan_id: vlan.id };
      $scope.vlans = [vlan];
      expect($scope.getDHCPStatus(iface)).toEqual("External (127.0.0.1)");
    });

    it("returns correct text if dhcp is disabled", () => {
      makeController();
      const vlan = { external_dhcp: null, dhcp_on: false, id: 0 };
      const iface = { vlan_id: vlan.id };
      $scope.vlans = [vlan];
      expect($scope.getDHCPStatus(iface)).toEqual("No DHCP");
    });

    it("returns correct text if vlan is null", () => {
      makeController();
      const iface = { vlan_id: null };
      $scope.vlans = [];
      expect($scope.getDHCPStatus(iface)).toEqual("No DHCP");
    });
  });

  describe("getFabricName", () => {
    it("returns the fabric name of the VLAN of an interface", () => {
      makeController();
      const fabric = { id: 1, name: "foo" };
      const otherFabric = { id: 2, name: "bar" };
      const vlan = { fabric: 1 };
      const otherVlan = { fabric: 2 };
      const iface = { vlan_id: vlan.id };
      $scope.fabrics = [fabric, otherFabric];
      $scope.vlans = [vlan, otherVlan];
      expect($scope.getFabricName(iface)).toEqual("foo");
    });
  });

  describe("groupInterfaces", () => {
    it(`returns physical interfaces grouped by
      vendor/product/firmware_version`, () => {
      makeController();
      const nic1 = {
        vendor: "vendor1",
        product: "product1",
        firmware_version: "1.0.0",
        type: "physical"
      };
      const nic2 = {
        vendor: "vendor2",
        product: "product2",
        firmware_version: "2.0.0",
        type: "physical"
      };
      const nic3 = {
        vendor: "vendor3",
        product: "product3",
        firmware_version: "3.0.0",
        type: "bridge"
      };
      const interfaces = [nic1, nic2, nic2, nic3, nic3, nic3];
      const grouped = $scope.groupInterfaces(interfaces);
      expect(grouped.length).toEqual(2);
      expect(grouped[0].interfaces.length).toEqual(1);
      expect(grouped[0].vendor).toEqual("vendor1");
      expect(grouped[1].interfaces.length).toEqual(2);
      expect(grouped[1].vendor).toEqual("vendor2");
    });

    it("sorts groups by vendor > product > firmware_version", () => {
      makeController();
      const nic1 = {
        vendor: "vendorA",
        product: "productA",
        firmware_version: "1",
        type: "physical"
      };
      const nic2 = {
        vendor: "vendorA",
        product: "productA",
        firmware_version: "2",
        type: "physical"
      };
      const nic3 = {
        vendor: "vendorA",
        product: "productB",
        firmware_version: "1",
        type: "physical"
      };
      const nic4 = {
        vendor: "vendorB",
        product: "productA",
        firmware_version: "1",
        type: "physical"
      };
      const interfaces = [nic3, nic2, nic4, nic1];
      const grouped = $scope.groupInterfaces(interfaces);
      expect(grouped.length).toEqual(4);
      expect(grouped[0].vendor).toEqual("vendorA");
      expect(grouped[1].firmware_version).toEqual("2");
      expect(grouped[2].product).toEqual("productB");
      expect(grouped[3].vendor).toEqual("vendorB");
    });
  });
});
