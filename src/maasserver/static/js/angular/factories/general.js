/* Copyright 2015-2018 Canonical Ltd.  This software is licensed under the
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

function GeneralManager($q, $timeout, RegionConnection, ErrorService) {
  // Constructor
  function GeneralManager() {
    // Holds the available endpoints and its data.
    this._data = {
      machine_actions: {
        method: "general.machine_actions",
        data: [],
        requested: false,
        loaded: false,
        polling: [],
        nextPromise: null
      },
      device_actions: {
        method: "general.device_actions",
        data: [],
        request: false,
        loaded: false,
        polling: [],
        nextPromise: null
      },
      region_controller_actions: {
        method: "general.region_controller_actions",
        data: [],
        requested: false,
        loaded: false,
        polling: [],
        nextPromise: null
      },
      rack_controller_actions: {
        method: "general.rack_controller_actions",
        data: [],
        requested: false,
        loaded: false,
        polling: [],
        nextPromise: null
      },
      region_and_rack_controller_actions: {
        method: "general.region_and_rack_controller_actions",
        data: [],
        requested: false,
        loaded: false,
        polling: [],
        nextPromise: null
      },
      architectures: {
        method: "general.architectures",
        data: [],
        requested: false,
        loaded: false,
        polling: [],
        nextPromise: null
      },
      known_architectures: {
        method: "general.known_architectures",
        data: [],
        requested: false,
        loaded: false,
        polling: [],
        nextPromise: null
      },
      pockets_to_disable: {
        method: "general.pockets_to_disable",
        data: [],
        requested: false,
        loaded: false,
        polling: [],
        nextPromise: null
      },
      components_to_disable: {
        method: "general.components_to_disable",
        data: [],
        requested: false,
        loaded: false,
        polling: [],
        nextPromise: null
      },
      hwe_kernels: {
        method: "general.hwe_kernels",
        data: [],
        requested: false,
        loaded: false,
        polling: [],
        nextPromise: null
      },
      min_hwe_kernels: {
        method: "general.min_hwe_kernels",
        data: [],
        requested: false,
        loaded: false,
        polling: [],
        nextPromise: null
      },
      default_min_hwe_kernel: {
        method: "general.default_min_hwe_kernel",
        data: { text: "" },
        requested: false,
        loaded: false,
        polling: [],
        nextPromise: null,
        replaceData: function(oldData, newData) {
          oldData.text = newData;
        }
      },
      osinfo: {
        method: "general.osinfo",
        data: {},
        requested: false,
        loaded: false,
        polling: [],
        nextPromise: null,
        isEmpty: function(data) {
          var osystems = data.osystems;
          return angular.isUndefined(osystems) || osystems.length === 0;
        },
        replaceData: function(oldData, newData) {
          angular.copy(newData, oldData);
        }
      },
      bond_options: {
        method: "general.bond_options",
        data: {},
        requested: false,
        loaded: false,
        polling: [],
        nextPromise: null,
        replaceData: function(oldData, newData) {
          angular.copy(newData, oldData);
        }
      },
      version: {
        method: "general.version",
        data: { text: null },
        requested: false,
        loaded: false,
        polling: [],
        nextPromise: null,
        replaceData: function(oldData, newData) {
          oldData.text = newData;
        }
      },
      power_types: {
        method: "general.power_types",
        data: [],
        requested: false,
        loaded: false,
        polling: [],
        nextPromise: null,
        replaceData: function(oldData, newData) {
          // Add new power types.
          var i, j, newPowerType, oldPowerType;
          for (i = 0; i < newData.length; i++) {
            newPowerType = newData[i];
            var newItem = true;
            for (j = 0; j < oldData.length; j++) {
              oldPowerType = oldData[j];
              if (newPowerType.name === oldPowerType.name) {
                newItem = false;
                break;
              }
            }

            // Item was previously not in the list so it is
            // inserted into the array.
            if (newItem) {
              oldData.push(newPowerType);
            }
          }

          // Remove any power types that are not included in
          // the newData.
          for (i = oldData.length - 1; i >= 0; i--) {
            oldPowerType = oldData[i];
            var found = false;
            for (j = 0; j < newData.length; j++) {
              newPowerType = newData[j];
              if (newPowerType.name === oldPowerType.name) {
                found = true;
                break;
              }
            }

            // Item was previously not in the list so it is
            // inserted into the array.
            if (!found) {
              oldData.splice(i, 1);
            }
          }
        }
      },
      release_options: {
        method: "general.release_options",
        data: {},
        requested: false,
        loaded: false,
        polling: [],
        nextPromise: null,
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

    // Use the same notify type as a default manager.
    this._type = "notify";

    // The scopes that have loaded this manager.
    this._scopes = [];
  }

  GeneralManager.prototype._getInternalData = function(name) {
    var data = this._data[name];
    if (angular.isUndefined(data)) {
      throw new Error("Unknown data: " + name);
    }
    return data;
  };

  // Return loaded data.
  GeneralManager.prototype.getData = function(name) {
    var d = this._getInternalData(name);
    d.requested = true;
    return d.data;
  };

  // Return true when all data has been loaded.
  GeneralManager.prototype.isLoaded = function() {
    var loaded = true;
    angular.forEach(this._data, function(data) {
      if (!data.loaded) {
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
      if (data.polling.length > 0) {
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
  GeneralManager.prototype.startPolling = function(scope, name) {
    var data = this._getInternalData(name);
    var idx = data.polling.indexOf(scope);
    if (idx === -1) {
      data.polling.push(scope);
      if (data.polling.length === 1) {
        // Polling needs to be started. This is the first scope
        // that is requesting for polling to be performed.
        this._poll(data);
      }
    }
  };

  // Stops the manager polling for data.
  GeneralManager.prototype.stopPolling = function(scope, name) {
    var data = this._getInternalData(name);
    var idx = data.polling.indexOf(scope);
    if (idx >= 0) {
      data.polling.splice(idx, 1);
    }
    if (data.polling.length === 0 && angular.isObject(data.nextPromise)) {
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
    if (angular.isUndefined(replaceData)) {
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
      },
      function(error) {
        if (raiseError) {
          ErrorService.raiseError(error);
        }
        return error;
      }
    );
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
    if (angular.isUndefined(isEmpty)) {
      isEmpty = function(data) {
        return data.length === 0;
      };
    }

    // Can only poll if connected.
    if (!RegionConnection.isConnected()) {
      this._pollAgain(data, this._pollErrorTimeout);
      return;
    }

    return this._loadData(data, false).then(
      function(newData) {
        var pollTimeout = self._pollTimeout;
        if (isEmpty(data.data)) {
          pollTimeout = self._pollEmptyTimeout;
        }
        self._pollAgain(data, pollTimeout);
        return newData;
      },
      function(error) {
        // Don't raise the error, just log it and try again.
        console.log(error); // eslint-disable-line no-console
        self._pollAgain(data, self._pollErrorTimeout);
      }
    );
  };

  // Loads all the items. This implemented so the ManagerHelperService
  // can work on this manager just like all the rest. Optionally pass a
  // list of specific items to load. Useful when reloading data.
  GeneralManager.prototype.loadItems = function(items) {
    var self = this;
    var defer = $q.defer();
    var waitingCount = 0;
    if (angular.isArray(items)) {
      waitingCount = items.length;
    } else {
      angular.forEach(this._data, function(data) {
        if (data.requested) {
          waitingCount++;
        }
      });
    }
    var done = function() {
      waitingCount -= 1;
      if (waitingCount === 0) {
        defer.resolve();
      }
    };

    angular.forEach(this._data, function(data, name) {
      if (
        (angular.isArray(items) && items.indexOf(name) !== -1) ||
        (!angular.isArray(items) && data.requested)
      ) {
        self._loadData(data, true).then(function() {
          done();
        });
      }
    });

    return defer.promise;
  };

  // Enables auto reloading of the item list on connection to region.
  GeneralManager.prototype.enableAutoReload = function() {
    if (!this._autoReload) {
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
    if (this._autoReload) {
      RegionConnection.unregisterHandler("open", this._reloadFunc);
      this._reloadFunc = null;
      this._autoReload = false;
    }
  };

  // Get navigation options so navigation can be updated.
  GeneralManager.prototype.getNavigationOptions = () => {
    return RegionConnection.callMethod("general.navigation_options");
  };

  return new GeneralManager();
}

GeneralManager.$inject = ["$q", "$timeout", "RegionConnection", "ErrorService"];

export default GeneralManager;
