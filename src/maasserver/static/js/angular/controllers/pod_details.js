/* Copyright 2017 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Node Details Controller
 */

angular.module('MAAS').controller('PodDetailsController', [
    '$scope', '$rootScope', '$location', '$routeParams',
    'PodsManager', 'GeneralManager', 'UsersManager',
    'ManagerHelperService', 'ErrorService', function(
        $scope, $rootScope, $location, $routeParams,
        PodsManager, GeneralManager, UsersManager,
        ManagerHelperService, ErrorService) {

        // Set title and page.
        $rootScope.title = "Loading...";
        $rootScope.page = "pods";

        // Initial values.
        $scope.loaded = false;
        $scope.pod = null;
        $scope.action = {
          option: null,
          options: [
            {
              name: 'refresh',
              title: 'Refresh',
              sentence: 'refresh',
              operation: angular.bind(PodsManager, PodsManager.refresh)
            },
            {
              name: 'delete',
              title: 'Delete',
              sentence: 'delete',
              operation: angular.bind(PodsManager, PodsManager.deleteItem)
            }
          ],
          inProgress: false,
          error: null
        };
        $scope.powerTypes = GeneralManager.getData("power_types");

        // Return true if the authenticated user is super user.
        $scope.isSuperUser = function() {
            return UsersManager.isSuperUser();
        };

        // Return true if there is an action error.
        $scope.isActionError = function() {
            return $scope.action.error !== null;
        };

        // Called when the action.option has changed.
        $scope.actionOptionChanged = function() {
            // Clear the action error.
            $scope.action.error = null;
        };

        // Cancel the action.
        $scope.actionCancel = function() {
            $scope.action.option = null;
            $scope.action.error = null;
        };

        // Perform the action.
        $scope.actionGo = function() {
            $scope.action.inProgress = true;
            $scope.action.option.operation($scope.pod).then(function() {
                  // If the action was delete, then go back to listing.
                  if($scope.action.option.name === "delete") {
                      $location.path("/pods");
                  }
                  $scope.action.inProgress = false;
                  $scope.action.option = null;
                  $scope.action.error = null;
              }, function(error) {
                  $scope.action.inProgress = false;
                  $scope.action.error = error;
              });
        };

        // Start watching key fields.
        $scope.startWatching = function() {
            $scope.$watch("pod.name", function() {
                $rootScope.title = 'Pod ' + $scope.pod.name;
            });
        };

        // Load all the required managers.
        ManagerHelperService.loadManagers($scope, [
            PodsManager, GeneralManager, UsersManager]).then(function() {
            // Possibly redirected from another controller that already had
            // this pod set to active. Only call setActiveItem if not already
            // the activeItem.
            var activePod = PodsManager.getActiveItem();
            if(angular.isObject(activePod) &&
                activePod.id === parseInt($routeParams.id, 10)) {
                $scope.pod = activePod;
                $scope.loaded = true;
                $scope.startWatching();
            } else {
                PodsManager.setActiveItem(
                    parseInt($routeParams.id, 10)).then(function(pod) {
                        $scope.pod = pod;
                        $scope.loaded = true;
                        $scope.startWatching();
                    }, function(error) {
                        ErrorService.raiseError(error);
                    });
            }
        });
    }]);
