/* Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Manager Helper Service
 *
 * Used by controllers to load managers. It helps the initialization of
 * managers and makes sure that all items in the manager are loaded
 * before resolving the defer.
 */

angular.module('MAAS').service('ManagerHelperService', [
    '$q', '$timeout', 'ErrorService', 'RegionConnection',
    function($q, $timeout, ErrorService, RegionConnection) {

        // Loads the manager.
        this.loadManager = function(manager) {
            // Do this entire operation with in the context of the region
            // connection is connected.
            var defer = $q.defer();
            RegionConnection.defaultConnect().then(function() {
                if(manager.isLoaded()) {
                    $timeout(function() {
                        defer.resolve(manager);
                    });
                } else {
                    manager.loadItems().then(function() {
                        defer.resolve(manager);
                    }, function(error) {
                        ErrorService.raiseError(error);
                    });
                }
                // Always enable auto reload. This will make sure the items
                // are reloaded if the connection goes down.
                manager.enableAutoReload();
            });
            return defer.promise;
        };

        // Gets the list of managers.
        this.loadManagers = function(managers) {
            var defer = $q.defer();
            var loadedManagers = [];

            // Resolves the defer if all managers are loaded.
            var resolveAllLoaded = function() {
                if(loadedManagers.length === managers.length) {
                    defer.resolve(managers);
                }
            };

            var self = this;
            angular.forEach(managers, function(manager) {
                self.loadManager(manager).then(function(loadedManager) {
                    loadedManagers.push(loadedManager);
                    resolveAllLoaded();
                });
            });
            return defer.promise;
        };

        // Tries to parse the specified string as JSON. If parsing fails,
        // returns the original string. (This is useful since some manager
        // calls return an error that could be either plain text, or JSON.)
        this.tryParsingJSON = function(string) {
            var error;
            try {
                error = JSON.parse(string);
            } catch(e) {
                if (e instanceof SyntaxError) {
                    return string;
                } else {
                    throw e;
                }
            }
            return error;
        };

        // Returns a printable version of the specified dictionary (useful
        // for displaying an error to the user).
        this.getPrintableString = function(dict, showNames) {
            var result = '';
            angular.forEach(dict, function(value, key) {
                var error = dict[key];
                if(showNames === true) {
                    result += key + ": ";
                }
                if(angular.isString(error) || angular.isNumber(error)) {
                    result += error + "  ";
                } else if(angular.isObject(error)) {
                    angular.forEach(error, function(error) {
                        result += error + "  ";
                    });
                }
                result = result.trim() + "\n";
            });
            return result.trim();
        };

        // Convert the Python dict error message to displayed message.
        // We know it's probably a form ValidationError dictionary, so just use
        // it as such, and recover if that doesn't parse as JSON.
        this.parseLikelyValidationError = function(error, showNames) {
            error = this.tryParsingJSON(error);
            if(!angular.isObject(error)) {
                return error;
            } else {
                return this.getPrintableString(error, showNames);
            }
        };
    }]);
