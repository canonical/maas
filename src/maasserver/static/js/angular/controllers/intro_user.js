/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Intro Controller
 */

/* @ngInject */
function IntroUserController(
  $rootScope,
  $scope,
  $window,
  $location,
  UsersManager,
  ManagerHelperService
) {
  $rootScope.page = "intro";
  $rootScope.title = "Welcome";

  $scope.loading = true;
  $scope.user = null;

  // Set the skip function on the rootScope to allow skipping the
  // intro view.
  $rootScope.skip = function() {
    $scope.clickContinue(true);
  };

  // Return true if super user.
  $scope.isSuperUser = function() {
    return UsersManager.isSuperUser();
  };

  // Return true if continue can be clicked.
  $scope.canContinue = function() {
    return $scope.user.sshkeys_count > 0;
  };

  // Called when continue button is clicked.
  $scope.clickContinue = function(force) {
    if (angular.isUndefined(force)) {
      force = false;
    }
    if (force || $scope.canContinue()) {
      UsersManager.markIntroComplete().then(function() {
        // Reload the whole page so that the MAAS_config will
        // be set to the new value.
        $window.location.reload();
      });
    }
  };

  // If intro has been completed redirect to '/'.
  if (MAAS_config.user_completed_intro) {
    $location.path("/");
  } else {
    // Load the required managers.
    ManagerHelperService.loadManager($scope, UsersManager).then(function() {
      $scope.loading = false;
      $scope.user = UsersManager.getAuthUser();
    });
  }
}

export default IntroUserController;
