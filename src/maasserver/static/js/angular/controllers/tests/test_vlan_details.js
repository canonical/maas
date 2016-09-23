/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for SubentsListController.
 */

describe("VLANDetailsController", function() {

    // Load the MAAS module.
    beforeEach(module("MAAS"));

    var VLAN_ID = makeInteger(5000, 6000);

    // Make a fake VLAN
    function makeVLAN() {
        var vlan = {
            id: VLAN_ID,
            vid: makeInteger(1,4094),
            fabric: 1,
            name: null,
            dhcp_on: true,
            space_ids: [2001],
            primary_rack: primaryController.id,
            secondary_rack: secondaryController.id,
            primary_rack_sid: primaryController.system_id,
            secondary_rack_sid: secondaryController.system_id,
            rack_sids: []
        };
        VLANsManager._items.push(vlan);
        return vlan;
    }

    // Make a fake fabric
    function makeFabric() {
        var fabric = {
            id: 1,
            name: 'fabric-0'
        };
        FabricsManager._items.push(fabric);
        return fabric;
    }

    // Make a fake space
    function makeSpace(id) {
        if(id === undefined) {
            id = 2001;
        }
        var space = {
            id: id,
            name: 'space-' + id
        };
        SpacesManager._items.push(space);
        return space;
    }

    // Make a fake subnet
    function makeSubnet(id, spaceId) {
        if(id === undefined) {
            id = 6001;
        }
        if(!spaceId) {
            spaceId = 2001;
        }
        var subnet = {
            id: id,
            name: null,
            cidr: '192.168.0.1/24',
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
        if(angular.isObject(vlan)) {
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
    beforeEach(inject(function($injector) {
        VLANsManager = $injector.get("VLANsManager");
        SubnetsManager = $injector.get("SubnetsManager");
        SpacesManager = $injector.get("SpacesManager");
        FabricsManager = $injector.get("FabricsManager");
        ControllersManager = $injector.get("ControllersManager");
        UsersManager = $injector.get("UsersManager");
        ManagerHelperService = $injector.get("ManagerHelperService");
        ErrorService = $injector.get("ErrorService");
    }));

    var vlan, fabric, primaryController, secondaryController, $routeParams;
    var space, subnet;
    beforeEach(function() {
        primaryController = makeRackController(1, "primary", "p1");
        secondaryController = makeRackController(2, "secondary", "p2");
        vlan = makeVLAN();
        VLANsManager.addRackController(vlan, primaryController);
        VLANsManager.addRackController(vlan, secondaryController);
        fabric = makeFabric();
        space = makeSpace();
        subnet = makeSubnet();
        $routeParams = {
            vlan_id: vlan.id
        };
    });

    function makeController(loadManagersDefer) {
        var loadManagers = spyOn(ManagerHelperService, "loadManagers");
        if(angular.isObject(loadManagersDefer)) {
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
            setActiveDefer.promise);
        var defer = $q.defer();
        var controller = makeController(defer);

        defer.resolve();
        $rootScope.$digest();
        setActiveDefer.resolve(vlan);
        $rootScope.$digest();

        return controller;
    }

    it("sets title and page on $rootScope", function() {
        var controller = makeController();
        expect($rootScope.title).toBe("Loading...");
        expect($rootScope.page).toBe("networks");
    });

    it("calls loadManagers with required managers", function() {
        var controller = makeController();
        expect(ManagerHelperService.loadManagers).toHaveBeenCalledWith(
            $scope, [
                VLANsManager, SubnetsManager, SpacesManager, FabricsManager,
                ControllersManager, UsersManager]);
    });

    it("raises error if vlan identifier is invalid", function() {
        spyOn(VLANsManager, "setActiveItem").and.returnValue(
            $q.defer().promise);
        spyOn(ErrorService, "raiseError").and.returnValue(
            $q.defer().promise);
        var defer = $q.defer();
        var controller = makeController(defer);
        $routeParams.vlan_id = 'xyzzy';

        defer.resolve();
        $rootScope.$digest();

        expect(controller.vlan).toBe(null);
        expect(controller.loaded).toBe(false);
        expect(VLANsManager.setActiveItem).not.toHaveBeenCalled();
        expect(ErrorService.raiseError).toHaveBeenCalled();
    });

    it("doesn't call setActiveItem if vlan is loaded", function() {
        spyOn(VLANsManager, "setActiveItem").and.returnValue(
            $q.defer().promise);
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
        spyOn(VLANsManager, "setActiveItem").and.returnValue(
            $q.defer().promise);
        var defer = $q.defer();
        var controller = makeController(defer);
        $routeParams.vlan_id = vlan.id;

        defer.resolve();
        $rootScope.$digest();

        expect(VLANsManager.setActiveItem).toHaveBeenCalledWith(
            vlan.id);
    });

    it("sets vlan and loaded once setActiveItem resolves", function() {
        var controller = makeControllerResolveSetActiveItem();
        expect(controller.vlan).toBe(vlan);
        expect(controller.loaded).toBe(true);
    });

    it("title is updated once setActiveItem resolves", function() {
        var controller = makeControllerResolveSetActiveItem();
        expect(controller.title).toBe(
            "VLAN " + vlan.vid + " in " + fabric.name);
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

    it("updates primaryRack variable when controller changes", function() {
        vlan.primary_rack = 0;
        vlan.primary_rack_sid = null;
        var controller = makeControllerResolveSetActiveItem();
        expect(controller.primaryRack).toBe(null);
        expect(controller.secondaryRack).toBe(secondaryController);
        vlan.primary_rack = primaryController.id;
        vlan.primary_rack_sid = primaryController.system_id;
        $scope.$digest();
        expect(controller.primaryRack).toBe(primaryController);
    });

    it("updates secondaryRack variable when controller changes", function() {
        vlan.secondary_rack = 0;
        vlan.secondary_rack_sid = null;
        var controller = makeControllerResolveSetActiveItem();
        expect(controller.primaryRack).toBe(primaryController);
        expect(controller.secondaryRack).toBe(null);
        vlan.secondary_rack = secondaryController.id;
        vlan.secondary_rack_sid = secondaryController.system_id;
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

    it("updates relatedSpaces and relatedSubnets when spaces list changes",
        function() {
        var controller = makeControllerResolveSetActiveItem();
        expect(controller.spaces.length).toBe(1);
        expect(controller.relatedSpaces.length).toBe(1);
        makeSpace(2002);
        vlan.space_ids.push(2002);
        makeSubnet(6002, 2002);
        expect(controller.relatedSpaces.length).toBe(1);
        expect(controller.controllers.length).toBe(2);
        $scope.$digest();
        expect(controller.relatedSpaces.length).toBe(2);
    });

    it("actionOption cleared on action success", function() {
        var controller = makeControllerResolveSetActiveItem();
        controller.actionOption = controller.DELETE_ACTION;
        var defer = $q.defer();
        spyOn(VLANsManager, "deleteVLAN").and.returnValue(
            defer.promise);
        controller.actionGo();
        defer.resolve();
        $scope.$digest();
        expect(controller.actionOption).toBe(null);
        expect(controller.actionError).toBe(null);
    });

    it("actionOption and actionError populated on action failure", function() {
        var controller = makeControllerResolveSetActiveItem();
        controller.actionOption = controller.PROVIDE_DHCP_ACTION;
        // This will populate the default values for the racks with
        // the current values from the mock objects.
        controller.actionOptionChanged();
        var defer = $q.defer();
        spyOn(VLANsManager, "configureDHCP").and.returnValue(
            defer.promise);
        controller.actionGo();
        result = {error: 'errorString', request: {
            params: {
                action: 'enable_dhcp'
            }
        }};
        controller.actionOption = null;
        defer.reject(result);
        $scope.$digest();
        expect(controller.actionOption).toBe(controller.PROVIDE_DHCP_ACTION);
        expect(controller.actionError).toBe('errorString');
    });

    it("performAction for enable_dhcp not called if racks are missing",
    function() {
        vlan.primary_rack = 0;
        vlan.primary_rack_sid = null;
        vlan.secondary_rack = 0;
        vlan.secondary_rack_sid = null;
        var controller = makeControllerResolveSetActiveItem();
        controller.actionOption = controller.PROVIDE_DHCP_ACTION;
        // This will populate the default values for the racks with
        // the current values from the mock objects.
        controller.actionOptionChanged();
        controller.provideDHCPAction.primaryRack = null;
        controller.provideDHCPAction.secondaryRack = null;
        controller.provideDHCPAction.subnet = 1;
        controller.provideDHCPAction.gatewayIP = "192.168.0.1";
        controller.provideDHCPAction.startIP = "192.168.0.2";
        controller.provideDHCPAction.endIP = "192.168.0.254";
        var defer = $q.defer();
        spyOn(VLANsManager, "configureDHCP").and.returnValue(
            defer.promise);
        controller.actionGo();
        defer.resolve();
        $scope.$digest();
        expect(VLANsManager.configureDHCP).not.toHaveBeenCalled();
        expect(controller.actionOption).toBe(controller.PROVIDE_DHCP_ACTION);
        expect(controller.actionError).toBe(
            "A primary rack controller must be specified.");
    });


    it("performAction for enable_dhcp called with all params", function() {
        var controller = makeControllerResolveSetActiveItem();
        controller.actionOption = controller.PROVIDE_DHCP_ACTION;
        // This will populate the default values for the racks with
        // the current values from the mock objects.
        controller.actionOptionChanged();
        controller.provideDHCPAction.subnet = 1;
        controller.provideDHCPAction.gatewayIP = "192.168.0.1";
        controller.provideDHCPAction.startIP = "192.168.0.2";
        controller.provideDHCPAction.endIP = "192.168.0.254";
        var defer = $q.defer();
        spyOn(VLANsManager, "configureDHCP").and.returnValue(
            defer.promise);
        controller.actionGo();
        defer.resolve();
        $scope.$digest();
        expect(VLANsManager.configureDHCP).toHaveBeenCalledWith(
            controller.vlan,
            [
                controller.primaryRack.system_id,
                controller.secondaryRack.system_id
            ],
            {
                subnet: 1,
                gateway: "192.168.0.1",
                start: "192.168.0.2",
                end: "192.168.0.254"
            }
        );
        expect(controller.actionOption).toBe(null);
        expect(controller.actionError).toBe(null);
    });

    it("performAction for disable_dhcp called with all params", function() {
        var controller = makeControllerResolveSetActiveItem();
        controller.actionOption = controller.DISABLE_DHCP_ACTION;
        // This will populate the default values for the racks with
        // the current values from the mock objects.
        controller.actionOptionChanged();
        var defer = $q.defer();
        spyOn(VLANsManager, "disableDHCP").and.returnValue(
            defer.promise);
        controller.actionGo();
        defer.resolve();
        $scope.$digest();
        expect(VLANsManager.disableDHCP).toHaveBeenCalledWith(controller.vlan);
        expect(controller.actionOption).toBe(null);
        expect(controller.actionError).toBe(null);
    });


    it("prepares provideDHCPAction on actionOptionChanged " +
        "and populates suggested gateway", function() {
        var controller = makeControllerResolveSetActiveItem();
        controller.subnets[0].gateway_ip = null;
        controller.subnets[0].statistics = {
            suggested_gateway: "192.168.0.1"
        };
        controller.updateSubnet();
        controller.actionOption = controller.PROVIDE_DHCP_ACTION;
        controller.actionOptionChanged();
        expect(controller.provideDHCPAction).toEqual({
            subnet: subnet.id,
            primaryRack: "p1",
            secondaryRack: "p2",
            maxIPs: 0,
            startIP: "",
            startPlaceholder: "(no available IPs)",
            endIP: "",
            endPlaceholder: "(no available IPs)",
            gatewayIP: '192.168.0.1',
            gatewayPlaceholder: '192.168.0.1',
            needsGatewayIP: true,
            subnetMissingGatewayIP: true,
            needsDynamicRange: false
        });
    });

    it("provideDHCPAction uses suggested dynamic range", function() {
        var controller = makeControllerResolveSetActiveItem();
        controller.subnets[0].statistics = {
            num_addresses: 26,
            suggested_dynamic_range: {
                num_addresses: 26,
                start: "192.168.0.200",
                end: "192.168.0.225"
            },
            first_address: "192.168.0.1"
        };
        controller.updateSubnet();
        controller.actionOption = controller.PROVIDE_DHCP_ACTION;
        controller.actionOptionChanged();
        expect(controller.provideDHCPAction).toEqual({
            subnet: subnet.id,
            primaryRack: "p1",
            secondaryRack: "p2",
            maxIPs: 26,
            startIP: "192.168.0.200",
            endIP: "192.168.0.225",
            startPlaceholder: "192.168.0.200",
            endPlaceholder: "192.168.0.225",
            gatewayIP: '',
            gatewayPlaceholder: '',
            needsGatewayIP: false,
            subnetMissingGatewayIP: true,
            needsDynamicRange: true
        });
    });

    it("prevents selection of a duplicate rack controller", function() {
        var controller = makeControllerResolveSetActiveItem();
        controller.actionOption = controller.PROVIDE_DHCP_ACTION;
        controller.actionOptionChanged();
        controller.provideDHCPAction.primaryRack = "p2";
        controller.updatePrimaryRack();
        expect(controller.provideDHCPAction.primaryRack).toEqual("p2");
        // This should automatically select p1 by default; the user has to
        // clear it out manually if desired. (this is done via an extra option
        // in the view.)
        expect(controller.provideDHCPAction.secondaryRack).toBe("p1");
        controller.provideDHCPAction.secondaryRack = "p2";
        controller.updateSecondaryRack();
        expect(controller.provideDHCPAction.primaryRack).toBe(null);
        expect(controller.provideDHCPAction.secondaryRack).toBe(null);
    });

    describe("filterPrimaryRack", function() {

        it("filters out the currently-selected primary rack",
        function() {
            var controller = makeControllerResolveSetActiveItem();
            controller.actionOption = controller.PROVIDE_DHCP_ACTION;
            controller.actionOptionChanged();
            // The filter should return false if the item is to be excluded.
            // So the primary rack should match, as this filter is used from
            // the secondary rack drop-down to exclude the primary.
            expect(controller.filterPrimaryRack(
                primaryController)).toBe(false);
            expect(controller.filterPrimaryRack(
                secondaryController)).toBe(true);
        });
    });

    describe("updatePossibleActions", function() {

        // Note: updatePossibleActions() is called indirectly by these tests
        // after all the managers load.

        it("returns an empty actions list for a non-superuser",
        function() {
            vlan.dhcp_on = true;
            UsersManager._authUser = {is_superuser: false};
            var controller = makeControllerResolveSetActiveItem();
            $scope.$digest();
            expect(controller.actionOptions).toEqual([]);
        });

        it("returns enable_dhcp and delete when dhcp is off",
        function() {
            vlan.dhcp_on = false;
            UsersManager._authUser = {is_superuser: true};
            var controller = makeControllerResolveSetActiveItem();
            expect(controller.actionOptions).toEqual([
                controller.PROVIDE_DHCP_ACTION,
                controller.DELETE_ACTION
            ]);
            expect(controller.PROVIDE_DHCP_ACTION.title).toBe("Provide DHCP");
        });

        it("returns disable_dhcp, enable_dhcp (with new title) and delete "+
            "when dhcp is on", function() {
            vlan.dhcp_on = true;
            UsersManager._authUser = {is_superuser: true};
            var controller = makeControllerResolveSetActiveItem();
            expect(controller.actionOptions).toEqual([
                controller.DISABLE_DHCP_ACTION,
                controller.PROVIDE_DHCP_ACTION,
                controller.DELETE_ACTION
            ]);
            expect(controller.PROVIDE_DHCP_ACTION.title).toBe(
                "Reconfigure DHCP");
        });
    });
});
