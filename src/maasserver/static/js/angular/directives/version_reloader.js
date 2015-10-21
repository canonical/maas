/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Version reloader.
 *
 * Watches the version reported by the GeneralManager if it changes then
 * the entire page is reloaded by-passing the local browser cache.
 */


angular.module('MAAS').directive('maasVersionReloader', [
    '$window', 'GeneralManager', 'ManagerHelperService',
    function($window, GeneralManager, ManagerHelperService) {
        return {
            restrict: "A",
            controller: function($scope) {
                $scope.version = GeneralManager.getData("version");

                // Reload the page by-passing the browser cache.
                $scope.reloadPage = function() {
                    // Force cache reload by passing true.
                    $window.location.reload(true);
                };

                ManagerHelperService.loadManager(GeneralManager).then(
                    function() {
                        GeneralManager.enableAutoReload(true);
                        $scope.$watch("version.text",
                            function(newValue, oldValue) {
                                if(newValue !== oldValue) {
                                    $scope.reloadPage();
                                }
                            });
                    });
            }
        };
    }]);
