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
        // tab-independent variables.
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

    setupController = function(fabrics, spaces, vlans, subnets) {
        var defer = $q.defer();
        var controller = makeController(defer);
        $scope.fabrics = fabrics;
        FabricsManager._items = fabrics;
        $scope.spaces = spaces;
        SpacesManager._items = spaces;
        $scope.vlans = vlans;
        VLANsManager._items = vlans;
        $scope.subnets = subnets;
        SubnetsManager._items = subnets;
        defer.resolve();
        $rootScope.$digest();
        return controller;
    };

    testUpdates = function(controller, fabrics, spaces, vlans, subnets,
                           expectedFabricsData, expectedSpacesData) {
        $scope.fabrics = fabrics;
        FabricsManager._items = fabrics;
        $scope.spaces = spaces;
        SpacesManager._items = spaces;
        $scope.vlans = vlans;
        VLANsManager._items = vlans;
        $scope.subnets = subnets;
        SubnetsManager._items = subnets;
        $rootScope.$digest();
        expect($scope.tabs.fabrics.data).toEqual(expectedFabricsData);
        expect($scope.tabs.spaces.data).toEqual(expectedSpacesData);
    };

    it("subnet_list initial update happens correctly", function() {
        var fabrics = [ { id: 0, name: "fabric 0" } ];
        var spaces = [ { id: 0, name: "space 0" } ];
        var vlans = [ { id: 1, name: "vlan4", vid: 4, fabric: 0 } ];
        var subnets = [
            { id:0, name:"subnet 0", vlan:1, space:0, cidr:"10.20.0.0/16" }
        ];

        var expectedFabricsData = [
          { fabric: { id: 0, name: 'fabric 0' },
            rows: [
              { vlan: { id: 1, name: 'vlan4', vid: 4, fabric: 0 },
                space: { id: 0, name: 'space 0' },
                subnet: {
                  id: 0, name: 'subnet 0', vlan: 1, space: 0,
                  cidr: '10.20.0.0/16'}
              }
            ]
          }
        ];
        var expectedSpacesData = [
          { space: { id: 0, name: 'space 0' },
            rows: [
              { fabric: { id: 0, name: 'fabric 0' },
                vlan: { id: 1, name: 'vlan4', vid: 4, fabric: 0 },
                subnet: {
                  id: 0, name: 'subnet 0', vlan: 1, space: 0,
                  cidr: '10.20.0.0/16' } }
            ]
          }
        ];
        controller = setupController(fabrics, spaces, vlans, subnets);
        expect($scope.tabs.fabrics.data).toEqual(expectedFabricsData);
        expect($scope.tabs.spaces.data).toEqual(expectedSpacesData);
    });

    it("adding fabric updates lists", function() {
        var fabrics = [ { id: 0, name: "fabric 0" } ];
        var spaces = [ { id: 0, name: "space 0" } ];
        var vlans = [ { id: 1, name: "vlan4", vid: 4, fabric: 0 } ];
        var subnets = [
            { id:0, name:"subnet 0", vlan:1, space:0, cidr:"10.20.0.0/16" }
        ];

        var expectedFabricsData = [
          { fabric: { id: 0, name: 'fabric 0' },
            rows: [
              { vlan: { id: 1, name: 'vlan4', vid: 4, fabric: 0 },
                space: { id: 0, name: 'space 0' },
                subnet: {
                  id: 0, name: 'subnet 0', vlan: 1, space: 0,
                  cidr: '10.20.0.0/16'}
              }
            ]
          },
          { fabric: { id: 1, name: 'fabric 1' }, rows: [ ] }
        ];
        var expectedSpacesData = [
          { space: { id: 0, name: 'space 0' },
            rows: [
              { fabric: { id: 0, name: 'fabric 0' },
                vlan: { id: 1, name: 'vlan4', vid: 4, fabric: 0 },
                subnet: {
                  id: 0, name: 'subnet 0', vlan: 1, space: 0,
                  cidr: '10.20.0.0/16' } }
            ]
          }
        ];
        controller = setupController(fabrics, spaces, vlans, subnets);
        fabrics.push({id: 1, name: "fabric 1"});
        testUpdates(controller, fabrics, spaces, vlans, subnets,
                    expectedFabricsData, expectedSpacesData);

    });

    it("adding space updates lists", function() {
        var fabrics = [ { id: 0, name: "fabric 0" } ];
        var spaces = [ { id: 0, name: "space 0" } ];
        var vlans = [ { id: 1, name: "vlan4", vid: 4, fabric: 0 } ];
        var subnets = [
            { id:0, name:"subnet 0", vlan:1, space:0, cidr:"10.20.0.0/16" }
        ];

        var expectedFabricsData = [
          { fabric: { id: 0, name: 'fabric 0' },
            rows: [
              { vlan: { id: 1, name: 'vlan4', vid: 4, fabric: 0 },
                space: { id: 0, name: 'space 0' },
                subnet: {
                  id: 0, name: 'subnet 0', vlan: 1, space: 0,
                  cidr: '10.20.0.0/16'}
              }
            ]
          }
        ];
        var expectedSpacesData = [
          { space: { id: 0, name: 'space 0' },
            rows: [
              { fabric: { id: 0, name: 'fabric 0' },
                vlan: { id: 1, name: 'vlan4', vid: 4, fabric: 0 },
                subnet: {
                  id: 0, name: 'subnet 0', vlan: 1, space: 0,
                  cidr: '10.20.0.0/16' } }
            ]
          },
          { space: { id: 1, name: 'space 1' }, rows: [ ]}
        ];
        controller = setupController(fabrics, spaces, vlans, subnets);
        spaces.push({id: 1, name: "space 1"});
        testUpdates(controller, fabrics, spaces, vlans, subnets,
                    expectedFabricsData, expectedSpacesData);

    });

    it("adding vlan updates lists", function() {
        var fabrics = [ { id: 0, name: "fabric 0" } ];
        var spaces = [ { id: 0, name: "space 0" } ];
        var vlans = [ { id: 1, name: "vlan4", vid: 4, fabric: 0 } ];
        var subnets = [
            { id:0, name:"subnet 0", vlan:1, space:0, cidr:"10.20.0.0/16" }
        ];

        var expectedFabricsData = [
          { fabric: { id: 0, name: 'fabric 0' },
            rows: [
              { vlan: { id: 1, name: 'vlan4', vid: 4, fabric: 0 },
                space: { id: 0, name: 'space 0' },
                subnet: {
                  id: 0, name: 'subnet 0', vlan: 1, space: 0,
                  cidr: '10.20.0.0/16'}
              },
              { vlan: { id: 2, name: 'vlan2', vid: 2, fabric: 0 },
                space: null, subnet: null }
            ]
          }
        ];
        var expectedSpacesData = [
          { space: { id: 0, name: 'space 0' },
            rows: [
              { fabric: { id: 0, name: 'fabric 0' },
                vlan: { id: 1, name: 'vlan4', vid: 4, fabric: 0 },
                subnet: {
                  id: 0, name: 'subnet 0', vlan: 1, space: 0,
                  cidr: '10.20.0.0/16' } }
            ]
          }
        ];
        controller = setupController(fabrics, spaces, vlans, subnets);
        vlans.push({id: 2, name: "vlan2", vid: 2, fabric: 0});
        testUpdates(controller, fabrics, spaces, vlans, subnets,
                    expectedFabricsData, expectedSpacesData);

    });

    it("adding subnet updates lists", function() {
        var fabrics = [ { id: 0, name: "fabric 0" } ];
        var spaces = [ { id: 0, name: "space 0" } ];
        var vlans = [ { id: 1, name: "vlan4", vid: 4, fabric: 0 } ];
        var subnets = [
            { id:0, name:"subnet 0", vlan:1, space:0, cidr:"10.20.0.0/16" }
        ];

        var expectedFabricsData = [
          { fabric: { id: 0, name: 'fabric 0' },
            rows: [
              { vlan: { id: 1, name: 'vlan4', vid: 4, fabric: 0 },
                space: { id: 0, name: 'space 0' },
                subnet: {
                  id: 0, name: 'subnet 0', vlan: 1, space: 0,
                  cidr: '10.20.0.0/16'}
              },
              { vlan: { id: 1, name: 'vlan4', vid: 4, fabric: 0 },
                space: { id: 0, name: 'space 0' },
                subnet: {
                  id: 1, name: 'subnet 1', vlan: 1, space: 0,
                  cidr: '10.99.34.0/24'}
              }
            ]
          }
        ];
        var expectedSpacesData = [
          { space: { id: 0, name: 'space 0' },
            rows: [
              { fabric: { id: 0, name: 'fabric 0' },
                vlan: { id: 1, name: 'vlan4', vid: 4, fabric: 0 },
                subnet: {
                  id: 0, name: 'subnet 0', vlan: 1, space: 0,
                  cidr: '10.20.0.0/16' } },
              { fabric: { id: 0, name: 'fabric 0' },
                vlan: { id: 1, name: 'vlan4', vid: 4, fabric: 0 },
                subnet: {
                  id: 1, name: 'subnet 1', vlan: 1, space: 0,
                  cidr: '10.99.34.0/24' } }
            ]
          }
        ];
        controller = setupController(fabrics, spaces, vlans, subnets);
        subnets.push(
            {id: 1, name: "subnet 1", vlan: 1, space: 0,
             cidr: "10.99.34.0/24"}
        );
        testUpdates(controller, fabrics, spaces, vlans, subnets,
                    expectedFabricsData, expectedSpacesData);

    });
});
