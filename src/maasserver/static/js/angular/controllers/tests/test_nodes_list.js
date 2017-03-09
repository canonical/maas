/* Copyright 2015-2017 Canonical Ltd.  This software is licensed under the
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
    var MachinesManager, DevicesManager, ControllersManager, GeneralManager;
    var ZonesManager, UsersManager, ServicesManager;
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

        // Start the connection so a valid websocket is created in the
        // RegionConnection.
        RegionConnection.connect("");

        // Create the controller.
        var controller = $controller("NodesListController", {
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
            ScriptsManager: ScriptsManager
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

    describe("getReleaseTitle", function() {
        it("returns release title from osinfo", function() {
            var controller = makeController();
            $scope.osinfo = {
                releases: [
                    ['ubuntu/xenial', 'Ubuntu Xenial']
                ]
            };
            expect($scope.getReleaseTitle('ubuntu/xenial')).toBe(
                'Ubuntu Xenial');
        });

        it("returns release name when not in osinfo", function() {
            var controller = makeController();
            $scope.osinfo = {
                releases: []
            };
            expect($scope.getReleaseTitle('ubuntu/xenial')).toBe(
                'ubuntu/xenial');
        });
    });

    describe("getStatusText", function() {
        it("returns status text when not deployed or deploying", function() {
            var controller = makeController();
            var node = {
                status: makeName("status")
            };

            expect($scope.getStatusText(node)).toBe(node.status);
        });

        it("returns status with release title when deploying", function() {
            var controller = makeController();
            var node = {
                status: "Deploying",
                osystem: "ubuntu",
                distro_series: "xenial"
            };
            $scope.osinfo = {
                releases: [
                    ['ubuntu/xenial', 'Ubuntu Xenial']
                ]
            };
            expect($scope.getStatusText(node)).toBe(
                'Deploying Ubuntu Xenial');
        });

        it("returns release title when deployed", function() {
            var controller = makeController();
            var node = {
                status: "Deployed",
                osystem: "ubuntu",
                distro_series: "xenial"
            };
            $scope.osinfo = {
                releases: [
                    ['ubuntu/xenial', 'Ubuntu Xenial']
                ]
            };
            expect($scope.getStatusText(node)).toBe(
                'Ubuntu Xenial');
        });

        it("returns release title without codename when deployed", function() {
            var controller = makeController();
            var node = {
                status: "Deployed",
                osystem: "ubuntu",
                distro_series: "xenial"
            };
            $scope.osinfo = {
                releases: [
                    ['ubuntu/xenial', 'Ubuntu 16.04 LTS "Xenial Xerus"']
                ]
            };
            expect($scope.getStatusText(node)).toBe(
                'Ubuntu 16.04 LTS');
        });
    });

    it("sets title and page on $rootScope", function() {
        var controller = makeController();
        expect($rootScope.title).toBe("Machines");
        expect($rootScope.page).toBe("nodes");
    });

    it("sets initial values on $scope", function() {
        // tab-independent variables.
        var controller = makeController();
        expect($scope.nodes).toBe(MachinesManager.getItems());
        expect($scope.devices).toBe(DevicesManager.getItems());
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

    it("calls startPolling when scope created", function() {
        spyOn(GeneralManager, "startPolling");
        var controller = makeController();
        expect(GeneralManager.startPolling).toHaveBeenCalledWith(
            "osinfo");
    });

    it("calls stopPolling when scope destroyed", function() {
        var controller = makeController();
        spyOn(GeneralManager, "stopPolling");
        $scope.$destroy();
        expect(GeneralManager.stopPolling).toHaveBeenCalledWith(
            "osinfo");
    });

    it("saves current filters for nodes and devices when scope destroyed",
        function() {
            var controller = makeController();
            var nodesFilters = {};
            var devicesFilters = {};
            var controllersFilters = {};
            $scope.tabs.nodes.filters = nodesFilters;
            $scope.tabs.devices.filters = devicesFilters;
            $scope.tabs.controllers.filters = controllersFilters;
            $scope.$destroy();
            expect(SearchService.retrieveFilters("nodes")).toBe(nodesFilters);
            expect(SearchService.retrieveFilters("devices")).toBe(
                devicesFilters);
            expect(SearchService.retrieveFilters("controllers")).toBe(
                controllersFilters);
        });

    it("calls loadManagers with MachinesManager, DevicesManager," +
        "ControllersManager, GeneralManager, UsersManager",
        function() {
            var controller = makeController();
            expect(ManagerHelperService.loadManagers).toHaveBeenCalledWith(
                $scope, [MachinesManager, DevicesManager, ControllersManager,
                GeneralManager, ZonesManager, UsersManager, ServicesManager,
                ScriptsManager]);
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
                "nodes", SearchService.getCurrentFilters(query));
            var controller = makeController();
            expect($scope.tabs.nodes.search).toBe(query);
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

        it("calls $location search", function() {
            var controller = makeController();
            spyOn($location, "search");
            $scope.toggleTab('nodes');
            expect($location.search).toHaveBeenCalledWith('tab', 'nodes');
        });
    });

    angular.forEach(["nodes", "devices", "controllers"], function(tab) {

        describe("tab(" + tab + ")", function() {

            var manager;
            beforeEach(function() {
                if(tab === "nodes") {
                    manager = MachinesManager;
                } else if(tab === "devices") {
                    manager = DevicesManager;
                } else if(tab === "controllers") {
                    manager = ControllersManager;
                } else {
                    throw new Error("Unknown manager for tab: " + tab);
                }
            });

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
                expect(tabScope.filtered_items).toEqual([]);
                expect(tabScope.predicate).toBe("fqdn");
                expect(tabScope.allViewableChecked).toBe(false);
                expect(tabScope.selectedItems).toBe(
                    tabScope.manager.getSelectedItems());
                expect(tabScope.metadata).toBe(tabScope.manager.getMetadata());
                expect(tabScope.filters).toEqual(
                    SearchService.getEmptyFilter());
                expect(tabScope.column).toBe("fqdn");
                expect(tabScope.actionOption).toBeNull();
                // The controllers page uses a function so it can handle
                // different controller types
                if(tab !== "controllers") {
                    expect(tabScope.takeActionOptions).toEqual([]);
                }
                expect(tabScope.actionErrorCount).toBe(0);
                expect(tabScope.zoneSelection).toBeNull();

                // Only the nodes tab uses the osSelection and
                // commissionOptions fields.
                if(tab === "nodes") {
                    expect(tabScope.osSelection.osystem).toBeNull();
                    expect(tabScope.osSelection.release).toBeNull();
                    expect(tabScope.commissionOptions).toEqual({
                        enableSSH: false,
                        skipNetworking: false,
                        skipStorage: false
                    });
                    expect(tabScope.releaseOptions).toEqual({});
                }

                // Only controllers tab uses the registerUrl and
                // registerSecret.
                if(tab === "controllers") {
                    expect(tabScope.registerUrl).toBe(registerUrl);
                    expect(tabScope.registerSecret).toBe(registerSecret);
                }
            });

            it("resets search matches previous search and empty filtered_items",
                function() {
                    var controller = makeController();
                    var tabScope = $scope.tabs[tab];
                    var search = makeName("search");

                    // Add item to filtered_items.
                    tabScope.filtered_items.push(makeObject(tab));
                    tabScope.search = "in:(Selected)";
                    tabScope.previous_search = search;
                    $scope.$digest();

                    // Empty the filtered_items, which should clear the search.
                    tabScope.filtered_items.splice(0, 1);
                    tabScope.search = search;
                    $scope.$digest();
                    expect(tabScope.search).toBe("");
                });

            it("doesnt reset search matches if not empty filtered_items",
                function() {
                    var controller = makeController();
                    var tabScope = $scope.tabs[tab];
                    var search = makeName("search");

                    // Add item to filtered_items.
                    tabScope.filtered_items.push(
                        makeObject(tab), makeObject(tab));
                    tabScope.search = "in:(Selected)";
                    tabScope.previous_search = search;
                    $scope.$digest();

                    // Remove one item from filtered_items, which should not
                    // clear the search.
                    tabScope.filtered_items.splice(0, 1);
                    tabScope.search = search;
                    $scope.$digest();
                    expect(tabScope.search).toBe(search);
                });

            it("doesnt reset search when previous search doesnt match",
                function() {
                    var controller = makeController();
                    var tabScope = $scope.tabs[tab];

                    // Add item to filtered_items.
                    tabScope.filtered_items.push(makeObject(tab));
                    tabScope.search = "in:(Selected)";
                    tabScope.previous_search = makeName("search");
                    $scope.$digest();

                    // Empty the filtered_items, but change the search which
                    // should stop the search from being reset.
                    tabScope.filtered_items.splice(0, 1);
                    var search = makeName("search");
                    tabScope.search = search;
                    $scope.$digest();
                    expect(tabScope.search).toBe(search);
                });
        });

    });

    angular.forEach(["nodes", "devices", "controllers"], function(tab) {

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
                    $scope.tabs.controllers.filtered_items = $scope.controllers;
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
                    $scope.tabs.controllers.filtered_items = $scope.controllers;
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

            if(tab === "nodes") {

                // Only used on nodes tab.
                describe("showSpinner", function() {

                    it("returns false/true based on status codes", function() {
                        var STATUSES = [1, 9, 12, 14, 17, 19];
                        var i, controller = makeController();
                        for(i = 0; i < 20; i++) {
                            var node = {
                                status_code: i
                            };
                            var expected = false;
                            if(STATUSES.indexOf(i) > -1) {
                                expected = true;
                            }
                            expect($scope.showSpinner(node)).toBe(expected);
                        }
                    });
                });
            }
        });
    });

    angular.forEach(["nodes", "devices", "controllers"], function(tab) {

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
                var object = makeObject("nodes");
                MachinesManager._items.push(object);
                MachinesManager._selectedItems.push(object);
                $scope.tabs.nodes.actionOption = { name: "deploy" };
                $scope.tabs.nodes.osSelection.osystem = "ubuntu";
                $scope.tabs.nodes.osSelection.release = "ubuntu/trusty";
                $scope.actionGo("nodes");
                defer.resolve();
                $scope.$digest();
                expect($scope.tabs.nodes.osSelection.$reset).toHaveBeenCalled();
            });

            it("calls performAction with commissionOptions",
                function() {
                    var controller = makeController();
                    var object = makeObject("nodes");
                    var spy = spyOn(
                        $scope.tabs.nodes.manager,
                        "performAction").and.returnValue(
                            $q.defer().promise);
                    var commissioning_script_ids = [
                        makeInteger(0, 100), makeInteger(0, 100)];
                    var testing_script_ids = [
                        makeInteger(0, 100), makeInteger(0, 100)];
                    $scope.tabs.nodes.actionOption = { name: "commission" };
                    $scope.tabs.nodes.selectedItems = [object];
                    $scope.tabs.nodes.commissionOptions.enableSSH = true;
                    $scope.tabs.nodes.commissionOptions.skipNetworking = false;
                    $scope.tabs.nodes.commissionOptions.skipStorage = false;
                    $scope.tabs.nodes.commissioningSelection = [];
                    angular.forEach(
                            commissioning_script_ids, function(script_id) {
                        $scope.tabs.nodes.commissioningSelection.push({
                            id: script_id,
                            name: makeName("script_name")
                        });
                    });
                    $scope.tabs.nodes.testSelection = [];
                    angular.forEach(testing_script_ids, function(script_id) {
                        $scope.tabs.nodes.testSelection.push({
                            id: script_id,
                            name: makeName("script_name")
                        });
                    });
                    $scope.actionGo("nodes");
                    expect(spy).toHaveBeenCalledWith(
                        object, "commission", {
                            enable_ssh: true,
                            skip_networking: false,
                            skip_storage: false,
                            commissioning_scripts: commissioning_script_ids,
                            testing_scripts: testing_script_ids
                        });
            });

            it("calls performAction with testOptions",
                function() {
                    var controller = makeController();
                    var object = makeObject("nodes");
                    var spy = spyOn(
                        $scope.tabs.nodes.manager,
                        "performAction").and.returnValue(
                            $q.defer().promise);
                    var testing_script_ids = [
                        makeInteger(0, 100), makeInteger(0, 100)];
                    $scope.tabs.nodes.actionOption = { name: "test" };
                    $scope.tabs.nodes.selectedItems = [object];
                    $scope.tabs.nodes.commissionOptions.enableSSH = true;
                    $scope.tabs.nodes.testSelection = [];
                    angular.forEach(testing_script_ids, function(script_id) {
                        $scope.tabs.nodes.testSelection.push({
                            id: script_id,
                            name: makeName("script_name")
                        });
                    });
                    $scope.actionGo("nodes");
                    expect(spy).toHaveBeenCalledWith(
                        object, "test", {
                            enable_ssh: true,
                            testing_scripts: testing_script_ids
                        });
            });

            it("calls performAction with releaseOptions",
                function() {
                    var controller = makeController();
                    var object = makeObject("nodes");
                    var spy = spyOn(
                        $scope.tabs.nodes.manager,
                        "performAction").and.returnValue(
                        $q.defer().promise);
                    var secureErase = makeName("secureErase");
                    var quickErase = makeName("quickErase");
                    $scope.tabs.nodes.actionOption = { name: "release" };
                    $scope.tabs.nodes.selectedItems = [object];
                    $scope.tabs.nodes.releaseOptions.erase = true;
                    $scope.tabs.nodes.releaseOptions.secureErase = secureErase;
                    $scope.tabs.nodes.releaseOptions.quickErase = quickErase;
                    $scope.actionGo("nodes");
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
                var object = makeObject("nodes");
                MachinesManager._items.push(object);
                MachinesManager._selectedItems.push(object);
                $scope.tabs.nodes.actionOption = { name: "commission" };
                $scope.tabs.nodes.commissionOptions.enableSSH = true;
                $scope.tabs.nodes.commissionOptions.skipNetworking = true;
                $scope.tabs.nodes.commissionOptions.skipStorage = true;
                $scope.tabs.nodes.commissioningSelection = [{
                    id: makeInteger(0, 100),
                    name: makeName("script_name")
                }];
                $scope.tabs.nodes.testSelection = [{
                    id: makeInteger(0, 100),
                    name: makeName("script_name")
                }];

                $scope.actionGo("nodes");
                defer.resolve();
                $scope.$digest();
                expect($scope.tabs.nodes.commissionOptions).toEqual({
                    enableSSH: false,
                    skipNetworking: false,
                    skipStorage: false
                });
                expect($scope.tabs.nodes.commissioningSelection).toEqual([]);
                expect($scope.tabs.nodes.testSelection).toEqual([]);
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
});
