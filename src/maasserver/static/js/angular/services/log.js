/* Copyright 2017 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Log Service
 *
 * Allows logging to be enabled or disabled, and allows a particular log level
 * to be set, which will allow logs of a specified importance (or more) to be
 * seen.
 *
 * Also appends a time index (in seconds, accurate to milliseconds) to the
 * beginning of the log string.
 */

/* @ngInject */
function LogService($window) {
  var self = this;

  // Global enable/disable for MAAS logging. If set to `false`, this
  // value takes precedence over the logLevel.
  self.logging = true;

  // Specifies the log level.
  // Level 1: error() logging
  // Level 2: error() and warn() logging
  // Level 3: all of the above, plus info()
  // Level 4: all of the above, plus log()
  // Level 5: all of the above, plus debug()
  self.logLevel = 5;

  // Returns a monotonic time (in milliseconds) since page load.
  self.now = function() {
    return $window.performance ? $window.performance.now() : 0;
  };

  // Standard logging functions.
  /* eslint-disable no-console */
  self._debug = console.debug;
  self._log = console.log;
  self._info = console.info;
  self._warn = console.warn;
  self._error = console.error;
  /* eslint-enable no-console */

  // Formats the specified time (in milliseconds) in seconds.
  this.formatMilliseconds = function(milliseconds) {
    return parseFloat(milliseconds / 1000.0).toFixed(3);
  };

  // Internal function to log using the specified destination, with the
  // specified list of arguments.
  this.__log = function(destination, args) {
    if (self.logging === true) {
      // Add time index to the beginning of the log.
      Array.prototype.unshift.call(
        args,
        "[" + self.formatMilliseconds(self.now()) + "]"
      );
      destination.apply(console, args);
    }
  };

  // Wrapper to check the log level and then call self._debug().
  this.debug = function() {
    if (self.logLevel >= 5) {
      self.__log(self._debug, arguments);
    }
  };

  // Wrapper to check the log level and then call self._log().
  this.log = function() {
    if (self.logLevel >= 4) {
      self.__log(self._log, arguments);
    }
  };

  // Wrapper to check the log level and then call self._info().
  this.info = function() {
    if (self.logLevel >= 3) {
      self.__log(self._info, arguments);
    }
  };

  // Wrapper to check the log level and then call self._warn().
  this.warn = function() {
    if (self.logLevel >= 2) {
      self.__log(self._warn, arguments);
    }
  };

  // Wrapper to check the log level and then call self._err().
  this.error = function() {
    if (self.logLevel >= 1) {
      self.__log(self._error, arguments);
    }
  };
}

export default LogService;
