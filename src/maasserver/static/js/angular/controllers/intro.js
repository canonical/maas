/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Intro Controller
 */

angular.module('MAAS').controller('IntroController', [
    '$rootScope', '$scope', '$window', '$location',
    'ConfigsManager', 'ManagerHelperService',
    function(
        $rootScope, $scope, $window, $location,
        ConfigsManager, ManagerHelperService) {

            $rootScope.page = "intro";
            $rootScope.title = "Welcome";

            $scope.loading = true;

            // Set the skip function on the rootScope to allow skipping the
            // intro view.
            $rootScope.skip = function() {
                ConfigsManager.updateItem({
                    'name': 'completed_intro',
                    'value': true
                }).then(function() {
                    // Reload the whole page so that the MAAS_config will be
                    // set to the new value.
                    $window.location.reload();
                });
            };

            // If intro has been completed redirect to '/'.
            if(MAAS_config.completed_intro) {
                $location.path('/');
            } else {
                // Load the required managers.
                ManagerHelperService.loadManager(
                    ConfigsManager).then(function() {
                        $scope.loading = false;
                    });
            }
    }]);
