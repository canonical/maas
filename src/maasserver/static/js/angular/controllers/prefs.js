/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Preferences Controller
 */

angular.module('MAAS').controller('PreferencesController', [
    '$scope', 'UsersManager', 'ManagerHelperService',
    function(
        $scope, UsersManager, ManagerHelperService) {
            $scope.loading = true;
            ManagerHelperService.loadManager(UsersManager).then(function() {
                $scope.loading = false;
            });
    }]);
