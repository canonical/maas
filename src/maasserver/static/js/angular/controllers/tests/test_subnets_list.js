/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for SubentsListController.
 */

describe("SubentsListController", function() {

    // Load the MAAS module.
    beforeEach(module("MAAS"));

    // Grab the needed angular pieces.
    var $controller, $rootScope, $scope, $q, $routeParams;
    beforeEach(inject(function($injector) {
        $controller = $injector.get("$controller");
        $rootScope = $injector.get("$rootScope");
        $scope = $rootScope.$new();
        $q = $injector.get("$q");
        $routeParams = {};
    }));

    // Load the NodesManager, DevicesManager,
    // NodesManager, RegionConnection, SearchService.
    var SubnetsManager, FabricsManager, SpacesManager, VLANsManager;
    var ManagerHelperService, RegionConnection;
    beforeEach(inject(function($injector) {
        SubnetsManager = $injector.get("SubnetsManager");
        FabricsManager = $injector.get("FabricsManager");
        SpacesManager = $injector.get("SpacesManager");
        VLANsManager = $injector.get("VLANsManager");
        ManagerHelperService = $injector.get("ManagerHelperService");
    }));

    // Makes the NodesListController
    function makeController(loadManagersDefer, defaultConnectDefer) {
        var loadManagers = spyOn(ManagerHelperService, "loadManagers");
        if(angular.isObject(loadManagersDefer)) {
            loadManagers.and.returnValue(loadManagersDefer.promise);
        } else {
            loadManagers.and.returnValue($q.defer().promise);
        }

        // Create the controller.
        var controller = $controller("SubnetsListController", {
            $scope: $scope,
            $rootScope: $rootScope,
            $routeParams: $routeParams,
            SubnetsManager: SubnetsManager,
            FabricsManager: FabricsManager,
            SpacesManager: SpacesManager,
            VLANsManager: VLANsManager,
            ManagerHelperService: ManagerHelperService
        });

        return controller;
    }

    it("sets title and page on $rootScope", function() {
        var controller = makeController();
        expect($rootScope.title).toBe("Fabrics");
        expect($rootScope.page).toBe("subnets");
    });

    it("sets initial values on $scope", function() {
        // tab-independant variables.
        var controller = makeController();
        expect($scope.subnets).toBe(SubnetsManager.getItems());
        expect($scope.fabrics).toBe(FabricsManager.getItems());
        expect($scope.spaces).toBe(SpacesManager.getItems());
        expect($scope.vlans).toBe(VLANsManager.getItems());
        expect($scope.loading).toBe(true);
    });

    it("calls loadManagers with SubnetsManager, FabricsManager, " +
        "SpacesManager, VLANsManager",
        function() {
            var controller = makeController();
            expect(ManagerHelperService.loadManagers).toHaveBeenCalledWith(
                [SubnetsManager, FabricsManager, SpacesManager, VLANsManager]);
        });

    it("sets loading to false with loadManagers resolves", function() {
        var defer = $q.defer();
        var controller = makeController(defer);
        defer.resolve();
        $rootScope.$digest();
        expect($scope.loading).toBe(false);
    });

    describe("toggleTab", function() {

        it("sets $rootScope.title", function() {
            var controller = makeController();
            $scope.toggleTab('spaces');
            expect($rootScope.title).toBe($scope.tabs.spaces.pagetitle);
            $scope.toggleTab('fabrics');
            expect($rootScope.title).toBe($scope.tabs.fabrics.pagetitle);
        });

        it("sets currentpage", function() {
            var controller = makeController();
            $scope.toggleTab('spaces');
            expect($scope.currentpage).toBe('spaces');
            $scope.toggleTab('fabrics');
            expect($scope.currentpage).toBe('fabrics');
        });
    });

    it("fabrics updated properly", function() {
        var controller = makeController();
        var fabrics = [
            { id: 0, name: "fabric 0" },
            { id: 1, name: "fabric 1" }
        ];
        var spaces = [
            { id: 0, name: "Default space" },
            { id: 1, name: "DMZ" },
            { id: 2, name: "LAN" }
        ];
        var vlans = [
            { id: 0, name: "vlan5", vid: 5, fabric: 0 },
            { id: 1, name: "vlan4", vid: 4, fabric: 0 },
            { id: 2, name: "vlan3", vid: 3, fabric: 1 }
        ];
        var subnets = [
            { id:0, name:"subnet 0", vlan:1, space:1, cidr:"10.20.0.0/16" },
            { id:1, name:"subnet 1", vlan:1, space:1, cidr:"10.10.0.0/24" },
            { id:2, name:"subnet 2", vlan:1, space:2, cidr:"10.0.0.0/24" },
            { id:3, name:"subnet 3", vlan:2, space:1, cidr:"10.99.0.0/23" },
            { id:4, name:"subnet 4", vlan:2, space:1, cidr:"10.100.6.0/24" },
            { id:5, name:"subnet 5", vlan:1, space:1, cidr:"10.200.7.0/24" }
        ];
        var expectedFabricsData = [
          { fabric: { id: 0, name: 'fabric 0' },
            rows: [
              {
                vlan: { id: 0, name: 'vlan5', vid: 5, fabric: 0 },
                space: null,
                subnet: null
              },
              { vlan: { id: 1, name: 'vlan4', vid: 4, fabric: 0 },
                space: { id: 1, name: 'DMZ' },
                subnet: {
                  id: 0, name: 'subnet 0', vlan: 1, space: 1,
                  cidr: '10.20.0.0/16'
                }
              },
              { vlan: { id: 1, name: 'vlan4', vid: 4, fabric: 0 },
                space: { id: 1, name: 'DMZ' },
                subnet: {
                  id: 1, name: 'subnet 1', vlan: 1, space: 1,
                  cidr: '10.10.0.0/24' }
              },
              { vlan: { id: 1, name: 'vlan4', vid: 4, fabric: 0 },
                space: { id: 2, name: 'LAN' },
                subnet: {
                  id: 2, name: 'subnet 2', vlan: 1, space: 2,
                  cidr: '10.0.0.0/24' }
              },
              { vlan: { id: 1, name: 'vlan4', vid: 4, fabric: 0 },
                space: { id: 1, name: 'DMZ' },
                subnet: {
                  id: 5, name: 'subnet 5', vlan: 1, space: 1,
                  cidr: '10.200.7.0/24' }
              }
            ]
          },
          { fabric: { id: 1, name: 'fabric 1' },
            rows: [
              { vlan: { id: 2, name: 'vlan3', vid: 3, fabric: 1 },
                space: { id: 1, name: 'DMZ' },
                subnet: {
                  id: 3, name: 'subnet 3', vlan: 2, space: 1,
                  cidr: '10.99.0.0/23' } },
              { vlan: { id: 2, name: 'vlan3', vid: 3, fabric: 1 },
                space: { id: 1, name: 'DMZ' },
                subnet: {
                  id: 4, name: 'subnet 4', vlan: 2, space: 1,
                  cidr: '10.100.6.0/24' } }
            ]
          }
        ];
        var expectedSpacesData = [
          { space: { id: 0, name: 'Default space' }, rows: [  ] },
          { space: { id: 1, name: 'DMZ' },
            rows: [
              { fabric: { id: 0, name: 'fabric 0' },
                vlan: { id: 1, name: 'vlan4', vid: 4, fabric: 0 },
                subnet: {
                  id: 0, name: 'subnet 0', vlan: 1, space: 1,
                  cidr: '10.20.0.0/16' } },
              { fabric: { id: 0, name: 'fabric 0' },
                vlan: { id: 1, name: 'vlan4', vid: 4, fabric: 0 },
                subnet: {
                  id: 1, name: 'subnet 1', vlan: 1, space: 1,
                  cidr: '10.10.0.0/24' } },
              { fabric: { id: 1, name: 'fabric 1' },
                vlan: { id: 2, name: 'vlan3', vid: 3, fabric: 1 },
                subnet: {
                  id: 3, name: 'subnet 3', vlan: 2, space: 1,
                  cidr: '10.99.0.0/23' } },
              { fabric: { id: 1, name: 'fabric 1' },
                vlan: { id: 2, name: 'vlan3', vid: 3, fabric: 1 },
                subnet: {
                  id: 4, name: 'subnet 4', vlan: 2, space: 1,
                  cidr: '10.100.6.0/24' } },
              { fabric: { id: 0, name: 'fabric 0' },
                vlan: { id: 1, name: 'vlan4', vid: 4, fabric: 0 },
                subnet: {
                  id: 5, name: 'subnet 5', vlan: 1, space: 1,
                  cidr: '10.200.7.0/24' } }
            ]
          },
          { space: { id: 2, name: 'LAN' },
            rows: [
              { fabric: { id: 0, name: 'fabric 0' },
                vlan: { id: 1, name: 'vlan4', vid: 4, fabric: 0 },
                subnet: {
                  id: 2, name: 'subnet 2', vlan: 1, space: 2,
                  cidr: '10.0.0.0/24' } }
            ]
          }
        ];
        $scope.fabrics = fabrics;
        FabricsManager._items = fabrics;
        $scope.spaces = spaces;
        SpacesManager._items = spaces;
        $scope.vlans = vlans;
        VLANsManager._items = vlans;
        $scope.subnets = subnets;
        SubnetsManager._items = subnets;
        $scope.forceUpdateFabricsData();
        $scope.forceUpdateSpacesData();
        expect($scope.tabs.fabrics.data).toEqual(expectedFabricsData);
        expect($scope.tabs.spaces.data).toEqual(expectedSpacesData);
    });

});
