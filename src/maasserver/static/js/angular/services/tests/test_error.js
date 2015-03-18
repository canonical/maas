/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for ErrorService.
 */

describe("ErrorService", function() {

    // Load the MAAS module.
    beforeEach(module("MAAS"));

    // Grab the needed angular pieces.
    var $location;
    beforeEach(inject(function($injector) {
        $location = $injector.get("$location");
    }));

    // Load the ErrorService.
    var ErrorService;
    beforeEach(inject(function($injector) {
        ErrorService = $injector.get("ErrorService");
    }));

    it("initializes _error and _backUrl to null", function() {
        expect(ErrorService._error).toBeNull();
        expect(ErrorService._backUrl).toBeNull();
    });

    describe("raiseError", function() {

        it("sets _error and _backUrl and calls $location.path", function() {
            var error = makeName("error");
            var url = makeName("url");
            spyOn($location, "url").and.returnValue(url);
            spyOn($location, "path");
            ErrorService.raiseError(error);
            expect(ErrorService._error).toBe(error);
            expect(ErrorService._backUrl).toBe(url);
            expect($location.path).toHaveBeenCalledWith("/error");
        });

        it("only sets _error and _backUrl once", function() {
            var errors = [
                makeName("error"),
                makeName("error")
            ];
            var urls = [
                makeName("url"),
                makeName("url")
            ];
            var i = 0;
            spyOn($location, "url").and.callFake(function() {
                return urls[i++];
            });
            spyOn($location, "path");
            ErrorService.raiseError(errors[0]);
            ErrorService.raiseError(errors[1]);
            expect(ErrorService._error).toBe(errors[0]);
            expect(ErrorService._backUrl).toBe(urls[0]);
        });
    });
});
