/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for ErrorController.
 */

describe("ErrorController", function() {

    // Load the MAAS module.
    beforeEach(module("MAAS"));

    // Grab the needed angular pieces.
    var $controller, $rootScope, $location, $scope;
    beforeEach(inject(function($injector) {
        $controller = $injector.get("$controller");
        $rootScope = $injector.get("$rootScope");
        $location = $injector.get("$location");
        $scope = $rootScope.$new();
    }));

    // Load the ErrorService.
    var ErrorService;
    beforeEach(inject(function($injector) {
        ErrorService = $injector.get("ErrorService");
    }));

    // Makes the ErrorController
    function makeController() {
        return $controller("ErrorController", {
            $scope: $scope,
            $rootScope: $rootScope,
            $location: $location,
            ErrorService: ErrorService
        });
    }

    it("sets $rootScope title and page", function() {
        var controller = makeController();
        expect($rootScope.title).toBe("Error");
        expect($rootScope.page).toBe("");
    });

    it("sets error from ErrorService and clears error", function() {
        var error = makeName("error");
        ErrorService._error = error;
        var controller = makeController();
        expect($scope.error).toBe(error);
        expect(ErrorService._error).toBeNull();
    });

    it("sets backUrl from ErrorService and clears backUrl", function() {
        var backUrl = makeName("url");
        ErrorService._backUrl = backUrl;
        var controller = makeController();
        expect($scope.backUrl).toBe(backUrl);
        expect(ErrorService._backUrl).toBeNull();
    });

    it("calls $location.path if missing error", function() {
        spyOn($location, "path");
        var controller = makeController();
        expect($location.path).toHaveBeenCalledWith("/");
    });

    describe("goBack", function() {

        it("calls $location.path with backUrl when set", function() {
            var controller = makeController();
            $scope.backUrl = makeName("url");
            spyOn($location, "path");
            $scope.goBack();
            expect($location.path).toHaveBeenCalledWith($scope.backUrl);
        });

        it("calls $location.path with index path if backUrl not set",
            function() {
                var controller = makeController();
                spyOn($location, "path");
                $scope.goBack();
                expect($location.path).toHaveBeenCalledWith("/");
            });
    });
});
