/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for SSH keys directive.
 */

import { makeName } from "testing/utils";
import MockWebSocket from "testing/websocket";

describe("maasSshKeys", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Preload the $templateCache with empty contents. We only test the
  // controller of the directive, not the template.
  var $sce, $q, $templateCache;
  beforeEach(inject(function($injector) {
    $sce = $injector.get("$sce");
    $q = $injector.get("$q");
    $templateCache = $injector.get("$templateCache");
    $templateCache.put("static/partials/ssh-keys.html?v=undefined", "");
  }));

  // Load the required managers.
  var SSHKeysManager, ManagerHelperService;
  beforeEach(inject(function($injector) {
    SSHKeysManager = $injector.get("SSHKeysManager");
    ManagerHelperService = $injector.get("ManagerHelperService");
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
  function compileDirective() {
    var directive;
    var html = ["<div>", "<maas-ssh-keys></maas-ssh-keys>", "</div>"].join("");

    // Compile the directive.
    inject(function($compile) {
      directive = $compile(html)($scope);
    });

    // Perform the digest cycle to finish the compile.
    $scope.$digest();
    return directive.find("maas-ssh-keys");
  }

  it("sets initial variables", function() {
    var directive = compileDirective();
    var scope = directive.isolateScope();
    expect(scope.loading).toBe(true);
    expect(scope.keys).toBe(SSHKeysManager.getItems());
    expect(scope.groupedKeys).toEqual([]);
    expect(scope.add).toEqual({
      source: "lp",
      authId: "",
      key: "",
      error: null,
      saving: false
    });
    expect(scope.sourceTitles).toEqual({
      lp: "Launchpad",
      gh: "Github",
      upload: "Upload"
    });
    expect(scope.openRow).toBeNull();
    expect(scope.rowMode).toBeNull();
    expect(scope.trustAsHtml).toBe($sce.trustAsHtml);
  });

  it("clears loading once user manager loaded", function() {
    var defer = $q.defer();
    spyOn(ManagerHelperService, "loadManager").and.returnValue(defer.promise);
    var directive = compileDirective();
    var scope = directive.isolateScope();

    defer.resolve();
    $scope.$digest();
    expect(scope.loading).toBe(false);
  });

  it("updates groupedKeys when keys change", function() {
    var directive = compileDirective();
    var scope = directive.isolateScope();
    var lpMAAS1 = {
      keysource: {
        protocol: "lp",
        auth_id: "maas"
      },
      key: "1"
    };
    var lpMAAS2 = {
      keysource: {
        protocol: "lp",
        auth_id: "maas"
      },
      key: "2"
    };
    var lpMAAS3 = {
      keysource: {
        protocol: "lp",
        auth_id: "maas"
      },
      key: "3"
    };
    var lpBlake1 = {
      keysource: {
        protocol: "lp",
        auth_id: "blake"
      },
      key: "1"
    };
    var lpBlake2 = {
      keysource: {
        protocol: "lp",
        auth_id: "blake"
      },
      key: "2"
    };
    var ghBlake1 = {
      keysource: {
        protocol: "gh",
        auth_id: "blake"
      },
      key: "1"
    };
    var uploaded1 = {
      id: 1,
      keysource: null,
      key: "1"
    };
    var uploaded2 = {
      id: 2,
      keysource: null,
      key: "2"
    };
    var keys = [
      lpMAAS1,
      lpMAAS2,
      lpMAAS3,
      lpBlake1,
      lpBlake2,
      ghBlake1,
      uploaded1,
      uploaded2
    ];
    scope.keys.push.apply(scope.keys, keys);
    $scope.$digest();

    expect(scope.groupedKeys).toEqual([
      {
        id: "lp/maas",
        source: "lp",
        authId: "maas",
        keys: [lpMAAS1, lpMAAS2, lpMAAS3]
      },
      {
        id: "lp/blake",
        source: "lp",
        authId: "blake",
        keys: [lpBlake1, lpBlake2]
      },
      {
        id: "gh/blake",
        source: "gh",
        authId: "blake",
        keys: [ghBlake1]
      },
      {
        id: "upload/1",
        source: "upload",
        authId: "",
        keys: [uploaded1]
      },
      {
        id: "upload/2",
        source: "upload",
        authId: "",
        keys: [uploaded2]
      }
    ]);
  });

  describe("open", function() {
    it("sets openRow and rowMode", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var obj = {
        id: makeName("id")
      };
      var mode = makeName("mode");
      scope.open(obj, mode);
      expect(scope.openRow).toBe(obj.id);
      expect(scope.rowMode).toBe(mode);
    });
  });

  describe("close", function() {
    it("clears openRow", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.openRow = {};
      scope.close();
      expect(scope.openRow).toBeNull();
    });
  });

  describe("canImportKeys", function() {
    it("returns false if saving", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.add.saving = true;
      expect(scope.canImportKeys()).toBe(false);
    });

    it("returns false if lp source and no authId", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.add.saving = false;
      scope.add.source = "lp";
      scope.add.authId = "";
      expect(scope.canImportKeys()).toBe(false);
    });

    it("returns true if lp source and authId", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.add.saving = false;
      scope.add.source = "lp";
      scope.add.authId = makeName("auth");
      expect(scope.canImportKeys()).toBe(true);
    });

    it("returns false if gh source and no authId", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.add.saving = false;
      scope.add.source = "gh";
      scope.add.authId = "";
      expect(scope.canImportKeys()).toBe(false);
    });

    it("returns true if gh source and authId", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.add.saving = false;
      scope.add.source = "gh";
      scope.add.authId = makeName("auth");
      expect(scope.canImportKeys()).toBe(true);
    });

    it("returns false if uploaded without key", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.add.saving = false;
      scope.add.source = "upload";
      scope.add.key = "";
      expect(scope.canImportKeys()).toBe(false);
    });

    it("returns true if uploaded with key", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.add.saving = false;
      scope.add.source = "upload";
      scope.add.key = makeName("key");
      expect(scope.canImportKeys()).toBe(true);
    });
  });

  describe("importKeys", function() {
    it("does nothing if cannot import keys", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      spyOn(scope, "canImportKeys").and.returnValue(false);
      scope.add.source = "lp";
      spyOn(SSHKeysManager, "importKeys");
      scope.importKeys();
      expect(SSHKeysManager.importKeys).not.toHaveBeenCalled();
    });

    it("clears error and sets saving", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var defer = $q.defer();
      spyOn(SSHKeysManager, "importKeys").and.returnValue(defer.promise);
      spyOn(scope, "canImportKeys").and.returnValue(true);
      scope.add.source = "lp";
      scope.add.authId = makeName("auth");
      scope.add.error = {};
      scope.add.saving = false;
      scope.importKeys();
      expect(scope.add.error).toBeNull();
      expect(scope.add.saving).toBe(true);
      expect(SSHKeysManager.importKeys).toHaveBeenCalledWith({
        protocol: "lp",
        auth_id: scope.add.authId
      });
    });

    it("import - clears saving on resolve", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var defer = $q.defer();
      spyOn(SSHKeysManager, "importKeys").and.returnValue(defer.promise);
      spyOn(scope, "canImportKeys").and.returnValue(true);
      scope.add.source = "lp";
      scope.add.authId = makeName("auth");
      scope.importKeys();

      expect(scope.add.error).toBeNull();
      expect(scope.add.saving).toBe(true);
      expect(SSHKeysManager.importKeys).toHaveBeenCalledWith({
        protocol: "lp",
        auth_id: scope.add.authId
      });
      defer.resolve();
      $scope.$digest();

      expect(scope.add.saving).toBe(false);
      expect(scope.add.source).toBe("lp");
      expect(scope.add.authId).toBe("");
      expect(scope.add.key).toBe("");
    });

    it("import - sets error on reject", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var defer = $q.defer();
      spyOn(SSHKeysManager, "importKeys").and.returnValue(defer.promise);
      spyOn(scope, "canImportKeys").and.returnValue(true);
      scope.add.source = "lp";
      scope.add.authId = makeName("auth");
      scope.importKeys();

      expect(scope.add.error).toBeNull();
      expect(scope.add.saving).toBe(true);
      expect(SSHKeysManager.importKeys).toHaveBeenCalledWith({
        protocol: "lp",
        auth_id: scope.add.authId
      });
      var error = makeName("error");
      defer.reject(error);
      $scope.$digest();

      expect(scope.add.saving).toBe(false);
      expect(scope.add.error).toBe(error);
    });

    it("import - handles __all__ in error on reject", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var defer = $q.defer();
      spyOn(SSHKeysManager, "importKeys").and.returnValue(defer.promise);
      spyOn(scope, "canImportKeys").and.returnValue(true);
      scope.add.source = "lp";
      scope.add.authId = makeName("auth");
      scope.importKeys();

      expect(scope.add.error).toBeNull();
      expect(scope.add.saving).toBe(true);
      expect(SSHKeysManager.importKeys).toHaveBeenCalledWith({
        protocol: "lp",
        auth_id: scope.add.authId
      });
      var error = {
        __all__: [makeName("error")]
      };
      defer.reject(angular.toJson(error));
      $scope.$digest();

      expect(scope.add.saving).toBe(false);
      expect(scope.add.error).toBe(error.__all__[0]);
    });

    it("create - clears saving on resolve", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var defer = $q.defer();
      spyOn(SSHKeysManager, "createItem").and.returnValue(defer.promise);
      spyOn(scope, "canImportKeys").and.returnValue(true);
      scope.add.source = "upload";
      scope.add.key = makeName("key");
      scope.importKeys();

      expect(scope.add.error).toBeNull();
      expect(scope.add.saving).toBe(true);
      expect(SSHKeysManager.createItem).toHaveBeenCalledWith({
        key: scope.add.key
      });
      defer.resolve();
      $scope.$digest();

      expect(scope.add.saving).toBe(false);
      expect(scope.add.source).toBe("lp");
      expect(scope.add.authId).toBe("");
      expect(scope.add.key).toBe("");
    });

    it("create - sets error on reject", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var defer = $q.defer();
      spyOn(SSHKeysManager, "createItem").and.returnValue(defer.promise);
      spyOn(scope, "canImportKeys").and.returnValue(true);
      scope.add.source = "upload";
      scope.add.key = makeName("key");
      scope.importKeys();

      expect(scope.add.error).toBeNull();
      expect(scope.add.saving).toBe(true);
      expect(SSHKeysManager.createItem).toHaveBeenCalledWith({
        key: scope.add.key
      });
      var error = {
        key: [makeName("error")]
      };
      defer.reject(angular.toJson(error));
      $scope.$digest();

      expect(scope.add.saving).toBe(false);
      expect(scope.add.error).toBe(error.key[0]);
    });
  });

  describe("importKeys", function() {
    it("calls deleteItem on all keys", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var obj = {
        keys: [{}, {}]
      };
      spyOn(SSHKeysManager, "deleteItem");
      scope.confirmDelete(obj);
      expect(SSHKeysManager.deleteItem.calls.argsFor(0)).toEqual([obj.keys[0]]);
      expect(SSHKeysManager.deleteItem.calls.argsFor(1)).toEqual([obj.keys[1]]);
    });
  });
});
