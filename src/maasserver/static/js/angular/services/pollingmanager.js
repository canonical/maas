/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Space Manager
 *
 * Manages all of the spaces in the browser. The manager uses the
 * RegionConnection to load the spaces, update the spaces, and listen for
 * notification events about spaces.
 */

/* @ngInject */
function PollingManager($q, $timeout, Manager) {
  function PollingManager() {
    Manager.call(this);

    // The way this manager recieves its updated information. 'poll'
    // means this manager periodicly polls for new data from the
    // websocket.
    this._type = "poll";

    // Set to true when polling has been enabled.
    this._polling = false;

    // The next promise for the polling interval.
    this._nextPromise = null;

    // Amount of time in milliseconds the manager should wait to poll
    // for new data.
    this._pollTimeout = 10000;

    // Amount of time in milliseconds the manager should wait to poll
    // for new data when an error occurs.
    this._pollErrorTimeout = 3000;

    // Amount of time in milliseconds the manager should wait to poll
    // for new data when the retrieved data is empty.
    this._pollEmptyTimeout = 3000;
  }

  PollingManager.prototype = new Manager();

  // Returns true when currently polling.
  PollingManager.prototype.isPolling = function() {
    return this._polling;
  };

  // Starts the polling.
  PollingManager.prototype.startPolling = function() {
    if (!this._polling) {
      this._polling = true;
      return this._poll();
    } else {
      return this._nextPromise;
    }
  };

  // Stops the polling.
  PollingManager.prototype.stopPolling = function() {
    this._polling = false;
    if (angular.isObject(this._nextPromise)) {
      $timeout.cancel(this._nextPromise);
      this._nextPromise = null;
    }
  };

  // Registers the next polling attempt.
  PollingManager.prototype._pollAgain = function(timeout) {
    var self = this;
    this._nextPromise = $timeout(function() {
      self._poll();
    }, timeout);
    return this._nextPromise;
  };

  // Polls for the data from the region.
  PollingManager.prototype._poll = function() {
    var self = this;
    return this.reloadItems().then(
      function(items) {
        var pollTimeout = self._pollTimeout;
        if (items.length === 0) {
          pollTimeout = self._pollEmptyTimeout;
        }
        self._pollAgain(pollTimeout);
        return items;
      },
      function(error) {
        self._pollAgain(self._pollErrorTimeout);
        return $q.reject(error);
      }
    );
  };

  return PollingManager;
}

PollingManager.$inject = ["$q", "$timeout", "Manager"];

export default PollingManager;
