/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for ManagerHelperService.
 */

describe("ManagerHelperService", function() {

    // Load the MAAS module.
    beforeEach(module("MAAS"));

    // Grab the needed angular pieces.
    var $rootScope, $timeout, $q;
    beforeEach(inject(function($injector) {
        $rootScope = $injector.get("$rootScope");
        $timeout = $injector.get("$timeout");
        $q = $injector.get("$q");
    }));

    // Load the ManagerHelperService.
    var ManagerHelperService, RegionConnection, ErrorService;
    beforeEach(inject(function($injector) {
        ManagerHelperService = $injector.get("ManagerHelperService");
        RegionConnection = $injector.get("RegionConnection");
        ErrorService = $injector.get("ErrorService");
    }));

    // Makes a fake manager.
    function makeManager() {
        var manager = {
            isLoaded: jasmine.createSpy(),
            loadItems: jasmine.createSpy(),
            enableAutoReload: jasmine.createSpy()
        };
        manager.isLoaded.and.returnValue(false);
        manager.loadItems.and.returnValue($q.defer().promise);
        return manager;
    }

    describe("loadManager", function() {

        it("calls RegionConnection.defaultConnect", function() {
            spyOn(RegionConnection, "defaultConnect").and.returnValue(
                $q.defer().promise);
            var manager = makeManager();
            ManagerHelperService.loadManager(manager);
            expect(RegionConnection.defaultConnect).toHaveBeenCalled();
        });

        it("doesn't call loadItems if manager already loaded", function(done) {
            var defer = $q.defer();
            spyOn(RegionConnection, "defaultConnect").and.returnValue(
                defer.promise);
            var manager = makeManager();
            manager.isLoaded.and.returnValue(true);
            ManagerHelperService.loadManager(manager).then(function() {
                expect(manager.loadItems).not.toHaveBeenCalled();
                done();
            });
            defer.resolve();
            $timeout.flush();
        });

        it("calls loadItems if manager not loaded", function(done) {
            var defer = $q.defer();
            spyOn(RegionConnection, "defaultConnect").and.returnValue(
                defer.promise);
            var manager = makeManager();
            var loadItemsDefer = $q.defer();
            manager.loadItems.and.returnValue(loadItemsDefer.promise);
            ManagerHelperService.loadManager(manager).then(function() {
                expect(manager.loadItems).toHaveBeenCalled();
                done();
            });
            defer.resolve();
            $rootScope.$digest();
            loadItemsDefer.resolve();
            $rootScope.$digest();
        });

        it("calls enableAutoReload", function(done) {
            var defer = $q.defer();
            spyOn(RegionConnection, "defaultConnect").and.returnValue(
                defer.promise);
            var manager = makeManager();
            manager.isLoaded.and.returnValue(true);
            ManagerHelperService.loadManager(manager).then(function() {
                expect(manager.enableAutoReload).toHaveBeenCalled();
                done();
            });
            defer.resolve();
            $timeout.flush();
        });
    });

    describe("loadManagers", function() {

        it("calls loadManager for all managers", function(done) {
            var managers = [
                makeManager(),
                makeManager()
            ];
            var defers = [
                $q.defer(),
                $q.defer()
            ];
            var i = 0;
            spyOn(ManagerHelperService, "loadManager").and.callFake(
                function(manager) {
                    expect(manager).toBe(managers[i]);
                    return defers[i++].promise;
                });
            ManagerHelperService.loadManagers(managers).then(
                function(loadedManagers) {
                    expect(loadedManagers).toBe(managers);
                    done();
                });
            defers[0].resolve();
            $rootScope.$digest();
            defers[1].resolve();
            $rootScope.$digest();
        });
    });
});
