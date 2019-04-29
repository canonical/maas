/* Copyright 2015-2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Manager Helper Service
 *
 * Used by controllers to load managers. It helps the initialization of
 * managers and makes sure that all items in the manager are loaded
 * before resolving the defer.
 */

/* @ngInject */
function ManagerHelperService($q, $timeout, ErrorService, RegionConnection) {
  // Loads the manager.
  this.loadManager = function(scope, manager) {
    var defer = $q.defer();
    var self = this;

    // If the manager already has this scope loaded then nothing needs
    // to be done.
    if (manager._scopes.indexOf(scope) > -1) {
      $timeout(function() {
        defer.resolve(manager);
      });
      return defer.promise;
    }

    // Do this entire operation with in the context of the region
    // connection is connected.
    RegionConnection.defaultConnect().then(function() {
      if (manager._type === "notify") {
        if (manager.isLoaded()) {
          $timeout(function() {
            manager._scopes.push(scope);
            defer.resolve(manager);
          });
        } else {
          manager.loadItems().then(
            function() {
              manager._scopes.push(scope);
              defer.resolve(manager);
            },
            function(error) {
              ErrorService.raiseError(error);
            }
          );
        }
        // Always enable auto reload. This will make sure the items
        // are reloaded if the connection goes down.
        manager.enableAutoReload();

        // Remove the scope for the loaded scopes for the manager.
        scope.$on("$destroy", function() {
          self.unloadManager(scope, manager);
        });
      } else if (manager._type === "poll") {
        if (manager.isPolling()) {
          $timeout(function() {
            manager._scopes.push(scope);
            defer.resolve(manager);
          });
        } else {
          manager.startPolling().then(
            function() {
              manager._scopes.push(scope);
              defer.resolve(manager);
            },
            function(error) {
              ErrorService.raiseError(error);
            }
          );
        }

        // Stop the polling when the scope is destroyed and its
        // not in use by any other scopes.
        scope.$on("$destroy", function() {
          self.unloadManager(scope, manager);
        });
      } else {
        throw new Error("Unknown manager type: " + manager._type);
      }
    });
    return defer.promise;
  };

  // Gets the list of managers.
  this.loadManagers = function(scope, managers) {
    var defer = $q.defer();
    var loadedManagers = [];

    // Resolves the defer if all managers are loaded.
    var resolveAllLoaded = function() {
      if (loadedManagers.length === managers.length) {
        defer.resolve(managers);
      }
    };

    var self = this;
    angular.forEach(managers, function(manager) {
      self.loadManager(scope, manager).then(function(loadedManager) {
        loadedManagers.push(loadedManager);
        resolveAllLoaded();
      });
    });
    return defer.promise;
  };

  this.unloadManager = function(scope, manager) {
    var idx = manager._scopes.indexOf(scope);
    if (idx > -1) {
      manager._scopes.splice(idx, 1);
    }
    if (manager._type === "poll" && manager._scopes.length === 0) {
      manager.stopPolling();
    }
  };

  this.unloadManagers = function(scope, managers) {
    var self = this;
    angular.forEach(managers, function(manager) {
      self.unloadManager(scope, manager);
    });
  };

  // Tries to parse the specified string as JSON. If parsing fails,
  // returns the original string. (This is useful since some manager
  // calls return an error that could be either plain text, or JSON.)
  this.tryParsingJSON = function(string) {
    var error;
    try {
      error = JSON.parse(string);
    } catch (e) {
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
    var result = "";
    angular.forEach(dict, function(value, key) {
      var error = dict[key];
      if (showNames === true) {
        result += key + ": ";
      }
      if (angular.isString(error) || angular.isNumber(error)) {
        result += error + "  ";
      } else if (angular.isObject(error)) {
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
  this.parseValidationError = function(error, showNames) {
    error = this.tryParsingJSON(error);
    if (!angular.isObject(error)) {
      return error;
    } else {
      return this.getPrintableString(error, showNames);
    }
  };
}

export default ManagerHelperService;
