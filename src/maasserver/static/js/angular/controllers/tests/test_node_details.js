/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for NodeDetailsController.
 */

describe("NodeDetailsController", function() {

    // Load the MAAS module.
    beforeEach(module("MAAS"));

    // Grab the needed angular pieces.
    var $controller, $rootScope, $location, $scope, $q;
    beforeEach(inject(function($injector) {
        $controller = $injector.get("$controller");
        $rootScope = $injector.get("$rootScope");
        $location = $injector.get("$location");
        $scope = $rootScope.$new();
        $q = $injector.get("$q");
    }));

    // Load the NodesManager, ClustersManager, ZonesManager, GeneralManager,
    // RegionConnection, ManagerHelperService, ErrorService and mock the
    // websocket connection.
    var NodesManager, DevicesManager, GeneralManager, RegionConnection;
    var ManagerHelperService, ErrorService, webSocket;
    beforeEach(inject(function($injector) {
        NodesManager = $injector.get("NodesManager");
        ClustersManager = $injector.get("ClustersManager");
        ZonesManager = $injector.get("ZonesManager");
        GeneralManager = $injector.get("GeneralManager");
        RegionConnection = $injector.get("RegionConnection");
        ManagerHelperService = $injector.get("ManagerHelperService");
        ErrorService = $injector.get("ErrorService");

        // Mock buildSocket so an actual connection is not made.
        webSocket = new MockWebSocket();
        spyOn(RegionConnection, "buildSocket").and.returnValue(webSocket);
    }));

    // Make a fake cluster.
    function makeCluster() {
        var cluster = {
            id: makeInteger(0, 10000),
            name: makeName("cluster"),
            uuid: makeName("uuid"),
            power_types: []
        };
        ClustersManager._items.push(cluster);
        return cluster;
    }

    // Make a fake zone.
    function makeZone() {
        var zone = {
            id: makeInteger(0, 10000),
            name: makeName("zone")
        };
        ZonesManager._items.push(zone);
        return zone;
    }

    // Make a fake node.
    function makeNode() {
        var cluster = makeCluster();
        var zone = makeZone();
        var node = {
            system_id: makeName("system_id"),
            fqdn: makeName("fqdn"),
            actions: [],
            architecture: "amd64/generic",
            nodegroup: angular.copy(cluster),
            zone: angular.copy(zone),
            power_type: "",
            power_parameters: null
        };
        NodesManager._items.push(node);
        return node;
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
    function makeController(loadManagersDefer) {
        var loadManagers = spyOn(ManagerHelperService, "loadManagers");
        if(angular.isObject(loadManagersDefer)) {
            loadManagers.and.returnValue(loadManagersDefer.promise);
        } else {
            loadManagers.and.returnValue($q.defer().promise);
        }

        // Start the connection so a valid websocket is created in the
        // RegionConnection.
        RegionConnection.connect("");

        return $controller("NodeDetailsController", {
            $scope: $scope,
            $rootScope: $rootScope,
            $routeParams: $routeParams,
            $location: $location,
            NodesManager: NodesManager,
            ClustersManager: ClustersManager,
            ZonesManager: ZonesManager,
            GeneralManager: GeneralManager,
            ManagerHelperService: ManagerHelperService,
            ErrorService: ErrorService
        });
    }

    it("sets title to loading and page to nodes", function() {
        var controller = makeController();
        expect($rootScope.title).toBe("Loading...");
        expect($rootScope.page).toBe("nodes");
    });

    it("sets the initial $scope values", function() {
        var controller = makeController();
        expect($scope.loaded).toBe(false);
        expect($scope.node).toBeNull();
        expect($scope.actionOption).toBeNull();
        expect($scope.allActionOptions).toBe(
            GeneralManager.getData("actions"));
        expect($scope.availableActionOptions).toEqual([]);
        expect($scope.osinfo).toBe(GeneralManager.getData("osinfo"));
    });

    it("sets initial values for summary section", function() {
        var controller = makeController();
        expect($scope.summary).toEqual({
            editing: false,
            cluster: {
                selected: null,
                options: ClustersManager.getItems()
            },
            architecture: {
                selected: null,
                options: GeneralManager.getData("architectures")
            },
            zone: {
                selected: null,
                options: ZonesManager.getItems()
            }
        });
        expect($scope.summary.cluster.options).toBe(
            ClustersManager.getItems());
        expect($scope.summary.architecture.options).toBe(
            GeneralManager.getData("architectures"));
        expect($scope.summary.zone.options).toBe(
            ZonesManager.getItems());
    });

    it("sets initial values for power section", function() {
        var controller = makeController();
        expect($scope.power).toEqual({
            editing: false,
            type: null,
            parameters: {}
        });
    });

    it("calls loadManagers with all needed managers", function() {
        var controller = makeController();
        expect(ManagerHelperService.loadManagers).toHaveBeenCalledWith([
            NodesManager, ClustersManager, ZonesManager, GeneralManager]);
    });

    it("calls setActiveItem onces managers loaded", function() {
        spyOn(NodesManager, "setActiveItem").and.returnValue(
            $q.defer().promise);
        var defer = $q.defer();
        var controller = makeController(defer);

        defer.resolve();
        $rootScope.$digest();

        expect(NodesManager.setActiveItem).toHaveBeenCalledWith(
            node.system_id);
    });

    it("sets node and loaded once setActiveItem resolves", function() {
        var setActiveDefer = $q.defer();
        spyOn(NodesManager, "setActiveItem").and.returnValue(
            setActiveDefer.promise);
        var defer = $q.defer();
        var controller = makeController(defer);

        defer.resolve();
        $rootScope.$digest();
        setActiveDefer.resolve(node);
        $rootScope.$digest();

        expect($scope.node).toBe(node);
        expect($scope.loaded).toBe(true);
    });

    it("title is updated once setActiveItem resolves", function() {
        var setActiveDefer = $q.defer();
        spyOn(NodesManager, "setActiveItem").and.returnValue(
            setActiveDefer.promise);
        var defer = $q.defer();
        var controller = makeController(defer);

        defer.resolve();
        $rootScope.$digest();
        setActiveDefer.resolve(node);
        $rootScope.$digest();

        expect($rootScope.title).toBe(node.fqdn);
    });

    it("summary section is updated once setActiveItem resolves", function() {
        var setActiveDefer = $q.defer();
        spyOn(NodesManager, "setActiveItem").and.returnValue(
            setActiveDefer.promise);
        var defer = $q.defer();
        var controller = makeController(defer);

        defer.resolve();
        $rootScope.$digest();
        setActiveDefer.resolve(node);
        $rootScope.$digest();

        expect($scope.summary.cluster.selected).toBe(
            ClustersManager.getItemFromList(node.nodegroup.id));
        expect($scope.summary.zone.selected).toBe(
            ZonesManager.getItemFromList(node.zone.id));
        expect($scope.summary.architecture.selected).toBe(node.architecture);
    });

    it("power section is updated once setActiveItem resolves", function() {
        var power_types = [
            {
                name: makeName("power")
            },
            {
                name: makeName("power")
            },
            {
                name: makeName("power")
            }
        ];
        var cluster = ClustersManager.getItemFromList(node.nodegroup.id);
        cluster.power_types = power_types;
        node.power_type = power_types[0].name;
        node.power_parameters = {
            data: makeName("data")
        };

        var setActiveDefer = $q.defer();
        spyOn(NodesManager, "setActiveItem").and.returnValue(
            setActiveDefer.promise);
        var defer = $q.defer();
        var controller = makeController(defer);

        defer.resolve();
        $rootScope.$digest();
        setActiveDefer.resolve(node);
        $rootScope.$digest();

        expect($scope.power.types).toBe(power_types);
        expect($scope.power.type).toBe(power_types[0]);
        expect($scope.power.parameters).toEqual(node.power_parameters);
        expect($scope.power.parameters).not.toBe(node.power_parameters);
    });

    it("starts watching once setActiveItem resolves", function() {
        var setActiveDefer = $q.defer();
        spyOn(NodesManager, "setActiveItem").and.returnValue(
            setActiveDefer.promise);
        var defer = $q.defer();
        var controller = makeController(defer);

        spyOn($scope, "$watch");
        spyOn($scope, "$watchCollection");

        defer.resolve();
        $rootScope.$digest();
        setActiveDefer.resolve(node);
        $rootScope.$digest();

        var watches = [];
        var i, calls = $scope.$watch.calls.allArgs();
        for(i = 0; i < calls.length; i++) {
            watches.push(calls[i][0]);
        }

        var watchCollections = [];
        calls = $scope.$watchCollection.calls.allArgs();
        for(i = 0; i < calls.length; i++) {
            watchCollections.push(calls[i][0]);
        }

        expect(watches).toEqual([
            "node.fqdn",
            "node.actions",
            "node.nodegroup.id",
            "node.architecture",
            "node.zone.id",
            "node.power_type",
            "node.power_parameters"
        ]);
        expect(watchCollections).toEqual([
            $scope.summary.cluster.options,
            $scope.summary.architecture.options,
            $scope.summary.zone.options
        ]);
    });

    it("calls startPolling onces managers loaded", function() {
        spyOn(NodesManager, "setActiveItem").and.returnValue(
            $q.defer().promise);
        spyOn(GeneralManager, "startPolling");
        var defer = $q.defer();
        var controller = makeController(defer);

        defer.resolve();
        $rootScope.$digest();

        expect(GeneralManager.startPolling.calls.allArgs()).toEqual(
            [["architectures"], ["osinfo"]]);
    });

    it("calls stopPolling when the $scope is destroyed", function() {
        spyOn(GeneralManager, "stopPolling");
        var controller = makeController();
        $scope.$destroy();
        expect(GeneralManager.stopPolling.calls.allArgs()).toEqual(
            [["architectures"], ["osinfo"]]);
    });

    describe("getPowerStateText", function() {

        it("returns blank if no node", function() {
            var controller = makeController();
            expect($scope.getPowerStateText()).toBe("");
        });

        it("returns blank if power_state is unknown", function() {
            var controller = makeController();
            $scope.node = node;
            node.power_state = "unknown";
            expect($scope.getPowerStateText()).toBe("");
        });

        it("returns power_state prefixed with Power ", function() {
            var controller = makeController();
            var state = makeName("state");
            $scope.node = node;
            node.power_state = state;
            expect($scope.getPowerStateText()).toBe("Power " + state);
        });
    });

    describe("getOSText", function() {

        it("returns blank if no node", function() {
            var controller = makeController();
            expect($scope.getOSText()).toBe("");
        });

        it("returns osystem/series if no osinfo", function() {
            var controller = makeController();
            var osystem = makeName("osystem");
            var series = makeName("distro_series");
            var os_series = osystem + "/" + series;
            $scope.node = node;
            node.osystem = osystem;
            node.distro_series = series;
            expect($scope.getOSText()).toBe(os_series);
        });

        it("returns release title if osinfo", function() {
            var controller = makeController();
            var osystem = makeName("osystem");
            var series = makeName("distro_series");
            var os_series = osystem + "/" + series;
            var title = makeName("title");
            $scope.node = node;
            $scope.osinfo = {
                releases: [
                    [os_series, title]
                ]
            };
            node.osystem = osystem;
            node.distro_series = series;
            expect($scope.getOSText()).toBe(title);
        });

        it("returns osystem/series not in osinfo", function() {
            var controller = makeController();
            var osystem = makeName("osystem");
            var series = makeName("distro_series");
            var os_series = osystem + "/" + series;
            $scope.node = node;
            $scope.osinfo = {
                releases: [
                    [makeName("release"), makeName("title")]
                ]
            };
            node.osystem = osystem;
            node.distro_series = series;
            expect($scope.getOSText()).toBe(os_series);
        });
    });

    describe("isDeployError", function() {

        it("returns true if deploy action and missing osinfo", function() {
            var controller = makeController();
            $scope.actionOption = {
                name: "deploy"
            };
            expect($scope.isDeployError()).toBe(true);
        });

        it("returns true if deploy action and no osystems", function() {
            var controller = makeController();
            $scope.actionOption = {
                name: "deploy"
            };
            $scope.osinfo = {
                osystems: []
            };
            expect($scope.isDeployError()).toBe(true);
        });

        it("returns false if actionOption null", function() {
            var controller = makeController();
            expect($scope.isDeployError()).toBe(false);
        });

        it("returns false if not deploy action", function() {
            var controller = makeController();
            $scope.actionOption = {
                name: "release"
            };
            expect($scope.isDeployError()).toBe(false);
        });

        it("returns false if osystems present", function() {
            var controller = makeController();
            $scope.actionOption = {
                name: "deploy"
            };
            $scope.osinfo = {
                osystems: [makeName("os")]
            };
            expect($scope.isDeployError()).toBe(false);
        });
    });

    describe("actionCancel", function() {

        it("sets actionOption to null", function() {
            var controller = makeController();
            $scope.actionOption = {};
            $scope.actionCancel();
            expect($scope.actionOption).toBeNull();
        });
    });

    describe("actionGo", function() {

        it("calls performAction with node and actionOption name", function() {
            var controller = makeController();
            spyOn(NodesManager, "performAction").and.returnValue(
                $q.defer().promise);
            $scope.node = node;
            $scope.actionOption = {
                name: "deploy"
            };
            $scope.actionGo();
            expect(NodesManager.performAction).toHaveBeenCalledWith(
                node, "deploy");
        });

        it("clears actionOption on resolve", function() {
            var controller = makeController();
            var defer = $q.defer();
            spyOn(NodesManager, "performAction").and.returnValue(
                defer.promise);
            $scope.node = node;
            $scope.actionOption = {
                name: "deploy"
            };
            $scope.actionGo();
            defer.resolve();
            $rootScope.$digest();
            expect($scope.actionOption).toBeNull();
        });

        it("changes path to node listing on delete", function() {
            var controller = makeController();
            var defer = $q.defer();
            spyOn(NodesManager, "performAction").and.returnValue(
                defer.promise);
            spyOn($location, "path");
            $scope.node = node;
            $scope.actionOption = {
                name: "delete"
            };
            $scope.actionGo();
            defer.resolve();
            $rootScope.$digest();
            expect($location.path).toHaveBeenCalledWith("/nodes");
        });
    });

    describe("editSummary", function() {

        it("sets editing to true for summary section", function() {
            var controller = makeController();
            $scope.summary.editing = false;
            $scope.editSummary();
            expect($scope.summary.editing).toBe(true);
        });
    });

    describe("cancelEditSummary", function() {

        it("sets editing to false for summary section", function() {
            var controller = makeController();
            $scope.node = node;
            $scope.summary.editing = true;
            $scope.cancelEditSummary();
            expect($scope.summary.editing).toBe(false);
        });

        it("calls updateSummary", function() {
            var controller = makeController();
            $scope.node = node;
            $scope.summary.editing = true;
            $scope.cancelEditSummary();

            // Since updateSummary is private in the controller, check
            // that the selected cluster is set, this will prove that
            // the method was called.
            expect($scope.summary.cluster.selected).toBe(
                ClustersManager.getItemFromList(node.nodegroup.id));
        });
    });

    describe("saveEditSummary", function() {

        it("sets editing to false for summary section", function() {
            var controller = makeController();
            $scope.node = node;
            $scope.summary.editing = true;
            $scope.saveEditSummary();
            expect($scope.summary.editing).toBe(false);
        });

        it("calls updateSummary", function() {
            var controller = makeController();
            $scope.node = node;
            $scope.summary.editing = true;
            $scope.saveEditSummary();

            // Since updateSummary is private in the controller, check
            // that the selected cluster is set, this will prove that
            // the method was called.
            expect($scope.summary.cluster.selected).toBe(
                ClustersManager.getItemFromList(node.nodegroup.id));
        });
    });

    describe("editPower", function() {

        it("sets editing to true for power section", function() {
            var controller = makeController();
            $scope.power.editing = false;
            $scope.editPower();
            expect($scope.power.editing).toBe(true);
        });
    });

    describe("cancelEditPower", function() {

        it("sets editing to false for power section", function() {
            var controller = makeController();
            $scope.node = node;
            $scope.power.editing = true;
            $scope.cancelEditPower();
            expect($scope.power.editing).toBe(false);
        });

        it("calls updatePower", function() {
            var controller = makeController();
            $scope.node = node;
            $scope.power.editing = true;

            // Set power_types so we can check that updatePower is called.
            var cluster = ClustersManager.getItemFromList(
                node.nodegroup.id);
            cluster.power_types = [
                {
                    type: makeName("power")
                }
            ];

            $scope.cancelEditPower();

            // Since updatePower is private in the controller, check
            // that the power types are set from the cluster, this will
            // prove that the method was called.
            expect($scope.power.types).toEqual(cluster.power_types);
        });
    });

    describe("saveEditPower", function() {

        it("sets editing to false for power section", function() {
            var controller = makeController();
            $scope.node = node;
            $scope.power.editing = true;
            $scope.saveEditPower();
            expect($scope.power.editing).toBe(false);
        });

        it("calls updatePower", function() {
            var controller = makeController();
            $scope.node = node;
            $scope.power.editing = true;

            // Set power_types so we can check that updatePower is called.
            var cluster = ClustersManager.getItemFromList(
                node.nodegroup.id);
            cluster.power_types = [
                {
                    type: makeName("power")
                }
            ];

            $scope.saveEditPower();

            // Since updatePower is private in the controller, check
            // that the power types are set from the cluster, this will
            // prove that the method was called.
            expect($scope.power.types).toEqual(cluster.power_types);
        });
    });
});
