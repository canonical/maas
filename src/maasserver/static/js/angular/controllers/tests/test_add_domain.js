/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for AddDomainController.
 */

describe("AddDomainController", function() {

    // Load the MAAS module.
    beforeEach(module("MAAS"));

    // Grab the needed angular pieces.
    var $controller, $rootScope, $q;
    beforeEach(inject(function($injector) {
        $controller = $injector.get("$controller");
        $rootScope = $injector.get("$rootScope");
        $q = $injector.get("$q");
    }));

    // Load the required dependencies for the AddDomainController
    // and mock the websocket connection.
    var DomainsManager, ManagerHelperService;
    var ValidationService, RegionConnection, webSocket;
    beforeEach(inject(function($injector) {
        DomainsManager = $injector.get("DomainsManager");
        ManagerHelperService = $injector.get("ManagerHelperService");
        ValidationService = $injector.get("ValidationService");
        RegionConnection = $injector.get("RegionConnection");

        // Mock buildSocket so an actual connection is not made.
        webSocket = new MockWebSocket();
        spyOn(RegionConnection, "buildSocket").and.returnValue(webSocket);
    }));

    // Create the parent scope and the scope for the controller.
    var parentScope, $scope;
    beforeEach(function() {
        parentScope = $rootScope.$new();
        parentScope.addDomainScope = null;
        $scope = parentScope.$new();
    });

    // Makes the AddDomainController
    function makeController() {
        // Start the connection so a valid websocket is created in the
        // RegionConnection.
        RegionConnection.connect("");

        return $controller("AddDomainController", {
            $scope: $scope,
            DomainsManager: DomainsManager,
            ValidationService: ValidationService,
            ManagerHelperService: ManagerHelperService
        });
    }

    it("sets addDomainScope on $scope.$parent", function() {
        var controller = makeController();
        expect(parentScope.addDomainScope).toBe($scope);
    });

    it("sets initial values on $scope", function() {
        var controller = makeController();
        expect($scope.viewable).toBe(false);
        expect($scope.error).toBe(null);
        expect($scope.domain).toEqual({
            name: "",
            authoritative: true
        });
    });

    describe("show", function() {

        it("does nothing if already viewable", function() {
            var controller = makeController();
            $scope.viewable = true;
            var name = makeName("name");
            $scope.domain.name = name;
            $scope.show();
            // The domain name should have stayed the same, showing that
            // the call did nothing.
            expect($scope.domain.name).toBe(name);
        });

        it("clears domain and sets viewable to true", function() {
            var controller = makeController();
            $scope.domain.name = makeName("name");
            $scope.show();
            expect($scope.domain.name).toBe("");
            expect($scope.viewable).toBe(true);
        });
    });

    describe("hide", function() {

        it("sets viewable to false", function() {
            var controller = makeController();
            $scope.viewable = true;
            $scope.hide();
            expect($scope.viewable).toBe(false);
        });

        it("emits event addDomainHidden", function(done) {
            var controller = makeController();
            $scope.viewable = true;
            $scope.$on("addDomainHidden", function() {
                done();
            });
            $scope.hide();
        });
    });

    describe("nameHasError", function() {

        it("returns false if name is empty", function() {
            var controller = makeController();
            expect($scope.nameHasError()).toBe(false);
        });

        it("returns false if valid name", function() {
            var controller = makeController();
            $scope.domain.name = "abc";
            expect($scope.nameHasError()).toBe(false);
        });

        it("returns true if invalid name", function() {
            var controller = makeController();
            $scope.domain.name = "a_bc.local";
            expect($scope.nameHasError()).toBe(true);
        });
    });

    describe("domainHasError", function() {

        it("returns true if name empty", function() {
            var controller = makeController();
            $scope.domain.authoritative = true;
            expect($scope.domainHasError()).toBe(true);
        });

        it("returns true if name invalid", function() {
            var controller = makeController();
            $scope.domain.name = "ab_c.local";
            expect($scope.domainHasError()).toBe(true);
        });
    });

    describe("cancel", function() {

        it("clears error", function() {
            var controller = makeController();
            $scope.error = makeName("error");
            $scope.cancel();
            expect($scope.error).toBeNull();
        });

        it("clears domain", function() {
            var controller = makeController();
            $scope.domain.name = makeName("name");
            $scope.cancel();
            expect($scope.domain.name).toBe("");
        });

        it("calls hide", function() {
            var controller = makeController();
            spyOn($scope, "hide");
            $scope.cancel();
            expect($scope.hide).toHaveBeenCalled();
        });
    });

    describe("save", function() {

        it("doest nothing if domain in error", function() {
            var controller = makeController();
            var error = makeName("error");
            $scope.error = error;
            spyOn($scope, "domainHasError").and.returnValue(true);
            $scope.save();
            // Error would have been cleared if save did anything.
            expect($scope.error).toBe(error);
        });

        it("clears error before calling create", function() {
            var controller = makeController();
            $scope.error = makeName("error");
            spyOn($scope, "domainHasError").and.returnValue(false);
            spyOn(DomainsManager, "create").and.returnValue(
                $q.defer().promise);
            $scope.domain.authoritative = true;
            $scope.save();
            expect($scope.error).toBeNull();
        });

        it("calls create with converted domain", function() {
            var controller = makeController();
            $scope.error = makeName("error");
            spyOn($scope, "domainHasError").and.returnValue(false);
            spyOn(DomainsManager, "create").and.returnValue(
                $q.defer().promise);
            var name = makeName("name");
            var authoritative = true;
            $scope.domain = {
                name: name,
                authoritative: authoritative
            };
            $scope.save();
            expect(DomainsManager.create).toHaveBeenCalledWith({
                name: name,
                authoritative: authoritative
            });
        });

        it("on create resolve domain is cleared", function() {
            var controller = makeController();
            $scope.error = makeName("error");
            spyOn($scope, "domainHasError").and.returnValue(false);
            var defer = $q.defer();
            spyOn(DomainsManager, "create").and.returnValue(defer.promise);
            $scope.domain.name = makeName("name");
            $scope.save();
            defer.resolve();
            $rootScope.$digest();
            expect($scope.domain.name).toBe("");
        });

        it("on create resolve hide is called when addAnother is false",
            function() {
                var controller = makeController();
                $scope.error = makeName("error");
                spyOn($scope, "domainHasError").and.returnValue(false);
                var defer = $q.defer();
                spyOn(DomainsManager, "create").and.returnValue(defer.promise);
                $scope.domain.name = makeName("name");
                spyOn($scope, "hide");
                $scope.save(false);
                defer.resolve();
                $rootScope.$digest();
                expect($scope.hide).toHaveBeenCalled();
            });

        it("on create resolve hide is not called when addAnother is true",
            function() {
                var controller = makeController();
                $scope.error = makeName("error");
                spyOn($scope, "domainHasError").and.returnValue(false);
                var defer = $q.defer();
                spyOn(DomainsManager, "create").and.returnValue(defer.promise);
                $scope.domain.name = makeName("name");
                spyOn($scope, "hide");
                $scope.save(true);
                defer.resolve();
                $rootScope.$digest();
                expect($scope.hide).not.toHaveBeenCalled();
            });

        it("on create reject error is set",
            function() {
                var controller = makeController();
                $scope.error = makeName("error");
                spyOn($scope, "domainHasError").and.returnValue(false);
                var defer = $q.defer();
                spyOn(DomainsManager, "create").and.returnValue(defer.promise);
                $scope.domain.name = makeName("name");
                $scope.save();
                var errorMsg = makeName("error");
                var error = "{'name': ['" + errorMsg + "']}";
                defer.reject(error);
                $rootScope.$digest();
                expect($scope.error).toBe(errorMsg + "  ");
            });
    });

    describe("convertPythonDictToErrorMsg", function() {
        it("converts name error for display",
            function() {
                var controller = makeController();
                var errorMsg = makeName("error");
                var error = "{'name': ['Node " + errorMsg + "']}";
                var expected = "Domain " + errorMsg + "  ";
                expect($scope.convertPythonDictToErrorMsg(
                        error)).toBe(expected);
        });

        it("converts unknown segments by default",
                function() {
                    var controller = makeController();
                    var errorSegment1 = makeName("error");
                    var errorSegment2 = makeName("error");
                    var error = "{'" + errorSegment1 +
                        "': ['" + errorSegment2 + "']}";
                    var expected = errorSegment1 + errorSegment2;
                    expect($scope.convertPythonDictToErrorMsg(
                            error)).toBe(expected);
        });
    });
});
