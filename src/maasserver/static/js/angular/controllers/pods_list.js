/* Copyright 2017-2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Pods List Controller
 */

angular.module('MAAS').controller('PodsListController', [
    '$scope', '$rootScope',
    'PodsManager', 'UsersManager', 'GeneralManager', 'ZonesManager',
    'ManagerHelperService', function(
        $scope, $rootScope, PodsManager, UsersManager, GeneralManager,
        ZonesManager, ManagerHelperService) {

        // Set title and page.
        $rootScope.title = "Pods";
        $rootScope.page = "pods";

        // Set initial values.
        $scope.podManager = PodsManager;
        $scope.pods = PodsManager.getItems();
        $scope.loading = true;

        $scope.filteredItems = [];
        $scope.selectedItems = PodsManager.getSelectedItems();
        $scope.predicate = 'name';
        $scope.allViewableChecked = false;
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
          progress: {
              total: 0,
              completed: 0,
              errors: 0
          }
        };
        $scope.add = {
          open: false,
          obj: {}
        };
        $scope.powerTypes = GeneralManager.getData("power_types");
        $scope.zones = ZonesManager.getItems();

        // Called to update `allViewableChecked`.
        function updateAllViewableChecked() {
            // Not checked when no pods.
            if($scope.pods.length === 0) {
                $scope.allViewableChecked = false;
                return;
            }

            // Loop through all filtered pods and see if all are checked.
            var i;
            for(i = 0; i < $scope.pods.length; i++) {
                if(!$scope.pods[i].$selected) {
                    $scope.allViewableChecked = false;
                    return;
                }
            }
            $scope.allViewableChecked = true;
        }

        function clearAction() {
            resetActionProgress();
            $scope.action.option = null;
        }

        // Clear the action if required.
        function shouldClearAction() {
            if($scope.selectedItems.length === 0) {
                clearAction();
                if($scope.action.option) {
                    $scope.action.option = null;
                }
            }
        }

        // Reset actionProgress to zero.
        function resetActionProgress() {
            var progress = $scope.action.progress;
            progress.completed = progress.total = progress.errors = 0;
            angular.forEach($scope.pods, function(pod) {
                delete pod.action_failed;
            });
        }

        // After an action has been performed check if we can leave all pods
        // selected or if an error occured and we should only show the failed
        // pods.
        function updateSelectedItems() {
            if(!$scope.hasActionsFailed()) {
                if(!$scope.hasActionsInProgress()) {
                     clearAction();
                }
                return;
            }
            angular.forEach($scope.pods, function(pod) {
                if(pod.action_failed === false) {
                    PodsManager.unselectItem(pod.id);
                }
            });
            shouldClearAction();
        }

        // Mark a pod as selected or unselected.
        $scope.toggleChecked = function(pod) {
            if(PodsManager.isSelected(pod.id)) {
                PodsManager.unselectItem(pod.id);
            } else {
                PodsManager.selectItem(pod.id);
            }
            updateAllViewableChecked();
            shouldClearAction();
        };

        // Select all viewable pods or deselect all viewable pods.
        $scope.toggleCheckAll = function() {
            if($scope.allViewableChecked) {
                angular.forEach($scope.pods, function(pod) {
                    PodsManager.unselectItem(pod.id);
                });
            } else {
                angular.forEach($scope.pods, function(pod) {
                    PodsManager.selectItem(pod.id);
                });
            }
            updateAllViewableChecked();
            shouldClearAction();
        };

        // When the pods change update if all check buttons should be
        // checked or not.
        $scope.$watchCollection("pods", function() {
            updateAllViewableChecked();
        });

        // Sorts the table by predicate.
        $scope.sortTable = function(predicate) {
            $scope.predicate = predicate;
            $scope.reverse = !$scope.reverse;
        };

        // Called when the current action is cancelled.
        $scope.actionCancel = function() {
            resetActionProgress();
            $scope.action.option = null;
        };

        // Perform the action on all pods.
        $scope.actionGo = function() {
            var extra = {};

            // Setup actionProgress.
            resetActionProgress();
            $scope.action.progress.total = $scope.selectedItems.length;

            // Perform the action on all selected items.
            var operation = $scope.action.option.operation;
            angular.forEach($scope.selectedItems, function(pod) {
                operation(pod).then(function() {
                        $scope.action.progress.completed += 1;
                        pod.action_failed = false;
                        updateSelectedItems();
                    }, function(error) {
                        $scope.action.progress.errors += 1;
                        pod.action_error = error;
                        pod.action_failed = true;
                        updateSelectedItems();
                    });
            });
        };

        // Returns true when actions are being performed.
        $scope.hasActionsInProgress = function() {
            var progress = $scope.action.progress;
            return progress.total > 0 && (
                progress.completed + progress.errors) !== progress.total;
        };

        // Returns true if any of the actions have failed.
        $scope.hasActionsFailed = function() {
            var progress = $scope.action.progress;
            return progress.errors > 0;
        };

        // Called when the add pod button is pressed.
        $scope.addPod = function() {
            $scope.add.open = true;
        };

        // Called when the cancel add pod button is pressed.
        $scope.cancelAddPod = function() {
            $scope.add.open = false;
            $scope.add.obj = {};
        };

        // Return true if the authenticated user is super user.
        $scope.isSuperUser = function() {
            return UsersManager.isSuperUser();
        };

        // Return the title of the power type.
        $scope.getPowerTypeTitle = function(power_type) {
            var i;
            for(i = 0; i < $scope.powerTypes.length; i++) {
                var powerType = $scope.powerTypes[i];
                if(powerType.name === power_type) {
                    return powerType.description;
                }
            }
            return power_type;
        };

        // Load the required managers for this controller.
        ManagerHelperService.loadManagers($scope, [
            PodsManager, UsersManager, GeneralManager, ZonesManager]).then(
            function() {
                $scope.loading = false;
            });
    }]);
