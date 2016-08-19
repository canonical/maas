/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Settings Controller
 */

angular.module('MAAS').controller('SettingsController', [
    '$scope', '$rootScope', '$routeParams', 'PackageRepositoriesManager',
    'DHCPSnippetsManager', 'MachinesManager', 'ControllersManager',
    'DevicesManager', 'SubnetsManager', 'GeneralManager',
    'ManagerHelperService',
    function($scope, $rootScope, $routeParams, PackageRepositoriesManager,
             DHCPSnippetsManager, MachinesManager, ControllersManager,
             DevicesManager, SubnetsManager, GeneralManager,
             ManagerHelperService) {

        // Set the title and page.
        $rootScope.title = "Loading...";
        $rootScope.page = "settings";

        // Initial values.
        $scope.loading = true;
        $scope.editing = false;

        $scope.isFieldEmpty = function(data, fieldName) {
            return (
                !angular.isString(data[fieldName]) ||
                data[fieldName] === "");
        };

        // Get the current options for the repository.
        $scope.getRepositoryOptions = function(repository) {
            var options = $scope.repositoryOptions[repository.id];
            if(!angular.isObject(options)) {
                options = {};
                $scope.repositoryOptions[repository.id] = options;
                return options;
            } else {
                return options;
            }
        };

        // Exit editing mode for all the repos, closing any dropdowns.
        $scope.closeAllRepos = function() {
            angular.forEach($scope.repositoryOptions, function(options, id) {
                if(angular.isObject(options)) {
                    options.editing = false;
                    options.saving = false;
                    options.removing = false;
                    options.error = null;
                    delete options.data;
                }
            });
            $scope.repositoryAddCancel();
            $scope.editing = false;
        };

        $scope.toggleCheckboxSelection = function(options, fieldname, key) {
            var items = options.data[fieldname];
            var idx = items.indexOf(key);
            if (idx > -1) {
                items.splice(idx, 1);
            } else {
                items.push(key);
            }
        };

        // Called when the enabled toggle is changed.
        $scope.repositoryEnabledToggle = function(repository) {
            var data = angular.copy(repository);
            var options = $scope.getRepositoryOptions(repository);
            options.saving = true;
            PackageRepositoriesManager.updateItem(data).then(function() {
                options.saving = false;
            }, function() {
                // Revert state change and clear toggling.
                repository.enabled = !repository.enabled;
                options.saving = false;
            });
        };

        // Called to enter remove mode for a repository.
        $scope.repositoryEnterRemove = function(repository) {
            $scope.closeAllRepos();
            var options = $scope.getRepositoryOptions(repository);
            options.removing = true;
        };

        // Called to exit remove mode for a repository.
        $scope.repositoryExitRemove = function(repository) {
            var options = $scope.getRepositoryOptions(repository);
            options.removing = false;
        };

        // Called to confirm the removal of a repository.
        $scope.repositoryConfirmRemove = function(repository) {
            PackageRepositoriesManager.deleteItem(repository).then(function() {
                $scope.repositoryExitRemove(repository);
            });
        };

        $scope.isPPA = function(data) {
            if(!angular.isObject(data)) {
                return false;
            }
            if(!angular.isString(data.url)) {
                return false;
            }
            return data.url.startsWith("ppa:") ||
                data.url.indexOf("ppa.launchpad.net") > -1;
        };

        $scope.isMirror = function(data) {
            if(!angular.isObject(data)) {
                return false;
            }
            if(!angular.isString(data.name)) {
                return false;
            }
            return data.name === "main_archive" ||
                data.name === "ports_archive";
        };

        // Called to enter edit mode for a repository.
        $scope.repositoryEnterEdit = function(repository) {
            $scope.closeAllRepos();
            $scope.editing = true;
            var options = $scope.getRepositoryOptions(repository);
            options.editing = true;
            options.saving = false;
            options.error = null;
            options.data = angular.copy(repository);
        };

        // Called to exit edit mode for a repository.
        $scope.repositoryExitEdit = function(repository, force) {
            // Force defaults to false.
            if(angular.isUndefined(force)) {
                force = false;
            }
            // Don't do anything if saving.
            var options = $scope.getRepositoryOptions(repository);
            if(options.saving && !force) {
                return;
            }
            options.editing = false;
            options.saving = false;
            options.error = null;
            delete options.data;
            $scope.editing = false;
        };

        $scope.cleanRepoTagFields = function(data) {
            // Turn tag-type fields into simple value array for saving.
            angular.forEach(
                    ['distributions','components'],
                    function(item) {
                var tagdata = data[item];
                data[item] = [];
                angular.forEach(tagdata, function(tag) {
                    data[item].push(tag.text);
                });
            });
        };

        // Return true if the options are valid.
        $scope.repoHasValidOptions = function(options) {
            if(!angular.isObject(options.data)) {
                return false;
            }
            if($scope.isFieldEmpty(options.data, "name") ||
                $scope.isFieldEmpty(options.data, "url")) {
                return false;
            }
            return true;
        };

        // Return true if the repository can be saved.
        $scope.repositoryCanBeSaved = function(repository) {
            var options = $scope.getRepositoryOptions(repository);
            return $scope.repoHasValidOptions(options);
        };

        // Called to save a modified repository.
        $scope.repositorySave = function(repository) {
            // Do nothing if cannot be saved.
            if(!$scope.repositoryCanBeSaved(repository)) {
                return;
            }
            var options = $scope.getRepositoryOptions(repository);
            var data = options.data;
            options.saving = true;
            $scope.cleanRepoTagFields(data);
            PackageRepositoriesManager.updateItem(data).then(function() {
                $scope.repositoryExitEdit(repository, true);
            }, function(error) {
                options.error =
                    ManagerHelperService.parseValidationError(error);
                options.saving = false;
            });
        };

        // Called when the active toggle is changed.
        $scope.repositoryToggle = function(repository) {
            var data = angular.copy(repository);
            var options = $scope.getRepositoryOptions(repository);
            options.toggling = true;
            PackageRepositoriesManager.updateItem(data).then(function() {
                options.toggling = false;
            }, function() {
                // Revert state change and clear toggling.
                repository.enabled = !repository.enabled;
                options.toggling = false;
            });
        };

        // Called to start adding a new repository.
        $scope.repositoryAdd = function(isPPA) {
            $scope.closeAllRepos();
            $scope.editing = true;
            var repo = {
                saving: false,
                data: {
                    name: "",
                    enabled: true,
                    url: "",
                    key: "",
                    arches: ["i386", "amd64"],
                    distributions: [],
                    components: []
                }
            };
            if (isPPA) {
                repo.data.url = "ppa:";
            }
            $scope.newRepository = repo;
        };

        // Called to cancel addind a new repository.
        $scope.repositoryAddCancel = function() {
            $scope.editing = false;
            $scope.newRepository = null;
        };

        // Called to check that the new repository is valid enough to be saved.
        $scope.repositoryAddCanBeSaved = function() {
            return $scope.repoHasValidOptions($scope.newRepository);
        };

        // Called to create the new repository.
        $scope.repositoryAddSave = function() {
            if(!$scope.repositoryAddCanBeSaved()) {
                return;
            }
            var data = $scope.newRepository.data;
            $scope.newRepository.saving = true;
            $scope.cleanRepoTagFields(data);
            PackageRepositoriesManager.create(data).then(function() {
                $scope.newRepository = null;
                $scope.editing = false;
            }, function(error) {
                $scope.newRepository.error =
                    ManagerHelperService.parseValidationError(error.error);
                $scope.newRepository.saving = false;
            });
        };

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

        // Exit editing mode for all snippets, closing any dropdowns.
        $scope.closeAllSnippets = function() {
            angular.forEach($scope.snippetOptions, function(options, id) {
                if(angular.isObject(options)) {
                    options.editing = false;
                    options.saving = false;
                    options.removing = false;
                    options.error = null;
                    delete options.data;
                }
            });
            $scope.snippetAddCancel();
            $scope.editing = false;
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
            $scope.closeAllSnippets();
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
            $scope.closeAllSnippets();
            $scope.editing = true;
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
            $scope.editing = false;
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
                options.error =
                    ManagerHelperService.parseValidationError(error);
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
            $scope.closeAllSnippets();
            $scope.editing = true;
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
            $scope.editing = false;
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
                $scope.newSnippet.error =
                    ManagerHelperService.parseValidationError(error.error);
                $scope.newSnippet.saving = false;
            });
            $scope.editing = false;
        };

        // Load the required managers.
        ManagerHelperService.loadManagers([
                PackageRepositoriesManager, DHCPSnippetsManager,
                MachinesManager, DevicesManager, ControllersManager,
                SubnetsManager, GeneralManager]).then(
            function() {

                // Setup page variables based on section.
                if($routeParams.section === "dhcp") {
                    $rootScope.title = "DHCP snippets";
                    $scope.currentpage = 'dhcp';
                    $scope.snippets = DHCPSnippetsManager.getItems();
                    $scope.subnets = SubnetsManager.getItems();
                    $scope.machines = MachinesManager.getItems();
                    $scope.devices = DevicesManager.getItems();
                    $scope.controllers = ControllersManager.getItems();
                    $scope.snippetOptions = {};
                    $scope.newSnippet = null;
                }
                else if($routeParams.section === "repositories") {
                    $rootScope.title = "Package Repositories";
                    $scope.currentpage = 'repositories';
                    $scope.known_architectures =
                        GeneralManager.getData("known_architectures");
                    $scope.pockets_to_disable =
                        GeneralManager.getData("pockets_to_disable");
                    $scope.repositories =
                        PackageRepositoriesManager.getItems();
                    $scope.repositoryOptions = {};
                    $scope.newRepository = null;
                    $scope.arches = {};
                }
                $scope.loading = false;
            });

    }]);
