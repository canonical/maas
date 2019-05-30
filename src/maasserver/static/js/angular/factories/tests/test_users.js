/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for UsersManager.
 */

import { makeName } from "testing/utils";

describe("UsersManager", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Grab the needed angular pieces.
  var $q, $rootScope;
  beforeEach(inject(function($injector) {
    $q = $injector.get("$q");
    $rootScope = $injector.get("$rootScope");
  }));

  // Load the UsersManager, RegionConnection, and ErrorService.
  var UsersManager, RegionConnection, ErrorService;
  beforeEach(inject(function($injector) {
    UsersManager = $injector.get("UsersManager");
    RegionConnection = $injector.get("RegionConnection");
    ErrorService = $injector.get("ErrorService");
  }));

  // Make a fake user.
  var userId = 0;
  function makeUser() {
    return {
      id: userId++,
      username: makeName("username"),
      first_name: makeName("first_name"),
      last_name: makeName("last_name"),
      email: makeName("email"),
      is_superuser: false
    };
  }

  it("set requires attributes", function() {
    expect(UsersManager._pk).toBe("id");
    expect(UsersManager._handler).toBe("user");
    expect(UsersManager._batchSize).toBe(200);
    expect(UsersManager._authUser).toBeNull();
  });

  describe("getAuthUser", function() {
    it("returns _authUser", function() {
      var user = {};
      UsersManager._authUser = user;
      expect(UsersManager.getAuthUser()).toBe(user);
    });
  });

  describe("_loadAuthUser", function() {
    it("calls callMethod with user.auth_user", function() {
      spyOn(RegionConnection, "callMethod").and.returnValue($q.defer().promise);
      UsersManager._loadAuthUser();
      expect(RegionConnection.callMethod).toHaveBeenCalledWith(
        "user.auth_user",
        {}
      );
    });

    it("sets _authUser to resolved user", function() {
      var defer = $q.defer();
      spyOn(RegionConnection, "callMethod").and.returnValue(defer.promise);
      UsersManager._loadAuthUser();

      var user = makeUser();
      defer.resolve(user);
      $rootScope.$digest();

      expect(UsersManager._authUser).toBe(user);
    });

    it("doesnt change _authUser reference when user resolved", function() {
      var defer = $q.defer();
      spyOn(RegionConnection, "callMethod").and.returnValue(defer.promise);
      UsersManager._loadAuthUser();

      var firstUser = makeUser();
      UsersManager._authUser = firstUser;

      var secondUser = makeUser();
      defer.resolve(secondUser);
      $rootScope.$digest();

      expect(UsersManager._authUser).toBe(firstUser);
      expect(UsersManager._authUser).toEqual(secondUser);
    });

    it("raises error on error", function() {
      var defer = $q.defer();
      spyOn(RegionConnection, "callMethod").and.returnValue(defer.promise);
      spyOn(ErrorService, "raiseError");
      UsersManager._loadAuthUser();

      var error = makeName("error");
      defer.reject(error);
      $rootScope.$digest();

      expect(ErrorService.raiseError).toHaveBeenCalledWith(error);
    });
  });

  describe("_replaceItem", function() {
    it("replaces the _authUser without changing reference", function() {
      var firstUser = makeUser();
      UsersManager._authUser = firstUser;

      var secondUser = makeUser();
      secondUser.id = firstUser.id;
      UsersManager._replaceItem(secondUser);

      expect(UsersManager._authUser).toBe(firstUser);
      expect(UsersManager._authUser).toEqual(secondUser);
    });
  });

  describe("loadItems", function() {
    it("calls _loadAuthUser", function() {
      spyOn(RegionConnection, "callMethod").and.returnValue($q.defer().promise);
      spyOn(UsersManager, "_loadAuthUser");
      UsersManager.loadItems();
      expect(UsersManager._loadAuthUser).toHaveBeenCalled();
    });
  });

  describe("reloadItems", function() {
    it("calls _loadAuthUser", function() {
      spyOn(RegionConnection, "callMethod").and.returnValue($q.defer().promise);
      spyOn(UsersManager, "_loadAuthUser");
      UsersManager.reloadItems();
      expect(UsersManager._loadAuthUser).toHaveBeenCalled();
    });
  });

  describe("createAuthorisationToken", function() {
    it("calls user.create_authorisation_token", function() {
      spyOn(RegionConnection, "callMethod").and.returnValue($q.defer().promise);
      UsersManager.createAuthorisationToken();
      expect(RegionConnection.callMethod).toHaveBeenCalledWith(
        "user.create_authorisation_token",
        {}
      );
    });

    it("raises error on error", function() {
      var defer = $q.defer();
      spyOn(RegionConnection, "callMethod").and.returnValue(defer.promise);
      spyOn(ErrorService, "raiseError");
      UsersManager.createAuthorisationToken();

      var error = makeName("error");
      defer.reject(error);
      $rootScope.$digest();

      expect(ErrorService.raiseError).toHaveBeenCalledWith(error);
    });
  });

  describe("deleteAuthorisationToken", function() {
    it("calls user.delete_authorisation_token", function() {
      spyOn(RegionConnection, "callMethod").and.returnValue($q.defer().promise);

      var key = makeName("key");
      UsersManager.deleteAuthorisationToken(key);
      expect(RegionConnection.callMethod).toHaveBeenCalledWith(
        "user.delete_authorisation_token",
        { key: key }
      );
    });

    it("raises error on error", function() {
      var defer = $q.defer();
      spyOn(RegionConnection, "callMethod").and.returnValue(defer.promise);
      spyOn(ErrorService, "raiseError");

      var key = makeName("key");
      UsersManager.deleteAuthorisationToken(key);

      var error = makeName("error");
      defer.reject(error);
      $rootScope.$digest();

      expect(ErrorService.raiseError).toHaveBeenCalledWith(error);
    });
  });

  describe("hasGlobalPermission", function() {
    it("returns true if auth user has permission", function() {
      var user = {
        global_permissions: ["create_machine"]
      };
      UsersManager._authUser = user;
      expect(UsersManager.hasGlobalPermission("create_machine")).toBe(true);
    });

    it("returns false if auth user doesn't have permission", function() {
      var user = {
        global_permissions: ["create_machine"]
      };
      UsersManager._authUser = user;
      expect(UsersManager.hasGlobalPermission("create_device")).toBe(false);
    });

    it("returns false if auth user no global_permissions", function() {
      var user = {};
      UsersManager._authUser = user;
      expect(UsersManager.hasGlobalPermission("create_device")).toBe(false);
    });
  });
});
