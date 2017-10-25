/* Copyright 2017 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for NodeResultsController
 */

describe("NodeResultsController", function() {

    // Load the MAAS module.
    beforeEach(module("MAAS"));

    // Grab the needed angular pieces.
    var $controller, $rootScope, $scope, $q;
    beforeEach(inject(function($injector) {
        $controller = $injector.get("$controller");
        $rootScope = $injector.get("$rootScope");
        $scope = $rootScope.$new();
        $scope.section = {
            area: pickItem(["testing", "commissioning", "summary"])
        };
        $q = $injector.get("$q");
    }));

    // Load the required dependencies for the NodeResultsController and
    // mock the websocket connection.
    var MachinesManager, ControllersManager, NodeResultsManagerFactory;
    var ManagerHelperService, ErrorService, RegionConnection, webSocket;
    beforeEach(inject(function($injector) {
        MachinesManager = $injector.get("MachinesManager");
        ControllersManager = $injector.get("ControllersManager");
        NodeResultsManagerFactory = $injector.get("NodeResultsManagerFactory");
        ManagerHelperService = $injector.get("ManagerHelperService");
        ErrorService = $injector.get("ErrorService");
        RegionConnection = $injector.get("RegionConnection");

        // Mock buildSocket so an actual connection is not made.
        webSocket = new MockWebSocket();
        spyOn(RegionConnection, "buildSocket").and.returnValue(webSocket);
    }));

    // Make a fake node.
    function makeNode() {
        var node = {
            system_id: makeName("system_id"),
            disks: []
        };
        MachinesManager._items.push(node);
        ControllersManager._items.push(node);
        return node;
    }

    // Makes the NodeResultsController
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

        return $controller("NodeResultsController", {
            $scope: $scope,
            $routeParams: $routeParams,
            MachinesManager: MachinesManager,
            ControllersManager: ControllersManager,
            NodeResultsManagerFactory: NodeResultsManagerFactory,
            ManagerHelperService: ManagerHelperService,
            ErrorService: ErrorService
        });
    }

    // Create the node that will be used and set the routeParams.
    var node, $routeParams;
    beforeEach(function() {
        node = makeNode();
        $routeParams = {
            system_id: node.system_id
        };
    });

    it("sets the initial $scope values", function() {
        var controller = makeController();
        expect($scope.commissioning_results).toBeNull();
        expect($scope.testing_results).toBeNull();
        expect($scope.installation_results).toBeNull();
        expect($scope.results).toBeNull();
        expect($scope.loaded).toBe(false);
        expect($scope.resultsLoaded).toBe(false);
        expect($scope.node).toBeNull();
        expect($scope.nodesManager).toBe(MachinesManager);
    });

    it("sets the initial $scope values when controller", function() {
        $routeParams.type = 'controller';
        var controller = makeController();
        expect($scope.commissioning_results).toBeNull();
        expect($scope.testing_results).toBeNull();
        expect($scope.installation_results).toBeNull();
        expect($scope.results).toBeNull();
        expect($scope.loaded).toBe(false);
        expect($scope.resultsLoaded).toBe(false);
        expect($scope.node).toBeNull();
        expect($scope.nodesManager).toBe(ControllersManager);
    });

    it("calls loadManager with MachinesManager", function() {
        var controller = makeController();
        expect(ManagerHelperService.loadManager).toHaveBeenCalledWith(
            $scope, MachinesManager);
    });

    it("doesnt call setActiveItem if node already loaded", function() {
        var defer = $q.defer();
        var controller = makeController(defer);
        MachinesManager._activeItem = node;
        spyOn(MachinesManager, "setActiveItem");

        defer.resolve();
        $rootScope.$digest();

        expect($scope.node).toBe(node);
        expect(MachinesManager.setActiveItem).not.toHaveBeenCalled();
    });

    it("calls setActiveItem if node not loaded", function() {
        var defer = $q.defer();
        var controller = makeController(defer);
        var setActiveDefer = $q.defer();
        spyOn(MachinesManager, "setActiveItem").and.returnValue(
            setActiveDefer.promise);

        defer.resolve();
        $rootScope.$digest();

        setActiveDefer.resolve(node);
        $rootScope.$digest();

        expect($scope.node).toBe(node);
        expect(MachinesManager.setActiveItem).toHaveBeenCalledWith(
            node.system_id);
    });

    it("calls raiseError if setActiveItem is rejected", function() {
        var defer = $q.defer();
        var controller = makeController(defer);
        var setActiveDefer = $q.defer();
        spyOn(MachinesManager, "setActiveItem").and.returnValue(
            setActiveDefer.promise);
        spyOn(ErrorService, "raiseError");

        defer.resolve();
        $rootScope.$digest();

        var error = makeName("error");
        setActiveDefer.reject(error);
        $rootScope.$digest();

        expect(ErrorService.raiseError).toHaveBeenCalledWith(error);
    });

    it("calls loadItems on the results manager", function() {
        var defer = $q.defer();
        var controller = makeController(defer);
        MachinesManager._activeItem = node;
        var manager = NodeResultsManagerFactory.getManager(node);
        spyOn(manager, "loadItems").and.returnValue($q.defer().promise);

        defer.resolve();
        $rootScope.$digest();
        expect(manager.loadItems).toHaveBeenCalled();
    });

    it("sets eventsLoaded once events manager loadItems resolves", function() {
        var defer = $q.defer();
        var controller = makeController(defer);
        MachinesManager._activeItem = node;
        var manager = NodeResultsManagerFactory.getManager(node);
        var loadDefer = $q.defer();
        spyOn(manager, "loadItems").and.returnValue(loadDefer.promise);

        defer.resolve();
        $rootScope.$digest();
        loadDefer.resolve();
        $rootScope.$digest();
        expect($scope.resultsLoaded).toBe(true);
    });

    it("sets results once events manager loadItems resolves", function() {
        var defer = $q.defer();
        var controller = makeController(defer);
        MachinesManager._activeItem = node;
        var manager = NodeResultsManagerFactory.getManager(node);
        var loadDefer = $q.defer();
        spyOn(manager, "loadItems").and.returnValue(loadDefer.promise);

        defer.resolve();
        $rootScope.$digest();
        loadDefer.resolve();
        $rootScope.$digest();
        expect($scope.resultsLoaded).toBe(true);
    });
});
