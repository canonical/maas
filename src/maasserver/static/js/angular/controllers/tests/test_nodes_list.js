/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for NodesListController.
 */

describe("NodesListController", function() {

    // Load the MAAS module.
    beforeEach(module("MAAS"));

    // Grab the needed angular pieces.
    var $controller, $rootScope, $scope, $q;
    beforeEach(inject(function($injector) {
        $controller = $injector.get("$controller");
        $rootScope = $injector.get("$rootScope");
        $scope = $rootScope.$new();
        $q = $injector.get("$q");
    }));

    // Load the NodesManager, DevicesManager, RegionConnection,
    // SearchService and mock the websocket connection.
    var NodesManager, DevicesManager, RegionConnection, SearchService;
    var webSocket;
    beforeEach(inject(function($injector) {
        NodesManager = $injector.get("NodesManager");
        DevicesManager = $injector.get("DevicesManager");
        RegionConnection = $injector.get("RegionConnection");
        SearchService = $injector.get("SearchService");

        // Mock buildSocket so an actual connection is not made.
        webSocket = new MockWebSocket();
        spyOn(RegionConnection, "buildSocket").and.returnValue(webSocket);
    }));

    // Makes the NodesListController
    function makeController() {
        return $controller("NodesListController", {
            $scope: $scope,
            $rootScope: $rootScope,
            NodesManager: NodesManager,
            DevicesManager: DevicesManager,
            RegionConnection: RegionConnection,
            SearchService: SearchService
        });
    }

    // Makes a fake node.
    function makeNode() {
        var node = {
            system_id: makeName("system_id"),
            $selected: false
        };
        NodesManager._items.push(node);
        return node;
    }
    // Makes a fake device.
    function makeDevice() {
        var device = {
            system_id: makeName("system_id"),
            $selected: false
        };
        DevicesManager._items.push(device);
        return device;
    }

    it("sets title and page on $rootScope", function() {
        var controller = makeController();
        expect($rootScope.title).toBe("Nodes");
        expect($rootScope.page).toBe("nodes");
    });

    it("sets initial values on $scope", function() {
        var controller = makeController();
        expect($scope.search).toBe("");
        expect($scope.searchValid).toBe(true);
        expect($scope.nodes).toBe(NodesManager.getItems());
        expect($scope.devices).toBe(DevicesManager.getItems());
        expect($scope.selectedNodes).toBe(NodesManager.getSelectedItems());
        expect($scope.filtered_nodes).toEqual([]);
        expect($scope.predicate).toBe("fqdn");
        expect($scope.allViewableChecked).toBe(false);
        expect($scope.metadata).toBe(NodesManager.getMetadata());
        expect($scope.filters).toBe(SearchService.emptyFilter);
        expect($scope.column).toBe("fqdn");
        expect($scope.actionOption).toBeNull();
        expect($scope.takeActionOptions).toEqual([]);
        expect($scope.actionError).toBe(false);
        expect($scope.addHardwareOption).toEqual({
            name: "hardware",
            title: "Add Hardware"
        });
        expect($scope.addHardwareOptions).toEqual([
            {
                name: "hardware",
                title: "Add Hardware"
            },
            {
                name: "chassis",
                title: "Add Chassis"
            }
        ]);
        expect($scope.addHardwareScope).toBeNull();
    });

    it("calls loadItems for nodes if not loaded", function(done) {
        spyOn(NodesManager, "loadItems").and.callFake(function() {
            done();
            return $q.defer().promise;
        });
        var controller = makeController();
    });

    it("calls loadItems for devices if not loaded", function(done) {
        spyOn(DevicesManager, "loadItems").and.callFake(function() {
            done();
            return $q.defer().promise;
        });
        var controller = makeController();
    });

    it("doesnt call loadItems for nodes if loaded", function() {
        spyOn(NodesManager, "isLoaded").and.returnValue("true");
        spyOn(NodesManager, "loadItems").and.returnValue($q.defer().promise);
        var controller = makeController();
        expect(NodesManager.loadItems).not.toHaveBeenCalled();
    });

    it("doesnt call loadItems for devices if loaded", function() {
        spyOn(DevicesManager, "isLoaded").and.returnValue("true");
        spyOn(DevicesManager, "loadItems").and.returnValue($q.defer().promise);
        var controller = makeController();
        expect(DevicesManager.loadItems).not.toHaveBeenCalled();
    });

    describe("toggleChecked", function() {

        var controller, node;
        beforeEach(function() {
            controller = makeController();
            node = makeNode();
            $scope.filtered_nodes = $scope.nodes;
        });

        it("selects node", function() {
            $scope.toggleChecked(node);
            expect(node.$selected).toBe(true);
        });

        it("deselects node", function() {
            NodesManager.selectItem(node.system_id);
            $scope.toggleChecked(node);
            expect(node.$selected).toBe(false);
        });

        it("sets allViewableChecked to true when all selected", function() {
            $scope.toggleChecked(node);
            expect($scope.allViewableChecked).toBe(true);
        });

        it("sets allViewableChecked to false when not all selected",
            function() {
                var node2 = makeNode();
                $scope.toggleChecked(node);
                expect($scope.allViewableChecked).toBe(false);
            });

        it("sets allViewableChecked to false when selected and deselected",
            function() {
                $scope.toggleChecked(node);
                $scope.toggleChecked(node);
                expect($scope.allViewableChecked).toBe(false);
            });

        it("resets search when in:selected and none selected", function() {
            $scope.search = "in:selected";
            $scope.toggleChecked(node);
            $scope.toggleChecked(node);
            expect($scope.search).toBe("");
        });

        it("ignores search when not in:selected and none selected", function() {
            $scope.search = "other";
            $scope.toggleChecked(node);
            $scope.toggleChecked(node);
            expect($scope.search).toBe("other");
        });

        it("clears action option when none selected", function() {
            $scope.actionOption = {};
            $scope.toggleChecked(node);
            $scope.toggleChecked(node);
            expect($scope.actionOption).toBeNull();
        });
    });

    describe("toggleCheckAll", function() {

        var controller, node1, node2;
        beforeEach(function() {
            controller = makeController();
            node1 = makeNode();
            node2 = makeNode();
            $scope.filtered_nodes = $scope.nodes;
        });

        it("selects all nodes", function() {
            $scope.toggleCheckAll();
            expect(node1.$selected).toBe(true);
            expect(node2.$selected).toBe(true);
        });

        it("deselects all nodes", function() {
            $scope.toggleCheckAll();
            $scope.toggleCheckAll();
            expect(node1.$selected).toBe(false);
            expect(node2.$selected).toBe(false);
        });

        it("resets search when in:selected and none selected", function() {
            $scope.search = "in:selected";
            $scope.toggleCheckAll();
            $scope.toggleCheckAll();
            expect($scope.search).toBe("");
        });

        it("ignores search when not in:selected and none selected", function() {
            $scope.search = "other";
            $scope.toggleCheckAll();
            $scope.toggleCheckAll();
            expect($scope.search).toBe("other");
        });

        it("clears action option when none selected", function() {
            $scope.actionOption = {};
            $scope.toggleCheckAll();
            $scope.toggleCheckAll();
            expect($scope.actionOption).toBeNull();
        });
    });

    describe("toggleFilter", function() {

        it("calls SearchService.toggleFilter", function() {
            var controller = makeController();
            spyOn(SearchService, "toggleFilter").and.returnValue(
                SearchService.emptyFilter);
            $scope.toggleFilter("hostname", "test");
            expect(SearchService.toggleFilter).toHaveBeenCalled();
        });

        it("sets $scope.filters", function() {
            var controller = makeController();
            var filters = { _: [], other: [] };
            spyOn(SearchService, "toggleFilter").and.returnValue(filters);
            $scope.toggleFilter("hostname", "test");
            expect($scope.filters).toBe(filters);
        });

        it("calls SearchService.filtersToString", function() {
            var controller = makeController();
            spyOn(SearchService, "filtersToString").and.returnValue("");
            $scope.toggleFilter("hostname", "test");
            expect(SearchService.filtersToString).toHaveBeenCalled();
        });

        it("sets $scope.search", function() {
            var controller = makeController();
            $scope.toggleFilter("hostname", "test");
            expect($scope.search).toBe("hostname:(test)");
        });
    });

    describe("isFilterActive", function() {

        it("returns true when active", function() {
            var controller = makeController();
            $scope.toggleFilter("hostname", "test");
            expect($scope.isFilterActive("hostname", "test")).toBe(true);
        });

        it("returns false when inactive", function() {
            var controller = makeController();
            $scope.toggleFilter("hostname", "test2");
            expect($scope.isFilterActive("hostname", "test")).toBe(false);
        });
    });

    describe("updateFilters", function() {

        it("updates filters and sets searchValid to true", function() {
            var controller = makeController();
            $scope.search = "test hostname:name";
            $scope.updateFilters();
            expect($scope.filters).toEqual({
                _: ["test"],
                hostname: ["name"]
            });
            expect($scope.searchValid).toBe(true);
        });

        it("updates sets filters empty and sets searchValid to false",
            function() {
                var controller = makeController();
                $scope.search = "test hostname:(name";
                $scope.updateFilters();
                expect($scope.filters).toBe(SearchService.emptyFilter);
                expect($scope.searchValid).toBe(false);
            });
    });

    describe("supportsAction", function() {

        it("returns true if actionOption is null", function() {
            var controller = makeController();
            var node = makeNode();
            node.actions = ["start", "stop"];
            expect($scope.supportsAction(node)).toBe(true);
        });

        it("returns true if actionOption in node.actions", function() {
            var controller = makeController();
            var node = makeNode();
            node.actions = ["start", "stop"];
            $scope.actionOption = { name: "start" };
            expect($scope.supportsAction(node)).toBe(true);
        });

        it("returns false if actionOption not in node.actions", function() {
            var controller = makeController();
            var node = makeNode();
            node.actions = ["start", "stop"];
            $scope.actionOption = { name: "deploy" };
            expect($scope.supportsAction(node)).toBe(false);
        });
    });

    describe("actionOptionSelected", function() {

        it("sets actionError to false", function() {
            var controller = makeController();
            $scope.actionError = true;
            $scope.actionOptionSelected();
            expect($scope.actionError).toBe(false);
        });

        it("sets actionError to true when selected node doesnt support action",
            function() {
                var controller = makeController();
                var node = makeNode();
                node.actions = ['start', 'stop'];
                $scope.actionOption = { name: 'deploy' };
                $scope.selectedNodes = [node];
                $scope.actionOptionSelected();
                expect($scope.actionError).toBe(true);
            });

        it("sets search to in:selected", function() {
            var controller = makeController();
            $scope.actionOptionSelected();
            expect($scope.search).toBe("in:selected");
        });

        it("calls hide on addHardwareScope", function() {
            var controller = makeController();
            $scope.addHardwareScope = {
                hide: jasmine.createSpy("hide")
            };
            $scope.actionOptionSelected();
            expect($scope.addHardwareScope.hide).toHaveBeenCalled();
        });
    });

    describe("actionCancel", function() {

        it("clears search if in:selected", function() {
            var controller = makeController();
            $scope.search = "in:selected";
            $scope.actionCancel();
            expect($scope.search).toBe("");
        });

        it("doesnt clear search if not in:selected", function() {
            var controller = makeController();
            $scope.search = "other";
            $scope.actionCancel();
            expect($scope.search).toBe("other");
        });

        it("sets actionOption to null", function() {
            var controller = makeController();
            $scope.actionOption = {};
            $scope.actionCancel();
            expect($scope.actionOption).toBeNull();
        });
    });

    describe("actionGo", function() {

        it("calls performAction for selected node", function() {
            spyOn(NodesManager, "performAction").and.returnValue(
                $q.defer().promise);
            var controller = makeController();
            var node = makeNode();
            $scope.actionOption = { name: "start" };
            $scope.selectedNodes = [node];
            $scope.actionGo();
            expect(NodesManager.performAction).toHaveBeenCalledWith(
                node, "start");
        });

        it("calls unselectItem after complete", function() {
            var defer = $q.defer();
            spyOn(NodesManager, "performAction").and.returnValue(
                defer.promise);
            spyOn(NodesManager, "unselectItem");
            var controller = makeController();
            var node = makeNode();
            $scope.actionOption = { name: "start" };
            $scope.selectedNodes = [node];
            $scope.actionGo();
            defer.resolve();
            $scope.$digest();
            expect(NodesManager.unselectItem).toHaveBeenCalled();
        });

        it("calls unselectItem after complete", function() {
            var defer = $q.defer();
            spyOn(NodesManager, "performAction").and.returnValue(
                defer.promise);
            spyOn(NodesManager, "unselectItem");
            var controller = makeController();
            var node = makeNode();
            $scope.actionOption = { name: "start" };
            $scope.selectedNodes = [node];
            $scope.actionGo();
            defer.resolve();
            $scope.$digest();
            expect(NodesManager.unselectItem).toHaveBeenCalled();
        });

        it("resets search when in:selected after complete", function() {
            var defer = $q.defer();
            spyOn(NodesManager, "performAction").and.returnValue(
                defer.promise);
            var node = makeNode();
            NodesManager._items = [node];
            NodesManager._selectedItems = [node];
            var controller = makeController();
            $scope.search = "in:selected";
            $scope.actionOption = { name: "start" };
            $scope.actionGo();
            defer.resolve();
            $scope.$digest();
            expect($scope.search).toBe("");
        });

        it("ignores search when not in:selected after complete", function() {
            var defer = $q.defer();
            spyOn(NodesManager, "performAction").and.returnValue(
                defer.promise);
            var node = makeNode();
            NodesManager._items = [node];
            NodesManager._selectedItems = [node];
            var controller = makeController();
            $scope.search = "other";
            $scope.actionOption = { name: "start" };
            $scope.actionGo();
            defer.resolve();
            $scope.$digest();
            expect($scope.search).toBe("other");
        });

        it("clears action option when complete", function() {
            var defer = $q.defer();
            spyOn(NodesManager, "performAction").and.returnValue(
                defer.promise);
            var node = makeNode();
            NodesManager._items = [node];
            NodesManager._selectedItems = [node];
            var controller = makeController();
            $scope.actionOption = { name: "start" };
            $scope.actionGo();
            defer.resolve();
            $scope.$digest();
            expect($scope.actionOption).toBeNull();
        });
    });

    describe("showAddHardware", function() {

        it("calls show in addHardwareScope", function() {
            var controller = makeController();
            $scope.addHardwareScope = {
                show: jasmine.createSpy("show")
            };
            $scope.addHardwareOption = {
                name: "hardware"
            };
            $scope.showAddHardware();
            expect($scope.addHardwareScope.show).toHaveBeenCalledWith(
                "hardware");
        });
    });
});
