/* Copyright (C) 2017 Canonical Ltd. */
'use strict';

var module = module;

(function(exports) {

    /**
     * The Web Handler used to communicate to the juju-core HTTPS API.
     * Objects defined here can be used to make asynchronous HTTP(S) requests
     * and handle responses.
     */
    class WebHandler {
        /**
           Send an asynchronous POST request to the given URL.

           @method sendPostRequest
           @param {String} path The remote target path/URL.
           @param {Object} headers Additional request headers as key/value
           pairs.
           @param {Object} data The data to send as a file object, a string or
           in general as an ArrayBufferView/Blob object.
           @param {String} username The user name for basic HTTP authentication
           (or null if no authentication is required).
           @param {String} password The password for basic HTTP authentication
           (or null if no authentication is required).
           @param {Function} progressCallback The progress event callback.
           @param {Function} completedCallback The load event callback.
           @return {Object} The asynchronous request instance.
        */
        sendPostRequest(path, headers, data, username, password,
                        withCredentials, progressCallback,
                        completedCallback) {
            var xhr = this._createRequest(
                path, 'POST', headers, username, password, withCredentials,
                progressCallback, completedCallback);
            // Send the POST data.
            xhr.send(data);
            return xhr;
        }

        /**
           Send an asynchronous PUT request to the given URL.

           @method sendPutRequest
           @param {String} path The remote target path/URL.
           @param {Object} headers Additional request headers as key/value
           pairs.
           @param {Object} data The data to send as a file object, a string or
           in general as an ArrayBufferView/Blob object.
           @param {String} username The user name for basic HTTP authentication
           (or null if no authentication is required).
           @param {String} password The password for basic HTTP authentication
           (or null if no authentication is required).
           @param {Function} progressCallback The progress event callback.
           @param {Function} completedCallback The load event callback.
           @return {Object} The asynchronous request instance.
        */
        sendPutRequest(path, headers, data, username, password,
                       withCredentials, progressCallback,
                       completedCallback) {
            var xhr = this._createRequest(
                path, 'PUT', headers, username, password, withCredentials,
                progressCallback, completedCallback);
            // Send the PUT data.
            xhr.send(data);
            return xhr;
        }

        /**
           Send an asynchronous PATCH request to the given URL.

           @method sendPatchRequest
           @param {String} path The remote target path/URL.
           @param {Object} headers Additional request headers as key/value
           pairs.
           @param {Object} data The data to send as a file object, a string or
           in general as an ArrayBufferView/Blob object.
           @param {String} username The user name for basic HTTP authentication
           (or null if no authentication is required).
           @param {String} password The password for basic HTTP authentication
           (or null if no authentication is required).
           @param {Function} progressCallback The progress event callback.
           @param {Function} completedCallback The load event callback.
           @return {Object} The asynchronous request instance.
        */
        sendPatchRequest(path, headers, data, username, password,
                         withCredentials, progressCallback,
                         completedCallback) {
            var xhr = this._createRequest(
                path, 'PATCH', headers, username, password, withCredentials,
                progressCallback, completedCallback);
            // Send the PATCH data.
            xhr.send(data);
            return xhr;
        }

        /**
           Send an asynchronous GET request to the given URL.

           @method sendGetRequest
           @param {String} path The remote target path/URL.
           @param {Object} headers Additional request headers as key/value
           pairs.
           @param {String} username The user name for basic HTTP authentication
           (or null if no authentication is required).
           @param {String} password The password for basic HTTP authentication
           (or null if no authentication is required).
           @param {Function} progressCallback The progress event callback.
           @param {Function} completedCallback The load event callback.
           @return {Object} The asynchronous request instance.
        */
        sendGetRequest(path, headers, username, password, withCredentials,
                       progressCallback, completedCallback) {
            var xhr = this._createRequest(
                path, 'GET', headers, username, password, withCredentials,
                progressCallback, completedCallback);
            // Send the GET request.
            xhr.send();
            return xhr;
        }

        /**
           Send an asynchronous DELETE request to the given URL.

           @method sendDeleteRequest
           @param {String} path The remote target path/URL.
           @param {Object} headers Additional request headers as key/value
           pairs.
           @param {String} username The user name for basic HTTP authentication
           (or null if no authentication is required).
           @param {String} password The password for basic HTTP authentication
           (or null if no authentication is required).
           @param {Function} progressCallback The progress event callback.
           @param {Function} completedCallback The load event callback.
           @return {Object} The asynchronous request instance.
        */
        sendDeleteRequest(path, headers, username, password,
                          withCredentials, progressCallback,
                          completedCallback) {
            var xhr = this._createRequest(
                path, 'DELETE', headers, username, password, withCredentials,
                progressCallback, completedCallback);
            // Send the GET request.
            xhr.send();
            return xhr;
        }

        /**
           Given a path and credentials, return a URL including the
           user:password fragment. The current host is used.

           @method getUrl
           @param {String} path The target path.
           @param {String} username The user name for basic HTTP authentication.
           @param {String} password The password for basic HTTP authentication.
           @return {String} The resulting URL.
        */
        getUrl(path, username, password) {
            var location = window.location;
            return location.protocol + '//' +
                username + ':' + password + '@' +
                location.host + path;
        }

        /**
           Create and return a value for the HTTP "Authorization" header.
           The resulting value includes the given credentials.

           @method _createAuthorizationHeader
           @param {String} username The user name.
           @param {String} password The password associated to the user name.
           @return {String} The resulting "Authorization" header value.
        */
        _createAuthorizationHeader(username, password) {
            var hash = btoa(username + ':' + password);
            return 'Basic ' + hash;
        }

        /**
           Create and return a xhr progress handler function.

           @method _createProgressHandler
           @param {Function} callback The progress event callback
           (or null if progress is not handled).
           @return {Function} The resulting progress handler function.
        */
        _createProgressHandler(callback) {
            var handler = function(evt) {
                if (typeof callback === 'function') {
                    callback(evt);
                }
            };
            return handler;
        }

        /**
           Create and return a xhr load handler function.

           @method _createCompletedHandler
           @param {Function} callback The completed event callback.
           @param {Function} progressHandler The progress event handler.
           @param {Object} xhr The asynchronous request instance.
           @return {Function} The resulting load handler function.
        */
        _createCompletedHandler(callback, progressHandler, xhr) {
            var handler = function(evt) {
                if (typeof callback === 'function') {
                    callback(evt);
                }
                // The request has been completed: detach all the handlers.
                xhr.removeEventListener('progress', progressHandler);
                xhr.removeEventListener('error', handler);
                xhr.removeEventListener('load', handler);
            };
            return handler;
        }

        /**
           Create, set up and return an asynchronous request to the given URL
           with the given method.

           @method _createRequest
           @param {String} path The remote target path/URL.
           @param {String} method The request method (e.g. "GET" or "POST").
           @param {Object} headers Additional request headers as key/value
           pairs.
           @param {String} username The user name for basic HTTP authentication
           (or null if no authentication is required).
           @param {String} password The password for basic HTTP authentication
           (or null if no authentication is required).
           @param {Function} progressCallback The progress event callback
           (or null if progress is not handled).
           @param {Function} completedCallback The load event callback.
           @return {Object} The asynchronous request instance.
        */
        _createRequest(path, method, headers, username, password,
                       withCredentials, progressCallback,
                       completedCallback) {
            var xhr = new XMLHttpRequest({});
            // Set up the event handlers.
            var progressHandler = this._createProgressHandler(progressCallback);
            var completedHandler = this._createCompletedHandler(
                completedCallback, progressHandler, xhr);
            xhr.addEventListener('progress', progressHandler, false);
            xhr.addEventListener('error', completedHandler, false);
            xhr.addEventListener('load', completedHandler, false);
            // Set up the request.
            xhr.open(method, path, true);
            Object.keys(headers || {}).forEach(key => {
                xhr.setRequestHeader(key, headers[key]);
            });
            // Handle basic HTTP authentication. Rather than passing the
            // username and password to the xhr directly, we create the
            // corresponding request header manually, so that a
            // request/response round trip is avoided and the authentication
            // works well in Firefox and IE.
            if (username && password) {
                var authHeader = this._createAuthorizationHeader(
                    username, password);
                xhr.setRequestHeader('Authorization', authHeader);
            }
            if (withCredentials === true) {
                xhr.withCredentials = withCredentials;
            }
            return xhr;
        };
    };

    exports.WebHandler = WebHandler;

}((module && module.exports) ? module.exports : this));
