/* Copyright 2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for user preference keys directive.
 */

import { makeName } from "testing/utils";

describe("maasPrefKeys", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Inject a fake RegionConnection.
  var RegionConnection;
  beforeEach(function() {
    RegionConnection = {
      defaultConnect: jasmine.createSpy("defaultConnect")
    };

    // Inject the fake RegionConnection into the provider so
    // when the directive is created if will use this
    // RegionConnection object instead of the one provided by
    // angular.
    angular.mock.module(function($provide) {
      $provide.value("RegionConnection", RegionConnection);
    });
  });

  // Inject a fake UsersManager.
  var UsersManager;
  beforeEach(function() {
    UsersManager = {
      createAuthorisationToken: jasmine.createSpy("createAuthorisationToken"),
      deleteAuthorisationToken: jasmine.createSpy("deleteAuthorisationToken")
    };

    // Inject the fake UsersManager into the provider so
    // when the directive is created if will use this
    // UsersManager object instead of the one provided by
    // angular.
    angular.mock.module(function($provide) {
      $provide.value("UsersManager", UsersManager);
    });
  });

  // Make token for directive.
  function makeToken() {
    var key = makeName("key");
    var secret = makeName("secret");
    var customerKey = makeName("customerKey");
    var customerName = makeName("customerName");
    return {
      key: key,
      secret: secret,
      customer: {
        key: customerKey,
        name: customerName
      }
    };
  }

  // Grab the needed angular pieces.
  var $rootScope, $scope, $q;
  beforeEach(inject(function($injector) {
    $rootScope = $injector.get("$rootScope");
    $q = $injector.get("$q");
    $scope = $rootScope.$new();
  }));

  // Create a default connection.
  var connectDefer;
  beforeEach(function() {
    connectDefer = $q.defer();
    RegionConnection.defaultConnect.and.returnValue(connectDefer.promise);
  });

  // Compile the directive.
  function compileDirective() {
    var directive;
    var html = [
      "<div>",
      "<div maas-pref-keys>",
      '<ul class="p-list" maas-pref-keys-inject="key_li">',
      "</ul>",
      "<a maas-pref-keys-add>Add</a>",
      '<script type="text/ng-template" id="key_li">',
      '<li maas-pref-key="{$ token.key $}">',
      "<span>",
      "{$ token.consumer.key $}:",
      "{$ token.key $}:",
      "{$ token.secret $}",
      "</span>",
      "<a maas-pref-key-delete>Delete</a>",
      "</li>",
      "</script>",
      "<div>",
      "</div>"
    ].join("");

    // Compile the directive.
    inject(function($compile) {
      directive = $compile(html)($scope);
    });

    // Perform the digest cycle to finish the compile.
    $scope.$digest();
    return angular.element(directive.find("div[maas-pref-keys]"));
  }

  describe("integration", function() {
    it("add/remove token", function() {
      var token = makeToken();
      var createDefer = $q.defer();
      var deleteDefer = $q.defer();
      UsersManager.createAuthorisationToken.and.returnValue(
        createDefer.promise
      );
      UsersManager.deleteAuthorisationToken.and.returnValue(
        deleteDefer.promise
      );

      var directive = compileDirective();
      var addDirective = angular.element(
        directive.find("a[maas-pref-keys-add]")
      );
      addDirective.click();

      connectDefer.resolve();
      createDefer.resolve(token);
      $scope.$digest();

      var injectDirective = angular.element(
        directive.find("ul[maas-pref-keys-inject]")
      );
      expect(injectDirective.children().length).toBe(1);

      var deleteDirective = angular.element(
        directive.find("a[maas-pref-key-delete]")
      );
      deleteDirective.click();

      deleteDefer.resolve();
      $scope.$digest();

      expect(UsersManager.deleteAuthorisationToken).toHaveBeenCalledWith(
        token.key
      );
      expect(injectDirective.children().length).toBe(0);
    });
  });
});
