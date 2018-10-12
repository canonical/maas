/* Copyright 2015-2018 Canonical Ltd.  This software is licensed under the
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

// Global MAAS_config;
MAAS_config = {};

describe("NodesListController", function() {

    // Load the MAAS module.
    beforeEach(module("MAAS"));

    // Grab the needed angular pieces.
    var $controller, $rootScope, $scope, $q, $routeParams, $location;
    beforeEach(inject(function($injector) {
        $controller = $injector.get("$controller");
        $rootScope = $injector.get("$rootScope");
        $location = $injector.get("$location");
        $scope = $rootScope.$new();
        $q = $injector.get("$q");
        $routeParams = {};
    }));

    // Load the required managers.
    var MachinesManager, DevicesManager, ControllersManager, GeneralManager,
        SwitchesManager, ZonesManager, UsersManager, ServicesManage,
        ResourcePoolsManager;
    var ManagerHelperService, SearchService;
    var ScriptsManager;
    beforeEach(inject(function($injector) {
        MachinesManager = $injector.get("MachinesManager");
        DevicesManager = $injector.get("DevicesManager");
        ControllersManager = $injector.get("ControllersManager");
        GeneralManager = $injector.get("GeneralManager");
        ZonesManager = $injector.get("ZonesManager");
        UsersManager = $injector.get("UsersManager");
        ServicesManager = $injector.get("ServicesManager");
        ManagerHelperService = $injector.get("ManagerHelperService");
        SearchService = $injector.get("SearchService");
        ScriptsManager = $injector.get("ScriptsManager");
        SwitchesManager = $injector.get("SwitchesManager");
        ResourcePoolsManager = $injector.get("ResourcePoolsManager");
    }));

    // Mock the websocket connection to the region
    var RegionConnection, webSocket;
    beforeEach(inject(function($injector) {
        RegionConnection = $injector.get("RegionConnection");
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

        if($location.path() === '') {
            $location.path("/machines");
        }

        // Start the connection so a valid websocket is created in the
        // RegionConnection.
        RegionConnection.connect("");

        // Create the controller.
        var controller = $controller("NodesListController", {
            $q: $q,
            $scope: $scope,
            $rootScope: $rootScope,
            $routeParams: $routeParams,
            $location: $location,
            MachinesManager: MachinesManager,
            DevicesManager: DevicesManager,
            ControllersManager: ControllersManager,
            GeneralManager: GeneralManager,
            ZonesManager: ZonesManager,
            UsersManager: UsersManager,
            ServicesManager: ServicesManager,
            ManagerHelperService: ManagerHelperService,
            SearchService: SearchService,
            ScriptsManager: ScriptsManager,
            SwitchesManager: SwitchesManager
        });

        // Since the osSelection directive is not used in this test the
        // osSelection item on the model needs to have $reset function added
        // because it will be called throughout many of the tests.
        $scope.tabs.machines.osSelection.$reset = jasmine.createSpy("$reset");

        return controller;
    }

    // Makes a fake node/device.
    function makeObject(tab) {
        if (tab === 'machines') {
            var node = {
                system_id: makeName("system_id"),
                $selected: false
            };
            MachinesManager._items.push(node);
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
        else if (tab === 'controllers') {
            var controller = {
                system_id: makeName("system_id"),
                $selected: false
            };
            ControllersManager._items.push(controller);
            return controller;
        }
        else if (tab === 'switches') {
            var network_switch = {
                system_id: makeName("system_id"),
                $selected: false
            };
            SwitchesManager._items.push(network_switch);
            return network_switch;
        }
        return null;
    }

    describe("isSuperUser", function() {
        it("returns true if the user is a superuser", function() {
            var controller = makeController();
            spyOn(UsersManager, "getAuthUser").and.returnValue(
                { is_superuser: true });
            expect($scope.isSuperUser()).toBe(true);
        });

        it("returns false if the user is not a superuser", function() {
            var controller = makeController();
            spyOn(UsersManager, "getAuthUser").and.returnValue(
                { is_superuser: false });
            expect($scope.isSuperUser()).toBe(false);
        });
    });

    it("sets title and page on $rootScope", function() {
        var controller = makeController();
        expect($rootScope.title).toBe("Machines");
        expect($rootScope.page).toBe("machines");
    });

    it("sets initial values on $scope", function() {
        // tab-independent variables.
        var controller = makeController();
        expect($scope.machines).toBe(MachinesManager.getItems());
        expect($scope.devices).toBe(DevicesManager.getItems());
        expect($scope.pools).toBe(ResourcePoolsManager.getItems());
        expect($scope.controllers).toBe(ControllersManager.getItems());
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

    it("saves current filters for nodes and devices when scope destroyed",
        function() {
            var controller = makeController();
            var nodesFilters = {};
            var devicesFilters = {};
            var controllersFilters = {};
            var switchesFilters = {};
            $scope.tabs.machines.filters = nodesFilters;
            $scope.tabs.devices.filters = devicesFilters;
            $scope.tabs.controllers.filters = controllersFilters;
            $scope.tabs.switches.filters = switchesFilters;
            $scope.$destroy();
            expect(SearchService.retrieveFilters("machines")).toBe(
                nodesFilters);
            expect(SearchService.retrieveFilters("devices")).toBe(
                devicesFilters);
            expect(SearchService.retrieveFilters("controllers")).toBe(
                controllersFilters);
            expect(SearchService.retrieveFilters("switches")).toBe(
                switchesFilters);
        });

    angular.forEach(
        ["machines", "devices", "controllers", "switches"],
        function(node_type) {
            it("calls loadManagers for " + node_type, function() {
                $location.path("/" + node_type);
                var controller = makeController();
                var page_managers = [$scope.tabs[node_type].manager];
                if($scope.currentpage === "machines" ||
                        $scope.currentpage === "controllers") {
                    page_managers.push(ScriptsManager);
                }
                expect(
                    ManagerHelperService.loadManagers
                ).toHaveBeenCalledWith(
                    $scope, [GeneralManager, ZonesManager, UsersManager,
                    ResourcePoolsManager,
                    ServicesManager].concat(page_managers));
            });
        });

    it("sets loading to false with loadManagers resolves", function() {
        var defer = $q.defer();
        var controller = makeController(defer);
        defer.resolve();
        $rootScope.$digest();
        expect($scope.loading).toBe(false);
    });

    it("sets nodes search from SearchService",
        function() {
            var query = makeName("query");
            SearchService.storeFilters(
                "machines", SearchService.getCurrentFilters(query));
            var controller = makeController();
            expect($scope.tabs.machines.search).toBe(query);
        });

    it("sets devices search from SearchService",
        function() {
            var query = makeName("query");
            SearchService.storeFilters(
                "devices", SearchService.getCurrentFilters(query));
            var controller = makeController();
            expect($scope.tabs.devices.search).toBe(query);
        });

    it("sets controllers search from SearchService",
        function() {
            var query = makeName("query");
            SearchService.storeFilters(
                "controllers", SearchService.getCurrentFilters(query));
            var controller = makeController();
            expect($scope.tabs.controllers.search).toBe(query);
        });

    it("sets switches search from SearchService",
        function() {
            var query = makeName("query");
            SearchService.storeFilters(
                "switches", SearchService.getCurrentFilters(query));
            makeController();
            expect($scope.tabs.switches.search).toBe(query);
        });

    it("sets nodes search from $routeParams.query",
        function() {
            var query = makeName("query");
            $routeParams.query = query;
            var controller = makeController();
            expect($scope.tabs.machines.search).toBe(query);
        });

    it("calls updateFilters for nodes if search from $routeParams.query",
        function() {
            var query = makeName("query");
            $routeParams.query = query;
            var controller = makeController();
            expect($scope.tabs.machines.filters._).toEqual([query]);
        });

    it("reloads osinfo on route update", function() {
        var controller = makeController();
        spyOn(GeneralManager, "loadItems").and.returnValue(
            $q.defer().promise);
        $scope.$emit("$routeUpdate");
        expect(GeneralManager.loadItems).toHaveBeenCalledWith(["osinfo"]);
    });

    describe("toggleTab", function() {

        it("sets $rootScope.title", function() {
            var controller = makeController();
            $scope.toggleTab('devices');
            expect($rootScope.title).toBe($scope.tabs.devices.pagetitle);
            $scope.toggleTab('machines');
            expect($rootScope.title).toBe($scope.tabs.machines.pagetitle);
            $scope.toggleTab('switches');
            expect($rootScope.title).toBe($scope.tabs.switches.pagetitle);
        });

        it("sets currentpage and $rootScope.page", function() {
            var controller = makeController();
            $scope.toggleTab('devices');
            expect($scope.currentpage).toBe('devices');
            expect($rootScope.page).toBe('devices');
            $scope.toggleTab('machines');
            expect($scope.currentpage).toBe('machines');
            expect($rootScope.page).toBe('machines');
            $scope.toggleTab('switches');
            expect($scope.currentpage).toBe('switches');
            expect($rootScope.page).toBe('switches');
        });
    });

    angular.forEach(["machines", "devices", "controllers", "switches"],
                    function(tab) {

        describe("tab(" + tab + ")", function() {

            it("sets initial values on $scope", function() {
                // Only controllers tab uses the registerUrl and
                // registerSecret. Set the values before the controller is
                // created. The create will pull the values into the scope.
                var registerUrl, registerSecret;
                if(tab === "controllers") {
                    registerUrl = makeName("url");
                    registerSecret = makeName("secret");
                    MAAS_config = {
                        register_url: registerUrl,
                        register_secret: registerSecret
                    };
                }

                var controller = makeController();
                var tabScope = $scope.tabs[tab];
                expect(tabScope.previous_search).toBe("");
                expect(tabScope.search).toBe("");
                expect(tabScope.searchValid).toBe(true);
                expect(tabScope.selectedItems).toBe(
                    tabScope.manager.getSelectedItems());
                expect(tabScope.metadata).toBe(tabScope.manager.getMetadata());
                expect(tabScope.filters).toEqual(
                    SearchService.getEmptyFilter());
                expect(tabScope.actionOption).toBeNull();

                // Only devices and controllers use the sorting and column
                // as the nodes tab uses the maas-machines-table directive.
                if(tab !== "machines" && tab !== "switches") {
                    expect(tabScope.filtered_items).toEqual([]);
                    expect(tabScope.predicate).toBe("fqdn");
                    expect(tabScope.allViewableChecked).toBe(false);
                    expect(tabScope.column).toBe("fqdn");
                }

                // The controllers page uses a function so it can handle
                // different controller types
                if(tab !== "controllers") {
                    expect(tabScope.takeActionOptions).toEqual([]);
                }
                expect(tabScope.actionErrorCount).toBe(0);
                expect(tabScope.zoneSelection).toBeNull();
                expect(tabScope.poolSelection).toBeNull();

                // Only the nodes tab uses the osSelection and
                // commissionOptions fields.
                if(tab === "machines" || tab === "switches") {
                    expect(tabScope.osSelection.osystem).toBeNull();
                    expect(tabScope.osSelection.release).toBeNull();
                    expect(tabScope.commissionOptions).toEqual({
                        enableSSH: false,
                        skipBMCConfig: false,
                        skipNetworking: false,
                        skipStorage: false,
                        updateFirmware: false,
                        configureHBA: false
                    });
                    expect(tabScope.commissioningSelection).toEqual([]);
                    expect(tabScope.releaseOptions).toEqual({});
                }

                // Only controllers tab uses the registerUrl and
                // registerSecret.
                if(tab === "controllers") {
                    expect(tabScope.registerUrl).toBe(registerUrl);
                    expect(tabScope.registerSecret).toBe(registerSecret);
                }
            });
        });
    });

    angular.forEach(["machines", "devices", "controllers", "switches"],
                    function(tab) {

        describe("tab(" + tab + ")", function() {

            it("resets search matches previous search and empty filtered_items",
                function() {
                    var controller = makeController();
                    var tabScope = $scope.tabs[tab];
                    var search = makeName("search");

                    if(tab === 'machines' || tab === 'switches') {
                        // Nodes uses the maas-machines-table directive, so
                        // the interaction is a little different.
                        tabScope.search = "in:(Selected)";
                        tabScope.previous_search = search;
                        $scope.onNodeListingChanged([makeObject(tab)], tab);

                        // Empty the listing search should be reset.
                        tabScope.search = search;
                        $scope.onNodeListingChanged([], tab);
                        expect(tabScope.search).toBe("");
                    } else {
                        // Add item to filtered_items.
                        tabScope.filtered_items.push(makeObject(tab));
                        tabScope.search = "in:(Selected)";
                        tabScope.previous_search = search;
                        $scope.$digest();

                        // Empty the filtered_items, which should clear the
                        // search.
                        tabScope.filtered_items.splice(0, 1);
                        tabScope.search = search;
                        $scope.$digest();
                        expect(tabScope.search).toBe("");
                    }
                });

            it("doesnt reset search matches if not empty filtered_items",
                function() {
                    var controller = makeController();
                    var tabScope = $scope.tabs[tab];
                    var search = makeName("search");
                    var nodes = [makeObject(tab), makeObject(tab)];

                    if(tab === 'machines' || tab === 'switches') {
                        $scope.onNodeListingChanged(nodes, tab);
                    } else {
                        // Add item to filtered_items.
                        tabScope.filtered_items.push(nodes[0], nodes[1]);
                    }
                    tabScope.search = "in:(Selected)";
                    tabScope.previous_search = search;
                    $scope.$digest();

                    // Remove one item from filtered_items, which should not
                    // clear the search.
                    if(tab === 'machines' || tab === 'switches') {
                        $scope.onNodeListingChanged([nodes[1]], tab);
                    } else {
                        tabScope.filtered_items.splice(0, 1);
                    }
                    tabScope.search = search;
                    $scope.$digest();
                    expect(tabScope.search).toBe(search);
                });

            it("doesnt reset search when previous search doesnt match",
                function() {
                    var controller = makeController();
                    var tabScope = $scope.tabs[tab];
                    var nodes = [makeObject(tab), makeObject(tab)];

                    if(tab === 'machines' || tab === 'switches') {
                        $scope.onNodeListingChanged(nodes, tab);
                    } else {
                        // Add item to filtered_items.
                        tabScope.filtered_items.push(nodes[0]);
                    }

                    tabScope.search = "in:(Selected)";
                    tabScope.previous_search = makeName("search");
                    $scope.$digest();

                    // Empty the filtered_items, but change the search which
                    // should stop the search from being reset.
                    if(tab === 'machines' || tab === 'switches') {
                        $scope.onNodeListingChanged([nodes[1]], tab);
                    } else {
                        tabScope.filtered_items.splice(0, 1);
                    }
                    var search = makeName("search");
                    tabScope.search = search;
                    $scope.$digest();
                    expect(tabScope.search).toBe(search);
                });
        });
    });

    angular.forEach(["machines", "devices", "controllers", "switches"],
                     function(tab) {

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
        });
    });

    angular.forEach(["machines", "switches"], function(tab) {

        describe("tab(" + tab + ")", function() {

            describe("toggleChecked", function() {

                var controller, object, tabObj;
                beforeEach(function() {
                    controller = makeController();
                    object = makeObject(tab);
                    tabObj = $scope.tabs[tab];
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
                    tabObj.manager.selectItem(object.system_id);
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
                    tabObj.manager.selectItem(object1.system_id);
                    tabObj.manager.selectItem(object2.system_id);
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
        });
    });

    angular.forEach(["devices", "controllers"], function(tab) {

        describe("tab(" + tab + ")", function() {

            describe("toggleChecked", function() {

                var controller, object, tabObj;
                beforeEach(function() {
                    controller = makeController();
                    object = makeObject(tab);
                    tabObj = $scope.tabs[tab];
                    $scope.tabs.devices.filtered_items = $scope.devices;
                    $scope.tabs.controllers.filtered_items = $scope.controllers;
                    $scope.tabs.switches.filtered_items = $scope.switches;
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
                    $scope.tabs.devices.filtered_items = $scope.devices;
                    $scope.tabs.controllers.filtered_items = $scope.controllers;
                    $scope.tabs.switches.filtered_items = $scope.switches;
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
        });
    });

    angular.forEach(["machines", "devices", "controllers", "switches"],
                    function(tab) {

        describe("tab(" + tab + ")", function() {

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

                it("does nothing if actionOption", function() {
                    var controller = makeController();
                    $scope.tabs[tab].actionOption = {};

                    var filters = { _: [], "in": ["Selected"] };
                    $scope.tabs[tab].filters = filters;
                    $scope.toggleFilter("hostname", "test", tab);
                    expect($scope.tabs[tab].filters).toEqual(filters);
                });

                it("calls SearchService.toggleFilter", function() {
                    var controller = makeController();
                    spyOn(SearchService, "toggleFilter").and.returnValue(
                        SearchService.getEmptyFilter());
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
                    expect($scope.tabs[tab].search).toBe("hostname:(=test)");
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
                            $scope.tabs[tab].filters).toEqual(
                                SearchService.getEmptyFilter());
                        expect($scope.tabs[tab].searchValid).toBe(false);
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
                    $scope.tabs.machines.actionOption = { name: "start" };
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

    angular.forEach(["machines", "devices", "controllers", "switches"],
                    function(tab) {

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

                it("calls hide on addHardwareScope", function() {
                    var controller;
                    if (tab === 'machines') {
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

                it("clears search if in:selected (controller)", function() {
                    var controller = makeController();
                    $scope.tabs.controllers.search = "in:(Selected)";
                    $scope.actionCancel('controllers');
                    expect($scope.tabs.controllers.search).toBe("");
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

                it("supports pluralization of names based on tab", function() {
                    var singulars = {
                        'machines': 'machine',
                        'switches': 'switch',
                        'devices': 'device',
                        'controllers': 'controller',
                    };
                    var controller = makeController();
                    expect($scope.pluralize(tab)).toEqual(singulars[tab]);
                    $scope.tabs[tab].selectedItems.length = 2;
                    expect($scope.pluralize(tab)).toEqual(tab);
                });

                it("resets actionProgress", function() {
                    var controller = makeController();
                    $scope.tabs[tab].actionProgress.total = makeInteger(0, 10);
                    $scope.tabs[tab].actionProgress.completed =
                        makeInteger(0, 10);
                    $scope.tabs[tab].actionProgress.errors[makeName("error")] =
                        [{}];
                    $scope.tabs[tab].actionProgress.showing_confirmation =
                        true;
                    $scope.tabs[tab].actionProgress.affected_nodes =
                        makeInteger(0, 10);
                    $scope.actionCancel(tab);
                    expect($scope.tabs[tab].actionProgress.total).toBe(0);
                    expect($scope.tabs[tab].actionProgress.completed).toBe(0);
                    expect($scope.tabs[tab].actionProgress.errors).toEqual({});
                    expect($scope.tabs[
                        tab].actionProgress.showing_confirmation).toBe(false);
                    expect($scope.tabs[
                        tab].actionProgress.affected_nodes).toBe(0);
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
                        $scope.$digest();
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
                    $scope.$digest();
                    expect(spy).toHaveBeenCalledWith(
                        object, "start", {});
                });

                it("calls unselectItem after failed action", function() {
                    var controller = makeController();
                    var object = makeObject(tab);
                    object.action_failed = false;
                    spyOn(
                        $scope, 'hasActionsFailed').and.returnValue(true);
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

                it("keeps items selected after success", function() {
                    var controller = makeController();
                    var object = makeObject(tab);
                    spyOn(
                        $scope, 'hasActionsFailed').and.returnValue(false);
                    spyOn(
                        $scope, 'hasActionsInProgress').and.returnValue(false);
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
                    expect($scope.tabs[tab].selectedItems).toEqual([object]);
                });

                it("increments actionProgress.completed after action complete",
                    function() {
                        var controller = makeController();
                        var object = makeObject(tab);
                        var defer = $q.defer();
                        spyOn(
                            $scope.tabs[tab].manager,
                            "performAction").and.returnValue(defer.promise);
                        spyOn(
                            $scope, 'hasActionsFailed').and.returnValue(true);
                        $scope.tabs[tab].actionOption = { name: "start" };
                        $scope.tabs[tab].selectedItems = [object];
                        $scope.actionGo(tab);
                        defer.resolve();
                        $scope.$digest();
                        expect(
                            $scope.tabs[tab].actionProgress.completed).toBe(1);
                    });

                it("set search to in:(Selected) search after complete",
                    function() {
                    var controller = makeController();
                    var defer = $q.defer();
                    spyOn(
                        $scope.tabs[tab].manager,
                        "performAction").and.returnValue(defer.promise);
                    spyOn(
                            $scope, 'hasActionsFailed').and.returnValue(false);
                    spyOn(
                        $scope, 'hasActionsInProgress').and.returnValue(false);
                    var object = makeObject(tab);
                    $scope.tabs[tab].manager._items.push(object);
                    $scope.tabs[tab].manager._selectedItems.push(object);
                    $scope.tabs[tab].previous_search = makeName("search");
                    $scope.tabs[tab].search = "in:(Selected)";
                    $scope.tabs[tab].actionOption = { name: "start" };
                    $scope.tabs[tab].filtered_items = [makeObject(tab)];
                    $scope.actionGo(tab);
                    defer.resolve();
                    $scope.$digest();
                    expect($scope.tabs[tab].search).toBe("in:(Selected)");
                });

                it("clears action option when complete", function() {
                    var controller = makeController();
                    var defer = $q.defer();
                    spyOn(
                        $scope.tabs[tab].manager,
                        "performAction").and.returnValue(defer.promise);
                    spyOn(
                        $scope, 'hasActionsFailed').and.returnValue(false);
                    spyOn(
                        $scope, 'hasActionsInProgress').and.returnValue(false);
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
                        $scope.$digest();
                        expect(spy).toHaveBeenCalledWith(
                            object, "set-zone", { zone_id: 1 });
                });

                it("clears action option when successfully complete",
                        function() {
                    var controller = makeController();
                    var defer = $q.defer();
                    spyOn(
                        $scope.tabs[tab].manager,
                        "performAction").and.returnValue(defer.promise);
                    spyOn(
                        $scope, 'hasActionsFailed').and.returnValue(false);
                    spyOn(
                        $scope, 'hasActionsInProgress').and.returnValue(false);
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

            describe("actionSetPool", function () {

                it("calls performAction with pool",
                    function() {
                        var controller = makeController();
                        var spy = spyOn(
                            $scope.tabs[tab].manager,
                            "performAction").and.returnValue(
                            $q.defer().promise);
                        var object = makeObject(tab);
                        var tabScope = $scope.tabs[tab];
                        tabScope.actionOption = { name: "set-pool" };
                        tabScope.selectedItems = [object];
                        tabScope.poolAction = 'select-pool';
                        tabScope.poolSelection = { id: 1 };
                        $scope.actionGo(tab);
                        $scope.$digest();
                        expect(spy).toHaveBeenCalledWith(
                            object, "set-pool", { pool_id: 1 });
                });

                it("calls performAction with new pool data",
                    function() {
                        var controller = makeController();
                        var createDefer = $q.defer();
                        var createSpy = spyOn(
                            ResourcePoolsManager,
                            "createItem").and.returnValue(
                            createDefer.promise);
                        var performSpy = spyOn(
                            $scope.tabs[tab].manager,
                            "performAction").and.returnValue(
                            $q.defer().promise);
                        var object = makeObject(tab);
                        var newPoolData = {
                            name: 'my-pool',
                            description: 'desc',
                        };
                        var tabScope = $scope.tabs[tab];
                        tabScope.actionOption = { name: "set-pool" };
                        tabScope.selectedItems = [object];
                        tabScope.poolSelection = null;
                        tabScope.poolAction = 'create-pool';
                        tabScope.newPool = newPoolData;
                        $scope.actionGo(tab);
                        createDefer.resolve({id: 84});
                        $scope.$digest();
                        expect(performSpy).toHaveBeenCalledWith(
                            object, "set-pool", {
                                pool_id:84
                            });
                        expect(createSpy).toHaveBeenCalledWith(
                            {name: newPoolData.name});
                });

                it("clears action option when successfully complete",
                        function() {
                    var controller = makeController();
                    var defer = $q.defer();
                    spyOn(
                        $scope.tabs[tab].manager,
                        "performAction").and.returnValue(defer.promise);
                    spyOn(
                        $scope, 'hasActionsFailed').and.returnValue(false);
                    spyOn(
                        $scope, 'hasActionsInProgress').and.returnValue(false);
                    var object = makeObject(tab);
                    $scope.tabs[tab].manager._items.push(object);
                    $scope.tabs[tab].manager._selectedItems.push(object);
                    $scope.tabs[tab].actionOption = { name: "set-pool" };
                    $scope.tabs[tab].poolSelection = { id: 1 };
                    $scope.actionGo(tab);
                    defer.resolve();
                    $scope.$digest();
                    expect($scope.tabs[tab].poolSelection).toBeNull();
                });
            });
        });
    });

    describe("tab(nodes)", function() {

        describe("actionGo", function() {

            it("calls performAction with osystem and distro_series",
                function() {
                    var controller = makeController();
                    var object = makeObject("machines");
                    var spy = spyOn(
                        $scope.tabs.machines.manager,
                        "performAction").and.returnValue(
                        $q.defer().promise);
                    $scope.tabs.machines.actionOption = { name: "deploy" };
                    $scope.tabs.machines.selectedItems = [object];
                    $scope.tabs.machines.osSelection.osystem = "ubuntu";
                    $scope.tabs.machines.osSelection.release = "ubuntu/trusty";
                    $scope.actionGo("machines");
                    $scope.$digest();
                    expect(spy).toHaveBeenCalledWith(
                        object, "deploy", {
                            osystem: "ubuntu",
                            distro_series: "trusty",
                            install_kvm: false
                        });
            });

            it("calls performAction with install_kvm",
                function() {
                    var controller = makeController();
                    var object = makeObject("machines");
                    var spy = spyOn(
                        $scope.tabs.machines.manager,
                        "performAction").and.returnValue(
                        $q.defer().promise);
                    $scope.tabs.machines.actionOption = {name: "deploy"};
                    $scope.tabs.machines.selectedItems = [object];
                    $scope.tabs.machines.osSelection.osystem = "debian";
                    $scope.tabs.machines.osSelection.release = "etch";
                    $scope.tabs.machines.deployOptions.installKVM = true;
                    $scope.actionGo("machines");
                    $scope.$digest();
                    // When deploying KVM, coerce the distro to ubuntu/bionic.
                    expect(spy).toHaveBeenCalledWith(
                        object, "deploy", {
                            osystem: "ubuntu",
                            distro_series: "bionic",
                            install_kvm: true
                        });
            });

            it("clears selected os and release when successfully complete",
                    function() {
                var controller = makeController();
                var defer = $q.defer();
                spyOn(
                    MachinesManager,
                    "performAction").and.returnValue(defer.promise);
                spyOn(
                    $scope, 'hasActionsFailed').and.returnValue(false);
                spyOn(
                    $scope, 'hasActionsInProgress').and.returnValue(false);
                var object = makeObject("machines");
                MachinesManager._items.push(object);
                MachinesManager._selectedItems.push(object);
                $scope.tabs.machines.actionOption = { name: "deploy" };
                $scope.tabs.machines.osSelection.osystem = "ubuntu";
                $scope.tabs.machines.osSelection.release = "ubuntu/trusty";
                $scope.actionGo("machines");
                defer.resolve();
                $scope.$digest();
                expect(
                    $scope.tabs.machines.osSelection.$reset
                ).toHaveBeenCalled();
            });

            it("calls performAction with commissionOptions",
                function() {
                    var controller = makeController();
                    var object = makeObject("machines");
                    var spy = spyOn(
                        $scope.tabs.machines.manager,
                        "performAction").and.returnValue(
                            $q.defer().promise);
                    var commissioning_scripts_ids = [
                        makeInteger(0, 100), makeInteger(0, 100)];
                    var testing_scripts_ids = [
                        makeInteger(0, 100), makeInteger(0, 100)];
                    $scope.tabs.machines.actionOption = { name: "commission" };
                    $scope.tabs.machines.selectedItems = [object];
                    $scope.tabs.machines.commissionOptions.enableSSH = true;
                    $scope.tabs.machines.commissionOptions.skipBMCConfig =
                        false;
                    $scope.tabs.machines.commissionOptions.skipNetworking =
                        false;
                    $scope.tabs.machines.commissionOptions.skipStorage = false;
                    $scope.tabs.machines.commissionOptions.updateFirmware =
                        true;
                    $scope.tabs.machines.commissionOptions.configureHBA = true;
                    $scope.tabs.machines.commissioningSelection = [];
                    angular.forEach(
                            commissioning_scripts_ids, function(script_id) {
                        $scope.tabs.machines.commissioningSelection.push({
                            id: script_id,
                            name: makeName("script_name")
                        });
                    });
                    $scope.tabs.machines.testSelection = [];
                    angular.forEach(testing_scripts_ids, function(script_id) {
                        $scope.tabs.machines.testSelection.push({
                            id: script_id,
                            name: makeName("script_name")
                        });
                    });
                    $scope.actionGo("machines");
                    $scope.$digest();
                    expect(spy).toHaveBeenCalledWith(
                        object, "commission", {
                            enable_ssh: true,
                            skip_bmc_config: false,
                            skip_networking: false,
                            skip_storage: false,
                            commissioning_scripts:
                                commissioning_scripts_ids.concat([
                                    'update_firmware', 'configure_hba']),
                            testing_scripts: testing_scripts_ids
                        });
            });

            it("calls performAction with testOptions",
                function() {
                    var controller = makeController();
                    var object = makeObject("machines");
                    var spy = spyOn(
                        $scope.tabs.machines.manager,
                        "performAction").and.returnValue(
                            $q.defer().promise);
                    var testing_script_ids = [
                        makeInteger(0, 100), makeInteger(0, 100)];
                    $scope.tabs.machines.actionOption = { name: "test" };
                    $scope.tabs.machines.selectedItems = [object];
                    $scope.tabs.machines.commissionOptions.enableSSH = true;
                    $scope.tabs.machines.testSelection = [];
                    angular.forEach(testing_script_ids, function(script_id) {
                        $scope.tabs.machines.testSelection.push({
                            id: script_id,
                            name: makeName("script_name")
                        });
                    });
                    $scope.actionGo("machines");
                    $scope.$digest();
                    expect(spy).toHaveBeenCalledWith(
                        object, "test", {
                            enable_ssh: true,
                            testing_scripts: testing_script_ids
                        });
            });

            it("sets showing_confirmation with testOptions",
                function() {
                    var controller = makeController();
                    var object = makeObject("machines");
                    object.status_code = 6;
                    var spy = spyOn(
                        $scope.tabs.machines.manager,
                        "performAction").and.returnValue(
                            $q.defer().promise);
                    $scope.tabs.machines.actionOption = { name: "test" };
                    $scope.tabs.machines.selectedItems = [object];
                    $scope.actionGo("machines");
                    expect($scope.tabs[
                        "machines"].actionProgress.showing_confirmation).toBe(
                            true);
                    expect($scope.tabs[
                        "machines"].actionProgress.affected_nodes).toBe(1);
                    expect(spy).not.toHaveBeenCalled();
            });

            it("calls performAction with releaseOptions",
                function() {
                    var controller = makeController();
                    var object = makeObject("machines");
                    var spy = spyOn(
                        $scope.tabs.machines.manager,
                        "performAction").and.returnValue(
                        $q.defer().promise);
                    var secureErase = makeName("secureErase");
                    var quickErase = makeName("quickErase");
                    $scope.tabs.machines.actionOption = { name: "release" };
                    $scope.tabs.machines.selectedItems = [object];
                    $scope.tabs.machines.releaseOptions.erase = true;
                    $scope.tabs.machines.releaseOptions.secureErase =
                        secureErase;
                    $scope.tabs.machines.releaseOptions.quickErase =
                        quickErase;
                    $scope.actionGo("machines");
                    $scope.$digest();
                    expect(spy).toHaveBeenCalledWith(
                        object, "release", {
                            erase: true,
                            secure_erase: secureErase,
                            quick_erase: quickErase
                        });
            });

            it("clears commissionOptions when successfully complete",
                    function() {
                var controller = makeController();
                var defer = $q.defer();
                spyOn(
                    MachinesManager,
                    "performAction").and.returnValue(defer.promise);
                spyOn(
                    $scope, 'hasActionsFailed').and.returnValue(false);
                spyOn(
                    $scope, 'hasActionsInProgress').and.returnValue(false);
                var object = makeObject("machines");
                MachinesManager._items.push(object);
                MachinesManager._selectedItems.push(object);
                $scope.tabs.machines.actionOption = { name: "commission" };
                $scope.tabs.machines.commissionOptions.enableSSH = true;
                $scope.tabs.machines.commissionOptions.skipNetworking = true;
                $scope.tabs.machines.commissionOptions.skipStorage = true;
                $scope.tabs.machines.commissionOptions.updateFirmware = true;
                $scope.tabs.machines.commissionOptions.configureHBA = true;
                $scope.tabs.machines.commissioningSelection = [{
                    id: makeInteger(0, 100),
                    name: makeName("script_name")
                }];
                $scope.tabs.machines.testSelection = [{
                    id: makeInteger(0, 100),
                    name: makeName("script_name")
                }];

                $scope.actionGo("machines");
                defer.resolve();
                $scope.$digest();
                expect($scope.tabs.machines.commissionOptions).toEqual({
                    enableSSH: false,
                    skipBMCConfig: false,
                    skipNetworking: false,
                    skipStorage: false,
                    updateFirmware: false,
                    configureHBA: false
                });
                expect($scope.tabs.machines.commissioningSelection).toEqual([]);
                expect($scope.tabs.machines.testSelection).toEqual([]);
            });
        });
    });

    describe('tab(pools)', function() {
        it('sets the actionOption when addPool is called', function() {
            makeController();
            var poolsTab = $scope.tabs.pools;
            expect(poolsTab.actionOption).toBe(false);
            poolsTab.addPool();
            expect(poolsTab.actionOption).toBe(true);
        });

        it('resets actionOption and newPool when cancelAddPool is called',
           function() {
            makeController();
            var poolsTab = $scope.tabs.pools;
            poolsTab.addPool();
            poolsTab.newPool = {'name': 'mypool'},
            poolsTab.cancelAddPool();
            expect(poolsTab.actionOption).toBe(false);
            expect(poolsTab.newPool).toEqual({});
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

    describe("hasCustomCommissioningScripts", function() {
        it("returns true with custom commissioning scripts", function() {
            var controller = makeController();
            ScriptsManager._items.push({script_type: 0});
            expect($scope.hasCustomCommissioningScripts()).toBe(true);
        });
        it("returns false without custom commissioning scripts", function() {
            var controller = makeController();
            expect($scope.hasCustomCommissioningScripts()).toBe(false);
        });
    });

    describe("showswitches", function() {
        it("is true if switches=on", function() {
            $routeParams.switches = "on";
            var controller = makeController();
            expect($scope.showswitches).toBe(true);
        });
        it("is false if switches=off", function() {
            $routeParams.switches = "off";
            var controller = makeController();
            expect($scope.showswitches).toBe(false);
        });
        it("is false if switches is not specified", function() {
            var controller = makeController();
            expect($scope.showswitches).toBe(false);
        });
    });

    describe("resource pools listing", function() {
        it("sets active target with initiatePoolAction", function() {
            makeController();
            var tab = $scope.tabs.pools;
            var pool = {id: 1, name: 'foo'};
            tab.initiatePoolAction(pool, 'action');
            expect(tab.activeTargetAction).toEqual('action');
            expect(tab.activeTarget).toEqual(pool);
        });

        it("unsets target with cancelPoolAction", function() {
            makeController();
            var tab = $scope.tabs.pools;
            tab.initiatePoolAction({id: 1, name: 'foo'}, 'action');
            tab.cancelPoolAction();
            expect(tab.activeTargetAction).toBe(null);
            expect(tab.activeTarget).toBe(null);
        });

        it("reports isPoolAction false when no action", function() {
            makeController();
            var tab = $scope.tabs.pools;
            var pool = {id: 1, name: 'foo'};
            expect(tab.isPoolAction(pool, 'action')).toBe(false);
        });

        it("reports isPoolAction true when action on the pool", function() {
            makeController();
            var tab = $scope.tabs.pools;
            var pool = {id: 1, name: 'foo'};
            tab.initiatePoolAction(pool, 'action');
            expect(tab.isPoolAction(pool, 'action')).toBe(true);
        });

        it("reports isPoolAction true with any action", function() {
            makeController();
            var tab = $scope.tabs.pools;
            var pool = {id: 1, name: 'foo'};
            tab.initiatePoolAction(pool, 'action');
            expect(tab.isPoolAction(pool)).toBe(true);
        });

        it("reports isPoolAction false when action on other pool", function() {
            makeController();
            var tab = $scope.tabs.pools;
            var pool1 = {id: 1, name: 'foo'};
            var pool2 = {id: 2, name: 'bar'};
            tab.initiatePoolAction(pool1, 'action');
            expect(tab.isPoolAction(pool2, 'action')).toBe(false);
        });

        it("reports isPoolAction false when different action", function() {
            makeController();
            var tab = $scope.tabs.pools;
            var pool = {id: 1, name: 'foo'};
            tab.initiatePoolAction(pool, 'action');
            expect(tab.isPoolAction(pool, 'other-action')).toBe(false);
        });

        it("reports isDefaultPool false", function() {
            makeController();
            var tab = $scope.tabs.pools;
            var pool = {id: 1, name: 'foo'};
            expect(tab.isDefaultPool(pool)).toBe(false);
        });

        it("reports isDefaultPool true", function() {
            makeController();
            var tab = $scope.tabs.pools;
            var pool = {id: 0, name: 'foo'};
            expect(tab.isDefaultPool(pool)).toBe(true);
        });

        it("switches to the machine tab with pool filter", function() {
            makeController();
            var machinesTab = $scope.tabs.machines;
            var pool = {id: 10, name: 'foo'};
            $scope.tabs.pools.goToPoolMachines(pool);
            expect(machinesTab.search).toEqual('pool:(=foo)');
            expect($location.path()).toEqual('/machines');
        });
    });

    describe("unselectImpossibleNodes", function() {
        it("unselects machines for which an action cannot be done", function() {
            makeController();
            var machinePossible = makeObject('machines');
            var machineImpossible = makeObject('machines');
            var tab = $scope.tabs.machines;

            tab.actionOption = { name: 'commission' };
            machinePossible.actions = ['commission'];
            machineImpossible.actions = ['deploy'];
            MachinesManager._items.push(machinePossible, machineImpossible);
            MachinesManager._selectedItems.push(
                machinePossible, machineImpossible
            );

            $scope.unselectImpossibleNodes('machines');

            expect(tab.selectedItems).toEqual([machinePossible]);
        });
    });
});
