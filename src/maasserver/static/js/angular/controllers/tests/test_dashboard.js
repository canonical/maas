/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for DashboardController.
 */

describe("DashboardController", function() {

    // Load the MAAS module.
    beforeEach(module("MAAS"));

    // Grab the needed angular pieces.
    var $controller, $rootScope, $scope, $q, $routeParams, $location;
    beforeEach(inject(function($injector) {
        $controller = $injector.get("$controller");
        $rootScope = $injector.get("$rootScope");
        $location = $injector.get("$location");
        $scope = $rootScope.$new();
        $q = $injector.get("$q");
        $routeParams = {};
    }));

    // Load any injected managers and services.
    var DiscoveriesManager, DomainsManager, MachinesManager, DevicesManager;
    var SubnetsManager, VLANsManager, ConfigsManager, ManagerHelperService;
    beforeEach(inject(function($injector) {
        DiscoveriesManager = $injector.get("DiscoveriesManager");
        DomainsManager = $injector.get("DomainsManager");
        MachinesManager = $injector.get("MachinesManager");
        DevicesManager = $injector.get("DevicesManager");
        SubnetsManager = $injector.get("SubnetsManager");
        VLANsManager = $injector.get("VLANsManager");
        ConfigsManager = $injector.get("ConfigsManager");
        ManagerHelperService = $injector.get("ManagerHelperService");
    }));

    // Makes the DashboardController
    function makeController(loadManagerDefer) {
        var loadManagers = spyOn(ManagerHelperService, "loadManagers");
        if(angular.isObject(loadManagerDefer)) {
            loadManagers.and.returnValue(loadManagerDefer.promise);
        } else {
            loadManagers.and.returnValue($q.defer().promise);
        }

        // Create the controller.
        var controller = $controller("DashboardController", {
            $scope: $scope,
            $rootScope: $rootScope,
            DiscoveriesManager: DiscoveriesManager,
            DomainsManager: DomainsManager,
            MachinesManager: MachinesManager,
            DevicesManager: DevicesManager,
            SubnetsManager: SubnetsManager,
            VLANsManager: VLANsManager,
            ConfigsManager: ConfigsManager,
            ManagerHelperService: ManagerHelperService
        });

        return controller;
    }

    it("sets title and page on $rootScope", function() {
        var controller = makeController();
        expect($rootScope.title).toBe("Dashboard");
        expect($rootScope.page).toBe("dashboard");
    });

    it("calls loadManagers with correct managers", function() {
        var controller = makeController();
        expect(ManagerHelperService.loadManagers).toHaveBeenCalledWith(
            $scope, [
                DiscoveriesManager, DomainsManager, MachinesManager,
                DevicesManager, SubnetsManager, VLANsManager, ConfigsManager]);
    });

    it("sets initial $scope", function() {
        var controller = makeController();
        expect($scope.loading).toBe(true);
        expect($scope.discoveredDevices).toBe(DiscoveriesManager.getItems());
        expect($scope.domains).toBe(DomainsManager.getItems());
        expect($scope.machines).toBe(MachinesManager.getItems());
        expect($scope.deviceManager).toBe(DevicesManager);
        expect($scope.configManager).toBe(ConfigsManager);
        expect($scope.networkDiscovery).toBeNull();
        expect($scope.column).toBe('mac');
        expect($scope.selectedDevice).toBeNull();
        expect($scope.convertTo).toBeNull();
    });

    describe("getDiscoveryName", function() {

        it("returns discovery hostname", function() {
            var controller = makeController();
            var discovery = { hostname: "hostname" };
            expect($scope.getDiscoveryName(discovery)).toBe("hostname");
        });

        it("returns discovery mac_organization with device octets", function() {
            var controller = makeController();
            var discovery = {
                hostname: null,
                mac_organization: "mac-org",
                mac_address: "00:11:22:33:44:55"
            };
            var expected_name = "unknown-mac-org-33-44-55";
            expect($scope.getDiscoveryName(discovery)).toBe(expected_name);
        });

        it("returns discovery with device mac", function() {
            var controller = makeController();
            var discovery = {
                hostname: null,
                mac_organization: null,
                mac_address: "00:11:22:33:44:55"
            };
            var expected_name = "unknown-00-11-22-33-44-55";
            expect($scope.getDiscoveryName(discovery)).toBe(expected_name);
        });
    });

    describe("getSubnetName", function() {

        it("calls SubnetsManager.getName with subnet", function() {
            var controller = makeController();
            var subnet = {
                id: makeInteger(0, 100)
            };
            var sentinel = {};
            SubnetsManager._items = [subnet];
            spyOn(SubnetsManager, "getName").and.returnValue(sentinel);
            expect($scope.getSubnetName(subnet.id)).toBe(sentinel);
            expect(SubnetsManager.getName).toHaveBeenCalledWith(subnet);
        });
    });

    describe("getVLANName", function() {

        it("calls VLANsManager.getName with vlan", function() {
            var controller = makeController();
            var vlan = {
                id: makeInteger(0, 100)
            };
            var sentinel = {};
            VLANsManager._items = [vlan];
            spyOn(VLANsManager, "getName").and.returnValue(sentinel);
            expect($scope.getVLANName(vlan.id)).toBe(sentinel);
            expect(VLANsManager.getName).toHaveBeenCalledWith(vlan);
        });
    });

    describe("toggleSelected", function() {

        it("clears selected if already selected", function() {
            var controller = makeController();
            var id = makeInteger(0, 100);
            $scope.selectedDevice = id;
            $scope.toggleSelected(id);
            expect($scope.selectedDevice).toBeNull();
        });

        it("sets selectedDevice and convertTo with static", function() {
            var controller = makeController();
            var id = makeInteger(0, 100);
            var defaultDomain = {
                id: 0
            };
            DomainsManager._items = [defaultDomain];
            var discovered = {
                discovery_id: id,
                hostname: makeName("hostname"),
                subnet: makeInteger(0, 100)
            };
            DiscoveriesManager._items = [discovered];
            $scope.toggleSelected(id);
            expect($scope.selectedDevice).toBe(id);
            expect($scope.convertTo).toEqual({
                type: 'device',
                hostname: $scope.getDiscoveryName(discovered),
                domain: defaultDomain,
                ip_assignment: 'dynamic',
                goTo: false,
                deviceIPOptions: [
                    ['dynamic', 'Dynamic'],
                    ['static', 'Static'],
                    ['external', 'External']
                ]
            });
        });

        it("sets selectedDevice and convertTo without static", function() {
            var controller = makeController();
            var id = makeInteger(0, 100);
            var defaultDomain = {
                id: 0
            };
            DomainsManager._items = [defaultDomain];
            var discovered = {
                discovery_id: id,
                hostname: makeName("hostname"),
                subnet: null
            };
            DiscoveriesManager._items = [discovered];
            $scope.toggleSelected(id);
            expect($scope.selectedDevice).toBe(id);
            expect($scope.convertTo).toEqual({
                type: 'device',
                hostname: $scope.getDiscoveryName(discovered),
                domain: defaultDomain,
                ip_assignment: 'dynamic',
                goTo: false,
                deviceIPOptions: [
                    ['dynamic', 'Dynamic'],
                    ['external', 'External']
                ]
            });
        });
    });

    describe("preProcess", function() {

        it("adjust item to include the needed fields", function() {
            var controller = makeController();
            var id = makeInteger(0, 100);
            var defaultDomain = {
                id: 0
            };
            DomainsManager._items = [defaultDomain];
            var discovered = {
                discovery_id: id,
                hostname: makeName("hostname"),
                subnet: makeInteger(0, 100),
                mac_address: makeName("mac"),
                ip: makeName("ip")
            };
            DiscoveriesManager._items = [discovered];
            $scope.toggleSelected(id);
            var observed = $scope.preProcess($scope.convertTo);
            expect(observed).not.toBe($scope.convertTo);
            expect(observed).toEqual({
                type: 'device',
                hostname: $scope.getDiscoveryName(discovered),
                domain: defaultDomain,
                ip_assignment: 'dynamic',
                goTo: false,
                deviceIPOptions: [
                    ['dynamic', 'Dynamic'],
                    ['static', 'Static'],
                    ['external', 'External']
                ],
                primary_mac: discovered.mac_address,
                extra_macs: [],
                interfaces: [{
                    mac: discovered.mac_address,
                    ip_assignment: 'dynamic',
                    ip_address: discovered.ip,
                    subnet: discovered.subnet
                }]
            });
        });
    });

    describe("afterSave", function() {

        it("removes item from DiscoveriesManager", function() {
            var controller = makeController();
            var id = makeInteger(0, 100);
            $scope.selectedDevice = id;
            $scope.convertTo = {
                goTo: false
            };
            spyOn(DiscoveriesManager, "_removeItem");
            $scope.afterSave();
            expect(DiscoveriesManager._removeItem).toHaveBeenCalledWith(id);
            expect($scope.selectedDevice).toBeNull();
        });

        it("doesn't call $location.path if not goTo", function() {
            var controller = makeController();
            var id = makeInteger(0, 100);
            $scope.selectedDevice = id;
            $scope.convertTo = {
                goTo: false
            };
            spyOn(DiscoveriesManager, "_removeItem");
            spyOn($location, "path");
            $scope.afterSave();
            expect($location.path).not.toHaveBeenCalled();
        });

        it("calls $location.path if goTo", function() {
            var controller = makeController();
            var id = makeInteger(0, 100);
            $scope.selectedDevice = id;
            $scope.convertTo = {
                goTo: true
            };
            spyOn(DiscoveriesManager, "_removeItem");
            var path = {
                search: jasmine.createSpy("search")
            };
            spyOn($location, "path").and.returnValue(path);
            $scope.afterSave();
            expect($location.path).toHaveBeenCalledWith("/nodes");
            expect(path.search).toHaveBeenCalledWith({ tab: "devices" });
        });
    });
});
