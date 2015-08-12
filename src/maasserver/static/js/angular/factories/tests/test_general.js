/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for GeneralManager.
 */


describe("GeneralManager", function() {

    // Load the MAAS module.
    beforeEach(module("MAAS"));

    // Grab the needed angular pieces.
    var $rootScope, $timeout, $q;
    beforeEach(inject(function($injector) {
        $rootScope = $injector.get("$rootScope");
        $timeout = $injector.get("$timeout");
        $q = $injector.get("$q");
    }));

    // Load the GeneralManager, RegionConnection, and ErrorService factory.
    var GeneralManager, RegionConnection, ErrorService, webSocket;
    beforeEach(inject(function($injector) {
        GeneralManager = $injector.get("GeneralManager");
        RegionConnection = $injector.get("RegionConnection");
        ErrorService = $injector.get("ErrorService");

        // Mock buildSocket so an actual connection is not made.
        webSocket = new MockWebSocket();
        spyOn(RegionConnection, "buildSocket").and.returnValue(webSocket);
    }));

    // Open the connection to the region before each test.
    beforeEach(function(done) {
        RegionConnection.registerHandler("open", function() {
            done();
        });
        RegionConnection.connect("");
    });

    it("sets timeout values", function() {
        expect(GeneralManager._pollTimeout).toBe(10000);
        expect(GeneralManager._pollErrorTimeout).toBe(3000);
        expect(GeneralManager._pollEmptyTimeout).toBe(3000);
    });

    it("autoReload off by default", function() {
        expect(GeneralManager._autoReload).toBe(false);
    });

    it("_data has expected keys", function() {
        expect(Object.keys(GeneralManager._data)).toEqual(
            ["node_actions", "device_actions", "architectures", "hwe_kernels",
             "osinfo"]);
    });

    it("_data.node_actions has correct data", function() {
        var node_actions = GeneralManager._data.node_actions;
        expect(node_actions.method).toBe("general.node_actions");
        expect(node_actions.data).toEqual([]);
        expect(node_actions.loaded).toBe(false);
        expect(node_actions.polling).toBe(false);
        expect(node_actions.nextPromise).toBeNull();
    });

    it("_data.device_actions has correct data", function() {
        var device_actions = GeneralManager._data.device_actions;
        expect(device_actions.method).toBe("general.device_actions");
        expect(device_actions.data).toEqual([]);
        expect(device_actions.loaded).toBe(false);
        expect(device_actions.polling).toBe(false);
        expect(device_actions.nextPromise).toBeNull();
    });

    it("_data.architectures has correct data", function() {
        var architectures = GeneralManager._data.architectures;
        expect(architectures.method).toBe("general.architectures");
        expect(architectures.data).toEqual([]);
        expect(architectures.loaded).toBe(false);
        expect(architectures.polling).toBe(false);
        expect(architectures.nextPromise).toBeNull();
    });

    it("_data.hwe_kernels has correct data", function() {
        var hwe_kernels = GeneralManager._data.hwe_kernels;
        expect(hwe_kernels.method).toBe("general.hwe_kernels");
        expect(hwe_kernels.data).toEqual([]);
        expect(hwe_kernels.loaded).toBe(false);
        expect(hwe_kernels.polling).toBe(false);
        expect(hwe_kernels.nextPromise).toBeNull();
    });

    it("_data.osinfo has correct data", function() {
        var osinfo = GeneralManager._data.osinfo;
        expect(osinfo.method).toBe("general.osinfo");
        expect(osinfo.data).toEqual({});
        expect(osinfo.loaded).toBe(false);
        expect(osinfo.polling).toBe(false);
        expect(osinfo.nextPromise).toBeNull();
        expect(angular.isFunction(osinfo.isEmpty)).toBe(true);
        expect(angular.isFunction(osinfo.replaceData)).toBe(true);
    });

    describe("_getInternalData", function() {

        it("raises error for unknown data", function() {
            var name = makeName("name");
            expect(function() {
                GeneralManager._getInternalData(name);
            }).toThrow(new Error("Unknown data: " + name));
        });

        it("returns data object", function() {
            expect(GeneralManager._getInternalData("node_actions")).toBe(
                GeneralManager._data.node_actions);
        });
    });

    describe("getData", function() {

        it("returns data from internal data", function() {
            expect(GeneralManager.getData("node_actions")).toBe(
                GeneralManager._data.node_actions.data);
        });
    });

    describe("isLoaded", function() {

        it("returns false if all false", function() {
            expect(GeneralManager.isLoaded()).toBe(false);
        });

        it("returns false if one false", function() {
            GeneralManager._data.node_actions.loaded = true;
            GeneralManager._data.device_actions.loaded = true;
            GeneralManager._data.architectures.loaded = true;
            GeneralManager._data.hwe_kernels.loaded = true;
            GeneralManager._data.osinfo.loaded = false;
            expect(GeneralManager.isLoaded()).toBe(false);
        });

        it("returns true if all true", function() {
            GeneralManager._data.node_actions.loaded = true;
            GeneralManager._data.device_actions.loaded = true;
            GeneralManager._data.architectures.loaded = true;
            GeneralManager._data.hwe_kernels.loaded = true;
            GeneralManager._data.osinfo.loaded = true;
            expect(GeneralManager.isLoaded()).toBe(true);
        });
    });

    describe("isDataLoaded", function() {

        it("returns loaded from internal data", function() {
            var loaded = {};
            GeneralManager._data.node_actions.loaded = loaded;
            expect(GeneralManager.isDataLoaded("node_actions")).toBe(loaded);
        });
    });

    describe("isPolling", function() {

        it("returns false if all false", function() {
            expect(GeneralManager.isPolling()).toBe(false);
        });

        it("returns true if one true", function() {
            GeneralManager._data.node_actions.polling = true;
            GeneralManager._data.architectures.polling = false;
            GeneralManager._data.hwe_kernels.polling = false;
            GeneralManager._data.osinfo.polling = false;
            expect(GeneralManager.isPolling()).toBe(true);
        });

        it("returns true if all true", function() {
            GeneralManager._data.node_actions.polling = true;
            GeneralManager._data.architectures.polling = true;
            GeneralManager._data.hwe_kernels.polling = true;
            GeneralManager._data.osinfo.polling = true;
            expect(GeneralManager.isPolling()).toBe(true);
        });
    });

    describe("isDataPolling", function() {

        it("returns polling from internal data", function() {
            var polling = {};
            GeneralManager._data.node_actions.polling = polling;
            expect(GeneralManager.isDataPolling("node_actions")).toBe(polling);
        });
    });

    describe("startPolling", function() {

        it("sets polling to true and calls _poll", function() {
            spyOn(GeneralManager, "_poll");
            GeneralManager.startPolling("node_actions");
            expect(GeneralManager._data.node_actions.polling).toBe(true);
            expect(GeneralManager._poll).toHaveBeenCalledWith(
                GeneralManager._data.node_actions);
        });

        it("does nothing if already polling", function() {
            spyOn(GeneralManager, "_poll");
            GeneralManager._data.node_actions.polling = true;
            GeneralManager.startPolling("node_actions");
            expect(GeneralManager._poll).not.toHaveBeenCalled();
        });
    });

    describe("stopPolling", function() {

        it("sets polling to false and cancels promise", function() {
            spyOn($timeout, "cancel");
            var nextPromise = {};
            GeneralManager._data.node_actions.polling = true;
            GeneralManager._data.node_actions.nextPromise = nextPromise;
            GeneralManager.stopPolling("node_actions");
            expect(GeneralManager._data.node_actions.polling).toBe(false);
            expect($timeout.cancel).toHaveBeenCalledWith(nextPromise);
        });
    });

    describe("_loadData", function() {

        it("calls callMethod with method", function() {
            spyOn(RegionConnection, "callMethod").and.returnValue(
                $q.defer().promise);
            GeneralManager._loadData(GeneralManager._data.node_actions);
            expect(RegionConnection.callMethod).toHaveBeenCalledWith(
                GeneralManager._data.node_actions.method);
        });

        it("sets loaded to true", function() {
            var defer = $q.defer();
            spyOn(RegionConnection, "callMethod").and.returnValue(
                defer.promise);
            GeneralManager._loadData(GeneralManager._data.node_actions);
            defer.resolve([]);
            $rootScope.$digest();
            expect(GeneralManager._data.node_actions.loaded).toBe(true);
        });

        it("sets node_actions data without changing reference", function() {
            var defer = $q.defer();
            spyOn(RegionConnection, "callMethod").and.returnValue(
                defer.promise);
            var actionsData = GeneralManager._data.node_actions.data;
            var newData = [makeName("action")];
            GeneralManager._loadData(GeneralManager._data.node_actions);
            defer.resolve(newData);
            $rootScope.$digest();
            expect(GeneralManager._data.node_actions.data).toEqual(newData);
            expect(GeneralManager._data.node_actions.data).toBe(actionsData);
        });

        it("sets osinfo data without changing reference", function() {
            var defer = $q.defer();
            spyOn(RegionConnection, "callMethod").and.returnValue(
                defer.promise);
            var osinfoData = GeneralManager._data.osinfo.data;
            var newData = { data: makeName("action") };
            GeneralManager._loadData(GeneralManager._data.osinfo);
            defer.resolve(newData);
            $rootScope.$digest();
            expect(GeneralManager._data.osinfo.data).toEqual(newData);
            expect(GeneralManager._data.osinfo.data).toBe(osinfoData);
        });

        it("calls raiseError if raiseError is true", function() {
            var defer = $q.defer();
            spyOn(RegionConnection, "callMethod").and.returnValue(
                defer.promise);
            spyOn(ErrorService, "raiseError");
            var error = makeName("error");
            GeneralManager._loadData(GeneralManager._data.node_actions, true);
            defer.reject(error);
            $rootScope.$digest();
            expect(ErrorService.raiseError).toHaveBeenCalledWith(error);
        });

        it("doesnt calls raiseError if raiseError is false", function() {
            var defer = $q.defer();
            spyOn(RegionConnection, "callMethod").and.returnValue(
                defer.promise);
            spyOn(ErrorService, "raiseError");
            var error = makeName("error");
            GeneralManager._loadData(GeneralManager._data.node_actions, false);
            defer.reject(error);
            $rootScope.$digest();
            expect(ErrorService.raiseError).not.toHaveBeenCalled();
        });

        it("doesnt calls raiseError if raiseError is undefined", function() {
            var defer = $q.defer();
            spyOn(RegionConnection, "callMethod").and.returnValue(
                defer.promise);
            spyOn(ErrorService, "raiseError");
            var error = makeName("error");
            GeneralManager._loadData(GeneralManager._data.node_actions);
            defer.reject(error);
            $rootScope.$digest();
            expect(ErrorService.raiseError).not.toHaveBeenCalled();
        });
    });

    describe("_pollAgain", function() {

        it("sets nextPromise on data", function() {
            GeneralManager._pollAgain(GeneralManager._data.node_actions);
            expect(
                GeneralManager._data.node_actions.nextPromise).not.toBeNull();
        });
    });

    describe("_poll", function() {

        it("calls _pollAgain with error timeout if not connected", function() {
            spyOn(RegionConnection, "isConnected").and.returnValue(false);
            spyOn(GeneralManager, "_pollAgain");
            GeneralManager._poll(GeneralManager._data.node_actions);
            expect(GeneralManager._pollAgain).toHaveBeenCalledWith(
                GeneralManager._data.node_actions,
                GeneralManager._pollErrorTimeout);
        });

        it("calls _loadData with raiseError false", function() {
            spyOn(GeneralManager, "_loadData").and.returnValue(
                $q.defer().promise);
            GeneralManager._poll(GeneralManager._data.node_actions);
            expect(GeneralManager._loadData).toHaveBeenCalledWith(
                GeneralManager._data.node_actions, false);
        });

        it("calls _pollAgain with empty timeout for node_actions", function() {
            var defer = $q.defer();
            spyOn(GeneralManager, "_pollAgain");
            spyOn(GeneralManager, "_loadData").and.returnValue(defer.promise);
            GeneralManager._poll(GeneralManager._data.node_actions);
            defer.resolve([]);
            $rootScope.$digest();
            expect(GeneralManager._pollAgain).toHaveBeenCalledWith(
                GeneralManager._data.node_actions,
                GeneralManager._pollEmptyTimeout);
        });

        it("calls _pollAgain with empty timeout for osinfo", function() {
            var defer = $q.defer();
            spyOn(GeneralManager, "_pollAgain");
            spyOn(GeneralManager, "_loadData").and.returnValue(defer.promise);
            GeneralManager._poll(GeneralManager._data.osinfo);
            defer.resolve({});
            $rootScope.$digest();
            expect(GeneralManager._pollAgain).toHaveBeenCalledWith(
                GeneralManager._data.osinfo,
                GeneralManager._pollEmptyTimeout);
        });

        it("calls _pollAgain with timeout for node_actions", function() {
            var defer = $q.defer();
            spyOn(GeneralManager, "_pollAgain");
            spyOn(GeneralManager, "_loadData").and.returnValue(defer.promise);
            var node_actions = [makeName("action")];
            GeneralManager._data.node_actions.data = node_actions;
            GeneralManager._poll(GeneralManager._data.node_actions);
            defer.resolve(node_actions);
            $rootScope.$digest();
            expect(GeneralManager._pollAgain).toHaveBeenCalledWith(
                GeneralManager._data.node_actions,
                GeneralManager._pollTimeout);
        });

        it("calls _pollAgain with error timeout on reject", function() {
            var defer = $q.defer();
            spyOn(GeneralManager, "_pollAgain");
            spyOn(GeneralManager, "_loadData").and.returnValue(defer.promise);
            var error = makeName("error");
            spyOn(console, "log");
            GeneralManager._poll(GeneralManager._data.node_actions);
            defer.reject(error);
            $rootScope.$digest();
            expect(console.log).toHaveBeenCalledWith(error);
            expect(GeneralManager._pollAgain).toHaveBeenCalledWith(
                GeneralManager._data.node_actions,
                GeneralManager._pollErrorTimeout);
        });
    });

    describe("loadItems", function() {

        it("calls _loadData for all data", function() {
            spyOn(GeneralManager, "_loadData").and.returnValue(
                $q.defer().promise);
            GeneralManager.loadItems();
            expect(GeneralManager._loadData.calls.count()).toBe(5);
        });

        it("resolve defer once all resolve", function(done) {
            var defers = [
                $q.defer(),
                $q.defer(),
                $q.defer(),
                $q.defer(),
                $q.defer()
            ];
            var i = 0;
            spyOn(GeneralManager, "_loadData").and.callFake(function() {
                return defers[i++].promise;
            });
            GeneralManager.loadItems().then(function() {
                done();
            });
            angular.forEach(defers, function(defer) {
                defer.resolve();
                $rootScope.$digest();
            });
        });
    });

    describe("enableAutoReload", function() {

        it("does nothing if already enabled", function() {
            spyOn(RegionConnection, "registerHandler");
            GeneralManager._autoReload = true;
            GeneralManager.enableAutoReload();
            expect(RegionConnection.registerHandler).not.toHaveBeenCalled();
        });

        it("adds handler and sets autoReload to true", function() {
            spyOn(RegionConnection, "registerHandler");
            GeneralManager.enableAutoReload();
            expect(RegionConnection.registerHandler).toHaveBeenCalled();
            expect(GeneralManager._autoReload).toBe(true);
        });
    });

    describe("disableAutoReload", function() {

        it("does nothing if already disabled", function() {
            spyOn(RegionConnection, "unregisterHandler");
            GeneralManager._autoReload = false;
            GeneralManager.disableAutoReload();
            expect(RegionConnection.unregisterHandler).not.toHaveBeenCalled();
        });

        it("removes handler and sets autoReload to false", function() {
            spyOn(RegionConnection, "unregisterHandler");
            GeneralManager._autoReload = true;
            GeneralManager.disableAutoReload();
            expect(RegionConnection.unregisterHandler).toHaveBeenCalled();
            expect(GeneralManager._autoReload).toBe(false);
        });
    });
});
