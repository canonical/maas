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

    // Load the NodesManager, RegionConnection, SearchService and mock the
    // websocket connection.
    var NodesManager, RegionConnection, SearchService, webSocket;
    beforeEach(inject(function($injector) {
        NodesManager = $injector.get("NodesManager");
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
        NodesManager._nodes.push(node);
        return node;
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
        expect($scope.nodes).toBe(NodesManager.getNodes());
        expect($scope.selectedNodes).toBe(NodesManager.getSelectedNodes());
        expect($scope.filtered_nodes).toEqual([]);
        expect($scope.predicate).toBe("fqdn");
        expect($scope.allViewableChecked).toBe(false);
        expect($scope.metadata).toBe(NodesManager.getMetadata());
        expect($scope.filters).toBe(SearchService.emptyFilter);
    });

    it("calls loadNodes if not loaded", function(done) {
        spyOn(NodesManager, "loadNodes").and.callFake(function() {
            done();
            return $q.defer().promise;
        });
        var controller = makeController();
    });

    it("doesnt call loadNodes if loaded", function() {
        spyOn(NodesManager, "isLoaded").and.returnValue("true");
        spyOn(NodesManager, "loadNodes").and.returnValue($q.defer().promise);
        var controller = makeController();
        expect(NodesManager.loadNodes).not.toHaveBeenCalled();
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
            NodesManager.selectNode(node.system_id);
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
});
