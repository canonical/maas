/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for controller image status directive.
 */

import { makeName } from "testing/utils";

describe("maasControllerImageStatus", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Get the manager and the directive service.
  var $timeout, $interval, $q;
  var ControllersManager, ControllerImageStatusService;
  beforeEach(inject(function($injector) {
    $timeout = $injector.get("$timeout");
    $interval = $injector.get("$interval");
    $q = $injector.get("$q");
    ControllersManager = $injector.get("ControllersManager");
    ControllerImageStatusService = $injector.get(
      "ControllerImageStatusService"
    );
  }));

  // Create a new scope before each test.
  var $scope;
  beforeEach(inject(function($rootScope) {
    $scope = $rootScope.$new();
  }));

  // Return the compiled directive with the osinfo from the scope.
  function compileDirective() {
    var directive;
    var html = [
      "<div>",
      '<maas-controller-image-status system-id="system_id">',
      "</maas-controller-image-status>",
      "</div>"
    ].join("");

    // Compile the directive.
    inject(function($compile) {
      directive = $compile(html)($scope);
    });

    // Perform the digest cycle to finish the compile.
    $scope.$digest();
    return directive.find("maas-controller-image-status");
  }

  describe("service", function() {
    var service;
    beforeEach(function() {
      service = ControllerImageStatusService;
    });

    describe("updateStatuses", function() {
      it("calls checkImageStates with controllers", function() {
        service.controllers = [makeName("systemId"), makeName("systemId")];
        spyOn(ControllersManager, "checkImageStates").and.returnValue(
          $q.defer().promise
        );
        service.updateStatuses();

        expect(ControllersManager.checkImageStates).toHaveBeenCalledWith([
          { system_id: service.controllers[0] },
          { system_id: service.controllers[1] }
        ]);
      });

      it("sets statuses with result", function() {
        var defer = $q.defer();
        service.controllers = [
          makeName("systemId"),
          makeName("systemId"),
          makeName("systemId")
        ];
        spyOn(ControllersManager, "checkImageStates").and.returnValue(
          defer.promise
        );
        service.updateStatuses();

        var results = {};
        results[service.controllers[0]] = makeName("status");
        results[service.controllers[1]] = makeName("status");
        defer.resolve(results);
        $scope.$digest();

        var statues = {};
        statues[service.controllers[0]] = results[service.controllers[0]];
        statues[service.controllers[1]] = results[service.controllers[1]];
        statues[service.controllers[2]] = "Unknown";
        expect(service.statuses).toEqual(statues);
      });
    });

    describe("register", function() {
      it("added to controllers and starts timer", function() {
        var systemId = makeName("systemId");
        service.register(systemId);

        expect(service.controllers).toEqual([systemId]);
        expect(service.startTimeout).toBeDefined();
        $timeout.cancel(service.startTimeout);
      });

      it("added multiple and restarts timer", function() {
        var systemId1 = makeName("systemId");
        var systemId2 = makeName("systemId");

        service.register(systemId1);
        var firstTimeout = service.startTimeout;

        service.register(systemId2);
        var secondTimeout = service.startTimeout;

        expect(firstTimeout).not.toBe(secondTimeout);
        expect(secondTimeout).toBeDefined();
        $timeout.cancel(secondTimeout);
      });

      it("starts interval after 100ms", function() {
        var systemId = makeName("systemId");
        spyOn(service, "updateStatuses");

        service.register(systemId);
        $timeout.flush(100);

        expect(service.runningInterval).toBeDefined();
      });

      it("cancels running interval on new controller", function() {
        var systemId = makeName("systemId");

        var interval = (service.runningInterval = {});
        spyOn($interval, "cancel");

        service.register(systemId);
        expect($interval.cancel).toHaveBeenCalledWith(interval);
        expect(service.runningInterval).not.toBeDefined();
        expect(service.controllers).toEqual([systemId]);
        expect(service.startTimeout).toBeDefined();
        $timeout.cancel(service.startTimeout);
      });
    });

    describe("unregister", function() {
      it("removes controller", function() {
        var systemId = makeName("systemId");
        service.controllers.push(systemId);
        service.unregister(systemId);

        expect(service.controllers.length).toBe(0);
      });

      it("stops timeout and interval", function() {
        var systemId = makeName("systemId");
        service.controllers.push(systemId);

        var startTimeout = (service.startTimeout = {});
        var runningInterval = (service.runningInterval = {});
        spyOn($timeout, "cancel");
        spyOn($interval, "cancel");

        service.unregister(systemId);
        expect($timeout.cancel).toHaveBeenCalledWith(startTimeout);
        expect(service.startTimeout).not.toBeDefined();
        expect($interval.cancel).toHaveBeenCalledWith(runningInterval);
        expect(service.runningInterval).not.toBeDefined();
      });
    });

    describe("showSpinner", function() {
      it("returns false if set and not syncing", function() {
        var systemId = makeName("systemId");
        var status = "out-of-sync";
        service.statuses[systemId] = status;
        expect(service.showSpinner(systemId)).toBe(false);
      });

      it("returns true if not set", function() {
        var systemId = makeName("systemId");
        expect(service.showSpinner(systemId)).toBe(true);
      });

      it("returns true if set and syncing", function() {
        var systemId = makeName("systemId");
        var status = "Syncing";
        service.statuses[systemId] = status;
        expect(service.showSpinner(systemId)).toBe(true);
      });
    });

    describe("getImageStatus", function() {
      it("returns status if set", function() {
        var systemId = makeName("systemId");
        var status = "out-of-sync";
        service.statuses[systemId] = status;
        expect(service.getImageStatus(systemId)).toBe(status);
      });

      it("returns asking", function() {
        var systemId = makeName("systemId");
        expect(service.getImageStatus(systemId)).toBe("Asking for status...");
      });
    });
  });

  describe("directive", function() {
    it("registers when systemId is set", function() {
      spyOn(ControllerImageStatusService, "register");
      compileDirective();

      // Should only be called once system_id is set.
      expect(ControllerImageStatusService.register).not.toHaveBeenCalled();
      $scope.system_id = makeName("systemId");
      $scope.$digest();
      expect(ControllerImageStatusService.register).toHaveBeenCalledWith(
        $scope.system_id
      );
    });

    it("unregisters when destroyed", function() {
      spyOn(ControllerImageStatusService, "register");
      spyOn(ControllerImageStatusService, "unregister");
      var directive = compileDirective();

      $scope.system_id = makeName("systemId");
      $scope.$digest();
      expect(ControllerImageStatusService.register).toHaveBeenCalledWith(
        $scope.system_id
      );

      directive.scope().$destroy();
      expect(ControllerImageStatusService.unregister).toHaveBeenCalledWith(
        $scope.system_id
      );
    });
  });
});
