/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Node Details Controller
 */

angular.module('MAAS').controller('NodeDetailsController', [
    '$scope', '$rootScope', '$routeParams', '$location',
    'NodesManager', 'ClustersManager', 'ZonesManager', 'GeneralManager',
    'UsersManager', 'ManagerHelperService', 'ErrorService',
    'ValidationService', function(
        $scope, $rootScope, $routeParams, $location,
        NodesManager, ClustersManager, ZonesManager, GeneralManager,
        UsersManager, ManagerHelperService, ErrorService, ValidationService) {

        // Set title and page.
        $rootScope.title = "Loading...";
        $rootScope.page = "nodes";

        // Initial values.
        $scope.loaded = false;
        $scope.node = null;
        $scope.actionOption = null;
        $scope.allActionOptions = GeneralManager.getData("node_actions");
        $scope.availableActionOptions = [];
        $scope.actionError = null;
        $scope.osinfo = GeneralManager.getData("osinfo");
        $scope.osSelection = {
            osystem: null,
            release: null
        };
        $scope.checkingPower = false;
        $scope.nic = {
            adding: false,
            error: false,
            errormsg: ""
        };

        // Holds errors that are displayed on the details page.
        $scope.errors = {
            cluster_disconnected: {
                viewable: false,
                message: "The cluster this node belongs to is disconnected. " +
                    "Reconnect the cluster to the region controller to save " +
                    "changes on this node."
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

        // Node name header section.
        $scope.nameHeader = {
            editing: false,
            value: ""
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

        // Storage section.
        $scope.storage = {
            column: 'model'
        };

        // Events section.
        $scope.events = {
            limit: 10
        };

        // Machine output section.
        $scope.machine_output = {
            viewable: false,
            selectedView: null,
            views: [],
            showSummaryToggle: true,
            summaryType: 'yaml'
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

        function updateName() {
            // Don't update the value if in editing mode. As this would
            // overwrite the users changes.
            if($scope.nameHeader.editing) {
                return;
            }
            $scope.nameHeader.value = $scope.node.fqdn;
        }

        // Update the available action options for the node.
        function updateAvailableActionOptions() {
            $scope.availableActionOptions = [];
            if(!$scope.node) {
                return;
            }

            // Build the available action options control from the
            // allowed actions, except set-zone which does not make
            // sense in this view because the form has this
            // functionality
            angular.forEach($scope.allActionOptions, function(option) {
                if($scope.node.actions.indexOf(option.name) >= 0
                   && option.name !== "set-zone") {
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

        // Updates the machine output section.
        function updateMachineOutput() {
            // Set if it should even be viewable.
            $scope.machine_output.viewable = (
                angular.isString($scope.node.summary_xml) ||
                angular.isString($scope.node.summary_yaml) ||
                $scope.node.commissioning_results.length > 0 ||
                $scope.node.installation_results.length > 0);

            // Grab the selected view name, so it can be kept the same if
            // possible.
            var viewName = null;
            if(angular.isObject($scope.machine_output.selectedView)) {
                viewName = $scope.machine_output.selectedView.name;
            }

            // If the viewName is empty, then a default one was not selected.
            // We want the installation output to be the default if possible.
            if(!angular.isString(viewName)) {
                viewName = "install";
            }

            // Setup the views that are viewable.
            $scope.machine_output.views = [];
            if(angular.isString($scope.node.summary_xml) ||
                angular.isString($scope.node.summary_yaml)) {
                $scope.machine_output.views.push({
                    name: "summary",
                    title: "Commissioning Summary"
                });
            }
            if($scope.node.commissioning_results.length > 0) {
                $scope.machine_output.views.push({
                    name: "output",
                    title: "Commissioning Output"
                });
            }
            if($scope.node.installation_results.length > 0) {
                $scope.machine_output.views.push({
                    name: "install",
                    title: "Installation Output"
                });
            }

            // Set the selected view to its previous value or to the first
            // entry in the views list.
            var selectedView = null;
            angular.forEach($scope.machine_output.views, function(view) {
                if(view.name === viewName) {
                    selectedView = view;
                }
            });
            if(angular.isObject(selectedView)) {
                $scope.machine_output.selectedView = selectedView;
            } else if ($scope.machine_output.views.length > 0) {
                $scope.machine_output.selectedView =
                    $scope.machine_output.views[0];
            } else {
                $scope.machine_output.selectedView = null;
            }

            // Show the summary toggle if in the summary view.
            $scope.machine_output.showSummaryToggle = false;
            if(angular.isObject($scope.machine_output.selectedView) &&
                $scope.machine_output.selectedView.name === "summary") {
                $scope.machine_output.showSummaryToggle = true;
            }
        }

        // Starts the watchers on the scope.
        function startWatching() {
            // Update the title and name when the node fqdn changes.
            $scope.$watch("node.fqdn", function() {
                updateTitle();
                updateName();
            });

            // Update the availableActionOptions when the node actions change.
            $scope.$watch("node.actions", updateAvailableActionOptions);

            // Update the errors when the selected cluster becomes connected
            // or disconnected.
            $scope.$watch("summary.cluster.selected.connected", updateErrors);

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

            // Update the machine output view when summary, commissioning, or
            // installation results are updated on the node.
            $scope.$watch("node.summary_xml", updateMachineOutput);
            $scope.$watch("node.summary_yaml", updateMachineOutput);
            $scope.$watch("node.commissioning_results", updateMachineOutput);
            $scope.$watch("node.installation_results", updateMachineOutput);
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
            var MAC_ERROR_MARKER = "One or more MAC addresses is invalid.";
            var cluster = ClustersManager.getItemFromList(
                $scope.node.nodegroup.id);
            if(isDisconnectedClusterError(error)) {
                cluster.connected = false;
            } else {
                // Not a disconnection, so, cluster.connected needs to be true.
                cluster.connected = true;
                var mac_error_offset = error.indexOf(MAC_ERROR_MARKER);
                if (mac_error_offset !== -1) {
                    // A MAC Address is invalid.
                    var message = error.substring(mac_error_offset +
                                                  MAC_ERROR_MARKER.length + 2);
                    message = message.substring(0, message.length - 4);
                    $scope.nic.error = true;
                    $scope.nic.errormsg = message;
                } else {
                    // Unknown error that we currently don't track so log
                    // it to the console.
                    console.log(error);
                }
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
                updateName();
                updateSummary();
                $scope.nic.adding = false; // Hide the add nic form.
                $scope.nic.errormsg = null;
            }, function(error) {
                handleSaveError(error);
                updateName();
                updateSummary();
            });
        }

        // Called when the node has been loaded.
        function nodeLoaded(node) {
            $scope.node = node;
            $scope.loaded = true;

            updateTitle();
            updateSummary();
            updateMachineOutput();
            startWatching();
        }

        $scope.getPowerStateClass = function() {
            // This will get called very early and node can be empty.
            // In that case just return an empty string. It will be
            // called again to show the correct information.
            if(!angular.isObject($scope.node)) {
                return "";
            }

            if($scope.checkingPower) {
                return "checking";
            } else {
                return $scope.node.power_state;
            }
        };

        // Get the power state text to show.
        $scope.getPowerStateText = function() {
            // This will get called very early and node can be empty.
            // In that case just return an empty string. It will be
            // called again to show the correct information.
            if(!angular.isObject($scope.node)) {
                return "";
            }

            if($scope.checkingPower) {
                return "Checking power";
            } else if($scope.node.power_state === "unknown") {
                return "";
            } else {
                return "Power " + $scope.node.power_state;
            }
        };

        // Returns true when the "check now" button for updating the power
        // state should be shown.
        $scope.canCheckPowerState = function() {
            // This will get called very early and node can be empty.
            // In that case just return false. It will be
            // called again to show the correct information.
            if(!angular.isObject($scope.node)) {
                return false;
            }
            return (
                $scope.node.power_state !== "unknown" &&
                !$scope.checkingPower);
        };

        // Check the power state of the node.
        $scope.checkPowerState = function() {
            $scope.checkingPower = true;
            NodesManager.checkPowerState($scope.node).then(function() {
                $scope.checkingPower = false;
            });
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

        // Return true if there is an action error.
        $scope.isActionError = function() {
            return $scope.actionError !== null;
        };

        // Return True if in deploy action and the osinfo is missing.
        $scope.isDeployError = function() {
            // Never a deploy error when there is an action error.
            if($scope.isActionError()) {
                return false;
            }

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

        // Return True if unable to deploy because of missing ssh keys.
        $scope.isSSHKeyError = function() {
            // Never a deploy error when there is an action error.
            if($scope.isActionError()) {
                return false;
            }
            if(angular.isObject($scope.actionOption) &&
                $scope.actionOption.name === "deploy" &&
                UsersManager.getSSHKeyCount() === 0) {
                return true;
            }
            return false;
        };

        // Called when the actionOption has changed.
        $scope.actionOptionChanged = function() {
            // Clear the action error.
            $scope.actionError = null;
        };

        // Cancel the action.
        $scope.actionCancel = function() {
            $scope.actionOption = null;
            $scope.actionError = null;
        };

        // Perform the action.
        $scope.actionGo = function() {
            var extra = {};
            // Set deploy parameters if a deploy.
            if($scope.actionOption.name === "deploy" &&
                angular.isString($scope.osSelection.osystem) &&
                angular.isString($scope.osSelection.release)) {

                // Set extra. UI side the release is structured os/release, but
                // when it is sent over the websocket only the "release" is
                // sent.
                extra.osystem = $scope.osSelection.osystem;
                var release = $scope.osSelection.release;
                release = release.split("/");
                release = release[release.length-1];
                extra.distro_series = release;
            }

            NodesManager.performAction(
                $scope.node, $scope.actionOption.name, extra).then(function() {
                    // If the action was delete, then go back to listing.
                    if($scope.actionOption.name === "delete") {
                        $location.path("/nodes");
                    }
                    $scope.actionOption = null;
                    $scope.actionError = null;
                    $scope.osSelection.osystem = "";
                    $scope.osSelection.release = "";
                }, function(error) {
                    $scope.actionError = error;
                });
        };

        // Return true if the authenticated user is super user.
        $scope.isSuperUser = function() {
            var authUser = UsersManager.getAuthUser();
            if(!angular.isObject(authUser)) {
                return false;
            }
            return authUser.is_superuser;
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
            return (
                $scope.isSuperUser() &&
                !isErrorViewable("cluster_disconnected"));
        };

        // Called to edit the node name.
        $scope.editName = function() {
            if(!$scope.canEdit()) {
                return;
            }

            // Do nothing if already editing because we don't want to reset
            // the current value.
            if($scope.nameHeader.editing) {
                return;
            }
            $scope.nameHeader.editing = true;

            // Set the value to the hostname, as that is what can be changed
            // not the fqdn.
            $scope.nameHeader.value = $scope.node.hostname;
        };

        // Return true when the value in nameHeader is invalid.
        $scope.editNameInvalid = function() {
            // Not invalid unless editing.
            if(!$scope.nameHeader.editing) {
                return false;
            }

            // The value cannot be blank.
            var value = $scope.nameHeader.value;
            if(value.length === 0) {
                return true;
            }
            return !ValidationService.validateHostname(value);
        };

        // Called to cancel editing of the node name.
        $scope.cancelEditName = function() {
            $scope.nameHeader.editing = false;
            updateName();
        };

        // Called to save editing of node name.
        $scope.saveEditName = function() {
            // Does nothing if invalid.
            if($scope.editNameInvalid()) {
                return;
            }
            $scope.nameHeader.editing = false;

            // Copy the node and make the changes.
            var node = angular.copy($scope.node);
            node.hostname = $scope.nameHeader.value;

            // Update the node.
            updateNode(node);
        };

        // Called to enter edit mode in the summary section.
        $scope.editSummary = function() {
            if(!$scope.canEdit()) {
                return;
            }
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
            if(!$scope.canEdit()) {
                return;
            }
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

        // Called to add a new network interface.
        $scope.saveAddInterface = function() {
            // Copy the node and make the changes.
            var node = angular.copy($scope.node);
            node.extra_macs.push($scope.nic.mac);

            // Update the node.
            updateNode(node);
        };

        // Return the ip address text for the given nic.
        $scope.getIPAddressText = function(nic) {
            return nic.ip_addresses.map(function(ipAddress) {
                return ipAddress.ip_address + " (" + ipAddress.type + ")";
            }).join(', ');
        };

        // Return the network text for the given nic.
        $scope.getNetworkText = function(nic) {
            return nic.networks.map(function(network) {
                return network.name + " (" + network.cidr + ")";
            }).join(', ');
        };

        // Return true if the "load more" events button should be available.
        $scope.allowShowMoreEvents = function() {
            if(!angular.isObject($scope.node)) {
                return false;
            }
            return (
                $scope.node.events.length > 0 &&
                $scope.node.events.length > $scope.events.limit &&
                $scope.events.limit < 50);
        };

        // Show another 10 events.
        $scope.showMoreEvents = function() {
            $scope.events.limit += 10;
        };

        // Return the nice text for the given event.
        $scope.getEventText = function(event) {
            var text = event.type.description;
            if(angular.isString(event.description) &&
                event.description.length > 0) {
                text += " - " + event.description;
            }
            return text;
        };

        // Called when the machine output view has changed.
        $scope.machineOutputViewChanged = function() {
            if(angular.isObject($scope.machine_output.selectedView) &&
                $scope.machine_output.selectedView.name === "summary") {
                $scope.machine_output.showSummaryToggle = true;
            } else {
                $scope.machine_output.showSummaryToggle = false;
            }
        };

        // Return the commissioning summary output data.
        $scope.getSummaryData = function() {
            // Can be called by angular before the node is set in the scope,
            // in that case return blank string. It will be called once the
            // node is set to get the correct information.
            if(!angular.isObject($scope.node)) {
                return "";
            }
            // Prepend a newline before the summary output, because the code
            // tag requires that the content start on a newline.
            return "\n" +
                $scope.node["summary_" + $scope.machine_output.summaryType];
        };

        // Return the installation log data.
        $scope.getInstallationData = function() {
            // Can be called by angular before the node is set in the scope,
            // in that case return blank string. It will be called once the
            // node is set to get the correct information.
            if(!angular.isObject($scope.node)) {
                return "";
            }
            // It is possible for the node to have multiple installation
            // results, but it is unused. Only one installation result will
            // exists for a node. Grab the first one in the array.
            var results = $scope.node.installation_results;
            if(results.length === 0) {
                return "";
            } else {
                // Prepend a newline before the data, because the code
                // tag requires that the content start on a newline.
                return "\n" + results[0].data;
            }
        };

        // Load all the required managers.
        ManagerHelperService.loadManagers([
            NodesManager,
            ClustersManager,
            ZonesManager,
            GeneralManager,
            UsersManager
        ]).then(function() {
            // Possibly redirected from another controller that already had
            // this node set to active. Only call setActiveItem if not already
            // the activeItem.
            var activeNode = NodesManager.getActiveItem();
            if(angular.isObject(activeNode) &&
                activeNode.system_id === $routeParams.system_id) {
                nodeLoaded(activeNode);
            } else {
                NodesManager.setActiveItem(
                    $routeParams.system_id).then(function(node) {
                        nodeLoaded(node);
                    }, function(error) {
                        ErrorService.raiseError(error);
                    });
            }

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
