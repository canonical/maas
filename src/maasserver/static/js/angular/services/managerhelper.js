/* Copyright 2015 Canonical Ltd.  This software is licensed under the
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
    }]);
