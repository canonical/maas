/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Error Service
 */

function ErrorService() {
  // Holds the client error.
  this._error = null;

  // Raise this error in the UI.
  this.raiseError = function(error) {
    // Possible that this method is called more than once.
    // Only take the first error.
    if (!angular.isString(this._error)) {
      this._error = error;
    }
  };
}

export default ErrorService;
