/* Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Version reloader.
 *
 * Watches the version reported by the GeneralManager if it changes then
 * the entire page is reloaded by-passing the local browser cache.
 */

/* @ngInject */
function maasVersionReloader(
  $window,
  GeneralManager,
  ManagerHelperService,
  LogService
) {
  return {
    restrict: "A",
    controller: VersionReloaderController
  };

  /* @ngInject */
  function VersionReloaderController($scope) {
    $scope.version = GeneralManager.getData("version");

    // Reload the page by-passing the browser cache.
    $scope.reloadPage = function() {
      // Force cache reload by passing true.
      $window.location.reload(true);
    };

    ManagerHelperService.loadManager($scope, GeneralManager).then(function() {
      GeneralManager.enableAutoReload(true);
      LogService.info(
        'Version reloader: Monitoring MAAS "' + $scope.site + '"; version',
        $scope.version.text,
        "via",
        $window.location.href
      );
      $scope.$watch("version.text", function(newValue, oldValue) {
        if (newValue !== oldValue) {
          LogService.info(
            "MAAS version changed from '" +
              oldValue +
              "' to '" +
              newValue +
              "'; forcing reload."
          );
          $scope.reloadPage();
        }
      });
    });
  }
}

export default maasVersionReloader;
