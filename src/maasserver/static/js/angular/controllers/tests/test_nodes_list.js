/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for NodesListController.
 */

// Make a fake user.
var userId = 0;
function makeUser() {
    return {
        id: userId++,
        username: makeName("username"),
        first_name: makeName("first_name"),
        last_name: makeName("last_name"),
        email: makeName("email"),
        is_superuser: false,
        sshkeys_count: 0
    };
}


describe("NodesListController", function() {

    // Load the MAAS module.
    beforeEach(module("MAAS"));

    // Grab the needed angular pieces.
    var $controller, $rootScope, $scope, $q, $routeParams;
    beforeEach(inject(function($injector) {
        $controller = $injector.get("$controller");
        $rootScope = $injector.get("$rootScope");
        $scope = $rootScope.$new();
        $q = $injector.get("$q");
        $routeParams = {};
    }));

    // Load the NodesManager, DevicesManager, GeneralManager,
    // NodesManager, RegionConnection, SearchService and mock the
    // websocket connection.
    var NodesManager, DevicesManager, GeneralManager, RegionConnection;
    var ManagerHelperService, SearchService, webSocket;
    beforeEach(inject(function($injector) {
        NodesManager = $injector.get("NodesManager");
        DevicesManager = $injector.get("DevicesManager");
        GeneralManager = $injector.get("GeneralManager");
        ZonesManager = $injector.get("ZonesManager");
        UsersManager = $injector.get("UsersManager");
        RegionConnection = $injector.get("RegionConnection");
        ManagerHelperService = $injector.get("ManagerHelperService");
        SearchService = $injector.get("SearchService");

        // Mock buildSocket so an actual connection is not made.
        webSocket = new MockWebSocket();
        spyOn(RegionConnection, "buildSocket").and.returnValue(webSocket);
    }));

    // Makes the NodesListController
    function makeController(loadManagersDefer, defaultConnectDefer) {
        var loadManagers = spyOn(ManagerHelperService, "loadManagers");
        if(angular.isObject(loadManagersDefer)) {
            loadManagers.and.returnValue(loadManagersDefer.promise);
        } else {
            loadManagers.and.returnValue($q.defer().promise);
        }

        var defaultConnect = spyOn(RegionConnection, "defaultConnect");
        if(angular.isObject(defaultConnectDefer)) {
            defaultConnect.and.returnValue(defaultConnectDefer.promise);
        } else {
            defaultConnect.and.returnValue($q.defer().promise);
        }

        // Start the connection so a valid websocket is created in the
        // RegionConnection.
        RegionConnection.connect("");

        // Create the controller.
        var controller = $controller("NodesListController", {
            $scope: $scope,
            $rootScope: $rootScope,
            $routeParams: $routeParams,
            NodesManager: NodesManager,
            DevicesManager: DevicesManager,
            ManagerHelperService: ManagerHelperService,
            SearchService: SearchService
        });

        // Since the osSelection directive is not used in this test the
        // osSelection item on the model needs to have $reset function added
        // because it will be called throughout many of the tests.
        $scope.tabs.nodes.osSelection.$reset = jasmine.createSpy("$reset");

        return controller;
    }

    // Makes a fake node/device.
    function makeObject(tab) {
        if (tab === 'nodes') {
            var node = {
                system_id: makeName("system_id"),
                $selected: false
            };
            NodesManager._items.push(node);
            return node;
        }
        else if (tab === 'devices') {
            var device = {
                system_id: makeName("system_id"),
                $selected: false
            };
            DevicesManager._items.push(device);
            return device;
        }
        return null;
    }

    it("sets title and page on $rootScope", function() {
        var controller = makeController();
        expect($rootScope.title).toBe("Nodes");
        expect($rootScope.page).toBe("nodes");
    });

    it("sets initial values on $scope", function() {
        // tab-independant variables.
        var controller = makeController();
        expect($scope.nodes).toBe(NodesManager.getItems());
        expect($scope.devices).toBe(DevicesManager.getItems());
        expect($scope.osinfo).toBe(GeneralManager.getData("osinfo"));
        expect($scope.addHardwareOption).toBeNull();
        expect($scope.addHardwareOptions).toEqual([
            {
                name: "machine",
                title: "Machine"
            },
            {
                name: "chassis",
                title: "Chassis"
            }
        ]);
        expect($scope.addHardwareScope).toBeNull();
        expect($scope.loading).toBe(true);
    });

    it("calls stopPolling when scope destroyed", function() {
        var controller = makeController();
        spyOn(GeneralManager, "stopPolling");
        $scope.$destroy();
        expect(GeneralManager.stopPolling).toHaveBeenCalledWith(
            "osinfo");
    });

    it("calls loadManagers with NodesManager, DevicesManager," +
        "GeneralManager, UsersManager",
        function() {
            var controller = makeController();
            expect(ManagerHelperService.loadManagers).toHaveBeenCalledWith(
                [NodesManager, DevicesManager, GeneralManager,
                 ZonesManager, UsersManager]);
        });

    it("sets loading to false with loadManagers resolves", function() {
        var defer = $q.defer();
        var controller = makeController(defer);
        defer.resolve();
        $rootScope.$digest();
        expect($scope.loading).toBe(false);
    });

    it("sets nodes search from $routeParams.query",
        function() {
            var query = makeName("query");
            $routeParams.query = query;
            var controller = makeController();
            expect($scope.tabs.nodes.search).toBe(query);
        });

    it("calls updateFilters for nodes if search from $routeParams.query",
        function() {
            var query = makeName("query");
            $routeParams.query = query;
            var controller = makeController();
            expect($scope.tabs.nodes.filters._).toEqual([query]);
        });

    describe("toggleTab", function() {

        it("sets $rootScope.title", function() {
            var controller = makeController();
            $scope.toggleTab('devices');
            expect($rootScope.title).toBe($scope.tabs.devices.pagetitle);
            $scope.toggleTab('nodes');
            expect($rootScope.title).toBe($scope.tabs.nodes.pagetitle);
        });

        it("sets currentpage", function() {
            var controller = makeController();
            $scope.toggleTab('devices');
            expect($scope.currentpage).toBe('devices');
            $scope.toggleTab('nodes');
            expect($scope.currentpage).toBe('nodes');
        });
    });

    angular.forEach(["nodes", "devices"], function(tab) {

        describe("tab(" + tab + ")", function() {

            var manager;
            beforeEach(function() {
                if(tab === "nodes") {
                    manager = NodesManager;
                } else if(tab === "devices") {
                    manager = DevicesManager;
                } else {
                    throw new Error("Unknown manager for tab: " + tab);
                }
            });

            it("sets initial values on $scope", function() {
                var controller = makeController();
                var tabScope = $scope.tabs[tab];
                expect(tabScope.previous_search).toBe("");
                expect(tabScope.search).toBe("");
                expect(tabScope.searchValid).toBe(true);
                expect(tabScope.filtered_items).toEqual([]);
                expect(tabScope.predicate).toBe("fqdn");
                expect(tabScope.allViewableChecked).toBe(false);
                expect(tabScope.selectedItems).toBe(
                    tabScope.manager.getSelectedItems());
                expect(tabScope.metadata).toBe(tabScope.manager.getMetadata());
                expect(tabScope.filters).toBe(SearchService.emptyFilter);
                expect(tabScope.column).toBe("fqdn");
                expect(tabScope.actionOption).toBeNull();
                expect(tabScope.takeActionOptions).toEqual([]);
                expect(tabScope.actionErrorCount).toBe(0);
                expect(tabScope.zoneSelection).toBeNull();

                // Only the nodes tab uses the osSelection field.
                if(tab === "nodes") {
                    expect(tabScope.osSelection.osystem).toBeNull();
                    expect(tabScope.osSelection.release).toBeNull();
                }
            });
        });

    });

    angular.forEach(["nodes", "devices"], function(tab) {

        describe("tab(" + tab + ")", function() {

            describe("clearSearch", function() {

                it("sets search to empty string", function() {
                    var controller = makeController();
                    $scope.tabs[tab].search = makeName("search");
                    $scope.clearSearch(tab);
                    expect($scope.tabs[tab].search).toBe("");
                });

                it("calls updateFilters", function() {
                    var controller = makeController();
                    spyOn($scope, "updateFilters");
                    $scope.clearSearch(tab);
                    expect($scope.updateFilters).toHaveBeenCalledWith(tab);
                });
            });

            describe("toggleChecked", function() {

                var controller, object, tabObj;
                beforeEach(function() {
                    controller = makeController();
                    object = makeObject(tab);
                    tabObj = $scope.tabs[tab];
                    $scope.tabs.nodes.filtered_items = $scope.nodes;
                    $scope.tabs.devices.filtered_items = $scope.devices;
                });

                it("selects object", function() {
                    $scope.toggleChecked(object, tab);
                    expect(object.$selected).toBe(true);
                });

                it("deselects object", function() {
                    tabObj.manager.selectItem(object.system_id);
                    $scope.toggleChecked(object, tab);
                    expect(object.$selected).toBe(false);
                });

                it("sets allViewableChecked to true when all objects selected",
                    function() {
                        $scope.toggleChecked(object, tab);
                        expect(tabObj.allViewableChecked).toBe(true);
                });

                it(
                    "sets allViewableChecked to false when not all objects " +
                    "selected",
                    function() {
                        var object2 = makeObject(tab);
                        $scope.toggleChecked(object, tab);
                        expect(tabObj.allViewableChecked).toBe(false);
                });

                it("sets allViewableChecked to false when selected and " +
                    "deselected",
                    function() {
                        $scope.toggleChecked(object, tab);
                        $scope.toggleChecked(object, tab);
                        expect(tabObj.allViewableChecked).toBe(false);
                });

                it("resets search when in:selected and none selected",
                    function() {
                    tabObj.search = "in:(Selected)";
                    $scope.toggleChecked(object, tab);
                    $scope.toggleChecked(object, tab);
                    expect(tabObj.search).toBe("");
                });

                it("ignores search when not in:selected and none selected",
                    function() {
                    tabObj.search = "other";
                    $scope.toggleChecked(object, tab);
                    $scope.toggleChecked(object, tab);
                    expect(tabObj.search).toBe("other");
                });

                it("updates actionErrorCount", function() {
                    object.actions = [];
                    tabObj.actionOption = {
                        "name": "deploy"
                    };
                    $scope.toggleChecked(object, tab);
                    expect(tabObj.actionErrorCount).toBe(1);
                });

                it("clears action option when none selected", function() {
                    object.actions = [];
                    tabObj.actionOption = {};
                    $scope.toggleChecked(object, tab);
                    $scope.toggleChecked(object, tab);
                    expect(tabObj.actionOption).toBeNull();
                });
            });

            describe("toggleCheckAll", function() {

                var controller, object1, object2, tabObj;
                beforeEach(function() {
                    controller = makeController();
                    object1 = makeObject(tab);
                    object2 = makeObject(tab);
                    tabObj = $scope.tabs[tab];
                    $scope.tabs.nodes.filtered_items = $scope.nodes;
                    $scope.tabs.devices.filtered_items = $scope.devices;
                });

                it("selects all objects", function() {
                    $scope.toggleCheckAll(tab);
                    expect(object1.$selected).toBe(true);
                    expect(object2.$selected).toBe(true);
                });

                it("deselects all objects", function() {
                    $scope.toggleCheckAll(tab);
                    $scope.toggleCheckAll(tab);
                    expect(object1.$selected).toBe(false);
                    expect(object2.$selected).toBe(false);
                });

                it("resets search when in:selected and none selected",
                    function() {
                    tabObj.search = "in:(Selected)";
                    $scope.toggleCheckAll(tab);
                    $scope.toggleCheckAll(tab);
                    expect(tabObj.search).toBe("");
                });

                it("ignores search when not in:selected and none selected",
                    function() {
                    tabObj.search = "other";
                    $scope.toggleCheckAll(tab);
                    $scope.toggleCheckAll(tab);
                    expect(tabObj.search).toBe("other");
                });

                it("updates actionErrorCount", function() {
                    object1.actions = [];
                    object2.actions = [];
                    tabObj.actionOption = {
                        "name": "deploy"
                    };
                    $scope.toggleCheckAll(tab);
                    expect(tabObj.actionErrorCount).toBe(2);
                });

                it("clears action option when none selected", function() {
                    $scope.actionOption = {};
                    $scope.toggleCheckAll(tab);
                    $scope.toggleCheckAll(tab);
                    expect(tabObj.actionOption).toBeNull();
                });
            });

            describe("showSelected", function() {

                it("sets search to in:selected", function() {
                    var controller = makeController();
                    $scope.tabs[tab].selectedItems.push(makeObject(tab));
                    $scope.tabs[tab].actionOption = {};
                    $scope.showSelected(tab);
                    expect($scope.tabs[tab].search).toBe("in:(Selected)");
                });

                it("updateFilters with the new search", function() {
                    var controller = makeController();
                    $scope.tabs[tab].selectedItems.push(makeObject(tab));
                    $scope.tabs[tab].actionOption = {};
                    $scope.showSelected(tab);
                    expect($scope.tabs[tab].filters["in"]).toEqual(
                        ["Selected"]);
                });
            });

            describe("toggleFilter", function() {

                it("resets search if in:selected", function() {
                    var controller = makeController();
                    $scope.tabs[tab].search = "in:(Selected)";
                    $scope.tabs[tab].filters = { _: [], "in": ["Selected"] };
                    $scope.toggleFilter("hostname", "test", tab);
                    expect($scope.tabs[tab].filters).toEqual({
                        _: [],
                        hostname: ["test"]
                    });
                });

                it("calls SearchService.toggleFilter", function() {
                    var controller = makeController();
                    spyOn(SearchService, "toggleFilter").and.returnValue(
                        SearchService.emptyFilter);
                    $scope.toggleFilter("hostname", "test", tab);
                    expect(SearchService.toggleFilter).toHaveBeenCalled();
                });

                it("sets $scope.filters", function() {
                    var controller = makeController();
                    var filters = { _: [], other: [] };
                    spyOn(SearchService, "toggleFilter").and.returnValue(
                        filters);
                    $scope.toggleFilter("hostname", "test", tab);
                    expect($scope.tabs[tab].filters).toBe(filters);
                });

                it("calls SearchService.filtersToString", function() {
                    var controller = makeController();
                    spyOn(SearchService, "filtersToString").and.returnValue(
                        "");
                    $scope.toggleFilter("hostname", "test", tab);
                    expect(SearchService.filtersToString).toHaveBeenCalled();
                });

                it("sets $scope.search", function() {
                    var controller = makeController();
                    $scope.toggleFilter("hostname", "test", tab);
                    expect($scope.tabs[tab].search).toBe("hostname:(test)");
                });
            });

            describe("isFilterActive", function() {

                it("returns true when active", function() {
                    var controller = makeController();
                    $scope.toggleFilter("hostname", "test", tab);
                    expect(
                        $scope.isFilterActive(
                            "hostname", "test", tab)).toBe(true);
                });

                it("returns false when inactive", function() {
                    var controller = makeController();
                    $scope.toggleFilter("hostname", "test2", tab);
                    expect(
                        $scope.isFilterActive(
                            "hostname", "test", tab)).toBe(false);
                });
            });

            describe("updateFilters", function() {

                it("updates filters and sets searchValid to true", function() {
                    var controller = makeController();
                    $scope.tabs[tab].search = "test hostname:name";
                    $scope.updateFilters(tab);
                    expect($scope.tabs[tab].filters).toEqual({
                        _: ["test"],
                        hostname: ["name"]
                    });
                    expect($scope.tabs[tab].searchValid).toBe(true);
                });

                it("updates sets filters empty and sets searchValid to false",
                    function() {
                        var controller = makeController();
                        $scope.tabs[tab].search = "test hostname:(name";
                        $scope.updateFilters(tab);
                        expect(
                            $scope.tabs[tab].filters).toBe(
                                SearchService.emptyFilter);
                        expect($scope.tabs[tab].searchValid).toBe(false);
                    });
            });

            describe("sortTable", function() {

                it("sets predicate", function() {
                    var controller = makeController();
                    var predicate = makeName('predicate');
                    $scope.sortTable(predicate, tab);
                    expect($scope.tabs[tab].predicate).toBe(predicate);
                });

                it("reverses reverse", function() {
                    var controller = makeController();
                    $scope.tabs[tab].reverse = true;
                    $scope.sortTable(makeName('predicate'), tab);
                    expect($scope.tabs[tab].reverse).toBe(false);
                });
            });

            describe("selectColumnOrSort", function() {

                it("sets column if different", function() {
                    var controller = makeController();
                    var column = makeName('column');
                    $scope.selectColumnOrSort(column, tab);
                    expect($scope.tabs[tab].column).toBe(column);
                });

                it("calls sortTable if column already set", function() {
                    var controller = makeController();
                    var column = makeName('column');
                    $scope.tabs[tab].column = column;
                    spyOn($scope, "sortTable");
                    $scope.selectColumnOrSort(column, tab);
                    expect($scope.sortTable).toHaveBeenCalledWith(
                        column, tab);
                });
            });

            describe("supportsAction", function() {

                it("returns true if actionOption is null", function() {
                    var controller = makeController();
                    var object = makeObject(tab);
                    object.actions = ["start", "stop"];
                    expect($scope.supportsAction(object, tab)).toBe(true);
                });

                it("returns true if actionOption in object.actions",
                    function() {
                    var controller = makeController();
                    var object = makeObject(tab);
                    object.actions = ["start", "stop"];
                    $scope.tabs.nodes.actionOption = { name: "start" };
                    expect($scope.supportsAction(object, tab)).toBe(true);
                });

                it("returns false if actionOption not in object.actions",
                    function() {
                    var controller = makeController();
                    var object = makeObject(tab);
                    object.actions = ["start", "stop"];
                    $scope.tabs[tab].actionOption = { name: "deploy" };
                    expect($scope.supportsAction(object, tab)).toBe(false);
                });
            });

        });

    });

    angular.forEach(["nodes", "devices"], function(tab) {

        describe("tab(" + tab + ")", function() {

            describe("actionOptionSelected", function() {

                it("sets actionErrorCount to zero", function() {
                    var controller = makeController();
                    $scope.tabs[tab].actionErrorCount = 1;
                    $scope.actionOptionSelected(tab);
                    expect($scope.tabs[tab].actionErrorCount).toBe(0);
                });

                it("sets actionErrorCount to 1 when selected object doesn't " +
                    "support action",
                    function() {
                        var controller = makeController();
                        var object = makeObject(tab);
                        object.actions = ['start', 'stop'];
                        $scope.tabs[tab].actionOption = { name: 'deploy' };
                        $scope.tabs[tab].selectedItems = [object];
                        $scope.actionOptionSelected(tab);
                        expect($scope.tabs[tab].actionErrorCount).toBe(1);
                    });

                it("sets search to in:selected", function() {
                    var controller = makeController();
                    $scope.actionOptionSelected(tab);
                    expect($scope.tabs[tab].search).toBe("in:(Selected)");
                });

                it("sets previous_search to search value", function() {
                    var controller = makeController();
                    var search = makeName("search");
                    $scope.tabs[tab].search = search;
                    $scope.tabs[tab].actionErrorCount = 1;
                    $scope.actionOptionSelected(tab);
                    expect($scope.tabs[tab].previous_search).toBe(search);
                });

                it("action deploy calls startPolling for osinfo", function() {
                    var controller = makeController();
                    $scope.tabs[tab].actionOption = {
                        "name": "deploy"
                    };
                    spyOn(GeneralManager, "startPolling");
                    $scope.actionOptionSelected(tab);
                    expect(GeneralManager.startPolling).toHaveBeenCalledWith(
                        "osinfo");
                });

                it("changing away from deploy calls startPolling for osinfo",
                    function() {
                        var controller = makeController();
                        $scope.tabs[tab].actionOption = {
                            "name": "deploy"
                        };
                        spyOn(GeneralManager, "startPolling");
                        spyOn(GeneralManager, "stopPolling");
                        $scope.actionOptionSelected(tab);

                        $scope.tabs[tab].actionOption = {
                            "name": "acquire"
                        };
                        $scope.actionOptionSelected(tab);
                        var expected = expect(GeneralManager.stopPolling);
                        expected.toHaveBeenCalledWith("osinfo");
                    });

                it("calls hide on addHardwareScope", function() {
                    var controller;
                    if (tab === 'nodes') {
                        controller = makeController();
                        $scope.addHardwareScope = {
                            hide: jasmine.createSpy("hide")
                        };
                        $scope.actionOptionSelected(tab);
                        expect(
                            $scope.addHardwareScope.hide).toHaveBeenCalled();
                    } else if (tab === 'devices') {
                        controller = makeController();
                        $scope.addDeviceScope = {
                            hide: jasmine.createSpy("hide")
                        };
                        $scope.actionOptionSelected(tab);
                        expect(
                            $scope.addDeviceScope.hide).toHaveBeenCalled();
                    }
                });

            });

            describe("isActionError", function() {

                it("returns true if actionErrorCount > 0", function() {
                    var controller = makeController();
                    $scope.tabs[tab].actionErrorCount = 2;
                    expect($scope.isActionError(tab)).toBe(true);
                });

                it("returns false if actionErrorCount === 0", function() {
                    var controller = makeController();
                    $scope.tabs[tab].actionErrorCount = 0;
                    expect($scope.isActionError(tab)).toBe(false);
                });

                it("returns true if deploy action missing osinfo", function() {
                    var controller = makeController();
                    $scope.tabs[tab].actionOption = {
                        name: "deploy"
                    };
                    $scope.tabs[tab].actionErrorCount = 0;
                    $scope.osinfo = {
                        osystems: []
                    };
                    expect($scope.isActionError(tab)).toBe(true);
                });

                it("returns true if action missing ssh keys",
                    function() {
                        var controller = makeController();
                        $scope.tabs[tab].actionOption = {
                            name: "deploy"
                        };
                        $scope.tabs[tab].actionErrorCount = 0;
                        $scope.osinfo = {
                            osystems: [makeName("os")]
                        };
                        var firstUser = makeUser();
                        UsersManager._authUser = firstUser;
                        firstUser.sshkeys_count = 0;
                        expect($scope.isActionError(tab)).toBe(true);
                    });

                it("returns false if deploy action not missing osinfo or keys",
                    function() {
                        var controller = makeController();
                        $scope.tabs[tab].actionOption = {
                            name: "deploy"
                        };
                        $scope.tabs[tab].actionErrorCount = 0;
                        $scope.osinfo = {
                            osystems: [makeName("os")]
                        };
                        var firstUser = makeUser();
                        firstUser.sshkeys_count = 1;
                        UsersManager._authUser = firstUser;
                        expect($scope.isActionError(tab)).toBe(false);
                    });
            });

            describe("isSSHKeyError", function() {

                it("returns false if actionErrorCount > 0", function() {
                    var controller = makeController();
                    $scope.tabs[tab].actionErrorCount = 2;
                    expect($scope.isSSHKeyError(tab)).toBe(false);
                });

                it("returns true if deploy action missing ssh keys",
                    function() {
                        var controller = makeController();
                        $scope.tabs[tab].actionOption = {
                            name: "deploy"
                        };
                        $scope.tabs[tab].actionErrorCount = 0;
                        expect($scope.isSSHKeyError(tab)).toBe(true);
                    });

                it("returns false if deploy action not missing ssh keys",
                    function() {
                        var controller = makeController();
                        $scope.tabs[tab].actionOption = {
                            name: "deploy"
                        };
                        $scope.tabs[tab].actionErrorCount = 0;
                        var firstUser = makeUser();
                        firstUser.sshkeys_count = 1;
                        UsersManager._authUser = firstUser;
                        expect($scope.isSSHKeyError(tab)).toBe(false);
                    });
            });

            describe("isDeployError", function() {

                it("returns false if actionErrorCount > 0", function() {
                    var controller = makeController();
                    $scope.tabs[tab].actionErrorCount = 2;
                    expect($scope.isDeployError(tab)).toBe(false);
                });

                it("returns true if deploy action missing osinfo", function() {
                    var controller = makeController();
                    $scope.tabs[tab].actionOption = {
                        name: "deploy"
                    };
                    $scope.tabs[tab].actionErrorCount = 0;
                    $scope.osinfo = {
                        osystems: []
                    };
                    expect($scope.isDeployError(tab)).toBe(true);
                });

                it("returns false if deploy action not missing osinfo",
                    function() {
                        var controller = makeController();
                        $scope.tabs[tab].actionOption = {
                            name: "deploy"
                        };
                        $scope.tabs[tab].actionErrorCount = 0;
                        $scope.osinfo = {
                            osystems: [makeName("os")]
                        };
                        expect($scope.isDeployError(tab)).toBe(false);
                    });
            });

            describe("actionCancel", function() {

                it("clears search if in:selected", function() {
                    var controller = makeController();
                    $scope.tabs[tab].search = "in:(Selected)";
                    $scope.actionCancel(tab);
                    expect($scope.tabs[tab].search).toBe("");
                });

                it("clears search if in:selected (device)", function() {
                    var controller = makeController();
                    $scope.tabs.devices.search = "in:(Selected)";
                    $scope.actionCancel('devices');
                    expect($scope.tabs.devices.search).toBe("");
                });

                it("doesnt clear search if not in:Selected", function() {
                    var controller = makeController();
                    $scope.tabs[tab].search = "other";
                    $scope.actionCancel(tab);
                    expect($scope.tabs[tab].search).toBe("other");
                });

                it("sets actionOption to null", function() {
                    var controller = makeController();
                    $scope.tabs[tab].actionOption = {};
                    $scope.actionCancel(tab);
                    expect($scope.tabs[tab].actionOption).toBeNull();
                });

                it("resets actionProgress", function() {
                    var controller = makeController();
                    $scope.tabs[tab].actionProgress.total = makeInteger(0, 10);
                    $scope.tabs[tab].actionProgress.completed =
                        makeInteger(0, 10);
                    $scope.tabs[tab].actionProgress.errors[makeName("error")] =
                        [{}];
                    $scope.actionCancel(tab);
                    expect($scope.tabs[tab].actionProgress.total).toBe(0);
                    expect($scope.tabs[tab].actionProgress.completed).toBe(0);
                    expect($scope.tabs[tab].actionProgress.errors).toEqual({});
                });
            });

            describe("actionGo", function() {

                it("sets actionProgress.total to the number of selectedItems",
                    function() {
                        var controller = makeController();
                        var object = makeObject(tab);
                        $scope.tabs[tab].actionOption = { name: "start" };
                        $scope.tabs[tab].selectedItems = [
                            makeObject(tab),
                            makeObject(tab),
                            makeObject(tab)
                            ];
                        $scope.actionGo(tab);
                        expect($scope.tabs[tab].actionProgress.total).toBe(
                            $scope.tabs[tab].selectedItems.length);
                    });

                it("calls performAction for selected object", function() {
                    var controller = makeController();
                    var object = makeObject(tab);
                    var spy = spyOn(
                        $scope.tabs[tab].manager,
                        "performAction").and.returnValue($q.defer().promise);
                    $scope.tabs[tab].actionOption = { name: "start" };
                    $scope.tabs[tab].selectedItems = [object];
                    $scope.actionGo(tab);
                    expect(spy).toHaveBeenCalledWith(
                        object, "start", {});
                });

                it("calls unselectItem after complete", function() {
                    var controller = makeController();
                    var object = makeObject(tab);
                    var defer = $q.defer();
                    spyOn(
                        $scope.tabs[tab].manager,
                        "performAction").and.returnValue(defer.promise);
                    var spy = spyOn($scope.tabs[tab].manager, "unselectItem");
                    $scope.tabs[tab].actionOption = { name: "start" };
                    $scope.tabs[tab].selectedItems = [object];
                    $scope.actionGo(tab);
                    defer.resolve();
                    $scope.$digest();
                    expect(spy).toHaveBeenCalled();
                });

                it("increments actionProgress.completed after action complete",
                    function() {
                        var controller = makeController();
                        var object = makeObject(tab);
                        var defer = $q.defer();
                        spyOn(
                            $scope.tabs[tab].manager,
                            "performAction").and.returnValue(defer.promise);
                        $scope.tabs[tab].actionOption = { name: "start" };
                        $scope.tabs[tab].selectedItems = [object];
                        $scope.actionGo(tab);
                        defer.resolve();
                        $scope.$digest();
                        expect(
                            $scope.tabs[tab].actionProgress.completed).toBe(1);
                    });

                it("resets search to previous_search after complete",
                    function() {
                    var controller = makeController();
                    var defer = $q.defer();
                    spyOn(
                        $scope.tabs[tab].manager,
                        "performAction").and.returnValue(defer.promise);
                    var object = makeObject(tab);
                    var prev_search = makeName("search");
                    $scope.tabs[tab].manager._items.push(object);
                    $scope.tabs[tab].manager._selectedItems.push(object);
                    $scope.tabs[tab].previous_search = prev_search;
                    $scope.tabs[tab].search = "in:(Selected)";
                    $scope.tabs[tab].actionOption = { name: "start" };
                    $scope.actionGo(tab);
                    defer.resolve();
                    $scope.$digest();
                    expect($scope.tabs[tab].search).toBe(prev_search);
                });

                it("ignores search when not in:selected after complete",
                    function() {
                    var controller = makeController();
                    var defer = $q.defer();
                    spyOn(
                        $scope.tabs[tab].manager,
                        "performAction").and.returnValue(defer.promise);
                    var object = makeObject(tab);
                    $scope.tabs[tab].manager._items.push(object);
                    $scope.tabs[tab].manager._selectedItems.push(object);
                    $scope.tabs[tab].search = "other";
                    $scope.tabs[tab].actionOption = { name: "start" };
                    $scope.actionGo(tab);
                    defer.resolve();
                    $scope.$digest();
                    expect($scope.tabs[tab].search).toBe("other");
                });

                it("clears action option when complete", function() {
                    var controller = makeController();
                    var defer = $q.defer();
                    spyOn(
                        $scope.tabs[tab].manager,
                        "performAction").and.returnValue(defer.promise);
                    var object = makeObject(tab);
                    $scope.tabs[tab].manager._items.push(object);
                    $scope.tabs[tab].manager._selectedItems.push(object);
                    $scope.tabs[tab].actionOption = { name: "start" };
                    $scope.actionGo(tab);
                    defer.resolve();
                    $scope.$digest();
                    expect($scope.tabs[tab].actionOption).toBeNull();
                });

                it("increments actionProgress.completed after action error",
                    function() {
                        var controller = makeController();
                        var object = makeObject(tab);
                        var defer = $q.defer();
                        spyOn(
                            $scope.tabs[tab].manager,
                            "performAction").and.returnValue(defer.promise);
                        $scope.tabs[tab].actionOption = { name: "start" };
                        $scope.tabs[tab].selectedItems = [object];
                        $scope.actionGo(tab);
                        defer.reject(makeName("error"));
                        $scope.$digest();
                        expect(
                            $scope.tabs[tab].actionProgress.completed).toBe(1);
                    });

                it("adds error to actionProgress.errors on action error",
                    function() {
                        var controller = makeController();
                        var object = makeObject(tab);
                        var defer = $q.defer();
                        spyOn(
                            $scope.tabs[tab].manager,
                            "performAction").and.returnValue(defer.promise);
                        $scope.tabs[tab].actionOption = { name: "start" };
                        $scope.tabs[tab].selectedItems = [object];
                        $scope.actionGo(tab);
                        var error = makeName("error");
                        defer.reject(error);
                        $scope.$digest();
                        var errorObjects =
                            $scope.tabs[tab].actionProgress.errors[error];
                        expect(errorObjects[0].system_id).toBe(
                            object.system_id);
                    });
            });

            describe("hasActionsInProgress", function() {

                it("returns false if actionProgress.total not > 0", function() {
                    var controller = makeController();
                    $scope.tabs[tab].actionProgress.total = 0;
                    expect($scope.hasActionsInProgress(tab)).toBe(false);
                });

                it("returns true if actionProgress total != completed",
                    function() {
                        var controller = makeController();
                        $scope.tabs[tab].actionProgress.total = 1;
                        $scope.tabs[tab].actionProgress.completed = 0;
                        expect($scope.hasActionsInProgress(tab)).toBe(true);
                    });

                it("returns false if actionProgress total == completed",
                    function() {
                        var controller = makeController();
                        $scope.tabs[tab].actionProgress.total = 1;
                        $scope.tabs[tab].actionProgress.completed = 1;
                        expect($scope.hasActionsInProgress(tab)).toBe(false);
                    });
            });

            describe("hasActionsFailed", function() {

                it("returns false if no errors", function() {
                    var controller = makeController();
                    $scope.tabs[tab].actionProgress.errors = {};
                    expect($scope.hasActionsFailed(tab)).toBe(false);
                });

                it("returns true if errors", function() {
                    var controller = makeController();
                    var error = makeName("error");
                    var object = makeObject(tab);
                    var errors = $scope.tabs[tab].actionProgress.errors;
                    errors[error] = [object];
                    expect($scope.hasActionsFailed(tab)).toBe(true);
                });
            });

            describe("actionSetZone", function () {
                it("calls performAction with zone",
                    function() {
                        var controller = makeController();
                        var spy = spyOn(
                            $scope.tabs[tab].manager,
                            "performAction").and.returnValue(
                            $q.defer().promise);
                        var object = makeObject(tab);
                        $scope.tabs[tab].actionOption = { name: "set-zone" };
                        $scope.tabs[tab].selectedItems = [object];
                        $scope.tabs[tab].zoneSelection = { id: 1 };
                        $scope.actionGo(tab);
                        expect(spy).toHaveBeenCalledWith(
                            object, "set-zone", { zone_id: 1 });
                });

                it("clears action option when complete", function() {
                    var controller = makeController();
                    var defer = $q.defer();
                    spyOn(
                        $scope.tabs[tab].manager,
                        "performAction").and.returnValue(defer.promise);
                    var object = makeObject(tab);
                    $scope.tabs[tab].manager._items.push(object);
                    $scope.tabs[tab].manager._selectedItems.push(object);
                    $scope.tabs[tab].actionOption = { name: "set-zone" };
                    $scope.tabs[tab].zoneSelection = { id: 1 };
                    $scope.actionGo(tab);
                    defer.resolve();
                    $scope.$digest();
                    expect($scope.tabs[tab].zoneSelection).toBeNull();
                });
            });
        });
    });

    describe("tab(nodes)", function() {

        describe("actionGo", function() {

            it("calls performAction with osystem and distro_series",
                function() {
                    var controller = makeController();
                    var object = makeObject("nodes");
                    var spy = spyOn(
                        $scope.tabs.nodes.manager,
                        "performAction").and.returnValue(
                        $q.defer().promise);
                    $scope.tabs.nodes.actionOption = { name: "deploy" };
                    $scope.tabs.nodes.selectedItems = [object];
                    $scope.tabs.nodes.osSelection.osystem = "ubuntu";
                    $scope.tabs.nodes.osSelection.release = "ubuntu/trusty";
                    $scope.actionGo("nodes");
                    expect(spy).toHaveBeenCalledWith(
                        object, "deploy", {
                            osystem: "ubuntu",
                            distro_series: "trusty"
                        });
            });

            it("clears selected os and release when complete", function() {
                var controller = makeController();
                var defer = $q.defer();
                spyOn(
                    NodesManager,
                    "performAction").and.returnValue(defer.promise);
                var object = makeObject("nodes");
                NodesManager._items.push(object);
                NodesManager._selectedItems.push(object);
                $scope.tabs.nodes.actionOption = { name: "deploy" };
                $scope.tabs.nodes.osSelection.osystem = "ubuntu";
                $scope.tabs.nodes.osSelection.release = "ubuntu/trusty";
                $scope.actionGo("nodes");
                defer.resolve();
                $scope.$digest();
                expect($scope.tabs.nodes.osSelection.$reset).toHaveBeenCalled();
            });
        });
    });

    describe("addHardwareOptionChanged", function() {

        it("calls show in addHardwareScope", function() {
            var controller = makeController();
            $scope.addHardwareScope = {
                show: jasmine.createSpy("show")
            };
            $scope.addHardwareOption = {
                name: "hardware"
            };
            $scope.addHardwareOptionChanged();
            expect($scope.addHardwareScope.show).toHaveBeenCalledWith(
                "hardware");
        });
    });

    describe("addDevice", function() {

        it("calls show in addDeviceScope", function() {
            var controller = makeController();
            $scope.addDeviceScope = {
                show: jasmine.createSpy("show")
            };
            $scope.addDevice();
            expect($scope.addDeviceScope.show).toHaveBeenCalled();
        });
    });

    describe("cancelAddDevice", function() {

        it("calls cancel in addDeviceScope", function() {
            var controller = makeController();
            $scope.addDeviceScope = {
                cancel: jasmine.createSpy("cancel")
            };
            $scope.cancelAddDevice();
            expect($scope.addDeviceScope.cancel).toHaveBeenCalled();
        });
    });

    describe("getDeviceIPAssignment", function() {

        it("returns 'External' for external assignment", function() {
            var controller = makeController();
            expect($scope.getDeviceIPAssignment("external")).toBe(
                "External");
        });

        it("returns 'Dynamic' for dynamic assignment", function() {
            var controller = makeController();
            expect($scope.getDeviceIPAssignment("dynamic")).toBe(
                "Dynamic");
        });

        it("returns 'Static' for static assignment", function() {
            var controller = makeController();
            expect($scope.getDeviceIPAssignment("static")).toBe(
                "Static");
        });
    });
});
