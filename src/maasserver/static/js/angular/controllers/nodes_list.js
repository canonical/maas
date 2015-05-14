/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Nodes List Controller
 */

angular.module('MAAS').controller('NodesListController', [
    '$scope', '$rootScope', '$routeParams', 'NodesManager', 'DevicesManager',
    'GeneralManager', 'ManagerHelperService', 'SearchService', 'ZonesManager',
    'UsersManager',
    function($scope, $rootScope, $routeParams, NodesManager, DevicesManager,
        GeneralManager, ManagerHelperService, SearchService, ZonesManager,
        UsersManager) {

        // Mapping of device.ip_assignment to viewable text.
        var DEVICE_IP_ASSIGNMENT = {
            external: "External",
            dynamic: "Dynamic",
            "static": "Static"
        };

        // Set title and page.
        $rootScope.title = "Nodes";
        $rootScope.page = "nodes";

        // Set initial values.
        $scope.nodes = NodesManager.getItems();
        $scope.zones = ZonesManager.getItems();
        $scope.devices = DevicesManager.getItems();
        $scope.currentpage = "nodes";
        $scope.osinfo = GeneralManager.getData("osinfo");
        $scope.loading = true;

        $scope.tabs = {};
        // Nodes tab.
        $scope.tabs.nodes = {};
        $scope.tabs.nodes.pagetitle = "Nodes";
        $scope.tabs.nodes.currentpage = "nodes";
        $scope.tabs.nodes.manager = NodesManager;
        $scope.tabs.nodes.search = "";
        $scope.tabs.nodes.searchValid = true;
        $scope.tabs.nodes.selectedItems = NodesManager.getSelectedItems();
        $scope.tabs.nodes.filtered_items = [];
        $scope.tabs.nodes.predicate = 'fqdn';
        $scope.tabs.nodes.allViewableChecked = false;
        $scope.tabs.nodes.metadata = NodesManager.getMetadata();
        $scope.tabs.nodes.filters = SearchService.emptyFilter;
        $scope.tabs.nodes.column = 'fqdn';
        $scope.tabs.nodes.actionOption = null;
        $scope.tabs.nodes.takeActionOptions = GeneralManager.getData(
            "node_actions");
        $scope.tabs.nodes.actionErrorCount = 0;
        $scope.tabs.nodes.actionProgress = {
            total: 0,
            completed: 0,
            errors: {}
        };
        $scope.tabs.nodes.osSelection = {
            osystem: null,
            release: null
        };
        $scope.tabs.nodes.zoneSelection = null;

        // Device tab.
        $scope.tabs.devices = {};
        $scope.tabs.devices.pagetitle = "Devices";
        $scope.tabs.devices.currentpage = "devices";
        $scope.tabs.devices.manager = DevicesManager;
        $scope.tabs.devices.search = "";
        $scope.tabs.devices.searchValid = true;
        $scope.tabs.devices.selectedItems = DevicesManager.getSelectedItems();
        $scope.tabs.devices.filtered_items = [];
        $scope.tabs.devices.predicate = 'fqdn';
        $scope.tabs.devices.allViewableChecked = false;
        $scope.tabs.devices.metadata = DevicesManager.getMetadata();
        $scope.tabs.devices.filters = SearchService.emptyFilter;
        $scope.tabs.devices.column = 'fqdn';
        $scope.tabs.devices.actionOption = null;
        $scope.tabs.devices.takeActionOptions = GeneralManager.getData(
            "device_actions");
        $scope.tabs.devices.actionErrorCount = 0;
        $scope.tabs.devices.actionProgress = {
            total: 0,
            completed: 0,
            errors: {}
        };
        $scope.tabs.devices.zoneSelection = null;

        // Options for add hardware dropdown.
        $scope.addHardwareOption = null;
        $scope.addHardwareOptions = [
            {
                name: "hardware",
                title: "Machine"
            },
            {
                name: "chassis",
                title: "Chassis"
            }
        ];

        // This will hold the AddHardwareController once it is initialized.
        // The controller will set this variable as it's always a child of
        // this scope.
        $scope.addHardwareScope = null;

        // This will hold the AddDeviceController once it is initialized.
        // The controller will set this variable as it's always a child of
        // this scope.
        $scope.addDeviceScope = null;

        // When the addHardwareScope is hidden it will emit this event. We
        // clear the call to action button, so it can be used again.
        $scope.$on("addHardwareHidden", function() {
            $scope.addHardwareOption = null;
        });

        // Return true if the tab is in viewing selected mode.
        function isViewingSelected(tab) {
            var search = $scope.tabs[tab].search.toLowerCase();
            return search === "in:(selected)" || search === "in:selected";
        }

        // Sets the search bar to only show selected.
        function enterViewSelected(tab) {
            $scope.tabs[tab].search = "in:(Selected)";
        }

        // Clear search bar from viewing selected.
        function leaveViewSelected(tab) {
            if(isViewingSelected(tab)) {
                $scope.tabs[tab].search = "";
                delete $scope.tabs[tab].filters["in"];
            }
        }

        // Called to update `allViewableChecked`.
        function updateAllViewableChecked(tab) {
            // Not checked when the filtered nodes are empty.
            if($scope.tabs[tab].filtered_items.length === 0) {
                $scope.tabs[tab].allViewableChecked = false;
                return;
            }

            // Loop through all filtered nodes and see if all are checked.
            var i;
            for(i = 0; i < $scope.tabs[tab].filtered_items.length; i++) {
                if(!$scope.tabs[tab].filtered_items[i].$selected) {
                    $scope.tabs[tab].allViewableChecked = false;
                    return;
                }
            }
            $scope.tabs[tab].allViewableChecked = true;
        }

        // Clear the action if required.
        function shouldClearAction(tab) {
            if($scope.tabs[tab].selectedItems.length === 0) {
                resetActionProgress(tab);
                leaveViewSelected(tab);
                $scope.tabs[tab].actionOption = null;
                $scope.tabs[tab].zoneSelection = null;
                if(tab === "nodes") {
                    $scope.tabs[tab].osSelection.osystem = "";
                    $scope.tabs[tab].osSelection.release = "";
                }
            }
            if($scope.tabs[tab].actionOption && !isViewingSelected(tab)) {
                $scope.tabs[tab].actionOption = null;
            }
        }

        // Update the number of selected items which have an error based on the
        // current selected action.
        function updateActionErrorCount(tab) {
            var i;
            $scope.tabs[tab].actionErrorCount = 0;
            for(i = 0; i < $scope.tabs[tab].selectedItems.length; i++) {
                var supported = $scope.supportsAction(
                    $scope.tabs[tab].selectedItems[i], tab);
                if(!supported) {
                    $scope.tabs[tab].actionErrorCount += 1;
                }
            }
        }

        // Reset actionProgress on tab to zero.
        function resetActionProgress(tab) {
            var progress = $scope.tabs[tab].actionProgress;
            progress.completed = progress.total = 0;
            progress.errors = {};
        }

        // Add error to action progress and group error messages by nodes.
        function addErrorToActionProgress(tab, error, node) {
            var progress = $scope.tabs[tab].actionProgress;
            progress.completed += 1;
            var nodes = progress.errors[error];
            if(angular.isUndefined(nodes)) {
                progress.errors[error] = [node];
            } else {
                nodes.push(node);
            }
        }

        // Toggles between the current tab.
        $scope.toggleTab = function(tab) {
            $rootScope.title = $scope.tabs[tab].pagetitle;
            $scope.currentpage = tab;
        };

        // Clear the search bar.
        $scope.clearSearch = function(tab) {
            $scope.tabs[tab].search = "";
            $scope.updateFilters(tab);
        };

        // Mark a node as selected or unselected.
        $scope.toggleChecked = function(node, tab) {
            if($scope.tabs[tab].manager.isSelected(node.system_id)) {
                $scope.tabs[tab].manager.unselectItem(node.system_id);
            } else {
                $scope.tabs[tab].manager.selectItem(node.system_id);
            }
            updateAllViewableChecked(tab);
            updateActionErrorCount(tab);
            shouldClearAction(tab);
        };

        // Select all viewable nodes or deselect all viewable nodes.
        $scope.toggleCheckAll = function(tab) {
            if($scope.tabs[tab].allViewableChecked) {
                angular.forEach(
                    $scope.tabs[tab].filtered_items, function(node) {
                        $scope.tabs[tab].manager.unselectItem(node.system_id);
                });
            } else {
                angular.forEach(
                    $scope.tabs[tab].filtered_items, function(node) {
                        $scope.tabs[tab].manager.selectItem(node.system_id);
                });
            }
            updateAllViewableChecked(tab);
            updateActionErrorCount(tab);
            shouldClearAction(tab);
        };

        // When the filtered nodes change update if all check buttons
        // should be checked or not.
        $scope.$watchCollection("tabs.nodes.filtered_items", function() {
            updateAllViewableChecked("nodes");
        });
        $scope.$watchCollection("tabs.devices.filtered_items", function() {
            updateAllViewableChecked("devices");
        });

        // Shows the current selection.
        $scope.showSelected = function(tab) {
            enterViewSelected(tab);
            $scope.updateFilters(tab);
        };

        // Adds or removes a filter to the search.
        $scope.toggleFilter = function(type, value, tab) {
            leaveViewSelected(tab);
            $scope.tabs[tab].filters = SearchService.toggleFilter(
                $scope.tabs[tab].filters, type, value);
            $scope.tabs[tab].search = SearchService.filtersToString(
                $scope.tabs[tab].filters);
            shouldClearAction(tab);
        };

        // Return True if the filter is active.
        $scope.isFilterActive = function(type, value, tab) {
            return SearchService.isFilterActive(
                $scope.tabs[tab].filters, type, value);
        };

        // Update the filters object when the search bar is updated.
        $scope.updateFilters = function(tab) {
            var filters = SearchService.getCurrentFilters(
                $scope.tabs[tab].search);
            if(filters === null) {
                $scope.tabs[tab].filters = SearchService.emptyFilter;
                $scope.tabs[tab].searchValid = false;
            } else {
                $scope.tabs[tab].filters = filters;
                $scope.tabs[tab].searchValid = true;
            }
            shouldClearAction(tab);
        };

        // Sorts the table by predicate.
        $scope.sortTable = function(predicate, tab) {
            $scope.tabs[tab].predicate = predicate;
            $scope.tabs[tab].reverse = !$scope.tabs[tab].reverse;
        };

        // Sets the viewable column or sorts.
        $scope.selectColumnOrSort = function(predicate, tab) {
            if($scope.tabs[tab].column !== predicate) {
                $scope.tabs[tab].column = predicate;
            } else {
                $scope.sortTable(predicate, tab);
            }
        };

        // Return True if the node supports the action.
        $scope.supportsAction = function(node, tab) {
            if(!$scope.tabs[tab].actionOption) {
                return true;
            }
            return node.actions.indexOf(
                $scope.tabs[tab].actionOption.name) >= 0;
        };

        // Called when the action option gets changed.
        $scope.actionOptionSelected = function(tab) {
            updateActionErrorCount(tab);
            enterViewSelected(tab);

            var actionOption = $scope.tabs[tab].actionOption;
            if(angular.isObject(actionOption) &&
                actionOption.name === "deploy") {
                GeneralManager.startPolling("osinfo");
            } else {
                GeneralManager.stopPolling("osinfo");
            }

            // Hide the add hardware/device section.
            if (tab === 'nodes') {
                if(angular.isObject($scope.addHardwareScope)) {
                    $scope.addHardwareScope.hide();
                }
            } else if(tab === 'devices') {
                if(angular.isObject($scope.addDeviceScope)) {
                    $scope.addDeviceScope.hide();
                }
            }
        };

        // Return True if there is an action error.
        $scope.isActionError = function(tab) {
            if(angular.isObject($scope.tabs[tab].actionOption) &&
                $scope.tabs[tab].actionOption.name === "deploy" &&
                $scope.tabs[tab].actionErrorCount === 0 &&
                ($scope.osinfo.osystems.length === 0 ||
                UsersManager.getSSHKeyCount() === 0)) {
                return true;
            }
            return $scope.tabs[tab].actionErrorCount !== 0;
        };

        // Return True if unable to deploy because of missing images.
        $scope.isDeployError = function(tab) {
            if($scope.tabs[tab].actionErrorCount !== 0) {
                return false;
            }
            if(angular.isObject($scope.tabs[tab].actionOption) &&
                $scope.tabs[tab].actionOption.name === "deploy" &&
                $scope.osinfo.osystems.length === 0) {
                return true;
            }
            return false;
        };

        // Return True if unable to deploy because of missing ssh keys.
        $scope.isSSHKeyError = function(tab) {
            if($scope.tabs[tab].actionErrorCount !== 0) {
                return false;
            }
            if(angular.isObject($scope.tabs[tab].actionOption) &&
                $scope.tabs[tab].actionOption.name === "deploy" &&
                UsersManager.getSSHKeyCount() === 0) {
                return true;
            }
            return false;
        };

        // Called when the current action is cancelled.
        $scope.actionCancel = function(tab) {
            resetActionProgress(tab);
            leaveViewSelected(tab);
            $scope.tabs[tab].actionOption = null;
            GeneralManager.stopPolling("osinfo");
        };

        // Perform the action on all nodes.
        $scope.actionGo = function(tab) {
            var extra = {};
            // Set deploy parameters if a deploy or set zone action.
            if($scope.tabs[tab].actionOption.name === "deploy" &&
                angular.isString($scope.tabs[tab].osSelection.osystem) &&
                angular.isString($scope.tabs[tab].osSelection.release)) {

                // Set extra. UI side the release is structured os/release, but
                // when it is sent over the websocket only the "release" is
                // sent.
                extra.osystem = $scope.tabs[tab].osSelection.osystem;
                var release = $scope.tabs[tab].osSelection.release;
                release = release.split("/");
                release = release[release.length-1];
                extra.distro_series = release;
            } else if($scope.tabs[tab].actionOption.name === "set-zone" &&
                angular.isNumber($scope.tabs[tab].zoneSelection.id)) {
                // Set the zone parameter
                extra.zone_id = $scope.tabs[tab].zoneSelection.id;
            }

            // Setup actionProgress.
            resetActionProgress(tab);
            $scope.tabs[tab].actionProgress.total =
                $scope.tabs[tab].selectedItems.length;

            // Perform the action on all selected items.
            angular.forEach($scope.tabs[tab].selectedItems, function(node) {
                $scope.tabs[tab].manager.performAction(
                    node, $scope.tabs[tab].actionOption.name,
                    extra).then(function() {
                        $scope.tabs[tab].actionProgress.completed += 1;
                        $scope.tabs[tab].manager.unselectItem(node.system_id);
                        shouldClearAction(tab);
                    }, function(error) {
                        addErrorToActionProgress(tab, error, node);
                    });
            });
        };

        // Returns true when actions are being performed.
        $scope.hasActionsInProgress = function(tab) {
            var progress = $scope.tabs[tab].actionProgress;
            return progress.total > 0 && progress.completed !== progress.total;
        };

        // Returns true if any of the actions have failed.
        $scope.hasActionsFailed = function(tab) {
            return Object.keys(
                $scope.tabs[tab].actionProgress.errors).length > 0;
        };

        // Called to when the addHardwareOption has changed.
        $scope.addHardwareOptionChanged = function() {
            if($scope.addHardwareOption) {
                $scope.addHardwareScope.show(
                    $scope.addHardwareOption.name);
            }
        };

        // Called when the add device button is pressed.
        $scope.addDevice = function() {
            $scope.addDeviceScope.show();
        };

        // Called when the cancel add device button is pressed.
        $scope.cancelAddDevice = function() {
            $scope.addDeviceScope.cancel();
        };

        // Get the display text for device ip assignment type.
        $scope.getDeviceIPAssignment = function(ipAssignment) {
            return DEVICE_IP_ASSIGNMENT[ipAssignment];
        };

        // Load NodesManager, DevicesManager, GeneralManager and ZonesManager.
        ManagerHelperService.loadManagers(
            [NodesManager, DevicesManager, GeneralManager, ZonesManager,
            UsersManager]).then(
            function() {
                $scope.loading = false;
            });

        // Stop polling when the scope is destroyed.
        $scope.$on("$destroy", function() {
            GeneralManager.stopPolling("osinfo");
        });

        // Switch to the specified tab, if specified.
        var tab = $routeParams.tab;
        if(angular.isString(tab)) {
            $scope.toggleTab(tab);
        } else {
            tab = 'nodes';
        }

        // Set the query if the present in $routeParams.
        var query = $routeParams.query;
        if(angular.isString(query)) {
            $scope.tabs[tab].search = query;
            $scope.updateFilters(tab);
        }
    }]);
