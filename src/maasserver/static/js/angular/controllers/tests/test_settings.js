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
    var DHCPSnippetsManager, SubnetsManager, MachinesManager;
    var DevicesManager, ControllersManager, ManagerHelperService;
    var RegionConnection, webSocket;
    beforeEach(inject(function($injector) {
        DHCPSnippetsManager = $injector.get("DHCPSnippetsManager");
        SubnetsManager = $injector.get("SubnetsManager");
        MachinesManager = $injector.get("MachinesManager");
        DevicesManager = $injector.get("DevicesManager");
        ControllersManager = $injector.get("ControllersManager");
        ManagerHelperService = $injector.get("ManagerHelperService");
        RegionConnection = $injector.get("RegionConnection");

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
            DHCPSnippetsManager: DHCPSnippetsManager,
            SubnetsManager: SubnetsManager,
            MachinesManager: MachinesManager,
            DevicesManager: DevicesManager,
            ControllersManager: ControllersManager,
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
        var controller = makeController();
        expect($scope.loading).toBe(false);
        expect($scope.title).toBe("DHCP snippets");
    });

    it("initialized default values", function() {
        var controller = makeController();
        expect($scope.snippets).toBe(DHCPSnippetsManager.getItems());
        expect($scope.subnets).toBe(SubnetsManager.getItems());
        expect($scope.machines).toBe(MachinesManager.getItems());
        expect($scope.devices).toBe(DevicesManager.getItems());
        expect($scope.controllers).toBe(ControllersManager.getItems());
        expect($scope.snippetOptions).toEqual({});
        expect($scope.newSnippet).toBeNull();
    });

    it("calls loadManagers with all needed managers", function() {
        var controller = makeController();
        expect(ManagerHelperService.loadManagers).toHaveBeenCalledWith([
            DHCPSnippetsManager, MachinesManager, DevicesManager,
            ControllersManager, SubnetsManager]);
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
            var controller = makeController();
            var snippet = makeSnippet();
            var options = $scope.getSnippetOptions(snippet);
            expect(options).toEqual({});
            expect($scope.getSnippetOptions(snippet)).toBe(options);
        });
    });

    describe("getSubnetName", function() {

        it("calls SubnetsManager.getName", function() {
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
            var controller = makeController();
            var snippet = makeSnippet();
            snippet.node = makeName("system_id");
            expect($scope.getSnippetTypeText(snippet)).toBe("Node");
        });

        it("returns 'Subnet'", function() {
            var controller = makeController();
            var snippet = makeSnippet();
            snippet.subnet = makeInteger();
            expect($scope.getSnippetTypeText(snippet)).toBe("Subnet");
        });

        it("returns 'Global'", function() {
            var controller = makeController();
            var snippet = makeSnippet();
            expect($scope.getSnippetTypeText(snippet)).toBe("Global");
        });
    });

    describe("getSnippetAppliesToObject", function() {

        it("returns node from MachinesManager", function() {
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

        it("calls snippetExitEdit", function() {
            var controller = makeController();
            var snippet = makeSnippet();
            spyOn($scope, "snippetExitEdit");
            $scope.snippetEnterRemove(snippet);
            expect($scope.snippetExitEdit).toHaveBeenCalledWith(snippet);
        });

        it("sets removing to true", function() {
            var controller = makeController();
            var snippet = makeSnippet();
            $scope.snippetEnterRemove(snippet);
            expect($scope.getSnippetOptions(snippet).removing).toBe(true);
        });
    });

    describe("snippetExitRemove", function() {

        it("sets removing to false", function() {
            var controller = makeController();
            var snippet = makeSnippet();
            $scope.snippetExitRemove(snippet);
            expect($scope.getSnippetOptions(snippet).removing).toBe(false);
        });
    });

    describe("snippetExitRemove", function() {

        it("sets removing to false", function() {
            var controller = makeController();
            var snippet = makeSnippet();
            $scope.snippetExitRemove(snippet);
            expect($scope.getSnippetOptions(snippet).removing).toBe(false);
        });
    });

    describe("snippetConfirmRemove", function() {

        it("calls deleteItem and then snippetExitRemove", function() {
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

        it("calls snippetExitRemove", function() {
            var controller = makeController();
            var snippet = makeSnippet();
            spyOn($scope, "snippetExitRemove");
            $scope.snippetEnterEdit(snippet);
            expect($scope.snippetExitRemove).toHaveBeenCalledWith(snippet);
        });

        it("sets options", function() {
            var controller = makeController();
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
            var controller = makeController();
            var snippet = makeSnippet();
            var options = $scope.getSnippetOptions(snippet);
            options.saving = true;
            options.editing = true;

            $scope.snippetExitEdit(snippet);
            expect(options.editing).toBe(true);
        });

        it("clears editing with saving and force", function() {
            var controller = makeController();
            var snippet = makeSnippet();
            var options = $scope.getSnippetOptions(snippet);
            options.saving = true;
            options.editing = true;

            $scope.snippetExitEdit(snippet, true);
            expect(options.editing).toBe(false);
        });

        it("clears all required fields", function() {
            var controller = makeController();
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
            var controller = makeController();
            var snippet = makeSnippet();
            var fieldName = makeName("field");
            expect($scope.isFieldEmpty(snippet, fieldName)).toBe(true);
        });

        it("true when empty string", function() {
            var controller = makeController();
            var snippet = makeSnippet();
            var fieldName = makeName("field");
            snippet[fieldName] = "";
            expect($scope.isFieldEmpty(snippet, fieldName)).toBe(true);
        });

        it("false when empty string", function() {
            var controller = makeController();
            var snippet = makeSnippet();
            var fieldName = makeName("field");
            snippet[fieldName] = makeName("value");
            expect($scope.isFieldEmpty(snippet, fieldName)).toBe(false);
        });
    });

    describe("isFieldEmpty", function() {

        it("true when not a string", function() {
            var controller = makeController();
            var snippet = makeSnippet();
            var fieldName = makeName("field");
            expect($scope.isFieldEmpty(snippet, fieldName)).toBe(true);
        });

        it("true when empty string", function() {
            var controller = makeController();
            var snippet = makeSnippet();
            var fieldName = makeName("field");
            snippet[fieldName] = "";
            expect($scope.isFieldEmpty(snippet, fieldName)).toBe(true);
        });

        it("false when empty string", function() {
            var controller = makeController();
            var snippet = makeSnippet();
            var fieldName = makeName("field");
            snippet[fieldName] = makeName("value");
            expect($scope.isFieldEmpty(snippet, fieldName)).toBe(false);
        });
    });

    describe("hasValidOptions", function() {

        it("false when no name", function() {
            var controller = makeController();
            var snippet = makeSnippet();
            var options = $scope.getSnippetOptions(snippet);
            options.data = {
                name: ""
            };
            expect($scope.hasValidOptions(options)).toBe(false);
        });

        it("false when no value", function() {
            var controller = makeController();
            var snippet = makeSnippet();
            var options = $scope.getSnippetOptions(snippet);
            options.data = {
                name: makeName("name"),
                value: ""
            };
            expect($scope.hasValidOptions(options)).toBe(false);
        });

        it("false when no node set", function() {
            var controller = makeController();
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
            var controller = makeController();
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
            var controller = makeController();
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
            var controller = makeController();
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
            var controller = makeController();
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
            var controller = makeController();
            var snippet = makeSnippet();
            var options = $scope.getSnippetOptions(snippet);
            options.data = {};
            spyOn(DHCPSnippetsManager, "updateItem").and.returnValue(
                $q.defer().promise);
            $scope.snippetSave(snippet);
        });

        it("calls updateItem for global", function() {
            var controller = makeController();
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
            var controller = makeController();
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
            var controller = makeController();
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
            var controller = makeController();
            var snippet = makeSnippet();
            var options = $scope.getSnippetOptions(snippet);
            options.type = "Global";
            options.data = {
                name: makeName("name"),
                value: makeName("value"),
                enabled: true
            };
            var defer = $q.defer();
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
            var controller = makeController();
            var snippet = makeSnippet();
            var options = $scope.getSnippetOptions(snippet);
            options.type = "Global";
            options.data = {
                name: makeName("name"),
                value: makeName("value"),
                enabled: true
            };
            var defer = $q.defer();
            spyOn(DHCPSnippetsManager, "updateItem").and.returnValue(
                defer.promise);
            var error = {};
            $scope.snippetSave(snippet);
            defer.reject(error);
            $scope.$digest();
            expect(options.error).toBe(error);
            expect(options.saving).toBe(false);
        });
    });

    describe("snippetToggle", function() {

        it("calls updateItem", function() {
            var controller = makeController();
            var snippet = makeSnippet();
            var options = $scope.getSnippetOptions(snippet);
            spyOn(DHCPSnippetsManager, "updateItem").and.returnValue(
                $q.defer().promise);
            $scope.snippetToggle(snippet);
            expect(options.toggling).toBe(true);
        });

        it("updateItem resolve clears toggling", function() {
            var controller = makeController();
            var snippet = makeSnippet();
            var options = $scope.getSnippetOptions(snippet);
            var defer = $q.defer();
            spyOn(DHCPSnippetsManager, "updateItem").and.returnValue(
                defer.promise);
            $scope.snippetToggle(snippet);
            defer.resolve();
            $scope.$digest();
            expect(options.toggling).toBe(false);
        });

        it("updateItem reject resets enabled", function() {
            var controller = makeController();
            var snippet = makeSnippet();
            var options = $scope.getSnippetOptions(snippet);
            var defer = $q.defer();
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
            var controller = makeController();
            $scope.newSnippet = {};
            $scope.snippetAddCancel();
            expect($scope.newSnippet).toBeNull();
        });
    });

    describe("snippetAddCanBeSaved", function() {

        it("calls hasValidOptions with newSnippet", function() {
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
            var controller = makeController();
            $scope.snippetAdd();
            $scope.snippetAddSave();
            spyOn(DHCPSnippetsManager, "create").and.returnValue(
                $q.defer().promise);
            $scope.snippetAddSave();
            expect(DHCPSnippetsManager.create).not.toHaveBeenCalled();
        });

        it("calls create for global", function() {
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
            expect($scope.newSnippet.error).toBe(error.error);
            expect($scope.newSnippet.saving).toBe(false);
        });
    });
});
