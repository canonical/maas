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

    describe("tryParsingJSON", function() {

        // Note: we're putting a lot of trust in JSON.parse(), so one simple
        // test should be enough.
        it("converts a JSON string into a JSON object", function() {
            var result = ManagerHelperService.tryParsingJSON(
                '{ "a": "b" }');
            expect(result).toEqual({ a: 'b' });
        });

        it("converts a non-JSON string into a string", function() {
            var result = ManagerHelperService.tryParsingJSON(
                'Not a JSON string.');
            expect(result).toEqual("Not a JSON string.");
        });

    });

    describe("getPrintableString", function() {

        it("converts a flat dictionary to a printable string", function() {
            var result = ManagerHelperService.getPrintableString(
                {
                    a: 'bc',
                    d: 1
                }, true);
            expect(result).toEqual("a: bc\nd: 1");
        });

        it("converts a dictionary of lists to a string with labels",
            function() {
            var result = ManagerHelperService.getPrintableString(
                {
                    a: ['b', 'cd']
                }, true);
            expect(result).toEqual("a: b  cd");
        });

        it("converts a dictionary of lists to a string without labels",
            function() {
            var result = ManagerHelperService.getPrintableString(
                {
                    a: ['b', 'c']
                }, false);
            expect(result).toEqual("b  c");
        });

        it("converts multiple key dictionary to multi-line string with labels",
            function() {
            var result = ManagerHelperService.getPrintableString(
                {
                    a: ['b', 'cx'],
                    d: ['e', 'f']
                }, true
            );
            expect(result).toEqual("a: b  cx\nd: e  f");
        });
    });

    describe("parseLikelyValidationError", function() {

        it("returns a flat error for a flat string", function() {
            var result = ManagerHelperService.parseLikelyValidationError(
                "This is an error.");
            expect(result).toEqual("This is an error.");
        });

        it("returns a formatted error for a JSON string without names",
            function() {
            var result = ManagerHelperService.parseLikelyValidationError(
                '{"This": "is an error on JSON."}', false);
            expect(result).toEqual("is an error on JSON.");
        });

        it("returns a formatted error for a JSON string with names",
            function() {
            var result = ManagerHelperService.parseLikelyValidationError(
                '{"This": "is an error on JSON."}', true);
            expect(result).toEqual("This: is an error on JSON.");
        });
    });
});
