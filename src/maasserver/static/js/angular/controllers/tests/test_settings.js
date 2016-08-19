/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for SettingsController.
 */

describe("SettingsController", function() {

    // Load the MAAS module.
    beforeEach(module("MAAS"));

    // Grab the needed angular pieces.
    var $controller, $rootScope, $scope, $q;
    beforeEach(inject(function($injector) {
        $controller = $injector.get("$controller");
        $rootScope = $injector.get("$rootScope");
        $q = $injector.get("$q");
        $scope = $rootScope.$new();
    }));

    // Load the required dependencies for the SettingsController and
    // mock the websocket connection.
    var DHCPSnippetsManager, SubnetsManager, MachinesManager, GeneralManager;
    var DevicesManager, ControllersManager, ManagerHelperService;
    var PackageRepositoriesManager, RegionConnection, webSocket;
    beforeEach(inject(function($injector) {
        PackageRepositoriesManager = $injector.get(
            "PackageRepositoriesManager");
        DHCPSnippetsManager = $injector.get("DHCPSnippetsManager");
        SubnetsManager = $injector.get("SubnetsManager");
        MachinesManager = $injector.get("MachinesManager");
        DevicesManager = $injector.get("DevicesManager");
        ControllersManager = $injector.get("ControllersManager");
        ManagerHelperService = $injector.get("ManagerHelperService");
        RegionConnection = $injector.get("RegionConnection");
        GeneralManager = $injector.get("GeneralManager");

        // Mock buildSocket so an actual connection is not made.
        webSocket = new MockWebSocket();
        spyOn(RegionConnection, "buildSocket").and.returnValue(webSocket);
    }));

    // Setup the routeParams.
    var $routeParams;
    beforeEach(function() {
        $routeParams = {};
    });

    // Make a fake snippet.
    var _nextId = 0;
    function makeSnippet() {
        return {
            id: _nextId++,
            name: makeName("snippet"),
            enabled: true,
            value: makeName("value")
        };
    }

    // Make a fake repository.
    var _nextRepoId = 0;
    function makeRepo() {
        return {
            id: _nextRepoId++,
            name: makeName("repo"),
            enabled: true,
            url: makeName("url"),
            key: makeName("key"),
            arches: [makeName("arch"), makeName("arch")],
            distributions: [makeName("dist"), makeName("dist")],
            components: [makeName("comp"), makeName("comp")]
        };
    }

    // Makes the SettingsController
    function makeController(loadManagersDefer) {
        var loadManagers = spyOn(ManagerHelperService, "loadManagers");
        if(angular.isObject(loadManagersDefer)) {
            loadManagers.and.returnValue(loadManagersDefer.promise);
        } else {
            loadManagers.and.returnValue($q.defer().promise);
        }

        return $controller("SettingsController", {
            $scope: $scope,
            $rootScope: $rootScope,
            $routeParams: $routeParams,
            PackageRepositoriesManager: PackageRepositoriesManager,
            DHCPSnippetsManager: DHCPSnippetsManager,
            SubnetsManager: SubnetsManager,
            MachinesManager: MachinesManager,
            DevicesManager: DevicesManager,
            ControllersManager: ControllersManager,
            GeneralManager: GeneralManager,
            ManagerHelperService: ManagerHelperService
        });
    }

    it("sets title to loading and page to settings", function() {
        var controller = makeController();
        expect($rootScope.title).toBe("Loading...");
        expect($rootScope.page).toBe("settings");
    });

    it("sets the values for 'dhcp' section", function() {
        $routeParams.section = "dhcp";
        var defer = $q.defer();
        var controller = makeController(defer);
        defer.resolve();
        $scope.$digest();
        expect($scope.loading).toBe(false);
        expect($scope.title).toBe("DHCP snippets");
        expect($scope.snippets).toBe(DHCPSnippetsManager.getItems());
        expect($scope.subnets).toBe(SubnetsManager.getItems());
        expect($scope.machines).toBe(MachinesManager.getItems());
        expect($scope.devices).toBe(DevicesManager.getItems());
        expect($scope.controllers).toBe(ControllersManager.getItems());
        expect($scope.snippetOptions).toEqual({});
        expect($scope.newSnippet).toBeNull();
    });

    it("sets the values for 'repositories' section", function() {
        $routeParams.section = "repositories";
        var defer = $q.defer();
        var controller = makeController(defer);
        defer.resolve();
        $scope.$digest();
        expect($scope.loading).toBe(false);
        expect($scope.title).toBe("Package Repositories");
        expect($scope.known_architectures).toEqual([]);
        expect($scope.pockets_to_disable).toEqual([]);
    });

    it("initialized default values", function() {
        var controller = makeController();
        expect($scope.loading).toBe(true);
    });

    it("calls loadManagers with all needed managers", function() {
        var controller = makeController();
        expect(ManagerHelperService.loadManagers).toHaveBeenCalledWith([
            PackageRepositoriesManager, DHCPSnippetsManager, MachinesManager,
            DevicesManager, ControllersManager, SubnetsManager,
            GeneralManager]);
    });

    it("sets loading to false", function() {
        var defer = $q.defer();
        var controller = makeController(defer);
        defer.resolve();
        $scope.$digest();
        expect($scope.loading).toBe(false);
    });

    describe("getSnippetOptions", function() {

        it("returns always same object", function() {
            $routeParams.section = "dhcp";
            var defer = $q.defer();
            var controller = makeController(defer);
            defer.resolve();
            $scope.$digest();
            var snippet = makeSnippet();
            var options = $scope.getSnippetOptions(snippet);
            expect(options).toEqual({});
            expect($scope.getSnippetOptions(snippet)).toBe(options);
        });
    });

    describe("getSubnetName", function() {

        it("calls SubnetsManager.getName", function() {
            $routeParams.section = "dhcp";
            var controller = makeController();
            var subnet = {};
            var subnetsName = {};
            spyOn(SubnetsManager, "getName").and.returnValue(subnetsName);
            expect($scope.getSubnetName(subnet)).toBe(subnetsName);
            expect(SubnetsManager.getName).toHaveBeenCalledWith(subnet);
        });
    });

    describe("getSnippetTypeText", function() {

        it("returns 'Node'", function() {
            $routeParams.section = "dhcp";
            var controller = makeController();
            var snippet = makeSnippet();
            snippet.node = makeName("system_id");
            expect($scope.getSnippetTypeText(snippet)).toBe("Node");
        });

        it("returns 'Subnet'", function() {
            $routeParams.section = "dhcp";
            var controller = makeController();
            var snippet = makeSnippet();
            snippet.subnet = makeInteger();
            expect($scope.getSnippetTypeText(snippet)).toBe("Subnet");
        });

        it("returns 'Global'", function() {
            $routeParams.section = "dhcp";
            var controller = makeController();
            var snippet = makeSnippet();
            expect($scope.getSnippetTypeText(snippet)).toBe("Global");
        });
    });

    describe("getSnippetAppliesToObject", function() {

        it("returns node from MachinesManager", function() {
            $routeParams.section = "dhcp";
            var controller = makeController();
            var system_id = makeName("system_id");
            var node = {
                system_id: system_id
            };
            var snippet = makeSnippet();
            snippet.node = system_id;
            MachinesManager._items = [node];
            expect($scope.getSnippetAppliesToObject(snippet)).toBe(node);
        });

        it("returns device from DevicesManager", function() {
            $routeParams.section = "dhcp";
            var controller = makeController();
            var system_id = makeName("system_id");
            var device = {
                system_id: system_id
            };
            var snippet = makeSnippet();
            snippet.node = system_id;
            DevicesManager._items = [device];
            expect($scope.getSnippetAppliesToObject(snippet)).toBe(device);
        });

        it("returns controller from ControllersManager", function() {
            $routeParams.section = "dhcp";
            var c = makeController();
            var system_id = makeName("system_id");
            var controller = {
                system_id: system_id
            };
            var snippet = makeSnippet();
            snippet.node = system_id;
            ControllersManager._items = [controller];
            expect($scope.getSnippetAppliesToObject(snippet)).toBe(controller);
        });

        it("returns subnet from SubnetsManager", function() {
            $routeParams.section = "dhcp";
            var controller = makeController();
            var subnet_id = makeInteger(0, 100);
            var subnet = {
                id: subnet_id
            };
            var snippet = makeSnippet();
            snippet.subnet = subnet_id;
            SubnetsManager._items = [subnet];
            expect($scope.getSnippetAppliesToObject(snippet)).toBe(subnet);
        });
    });

    describe("getSnippetAppliesToText", function() {

        it("returns node.fqdn from MachinesManager", function() {
            $routeParams.section = "dhcp";
            var controller = makeController();
            var system_id = makeName("system_id");
            var fqdn = makeName("fqdn");
            var node = {
                system_id: system_id,
                fqdn: fqdn
            };
            var snippet = makeSnippet();
            snippet.node = system_id;
            MachinesManager._items = [node];
            expect($scope.getSnippetAppliesToText(snippet)).toBe(fqdn);
        });

        it("returns device.fqdn from DevicesManager", function() {
            $routeParams.section = "dhcp";
            var controller = makeController();
            var system_id = makeName("system_id");
            var fqdn = makeName("fqdn");
            var device = {
                system_id: system_id,
                fqdn: fqdn
            };
            var snippet = makeSnippet();
            snippet.node = system_id;
            DevicesManager._items = [device];
            expect($scope.getSnippetAppliesToText(snippet)).toBe(fqdn);
        });

        it("returns controller.fqdn from ControllersManager", function() {
            $routeParams.section = "dhcp";
            var c = makeController();
            var system_id = makeName("system_id");
            var fqdn = makeName("fqdn");
            var controller = {
                system_id: system_id,
                fqdn: fqdn
            };
            var snippet = makeSnippet();
            snippet.node = system_id;
            ControllersManager._items = [controller];
            expect($scope.getSnippetAppliesToText(snippet)).toBe(fqdn);
        });

        it("returns subnet from SubnetsManager", function() {
            $routeParams.section = "dhcp";
            var controller = makeController();
            var subnet_id = makeInteger(0, 100);
            var cidr = makeName("cidr");
            var subnet = {
                id: subnet_id,
                cidr: cidr
            };
            var snippet = makeSnippet();
            snippet.subnet = subnet_id;
            SubnetsManager._items = [subnet];
            expect($scope.getSnippetAppliesToText(snippet)).toBe(cidr);
        });
    });

    describe("snippetEnterRemove", function() {

        it("calls closeAllSnippets", function() {
            $routeParams.section = "dhcp";
            var defer = $q.defer();
            var controller = makeController(defer);
            defer.resolve();
            $scope.$digest();
            var snippet = makeSnippet();
            spyOn($scope, "closeAllSnippets");
            $scope.snippetEnterRemove(snippet);
            expect($scope.closeAllSnippets).toHaveBeenCalled();
        });

        it("sets removing to true", function() {
            $routeParams.section = "dhcp";
            var defer = $q.defer();
            var controller = makeController(defer);
            defer.resolve();
            $scope.$digest();
            var snippet = makeSnippet();
            $scope.snippetEnterRemove(snippet);
            expect($scope.getSnippetOptions(snippet).removing).toBe(true);
        });
    });

    describe("snippetExitRemove", function() {

        it("sets removing to false", function() {
            $routeParams.section = "dhcp";
            var defer = $q.defer();
            var controller = makeController(defer);
            defer.resolve();
            $scope.$digest();
            var snippet = makeSnippet();
            $scope.snippetExitRemove(snippet);
            expect($scope.getSnippetOptions(snippet).removing).toBe(false);
        });
    });

    describe("snippetExitRemove", function() {

        it("sets removing to false", function() {
            $routeParams.section = "dhcp";
            var defer = $q.defer();
            var controller = makeController(defer);
            defer.resolve();
            $scope.$digest();
            var snippet = makeSnippet();
            $scope.snippetExitRemove(snippet);
            expect($scope.getSnippetOptions(snippet).removing).toBe(false);
        });
    });

    describe("snippetConfirmRemove", function() {

        it("calls deleteItem and then snippetExitRemove", function() {
            $routeParams.section = "dhcp";
            var controller = makeController();
            var snippet = makeSnippet();
            var defer = $q.defer();
            spyOn(DHCPSnippetsManager, "deleteItem").and.returnValue(
                defer.promise);
            spyOn($scope, "snippetExitRemove");
            $scope.snippetConfirmRemove(snippet);
            expect(DHCPSnippetsManager.deleteItem).toHaveBeenCalledWith(
                snippet);
            defer.resolve();
            $scope.$digest();
            expect($scope.snippetExitRemove).toHaveBeenCalledWith(snippet);
        });
    });

    describe("snippetEnterEdit", function() {

        it("calls closeAllSnippets", function() {
            $routeParams.section = "dhcp";
            var defer = $q.defer();
            var controller = makeController(defer);
            defer.resolve();
            $scope.$digest();
            var snippet = makeSnippet();
            spyOn($scope, "closeAllSnippets");
            $scope.snippetEnterEdit(snippet);
            expect($scope.closeAllSnippets).toHaveBeenCalled();
        });

        it("sets options", function() {
            $routeParams.section = "dhcp";
            var defer = $q.defer();
            var controller = makeController(defer);
            defer.resolve();
            $scope.$digest();
            var snippet = makeSnippet();
            snippet.node = "";
            var subnet = {
                id: makeInteger(0, 100)
            };
            SubnetsManager._items = [subnet];
            snippet.subnet = subnet.id;
            $scope.snippetEnterEdit(snippet);

            var options = $scope.getSnippetOptions(snippet);
            expect(options.editing).toBe(true);
            expect(options.saving).toBe(false);
            expect(options.error).toBeNull();
            expect(options.type).toBe($scope.getSnippetTypeText(snippet));
            expect(options.data).toEqual(snippet);
            expect(options.data).not.toBe(snippet);
            expect(options.subnet).toBe(subnet);
        });
    });

    describe("snippetExitEdit", function() {

        it("does nothing when saving without force", function() {
            $routeParams.section = "dhcp";
            var defer = $q.defer();
            var controller = makeController(defer);
            defer.resolve();
            $scope.$digest();
            var snippet = makeSnippet();
            var options = $scope.getSnippetOptions(snippet);
            options.saving = true;
            options.editing = true;

            $scope.snippetExitEdit(snippet);
            expect(options.editing).toBe(true);
        });

        it("clears editing with saving and force", function() {
            $routeParams.section = "dhcp";
            var defer = $q.defer();
            var controller = makeController(defer);
            defer.resolve();
            $scope.$digest();
            var snippet = makeSnippet();
            var options = $scope.getSnippetOptions(snippet);
            options.saving = true;
            options.editing = true;

            $scope.snippetExitEdit(snippet, true);
            expect(options.editing).toBe(false);
        });

        it("clears all required fields", function() {
            $routeParams.section = "dhcp";
            var defer = $q.defer();
            var controller = makeController(defer);
            defer.resolve();
            $scope.$digest();
            var snippet = makeSnippet();
            var options = $scope.getSnippetOptions(snippet);
            options.saving = true;
            options.editing = true;
            options.error = {};
            options.type = {};
            options.data = {};

            $scope.snippetExitEdit(snippet, true);
            expect(options.saving).toBe(false);
            expect(options.editing).toBe(false);
            expect(options.error).toBeNull();
            expect(options.type).toBeUndefined();
            expect(options.data).toBeUndefined();
        });
    });

    describe("isFieldEmpty", function() {

        it("true when not a string", function() {
            $routeParams.section = "dhcp";
            var controller = makeController();
            var snippet = makeSnippet();
            var fieldName = makeName("field");
            expect($scope.isFieldEmpty(snippet, fieldName)).toBe(true);
        });

        it("true when empty string", function() {
            $routeParams.section = "dhcp";
            var controller = makeController();
            var snippet = makeSnippet();
            var fieldName = makeName("field");
            snippet[fieldName] = "";
            expect($scope.isFieldEmpty(snippet, fieldName)).toBe(true);
        });

        it("false when empty string", function() {
            $routeParams.section = "dhcp";
            var controller = makeController();
            var snippet = makeSnippet();
            var fieldName = makeName("field");
            snippet[fieldName] = makeName("value");
            expect($scope.isFieldEmpty(snippet, fieldName)).toBe(false);
        });
    });

    describe("hasValidOptions", function() {

        it("false when no name", function() {
            $routeParams.section = "dhcp";
            var defer = $q.defer();
            var controller = makeController(defer);
            defer.resolve();
            $scope.$digest();
            var snippet = makeSnippet();
            var options = $scope.getSnippetOptions(snippet);
            options.data = {
                name: ""
            };
            expect($scope.hasValidOptions(options)).toBe(false);
        });

        it("false when no value", function() {
            $routeParams.section = "dhcp";
            var defer = $q.defer();
            var controller = makeController(defer);
            defer.resolve();
            $scope.$digest();
            var snippet = makeSnippet();
            var options = $scope.getSnippetOptions(snippet);
            options.data = {
                name: makeName("name"),
                value: ""
            };
            expect($scope.hasValidOptions(options)).toBe(false);
        });

        it("false when no node set", function() {
            $routeParams.section = "dhcp";
            var defer = $q.defer();
            var controller = makeController(defer);
            defer.resolve();
            $scope.$digest();
            var snippet = makeSnippet();
            var options = $scope.getSnippetOptions(snippet);
            options.type = "Node";
            options.data = {
                name: makeName("name"),
                value: makeName("value")
            };
            expect($scope.hasValidOptions(options)).toBe(false);
        });

        it("false when no subnet set", function() {
            $routeParams.section = "dhcp";
            var defer = $q.defer();
            var controller = makeController(defer);
            defer.resolve();
            $scope.$digest();
            var snippet = makeSnippet();
            var options = $scope.getSnippetOptions(snippet);
            options.type = "Subnet";
            options.data = {
                name: makeName("name"),
                value: makeName("value")
            };
            expect($scope.hasValidOptions(options)).toBe(false);
        });

        it("true when node is set", function() {
            $routeParams.section = "dhcp";
            var defer = $q.defer();
            var controller = makeController(defer);
            defer.resolve();
            $scope.$digest();
            var snippet = makeSnippet();
            var options = $scope.getSnippetOptions(snippet);
            options.type = "Node";
            options.data = {
                name: makeName("name"),
                value: makeName("value"),
                node: makeName("system_id")
            };
            expect($scope.hasValidOptions(options)).toBe(true);
        });

        it("true when subnet is set", function() {
            $routeParams.section = "dhcp";
            var defer = $q.defer();
            var controller = makeController(defer);
            defer.resolve();
            $scope.$digest();
            var snippet = makeSnippet();
            var options = $scope.getSnippetOptions(snippet);
            options.type = "Subnet";
            options.subnet = {
                id: makeInteger(0, 100)
            };
            options.data = {
                name: makeName("name"),
                value: makeName("value")
            };
            expect($scope.hasValidOptions(options)).toBe(true);
        });
    });

    describe("snippetCanBeSaved", function() {

        it("calls hasValidOptions with options", function() {
            $routeParams.section = "dhcp";
            var defer = $q.defer();
            var controller = makeController(defer);
            defer.resolve();
            $scope.$digest();
            var snippet = makeSnippet();
            var options = $scope.getSnippetOptions(snippet);
            var returnValue = {};
            spyOn($scope, "hasValidOptions").and.returnValue(returnValue);
            expect($scope.snippetCanBeSaved(snippet)).toBe(returnValue);
            expect($scope.hasValidOptions).toHaveBeenCalledWith(options);
        });
    });

    describe("snippetSave", function() {

        it("does nothing if snippet cannot be saved", function() {
            $routeParams.section = "dhcp";
            var defer = $q.defer();
            var controller = makeController(defer);
            defer.resolve();
            $scope.$digest();
            var snippet = makeSnippet();
            var options = $scope.getSnippetOptions(snippet);
            options.data = {};
            spyOn(DHCPSnippetsManager, "updateItem").and.returnValue(
                $q.defer().promise);
            $scope.snippetSave(snippet);
        });

        it("calls updateItem for global", function() {
            $routeParams.section = "dhcp";
            var defer = $q.defer();
            var controller = makeController(defer);
            defer.resolve();
            $scope.$digest();
            var snippet = makeSnippet();
            var options = $scope.getSnippetOptions(snippet);
            options.type = "Global";
            options.data = {
                name: makeName("name"),
                value: makeName("value"),
                enabled: true
            };
            spyOn(DHCPSnippetsManager, "updateItem").and.returnValue(
                $q.defer().promise);
            $scope.snippetSave(snippet);
            expect(DHCPSnippetsManager.updateItem).toHaveBeenCalledWith({
                name: options.data.name,
                value: options.data.value,
                enabled: true
            });
        });

        it("calls updateItem for node", function() {
            $routeParams.section = "dhcp";
            var defer = $q.defer();
            var controller = makeController(defer);
            defer.resolve();
            $scope.$digest();
            var snippet = makeSnippet();
            var options = $scope.getSnippetOptions(snippet);
            options.type = "Node";
            options.data = {
                name: makeName("name"),
                value: makeName("value"),
                enabled: true,
                node: makeName("system_id")
            };
            spyOn(DHCPSnippetsManager, "updateItem").and.returnValue(
                $q.defer().promise);
            $scope.snippetSave(snippet);
            expect(DHCPSnippetsManager.updateItem).toHaveBeenCalledWith({
                name: options.data.name,
                value: options.data.value,
                enabled: true,
                node: options.data.node
            });
        });

        it("calls updateItem for subnet", function() {
            $routeParams.section = "dhcp";
            var defer = $q.defer();
            var controller = makeController(defer);
            defer.resolve();
            $scope.$digest();
            var snippet = makeSnippet();
            var options = $scope.getSnippetOptions(snippet);
            options.type = "Subnet";
            options.subnet = {
                id: makeInteger(0, 100)
            };
            options.data = {
                name: makeName("name"),
                value: makeName("value"),
                enabled: true
            };
            spyOn(DHCPSnippetsManager, "updateItem").and.returnValue(
                $q.defer().promise);
            $scope.snippetSave(snippet);
            expect(DHCPSnippetsManager.updateItem).toHaveBeenCalledWith({
                name: options.data.name,
                value: options.data.value,
                enabled: true,
                subnet: options.subnet.id
            });
        });

        it("sets saving and calls snippetExitEdit", function() {
            $routeParams.section = "dhcp";
            var defer = $q.defer();
            var controller = makeController(defer);
            defer.resolve();
            $scope.$digest();
            var snippet = makeSnippet();
            var options = $scope.getSnippetOptions(snippet);
            options.type = "Global";
            options.data = {
                name: makeName("name"),
                value: makeName("value"),
                enabled: true
            };
            spyOn(DHCPSnippetsManager, "updateItem").and.returnValue(
                defer.promise);
            spyOn($scope, "snippetExitEdit");
            $scope.snippetSave(snippet);
            expect(options.saving).toBe(true);
            defer.resolve();
            $scope.$digest();
            expect($scope.snippetExitEdit).toHaveBeenCalledWith(snippet, true);
        });

        it("handles setting error", function() {
            $routeParams.section = "dhcp";
            var defer = $q.defer();
            var controller = makeController(defer);
            defer.resolve();
            $scope.$digest();
            var snippet = makeSnippet();
            var options = $scope.getSnippetOptions(snippet);
            options.type = "Global";
            options.data = {
                name: makeName("name"),
                value: makeName("value"),
                enabled: true
            };
            defer = $q.defer();
            spyOn(DHCPSnippetsManager, "updateItem").and.returnValue(
                defer.promise);
            var error = {};
            $scope.snippetSave(snippet);
            defer.reject(error);
            $scope.$digest();
            expect(options.error).toBe(
                    ManagerHelperService.parseValidationError(error));
            expect(options.saving).toBe(false);
        });
    });

    describe("snippetToggle", function() {

        it("calls updateItem", function() {
            $routeParams.section = "dhcp";
            var defer = $q.defer();
            var controller = makeController(defer);
            defer.resolve();
            $scope.$digest();
            var snippet = makeSnippet();
            var options = $scope.getSnippetOptions(snippet);
            spyOn(DHCPSnippetsManager, "updateItem").and.returnValue(
                $q.defer().promise);
            $scope.snippetToggle(snippet);
            expect(options.toggling).toBe(true);
        });

        it("updateItem resolve clears toggling", function() {
            $routeParams.section = "dhcp";
            var defer = $q.defer();
            var controller = makeController(defer);
            defer.resolve();
            $scope.$digest();
            var snippet = makeSnippet();
            var options = $scope.getSnippetOptions(snippet);
            spyOn(DHCPSnippetsManager, "updateItem").and.returnValue(
                defer.promise);
            $scope.snippetToggle(snippet);
            defer.resolve();
            $scope.$digest();
            expect(options.toggling).toBe(false);
        });

        it("updateItem reject resets enabled", function() {
            $routeParams.section = "dhcp";
            var defer = $q.defer();
            var controller = makeController(defer);
            defer.resolve();
            $scope.$digest();
            var snippet = makeSnippet();
            var options = $scope.getSnippetOptions(snippet);
            defer = $q.defer();
            spyOn(DHCPSnippetsManager, "updateItem").and.returnValue(
                defer.promise);
            $scope.snippetToggle(snippet);
            defer.reject();
            $scope.$digest();
            expect(snippet.enabled).toBe(false);
            expect(options.toggling).toBe(false);
        });
    });

    describe("snippetAdd", function() {

        it("sets newSnippet", function() {
            $routeParams.section = "dhcp";
            var controller = makeController();
            $scope.snippetAdd();
            expect($scope.newSnippet).toEqual({
                saving: false,
                type: "Global",
                data: {
                    name: "",
                    enabled: true
                }
            });
        });
    });

    describe("snippetAddCancel", function() {

        it("newSnippet gets cleared", function() {
            $routeParams.section = "dhcp";
            var controller = makeController();
            $scope.newSnippet = {};
            $scope.snippetAddCancel();
            expect($scope.newSnippet).toBeNull();
        });
    });

    describe("snippetAddCanBeSaved", function() {

        it("calls hasValidOptions with newSnippet", function() {
            $routeParams.section = "dhcp";
            var controller = makeController();
            var returnValue = {};
            $scope.newSnippet = {};
            spyOn($scope, "hasValidOptions").and.returnValue(returnValue);
            expect($scope.snippetAddCanBeSaved()).toBe(returnValue);
            expect($scope.hasValidOptions).toHaveBeenCalledWith(
                $scope.newSnippet);
        });
    });

    describe("snippetAddSave", function() {

        it("does nothing if snippet cannot be saved", function() {
            $routeParams.section = "dhcp";
            var controller = makeController();
            $scope.snippetAdd();
            $scope.snippetAddSave();
            spyOn(DHCPSnippetsManager, "create").and.returnValue(
                $q.defer().promise);
            $scope.snippetAddSave();
            expect(DHCPSnippetsManager.create).not.toHaveBeenCalled();
        });

        it("calls create for global", function() {
            $routeParams.section = "dhcp";
            var controller = makeController();
            var defer = $q.defer();
            $scope.snippetAdd();
            $scope.newSnippet.data.name = makeName("name");
            $scope.newSnippet.data.value = makeName("value");
            spyOn(DHCPSnippetsManager, "create").and.returnValue(
                defer.promise);
            $scope.snippetAddSave();
            expect(DHCPSnippetsManager.create).toHaveBeenCalledWith({
                name: $scope.newSnippet.data.name,
                value: $scope.newSnippet.data.value,
                enabled: true,
                subnet: null,
                node: null
            });
            defer.resolve();
            $scope.$digest();
            expect($scope.newSnippet).toBeNull();
        });

        it("calls create for node", function() {
            $routeParams.section = "dhcp";
            var controller = makeController();
            var defer = $q.defer();
            $scope.snippetAdd();
            $scope.newSnippet.type = "Node";
            $scope.newSnippet.data.name = makeName("name");
            $scope.newSnippet.data.value = makeName("value");
            $scope.newSnippet.data.node = makeName("system_id");
            spyOn(DHCPSnippetsManager, "create").and.returnValue(
                defer.promise);
            $scope.snippetAddSave();
            expect(DHCPSnippetsManager.create).toHaveBeenCalledWith({
                name: $scope.newSnippet.data.name,
                value: $scope.newSnippet.data.value,
                enabled: true,
                subnet: null,
                node: $scope.newSnippet.data.node
            });
            defer.resolve();
            $scope.$digest();
            expect($scope.newSnippet).toBeNull();
        });

        it("calls create for subnet", function() {
            $routeParams.section = "dhcp";
            var controller = makeController();
            var defer = $q.defer();
            $scope.snippetAdd();
            $scope.newSnippet.type = "Subnet";
            $scope.newSnippet.subnet = {
                id: makeInteger(0, 100)
            };
            $scope.newSnippet.data.name = makeName("name");
            $scope.newSnippet.data.value = makeName("value");
            spyOn(DHCPSnippetsManager, "create").and.returnValue(
                defer.promise);
            $scope.snippetAddSave();
            expect(DHCPSnippetsManager.create).toHaveBeenCalledWith({
                name: $scope.newSnippet.data.name,
                value: $scope.newSnippet.data.value,
                enabled: true,
                subnet: $scope.newSnippet.subnet.id,
                node: null
            });
            defer.resolve();
            $scope.$digest();
            expect($scope.newSnippet).toBeNull();
        });

        it("handles setting error", function() {
            $routeParams.section = "dhcp";
            var controller = makeController();
            var defer = $q.defer();
            var error = {
                error: {}
            };
            $scope.snippetAdd();
            $scope.newSnippet.data.name = makeName("name");
            $scope.newSnippet.data.value = makeName("value");
            spyOn(DHCPSnippetsManager, "create").and.returnValue(
                defer.promise);
            $scope.snippetAddSave();
            expect(DHCPSnippetsManager.create).toHaveBeenCalledWith({
                name: $scope.newSnippet.data.name,
                value: $scope.newSnippet.data.value,
                enabled: true,
                subnet: null,
                node: null
            });
            defer.reject(error);
            $scope.$digest();
            expect($scope.newSnippet.error).toBe(
                    ManagerHelperService.parseValidationError(error.error));
            expect($scope.newSnippet.saving).toBe(false);
        });
    });


///   REPOS


    describe("getRepositoryOptions", function() {

        it("returns always same object", function() {
            $routeParams.section = "repositories";
            var defer = $q.defer();
            var controller = makeController(defer);
            defer.resolve();
            $scope.$digest();
            var repository = makeRepo();
            var options = $scope.getRepositoryOptions(repository);
            expect(options).toEqual({});
            expect($scope.getRepositoryOptions(repository)).toBe(options);
        });
    });

    describe("repositoryEnterRemove", function() {

        it("calls closeAllRepos", function() {
            $routeParams.section = "repositories";
            var defer = $q.defer();
            var controller = makeController(defer);
            defer.resolve();
            $scope.$digest();
            var repository = makeRepo();
            spyOn($scope, "closeAllRepos");
            $scope.repositoryEnterRemove(repository);
            expect($scope.closeAllRepos).toHaveBeenCalled();
        });

        it("sets removing to true", function() {
            $routeParams.section = "repositories";
            var defer = $q.defer();
            var controller = makeController(defer);
            defer.resolve();
            $scope.$digest();
            var repository = makeRepo();
            $scope.repositoryEnterRemove(repository);
            expect($scope.getRepositoryOptions(repository).removing).toBe(
                true);
        });
    });

    describe("repositoryExitRemove", function() {

        it("sets removing to false", function() {
            $routeParams.section = "repositories";
            var defer = $q.defer();
            var controller = makeController(defer);
            defer.resolve();
            $scope.$digest();
            var repository = makeRepo();
            $scope.repositoryExitRemove(repository);
            expect($scope.getRepositoryOptions(repository).removing).toBe(
                false);
        });
    });

    describe("repositoryExitRemove", function() {

        it("sets removing to false", function() {
            $routeParams.section = "repositories";
            var defer = $q.defer();
            var controller = makeController(defer);
            defer.resolve();
            $scope.$digest();
            var repository = makeRepo();
            $scope.repositoryExitRemove(repository);
            expect($scope.getRepositoryOptions(repository).removing).toBe(
                false);
        });
    });

    describe("repositoryConfirmRemove", function() {

        it("calls deleteItem and then repositoryExitRemove", function() {
            $routeParams.section = "repositories";
            var controller = makeController();
            var repository = makeRepo();
            var defer = $q.defer();
            spyOn(PackageRepositoriesManager, "deleteItem").and.returnValue(
                defer.promise);
            spyOn($scope, "repositoryExitRemove");
            $scope.repositoryConfirmRemove(repository);
            expect(PackageRepositoriesManager.deleteItem).toHaveBeenCalledWith(
                repository);
            defer.resolve();
            $scope.$digest();
            expect($scope.repositoryExitRemove).toHaveBeenCalledWith(
                repository);
        });
    });

    describe("repositoryEnterEdit", function() {

        it("calls closeAllRepos", function() {
            $routeParams.section = "repositories";
            var defer = $q.defer();
            var controller = makeController(defer);
            defer.resolve();
            $scope.$digest();
            var repository = makeRepo();
            spyOn($scope, "closeAllRepos");
            $scope.repositoryEnterEdit(repository);
            expect($scope.closeAllRepos).toHaveBeenCalled();
        });

        it("sets options", function() {
            $routeParams.section = "repositories";
            var defer = $q.defer();
            var controller = makeController(defer);
            defer.resolve();
            $scope.$digest();
            var repository = makeRepo();
            repository.node = "";
            var subnet = {
                id: makeInteger(0, 100)
            };
            $scope.repositoryEnterEdit(repository);

            var options = $scope.getRepositoryOptions(repository);
            expect(options.editing).toBe(true);
            expect(options.saving).toBe(false);
            expect(options.error).toBeNull();
            expect(options.data).toEqual(repository);
            expect(options.data).not.toBe(repository);
        });
    });

    describe("repositoryExitEdit", function() {

        it("does nothing when saving without force", function() {
            $routeParams.section = "repositories";
            var defer = $q.defer();
            var controller = makeController(defer);
            defer.resolve();
            $scope.$digest();
            var repository = makeRepo();
            var options = $scope.getRepositoryOptions(repository);
            options.saving = true;
            options.editing = true;

            $scope.repositoryExitEdit(repository);
            expect(options.editing).toBe(true);
        });

        it("clears editing with saving and force", function() {
            $routeParams.section = "repositories";
            var defer = $q.defer();
            var controller = makeController(defer);
            defer.resolve();
            $scope.$digest();
            var repository = makeRepo();
            var options = $scope.getRepositoryOptions(repository);
            options.saving = true;
            options.editing = true;

            $scope.repositoryExitEdit(repository, true);
            expect(options.editing).toBe(false);
        });

        it("clears all required fields", function() {
            $routeParams.section = "repositories";
            var defer = $q.defer();
            var controller = makeController(defer);
            defer.resolve();
            $scope.$digest();
            var repository = makeRepo();
            var options = $scope.getRepositoryOptions(repository);
            options.saving = true;
            options.editing = true;
            options.error = {};
            options.type = {};
            options.data = {};

            $scope.repositoryExitEdit(repository, true);
            expect(options.saving).toBe(false);
            expect(options.editing).toBe(false);
            expect(options.error).toBeNull();
            expect(options.data).toBeUndefined();
        });
    });

    describe("repoHasValidOptions", function() {

        it("false when no data", function() {
            $routeParams.section = "repositories";
            var defer = $q.defer();
            var controller = makeController(defer);
            defer.resolve();
            $scope.$digest();
            var repository = makeRepo();
            var options = $scope.getRepositoryOptions(repository);
            options.data = null;
            expect($scope.repoHasValidOptions(options)).toBe(false);
        });

        it("false when no name and url", function() {
            $routeParams.section = "repositories";
            var defer = $q.defer();
            var controller = makeController(defer);
            defer.resolve();
            $scope.$digest();
            var repository = makeRepo();
            var options = $scope.getRepositoryOptions(repository);
            options.data = {
                name: "",
                url: ""
            };
            expect($scope.repoHasValidOptions(options)).toBe(false);
        });

    });

    describe("repositoryCanBeSaved", function() {

        it("calls repoHasValidOptions with options", function() {
            $routeParams.section = "repositories";
            var defer = $q.defer();
            var controller = makeController(defer);
            defer.resolve();
            $scope.$digest();
            var repository = makeRepo();
            var options = $scope.getRepositoryOptions(repository);
            var returnValue = {};
            spyOn($scope, "repoHasValidOptions").and.returnValue(returnValue);
            expect($scope.repositoryCanBeSaved(repository)).toBe(returnValue);
            expect($scope.repoHasValidOptions).toHaveBeenCalledWith(options);
        });
    });

    describe("repositorySave", function() {

        it("does nothing if repository cannot be saved", function() {
            $routeParams.section = "repositories";
            var defer = $q.defer();
            var controller = makeController(defer);
            defer.resolve();
            $scope.$digest();
            var repository = makeRepo();
            var options = $scope.getRepositoryOptions(repository);
            options.data = {};
            spyOn(PackageRepositoriesManager, "updateItem").and.returnValue(
                $q.defer().promise);
            $scope.repositorySave(repository);
        });

        it("calls updateItem for global", function() {
            $routeParams.section = "repositories";
            var defer = $q.defer();
            var controller = makeController(defer);
            defer.resolve();
            $scope.$digest();
            var repository = makeRepo();
            var options = $scope.getRepositoryOptions(repository);
            options.data = {
                name: makeName("name"),
                url: makeName("url"),
                enabled: true
            };
            spyOn(PackageRepositoriesManager, "updateItem").and.returnValue(
                $q.defer().promise);
            $scope.repositorySave(repository);
            expect(PackageRepositoriesManager.updateItem).toHaveBeenCalledWith({
                name: options.data.name,
                enabled: true,
                url: options.data.url,
                distributions: [],
                components: []
            });
        });

        it("sets saving and calls repositoryExitEdit", function() {
            $routeParams.section = "repositories";
            var defer = $q.defer();
            var controller = makeController(defer);
            defer.resolve();
            $scope.$digest();
            var repository = makeRepo();
            var options = $scope.getRepositoryOptions(repository);
            options.data = {
                name: makeName("name"),
                url: makeName("url"),
                enabled: true
            };
            spyOn(PackageRepositoriesManager, "updateItem").and.returnValue(
                defer.promise);
            spyOn($scope, "repositoryExitEdit");
            $scope.repositorySave(repository);
            expect(options.saving).toBe(true);
            defer.resolve();
            $scope.$digest();
            expect($scope.repositoryExitEdit).toHaveBeenCalledWith(
                repository, true);
        });

        it("handles setting error", function() {
            $routeParams.section = "repositories";
            var defer = $q.defer();
            var controller = makeController(defer);
            defer.resolve();
            $scope.$digest();
            var repository = makeRepo();
            var options = $scope.getRepositoryOptions(repository);
            options.data = {
                name: makeName("name"),
                url: makeName("url"),
                enabled: true
            };
            defer = $q.defer();
            spyOn(PackageRepositoriesManager, "updateItem").and.returnValue(
                defer.promise);
            var error = {};
            $scope.repositorySave(repository);
            defer.reject(error);
            $scope.$digest();
            expect(options.error).toBe(
                    ManagerHelperService.parseValidationError(error));
            expect(options.saving).toBe(false);
        });
    });

    describe("repositoryToggle", function() {

        it("calls updateItem", function() {
            $routeParams.section = "repositories";
            var defer = $q.defer();
            var controller = makeController(defer);
            defer.resolve();
            $scope.$digest();
            var repository = makeRepo();
            var options = $scope.getRepositoryOptions(repository);
            spyOn(PackageRepositoriesManager, "updateItem").and.returnValue(
                $q.defer().promise);
            $scope.repositoryToggle(repository);
            expect(options.toggling).toBe(true);
        });

        it("updateItem resolve clears toggling", function() {
            $routeParams.section = "repositories";
            var defer = $q.defer();
            var controller = makeController(defer);
            defer.resolve();
            $scope.$digest();
            var repository = makeRepo();
            var options = $scope.getRepositoryOptions(repository);
            spyOn(PackageRepositoriesManager, "updateItem").and.returnValue(
                defer.promise);
            $scope.repositoryToggle(repository);
            defer.resolve();
            $scope.$digest();
            expect(options.toggling).toBe(false);
        });

        it("updateItem reject resets enabled", function() {
            $routeParams.section = "repositories";
            var defer = $q.defer();
            var controller = makeController(defer);
            defer.resolve();
            $scope.$digest();
            var repository = makeRepo();
            var options = $scope.getRepositoryOptions(repository);
            defer = $q.defer();
            spyOn(PackageRepositoriesManager, "updateItem").and.returnValue(
                defer.promise);
            $scope.repositoryToggle(repository);
            defer.reject();
            $scope.$digest();
            expect(repository.enabled).toBe(false);
            expect(options.toggling).toBe(false);
        });
    });

    describe("repositoryAdd", function() {

        it("sets newRepository", function() {
            $routeParams.section = "repositories";
            var controller = makeController();
            $scope.repositoryAdd();
            expect($scope.newRepository).toEqual({
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
            });
        });
    });

    describe("repositoryAddCancel", function() {

        it("newRepository gets cleared", function() {
            $routeParams.section = "repositories";
            var controller = makeController();
            $scope.newRepository = {};
            $scope.repositoryAddCancel();
            expect($scope.newRepository).toBeNull();
        });
    });

    describe("repositoryAddCanBeSaved", function() {

        it("calls repoHasValidOptions with newRepository", function() {
            $routeParams.section = "repositories";
            var controller = makeController();
            var returnValue = {};
            $scope.newRepository = {};
            spyOn($scope, "repoHasValidOptions").and.returnValue(returnValue);
            expect($scope.repositoryAddCanBeSaved()).toBe(returnValue);
            expect($scope.repoHasValidOptions).toHaveBeenCalledWith(
                $scope.newRepository);
        });
    });

    describe("repositoryAddSave", function() {

        it("does nothing if repository cannot be saved", function() {
            $routeParams.section = "repositories";
            var controller = makeController();
            $scope.repositoryAdd();
            $scope.repositoryAddSave();
            spyOn(PackageRepositoriesManager, "create").and.returnValue(
                $q.defer().promise);
            $scope.repositoryAddSave();
            expect(PackageRepositoriesManager.create).not.toHaveBeenCalled();
        });

        it("calls create for global", function() {
            $routeParams.section = "repositories";
            var controller = makeController();
            var defer = $q.defer();
            $scope.repositoryAdd();
            $scope.newRepository.data.name = makeName("name");
            $scope.newRepository.data.url = makeName("url");
            spyOn(PackageRepositoriesManager, "create").and.returnValue(
                defer.promise);
            $scope.repositoryAddSave();
            expect(PackageRepositoriesManager.create).toHaveBeenCalledWith({
                name: $scope.newRepository.data.name,
                enabled: true,
                url: $scope.newRepository.data.url,
                key: "",
                arches: ["i386", "amd64"],
                distributions: [],
                components: []
            });
            defer.resolve();
            $scope.$digest();
            expect($scope.newRepository).toBeNull();
        });

        it("handles setting error", function() {
            $routeParams.section = "repositories";
            var controller = makeController();
            var defer = $q.defer();
            var error = {
                error: {}
            };
            $scope.repositoryAdd();
            $scope.newRepository.data.name = makeName("name");
            $scope.newRepository.data.url = makeName("url");
            spyOn(PackageRepositoriesManager, "create").and.returnValue(
                defer.promise);
            $scope.repositoryAddSave();
            expect(PackageRepositoriesManager.create).toHaveBeenCalledWith({
                name: $scope.newRepository.data.name,
                enabled: true,
                url: $scope.newRepository.data.url,
                key: "",
                arches: ["i386", "amd64"],
                distributions: [],
                components: []
            });
            defer.reject(error);
            $scope.$digest();
            expect($scope.newRepository.error).toBe(
                    ManagerHelperService.parseValidationError(error.error));
            expect($scope.newRepository.saving).toBe(false);
        });
    });
});
