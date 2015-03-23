/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Node Details Controller
 */

angular.module('MAAS').controller('NodeDetailsController', [
    '$scope', '$rootScope', '$routeParams', '$location',
    'NodesManager', 'ClustersManager', 'ZonesManager', 'GeneralManager',
    'ManagerHelperService', 'ErrorService', function(
        $scope, $rootScope, $routeParams, $location,
        NodesManager, ClustersManager, ZonesManager, GeneralManager,
        ManagerHelperService, ErrorService) {

        // Set title and page.
        $rootScope.title = "Loading...";
        $rootScope.page = "nodes";

        // Initial values.
        $scope.loaded = false;
        $scope.node = null;
        $scope.actionOption = null;
        $scope.allActionOptions = GeneralManager.getData("actions");
        $scope.availableActionOptions = [];
        $scope.osinfo = GeneralManager.getData("osinfo");

        // Summary section.
        $scope.summary = {
            editing: false,
            cluster: {
                selected: null,
                options: ClustersManager.getItems()
            },
            architecture: {
                selected: null,
                options: GeneralManager.getData("architectures")
            },
            zone: {
                selected: null,
                options: ZonesManager.getItems()
            }
        };

        // Power section.
        $scope.power = {
            editing: false,
            type: null,
            parameters: {}
        };

        // Updates the page title.
        function updateTitle() {
            if($scope.node && $scope.node.fqdn) {
                $rootScope.title = $scope.node.fqdn;
            }
        }

        // Update the available action options for the node.
        function updateAvailableActionOptions() {
            $scope.availableActionOptions = [];
            if(!$scope.node) {
                return;
            }

            angular.forEach($scope.allActionOptions, function(option) {
                if($scope.node.actions.indexOf(option.name) >= 0) {
                    $scope.availableActionOptions.push(option);
                }
            });
        }

        // Updates the currently selected items in the power section.
        function updatePower() {
            // Do not update the selected items, when editing this would
            // cause the users selection to change.
            if($scope.power.editing) {
                return;
            }

            var cluster = ClustersManager.getItemFromList(
                $scope.node.nodegroup.id);
            if(angular.isObject(cluster)) {
                $scope.power.types = cluster.power_types;
            } else {
                $scope.power.types = [];
            }

            var i;
            $scope.power.type = null;
            for(i = 0; i < $scope.power.types.length; i++) {
                if($scope.node.power_type === $scope.power.types[i].name) {
                    $scope.power.type = $scope.power.types[i];
                    break;
                }
            }
            $scope.power.parameters = angular.copy(
                $scope.node.power_parameters);
            if(!angular.isObject($scope.power.parameters)) {
                $scope.power.parameters = {};
            }
        }

        // Updates the currently selected items in the summary section.
        function updateSummary() {
            // Do not update the selected items, when editing this would
            // cause the users selection to change.
            if($scope.summary.editing) {
                return;
            }

            $scope.summary.cluster.selected = ClustersManager.getItemFromList(
                $scope.node.nodegroup.id);
            $scope.summary.zone.selected = ZonesManager.getItemFromList(
                $scope.node.zone.id);
            $scope.summary.architecture.selected = $scope.node.architecture;

            // Since the summary contains the selected cluster and the
            // power type is derived for that selection. Update the power
            // section as well.
            updatePower();
        }

        // Starts the watchers on the scope.
        function startWatching() {
            // Update the title when the node fqdn changes.
            $scope.$watch("node.fqdn", updateTitle);

            // Update the availableActionOptions when the node actions change.
            $scope.$watch("node.actions", updateAvailableActionOptions);

            // Update the summary when the node or clusters list is
            // updated.
            $scope.$watch("node.nodegroup.id", updateSummary);
            $scope.$watchCollection(
                $scope.summary.cluster.options, updateSummary);

            // Update the summary when the node or architectures list is
            // updated.
            $scope.$watch("node.architecture", updateSummary);
            $scope.$watchCollection(
                $scope.summary.architecture.options, updateSummary);

            // Update the summary when the node or zone list is
            // updated.
            $scope.$watch("node.zone.id", updateSummary);
            $scope.$watchCollection(
                $scope.summary.zone.options, updateSummary);

            // Update the power when the node power_type or power_parameters
            // are updated.
            $scope.$watch("node.power_type", updatePower);
            $scope.$watch("node.power_parameters", updatePower);
        }

        // Get the power state text to show.
        $scope.getPowerStateText = function() {
            // This will get called very early and node can be empty.
            // In that case just return an empty string. It will be
            // called again to show the correct information.
            if(!angular.isObject($scope.node)) {
                return "";
            }

            if($scope.node.power_state === "unknown") {
                return "";
            } else {
                return "Power " + $scope.node.power_state;
            }
        };

        // Returns the nice name of the OS for the node.
        $scope.getOSText = function() {
            // This will get called very early and node can be empty.
            // In that case just return an empty string. It will be
            // called again to show the correct information.
            if(!angular.isObject($scope.node)) {
                return "";
            }

            var i;
            var os_release = $scope.node.osystem +
                "/" + $scope.node.distro_series;

            // Possible that osinfo has not been fully loaded. In that case
            // we just return the os_release identifier.
            if(angular.isUndefined($scope.osinfo.releases)) {
                return os_release;
            }

            // Get the nice release name from osinfo.
            for(i = 0; i < $scope.osinfo.releases.length; i++) {
                var release = $scope.osinfo.releases[i];
                if(release[0] === os_release) {
                    return release[1];
                }
            }
            return os_release;
        };

        // Return True if in deploy action and the osinfo is missing.
        $scope.isDeployError = function() {
            var missing_osinfo = (
                angular.isUndefined($scope.osinfo.osystems) ||
                $scope.osinfo.osystems.length === 0);
            if(angular.isObject($scope.actionOption) &&
                $scope.actionOption.name === "deploy" &&
                missing_osinfo) {
                return true;
            }
            return false;
        };

        // Cancel the action.
        $scope.actionCancel = function() {
            $scope.actionOption = null;
        };

        // Perform the action.
        $scope.actionGo = function() {
            NodesManager.performAction(
                $scope.node, $scope.actionOption.name).then(function() {
                    // If the action was delete, then go back to listing.
                    if($scope.actionOption.name === "delete") {
                        $location.path("/nodes");
                    }
                    $scope.actionOption = null;
                }, function(error) {
                    // Report error loading. This is simple handlng for
                    // now but this should show a nice error dialog or
                    // something.
                    console.log(error);
                });
        };

        // Called to enter edit mode in the summary section.
        $scope.editSummary = function() {
            $scope.summary.editing = true;
        };

        // Called to cancel editing in the summary section.
        $scope.cancelEditSummary = function() {
            $scope.summary.editing = false;
            updateSummary();
        };

        // Called to save the changes made in the summary section.
        $scope.saveEditSummary = function() {
            // XXX blake_r - TODO the actual saving. Currently does nothing.
            $scope.summary.editing = false;
            updateSummary();
        };

        // Called to enter edit mode in the power section.
        $scope.editPower = function() {
            $scope.power.editing = true;
        };

        // Called to cancel editing in the power section.
        $scope.cancelEditPower = function() {
            $scope.power.editing = false;
            updatePower();
        };

        // Called to save the changes made in the power section.
        $scope.saveEditPower = function() {
            // XXX blake_r - TODO the actual saving. Currently does nothing.
            $scope.power.editing = false;
            updatePower();
        };

        // Load all the required managers.
        ManagerHelperService.loadManagers([
            NodesManager,
            ClustersManager,
            ZonesManager,
            GeneralManager
        ]).then(function() {
            // Get the active node and set loaded to true.
            NodesManager.setActiveItem(
                $routeParams.system_id).then(function(node) {
                    $scope.node = node;
                    $scope.loaded = true;

                    updateTitle();
                    updateSummary();
                    startWatching();
                }, function(error) {
                    ErrorService.raiseError(error);
                });

            // Poll for architectures and osinfo the whole time. This is
            // because the user can always see the architecture and
            // operating system. Need to keep this information up-to-date
            // so the user is viewing current data.
            GeneralManager.startPolling("architectures");
            GeneralManager.startPolling("osinfo");
        });

        // Stop polling for architectures and osinfo when the scope is
        // destroyed.
        $scope.$on("$destroy", function() {
            GeneralManager.stopPolling("architectures");
            GeneralManager.stopPolling("osinfo");
        });
    }]);
