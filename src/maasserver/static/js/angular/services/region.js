/* Copyright 2015-2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Region Connection
 *
 * Provides the websocket connection between the client and the MAAS regiond
 * service.
 */

// Message types
const MSG_TYPE = {
  REQUEST: 0,
  RESPONSE: 1,
  NOTIFY: 2,
  PING: 3,
  PING_REPLY: 4
};

// Response types
const RESPONSE_TYPE = {
  SUCCESS: 0,
  ERROR: 1
};

const REGION_STATE = {
  DOWN: 0,
  UP: 1,
  RETRY: 2
};

class RegionConnection {
  /* @ngInject */
  constructor($q, $rootScope, $timeout, $window, $cookies, LogService) {
    this.$q = $q;
    this.$rootScope = $rootScope;
    this.$timeout = $timeout;
    this.$window = $window;
    this.$cookies = $cookies;
    this.log = LogService;

    // Expose this constant so the tests can access it.
    this.STATE = REGION_STATE;

    this.callbacks = {};
    this.requests = {};
    this.pingsInFlight = new Set();
    this.requestId = 0;
    this.url = null;
    this.websocket = null;
    this.state = REGION_STATE.DOWN;
    this.ensureConnectionPromise = null;
    this.connectionCheckInterval = 5000;
    this.maxMissedPings = 5;
    this.maxPatience = 5;
    this.error = null;

    // Defer used for defaultConnect. If defaultConnect is called
    // quickly only the first one will start the connection. The
    // remaining will recieve this defer.
    this.defaultConnectDefer = null;

    // List of functions to call when a WebSocket event occurs. Each
    // function will get the WebSocket event passed to it.
    this.handlers = {
      open: [],
      error: [],
      close: []
    };

    // Object containing a fields with list of functions. When
    // a NOTIFY message is received it will match the name to a field
    // in this object. If the field exists in the object the list
    // of functions will be called with the action and obj_id.
    this.notifiers = {};
  }

  // Return a new request id.
  newRequestId() {
    this.requestId += 1;
    return this.requestId;
  }

  // Register event handler.
  registerHandler(name, func) {
    if (!angular.isDefined(this.handlers[name])) {
      throw new Error("Invalid handler: " + name);
    }
    if (!angular.isFunction(func)) {
      throw new Error("Requires a function to register a handler.");
    }
    this.handlers[name].push(func);
  }

  // Unregister event handler.
  unregisterHandler(name, func) {
    if (!angular.isDefined(this.handlers[name])) {
      throw new Error("Invalid handler: " + name);
    }
    let idx = this.handlers[name].indexOf(func);
    if (idx >= 0) {
      this.handlers[name].splice(idx, 1);
    }
  }

  // Register notification handler.
  registerNotifier(name, func) {
    if (!angular.isFunction(func)) {
      throw new Error("Requires a function to register a notifier.");
    }
    if (angular.isUndefined(this.notifiers[name])) {
      this.notifiers[name] = [];
    }
    this.notifiers[name].push(func);
  }

  // Unregister notification handler.
  unregisterNotifier(name, func) {
    if (angular.isUndefined(this.notifiers[name])) {
      return;
    }
    let idx = this.notifiers[name].indexOf(func);
    if (idx >= 0) {
      this.notifiers[name].splice(idx, 1);
    }
  }

  // Return True if currently connected to region.
  isConnected() {
    return this.state === REGION_STATE.UP;
  }

  // Builds the websocket connection.
  buildSocket(url) {
    return new WebSocket(url);
  }

  send(request) {
    if (this.state !== REGION_STATE.UP) {
      this.log.warn(
        "Sent request while region connection not available:",
        request
      );
    }
    // XXX mpontillo 2018-11-19: really we should handle errors here
    // in a more robust way, but that's a bigger change.
    this.websocket.send(angular.toJson(request));
  }

  ping() {
    let request_id = this.newRequestId();
    let request = {
      type: MSG_TYPE.PING,
      request_id: request_id
    };
    this.pingsInFlight.add(request_id);
    this.send(request);
  }

