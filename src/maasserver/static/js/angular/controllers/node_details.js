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

        // Holds errors that are displayed on the details page.
        $scope.errors = {
            cluster_disconnected: {
                viewable: false,
                message: "The cluster this node belongs to is disconnected. " +
                    "No changes can be made to this node until the cluster " +
                    "is reconnected"
            },
            invalid_arch: {
                viewable: false,
                message: "This node has an invalid architecture. Update the " +
                    "architecture for this node in the summary section below."
            },
            missing_power: {
                viewable: false,
                message: "This node does not have a power type set and " +
                    "MAAS will be unable to control it. Update the power " +
                    "information in the power section below."
            }
        };

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

        // Show given error.
        function showError(name) {
            $scope.errors[name].viewable = true;
        }

        // Hide given error.
        function hideError(name) {
            $scope.errors[name].viewable = false;
        }

        // Return true if the error is viewable.
        function isErrorViewable(name) {
            return $scope.errors[name].viewable;
        }

        // Return true if the architecture for the given node is invalid.
        function hasInvalidArchitecture(node) {
            return (
                node.architecture === "" ||
                $scope.summary.architecture.options.indexOf(
                    node.architecture) === -1);
        }

        // Update the shown errors based on the status of the node.
        function updateErrors() {
            // Check if the nodes power type is null, if so then show the
            // missing_power error.
            if($scope.node.power_type === "") {
                showError("missing_power");
            } else {
                hideError("missing_power");
            }

            // Show architecture error if the node doesn't have an architecture
            // or if the current architecture is not in the available
            // architectures.
            if(hasInvalidArchitecture($scope.node)) {
                showError("invalid_arch");
            } else {
                hideError("invalid_arch");
            }

            // Show the cluster disconnected error if the cluster is not
            // connected.
            var cluster = ClustersManager.getItemFromList(
                $scope.node.nodegroup.id);
            if(!cluster.connected) {
                showError("cluster_disconnected");
            } else {
                hideError("cluster_disconnected");
            }
        }

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
            // Update the viewable errors.
            updateErrors();

            // Always keep the available power types up-to-date even in
            // editing mode.
            var cluster = ClustersManager.getItemFromList(
                $scope.node.nodegroup.id);
            if(angular.isObject(cluster)) {
                $scope.power.types = cluster.power_types;
            } else {
                $scope.power.types = [];
            }

            // Do not update the selected items, when editing this would
            // cause the users selection to change.
            if($scope.power.editing) {
                return;
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

            // Force editing mode on, if the power_type is missing. This is
            // placed at the bottom because we wanted the selected items to
            // be filled in atleast once.
            if($scope.canEdit() && $scope.node.power_type === "") {
                $scope.power.editing = true;
            }
        }

        // Updates the currently selected items in the summary section.
        function updateSummary() {
            // Update the viewable errors.
            updateErrors();

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

            // Force editing mode on, if the architecture is invalid. This is
            // placed at the bottom because we wanted the selected items to
            // be filled in atleast once.
            if($scope.canEdit() && hasInvalidArchitecture($scope.node)) {
                $scope.summary.editing = true;
            }

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

        // Return true if the given error is because of RPC.
        function isDisconnectedClusterError(error) {
            // Contains disconnected cluster if error contains this content.
            var errorString = "Unable to get RPC connection for cluster";
            return error.indexOf(errorString) >= 0;
        }

        // Process the given error when saving the node.
        function handleSaveError(error) {
            // If it errored because the cluster was disconnected update
            // the cluster information, because this is not pushed over
            // the websocket. If it didn't error for that reason then
            // the cluster is connected.
            var cluster = ClustersManager.getItemFromList(
                $scope.node.nodegroup.id);
            if(isDisconnectedClusterError(error)) {
                if(angular.isObject(cluster)) {
                    cluster.connected = false;
                }
            } else {
                if(angular.isObject(cluster)) {
                    cluster.connected = true;
                }

                // Unknown error that we currently don't track so log
                // it to the console.
                console.log(error);
            }
        }

        // Update the node with new data on the region.
        function updateNode(node) {
            NodesManager.updateItem(node).then(function(node) {
                // If it was able to save correctly then the cluster is
                // connected. An error would have been raised if it wasn't.
                var cluster = ClustersManager.getItemFromList(
                    node.nodegroup.id);
                if(angular.isObject(cluster)) {
                    cluster.connected = true;
                }
                updateSummary();
            }, function(error) {
                handleSaveError(error);
                updateSummary();
            });
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

        // Return true if the current architecture selection is invalid.
        $scope.invalidArchitecture = function() {
            return (
                $scope.summary.architecture.selected === "" ||
                $scope.summary.architecture.options.indexOf(
                    $scope.summary.architecture.selected) === -1);
        };

        // Return true when the edit buttons can be clicked.
        $scope.canEdit = function() {
            return !isErrorViewable("cluster_disconnected");
        };

        // Called to enter edit mode in the summary section.
        $scope.editSummary = function() {
            $scope.summary.editing = true;
        };

        // Called to cancel editing in the summary section.
        $scope.cancelEditSummary = function() {
            // Leave edit mode only if node has valid architecture.
            if(!hasInvalidArchitecture($scope.node)) {
                $scope.summary.editing = false;
            }

            updateSummary();
        };

        // Called to save the changes made in the summary section.
        $scope.saveEditSummary = function() {
            // Do nothing if invalidArchitecture.
            if($scope.invalidArchitecture()) {
                return;
            }

            $scope.summary.editing = false;

            // Copy the node and make the changes.
            var node = angular.copy($scope.node);
            node.nodegroup = angular.copy($scope.summary.cluster.selected);
            node.zone = angular.copy($scope.summary.zone.selected);
            node.architecture = $scope.summary.architecture.selected;

            // Update the node.
            updateNode(node);
        };

        // Return true if the current power type selection is invalid.
        $scope.invalidPowerType = function() {
            return !angular.isObject($scope.power.type);
        };

        // Called to enter edit mode in the power section.
        $scope.editPower = function() {
            $scope.power.editing = true;
        };

        // Called to cancel editing in the power section.
        $scope.cancelEditPower = function() {
            // Only leave edit mode if node has valid power type.
            if($scope.node.power_type !== "") {
                $scope.power.editing = false;
            }
            updatePower();
        };

        // Called to save the changes made in the power section.
        $scope.saveEditPower = function() {
            // Does nothing if invalid power type.
            if($scope.invalidPowerType()) {
                return;
            }
            $scope.power.editing = false;

            // Copy the node and make the changes.
            var node = angular.copy($scope.node);
            node.power_type = $scope.power.type.name;
            node.power_parameters = angular.copy($scope.power.parameters);

            // Update the node.
            updateNode(node);
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
