/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for SubentsListController.
 */

describe("NetworksListController", function() {

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

    // Load the managers and services.
    var SubnetsManager, FabricsManager, SpacesManager, VLANsManager;
    var ManagerHelperService, RegionConnection;
    beforeEach(inject(function($injector) {
        SubnetsManager = $injector.get("SubnetsManager");
        FabricsManager = $injector.get("FabricsManager");
        SpacesManager = $injector.get("SpacesManager");
        VLANsManager = $injector.get("VLANsManager");
        ManagerHelperService = $injector.get("ManagerHelperService");
    }));

    // Makes the SubnetsListController
    function makeController(loadManagersDefer, defaultConnectDefer) {
        var loadManagers = spyOn(ManagerHelperService, "loadManagers");
        if(angular.isObject(loadManagersDefer)) {
            loadManagers.and.returnValue(loadManagersDefer.promise);
        } else {
            loadManagers.and.returnValue($q.defer().promise);
        }

        // Create the controller.
        var controller = $controller("NetworksListController", {
            $scope: $scope,
            $rootScope: $rootScope,
            $routeParams: $routeParams,
            $location: $location,
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
        expect($rootScope.title).toBe("Networks");
        expect($rootScope.page).toBe("networks");
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

    doUpdates = function(controller, fabrics, spaces, vlans, subnets) {
        $scope.fabrics = fabrics;
        FabricsManager._items = fabrics;
        $scope.spaces = spaces;
        SpacesManager._items = spaces;
        $scope.vlans = vlans;
        VLANsManager._items = vlans;
        $scope.subnets = subnets;
        SubnetsManager._items = subnets;
        $rootScope.$digest();
    };

    it("selects fabric groupBy by default", function() {
        var controller = setupController([], [], [], []);
        expect($scope.groupBy).toBe("fabric");
    });

    it("selects space groupBy with search string", function() {
        $location.search('by', 'space');
        var controller = setupController([], [], [], []);
        expect($scope.groupBy).toBe("space");
    });

    it("updates groupBy when location changes", function() {
        var controller = setupController([], [], [], []);
        $location.search('by', 'space');
        $rootScope.$broadcast('$routeUpdate');
        expect($scope.groupBy).toBe("space");
    });

    it("updates location when groupBy changes", function() {
        var controller = setupController([], [], [], []);
        expect($location.search()).toEqual({by: 'fabric'});
        $scope.groupBy = "space";
        $scope.updateGroupBy();
        expect($location.search()).toEqual({by: 'space'});
    });

    it("initial update populates fabrics", function() {
        $location.search('by', 'fabric');
        var fabrics = [ { id: 0, name: "fabric 0" } ];
        var spaces = [ { id: 0, name: "space 0" } ];
        var vlans = [ { id: 1, name: "vlan4", vid: 4, fabric: 0 } ];
        var subnets = [
            { id:0, name:"subnet 0", vlan:1, space:0, cidr:"10.20.0.0/16" }
        ];
        var controller = setupController(fabrics, spaces, vlans, subnets);
        var rows = $scope.group.fabrics.rows;
        expect(rows.length).toBe(1);
        expect($scope.group.spaces.rows).toBe(undefined);
        expect(rows[0].subnet).toBe(subnets[0]);
        expect(rows[0].subnet_name).toBe("10.20.0.0/16 (subnet 0)");
        expect(rows[0].space).toBe(spaces[0]);
        expect(rows[0].fabric).toBe(fabrics[0]);
        expect(rows[0].fabric_name).toBe("fabric 0");
        expect(rows[0].vlan).toBe(vlans[0]);
        expect(rows[0].vlan_name).toBe("4 (vlan4)");
    });

    it("initial update populates spaces", function() {
        $location.search('by', 'space');
        var fabrics = [ { id: 0, name: "fabric 0" } ];
        var spaces = [ { id: 0, name: "space 0" } ];
        var vlans = [ { id: 1, name: "vlan4", vid: 4, fabric: 0 } ];
        var subnets = [
            { id:0, name:"subnet 0", vlan:1, space:0, cidr:"10.20.0.0/16" }
        ];
        var controller = setupController(fabrics, spaces, vlans, subnets);
        var rows = $scope.group.spaces.rows;
        expect(rows.length).toBe(1);
        expect($scope.group.fabrics.rows).toBe(undefined);
        expect(rows[0].subnet).toBe(subnets[0]);
        expect(rows[0].subnet_name).toBe("10.20.0.0/16 (subnet 0)");
        expect(rows[0].space).toBe(spaces[0]);
        expect(rows[0].space_name).toBe("space 0");
        expect(rows[0].fabric).toBe(fabrics[0]);
        expect(rows[0].vlan).toBe(vlans[0]);
        expect(rows[0].vlan_name).toBe("4 (vlan4)");
    });

    it("adding fabric updates lists", function() {
        var fabrics = [ { id: 0, name: "fabric 0" } ];
        var spaces = [ { id: 0, name: "space 0" } ];
        var vlans = [ { id: 1, name: "vlan4", vid: 4, fabric: 0 } ];
        var subnets = [
            { id:0, name:"subnet 0", vlan:1, space:0, cidr:"10.20.0.0/16" }
        ];

        var controller = setupController(fabrics, spaces, vlans, subnets);
        expect($scope.group.fabrics.rows.length).toBe(1);
        fabrics.push({id: 1, name: "fabric 1"});
        vlans.push({id: 2, vid:0, fabric: 1});
        doUpdates(controller, fabrics, spaces, vlans, subnets);
        expect($scope.group.fabrics.rows.length).toBe(2);
        $scope.groupBy = "space";
        $scope.updateGroupBy();
        // We can't show a new fabric+vlan that doesn't have a subnet+space
        // on the "spaces" group by, so we need more data first.
        expect($scope.group.spaces.rows.length).toBe(1);
        subnets.push(
            {id:1, name:"subnet 1", vlan: 2, space: 0, cidr:"10.21.0.0/16"});
        spaces.push({});
        doUpdates(controller, fabrics, spaces, vlans, subnets);
        expect($scope.group.spaces.rows.length).toBe(2);
    });

    it("adding space updates lists", function() {
        var fabrics = [ { id: 0, name: "fabric 0" } ];
        var spaces = [ { id: 0, name: "space 0" } ];
        var vlans = [ { id: 1, name: "vlan4", vid: 4, fabric: 0 } ];
        var subnets = [
            {id:0, name:"subnet 0", vlan:1, space:0, cidr:"10.20.0.0/16"}
        ];
        var controller = setupController(fabrics, spaces, vlans, subnets);
        expect($scope.group.fabrics.rows.length).toBe(1);
        spaces.push({id: 1, name: "space 1"});
        subnets.push(
            {id:1, name:"subnet 1", vlan:1, space:1, cidr:"10.20.0.0/16"});
        doUpdates(controller, fabrics, spaces, vlans, subnets);
        expect($scope.group.fabrics.rows.length).toBe(2);
        $scope.groupBy = "space";
        $scope.updateGroupBy();
        // Second space should have a blank name
        expect($scope.group.spaces.rows.length).toBe(2);
        // Move 2nd subnet into first space and check that the name is no
        // longer shown.
        subnets[1].space = 0;
        $scope.updateGroupBy();
        expect($scope.group.spaces.rows[1].space_name).toBe("");
    });

    it("adding vlan updates lists appropriately", function() {
        var fabrics = [ { id: 0, name: "fabric 0" } ];
        var spaces = [ { id: 0, name: "space 0" } ];
        var vlans = [ { id: 1, name: "vlan4", vid: 4, fabric: 0 } ];
        var subnets = [
            { id:0, name:"subnet 0", vlan:1, space:0, cidr:"10.20.0.0/16" }
        ];
        var controller = setupController(fabrics, spaces, vlans, subnets);
        expect($scope.group.fabrics.rows.length).toBe(1);
        vlans.push({id: 2, name: "vlan2", vid: 2, fabric: 0});
        doUpdates(controller, fabrics, spaces, vlans, subnets);
        // Fabric should have blank name
        expect($scope.group.fabrics.rows[1].fabric_name).toBe("");
        expect($scope.group.fabrics.rows.length).toBe(2);
        $scope.groupBy = "space";
        $scope.updateGroupBy();
        // Orphaned VLANs should not be shown in the spaces view, since there
        // is not path from the space to that VLAN.
        expect($scope.group.spaces.rows.length).toBe(1);
    });

    it("adding subnet updates lists", function() {
        var fabrics = [ { id: 0, name: "fabric 0" } ];
        var spaces = [ { id: 0, name: "space 0" } ];
        var vlans = [ { id: 1, name: "vlan4", vid: 4, fabric: 0 } ];
        var subnets = [
            { id:0, name:"subnet 0", vlan:1, space:0, cidr:"10.20.0.0/16" }
        ];
        var controller = setupController(fabrics, spaces, vlans, subnets);
        expect($scope.group.fabrics.rows.length).toBe(1);
        subnets.push(
            {id: 1, name: "subnet 1", vlan: 1, space: 0,
             cidr: "10.99.34.0/24"}
        );
        doUpdates(controller, fabrics, spaces, vlans, subnets);
        expect($scope.group.fabrics.rows.length).toBe(2);
        // Test that redundant fabric and VLAN names are suppressed
        expect($scope.group.fabrics.rows[1].fabric_name).toBe("");
        expect($scope.group.fabrics.rows[1].vlan_name).toBe("");
        $scope.groupBy = "space";
        $scope.updateGroupBy();
        expect($scope.group.spaces.rows.length).toBe(2);
    });
});
