/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Settings Controller
 */

angular.module('MAAS').controller('SettingsController', [
    '$scope', '$rootScope', '$routeParams',
    'DHCPSnippetsManager', 'MachinesManager', 'ControllersManager',
    'DevicesManager', 'SubnetsManager', 'ManagerHelperService',
    function($scope, $rootScope, $routeParams,
             DHCPSnippetsManager, MachinesManager, ControllersManager,
             DevicesManager, SubnetsManager, ManagerHelperService) {

        // Set the title and page.
        $rootScope.title = "Loading...";
        $rootScope.page = "settings";

        // Initial values.
        $scope.loading = true;
        $scope.snippets = DHCPSnippetsManager.getItems();
        $scope.subnets = SubnetsManager.getItems();
        $scope.machines = MachinesManager.getItems();
        $scope.devices = DevicesManager.getItems();
        $scope.controllers = ControllersManager.getItems();
        $scope.snippetOptions = {};
        $scope.newSnippet = null;

        // Return the node from either the machines, devices, or controllers
        // manager.
        function getNode(system_id) {
            var node = MachinesManager.getItemFromList(system_id);
            if(angular.isObject(node)) {
                return node;
            }
            node = DevicesManager.getItemFromList(system_id);
            if(angular.isObject(node)) {
                return node;
            }
            node = ControllersManager.getItemFromList(system_id);
            if(angular.isObject(node)) {
                return node;
            }
        }

        // Get the current options for the snippet.
        $scope.getSnippetOptions = function(snippet) {
            var options = $scope.snippetOptions[snippet.id];
            if(!angular.isObject(options)) {
                options = {};
                $scope.snippetOptions[snippet.id] = options;
                return options;
            } else {
                return options;
            }
        };

        // Return the name of the subnet.
        $scope.getSubnetName = function(subnet) {
            return SubnetsManager.getName(subnet);
        };

        // Return the text for the type of snippet.
        $scope.getSnippetTypeText = function(snippet) {
            if(angular.isString(snippet.node)) {
                return "Node";
            } else if(angular.isNumber(snippet.subnet)) {
                return "Subnet";
            } else {
                return "Global";
            }
        };

        // Return the object the snippet applies to.
        $scope.getSnippetAppliesToObject = function(snippet) {
            if(angular.isString(snippet.node)) {
                return getNode(snippet.node);
            } else if(angular.isNumber(snippet.subnet)) {
                return SubnetsManager.getItemFromList(snippet.subnet);
            }
        };

        // Return the applies to text that is disabled in none edit mode.
        $scope.getSnippetAppliesToText = function(snippet) {
            var obj = $scope.getSnippetAppliesToObject(snippet);
            if(angular.isString(snippet.node) && angular.isObject(obj)) {
                return obj.fqdn;
            } else if(angular.isNumber(snippet.subnet) &&
                angular.isObject(obj)) {
                return SubnetsManager.getName(obj);
            } else {
                return "";
            }
        };

        // Called to enter remove mode for a DHCP snippet.
        $scope.snippetEnterRemove = function(snippet) {
            $scope.snippetExitEdit(snippet);

            var options = $scope.getSnippetOptions(snippet);
            options.removing = true;
        };

        // Called to exit remove mode for a DHCP snippet.
        $scope.snippetExitRemove = function(snippet) {
            var options = $scope.getSnippetOptions(snippet);
            options.removing = false;
        };

        // Called to confirm the removal of a snippet.
        $scope.snippetConfirmRemove = function(snippet) {
            DHCPSnippetsManager.deleteItem(snippet).then(function() {
                $scope.snippetExitRemove(snippet);
            });
        };

        // Called to enter edit mode for a DHCP snippet.
        $scope.snippetEnterEdit = function(snippet) {
            $scope.snippetExitRemove(snippet);

            var options = $scope.getSnippetOptions(snippet);
            options.editing = true;
            options.saving = false;
            options.error = null;
            options.type = $scope.getSnippetTypeText(snippet);
            options.data = angular.copy(snippet);
            if(!angular.isString(options.data.node)) {
                options.data.node = "";
            }
            if(angular.isNumber(snippet.subnet)) {
                options.subnet = SubnetsManager.getItemFromList(
                    snippet.subnet);
            }
        };

        // Called to exit edit mode for a DHCP snippet.
        $scope.snippetExitEdit = function(snippet, force) {
            // Force defaults to false.
            if(angular.isUndefined(force)) {
                force = false;
            }

            // Don't do anything if saving.
            var options = $scope.getSnippetOptions(snippet);
            if(options.saving && !force) {
                return;
            }
            options.editing = false;
            options.saving = false;
            options.error = null;
            delete options.type;
            delete options.data;
        };

        // Return true if the snippet name is invalid.
        $scope.isFieldEmpty = function(snippet, fieldName) {
            return (
                !angular.isString(snippet[fieldName]) ||
                snippet[fieldName] === "");
        };

        // Return true if the options are valid.
        $scope.hasValidOptions = function(options) {
            if($scope.isFieldEmpty(options.data, "name") ||
                $scope.isFieldEmpty(options.data, "value")) {
                return false;
            } else if(options.type === "Node") {
                return !$scope.isFieldEmpty(options.data, "node");
            } else if(options.type === "Subnet") {
                return angular.isObject(options.subnet);
            } else {
                return true;
            }
        };

        // Return true if the snippet can be saved.
        $scope.snippetCanBeSaved = function(snippet) {
            var options = $scope.getSnippetOptions(snippet);
            return $scope.hasValidOptions(options);
        };

        // Called to save a modified snippet.
        $scope.snippetSave = function(snippet) {
            // Do nothing if cannot be saved.
            if(!$scope.snippetCanBeSaved(snippet)) {
                return;
            }

            var options = $scope.getSnippetOptions(snippet);
            var data = options.data;
            if(options.type === "Global") {
                delete data.node;
                delete data.subnet;
            } else if(options.type === "Subnet") {
                delete data.node;
                data.subnet = options.subnet.id;
            } else if(options.type === "Node") {
                delete data.subnet;
            }
            options.saving = true;
            DHCPSnippetsManager.updateItem(data).then(function() {
                $scope.snippetExitEdit(snippet, true);
            }, function(error) {
                options.error = error;
                options.saving = false;
            });
        };

        // Called when the active toggle is changed.
        $scope.snippetToggle = function(snippet) {
            var data = angular.copy(snippet);
            var options = $scope.getSnippetOptions(snippet);

            options.toggling = true;
            DHCPSnippetsManager.updateItem(data).then(function() {
                options.toggling = false;
            }, function() {
                // Revert state change and clear toggling.
                snippet.enabled = !snippet.enabled;
                options.toggling = false;
            });
        };

        // Called to start adding a new snippet.
        $scope.snippetAdd = function() {
            $scope.newSnippet = {
                saving: false,
                type: "Global",
                data: {
                    name: "",
                    enabled: true
                }
            };
        };

        // Called to cancel addind a new snippet.
        $scope.snippetAddCancel = function() {
            $scope.newSnippet = null;
        };

        // Called to check that the new snippet is valid enough to be saved.
        $scope.snippetAddCanBeSaved = function() {
            return $scope.hasValidOptions($scope.newSnippet);
        };

        // Called to create the new snippet.
        $scope.snippetAddSave = function() {
            if(!$scope.snippetAddCanBeSaved()) {
                return;
            }

            var data = $scope.newSnippet.data;
            if($scope.newSnippet.type === "Global") {
                data.node = data.subnet = null;
            } else if($scope.newSnippet.type === "Subnet") {
                data.node = null;
                data.subnet = $scope.newSnippet.subnet.id;
            } else if($scope.newSnippet.type === "Node") {
                data.subnet = null;
            }
            $scope.newSnippet.saving = true;
            DHCPSnippetsManager.create(data).then(function() {
                $scope.newSnippet = null;
            }, function(error) {
                $scope.newSnippet.error = error.error;
                $scope.newSnippet.saving = false;
            });
        };

        // Load the required managers.
        ManagerHelperService.loadManagers([
            DHCPSnippetsManager, MachinesManager, DevicesManager,
            ControllersManager, SubnetsManager]).then(
            function() {
                $scope.loading = false;
            });

        // Set title based on section.
        if($routeParams.section === "dhcp") {
            $rootScope.title = "DHCP snippets";
            $scope.loading = false;
        }
    }]);
