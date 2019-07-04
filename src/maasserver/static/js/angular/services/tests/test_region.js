/* Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for RegionConnection.
 */

import { makeName } from "testing/utils";
import MockWebSocket from "testing/websocket";

describe("RegionConnection", function() {
  // Load the MAAS module to test.
  beforeEach(angular.mock.module("MAAS"));

  // Grab the needed angular pieces.
  var $timeout, $rootScope, $q, $cookies, $window;
  beforeEach(inject(function($injector) {
    $timeout = $injector.get("$timeout");
    $rootScope = $injector.get("$rootScope");
    $q = $injector.get("$q");
    $cookies = $injector.get("$cookies");
    $window = $injector.get("$window");
  }));

  // Load the RegionConnection factory.
  let RegionConnection, webSocket;
  beforeEach(inject(function($injector) {
    RegionConnection = $injector.get("RegionConnection");

    // Mock buildSocket so an actual connection is not made.
    webSocket = new MockWebSocket();
    spyOn(RegionConnection, "buildSocket").and.returnValue(webSocket);
  }));

  describe("newRequestId", function() {
    it("starts at 1", function() {
      expect(RegionConnection.newRequestId()).toBe(1);
    });

    it("increments by 1", function() {
      expect(RegionConnection.newRequestId()).toBe(1);
      expect(RegionConnection.newRequestId()).toBe(2);
      expect(RegionConnection.newRequestId()).toBe(3);
    });
  });

  describe("registerHandler", function() {
    var testHandler1, testHandler2;
    beforeEach(function() {
      testHandler1 = function() {};
      testHandler2 = function() {};
    });

    it("throws error on unknown handler", function() {
      expect(function() {
        RegionConnection.registerHandler("unknown", function() {});
      }).toThrow(new Error("Invalid handler: unknown"));
    });

    it("throws error non-functions", function() {
      expect(function() {
        RegionConnection.registerHandler("open", {});
      }).toThrow(new Error("Requires a function to register a handler."));
    });

    it("registers open handlers", function() {
      RegionConnection.registerHandler("open", testHandler1);
      RegionConnection.registerHandler("open", testHandler2);
      expect(RegionConnection.handlers.open).toEqual([
        testHandler1,
        testHandler2
      ]);
    });

    it("registers error handlers", function() {
      RegionConnection.registerHandler("error", testHandler1);
      RegionConnection.registerHandler("error", testHandler2);
      expect(RegionConnection.handlers.error).toEqual([
        testHandler1,
        testHandler2
      ]);
    });

    it("registers close handlers", function() {
      RegionConnection.registerHandler("close", testHandler1);
      RegionConnection.registerHandler("close", testHandler2);
      expect(RegionConnection.handlers.close).toEqual([
        testHandler1,
        testHandler2
      ]);
    });
  });

  describe("unregisterHandler", function() {
    var testHandler1, testHandler2;
    beforeEach(function() {
      testHandler1 = function() {};
      testHandler2 = function() {};
    });

    it("throws error on unknown handler", function() {
      expect(function() {
        RegionConnection.unregisterHandler("unknown", function() {});
      }).toThrow(new Error("Invalid handler: unknown"));
    });

    it("ignores unregistered handler", function() {
      RegionConnection.registerHandler("open", testHandler1);
      RegionConnection.unregisterHandler("open", testHandler2);
      expect(RegionConnection.handlers.open).toEqual([testHandler1]);
    });

    it("unregisters open handler", function() {
      RegionConnection.registerHandler("open", testHandler1);
      RegionConnection.unregisterHandler("open", testHandler1);
      expect(RegionConnection.handlers.open.length).toBe(0);
    });

    it("unregisters error handler", function() {
      RegionConnection.registerHandler("error", testHandler1);
      RegionConnection.unregisterHandler("error", testHandler1);
      expect(RegionConnection.handlers.error.length).toBe(0);
    });

    it("unregisters close handler", function() {
      RegionConnection.registerHandler("close", testHandler1);
      RegionConnection.unregisterHandler("close", testHandler1);
      expect(RegionConnection.handlers.close.length).toBe(0);
    });
  });

  describe("registerNotifier", function() {
    it("throws error non-functions", function() {
      expect(function() {
        RegionConnection.registerNotifier("testing", {});
      }).toThrow(new Error("Requires a function to register a notifier."));
    });

    it("adds handler", function() {
      var handler = function() {};
      RegionConnection.registerNotifier("testing", handler);
      expect(RegionConnection.notifiers.testing).toEqual([handler]);
    });

    it("adds multiple handlers", function() {
      var handler1 = function() {};
      var handler2 = function() {};
      RegionConnection.registerNotifier("testing", handler1);
      RegionConnection.registerNotifier("testing", handler2);
      expect(RegionConnection.notifiers.testing).toEqual([handler1, handler2]);
    });
  });

  describe("unregisterNotifier", function() {
    it("removes handler", function() {
      var handler = function() {};
      RegionConnection.registerNotifier("testing", handler);
      RegionConnection.unregisterNotifier("testing", handler);
      expect(RegionConnection.notifiers.testing.length).toBe(0);
    });

    it("removes only one handler", function() {
      var handler1 = function() {};
      var handler2 = function() {};
      RegionConnection.registerNotifier("testing", handler1);
      RegionConnection.registerNotifier("testing", handler2);
      RegionConnection.unregisterNotifier("testing", handler1);
      expect(RegionConnection.notifiers.testing).toEqual([handler2]);
    });

    it("does nothing if notification name never registered", function() {
      RegionConnection.unregisterNotifier("testing", {});
      expect(RegionConnection.notifiers.testing).toBeUndefined();
    });

    it("does nothing if handler never registered", function() {
      var handler1 = function() {};
      var handler2 = function() {};
      RegionConnection.registerNotifier("testing", handler1);
      RegionConnection.unregisterNotifier("testing", handler2);
      expect(RegionConnection.notifiers.testing).toEqual([handler1]);
    });
  });

  describe("isConnected", function() {
    it("returns true in STATE.UP", function() {
      RegionConnection.state = RegionConnection.STATE.UP;
      expect(RegionConnection.isConnected()).toBe(true);
    });

    it("returns false in STATE.DOWN", function() {
      RegionConnection.state = RegionConnection.STATE.DOWN;
      expect(RegionConnection.isConnected()).toBe(false);
    });

    it("returns false in STATE.RETRY", function() {
      RegionConnection.state = RegionConnection.STATE.RETRY;
      expect(RegionConnection.isConnected()).toBe(false);
    });
  });

  describe("scheduleEnsureConnection", function() {
    it("schedules ensureConnection to run", function() {
      spyOn(RegionConnection, "ensureConnection");
      RegionConnection.scheduleEnsureConnection();
      $timeout.flush();
      expect(RegionConnection.ensureConnection).toHaveBeenCalled();
    });

    it("does not schedule itself multiple times", function() {
      spyOn(RegionConnection, "ensureConnection");
      RegionConnection.scheduleEnsureConnection();
      RegionConnection.scheduleEnsureConnection();
      RegionConnection.scheduleEnsureConnection();
      RegionConnection.scheduleEnsureConnection();
      RegionConnection.scheduleEnsureConnection();
      $timeout.flush();
      expect(RegionConnection.ensureConnection).toHaveBeenCalledTimes(1);
    });
  });

  describe("ensureConnection", function() {
    beforeEach(function() {
      spyOn(RegionConnection, "scheduleEnsureConnection");
      spyOn(RegionConnection, "retry");
      spyOn(RegionConnection, "connect");
      spyOn(RegionConnection, "ping");
    });

    it("schedules itself to run again later", function() {
      RegionConnection.ensureConnection();
      expect(RegionConnection.scheduleEnsureConnection).toHaveBeenCalled();
    });

    it("calls retry() if in UP state with missed pings", function() {
      RegionConnection.state = RegionConnection.STATE.UP;
      for (let i = 0; i < RegionConnection.maxMissedPings; i++) {
        RegionConnection.pingsInFlight.add(i);
      }
      RegionConnection.ensureConnection();
      expect(RegionConnection.retry).toHaveBeenCalled();
    });

    it("calls retry() if UP with missed requests and pings", function() {
      RegionConnection.state = RegionConnection.STATE.UP;
      RegionConnection.pingsInFlight.add(1);
      for (let i = 0; i < RegionConnection.maxPatience - 1; i++) {
        RegionConnection.requests[i] = {};
      }
      RegionConnection.ensureConnection();
      expect(RegionConnection.retry).toHaveBeenCalled();
    });

    it("calls ping() if in UP state", function() {
      RegionConnection.state = RegionConnection.STATE.UP;
      RegionConnection.ensureConnection();
      expect(RegionConnection.ping).toHaveBeenCalled();
    });

    it("calls retry() and connect() if in RETRY state", function() {
      RegionConnection.state = RegionConnection.STATE.RETRY;
      RegionConnection.ensureConnection();
      expect(RegionConnection.retry).toHaveBeenCalled();
      expect(RegionConnection.connect).toHaveBeenCalled();
    });
  });

  describe("connect", function() {
    var url = "http://test-url",
      buildUrlSpy;
    beforeEach(function() {
      buildUrlSpy = spyOn(RegionConnection, "_buildUrl");
      buildUrlSpy.and.returnValue(url);
    });

    it("sets url", function() {
      RegionConnection.connect();
      expect(RegionConnection.url).toBe(url);
    });

    it("calls buildSocket with url", function() {
      RegionConnection.connect();
      expect(RegionConnection.buildSocket).toHaveBeenCalledWith(url);
    });

    it("sets websocket handlers", function() {
      RegionConnection.connect();
      expect(webSocket.onopen).not.toBeNull();
      expect(webSocket.onerror).not.toBeNull();
      expect(webSocket.onclose).not.toBeNull();
    });

    it("sets connect to true when onopen called", function() {
      RegionConnection.connect();
      webSocket.onopen({});
      expect(RegionConnection.isConnected()).toBe(true);
    });

    it("calls error handler when onerror called", function(done) {
      var evt_obj = {};
      RegionConnection.registerHandler("error", function(evt) {
        expect(evt).toBe(evt_obj);
        done();
      });
      RegionConnection.connect();
      webSocket.onerror(evt_obj);
    });

    it("isConnected() is false when onclose called", function() {
      RegionConnection.connect();
      webSocket.onclose({});
      expect(RegionConnection.isConnected()).toBe(false);
    });

    it("calls close handler when onclose called", function(done) {
      var evt_obj = {};
      RegionConnection.registerHandler("close", function(evt) {
        expect(evt).toBe(evt_obj);
        done();
      });
      RegionConnection.connect();
      webSocket.onclose(evt_obj);
    });

    it("calls onMessage when onmessage called", function() {
      var sampleData = { sample: "data" };
      spyOn(RegionConnection, "onMessage");
      RegionConnection.connect();
      webSocket.onmessage({ data: angular.toJson(sampleData) });
      expect(RegionConnection.onMessage).toHaveBeenCalledWith(sampleData);
    });
  });

  describe("retry", function() {
    beforeEach(function() {
      spyOn(webSocket, "close");
    });

    it("sets state to RETRY", function() {
      RegionConnection.connect("");
      RegionConnection.retry();
      expect(RegionConnection.state).toBe(RegionConnection.STATE.RETRY);
    });

    it("calls close on websocket", function() {
      RegionConnection.connect("");
      RegionConnection.retry();
      expect(webSocket.close).toHaveBeenCalled();
    });

    it("sets websocket to null", function() {
      RegionConnection.connect("");
      RegionConnection.retry();
      expect(RegionConnection.websocket).toBeNull();
    });

    it("clears out event handlers", function() {
      RegionConnection.connect("");
      let ws = RegionConnection.websocket;
      RegionConnection.retry();
      expect(ws.onopen).toBeNull();
      expect(ws.onerror).toBeNull();
      expect(ws.onclose).toBeNull();
    });
  });

  describe("_getProtocol", function() {
    it("returns window protocol", function() {
      expect(RegionConnection._getProtocol()).toBe($window.location.protocol);
    });
  });

  describe("_buildUrl", function() {
    it("returns url from $window.location", function() {
      expect(RegionConnection._buildUrl()).toBe(
        "ws://" +
          $window.location.hostname +
          ":" +
          $window.location.port +
          $window.location.pathname +
          "ws"
      );
    });

    it("uses wss connection if https protocol", function() {
      spyOn(RegionConnection, "_getProtocol").and.returnValue("https:");
      expect(RegionConnection._buildUrl()).toBe(
        "wss://" +
          $window.location.hostname +
          ":" +
          $window.location.port +
          $window.location.pathname +
          "ws"
      );
    });

    it("uses path from base[href]", function() {
      var path = makeName("path");
      var fakeElement = {
        attr: function(attr) {
          expect(attr).toBe("href");
          return path;
        },
        data: function(attr) {
          return undefined;
        }
      };
      spyOn(angular, "element").and.returnValue(fakeElement);

      expect(RegionConnection._buildUrl()).toBe(
        "ws://" +
          $window.location.hostname +
          ":" +
          $window.location.port +
          path +
          "/ws"
      );

      // Reset angular.element so the test will complete successfully as
      // angular.mock requires the actual call to work for afterEach.
      angular.element.and.callThrough();
    });

    it("uses port from data-websocket-port", function() {
      var port = "8888";
      var fakeElement = {
        attr: function(attr) {
          return undefined;
        },
        data: function(attr) {
          expect(attr).toBe("websocket-port");
          return port;
        }
      };
      spyOn(angular, "element").and.returnValue(fakeElement);

      expect(RegionConnection._buildUrl()).toBe(
        "ws://" +
          $window.location.hostname +
          ":" +
          port +
          $window.location.pathname +
          "ws"
      );

      // Reset angular.element so the test will complete successfully as
      // angular.mock requires the actual call to work for afterEach.
      angular.element.and.callThrough();
    });

    it("doesnt include ':' when no port given", function() {
      if (
        angular.isString($window.location.port) &&
        $window.location.port.length > 0
      ) {
        expect(RegionConnection._buildUrl()).toBe(
          "ws://" +
            $window.location.hostname +
            ":" +
            $window.location.port +
            $window.location.pathname +
            "ws"
        );
      } else {
        expect(RegionConnection._buildUrl()).toBe(
          "ws://" + $window.location.hostname + $window.location.pathname + "ws"
        );
      }
    });

    it("includes csrftoken if cookie defined", function() {
      var csrftoken = makeName("csrftoken");
      // No need to organize a cleanup: cookies are reset before each
      // test.
      if (angular.isFunction($cookies.put)) {
        $cookies.put("csrftoken", csrftoken);
      } else {
        $cookies.csrftoken = csrftoken;
      }
      expect(RegionConnection._buildUrl()).toBe(
        "ws://" +
          $window.location.hostname +
          ":" +
          $window.location.port +
          $window.location.pathname +
          "ws" +
          "?csrftoken=" +
          csrftoken
      );
    });
  });

  describe("defaultConnect", function() {
    it("resolve defer if already connected", function(done) {
      RegionConnection.state = RegionConnection.STATE.UP;
      RegionConnection.defaultConnect().then(function() {
        done();
      });
      $timeout.flush();
    });

    it("resolves defer once open handler is called", function(done) {
      RegionConnection.defaultConnect().then(function() {
        expect(RegionConnection.handlers.open).toEqual([]);
        expect(RegionConnection.handlers.error).toEqual([]);
        done();
      });
    });

    it("rejects defer once error handler is called", function(done) {
      spyOn(RegionConnection, "connect");
      RegionConnection.defaultConnect().then(null, function() {
        expect(RegionConnection.handlers.open).toEqual([]);
        expect(RegionConnection.handlers.error).toEqual([]);
        done();
      });
      angular.forEach(RegionConnection.handlers.error, function(func) {
        func();
      });
    });
  });

  describe("onMessage", function() {
    it("calls onResponse for a response message", function() {
      spyOn(RegionConnection, "onResponse");
      var msg = { type: 1 };
      RegionConnection.onMessage(msg);
      expect(RegionConnection.onResponse).toHaveBeenCalledWith(msg);
    });

    it("calls onNotify for a notify message", function() {
      spyOn(RegionConnection, "onNotify");
      var msg = { type: 2 };
      RegionConnection.onMessage(msg);
      expect(RegionConnection.onNotify).toHaveBeenCalledWith(msg);
    });
  });

  describe("onResponse", function() {
    it("resolves defer inside of rootScope", function(done) {
      var result = {};
      var requestId = RegionConnection.newRequestId();
      var defer = $q.defer();
      defer.promise.then(function(msg_result) {
        expect(msg_result).toBe(result);
        done();
      });

      spyOn($rootScope, "$apply").and.callThrough();

      RegionConnection.callbacks[requestId] = defer;
      RegionConnection.onResponse({
        type: 1,
        rtype: 0,
        request_id: requestId,
        result: result
      });
      expect($rootScope.$apply).toHaveBeenCalled();
      expect(RegionConnection.callbacks[requestId]).toBeUndefined();
    });

    it("rejects defer inside of rootScope", function(done) {
      var error = {};
      var requestId = RegionConnection.newRequestId();
      var defer = $q.defer();
      defer.promise.then(null, function(msg_error) {
        expect(msg_error).toBe(error);
        done();
      });

      spyOn($rootScope, "$apply").and.callThrough();

      RegionConnection.callbacks[requestId] = defer;
      RegionConnection.onResponse({
        type: 1,
        rtype: 1,
        request_id: requestId,
        error: error
      });
      expect($rootScope.$apply).toHaveBeenCalled();
      expect(RegionConnection.callbacks[requestId]).toBeUndefined();
    });

    it("rejects defer with original request if requested", function(done) {
      var error = {};
      var requestId = RegionConnection.newRequestId();
      var defer = $q.defer();
      var request = { expected: "request " };
      defer.promise.then(null, function(result) {
        expect(result.error).toBe(error);
        expect(result.request).toBe(request);
        done();
      });

      spyOn($rootScope, "$apply").and.callThrough();

      RegionConnection.callbacks[requestId] = defer;
      RegionConnection.requests[requestId] = request;
      RegionConnection.onResponse({
        type: 1,
        rtype: 1,
        request_id: requestId,
        error: error
      });
      expect($rootScope.$apply).toHaveBeenCalled();
      expect(RegionConnection.callbacks[requestId]).toBeUndefined();
      expect(RegionConnection.requests[requestId]).toBeUndefined();
    });
  });

  describe("onNotify", function() {
    it("calls handler for notification", function(done) {
      var name = "test";
      var action = "update";
      var data = 12;
      RegionConnection.registerNotifier(name, function(msg_action, msg_data) {
        expect(msg_action).toBe(action);
        expect(msg_data).toBe(data);
        done();
      });

      RegionConnection.onNotify({
        type: 2,
        name: name,
        action: action,
        data: data
      });
    });

    it("calls all handlers for notification", function() {
      var name = "test";
      var handler1 = jasmine.createSpy();
      var handler2 = jasmine.createSpy();
      RegionConnection.registerNotifier(name, handler1);
      RegionConnection.registerNotifier(name, handler2);

      RegionConnection.onNotify({
        type: 2,
        name: name,
        action: "delete",
        data: 12
      });
      expect(handler1).toHaveBeenCalled();
      expect(handler2).toHaveBeenCalled();
    });
  });

  describe("callMethod", function() {
    var promise, defer;
    beforeEach(function() {
      promise = {};
      defer = { promise: promise };
      spyOn($q, "defer").and.returnValue(defer);
      spyOn(webSocket, "send");
      RegionConnection.connect("");
    });

    it("adds defer to callbacks", function() {
      RegionConnection.callMethod("testing_method", {});
      expect(RegionConnection.callbacks[RegionConnection.requestId]).toBe(
        defer
      );
    });

    it("remembers request if requested", function() {
      var params = { foo: "bar" };
      RegionConnection.callMethod("testing_method", params, true);
      expect(RegionConnection.callbacks[RegionConnection.requestId]).toBe(
        defer
      );
      var requests = RegionConnection.requests;
      expect(requests[RegionConnection.requestId].method).toBe(
        "testing_method"
      );
      expect(requests[RegionConnection.requestId].params).toBe(params);
    });

    it("returns defer promise", function() {
      expect(RegionConnection.callMethod("testing_method", {})).toBe(promise);
    });

    it("sends JSON encoded message", function() {
      var method = "testing_method";
      var params = { arg1: 1, arg2: 2 };
      RegionConnection.callMethod(method, params);
      expect(webSocket.send).toHaveBeenCalledWith(
        angular.toJson({
          type: 0,
          request_id: RegionConnection.requestId,
          method: method,
          params: params
        })
      );
    });
  });
});
