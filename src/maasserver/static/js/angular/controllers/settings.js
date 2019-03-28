/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Settings Controller
 */

function SettingsController($scope, $rootScope, $routeParams,
    PackageRepositoriesManager, DHCPSnippetsManager,
    MachinesManager, ControllersManager,
    DevicesManager, SubnetsManager, GeneralManager,
    ManagerHelperService) {

    // Set the title and page.
    $rootScope.title = "Loading...";
    $rootScope.page = "settings";

    // Initial values.
    $scope.loading = true;
    $scope.snippetsManager = DHCPSnippetsManager;
    $scope.snippets = DHCPSnippetsManager.getItems();
    $scope.subnets = SubnetsManager.getItems();
    $scope.machines = MachinesManager.getItems();
    $scope.devices = DevicesManager.getItems();
    $scope.controllers = ControllersManager.getItems();
    $scope.known_architectures =
        GeneralManager.getData("known_architectures");
    $scope.pockets_to_disable =
        GeneralManager.getData("pockets_to_disable");
    $scope.components_to_disable =
        GeneralManager.getData("components_to_disable");
    $scope.packageRepositoriesManager = PackageRepositoriesManager;
    $scope.repositories =
        PackageRepositoriesManager.getItems();
    $scope.newSnippet = null;
    $scope.editSnippet = null;
    $scope.deleteSnippet = null;
    $scope.snippetTypes = ["Global", "Subnet", "Node"];
    $scope.newRepository = null;
    $scope.editRepository = null;
    $scope.deleteRepository = null;

    // Called when the enabled toggle is changed.
    $scope.repositoryEnabledToggle = function(repository) {
        PackageRepositoriesManager.updateItem(repository);
    };

    // Called to enter remove mode for a repository.
    $scope.repositoryEnterRemove = function(repository) {
        $scope.newRepository = null;
        $scope.editRepository = null;
        $scope.deleteRepository = repository;
    };

    // Called to exit remove mode for a repository.
    $scope.repositoryExitRemove = function() {
        $scope.deleteRepository = null;
    };

    // Called to confirm the removal of a repository.
    $scope.repositoryConfirmRemove = function() {
        PackageRepositoriesManager.deleteItem(
            $scope.deleteRepository).then(function() {
                $scope.repositoryExitRemove();
            });
    };

    // Return true if the repository is a PPA.
    $scope.isPPA = function(data) {
        if (!angular.isObject(data)) {
            return false;
        }
        if (!angular.isString(data.url)) {
            return false;
        }
        return data.url.indexOf("ppa:") === 0 ||
            data.url.indexOf("ppa.launchpad.net") > -1;
    };

    // Return true if the repository is a mirror.
    $scope.isMirror = function(data) {
        if (!angular.isObject(data)) {
            return false;
        }
        if (!angular.isString(data.name)) {
            return false;
        }
        return data.name === "main_archive" ||
            data.name === "ports_archive";
    };

    // Called to enter edit mode for a repository.
    $scope.repositoryEnterEdit = function(repository) {
        $scope.newRepository = null;
        $scope.deleteRepository = null;
        $scope.editRepository = repository;
    };

    // Called to exit edit mode for a repository.
    $scope.repositoryExitEdit = function() {
        $scope.editRepository = null;
    };

    // Called to start adding a new repository.
    $scope.repositoryAdd = function(isPPA) {
        var repo = {
            name: "",
            enabled: true,
            url: "",
            key: "",
            arches: ["i386", "amd64"],
            distributions: [],
            components: []
        };
        if (isPPA) {
            repo.url = "ppa:";
        }
        $scope.newRepository = repo;
    };

    // Called to cancel addind a new repository.
    $scope.repositoryAddCancel = function() {
        $scope.newRepository = null;
    };

    // Return the node from either the machines, devices, or controllers
    // manager.
    function getNode(system_id) {
        var node = MachinesManager.getItemFromList(system_id);
        if (angular.isObject(node)) {
            return node;
        }
        node = DevicesManager.getItemFromList(system_id);
        if (angular.isObject(node)) {
            return node;
        }
        node = ControllersManager.getItemFromList(system_id);
        if (angular.isObject(node)) {
            return node;
        }
    }

    // Return the name of the subnet.
    $scope.getSubnetName = function(subnet) {
        return SubnetsManager.getName(subnet);
    };

    // Return the text for the type of snippet.
    $scope.getSnippetTypeText = function(snippet) {
        if (angular.isString(snippet.node)) {
            return "Node";
        } else if (angular.isNumber(snippet.subnet)) {
            return "Subnet";
        } else {
            return "Global";
        }
    };

    // Return the object the snippet applies to.
    $scope.getSnippetAppliesToObject = function(snippet) {
        if (angular.isString(snippet.node)) {
            return getNode(snippet.node);
        } else if (angular.isNumber(snippet.subnet)) {
            return SubnetsManager.getItemFromList(snippet.subnet);
        }
    };

    // Return the applies to text that is disabled in none edit mode.
    $scope.getSnippetAppliesToText = function(snippet) {
        var obj = $scope.getSnippetAppliesToObject(snippet);
        if (angular.isString(snippet.node) && angular.isObject(obj)) {
            return obj.fqdn;
        } else if (angular.isNumber(snippet.subnet) &&
            angular.isObject(obj)) {
            return SubnetsManager.getName(obj);
        } else {
            return "";
        }
    };

    // Called to enter remove mode for a DHCP snippet.
    $scope.snippetEnterRemove = function(snippet) {
        $scope.newSnippet = null;
        $scope.editSnippet = null;
        $scope.deleteSnippet = snippet;
    };

    // Called to exit remove mode for a DHCP snippet.
    $scope.snippetExitRemove = function() {
        $scope.deleteSnippet = null;
    };

    // Called to confirm the removal of a snippet.
    $scope.snippetConfirmRemove = function() {
        DHCPSnippetsManager.deleteItem($scope.deleteSnippet).then(
            function() {
                $scope.snippetExitRemove();
            });
    };

    // Called to enter edit mode for a DHCP snippet.
    $scope.snippetEnterEdit = function(snippet) {
        $scope.newSnippet = null;
        $scope.deleteSnippet = null;
        $scope.editSnippet = snippet;
        $scope.editSnippet.type = $scope.getSnippetTypeText(snippet);
    };

    // Called to exit edit mode for a DHCP snippet.
    $scope.snippetExitEdit = function() {
        $scope.editSnippet = null;
    };

    // Called when the active toggle is changed.
    $scope.snippetToggle = function(snippet) {
        DHCPSnippetsManager.updateItem(snippet).then(null,
            function(error) {
                // Revert state change and clear toggling.
                snippet.enabled = !snippet.enabled;
                console.log(error);
            });
    };

    // Called to start adding a new snippet.
    $scope.snippetAdd = function() {
        $scope.editSnippet = null;
        $scope.deleteSnippet = null;
        $scope.newSnippet = {
            name: "",
            type: "Global",
            enabled: true
        };
    };

    // Called to cancel addind a new snippet.
    $scope.snippetAddCancel = function() {
        $scope.newSnippet = null;
    };

    // Setup page variables based on section.
    if ($routeParams.section === "dhcp") {
        $rootScope.title = "DHCP snippets";
        $scope.currentpage = 'dhcp';
    }
    else if ($routeParams.section === "repositories") {
        $rootScope.title = "Package repositories";
        $scope.currentpage = 'repositories';
    }

    // Load the required managers.
    ManagerHelperService.loadManagers($scope, [
        PackageRepositoriesManager, DHCPSnippetsManager,
        MachinesManager, DevicesManager, ControllersManager,
        SubnetsManager, GeneralManager]).then(
            function() {
                $scope.loading = false;
            });
};

angular.module('MAAS').controller(
    'SettingsController', SettingsController);
