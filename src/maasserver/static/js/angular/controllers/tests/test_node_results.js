/* Copyright 2017-2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for NodeResultsController
 */

import {
  makeFakeResponse,
  makeInteger,
  makeName,
  pickItem
} from "testing/utils";
import MockWebSocket from "testing/websocket";

// 2019-04-30 Caleb - Syntax error `import { ScriptStatus }from "../../enum"`;
// TODO - Fix es module imports in test files
const ScriptStatus = {
  PENDING: 0,
  RUNNING: 1,
  PASSED: 2,
  FAILED: 3,
  TIMEDOUT: 4,
  ABORTED: 5,
  DEGRADED: 6,
  INSTALLING: 7,
  FAILED_INSTALLING: 8,
  SKIPPED: 9
};

describe("NodeResultsController", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Grab the needed angular pieces.
  var $controller, $location, $rootScope, $scope, $q;
  beforeEach(inject(function($injector) {
    $controller = $injector.get("$controller");
    $rootScope = $injector.get("$rootScope");
    $location = $injector.get("$location");
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

  // Make a result.
  function makeResult(type, status) {
    if (type === null) {
      type = makeInteger(0, 3);
    }
    if (status === null) {
      status = makeInteger(0, 8);
    }
    var id = makeInteger(0, 1000);
    var result = {
      id: id,
      name: makeName("name"),
      type: type,
      status: status,
      history_list: [
        {
          id: id,
          status: status
        }
      ]
    };
    var i;
    for (i = 0; i < 3; i++) {
      result.history_list.push({
        id: makeInteger(0, 1000),
        status: makeInteger(0, 8)
      });
    }
    return result;
  }

  // Makes the NodeResultsController
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
    makeController();
    expect($scope.commissioning_results).toBeNull();
    expect($scope.testing_results).toBeNull();
    expect($scope.installation_results).toBeNull();
    expect($scope.results).toBeNull();
    expect($scope.logs.option).toBeNull();
    expect($scope.logs.availableOptions).toEqual([]);
    expect($scope.logOutput).toEqual("Loading...");
    expect($scope.loaded).toBe(false);
    expect($scope.resultsLoaded).toBe(false);
    expect($scope.node).toBeNull();
    expect($scope.nodesManager).toBe(MachinesManager);
  });

  it("sets the initial $scope values when controller", function() {
    $location.path("/controller");
    makeController();
    expect($scope.commissioning_results).toBeNull();
    expect($scope.testing_results).toBeNull();
    expect($scope.installation_results).toBeNull();
    expect($scope.results).toBeNull();
    expect($scope.logs.option).toBeNull();
    expect($scope.logs.availableOptions).toEqual([]);
    expect($scope.logOutput).toEqual("Loading...");
    expect($scope.loaded).toBe(false);
    expect($scope.resultsLoaded).toBe(false);
    expect($scope.node).toBeNull();
    expect($scope.nodesManager).toBe(ControllersManager);
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
    expect(MachinesManager.setActiveItem).toHaveBeenCalledWith(node.system_id);
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

  it("calls loadItems on the results manager", function() {
    var defer = $q.defer();
    makeController(defer);
    MachinesManager._activeItem = node;
    var manager = NodeResultsManagerFactory.getManager(node);
    spyOn(manager, "loadItems").and.returnValue($q.defer().promise);

    defer.resolve();
    $rootScope.$digest();
    expect(manager.loadItems).toHaveBeenCalled();
  });

  it("sets eventsLoaded once events manager loadItems resolves", function() {
    var defer = $q.defer();
    makeController(defer);
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
    makeController(defer);
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

  describe("updateLogs", function() {
    it("only runs on logs page", function() {
      var defer = $q.defer();
      makeController(defer);
      MachinesManager._activeItem = node;
      var loadDefer = $q.defer();

      defer.resolve();
      $rootScope.$digest();
      loadDefer.resolve();
      $rootScope.$digest();
      expect($scope.logs.availableOptions).toEqual([]);
    });

    it("loads summary", function() {
      var defer = $q.defer();
      makeController(defer);
      $scope.section = { area: "logs" };
      MachinesManager._activeItem = node;
      webSocket.returnData.push(makeFakeResponse([]));
      defer.resolve();
      $rootScope.$digest();
      var expectFunc;
      expectFunc = function() {
        if ($scope.resultsLoaded) {
          expect($scope.logs.availableOptions).toEqual([
            {
              title: "Machine output (YAML)",
              id: "summary_yaml"
            },
            {
              title: "Machine output (XML)",
              id: "summary_xml"
            }
          ]);
          expect($scope.logs.option).toEqual({
            title: "Machine output (YAML)",
            id: "summary_yaml"
          });
        } else {
          setTimeout(expectFunc);
        }
      };
      setTimeout(expectFunc);
    });
  });

  describe("updateLogOutput", function() {
    it("sets to loading when no node", function() {
      makeController();
      $scope.updateLogOutput();
      expect($scope.logOutput).toEqual("Loading...");
    });

    it("sets summary xml", function() {
      var defer = $q.defer();
      makeController(defer);
      MachinesManager._activeItem = node;
      var managerDefer = $q.defer();
      $scope.logs = { option: { id: "summary_xml" } };
      spyOn(MachinesManager, "getSummaryXML").and.returnValue(
        managerDefer.promise
      );

      defer.resolve();
      $rootScope.$digest();
      managerDefer.resolve();
      $rootScope.$digest();

      $scope.updateLogOutput();
      expect(MachinesManager.getSummaryXML).toHaveBeenCalledWith(node);
    });

    it("sets summary yaml", function() {
      var defer = $q.defer();
      makeController(defer);
      MachinesManager._activeItem = node;
      var managerDefer = $q.defer();
      $scope.logs = { option: { id: "summary_yaml" } };
      spyOn(MachinesManager, "getSummaryYAML").and.returnValue(
        managerDefer.promise
      );

      defer.resolve();
      $rootScope.$digest();
      managerDefer.resolve();
      $rootScope.$digest();

      $scope.updateLogOutput();
      expect(MachinesManager.getSummaryYAML).toHaveBeenCalledWith(node);
    });

    it("sets system booting", function() {
      makeController();
      var installation_result = makeResult(1, 0);
      $scope.installation_results = [installation_result];
      $scope.node = node;
      $scope.logs = { option: { id: installation_result.id } };

      $scope.updateLogOutput();
      expect($scope.logOutput).toEqual("System is booting...");
    });

    it("sets installation has begun", function() {
      makeController();
      var installation_result = makeResult(1, 1);
      $scope.installation_results = [installation_result];
      $scope.node = node;
      $scope.logs = { option: { id: installation_result.id } };

      $scope.updateLogOutput();
      expect($scope.logOutput).toEqual("Installation has begun!");
    });

    it("sets installation output succeeded", function() {
      var defer = $q.defer();
      makeController(defer);
      var installation_result = makeResult(1, 2);
      MachinesManager._activeItem = node;
      var manager = NodeResultsManagerFactory.getManager(node);
      var managerDefer = $q.defer();
      spyOn(manager, "get_result_data").and.returnValue(managerDefer.promise);

      defer.resolve();
      $rootScope.$digest();
      managerDefer.resolve();
      $rootScope.$digest();

      $scope.installation_results = [installation_result];
      $scope.logs = { option: { id: installation_result.id } };
      $scope.updateLogOutput();
      expect(manager.get_result_data).toHaveBeenCalledWith(
        installation_result.id,
        "combined"
      );
    });

    it("sets installation output failed", function() {
      var defer = $q.defer();
      makeController(defer);
      var installation_result = makeResult(1, 3);
      MachinesManager._activeItem = node;
      var manager = NodeResultsManagerFactory.getManager(node);
      var managerDefer = $q.defer();
      spyOn(manager, "get_result_data").and.returnValue(managerDefer.promise);

      defer.resolve();
      $rootScope.$digest();
      managerDefer.resolve();
      $rootScope.$digest();

      $scope.installation_results = [installation_result];
      $scope.logs = { option: { id: installation_result.id } };
      $scope.updateLogOutput();
      expect(manager.get_result_data).toHaveBeenCalledWith(
        installation_result.id,
        "combined"
      );
    });

    it("sets timed out", function() {
      makeController();
      var installation_result = makeResult(1, 4);
      $scope.installation_results = [installation_result];
      $scope.node = node;
      $scope.logs = { option: { id: installation_result.id } };

      $scope.updateLogOutput();
      expect($scope.logOutput).toEqual("Installation failed after 40 minutes.");
    });

    it("sets installation aborted", function() {
      makeController();
      var installation_result = makeResult(1, 5);
      $scope.installation_results = [installation_result];
      $scope.node = node;
      $scope.logs = { option: { id: installation_result.id } };

      $scope.updateLogOutput();
      expect($scope.logOutput).toEqual("Installation was aborted.");
    });

    it("sets unknown status", function() {
      makeController();
      var installation_result = makeResult(1, makeInteger(6, 100));
      $scope.installation_results = [installation_result];
      $scope.node = node;
      $scope.logs = { option: { id: installation_result.id } };

      $scope.updateLogOutput();
      expect($scope.logOutput).toEqual(
        "BUG: Unknown log status " + installation_result.status
      );
    });

    it("sets no installation log", function() {
      makeController();
      $scope.installation_results = [];
      $scope.node = node;
      $scope.logs = { option: { id: 123 } };

      $scope.updateLogOutput();
      expect($scope.logOutput).toEqual("BUG: No installation result found.");
    });

    it("sets install id to ScriptResult /tmp/install.log", function() {
      var defer = $q.defer();
      var loadItems_defer = $q.defer();
      makeController(loadItems_defer);
      $scope.section = { area: "logs" };
      MachinesManager._activeItem = node;
      webSocket.returnData.push(makeFakeResponse([]));
      var manager = NodeResultsManagerFactory.getManager(node);
      spyOn(manager, "loadItems").and.returnValue(defer.promise);
      manager.installation_results = [];
      var i;
      for (i = 0; i < 3; i++) {
        manager.installation_results.push(makeResult());
      }
      var installation_result = pickItem(manager.installation_results);
      installation_result.name = "/tmp/install.log";
      defer.resolve();
      loadItems_defer.resolve();
      $rootScope.$digest();
      var expectFunc;
      expectFunc = function() {
        if ($scope.resultsLoaded) {
          expect($scope.logs.availableOptions[0].id).toBe(
            installation_result.id
          );
        } else {
          setTimeout(expectFunc);
        }
      };
      setTimeout(expectFunc);
    });
  });

  describe("loadHistory", function() {
    it("loads results", function() {
      var defer = $q.defer();
      makeController();
      var result = {
        id: makeInteger(0, 100)
      };
      var history_list = [
        { id: makeInteger(0, 100) },
        { id: makeInteger(0, 100) },
        { id: makeInteger(0, 100) }
      ];
      $scope.node = node;
      $scope.nodeResultsManager = NodeResultsManagerFactory.getManager(
        $scope.node
      );
      spyOn($scope.nodeResultsManager, "get_history").and.returnValue(
        defer.promise
      );

      $scope.loadHistory(result);
      defer.resolve(history_list);
      $rootScope.$digest();

      expect(result.history_list).toBe(history_list);
      expect(result.loading_history).toBe(false);
      expect(result.showing_history).toBe(true);
    });

    it("doesnt reload", function() {
      makeController();
      var result = {
        id: makeInteger(0, 100),
        history_list: [{ id: makeInteger(0, 100) }]
      };
      $scope.node = node;
      $scope.nodeResultsManager = NodeResultsManagerFactory.getManager(
        $scope.node
      );
      spyOn($scope.nodeResultsManager, "get_history");

      $scope.loadHistory(result);

      expect(result.showing_history).toBe(true);
      expect($scope.nodeResultsManager.get_history).not.toHaveBeenCalled();
    });
  });

  describe("hasSuppressedTests", () => {
    it("returns whether there are suppressed tests in results", () => {
      makeController();
      const suppressedResult = makeResult(1);
      $scope.results = [
        {
          hardware_type: 1,
          results: {
            subtype: [
              ...Array.from(Array(3)).map(() => makeResult(1)),
              suppressedResult
            ]
          }
        },
        {
          hardware_type: 2,
          results: {
            subtype: Array.from(Array(3)).map(() => makeResult(2))
          }
        }
      ];

      expect($scope.hasSuppressedTests()).toEqual(false);

      suppressedResult.suppressed = true;
      expect($scope.hasSuppressedTests()).toEqual(true);
    });
  });

  describe("isSuppressible", () => {
    it(`returns true if a result's status is
      FAILED, FAILED_INSTALLING or TIMEDOUT`, () => {
      makeController();
      const results = [
        makeResult(0, ScriptStatus.FAILED),
        makeResult(0, ScriptStatus.FAILED_INSTALLING),
        makeResult(0, ScriptStatus.TIMEDOUT),
        makeResult(0, ScriptStatus.PASSED)
      ];

      expect($scope.isSuppressible(results[0])).toBe(true);
      expect($scope.isSuppressible(results[1])).toBe(true);
      expect($scope.isSuppressible(results[2])).toBe(true);
      expect($scope.isSuppressible(results[3])).toBe(false);
    });
  });

  describe("getSuppressedCount", () => {
    it("returns number of suppressed tests in node test results", () => {
      makeController();
      const results1 = Array.from(Array(5)).map((e, i) => {
        const result = makeResult(1, ScriptStatus.FAILED);
        if (i % 2 === 0) {
          result.suppressed = true;
        }
        return result;
      });
      const results2 = Array.from(Array(5)).map((e, i) => {
        const result = makeResult(2, ScriptStatus.FAILED);
        if (i % 2 === 0) {
          result.suppressed = true;
        }
        return result;
      });
      $scope.results = [
        {
          hardware_type: 1,
          results: {
            subtype: results1
          }
        },
        {
          hardware_type: 2,
          results: {
            subtype: results2
          }
        }
      ];

      expect($scope.getSuppressedCount()).toEqual(6);
    });

    it("returns 'All' if all suppressible tests are suppressed", () => {
      makeController();
      const results = Array.from(Array(5)).map((e, i) => {
        const result = makeResult(2, ScriptStatus.FAILED);
        result.suppressed = true;
        return result;
      });
      $scope.results = [
        {
          hardware_type: 1,
          results: {
            subtype: results
          }
        }
      ];

      expect($scope.getSuppressedCount()).toEqual("All");
    });
  });

  describe("toggleSuppressed", () => {
    it("calls suppressTests manager method if test not suppressed", () => {
      makeController();
      const result = makeResult();
      $scope.node = node;
      spyOn($scope.nodesManager, "suppressTests");

      $scope.toggleSuppressed(result);

      expect($scope.nodesManager.suppressTests).toHaveBeenCalledWith(
        $scope.node,
        [result]
      );
    });

    it("calls unsuppressTests manager method if test suppressed", () => {
      makeController();
      const result = makeResult();
      result.suppressed = true;
      $scope.node = node;
      spyOn($scope.nodesManager, "unsuppressTests");

      $scope.toggleSuppressed(result);

      expect($scope.nodesManager.unsuppressTests).toHaveBeenCalledWith(
        $scope.node,
        [result]
      );
    });
  });
});
