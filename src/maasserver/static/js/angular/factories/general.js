/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS General Manager
 *
 * Manager for general information from the region. The general handler on the
 * region side does not push information to the client. This manager uses
 * polling to grab this data periodically from the region.
 *
 * This manage provides different pieces of data and is structure differently
 * than extending the Manager service. It still provides the Manager service
 * interface allowing the ManagerHelperService to load this manager.
 */

angular.module('MAAS').factory(
    'GeneralManager',
    ['$q', '$timeout', 'RegionConnection', 'ErrorService',
    function($q, $timeout, RegionConnection, ErrorService) {

        // Constructor
        function GeneralManager() {
            // Holds the available endpoints and its data.
            this._data = {
                actions: {
                    method: "general.actions",
                    data: [],
                    loaded: false,
                    polling: false,
                    nextPromise: null
                },
                architectures: {
                    method: "general.architectures",
                    data: [],
                    loaded: false,
                    polling: false,
                    nextPromise: null
                },
                osinfo: {
                    method: "general.osinfo",
                    data: {},
                    loaded: false,
                    polling: false,
                    nextPromise: null,
                    isEmpty: function(data) {
                        var osystems = data.osystems;
                        return (angular.isUndefined(osystems) ||
                            osystems.length === 0);
                    },
                    replaceData: function(oldData, newData) {
                        angular.copy(newData, oldData);
                    }
                }
            };

            // Amount of time in milliseconds the manager should wait to poll
            // for new data.
            this._pollTimeout = 10000;

            // Amount of time in milliseconds the manager should wait to poll
            // for new data when an error occurs.
            this._pollErrorTimeout = 3000;

            // Amount of time in milliseconds the manager should wait to poll
            // for new data when the retrieved data is empty.
            this._pollEmptyTimeout = 3000;

            // Set to true when the items list should reload upon re-connection
            // to the region.
            this._autoReload = false;
        }

        GeneralManager.prototype._getInternalData = function(name) {
            var data = this._data[name];
            if(angular.isUndefined(data)) {
                throw new Error("Unknown data: " + name);
            }
            return data;
        };

        // Return loaded data.
        GeneralManager.prototype.getData = function(name) {
            return this._getInternalData(name).data;
        };

        // Return true when all data has been loaded.
        GeneralManager.prototype.isLoaded = function() {
            var loaded = true;
            angular.forEach(this._data, function(data) {
                if(!data.loaded) {
                    loaded = false;
                }
            });
            return loaded;
        };

        // Return true when data has been loaded.
        GeneralManager.prototype.isDataLoaded = function(name) {
            return this._getInternalData(name).loaded;
        };

        // Returns true when the manager is currently polling.
        GeneralManager.prototype.isPolling = function() {
            var polling = false;
            angular.forEach(this._data, function(data) {
                if(data.polling) {
                    polling = true;
                }
            });
            return polling;
        };

        // Returns true when the manager is currently polling for that data.
        GeneralManager.prototype.isDataPolling = function(name) {
            return this._getInternalData(name).polling;
        };

        // Starts the manager polling for data.
        GeneralManager.prototype.startPolling = function(name) {
            var data = this._getInternalData(name);
            if(!data.polling) {
                data.polling = true;
                this._poll(data);
            }
        };

        // Stops the manager polling for data.
        GeneralManager.prototype.stopPolling = function(name) {
            var data = this._getInternalData(name);
            data.polling = false;
            if(angular.isObject(data.nextPromise)) {
                $timeout.cancel(data.nextPromise);
                data.nextPromise = null;
            }
        };

        // Load the data from the region.
        GeneralManager.prototype._loadData = function(data, raiseError) {
            var replaceData = data.replaceData;
            raiseError = raiseError || false;

            // Set default replaceData function if data doesn't provide its
            // own function.
            if(angular.isUndefined(replaceData)) {
                replaceData = function(oldData, newData) {
                    oldData.length = 0;
                    oldData.push.apply(oldData, newData);
                };
            }

            return RegionConnection.callMethod(data.method).then(
                function(newData) {
                    replaceData(data.data, newData);
                    data.loaded = true;
                    return data.data;
                }, function(error) {
                    if(raiseError) {
                        ErrorService.raiseError(error);
                    }
                    return error;
                });
        };

        GeneralManager.prototype._pollAgain = function(data, timeout) {
            var self = this;
            data.nextPromise = $timeout(function() {
                self._poll(data);
            }, timeout);
        };

        // Polls for the data from the region.
        GeneralManager.prototype._poll = function(data) {
            var self = this;
            var isEmpty = data.isEmpty;

            // Set default isEmpty function if data doesn't provide its
            // own function.
            if(angular.isUndefined(isEmpty)) {
                isEmpty = function(data) {
                    return data.length === 0;
                };
            }

            // Can only poll if connected.
            if(!RegionConnection.isConnected()) {
                this._pollAgain(data, this._pollErrorTimeout);
                return;
            }

            return this._loadData(data, false).then(function(newData) {
                var pollTimeout = self._pollTimeout;
                if(isEmpty(data.data)) {
                    pollTimeout = self._pollEmptyTimeout;
                }
                self._pollAgain(data, pollTimeout);
                return newData;
            }, function(error) {
                // Don't raise the error, just log it and try again.
                console.log(error);
                self._pollAgain(data, self._pollErrorTimeout);
            });
        };

        // Loads all the items. This implemented so the ManagerHelperService
        // can work on this manager just like all the rest.
        GeneralManager.prototype.loadItems = function() {
            var self = this;
            var defer = $q.defer();
            var waitingCount = Object.keys(this._data).length;
            var done = function() {
                waitingCount -= 1;
                if(waitingCount === 0) {
                    defer.resolve();
                }
            };

            angular.forEach(this._data, function(data) {
                self._loadData(data, true).then(function() {
                    done();
                });
            });

            return defer.promise;
        };

        // Enables auto reloading of the item list on connection to region.
        GeneralManager.prototype.enableAutoReload = function() {
            if(!this._autoReload) {
                this._autoReload = true;
                var self = this;
                this._reloadFunc = function() {
                    self.loadItems();
                };
                RegionConnection.registerHandler("open", this._reloadFunc);
            }
        };

        // Disable auto reloading of the item list on connection to region.
        GeneralManager.prototype.disableAutoReload = function() {
            if(this._autoReload) {
                RegionConnection.unregisterHandler("open", this._reloadFunc);
                this._reloadFunc = null;
                this._autoReload = false;
            }
        };

        return new GeneralManager();
    }]);