  scheduleEnsureConnection() {
    if (this.ensureConnectionPromise) {
      this.$timeout.cancel(this.ensureConnectionPromise);
      this.ensureConnectionPromise = null;
    }
    this.ensureConnectionPromise = this.$timeout(
      this.ensureConnection.bind(this),
      this.connectionCheckInterval
    );
  }

  ensureConnection() {
    this.scheduleEnsureConnection();
    if (this.state === REGION_STATE.UP) {
      let missedPings = this.pingsInFlight.size;
      let outstandingRequests = Object.keys(this.requests).length;
      let impatienceFactor = missedPings + outstandingRequests;
      if (missedPings > 0) {
        this.log.debug("Still waiting for ping replies: ", this.pingsInFlight);
      }
      if (missedPings >= this.maxMissedPings) {
        // Assume the connection has timed out.
        this.log.warn("Closed connection: ping timeout.");
        this.retry();
      } else if (missedPings > 0 && impatienceFactor >= this.maxPatience) {
        this.log.warn("Closed connection: impatience factor exceeded.");
        this.retry();
      } else {
        this.ping();
      }
    } else if (this.state === REGION_STATE.RETRY) {
      // We know we're already in RETRY state, but call retry()
      // again to ensure we don't continue to create additional
      // WebSocket objects (without closing them).
      this.retry();
      this.log.debug("Attempting to reconnect...");
      this.connect();
    }
  }

  // Opens the websocket connection.
  connect() {
    this.url = this._buildUrl();
    this.websocket = this.buildSocket(this.url);

    this.websocket.onopen = evt => {
      this.state = REGION_STATE.UP;
      this.pingsInFlight.clear();
      this.scheduleEnsureConnection();
      angular.forEach(this.handlers.open, func => {
        func(evt);
      });
      this.log.debug("WebSocket connection established.");
    };
    this.websocket.onerror = evt => {
      this.log.error("WebSocket error: ", evt);
      angular.forEach(this.handlers.error, func => {
        func(evt);
      });
    };
    this.websocket.onclose = evt => {
      let url = this.url.split("?")[0];
      this.log.warn("WebSocket connection closed: " + url);
      angular.forEach(this.handlers.close, func => {
        func(evt);
      });
      this.websocket = null;
      this.retry();
    };
    this.websocket.onmessage = evt => {
      this.onMessage(angular.fromJson(evt.data));
    };
  }

  // Closes the websocket connection and begin to retry the connection.
  retry() {
    // Ensure the socket is closed, if applicable. If the WebSocket
    // is already null (such as what might happen if this method is
    // called from the onclose() hanlder), no need to close it again.
    if (this.websocket) {
      // Clear out event handlers. By now we already know the
      // websocket is closed; we don't want stray events from the
      // now-dead websocket to affect the existing connection.
      this.websocket.onopen = null;
      this.websocket.onerror = null;
      this.websocket.onclose = null;
      this.websocket.close();
      this.websocket = null;
    }
    // Set the state to RETRY so that ensureConnection will attempt
    // to reconnect the next time it runs.
    this.state = REGION_STATE.RETRY;
  }

  // Return the protocol used for the websocket connection.
  _getProtocol() {
    return this.$window.location.protocol;
  }

  // Return connection url to websocket from current location and
  // html options.
  _buildUrl() {
    let host = this.$window.location.hostname;
    let port = this.$window.location.port;
    let path = this.$window.location.pathname;
    let proto = "ws";
    if (this._getProtocol() === "https:") {
      proto = "wss";
    }

    // Path and port can be overridden by href and data-websocket-port
    // in the base element respectively.
    let base = angular.element("base");
    if (angular.isDefined(base)) {
      let newPath = base.attr("href");
      if (angular.isDefined(newPath)) {
        path = newPath;
      }
      let newPort = base.data("websocket-port");
      if (angular.isDefined(newPort)) {
        port = newPort;
      }
    }

    // Append final '/' if missing from end of path.
    if (path[path.length - 1] !== "/") {
      path += "/";
    }

    // Build the URL. Include the :port only if it has a value.
    let url = proto + "://" + host;
    if (angular.isString(port) && port.length > 0) {
      url += ":" + port;
    }
    url += path + "ws";

    // Include the csrftoken in the URL if it's defined.
    let csrftoken;
    if (angular.isFunction(this.$cookies.get)) {
      csrftoken = this.$cookies.get("csrftoken");
    } else {
      csrftoken = this.$cookies.csrftoken;
    }
    if (angular.isDefined(csrftoken)) {
      url += "?csrftoken=" + encodeURIComponent(csrftoken);
    }

    return url;
  }

