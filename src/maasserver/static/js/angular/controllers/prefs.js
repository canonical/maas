/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Preferences Controller
 */

function PreferencesController(
    $scope, UsersManager, ManagerHelperService) {
    $scope.loading = true;
    ManagerHelperService.loadManager(
        $scope, UsersManager).then(function() {
            $scope.loading = false;
        });
};

angular.module('MAAS').controller(
    'PreferencesController', PreferencesController);
