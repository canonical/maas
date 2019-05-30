/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for controller status directive.
 */

import { makeName, pickItem } from "testing/utils";

describe("maasControllerStatus", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Make service.
  var _nextId = 0;
  function makeService(status) {
    var name = makeName("service");
    if (angular.isUndefined(status)) {
      status = pickItem(["running", "dead", "off", "degraded"]);
    }
    return {
      id: _nextId++,
      name: name,
      status: status
    };
  }

  // Make controller with services.
  function makeController(services) {
    var service_ids = [];
    if (angular.isArray(services)) {
      angular.forEach(services, function(service) {
        service_ids.push(service.id);
      });
    }
    return {
      service_ids: service_ids
    };
  }

  // Get the required managers.
  var ServicesManager;
  beforeEach(inject(function($injector) {
    ServicesManager = $injector.get("ServicesManager");
  }));

  // Create a new scope before each test.
  var $scope;
  beforeEach(inject(function($rootScope) {
    $scope = $rootScope.$new();
  }));

  // Return the compiled directive with the osinfo from the scope.
  function compileDirective() {
    var directive;
    var html =
      '<div><div data-maas-controller-status="controller">' + "</div></div>";

    // Compile the directive.
    inject(function($compile) {
      directive = $compile(html)($scope);
    });

    // Perform the digest cycle to finish the compile.
    $scope.$digest();
    return directive.find("div");
  }

  it("sets serviceClass in the class for element", function() {
    var directive = compileDirective();
    var serviceClass = makeName("serviceClass");
    directive.isolateScope().serviceClass = serviceClass;
    $scope.$digest();
    expect(directive.find("span").hasClass("p-icon--" + serviceClass)).toBe(
      true
    );
  });

  it("services is ServicesManager.getItems()", function() {
    var directive = compileDirective();
    expect(directive.isolateScope().services).toBe(ServicesManager.getItems());
  });

  it("serviceClass updated when services change on controller", function() {
    var service = makeService("running");
    ServicesManager._items.push(service);
    $scope.controller = makeController();
    var directive = compileDirective();
    $scope.controller.service_ids = [service.id];
    $scope.$digest();
    expect(directive.isolateScope().serviceClass).toBe("success");
  });

  it("serviceClass updated when services change in manager", function() {
    var service = makeService("running");
    ServicesManager._items.push(service);
    $scope.controller = makeController([service]);
    var directive = compileDirective();
    var newService = angular.copy(service);
    newService.status = "dead";
    ServicesManager._items.splice(0, 1);
    ServicesManager._items.push(newService);
    $scope.$digest();
    expect(directive.isolateScope().serviceClass).toBe("power-error");
  });

  it("any dead is error", function() {
    var services = [
      makeService("dead"),
      makeService("degraded"),
      makeService("running"),
      makeService("unknown"),
      makeService("off")
    ];
    ServicesManager._items.push.apply(ServicesManager._items, services);
    $scope.controller = makeController(services);
    var directive = compileDirective();
    expect(directive.isolateScope().serviceClass).toBe("power-error");
  });

  it("any degraded without error is warning", function() {
    var services = [
      makeService("degraded"),
      makeService("running"),
      makeService("unknown"),
      makeService("off")
    ];
    ServicesManager._items.push.apply(ServicesManager._items, services);
    $scope.controller = makeController(services);
    var directive = compileDirective();
    expect(directive.isolateScope().serviceClass).toBe("warning");
  });

  it("any running without error or degraded is success", function() {
    var services = [
      makeService("running"),
      makeService("unknown"),
      makeService("off")
    ];
    ServicesManager._items.push.apply(ServicesManager._items, services);
    $scope.controller = makeController(services);
    var directive = compileDirective();
    expect(directive.isolateScope().serviceClass).toBe("success");
  });

  it("update service status updates service class", function() {
    var services = [makeService("dead")];
    ServicesManager._items.push.apply(ServicesManager._items, services);
    $scope.controller = makeController(services);
    var directive = compileDirective();
    expect(directive.isolateScope().serviceClass).toBe("power-error");

    services[0].status = "running";
    $scope.$digest();
    expect(directive.isolateScope().serviceClass).toBe("success");
  });
});