  // Opens the default websocket connection.
  defaultConnect() {
    // Already been called but the connection has not been completed.
    if (angular.isObject(this.defaultConnectDefer)) {
      return this.defaultConnectDefer.promise;
    }

    // Already connected.
    let defer;
    if (this.isConnected()) {
      // Create a new defer as the defaultConnectDefer would
      // have already been resolved.
      defer = this.$q.defer();

      // Cannot resolve the defer inline as it hasn't been given
      // back to the caller. It will be called in the next loop.
      this.$timeout(defer.resolve);
      return defer.promise;
    }

    // Start the connection.
    defer = this.defaultConnectDefer = this.$q.defer();
    let opened = evt => {
      this.defaultConnectDefer = null;
      this.unregisterHandler("open", opened);
      this.unregisterHandler("error", errored);
      this.$rootScope.$apply(defer.resolve(evt));
    };
    let errored = evt => {
      this.defaultConnectDefer = null;
      this.unregisterHandler("open", opened);
      this.unregisterHandler("error", errored);
      this.$rootScope.$apply(defer.reject(evt));
    };
    this.registerHandler("open", opened);
    this.registerHandler("error", errored);
    this.connect();
    return defer.promise;
  }

  // Called when a message is received.
  onMessage(msg) {
    // Synchronous response
    if (msg.type === MSG_TYPE.RESPONSE) {
      this.onResponse(msg);
      // Asynchronous notification
    } else if (msg.type === MSG_TYPE.NOTIFY) {
      this.onNotify(msg);
      // Reply to connectivity check
    } else if (msg.type === MSG_TYPE.PING_REPLY) {
      this.onPingReply(msg);
    }
  }

  // Called when a response message is recieved.
  onResponse(msg) {
    // Grab the registered defer from the callbacks list.
    let defer = this.callbacks[msg.request_id];
    let remembered_request = this.requests[msg.request_id];
    if (angular.isDefined(defer)) {
      if (msg.rtype === RESPONSE_TYPE.SUCCESS) {
        // Resolve the defer inside of the digest cycle, so any
        // update to an object or collection will trigger a
        // watcher.
        this.$rootScope.$apply(defer.resolve(msg.result));
      } else if (msg.rtype === RESPONSE_TYPE.ERROR) {
        // Reject the defer since an error occurred.
        if (angular.isObject(remembered_request)) {
          this.$rootScope.$apply(
            defer.reject({
              error: msg.error,
              request: remembered_request
            })
          );
        } else {
          this.$rootScope.$apply(defer.reject(msg.error));
        }
      }
      // Remove the defer from the callback list.
      delete this.callbacks[msg.request_id];
      delete this.requests[msg.request_id];
    }
  }

  // Called when a notify response is recieved.
  onNotify(msg) {
    let handlers = this.notifiers[msg.name];
    if (angular.isArray(handlers)) {
      angular.forEach(handlers, function(handler) {
        handler(msg.action, msg.data);
      });
    }
  }

  onPingReply(msg) {
    // Note: The msg.result at this point contains the last sequence
    // number received, but it isn't really relevant for us. It could
    // be helpful for debug logging, if necessary.
    this.pingsInFlight.delete(msg.request_id);
  }

  // Call method on the region.
  callMethod(method, params, remember) {
    let defer = this.$q.defer();
    let request_id = this.newRequestId();
    let request = {
      type: MSG_TYPE.REQUEST,
      request_id: request_id,
      method: method,
      params: params
    };
    this.callbacks[request_id] = defer;
    // If requested, remember what the details of the request were,
    // so that the controller can refresh its memory.
    if (remember) {
      this.requests[request_id] = request;
    }
    this.send(request);
    // Uncomment this to log every WebSocket method call.
    // this.log.debug("callMethod(): ", request, remember);
    return defer.promise;
  }
}

export default RegionConnection;
