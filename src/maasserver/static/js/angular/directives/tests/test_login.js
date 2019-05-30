/* Copyright 2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for external login directive.
 */

describe("maasExternalLogin", function() {
  var $rootScope,
    $scope,
    $compile,
    redirectUrl,
    visitPageFunc,
    dischargeResponse;

  beforeEach(angular.mock.module("MAAS"));

  beforeEach(
    angular.mock.module(function($provide) {
      $provide.value("$window", {
        location: {
          replace: function(url) {
            redirectUrl = url;
          }
        }
      });

      // mock Bakery, since we can't use the real one.
      dischargeResponse = { status: 200 };
      $provide.factory("getBakery", function() {
        return function(visitPage) {
          visitPageFunc = visitPage;
          return {
            get: function(url, headers, callback) {
              callback(null, { currentTarget: dischargeResponse });
            }
          };
        };
      });
    })
  );

  // Create a new scope before each test.
  beforeEach(inject(function($injector, _$window_) {
    $rootScope = $injector.get("$rootScope");
    $scope = $rootScope.$new();
    $compile = $injector.get("$compile");
  }));

  function compileDirective() {
    var html =
      '<external-login auth-url="http://auth.example.com/"' +
      'next-path="/somepage">';
    var directive = $compile(html)($scope);
    $scope.$digest();
    return directive;
  }

  it("sets the externalAuthURL", function() {
    var directive = compileDirective();
    var scope = directive.isolateScope();
    expect(scope.externalAuthURL).toBe("http://auth.example.com/");
  });

  it("sets the login button URL", function() {
    var directive = compileDirective();
    // simulate login URL response
    visitPageFunc({ Info: { VisitURL: "http://auth.example.com/login" } });
    // $scope.$digest();
    var scope = directive.isolateScope();
    expect(scope.loginURL).toEqual("http://auth.example.com/login");
    var anchor = directive.find("a");
    expect(anchor.attr("href")).toBe("http://auth.example.com/login");
    // no error is shown
    expect(directive.find("#login-error").length).toBe(0);
  });

  it("redirects after login", function() {
    compileDirective();
    expect(redirectUrl).toBe("/somepage");
  });

  it("shows an error message if getting the visit URL fails", function() {
    dischargeResponse = { status: 500, responseText: "something broke!" };
    var directive = compileDirective();
    var error = directive.find("#login-error");
    expect(error.text().trim()).toBe(
      "Error getting login link:  something broke!"
    );
  });
});
