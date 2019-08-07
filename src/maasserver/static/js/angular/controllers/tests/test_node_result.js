/* Copyright 2015-2017 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for NodeResultController.
 */

import { makeFakeResponse, makeInteger, makeName } from "testing/utils";
import MockWebSocket from "testing/websocket";

describe("NodeResultController", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

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
  var MachinesManager, ControllersManager, RegionConnection;
  var NodeResultsManagerFactory, ManagerHelperService;
  var ErrorService, webSocket;
  beforeEach(inject(function($injector) {
    MachinesManager = $injector.get("MachinesManager");
    ControllersManager = $injector.get("ControllersManager");
    RegionConnection = $injector.get("RegionConnection");
    NodeResultsManagerFactory = $injector.get("NodeResultsManagerFactory");
    ManagerHelperService = $injector.get("ManagerHelperService");
    ErrorService = $injector.get("ErrorService");

    // Mock buildSocket so an actual connection is not made.
    webSocket = new MockWebSocket();
    spyOn(RegionConnection, "buildSocket").and.returnValue(webSocket);
    spyOn(RegionConnection, "callMethod").and.returnValue($q.defer().promise);
  }));

  // Make a fake result.
  function makeResult() {
    return {
      id: makeInteger(0, 1000),
      name: makeName("name")
    };
  }

  // Make a fake node.
  function makeNode() {
    var node = {
      system_id: makeName("system_id"),
      fqdn: makeName("fqdn")
    };
    MachinesManager._items.push(node);
    ControllersManager._items.push(node);
    return node;
  }

  // Create the node that will be used and set the routeParams.
  var node, $routeParams, script_result;
  beforeEach(function() {
    node = makeNode();
    script_result = makeResult();
    $routeParams = {
      id: script_result.id,
      system_id: node.system_id
    };
  });

  // Makes the NodeResultController
  function makeController(loadManagerDefer) {
    var loadManager = spyOn(ManagerHelperService, "loadManager");
    if (angular.isObject(loadManagerDefer)) {
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
      MachinesManager: MachinesManager,
      ControllersManager: ControllersManager,
      NodeResultsManagerFactory: NodeResultsManagerFactory,
      ManagerHelperService: ManagerHelperService,
      ErrorService: ErrorService
    });
  }

  it("sets title to loading and page to nodes", function() {
    makeController();
    expect($rootScope.title).toBe("Loading...");
  });

  it("sets the initial $scope values", function() {
    makeController();
    expect($scope.loaded).toBe(false);
    expect($scope.resultLoaded).toBe(false);
    expect($scope.node).toBeNull();
    expect($scope.output).toBe("combined");
    expect($scope.result).toBeNull();
    expect($scope.nodesManager).toBe(MachinesManager);
    expect($scope.type_name).toBe("machine");
  });

  it("sets the initial $scope values when controller", function() {
    $location.path("/controller");
    makeController();
    expect($scope.loaded).toBe(false);
    expect($scope.resultLoaded).toBe(false);
    expect($scope.node).toBeNull();
    expect($scope.output).toBe("combined");
    expect($scope.result).toBeNull();
    expect($scope.nodesManager).toBe(ControllersManager);
    expect($scope.type_name).toBe("controller");
  });

  it("calls loadManager with MachinesManager", function() {
    makeController();
    expect(ManagerHelperService.loadManager).toHaveBeenCalledWith(
      $scope,
      MachinesManager
    );
  });

  it("doesnt call setActiveItem if node already loaded", function() {
    var defer = $q.defer();
    makeController(defer);
    MachinesManager._activeItem = node;
    spyOn(MachinesManager, "setActiveItem");

    defer.resolve();
    $rootScope.$digest();

    expect($scope.node).toBe(node);
    expect($scope.loaded).toBe(true);
    expect(MachinesManager.setActiveItem).not.toHaveBeenCalled();
  });

  it("calls setActiveItem if node not loaded", function() {
    var defer = $q.defer();
    makeController(defer);
    var setActiveDefer = $q.defer();
    spyOn(MachinesManager, "setActiveItem").and.returnValue(
      setActiveDefer.promise
    );

    defer.resolve();
    $rootScope.$digest();

    setActiveDefer.resolve(node);
    $rootScope.$digest();

    expect($scope.node).toBe(node);
    expect($scope.loaded).toBe(true);
    expect(MachinesManager.setActiveItem).toHaveBeenCalledWith(node.system_id);
  });

  // eslint-disable-next-line no-undef
  xit("loads result on load", function(done) {
    var defer = $q.defer();
    makeController(defer);
    MachinesManager._activeItem = node;
    var script_result = makeResult();
    webSocket.returnData.push(makeFakeResponse(script_result));

    defer.resolve();
    $rootScope.$digest();

    expect($scope.node).toBe(node);
    expect($scope.loaded).toBe(true);
    var expectFunc;
    expectFunc = function() {
      if ($scope.resultLoaded) {
        expect($scope.result.id).toBe(script_result.id);
        done();
      } else {
        setTimeout(expectFunc);
      }
    };
    setTimeout(expectFunc);
  });

  it("calls raiseError if setActiveItem is rejected", function() {
    var defer = $q.defer();
    makeController(defer);
    var setActiveDefer = $q.defer();
    spyOn(MachinesManager, "setActiveItem").and.returnValue(
      setActiveDefer.promise
    );
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
    makeController(defer);
    MachinesManager._activeItem = node;
    $scope.result = script_result;

    defer.resolve();
    $rootScope.$digest();

    node.fqdn = makeName("fqdn");
    $rootScope.$digest();
    expect($rootScope.title).toBe(node.fqdn + " - " + script_result.name);
  });

  describe("get_result_data", function() {
    it("sets initial variables", function() {
      var defer = $q.defer();
      makeController(defer);
      var output = makeName("output");
      MachinesManager._activeItem = node;
      $scope.result = script_result;

      defer.resolve();
      $rootScope.$digest();
      $scope.get_result_data(output);

      expect($scope.output).toBe(output);
      expect($scope.data).toBe("Loading...");
    });

    it("returns result", function() {
      var defer = $q.defer();
      makeController();
      var output = makeName("output");
      var data = makeName("data");
      $scope.node = node;
      $scope.result = script_result;
      var nodeResultsManager = NodeResultsManagerFactory.getManager(
        $scope.node
      );
      spyOn(nodeResultsManager, "get_result_data").and.returnValue(
        defer.promise
      );

      $scope.get_result_data(output);
      defer.resolve(data);
      $rootScope.$digest();

      expect($scope.output).toBe(output);
      expect($scope.data).toBe(data);
    });

    it("returns empty file when empty", function() {
      var defer = $q.defer();
      makeController();
      var output = makeName("output");
      $scope.node = node;
      $scope.result = script_result;
      var nodeResultsManager = NodeResultsManagerFactory.getManager(
        $scope.node
      );
      spyOn(nodeResultsManager, "get_result_data").and.returnValue(
        defer.promise
      );

      $scope.get_result_data(output);
      defer.resolve("");
      $rootScope.$digest();

      expect($scope.output).toBe(output);
      expect($scope.data).toBe("Empty file.");
    });
  });
});
