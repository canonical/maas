/* Copyright 2015-2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for NodeEventsController.
 */

import { makeName } from "testing/utils";
import MockWebSocket from "testing/websocket";

describe("NodeEventsController", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Grab the needed angular pieces.
  var $controller, $location, $rootScope, $scope, $q;
  beforeEach(inject(function($injector) {
    $controller = $injector.get("$controller");
    $rootScope = $injector.get("$rootScope");
    $location = $injector.get("$location");
    $scope = $rootScope.$new();
    $q = $injector.get("$q");
  }));

  // Load the required dependencies for the NodeEventsController and
  // mock the websocket connection.
  var MachinesManager, ControllersManager, EventsManagerFactory;
  var ManagerHelperService, ErrorService, RegionConnection, webSocket;
  beforeEach(inject(function($injector) {
    MachinesManager = $injector.get("MachinesManager");
    ControllersManager = $injector.get("ControllersManager");
    EventsManagerFactory = $injector.get("EventsManagerFactory");
    ManagerHelperService = $injector.get("ManagerHelperService");
    ErrorService = $injector.get("ErrorService");
    RegionConnection = $injector.get("RegionConnection");

    // Mock buildSocket so an actual connection is not made.
    webSocket = new MockWebSocket();
    spyOn(RegionConnection, "buildSocket").and.returnValue(webSocket);
    spyOn(RegionConnection, "callMethod").and.returnValue($q.defer().promise);
  }));

  // Make a fake node.
  var _id = 0;
  function makeNode() {
    var node = {
      id: _id++,
      system_id: makeName("system_id"),
      fqdn: makeName("fqdn")
    };
    MachinesManager._items.push(node);
    ControllersManager._items.push(node);
    return node;
  }

  // Make a fake event.
  function makeEvent() {
    return {
      type: {
        description: makeName("type")
      },
      description: makeName("description")
    };
  }

  // Create the node that will be used and set the routeParams.
  var node, $routeParams;
  beforeEach(function() {
    node = makeNode();
    $routeParams = {
      system_id: node.system_id
    };
  });

  // Makes the NodeEventsController
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

    return $controller("NodeEventsController", {
      $scope: $scope,
      $rootScope: $rootScope,
      $routeParams: $routeParams,
      MachinesManager: MachinesManager,
      ControllersManager: ControllersManager,
      EventsManagerFactory: EventsManagerFactory,
      ManagerHelperService: ManagerHelperService,
      ErrorService: ErrorService
    });
  }

  it("sets title to loading", function() {
    makeController();
    expect($rootScope.title).toBe("Loading...");
  });

  it("sets the initial $scope values", function() {
    makeController();
    expect($scope.loaded).toBe(false);
    expect($scope.node).toBeNull();
    expect($scope.events).toEqual([]);
    expect($scope.eventsLoaded).toEqual(false);
    expect($scope.days).toEqual(1);
    expect($scope.nodesManager).toBe(MachinesManager);
    expect($scope.type_name).toBe("machine");
  });

  it("sets the initial $scope values when controller", function() {
    $location.path("/controller");
    makeController();
    expect($scope.loaded).toBe(false);
    expect($scope.node).toBeNull();
    expect($scope.events).toEqual([]);
    expect($scope.eventsLoaded).toEqual(false);
    expect($scope.days).toEqual(1);
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

  it("gets the events manager for the node", function() {
    var defer = $q.defer();
    makeController(defer);
    MachinesManager._activeItem = node;
    spyOn(EventsManagerFactory, "getManager").and.callThrough();

    defer.resolve();
    $rootScope.$digest();
    expect(EventsManagerFactory.getManager).toHaveBeenCalledWith(node.id);

    var manager = EventsManagerFactory.getManager(node.id);
    expect($scope.events).toBe(manager.getItems());
  });

  it("calls loadItems on the events manager", function() {
    var defer = $q.defer();
    makeController(defer);
    MachinesManager._activeItem = node;
    var manager = EventsManagerFactory.getManager(node.id);
    spyOn(manager, "loadItems").and.returnValue($q.defer().promise);

    defer.resolve();
    $rootScope.$digest();
    expect(manager.loadItems).toHaveBeenCalled();
  });

  it("sets eventsLoaded once events manager loadItems resolves", function() {
    var defer = $q.defer();
    makeController(defer);
    MachinesManager._activeItem = node;
    var manager = EventsManagerFactory.getManager(node.id);
    var loadDefer = $q.defer();
    spyOn(manager, "loadItems").and.returnValue(loadDefer.promise);

    defer.resolve();
    $rootScope.$digest();
    loadDefer.resolve();
    $rootScope.$digest();
    expect($scope.eventsLoaded).toBe(true);
  });

  it("watches node.fqdn updates $rootScope.title", function() {
    var defer = $q.defer();
    makeController(defer);
    MachinesManager._activeItem = node;

    defer.resolve();
    $rootScope.$digest();

    node.fqdn = makeName("fqdn");
    $rootScope.$digest();
    expect($rootScope.title).toBe(node.fqdn + " - events");
  });

  describe("getEventText", function() {
    it("returns just event type description without dash", function() {
      makeController();
      var evt = makeEvent();
      delete evt.description;
      expect($scope.getEventText(evt)).toBe(evt.type.description);
    });

    it("returns event type description with event description", function() {
      makeController();
      var evt = makeEvent();
      expect($scope.getEventText(evt)).toBe(
        evt.type.description + " - " + evt.description
      );
    });
  });

  describe("loadMore", function() {
    it("adds 1 days to $scope.days", function() {
      var defer = $q.defer();
      makeController(defer);
      MachinesManager._activeItem = node;

      defer.resolve();
      $rootScope.$digest();
      $scope.loadMore();

      expect($scope.days).toBe(2);
    });

    it("calls loadMaximumDays with $scope.days", function() {
      var defer = $q.defer();
      makeController(defer);
      MachinesManager._activeItem = node;
      var manager = EventsManagerFactory.getManager(node.id);
      spyOn(manager, "loadMaximumDays");

      defer.resolve();
      $rootScope.$digest();
      $scope.loadMore();

      expect(manager.loadMaximumDays).toHaveBeenCalledWith(2);
    });
  });
});
