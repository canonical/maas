/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Error Controller
 */

angular.module('MAAS').controller('ErrorController', [
    '$scope', '$rootScope', '$location', 'ErrorService', function($scope,
        $rootScope, $location, ErrorService) {

        // Set the title and page.
        $rootScope.title = "Error";
        $rootScope.page = "";

        // Get the error message and clear it in the service.
        $scope.error = ErrorService._error;
        ErrorService._error = null;

        // Get the url to return to when back is clicked.
        $scope.backUrl = ErrorService._backUrl;
        ErrorService._backUrl = null;

        // If the error is not a string then the user should not be here.
        if(!angular.isString($scope.error)) {
            // Go back to index.
            $location.path('/');
        }

        // Go back to previous page.
        $scope.goBack = function() {
            if(angular.isString($scope.backUrl)) {
                $location.path($scope.backUrl);
            } else {
                $location.path('/');
            }
        };
    }]);
