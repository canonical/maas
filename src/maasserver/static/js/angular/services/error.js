/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Error Service
 */

angular.module('MAAS').service('ErrorService', ['$location',
    function($location) {

        // Holds the raised error and url when the error was raised.
        this._error = null;
        this._backUrl = null;

        // Raise this error in the UI. Will cause the page to redirect to the
        // error page.
        this.raiseError = function(error) {
            // Possible that this method is called more than once, before the
            // location is changed. Only take the first error.
            if(!angular.isString(this._error)) {
                this._error = error;
                this._backUrl = $location.url();
            }
            $location.path('/error');
        };
    }]);
