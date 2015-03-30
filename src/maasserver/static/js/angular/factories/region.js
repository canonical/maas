/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Region Connection
 *
 * Provides the websocket connection between the client and the MAAS regiond
 * service.
 */

angular.module('MAAS').factory(
    'RegionConnection',
    ['$q', '$rootScope', '$timeout', '$window', '$cookies', function(
        $q, $rootScope, $timeout, $window, $cookies) {

        // Message types
        var MSG_TYPE = {
            REQUEST: 0,
            RESPONSE: 1,
            NOTIFY: 2
        };

        // Response types
        var RESPONSE_TYPE = {
            SUCCESS: 0,
            ERROR: 1
        };

        // Constructor
        function RegionConnection() {
            this.callbacks = {};
            this.requestId = 0;
            this.url = null;
            this.websocket = null;
            this.connected = false;
            this.autoReconnect = true;
            this.retryTimeout = 5000;

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
        RegionConnection.prototype.newRequestId = function() {
            this.requestId += 1;
            return this.requestId;
        };

        // Register event handler.
        RegionConnection.prototype.registerHandler = function (name, func) {
            if(!angular.isDefined(this.handlers[name])) {
                throw new Error("Invalid handler: " + name);
            }
            if(!angular.isFunction(func)) {
                throw new Error("Requires a function to register a handler.");
            }
            this.handlers[name].push(func);
        };

        // Unregister event handler.
        RegionConnection.prototype.unregisterHandler = function (name, func) {
            if(!angular.isDefined(this.handlers[name])) {
                throw new Error("Invalid handler: " + name);
            }
            var idx = this.handlers[name].indexOf(func);
            if(idx >= 0) {
                this.handlers[name].splice(idx, 1);
            }
        };

        // Register notification handler.
        RegionConnection.prototype.registerNotifier = function(name, func) {
            if(!angular.isFunction(func)) {
                throw new Error("Requires a function to register a notifier.");
            }
            if(angular.isUndefined(this.notifiers[name])) {
                this.notifiers[name] = [];
            }
            this.notifiers[name].push(func);
        };

        // Unregister notification handler.
        RegionConnection.prototype.unregisterNotifier = function(name, func) {
            if(angular.isUndefined(this.notifiers[name])) {
                return;
            }
            var idx = this.notifiers[name].indexOf(func);
            if(idx >= 0) {
                this.notifiers[name].splice(idx, 1);
            }
        };

        // Return True if currently connected to region.
        RegionConnection.prototype.isConnected = function() {
            return this.connected;
        };

        // Builds the websocket connection.
        RegionConnection.prototype.buildSocket = function(url) {
            return new WebSocket(url);
        };

        // Opens the websocket connection.
        RegionConnection.prototype.connect = function(url) {
            this.url = url;
            this.autoReconnect = true;
            this.websocket = this.buildSocket(this.url);

            var self = this;
            this.websocket.onopen = function(evt) {
                self.connected = true;
                angular.forEach(self.handlers.open, function(func) {
                    func(evt);
                });
            };
            this.websocket.onerror = function(evt) {
                angular.forEach(self.handlers.error, function(func) {
                    func(evt);
                });
            };
            this.websocket.onclose = function(evt) {
                self.connected = false;
                angular.forEach(self.handlers.close, function(func) {
                    func(evt);
                });
                if(self.autoReconnect) {
                    $timeout(function() {
                        self.connect(self.url);
                    }, self.retryTimeout);
                }
            };
            this.websocket.onmessage = function(evt) {
                self.onMessage(angular.fromJson(evt.data));
            };
        };

        // Closes the websocket connection.
        RegionConnection.prototype.close = function() {
            this.autoReconnect = false;
            this.websocket.close();
            this.websocket = null;
        };

        // Return connection url to websocket from current location and
        // html options.
        RegionConnection.prototype._buildUrl = function() {
            var host = $window.location.hostname;
            var port = $window.location.port;
            var path = $window.location.pathname;

            // Port can be overridden by data-websocket-port in the base
            // element.
            var base = angular.element("base");
            if(angular.isDefined(base)) {
                var newPort = base.data("websocket-port");
                if(angular.isDefined(newPort)) {
                    port = newPort;
                }
            }

            // Append final '/' if missing from end of path.
            if(path[path.length - 1] !== '/') {
                path += '/';
            }

            url = "ws://" + host + ":" + port + path + "ws";

            // Include the csrftoken in the URL if it's defined.
            csrftoken = $cookies.csrftoken;
            if(angular.isDefined(csrftoken)) {
                url += '?csrftoken=' + encodeURIComponent(csrftoken);
            }

            return url;
        };

        // Opens the default websocket connection.
        RegionConnection.prototype.defaultConnect = function() {
            // Already been called but the connection has not been completed.
            if(angular.isObject(this.defaultConnectDefer)) {
                return this.defaultConnectDefer.promise;
            }

            // Already connected.
            var defer;
            if(this.isConnected()) {
                // Create a new defer as the defaultConnectDefer would
                // have already been resolved.
                defer = $q.defer();

                // Cannot resolve the defer inline as it hasn't been given
                // back to the caller. It will be called in the next loop.
                $timeout(defer.resolve);
                return defer.promise;
            }

            // Start the connection.
            var self = this, opened, errored;
            defer = this.defaultConnectDefer = $q.defer();
            opened = function(evt) {
                this.defaultConnectDefer = null;
                self.unregisterHandler("open", opened);
                self.unregisterHandler("error", errored);
                $rootScope.$apply(defer.resolve(evt));
            };
            errored = function(evt) {
                this.defaultConnectDefer = null;
                self.unregisterHandler("open", opened);
                self.unregisterHandler("error", errored);
                $rootScope.$apply(defer.reject(evt));
            };
            this.registerHandler("open", opened);
            this.registerHandler("error", errored);
            this.connect(this._buildUrl());
            return defer.promise;
        };

        // Called when a message is received.
        RegionConnection.prototype.onMessage = function(msg) {
            // Response
            if(msg.type === MSG_TYPE.RESPONSE) {
                this.onResponse(msg);
            // Notify
            } else if(msg.type === MSG_TYPE.NOTIFY) {
                this.onNotify(msg);
            }
        };

        // Called when a response message is recieved.
        RegionConnection.prototype.onResponse = function(msg) {
            // Grab the registered defer from the callbacks list.
            var defer = this.callbacks[msg.request_id];
            if(angular.isDefined(defer)) {
                if(msg.rtype === RESPONSE_TYPE.SUCCESS) {
                    // Resolve the defer inside of the digest cycle, so any
                    // update to an object or collection will trigger a
                    // watcher.
                    $rootScope.$apply(defer.resolve(msg.result));
                } else if(msg.rtype === RESPONSE_TYPE.ERROR) {
                    // Reject the defer since an error occurred.
                    $rootScope.$apply(defer.reject(msg.error));
                }
                // Remove the defer from the callback list.
                delete this.callbacks[msg.request_id];
            }
        };

        // Called when a notify response is recieved.
        RegionConnection.prototype.onNotify = function(msg) {
            var handlers = this.notifiers[msg.name];
            if(angular.isArray(handlers)) {
                angular.forEach(handlers, function(handler) {
                    handler(msg.action, msg.data);
                });
            }
        };

        // Call method on the region.
        RegionConnection.prototype.callMethod = function(method, params) {
            var defer = $q.defer();
            var request_id = this.newRequestId();
            var request = {
                type: MSG_TYPE.REQUEST,
                request_id: request_id,
                method: method,
                params: params
            };
            this.callbacks[request_id] = defer;
            this.websocket.send(angular.toJson(request));
            return defer.promise;
        };

        return new RegionConnection();
    }]);
