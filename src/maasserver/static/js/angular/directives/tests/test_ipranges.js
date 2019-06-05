/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for IP Ranges directive.
 */

import { makeInteger } from "testing/utils";
import MockWebSocket from "testing/websocket";

describe("maasIPRanges", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Preload the $templateCache with empty contents. We only test the
  // controller of the directive, not the template.
  var $q, $templateCache;
  beforeEach(inject(function($injector) {
    $q = $injector.get("$q");
    $templateCache = $injector.get("$templateCache");
    $templateCache.put("static/partials/ipranges.html?v=undefined", "");
  }));

  // Load the required managers.
  var IPRangesManager, UsersManager;
  beforeEach(inject(function($injector) {
    IPRangesManager = $injector.get("IPRangesManager");
    UsersManager = $injector.get("UsersManager");
    // Mock buildSocket so an actual connection is not made.
    let RegionConnection = $injector.get("RegionConnection");
    let webSocket = new MockWebSocket();
    spyOn(RegionConnection, "buildSocket").and.returnValue(webSocket);
  }));

  // Create a new scope before each test.
  var $scope;
  beforeEach(inject(function($rootScope) {
    $scope = $rootScope.$new();
  }));

  // Return the compiled directive with the items from the scope.
  function compileDirective(obj) {
    if (angular.isUndefined(obj)) {
      obj = "";
    }
    var directive;
    var html = [
      "<div>",
      '<maas-ip-ranges obj="' + obj + '"></maas-ip-ranges>',
      "</div>"
    ].join("");

    // Compile the directive.
    inject(function($compile) {
      directive = $compile(html)($scope);
    });

    // Perform the digest cycle to finish the compile.
    $scope.$digest();
    return directive.find("maas-ip-ranges");
  }

  it("sets initial variables", function() {
    var directive = compileDirective();
    var scope = directive.isolateScope();
    expect(scope.loading).toBe(true);
    expect(scope.ipranges).toBe(IPRangesManager.getItems());
    expect(scope.iprangeManager).toBe(IPRangesManager);
    expect(scope.newRange).toBeNull();
    expect(scope.editIPRange).toBeNull();
    expect(scope.deleteIPRange).toBeNull();
  });

  describe("isSuperUser", function() {
    it("returns UsersManager.isSuperUser", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();

      var sentinel = {};
      spyOn(UsersManager, "isSuperUser").and.returnValue(sentinel);
      expect(scope.isSuperUser()).toBe(sentinel);
    });
  });

  describe("addRange with subnet", function() {
    it("reserved", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.subnet = {
        id: makeInteger(0, 100)
      };
      scope.addRange("reserved");
      expect(scope.newRange).toEqual({
        type: "reserved",
        subnet: scope.subnet.id,
        start_ip: "",
        end_ip: "",
        comment: ""
      });
    });

    it("dynamic", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.subnet = {
        id: makeInteger(0, 100)
      };
      scope.addRange("dynamic");
      expect(scope.newRange).toEqual({
        type: "dynamic",
        subnet: scope.subnet.id,
        start_ip: "",
        end_ip: "",
        comment: "Dynamic"
      });
    });
  });

  describe("addRange with vlan", function() {
    it("reserved", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.vlan = {
        id: makeInteger(0, 100)
      };
      scope.addRange("reserved");
      expect(scope.newRange).toEqual({
        type: "reserved",
        vlan: scope.vlan.id,
        start_ip: "",
        end_ip: "",
        comment: ""
      });
    });

    it("dynamic", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.vlan = {
        id: makeInteger(0, 100)
      };
      scope.addRange("dynamic");
      expect(scope.newRange).toEqual({
        type: "dynamic",
        vlan: scope.vlan.id,
        start_ip: "",
        end_ip: "",
        comment: "Dynamic"
      });
    });
  });

  describe("cancelAddRange", function() {
    it("clears newRange", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.newRange = {};
      scope.cancelAddRange();
      expect(scope.newRange).toBeNull();
    });
  });

  describe("ipRangeCanBeModified", function() {
    it("returns true for super user", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var range = {
        type: "dynamic"
      };
      spyOn(scope, "isSuperUser").and.returnValue(true);
      expect(scope.ipRangeCanBeModified(range)).toBe(true);
    });

    it("returns false for standard user and dynamic", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var range = {
        type: "dynamic"
      };
      spyOn(scope, "isSuperUser").and.returnValue(false);
      expect(scope.ipRangeCanBeModified(range)).toBe(false);
    });

    it("returns false for standard user who is not owner", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var user = {
        id: makeInteger(0, 100)
      };
      var range = {
        type: "reserved",
        user: makeInteger(101, 200)
      };
      spyOn(UsersManager, "getAuthUser").and.returnValue(user);
      spyOn(scope, "isSuperUser").and.returnValue(false);
      expect(scope.ipRangeCanBeModified(range)).toBe(false);
    });

    it("returns true for standard user who is owner", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var user = {
        id: makeInteger(0, 100)
      };
      var range = {
        type: "reserved",
        user: user.id
      };
      spyOn(UsersManager, "getAuthUser").and.returnValue(user);
      spyOn(scope, "isSuperUser").and.returnValue(false);
      expect(scope.ipRangeCanBeModified(range)).toBe(true);
    });
  });

  describe("isIPRangeInEditMode", function() {
    it("returns true when editIPRange", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var range = {};
      scope.editIPRange = range;
      expect(scope.isIPRangeInEditMode(range)).toBe(true);
    });

    it("returns false when editIPRange", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var range = {};
      scope.editIPRange = range;
      expect(scope.isIPRangeInEditMode({})).toBe(false);
    });
  });

  describe("ipRangeToggleEditMode", function() {
    it("clears deleteIPRange", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.deleteIPRange = {};
      scope.ipRangeToggleEditMode({});
      expect(scope.deleteIPRange).toBeNull();
    });

    it("clears editIPRange when already set", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var range = {};
      scope.editIPRange = range;
      scope.ipRangeToggleEditMode(range);
      expect(scope.editIPRange).toBeNull();
    });

    it("sets editIPRange when different range", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var range = {};
      var otherRange = {};
      scope.editIPRange = otherRange;
      scope.ipRangeToggleEditMode(range);
      expect(scope.editIPRange).toBe(range);
    });
  });

  describe("isIPRangeInDeleteMode", function() {
    it("return true when deleteIPRange is same", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var range = {};
      scope.deleteIPRange = range;
      expect(scope.isIPRangeInDeleteMode(range)).toBe(true);
    });

    it("return false when deleteIPRange is different", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var range = {};
      scope.deleteIPRange = range;
      expect(scope.isIPRangeInDeleteMode({})).toBe(false);
    });
  });

  describe("ipRangeEnterDeleteMode", function() {
    it("clears editIPRange and sets deleteIPRange", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var range = {};
      scope.editIPRange = {};
      scope.ipRangeEnterDeleteMode(range);
      expect(scope.editIPRange).toBeNull();
      expect(scope.deleteIPRange).toBe(range);
    });
  });

  describe("ipRangeCancelDelete", function() {
    it("clears deleteIPRange", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.deleteIPRange = {};
      scope.ipRangeCancelDelete();
      expect(scope.deleteIPRange).toBeNull();
    });
  });

  describe("ipRangeConfirmDelete", function() {
    it("calls deleteItem and clears deleteIPRange on resolve", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var range = {};
      scope.deleteIPRange = range;

      var defer = $q.defer();
      spyOn(IPRangesManager, "deleteItem").and.returnValue(defer.promise);
      scope.ipRangeConfirmDelete();

      expect(IPRangesManager.deleteItem).toHaveBeenCalledWith(range);
      defer.resolve();
      scope.$digest();

      expect(scope.deleteIPRange).toBeNull();
    });
  });

  describe("ipRangeSort", function() {
    it("returns sortable numeric IPv4 value", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var smaller = scope.ipRangeSort({ start_ip: "10.0.0.21" });
      var larger = scope.ipRangeSort({ start_ip: "10.0.0.200" });
      expect(smaller < larger).toBe(true);
    });

    it("returns sortable numeric IPv6 value", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var smaller = scope.ipRangeSort({ start_ip: "2001::21" });
      var larger = scope.ipRangeSort({ start_ip: "2001::200" });
      expect(smaller < larger).toBe(true);
    });
  });
});
