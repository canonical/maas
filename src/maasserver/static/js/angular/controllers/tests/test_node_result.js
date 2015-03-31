/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for NodeResultController.
 */

describe("NodeResultController", function() {

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

    // Load the required dependencies for the NodeResultController and
    // mock the websocket connection.
    var NodesManager, RegionConnection, ManagerHelperService, ErrorService;
    var webSocket;
    beforeEach(inject(function($injector) {
        NodesManager = $injector.get("NodesManager");
        RegionConnection = $injector.get("RegionConnection");
        ManagerHelperService = $injector.get("ManagerHelperService");
        ErrorService = $injector.get("ErrorService");

        // Mock buildSocket so an actual connection is not made.
        webSocket = new MockWebSocket();
        spyOn(RegionConnection, "buildSocket").and.returnValue(webSocket);
    }));

    // Make a fake commissioning result.
    function makeCommissioningResult() {
        return {
            name: makeName("name"),
            data: makeName("data")
        };
    }

    // Make a fake node.
    function makeNode() {
        var node = {
            system_id: makeName("system_id"),
            fqdn: makeName("fqdn"),
            commissioning_results: [
                makeCommissioningResult(),
                makeCommissioningResult(),
                makeCommissioningResult()
            ]
        };
        NodesManager._items.push(node);
        return node;
    }

    // Create the node that will be used and set the routeParams.
    var node, $routeParams;
    beforeEach(function() {
        node = makeNode();
        $routeParams = {
            system_id: node.system_id,
            filename: node.commissioning_results[0].name
        };
    });

    // Makes the NodeResultController
    function makeController(loadManagerDefer) {
        var loadManager = spyOn(ManagerHelperService, "loadManager");
        if(angular.isObject(loadManagerDefer)) {
            loadManager.and.returnValue(loadManagerDefer.promise);
        } else {
            loadManager.and.returnValue($q.defer().promise);
        }

        // Start the connection so a valid websocket is created in the
        // RegionConnection.
        RegionConnection.connect("");

        return $controller("NodeResultController", {
            $scope: $scope,
            $rootScope: $rootScope,
            $routeParams: $routeParams,
            $location: $location,
            NodesManager: NodesManager,
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
        expect($scope.filename).toBe($routeParams.filename);
    });

    it("calls loadManager with NodesManager", function() {
        var controller = makeController();
        expect(ManagerHelperService.loadManager).toHaveBeenCalledWith(
            NodesManager);
    });

    it("doesnt call setActiveItem if node already loaded", function() {
        var defer = $q.defer();
        var controller = makeController(defer);
        NodesManager._activeItem = node;
        spyOn(NodesManager, "setActiveItem");

        defer.resolve();
        $rootScope.$digest();

        expect($scope.node).toBe(node);
        expect($scope.loaded).toBe(true);
        expect(NodesManager.setActiveItem).not.toHaveBeenCalled();
    });

    it("calls setActiveItem if node not loaded", function() {
        var defer = $q.defer();
        var controller = makeController(defer);
        var setActiveDefer = $q.defer();
        spyOn(NodesManager, "setActiveItem").and.returnValue(
            setActiveDefer.promise);

        defer.resolve();
        $rootScope.$digest();

        setActiveDefer.resolve(node);
        $rootScope.$digest();

        expect($scope.node).toBe(node);
        expect($scope.loaded).toBe(true);
        expect(NodesManager.setActiveItem).toHaveBeenCalledWith(
            node.system_id);
    });

    it("calls raiseError if setActiveItem is rejected", function() {
        var defer = $q.defer();
        var controller = makeController(defer);
        var setActiveDefer = $q.defer();
        spyOn(NodesManager, "setActiveItem").and.returnValue(
            setActiveDefer.promise);
        spyOn(ErrorService, "raiseError");

        defer.resolve();
        $rootScope.$digest();

        var error = makeName("error");
        setActiveDefer.reject(error);
        $rootScope.$digest();

        expect(ErrorService.raiseError).toHaveBeenCalledWith(error);
    });

    it("watches node.fqdn updates $rootScope.title", function() {
        var defer = $q.defer();
        var controller = makeController(defer);
        NodesManager._activeItem = node;

        defer.resolve();
        $rootScope.$digest();

        node.fqdn = makeName("fqdn");
        $rootScope.$digest();
        expect($rootScope.title).toBe(
            node.fqdn + " - " + $routeParams.filename);
    });

    describe("getResultData", function() {

        it("returns empty string if node not loaded", function() {
            var controller = makeController();
            expect($scope.getResultData()).toBe("");
        });

        it("returns data from result with newline prepended", function() {
            var controller = makeController();
            $scope.node = node;
            expect($scope.getResultData()).toBe(
                "\n" + node.commissioning_results[0].data);
        });

        it("returns 'Empty file` for empty data from result", function() {
            var controller = makeController();
            $scope.node = node;
            node.commissioning_results[0].data = "";
            expect($scope.getResultData()).toBe(
                "\nEmpty file");
        });

        it("calls $location.path back to node details if result missing",
            function() {
                $routeParams.filename = makeName("wrong_name");
                var controller = makeController();
                $scope.node = node;
                spyOn($location, "path");
                expect($scope.getResultData()).toBe("");
                expect($location.path).toHaveBeenCalledWith(
                    "/node/" + node.system_id);
            });
    });
});
