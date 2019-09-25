/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for SubentsListController.
 */

import { makeInteger, makeName } from "testing/utils";
import MockWebSocket from "testing/websocket";

describe("VLANDetailsController", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  var VLAN_ID = makeInteger(5000, 6000);

  // Make a fake VLAN
  function makeVLAN() {
    var vlan = {
      id: VLAN_ID,
      vid: makeInteger(1, 4094),
      fabric: 1,
      name: null,
      dhcp_on: true,
      space_ids: [2001],
      primary_rack: primaryController.system_id,
      secondary_rack: secondaryController.system_id,
      rack_sids: []
    };
    VLANsManager._items.push(vlan);
    return vlan;
  }

  // Make a fake fabric
  function makeFabric(id) {
    if (id === undefined) {
      id = 1;
    }
    var fabric = {
      id: id,
      name: "fabric-" + id,
      default_vlan_id: 5000
    };
    FabricsManager._items.push(fabric);
    return fabric;
  }

  // Make a fake space
  function makeSpace(id) {
    if (id === undefined) {
      id = 2001;
    }
    var space = {
      id: id,
      name: "space-" + id
    };
    SpacesManager._items.push(space);
    return space;
  }

  // Make a fake subnet
  function makeSubnet(id, spaceId) {
    if (id === undefined) {
      id = 6001;
    }
    if (!spaceId) {
      spaceId = 2001;
    }
    var subnet = {
      id: id,
      name: null,
      cidr: "192.168.0.1/24",
      space: spaceId,
      vlan: VLAN_ID,
      statistics: { ranges: [] }
    };
    SubnetsManager._items.push(subnet);
    return subnet;
  }

  // Make a fake controller
  function makeRackController(id, name, sid, vlan) {
    var rack = {
      id: id,
      system_id: sid,
      hostname: name,
      node_type: 2,
      default_vlan_id: VLAN_ID,
      vlan_ids: [VLAN_ID]
    };
    ControllersManager._items.push(rack);
    if (angular.isObject(vlan)) {
      VLANsManager.addRackController(vlan, rack);
    }
    return rack;
  }

  // Grab the needed angular pieces.
  var $controller, $rootScope, $filter, $location, $scope, $q;
  beforeEach(inject(function($injector) {
    $controller = $injector.get("$controller");
    $rootScope = $injector.get("$rootScope");
    $filter = $injector.get("$filter");
    $location = $injector.get("$location");
    $scope = $rootScope.$new();
    $q = $injector.get("$q");
  }));

  // Load any injected managers and services.
  var VLANsManager, SubnetsManager, SpacesManager, FabricsManager;
  var ControllersManager, UsersManager, ManagerHelperService, ErrorService;
  var DHCPSnippetsManager, RegionConnection, webSocket;
  beforeEach(inject(function($injector) {
    VLANsManager = $injector.get("VLANsManager");
    SubnetsManager = $injector.get("SubnetsManager");
    SpacesManager = $injector.get("SpacesManager");
    FabricsManager = $injector.get("FabricsManager");
    ControllersManager = $injector.get("ControllersManager");
    UsersManager = $injector.get("UsersManager");
    ManagerHelperService = $injector.get("ManagerHelperService");
    ErrorService = $injector.get("ErrorService");
    DHCPSnippetsManager = $injector.get("DHCPSnippetsManager");
    RegionConnection = $injector.get("RegionConnection");

    // Mock buildSocket so an actual connection is not made.
    webSocket = new MockWebSocket();
    spyOn(RegionConnection, "buildSocket").and.returnValue(webSocket);
    spyOn(RegionConnection, "callMethod").and.returnValue($q.defer().promise);
  }));

  var vlan, fabric, fabric2, primaryController, secondaryController;
  var subnet, $routeParams;
  beforeEach(function() {
    primaryController = makeRackController(1, "primary", "p1");
    secondaryController = makeRackController(2, "secondary", "p2");
    vlan = makeVLAN();
    VLANsManager.addRackController(vlan, primaryController);
    VLANsManager.addRackController(vlan, secondaryController);
    fabric = makeFabric(1);
    fabric2 = makeFabric(2);
    makeSpace();
    subnet = makeSubnet();
    $routeParams = {
      vlan_id: vlan.id
    };
  });

  function makeController(loadManagersDefer) {
    var loadManagers = spyOn(ManagerHelperService, "loadManagers");
    if (angular.isObject(loadManagersDefer)) {
      loadManagers.and.returnValue(loadManagersDefer.promise);
    } else {
      loadManagers.and.returnValue($q.defer().promise);
    }

    // Create the controller.
    var controller = $controller("VLANDetailsController as vlanDetails", {
      $scope: $scope,
      $rootScope: $rootScope,
      $routeParams: $routeParams,
      $filter: $filter,
      $location: $location,
      VLANsManager: VLANsManager,
      SubnetsManager: SubnetsManager,
      SpacesManager: SpacesManager,
      FabricsManager: FabricsManager,
      ControllersManager: ControllersManager,
      UsersManager: UsersManager,
      ManagerHelperService: ManagerHelperService,
      ErrorService: ErrorService
    });

    return controller;
  }

  // Make the controller and resolve the setActiveItem call.
  function makeControllerResolveSetActiveItem() {
    var setActiveDefer = $q.defer();
    spyOn(VLANsManager, "setActiveItem").and.returnValue(
      setActiveDefer.promise
    );
    var defer = $q.defer();
    var controller = makeController(defer);

    defer.resolve();
    $rootScope.$digest();
    setActiveDefer.resolve(vlan);
    $rootScope.$digest();

    return controller;
  }

  it("sets title and page on $rootScope", function() {
    makeController();
    expect($rootScope.title).toBe("Loading...");
    expect($rootScope.page).toBe("networks");
  });

  it("calls loadManagers with required managers", function() {
    makeController();
    expect(ManagerHelperService.loadManagers).toHaveBeenCalledWith($scope, [
      VLANsManager,
      SubnetsManager,
      SpacesManager,
      FabricsManager,
      ControllersManager,
      UsersManager,
      DHCPSnippetsManager
    ]);
  });

  it("raises error if vlan identifier is invalid", function() {
    spyOn(VLANsManager, "setActiveItem").and.returnValue($q.defer().promise);
    spyOn(ErrorService, "raiseError").and.returnValue($q.defer().promise);
    var defer = $q.defer();
    var controller = makeController(defer);
    $routeParams.vlan_id = "xyzzy";

    defer.resolve();
    $rootScope.$digest();

    expect(controller.vlan).toBe(null);
    expect(controller.loaded).toBe(false);
    expect(VLANsManager.setActiveItem).not.toHaveBeenCalled();
    expect(ErrorService.raiseError).toHaveBeenCalled();
  });

  it("doesn't call setActiveItem if vlan is loaded", function() {
    spyOn(VLANsManager, "setActiveItem").and.returnValue($q.defer().promise);
    var defer = $q.defer();
    var controller = makeController(defer);
    VLANsManager._activeItem = vlan;
    $routeParams.vlan_id = vlan.id;

    defer.resolve();
    $rootScope.$digest();

    expect(controller.vlan).toBe(vlan);
    expect(controller.loaded).toBe(true);
    expect(VLANsManager.setActiveItem).not.toHaveBeenCalled();
  });

  it("calls setActiveItem if vlan is not active", function() {
    spyOn(VLANsManager, "setActiveItem").and.returnValue($q.defer().promise);
    var defer = $q.defer();
    makeController(defer);
    $routeParams.vlan_id = vlan.id;

    defer.resolve();
    $rootScope.$digest();

    expect(VLANsManager.setActiveItem).toHaveBeenCalledWith(vlan.id);
  });

  it("sets vlan and loaded once setActiveItem resolves", function() {
    var controller = makeControllerResolveSetActiveItem();
    expect(controller.vlan).toBe(vlan);
    expect(controller.loaded).toBe(true);
  });

  it("title is updated once setActiveItem resolves", function() {
    var controller = makeControllerResolveSetActiveItem();
    expect(controller.title).toBe("VLAN " + vlan.vid + " in " + fabric.name);
  });

  it("default VLAN title is special", function() {
    vlan.vid = 0;
    var controller = makeControllerResolveSetActiveItem();
    expect(controller.title).toBe("Default VLAN in " + fabric.name);
  });

  it("custom VLAN name renders in title", function() {
    vlan.name = "Super Awesome VLAN";
    var controller = makeControllerResolveSetActiveItem();
    expect(controller.title).toBe("Super Awesome VLAN in " + fabric.name);
  });

  it("changes title when VLAN name changes", function() {
    vlan.vid = 0;
    var controller = makeControllerResolveSetActiveItem();
    expect(controller.title).toBe("Default VLAN in " + fabric.name);
    vlan.name = "Super Awesome VLAN";
    $scope.$digest();
    expect(controller.title).toBe("Super Awesome VLAN in " + fabric.name);
  });

  it("changes title when fabric name changes", function() {
    vlan.name = "Super Awesome VLAN";
    var controller = makeControllerResolveSetActiveItem();
    expect(controller.title).toBe("Super Awesome VLAN in " + fabric.name);
    fabric.name = "space";
    $scope.$digest();
    expect(controller.title).toBe("Super Awesome VLAN in space");
  });

  it("updates VLAN when fabric changes", function() {
    vlan.name = "Super Awesome VLAN";
    var controller = makeControllerResolveSetActiveItem();
    expect(controller.title).toBe("Super Awesome VLAN in " + fabric.name);
    fabric2.name = "space";
    vlan.fabric = fabric2.id;
    $scope.$digest();
    expect(controller.title).toBe("Super Awesome VLAN in space");
  });

  it("updates primaryRack variable when controller changes", function() {
    vlan.primary_rack = 0;
    var controller = makeControllerResolveSetActiveItem();
    expect(controller.primaryRack).toBe(null);
    expect(controller.secondaryRack).toBe(secondaryController);
    vlan.primary_rack = primaryController.system_id;
    $scope.$digest();
    expect(controller.primaryRack).toBe(primaryController);
  });

  it("updates secondaryRack variable when controller changes", function() {
    vlan.secondary_rack = 0;
    var controller = makeControllerResolveSetActiveItem();
    expect(controller.primaryRack).toBe(primaryController);
    expect(controller.secondaryRack).toBe(null);
    vlan.secondary_rack = secondaryController.system_id;
    $scope.$digest();
    expect(controller.secondaryRack).toBe(secondaryController);
  });

  it("updates reatedControllers when controllers list changes", function() {
    var controller = makeControllerResolveSetActiveItem();
    expect(controller.controllers.length).toBe(2);
    expect(controller.relatedControllers.length).toBe(2);
    makeRackController(3, "three", "t3", vlan);
    expect(controller.relatedControllers.length).toBe(2);
    expect(controller.controllers.length).toBe(3);
    $scope.$digest();
    expect(controller.relatedControllers.length).toBe(3);
  });

  it("updates relatedSubnets when subnets list changes", function() {
    var controller = makeControllerResolveSetActiveItem();
    makeSubnet(6002);
    expect(controller.relatedSubnets.length).toBe(1);
    expect(controller.subnets.length).toBe(2);
    $scope.$digest();
    expect(controller.relatedSubnets.length).toBe(2);
  });

  it("updates relatedSubnets when spaces list changes", function() {
    var controller = makeControllerResolveSetActiveItem();
    expect(controller.spaces.length).toBe(1);
    makeSpace(2002);
    vlan.space_ids.push(2002);
    makeSubnet(6002, 2002);
    expect(controller.controllers.length).toBe(2);
    $scope.$digest();
  });

  it("actionOption cleared on action success", function() {
    var controller = makeControllerResolveSetActiveItem();
    controller.actionOption = controller.DELETE_ACTION;
    var defer = $q.defer();
    spyOn(VLANsManager, "deleteVLAN").and.returnValue(defer.promise);
    controller.actionGo();
    defer.resolve();
    $scope.$digest();
    expect(controller.actionOption).toBe(null);
    expect(controller.actionError).toBe(null);
  });

  it(
    "prepares provideDHCPAction on actionOptionChanged " +
      "and populates suggested gateway",
    function() {
      var controller = makeControllerResolveSetActiveItem();
      controller.subnets[0].gateway_ip = null;
      controller.subnets[0].statistics = {
        suggested_gateway: "192.168.0.1"
      };
      // to avoid side effects of calling `openDHCPPanel`
      spyOn(controller, "setSuggestedRange");
      controller.updateSubnet();
      controller.openDHCPPanel();
      expect(controller.provideDHCPAction).toEqual({
        subnet: subnet.id,
        relayVLAN: null,
        primaryRack: "p1",
        secondaryRack: "p2",
        maxIPs: 0,
        startIP: "",
        startPlaceholder: "(no available IPs)",
        endIP: "",
        endPlaceholder: "(no available IPs)",
        gatewayIP: "192.168.0.1",
        gatewayPlaceholder: "192.168.0.1",
        needsGatewayIP: true,
        subnetMissingGatewayIP: true,
        needsDynamicRange: false
      });
    }
  );

  it("prevents selection of a duplicate rack controller", function() {
    var controller = makeControllerResolveSetActiveItem();
    // to avoid side effects of calling `openDHCPPanel`
    spyOn(controller, "setSuggestedRange");
    controller.openDHCPPanel();
    controller.provideDHCPAction.primaryRack = "p2";
    controller.updatePrimaryRack();
    expect(controller.provideDHCPAction.primaryRack).toEqual("p2");
    // This should automatically select p1 by default; the user has to
    // clear it out manually if desired. (this is done via an extra option
    // in the view.)
    expect(controller.provideDHCPAction.secondaryRack).toBe(
      controller.secondaryRack
    );
    controller.provideDHCPAction.secondaryRack = "p2";
    controller.updateSecondaryRack();
    expect(controller.provideDHCPAction.primaryRack).toBe(null);
    expect(controller.provideDHCPAction.secondaryRack).toBe(null);
  });

  describe("filterPrimaryRack", function() {
    it("filters out the currently-selected primary rack", function() {
      var controller = makeControllerResolveSetActiveItem();
      // to avoid side effects of calling `openDHCPPanel`
      spyOn(controller, "setSuggestedRange");
      controller.openDHCPPanel();
      // The filter should return false if the item is to be excluded.
      // So the primary rack should match, as this filter is used from
      // the secondary rack drop-down to exclude the primary.
      expect(controller.filterPrimaryRack(primaryController)).toBe(false);
      expect(controller.filterPrimaryRack(secondaryController)).toBe(true);
    });
  });

  describe("enterEditSummary", function() {
    it("sets editSummary", function() {
      var controller = makeController();
      controller.enterEditSummary();
      expect(controller.editSummary).toBe(true);
    });
  });

  describe("exitEditSummary", function() {
    it("sets editSummary", function() {
      var controller = makeController();
      controller.enterEditSummary();
      controller.exitEditSummary();
      expect(controller.editSummary).toBe(false);
    });
  });

  describe("getSpaceName", function() {
    it("returns space name", function() {
      var controller = makeController();
      var spaceName = makeName("space");
      SpacesManager._items = [
        {
          id: 1,
          name: spaceName
        }
      ];
      controller.vlan = {
        space: 1
      };
      expect(controller.getSpaceName()).toBe(spaceName);
    });

    it("returns space (undefined)", function() {
      var controller = makeController();
      controller.vlan = {};
      expect(controller.getSpaceName()).toBe("(undefined)");
    });
  });

  describe("updatePossibleActions", function() {
    // Note: updatePossibleActions() is called indirectly by these tests
    // after all the managers load.

    it("returns an empty actions list for a non-superuser", function() {
      vlan.dhcp_on = true;
      UsersManager._authUser = { is_superuser: false };
      var controller = makeControllerResolveSetActiveItem();
      $scope.$digest();
      expect(controller.actionOptions).toEqual([]);
    });

    it("returns delete when dhcp is off", function() {
      vlan.dhcp_on = false;
      UsersManager._authUser = { is_superuser: true };
      var controller = makeControllerResolveSetActiveItem();
      expect(controller.actionOptions).toEqual([controller.DELETE_ACTION]);
    });

    it("returns delete when dhcp is on", function() {
      vlan.dhcp_on = true;
      UsersManager._authUser = { is_superuser: true };
      var controller = makeControllerResolveSetActiveItem();
      expect(controller.actionOptions).toEqual([controller.DELETE_ACTION]);
    });

    it("returns delete when relay_vlan is set", function() {
      vlan.relay_vlan = 5001;
      UsersManager._authUser = { is_superuser: true };
      var controller = makeControllerResolveSetActiveItem();
      expect(controller.actionOptions).toEqual([controller.DELETE_ACTION]);
    });
  });

  describe("openDHCPPanel", function() {
    it("opens DHCP panel", function() {
      var controller = makeControllerResolveSetActiveItem();
      // to avoid side effects of calling `openDHCPPanel`
      spyOn(controller, "setSuggestedRange");
      controller.openDHCPPanel();
      expect(controller.showDHCPPanel).toBe(true);
    });

    it("calls `initProvideDHCP` and `setSuggestedRange`", function() {
      var controller = makeControllerResolveSetActiveItem();
      spyOn(controller, "initProvideDHCP");
      spyOn(controller, "setSuggestedRange");
      controller.openDHCPPanel();
      expect(controller.initProvideDHCP).toHaveBeenCalled();
      expect(controller.setSuggestedRange).toHaveBeenCalled();
    });
  });

  describe("closeDHCPPanel", function() {
    it("closes DHCP Panel", function() {
      var controller = makeController();
      controller.showDHCPPanel = true;
      controller.closeDHCPPanel();
      expect(controller.showDHCPPanel).toBe(false);
    });

    it("unsets `suggestedRange`", function() {
      var controller = makeController();
      controller.suggestedRange = {
        subnet: 1,
        type: "dynamic",
        comment: "Dynamic",
        start_ip: "127.168.0.1",
        end_ip: "127.168.0.2",
        gateway_ip: "127.168.0.0"
      };
      controller.closeDHCPPanel();
      expect(controller.suggestedRange).toBe(null);
    });

    it("unsets `isProvidingDHCP`", function() {
      var controller = makeController();
      controller.isProvidingDHCP = true;
      controller.closeDHCPPanel();
      expect(controller.isProvidingDHCP).toBe(false);
    });

    it("unsets `DHCPError`", function() {
      var controller = makeController();
      controller.DHCPError = "Lorem ipsum dolor sit amet";
      controller.closeDHCPPanel();
      expect(controller.DHCPError).toBe(null);
    });

    it("sets `MAASProvidesDHCP`", function() {
      var controller = makeController();
      controller.MAASProvidesDHCP = false;
      controller.closeDHCPPanel();
      expect(controller.MAASProvidesDHCP).toBe(true);
    });
  });

  describe("getDHCPButtonText", function() {
    it("reads 'Enable' if status is disabled", function() {
      var controller = makeControllerResolveSetActiveItem();
      controller.vlan.dhcp_on = false;
      expect(controller.getDHCPButtonText()).toBe("Enable DHCP");
    });

    it("reads 'Reconfigure' if status is enabled", function() {
      var controller = makeControllerResolveSetActiveItem();
      controller.vlan.dhcp_on = true;
      expect(controller.getDHCPButtonText()).toBe("Reconfigure DHCP");
    });

    it("reads 'Reconfigure relay' if status is relayed", function() {
      var controller = makeControllerResolveSetActiveItem();
      controller.vlan.relay_vlan = 2;
      expect(controller.getDHCPButtonText()).toBe("Reconfigure DHCP relay");
    });
  });

  describe("showGatewayCol", function() {
    it("returns `true` if one of more subnets have no gateway", function() {
      var controller = makeController();
      controller.relatedSubnets = [
        { subnet: { gateway_ip: "127.0.0.1" } },
        { subnet: { gateway_ip: null } },
        { subnet: { gateway_ip: "127.0.0.2" } }
      ];
      expect(controller.showGatewayCol()).toBe(true);
    });

    it("returns `false` if all subnets have gateway", function() {
      var controller = makeController();
      controller.relatedSubnets = [
        { subnet: { gateway_ip: "127.0.0.1" } },
        { subnet: { gateway_ip: "127.0.0.2" } }
      ];
      expect(controller.showGatewayCol()).toBe(false);
    });
  });

  describe("setSuggestedRange", function() {
    it("sets a suggested IP range", function() {
      var controller = makeController();
      controller.suggestedRange = null;
      controller.relatedSubnets = [
        {
          subnet: {
            id: 1,
            gateway_ip: "127.168.0.0",
            statistics: {
              ranges: [
                {
                  num_addresses: 2,
                  purpose: ["unused"],
                  start: "127.168.0.1",
                  end: "127.168.0.2"
                }
              ]
            }
          }
        }
      ];

      controller.setSuggestedRange();

      expect(controller.suggestedRange).toEqual({
        type: "dynamic",
        comment: "Dynamic",
        start_ip: "127.168.0.1",
        end_ip: "127.168.0.2",
        subnet: 1,
        gateway_ip: "127.168.0.0"
      });
    });

    it("sets placeholders if relay VLAN is set", function() {
      var controller = makeController();
      controller.suggestedRange = null;
      controller.relayVLAN = true;
      controller.relatedSubnets = [
        {
          subnet: {
            id: 1,
            gateway_ip: "127.168.0.0",
            statistics: {
              ranges: [
                {
                  num_addresses: 2,
                  purpose: ["unused"],
                  start: "127.168.0.1",
                  end: "127.168.0.2"
                }
              ]
            }
          }
        }
      ];

      controller.setSuggestedRange();

      expect(controller.suggestedRange).toEqual({
        type: "dynamic",
        comment: "Dynamic",
        start_ip: "",
        end_ip: "",
        subnet: 1,
        gateway_ip: "",
        startPlaceholder: "127.168.0.1 (Optional)",
        endPlaceholder: "127.168.0.2 (Optional)"
      });
    });
  });

  describe("getDHCPPanelTitle", function() {
    it("sets the panel title to 'Configure DHCP'", function() {
      var controller = makeController();
      controller.vlan = { dhcp_on: false };
      expect(controller.getDHCPPanelTitle()).toBe("Configure DHCP");
    });

    it("sets the panel title to 'Reconfigure DHCP'", function() {
      var controller = makeController();
      controller.vlan = { dhcp_on: true };
      expect(controller.getDHCPPanelTitle()).toBe("Reconfigure DHCP");
    });

    it("sets the panel title to 'Configure MAAS-managed DHCP", function() {
      var controller = makeController();
      var VLAN_ID = makeInteger(5000, 6000);
      var vlan = {
        id: VLAN_ID,
        vid: makeInteger(1, 4094),
        fabric: 1,
        name: null,
        dhcp_on: true,
        space_ids: [2001],
        primary_rack: primaryController.system_id,
        secondary_rack: secondaryController.system_id,
        rack_sids: [],
        external_dhcp: 1
      };
      VLANsManager._items.push(vlan);
      controller.vlan = { external_dhcp: 1 };
      expect(controller.getDHCPPanelTitle()).toBe(
        "Configure MAAS-managed DHCP"
      );
    });
  });

  describe("toggleMAASProvidesDHCP", function() {
    it("sets `MAASProvidesDHCP` to `false`", function() {
      var controller = makeController();
      controller.MAASProvidesDHCP = true;
      controller.toggleMAASProvidesDHCP();
      expect(controller.MAASProvidesDHCP).toBe(false);
    });

    it("sets `MAASProvidesDHCP` to `true`", function() {
      var controller = makeController();
      controller.MAASProvidesDHCP = false;
      controller.toggleMAASProvidesDHCP();
      expect(controller.MAASProvidesDHCP).toBe(true);
    });
  });

  describe("setDHCPAction", function() {
    it("sets `provideDHCP` to `true`", function() {
      var controller = makeController();
      // To prevent side effects of calling `openDHCPPanel`
      spyOn(controller, "setSuggestedRange");
      controller.provideDHCP = false;
      controller.relayVLAN = true;
      controller.setDHCPAction("provideDHCP");
      expect(controller.provideDHCP).toBe(true);
      expect(controller.relayVLAN).toBe(false);
    });

    it("sets `relayVLAN` to `false`", function() {
      var controller = makeController();
      // To prevent side effects of calling `openDHCPPanel`
      spyOn(controller, "setSuggestedRange");
      controller.provideDHCP = true;
      controller.relayVLAN = false;
      controller.setDHCPAction("relayVLAN");
      expect(controller.relayVLAN).toBe(true);
      expect(controller.provideDHCP).toBe(false);
    });

    it("calls `setSuggestedRange` for DHCP", function() {
      var controller = makeControllerResolveSetActiveItem();
      spyOn(controller, "setSuggestedRange");
      controller.setDHCPAction("provideDHCP");
      expect(controller.setSuggestedRange).toHaveBeenCalled();
    });

    it("calls `setSuggestedRange` for relay VLAN", function() {
      var controller = makeController();
      spyOn(controller, "setSuggestedRange");
      controller.setDHCPAction("relayVLAN");
      expect(controller.setSuggestedRange).toHaveBeenCalled();
    });
  });

  describe("enableDHCP", function() {
    it("DHCPError populated on action failure", function() {
      var controller = makeControllerResolveSetActiveItem();
      // To prevent side effects of calling `openDHCPPanel`
      spyOn(controller, "setSuggestedRange");
      controller.openDHCPPanel();
      var defer = $q.defer();
      spyOn(VLANsManager, "configureDHCP").and.returnValue(defer.promise);
      controller.enableDHCP();
      const result = {
        error: "errorString",
        request: {
          params: {
            action: "enable_dhcp"
          }
        }
      };
      defer.reject(result);
      $scope.$digest();
      expect(controller.DHCPError).toBe("errorString");
    });

    it("performAction for enable_dhcp called with all params", function() {
      var controller = makeControllerResolveSetActiveItem();
      controller.actionOption = controller.PROVIDE_DHCP_ACTION;
      // This will populate the default values for the racks with
      // the current values from the mock objects.
      // To prevent side effects of calling `openDHCPPanel`
      spyOn(controller, "setSuggestedRange");
      controller.openDHCPPanel();
      controller.provideDHCPAction.subnet = 1;
      controller.provideDHCPAction.gatewayIP = "192.168.0.1";
      controller.provideDHCPAction.startIP = "192.168.0.2";
      controller.provideDHCPAction.endIP = "192.168.0.254";
      var defer = $q.defer();
      spyOn(VLANsManager, "configureDHCP").and.returnValue(defer.promise);
      controller.enableDHCP();
      defer.resolve();
      $scope.$digest();
      expect(VLANsManager.configureDHCP).toHaveBeenCalledWith(
        controller.vlan,
        [controller.primaryRack.system_id, controller.secondaryRack.system_id],
        {
          subnet: 1,
          gateway: "192.168.0.1",
          start: "192.168.0.2",
          end: "192.168.0.254"
        }
      );
      expect(controller.DHCPError).toBe(null);
    });

    it(`performAction for enable_dhcp not called
        if racks are missing`, function() {
      vlan.primary_rack = 0;
      vlan.secondary_rack = 0;
      var controller = makeControllerResolveSetActiveItem();
      controller.actionOption = controller.PROVIDE_DHCP_ACTION;
      // This will populate the default values for the racks with
      // the current values from the mock objects.
      // To prevent side effects of calling `openDHCPPanel`
      spyOn(controller, "setSuggestedRange");
      controller.openDHCPPanel();
      controller.provideDHCPAction.primaryRack = null;
      controller.provideDHCPAction.secondaryRack = null;
      controller.provideDHCPAction.subnet = 1;
      controller.provideDHCPAction.gatewayIP = "192.168.0.1";
      controller.provideDHCPAction.startIP = "192.168.0.2";
      controller.provideDHCPAction.endIP = "192.168.0.254";
      var defer = $q.defer();
      spyOn(VLANsManager, "configureDHCP").and.returnValue(defer.promise);
      controller.enableDHCP();
      defer.resolve();
      $scope.$digest();
      expect(VLANsManager.configureDHCP).not.toHaveBeenCalled();
      expect(controller.DHCPError).toBe(
        "A primary rack controller must be specified."
      );
    });
  });

  describe("relayDHCP", function() {
    it("performAction for relay_dhcp called with all params", function() {
      var controller = makeControllerResolveSetActiveItem();
      controller.actionOption = controller.RELAY_DHCP_ACTION;
      // This will populate the default values for the racks with
      // the current values from the mock objects.
      controller.relatedSubnets = [
        {
          subnet: {
            id: 1,
            gateway_ip: "192.168.0.1",
            statistics: {
              ranges: [
                {
                  num_addresses: 2,
                  purpose: ["unused"],
                  start: "192.168.0.2",
                  end: "192.168.0.254"
                }
              ]
            }
          }
        }
      ];
      controller.openDHCPPanel();
      controller.provideDHCPAction.subnet = 1;
      controller.provideDHCPAction.gatewayIP = "192.168.0.1";
      controller.provideDHCPAction.startIP = "192.168.0.2";
      controller.provideDHCPAction.endIP = "192.168.0.254";
      var relay = {
        id: makeInteger(5001, 6000)
      };
      VLANsManager._items = [relay];
      controller.provideDHCPAction.relayVLAN = relay;
      var defer = $q.defer();
      spyOn(VLANsManager, "configureDHCP").and.returnValue(defer.promise);
      controller.relayDHCP();
      defer.resolve();
      $scope.$digest();
      expect(VLANsManager.configureDHCP).toHaveBeenCalledWith(
        controller.vlan,
        [],
        {
          subnet: 1,
          gateway: "192.168.0.1",
          start: "192.168.0.2",
          end: "192.168.0.254"
        },
        relay.id
      );
      expect(controller.DHCPError).toBe(null);
    });
  });

  describe("disableDHCP", function() {
    it("performAction for disable_dhcp called with all params", function() {
      var controller = makeControllerResolveSetActiveItem();
      controller.actionOption = controller.DISABLE_DHCP_ACTION;
      // This will populate the default values for the racks with
      // the current values from the mock objects.
      // To prevent side effects of calling `openDHCPPanel`
      spyOn(controller, "setSuggestedRange");
      controller.openDHCPPanel();
      var defer = $q.defer();
      spyOn(VLANsManager, "disableDHCP").and.returnValue(defer.promise);
      controller.disableDHCP();
      defer.resolve();
      $scope.$digest();
      expect(VLANsManager.disableDHCP).toHaveBeenCalledWith(controller.vlan);
      expect(controller.DHCPError).toBe(null);
    });
  });

  describe("dismissHighAvailabilityNotification", function() {
    it("sets hideHighAvailabilityNotification to true", function() {
      var controller = makeController();
      controller.vlan = { id: 5001 };
      controller.hideHighAvailabilityNotification = false;
      controller.dismissHighAvailabilityNotification();
      expect(controller.hideHighAvailabilityNotification).toBe(true);
    });
  });

  describe("showHighAvailabilityNotification", function() {
    it("returns true if has DHCP, no secondary rack but could", function() {
      var controller = makeController();
      controller.vlan = { dhcp_on: true };
      controller.provideDHCPAction.secondaryRack = null;
      controller.relatedControllers = [{ id: 1 }, { id: 2 }];
      controller.hideHighAvailabilityNotification = false;
      expect(controller.showHighAvailabilityNotification()).toBe(true);
    });

    it("returns false if no DHCP", function() {
      var controller = makeController();
      controller.vlan = { dhcp_on: false };
      controller.relatedControllers = [{ id: 1 }, { id: 2 }];
      controller.hideHighAvailabilityNotification = false;
      expect(controller.showHighAvailabilityNotification()).toBe(false);
    });

    it("returns false if has secondary rack", function() {
      var controller = makeController();
      controller.vlan = { dhcp_on: true };
      controller.hideHighAvailabilityNotification = false;
      expect(controller.showHighAvailabilityNotification()).toBe(false);
    });

    it("returns false if has no available racks", function() {
      var controller = makeController();
      controller.vlan = { dhcp_on: true };
      controller.hideHighAvailabilityNotification = false;
      expect(controller.showHighAvailabilityNotification()).toBe(false);
    });

    it("returns false if hideHighAvailabilityNotification if true", function() {
      var controller = makeController();
      controller.vlan = { dhcp_on: true };
      controller.hideHighAvailabilityNotification = true;
      expect(controller.showHighAvailabilityNotification()).toBe(false);
    });
  });

  describe("getAvailableVLANS", function() {
    it("doesn't return current VLAN", function() {
      var controller = makeControllerResolveSetActiveItem();
      var vlan = {
        id: 5259,
        vid: 525,
        fabric: 1,
        name: null,
        dhcp_on: true,
        space_ids: [2001],
        primary_rack: primaryController.system_id,
        secondary_rack: secondaryController.system_id,
        rack_sids: [],
        external_dhcp: 1
      };
      controller.vlans = [vlan];
      controller.vlan = vlan;
      expect(controller.getAvailableVLANS()).toBe(0);
    });

    it("doesn't return vlan with no dhcp", function() {
      var controller = makeControllerResolveSetActiveItem();
      var vlan = {
        id: 5259,
        vid: 525,
        fabric: 1,
        name: null,
        dhcp_on: false,
        space_ids: [2001],
        primary_rack: primaryController.system_id,
        secondary_rack: secondaryController.system_id,
        rack_sids: [],
        external_dhcp: 1
      };
      controller.vlans = [vlan];
      controller.vlan = vlan;
      expect(controller.getAvailableVLANS()).toBe(0);
    });

    it("returns if not current vlan and has dhcp", function() {
      var controller = makeControllerResolveSetActiveItem();
      controller.vlans = [
        {
          id: 5259,
          vid: 525,
          fabric: 1,
          name: null,
          dhcp_on: true,
          space_ids: [2001],
          primary_rack: primaryController.system_id,
          secondary_rack: secondaryController.system_id,
          rack_sids: [],
          external_dhcp: 1
        }
      ];
      controller.vlan = {
        id: 5239,
        vid: 525,
        fabric: 1,
        name: null,
        dhcp_on: true,
        space_ids: [2001],
        primary_rack: primaryController.system_id,
        secondary_rack: secondaryController.system_id,
        rack_sids: [],
        external_dhcp: 1
      };
      expect(controller.getAvailableVLANS()).toBe(1);
    });
  });

  describe("canPerformAction", () => {
    it("returns true if actionOption is delete", () => {
      const controller = makeController();
      controller.actionOption = controller.DELETE_ACTION;
      expect(controller.canPerformAction()).toBe(true);
    });
  });
});
