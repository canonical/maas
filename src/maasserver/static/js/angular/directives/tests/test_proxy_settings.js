/* Copyright 2017 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for MAAS proxy settings directive.
 */

import template from "../../../../partials/proxy-settings.html";

describe("maasProxySettings", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Get required angular pieces and create a new scope before each test.
  var $scope,
    $compile,
    $q,
    $templateCache,
    ConfigsManager,
    ManagerHelperService;
  beforeEach(inject(function($rootScope, $injector) {
    $scope = $rootScope.$new();
    $compile = $injector.get("$compile");
    $q = $injector.get("$q");
    $templateCache = $injector.get("$templateCache");
    $templateCache.put("static/partials/proxy-settings.html", template);
    ConfigsManager = $injector.get("ConfigsManager");
    ManagerHelperService = $injector.get("ManagerHelperService");
  }));

  // Create the config options.
  var httpProxy, enableHttpProxy, usePeerProxy;
  beforeEach(function() {
    httpProxy = {
      name: "http_proxy",
      value: ""
    };
    enableHttpProxy = {
      name: "enable_http_proxy",
      value: true
    };
    usePeerProxy = {
      name: "use_peer_proxy",
      value: false
    };
    ConfigsManager._items = [httpProxy, enableHttpProxy, usePeerProxy];
  });

  // Return the compiled directive.
  function compileDirective() {
    var loadManagerDefer = $q.defer();
    spyOn(ManagerHelperService, "loadManager").and.returnValue(
      loadManagerDefer.promise
    );

    var html = "<div><maas-proxy-settings></maas-proxy-settings></div>";
    var directive = $compile(html)($scope);
    $scope.$digest();
    loadManagerDefer.resolve();
    $scope.$digest();

    return angular.element(directive.find("maas-proxy-settings"));
  }

  it("no-proxy without http proxy", function() {
    enableHttpProxy.value = false;
    usePeerProxy.value = false;
    httpProxy.value = "";
    var directive = compileDirective(
      "<maas-proxy-settings></maas-proxy-settings>"
    );
    var scope = directive.isolateScope();
    var enableProxyField = angular.element(
      directive.find("#id_proxy-enable_http_proxy")
    );
    var httpProxyField = angular.element(
      directive.find("#id_proxy-http_proxy")
    );
    var usePeerProxyField = angular.element(
      directive.find("#id_proxy-use_peer_proxy")
    );
    expect(scope.proxy_type).toBe("no-proxy");
    expect(enableProxyField.attr("value")).toBe("False");
    expect(httpProxyField.attr("value")).toBe(undefined);
    expect(usePeerProxyField.attr("value")).toBe("False");
  });

  it("no-proxy with http_proxy set", function() {
    enableHttpProxy.value = false;
    usePeerProxy.value = false;
    httpProxy.value = "http://proxy.example.com/";
    var directive = compileDirective(
      "<maas-proxy-settings></maas-proxy-settings>"
    );
    var scope = directive.isolateScope();
    var enableProxyField = angular.element(
      directive.find("#id_proxy-enable_http_proxy")
    );
    var httpProxyField = angular.element(
      directive.find("#id_proxy-http_proxy")
    );
    var usePeerProxyField = angular.element(
      directive.find("#id_proxy-use_peer_proxy")
    );
    expect(scope.proxy_type).toBe("no-proxy");
    expect(enableProxyField.attr("value")).toBe("False");
    expect(httpProxyField.attr("value")).toBe(undefined);
    expect(usePeerProxyField.attr("value")).toBe("False");
  });

  it("no-proxy with use_peer_proxy set", function() {
    enableHttpProxy.value = false;
    usePeerProxy.value = true;
    httpProxy.value = "http://peer-proxy.example.com/";
    var directive = compileDirective(
      "<maas-proxy-settings></maas-proxy-settings>"
    );
    var scope = directive.isolateScope();
    var enableProxyField = angular.element(
      directive.find("#id_proxy-enable_http_proxy")
    );
    var httpProxyField = angular.element(
      directive.find("#id_proxy-http_proxy")
    );
    var usePeerProxyField = angular.element(
      directive.find("#id_proxy-use_peer_proxy")
    );
    expect(scope.proxy_type).toBe("no-proxy");
    expect(enableProxyField.attr("value")).toBe("False");
    expect(httpProxyField.attr("value")).toBe(undefined);
    expect(usePeerProxyField.attr("value")).toBe("False");
  });

  it("builtin-proxy", function() {
    enableHttpProxy.value = true;
    usePeerProxy.value = false;
    httpProxy.value = "";
    var directive = compileDirective(
      "<maas-proxy-settings></maas-proxy-settings>"
    );
    var scope = directive.isolateScope();
    var enableProxyField = angular.element(
      directive.find("#id_proxy-enable_http_proxy")
    );
    var httpProxyField = angular.element(
      directive.find("#id_proxy-http_proxy")
    );
    var usePeerProxyField = angular.element(
      directive.find("#id_proxy-use_peer_proxy")
    );
    expect(scope.proxy_type).toBe("builtin-proxy");
    expect(enableProxyField.attr("value")).toBe("True");
    expect(httpProxyField.attr("value")).toBe(undefined);
    expect(usePeerProxyField.attr("value")).toBe("False");
  });

  it("builtin-proxy with use_peer_proxy set", function() {
    enableHttpProxy.value = true;
    usePeerProxy.value = true;
    httpProxy.value = "";
    var directive = compileDirective(
      "<maas-proxy-settings></maas-proxy-settings>"
    );
    var scope = directive.isolateScope();
    var enableProxyField = angular.element(
      directive.find("#id_proxy-enable_http_proxy")
    );
    var httpProxyField = angular.element(
      directive.find("#id_proxy-http_proxy")
    );
    var usePeerProxyField = angular.element(
      directive.find("#id_proxy-use_peer_proxy")
    );
    expect(scope.proxy_type).toBe("builtin-proxy");
    expect(enableProxyField.attr("value")).toBe("True");
    expect(httpProxyField.attr("value")).toBe(undefined);
    expect(usePeerProxyField.attr("value")).toBe("False");
  });

  it("external-proxy set", function() {
    enableHttpProxy.value = true;
    usePeerProxy.value = false;
    httpProxy.value = "http://proxy.example.com/";
    var directive = compileDirective(
      "<maas-proxy-settings></maas-proxy-settings>"
    );
    var scope = directive.isolateScope();
    var enableProxyField = angular.element(
      directive.find("#id_proxy-enable_http_proxy")
    );
    var httpProxyField = angular.element(
      directive.find("#id_proxy-http_proxy")
    );
    var usePeerProxyField = angular.element(
      directive.find("#id_proxy-use_peer_proxy")
    );
    expect(scope.proxy_type).toBe("external-proxy");
    expect(enableProxyField.attr("value")).toBe("True");
    expect(httpProxyField.attr("value")).toBe("http://proxy.example.com/");
    expect(usePeerProxyField.attr("value")).toBe("False");
  });

  it("peer-proxy set", function() {
    enableHttpProxy.value = true;
    usePeerProxy.value = true;
    httpProxy.value = "http://proxy.example.com/";
    var directive = compileDirective(
      "<maas-proxy-settings></maas-proxy-settings>"
    );
    var scope = directive.isolateScope();
    var enableProxyField = angular.element(
      directive.find("#id_proxy-enable_http_proxy")
    );
    var httpProxyField = angular.element(
      directive.find("#id_proxy-http_proxy")
    );
    var usePeerProxyField = angular.element(
      directive.find("#id_proxy-use_peer_proxy")
    );
    expect(scope.proxy_type).toBe("peer-proxy");
    expect(enableProxyField.attr("value")).toBe("True");
    expect(httpProxyField.attr("value")).toBe("http://proxy.example.com/");
    expect(usePeerProxyField.attr("value")).toBe("True");
  });
});
