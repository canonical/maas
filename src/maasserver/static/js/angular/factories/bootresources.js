/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS BootResource Manager
 *
 * Manager for the boot resources. This manager is unique from all the other
 * managers because it uses polling instead of having the region push the
 * information.
 *
 * Why is it polling?
 * The boot resource information is split between the region controller and
 * all rack controllers. The region controller does not cache any information
 * about a rack controllers images it contacts the rack as its source of truth.
 * This means that the client needs to use polling so the region controller
 * can ask each rack controller what is the status of your images.
 */

function BootResourcesManager($q, $timeout, RegionConnection, ErrorService) {
  function BootResourcesManager() {
    // Set true once been loaded the first time.
    this._loaded = false;

    // Holds the data recieved from polling.
    this._data = {};

    // Set to true when polling has been enabled.
    this._polling = false;

    // The next promise for the polling interval.
    this._nextPromise = null;

    // Amount of time in milliseconds the manager should wait to poll
    // for new data.
    this._pollTimeout = 10000;

    // Amount of time in milliseconds the manager should wait to poll
    // for new data when an error occurs.
    this._pollErrorTimeout = 500;

    // Amount of time in milliseconds the manager should wait to poll
    // for new data when the retrieved data is empty.
    this._pollEmptyTimeout = 3000;
  }

  // Return the data.
  BootResourcesManager.prototype.getData = function() {
    return this._data;
  };

  // Return true when data has been loaded.
  BootResourcesManager.prototype.isLoaded = function() {
    return this._loaded;
  };

  // Returns true when currently polling.
  BootResourcesManager.prototype.isPolling = function() {
    return this._polling;
  };

  // Starts the polling for data.
  BootResourcesManager.prototype.startPolling = function() {
    if (!this._polling) {
      this._polling = true;
      return this._poll();
    } else {
      return this._nextPromise;
    }
  };

  // Stops the polling for data.
  BootResourcesManager.prototype.stopPolling = function() {
    this._polling = false;
    if (angular.isObject(this._nextPromise)) {
      $timeout.cancel(this._nextPromise);
      this._nextPromise = null;
    }
  };

  // Load the data from the region.
  BootResourcesManager.prototype._loadData = function(raiseError) {
    raiseError = raiseError || false;
    var self = this;
    return RegionConnection.callMethod("bootresource.poll").then(
      function(newData) {
        angular.copy(angular.fromJson(newData), self._data);
        self._loaded = true;
        return self._data;
      },
      function(error) {
        if (raiseError) {
          ErrorService.raiseError(error);
        }
      }
    );
  };

  // Registers the next polling attempt.
  BootResourcesManager.prototype._pollAgain = function(timeout) {
    var self = this;
    this._nextPromise = $timeout(function() {
      self._poll();
    }, timeout);
    return this._nextPromise;
  };

  // Polls for the data from the region.
  BootResourcesManager.prototype._poll = function() {
    var self = this;

    // Can only poll if connected.
    if (!RegionConnection.isConnected()) {
      return this._pollAgain(this._pollErrorTimeout);
    }

    return this._loadData(false).then(
      function(newData) {
        var pollTimeout = self._pollTimeout;
        if (
          !angular.isObject(newData) ||
          newData.connection_error ||
          !angular.isArray(newData.resources) ||
          newData.resources.length === 0
        ) {
          pollTimeout = self._pollEmptyTimeout;
        }
        self._pollAgain(pollTimeout);
        return newData;
      },
      function(error) {
        // Don't raise the error, just log it and try again.
        console.log(error); // eslint-disable-line no-console
        self._pollAgain(self._pollErrorTimeout);
      }
    );
  };

  // Loads the resources. This implemented so the ManagerHelperService
  // can work on this manager just like all the rest.
  BootResourcesManager.prototype.loadItems = function() {
    var defer = $q.defer();
    this._loadData(true).then(function() {
      defer.resolve();
    });
    return defer.promise;
  };

  // Does nothing. This implemented so the ManagerHelperService
  // can work on this manager just like all the rest.
  BootResourcesManager.prototype.enableAutoReload = function() {};

  // Stop the running image import process.
  BootResourcesManager.prototype.stopImport = function(params) {
    var self = this;
    return RegionConnection.callMethod("bootresource.stop_import", params).then(
      function(newData) {
        angular.copy(angular.fromJson(newData), self._data);
        self._loaded = true;
        return self._data;
      }
    );
  };

  // Save the ubuntu options and start the import process.
  BootResourcesManager.prototype.saveUbuntu = function(params) {
    var self = this;
    return RegionConnection.callMethod("bootresource.save_ubuntu", params).then(
      function(newData) {
        angular.copy(angular.fromJson(newData), self._data);
        self._loaded = true;
        return self._data;
      }
    );
  };

  // Save the Ubuntu Core images and start the import process.
  BootResourcesManager.prototype.saveUbuntuCore = function(params) {
    var self = this;
    return RegionConnection.callMethod(
      "bootresource.save_ubuntu_core",
      params
    ).then(function(newData) {
      angular.copy(angular.fromJson(newData), self._data);
      self._loaded = true;
      return self._data;
    });
  };

  // Save the other images and start the import process.
  BootResourcesManager.prototype.saveOther = function(params) {
    var self = this;
    return RegionConnection.callMethod("bootresource.save_other", params).then(
      function(newData) {
        angular.copy(angular.fromJson(newData), self._data);
        self._loaded = true;
        return self._data;
      }
    );
  };

  // Fetch the releases and arches from the provided source.
  BootResourcesManager.prototype.fetch = function(source) {
    return RegionConnection.callMethod("bootresource.fetch", source);
  };

  // Delete an image.
  BootResourcesManager.prototype.deleteImage = function(params) {
    var self = this;
    return RegionConnection.callMethod(
      "bootresource.delete_image",
      params
    ).then(function(newData) {
      angular.copy(angular.fromJson(newData), self._data);
      self._loaded = true;
      return self._data;
    });
  };

  return new BootResourcesManager();
}

BootResourcesManager.$inject = [
  "$q",
  "$timeout",
  "RegionConnection",
  "ErrorService"
];

export default BootResourcesManager;
