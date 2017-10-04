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
        expect($scope.resultsLoaded).toBe(false);
        expect($scope.node).toBeNull();
        expect($scope.commissioning_results).toEqual([
            {
                title: "CPU",
                hardware_type: 1,
                results: {}
            },
            {
                title: "Memory",
                hardware_type: 2,
                results: {}
            },
            {
                title: "Storage",
                hardware_type: 3,
                results: {}
            },
            {
                title: "Other Results",
                hardware_type: 0,
                results: {}
            }
        ]);
        expect($scope.testing_results).toEqual([
            {
                title: "CPU",
                hardware_type: 1,
                results: {}
            },
            {
                title: "Memory",
                hardware_type: 2,
                results: {}
            },
            {
                title: "Storage",
                hardware_type: 3,
                results: {}
            },
            {
                title: "Other Results",
                hardware_type: 0,
                results: {}
            }
        ]);
        expect($scope.installation_result).toEqual({});
        expect($scope.nodesManager).toBe(MachinesManager);
    });

    it("sets the initial $scope values when controller", function() {
        $routeParams.type = 'controller';
        var controller = makeController();
        expect($scope.resultsLoaded).toBe(false);
        expect($scope.node).toBeNull();
        expect($scope.commissioning_results).toEqual([
            {
                title: "CPU",
                hardware_type: 1,
                results: {}
            },
            {
                title: "Memory",
                hardware_type: 2,
                results: {}
            },
            {
                title: "Storage",
                hardware_type: 3,
                results: {}
            },
            {
                title: "Other Results",
                hardware_type: 0,
                results: {}
            }
        ]);
        expect($scope.testing_results).toEqual([
            {
                title: "CPU",
                hardware_type: 1,
                results: {}
            },
            {
                title: "Memory",
                hardware_type: 2,
                results: {}
            },
            {
                title: "Storage",
                hardware_type: 3,
                results: {}
            },
            {
                title: "Other Results",
                hardware_type: 0,
                results: {}
            }
        ]);
        expect($scope.installation_result).toEqual({});
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

    it("gets the results manager for the node", function() {
        var defer = $q.defer();
        var controller = makeController(defer);
        MachinesManager._activeItem = node;
        spyOn(NodeResultsManagerFactory, "getManager").and.callThrough();

        defer.resolve();
        $rootScope.$digest();
        expect(NodeResultsManagerFactory.getManager).toHaveBeenCalledWith(
            node.system_id);
    });

    it("calls loadItems on the results manager", function() {
        var defer = $q.defer();
        var controller = makeController(defer);
        MachinesManager._activeItem = node;
        var manager = NodeResultsManagerFactory.getManager(node.system_id);
        spyOn(manager, "loadItems").and.returnValue($q.defer().promise);

        defer.resolve();
        $rootScope.$digest();
        expect(manager.loadItems).toHaveBeenCalled();
    });

    it("sets eventsLoaded once events manager loadItems resolves", function() {
        var defer = $q.defer();
        var controller = makeController(defer);
        MachinesManager._activeItem = node;
        var manager = NodeResultsManagerFactory.getManager(node.system_id);
        var loadDefer = $q.defer();
        spyOn(manager, "loadItems").and.returnValue(loadDefer.promise);

        defer.resolve();
        $rootScope.$digest();
        loadDefer.resolve();
        $rootScope.$digest();
        expect($scope.resultsLoaded).toBe(true);
    });

    it("stores commissioning CPU result", function(done) {
        var defer = $q.defer();
        var controller = makeController(defer);
        MachinesManager._activeItem = node;
        var script_result = {
            result_type: 0,
            hardware_type: 1,
            showing_results: false,
            showing_menu: false,
            showing_history: false,
            $selected: false
        };
        webSocket.returnData.push(makeFakeResponse([script_result]));

        defer.resolve();
        $rootScope.$digest();

        var expectFunc;
        expectFunc = function() {
            if($scope.resultsLoaded) {
                expect($scope.commissioning_results[0].results[null]).toEqual(
                    [script_result]);
                done();
            } else {
                setTimeout(expectFunc);
            }
        };
        setTimeout(expectFunc);
    });

    it("stores commissioning memory result", function(done) {
        var defer = $q.defer();
        var controller = makeController(defer);
        MachinesManager._activeItem = node;
        var script_result = {
            result_type: 0,
            hardware_type: 2,
            showing_results: false,
            showing_menu: false,
            showing_history: false,
            $selected: false
        };
        webSocket.returnData.push(makeFakeResponse([script_result]));

        defer.resolve();
        $rootScope.$digest();

        var expectFunc;
        expectFunc = function() {
            if($scope.resultsLoaded) {
                expect($scope.commissioning_results[1].results[null]).toEqual(
                    [script_result]);
                done();
            } else {
                setTimeout(expectFunc);
            }
        };
        setTimeout(expectFunc);
    });

    it("stores commissioning storage result", function(done) {
        var defer = $q.defer();
        var controller = makeController(defer);
        var physical_blockdevice_id = makeInteger(0, 100);
        var name = makeName("name");
        var model = makeName("model");
        var serial = makeName("serial");
        node.disks = [{
            id: physical_blockdevice_id,
            name: name,
            model: model,
            serial: serial
        }];
        MachinesManager._activeItem = node;
        var script_result = {
            result_type: 0,
            hardware_type: 3,
            physical_blockdevice: physical_blockdevice_id,
            showing_results: false,
            showing_menu: false,
            showing_history: false,
            $selected: false
        };
        webSocket.returnData.push(makeFakeResponse([script_result]));

        defer.resolve();
        $rootScope.$digest();

        var expectFunc;
        expectFunc = function() {
            if($scope.resultsLoaded) {
                expect($scope.commissioning_results[2].results[
                    "/dev/" + name + " (Model: " + model + ", Serial: " +
                        serial + ")"]).toEqual([script_result]);
                done();
            } else {
                setTimeout(expectFunc);
            }
        };
        setTimeout(expectFunc);
    });

    it("stores commissioning other result", function(done) {
        var defer = $q.defer();
        var controller = makeController(defer);
        MachinesManager._activeItem = node;
        var script_result = {
            result_type: 0,
            hardware_type: 0,
            showing_results: false,
            showing_menu: false,
            showing_history: false,
            $selected: false
        };
        webSocket.returnData.push(makeFakeResponse([script_result]));

        defer.resolve();
        $rootScope.$digest();

        var expectFunc;
        expectFunc = function() {
            if($scope.resultsLoaded) {
                expect($scope.commissioning_results[3].results[null]).toEqual(
                    [script_result]);
                done();
            } else {
                setTimeout(expectFunc);
            }
        };
        setTimeout(expectFunc);
    });

    it("stores testing CPU result", function(done) {
        var defer = $q.defer();
        var controller = makeController(defer);
        MachinesManager._activeItem = node;
        var script_result = {
            result_type: 2,
            hardware_type: 1,
            showing_results: false,
            showing_menu: false,
            showing_history: false,
            $selected: false
        };
        webSocket.returnData.push(makeFakeResponse([script_result]));

        defer.resolve();
        $rootScope.$digest();

        var expectFunc;
        expectFunc = function() {
            if($scope.resultsLoaded) {
                expect($scope.testing_results[0].results[null]).toEqual(
                    [script_result]);
                done();
            } else {
                setTimeout(expectFunc);
            }
        };
        setTimeout(expectFunc);
    });

    it("stores testing memory result", function(done) {
        var defer = $q.defer();
        var controller = makeController(defer);
        MachinesManager._activeItem = node;
        var script_result = {
            result_type: 2,
            hardware_type: 2,
            showing_results: false,
            showing_menu: false,
            showing_history: false,
            $selected: false
        };
        webSocket.returnData.push(makeFakeResponse([script_result]));

        defer.resolve();
        $rootScope.$digest();

        var expectFunc;
        expectFunc = function() {
            if($scope.resultsLoaded) {
                expect($scope.testing_results[1].results[null]).toEqual(
                    [script_result]);
                done();
            } else {
                setTimeout(expectFunc);
            }
        };
        setTimeout(expectFunc);
    });

    it("stores testing storage result", function(done) {
        var defer = $q.defer();
        var controller = makeController(defer);
        var physical_blockdevice_id = makeInteger(0, 100);
        var name = makeName("name");
        var model = makeName("model");
        var serial = makeName("serial");
        node.disks = [{
            id: physical_blockdevice_id,
            name: name,
            model: model,
            serial: serial
        }];
        MachinesManager._activeItem = node;
        var script_result = {
            result_type: 2,
            hardware_type: 3,
            physical_blockdevice: physical_blockdevice_id,
            showing_results: false,
            showing_menu: false,
            showing_history: false,
            $selected: false
        };
        webSocket.returnData.push(makeFakeResponse([script_result]));

        defer.resolve();
        $rootScope.$digest();

        var expectFunc;
        expectFunc = function() {
            if($scope.resultsLoaded) {
                expect($scope.testing_results[2].results[
                    "/dev/" + name + " (Model: " + model + ", Serial: " +
                        serial + ")"]).toEqual([script_result]);
                done();
            } else {
                setTimeout(expectFunc);
            }
        };
        setTimeout(expectFunc);
    });

    it("stores testing other result", function(done) {
        var defer = $q.defer();
        var controller = makeController(defer);
        MachinesManager._activeItem = node;
        var script_result = {
            result_type: 2,
            hardware_type: 0,
            showing_results: false,
            showing_menu: false,
            showing_history: false,
            $selected: false
        };
        webSocket.returnData.push(makeFakeResponse([script_result]));

        defer.resolve();
        $rootScope.$digest();

        var expectFunc;
        expectFunc = function() {
            if($scope.resultsLoaded) {
                expect($scope.testing_results[3].results[null]).toEqual(
                    [script_result]);
                done();
            } else {
                setTimeout(expectFunc);
            }
        };
        setTimeout(expectFunc);
    });

    it("stores testing other result", function(done) {
        var defer = $q.defer();
        var controller = makeController(defer);
        MachinesManager._activeItem = node;
        var script_result = {
            result_type: 1,
            showing_results: false,
            showing_menu: false,
            showing_history: false,
            $selected: false
        };
        webSocket.returnData.push(makeFakeResponse([script_result]));

        defer.resolve();
        $rootScope.$digest();

        var expectFunc;
        expectFunc = function() {
            if($scope.resultsLoaded) {
                expect($scope.installation_result).toEqual(script_result);
                done();
            } else {
                setTimeout(expectFunc);
            }
        };
        setTimeout(expectFunc);
    });
});
