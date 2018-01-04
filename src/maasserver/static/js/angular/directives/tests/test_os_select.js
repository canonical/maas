/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for OS select directive.
 */

describe("maasOsSelect", function() {

    // Load the MAAS module.
    beforeEach(module("MAAS"));

    // Make OS choice.
    function makeOS() {
        name = makeName("os");
        return [name, name];
    }

    // Make release choice for os.
    function makeRelease(os) {
        release = makeName("release");
        osRelease = os[0] + "/" + release;
        return [osRelease, release];
    }

    // Make fake os information object.
    function makeOSInfo() {
        var i, j;
        var osystems = [], releases = [];
        for(i = 0; i < 5; i++) {
            os = makeOS();
            osystems.push(os);
            for(j = 0; j < 5; j++) {
                var release = makeRelease(os);
                releases.push(release);
            }
        }
        return {
            osystems: osystems,
            releases: releases,
            default_osystem: osystems[osystems.length - 1][0],
            default_release: releases[releases.length - 1][0].split("/")[1]
        };
    }

    // Return subset of releases for the os.
    function getReleasesForOS(os, releases) {
        var i, available = [];
        for(i = 0; i < releases.length; i++) {
            choice = releases[i];
            if(choice[0].indexOf(os) > -1) {
                available.push(choice);
            }
        }
        return available;
    }

    // Create a new scope before each test.
    var $scope;
    beforeEach(inject(function($rootScope) {
        $scope = $rootScope.$new();
        $scope.osinfo = makeOSInfo();
        $scope.selected = null;
    }));

    // Return the compiled directive with the osinfo from the scope.
    function compileDirective(maasOsSelect, ngModel) {
        var directive;
        var html = '<div><span data-maas-os-select="' + maasOsSelect + '" ' +
            'data-ng-model="' + ngModel + '"></span></div>';

        // Compile the directive.
        inject(function($compile) {
            directive = $compile(html)($scope);
        });

        // Perform the digest cycle to finish the compile.
        $scope.$digest();
        return directive.find("span");
    }

    it("creates os select with ng-options", function() {
        var directive = compileDirective("osinfo", "selected");
        var select = directive.find('select[name="os"]');
        expect(select.attr("data-ng-options")).toBe(
                "os[0] as os[1] for os in maasOsSelect.osystems");
    });

    it("creates os select with ng-model", function() {
        var directive = compileDirective("osinfo", "selected");
        var select = directive.find('select[name="os"]');
        expect(select.attr("data-ng-model")).toBe("ngModel.osystem");
    });

    it("creates os select with ng-change", function() {
        var directive = compileDirective("osinfo", "selected");
        var select = directive.find('select[name="os"]');
        expect(select.attr("data-ng-change")).toBe("selectedOSChanged()");
    });

    it("creates release select with ng-options", function() {
        var directive = compileDirective("osinfo", "selected");
        var select = directive.find('select[name="release"]');
        expect(select.attr("data-ng-options")).toBe(
                "release[0] as release[1] for release in releases");
    });

    it("creates release select with ng-model", function() {
        var directive = compileDirective("osinfo", "selected");
        var select = directive.find('select[name="release"]');
        expect(select.attr("data-ng-model")).toBe("ngModel.release");
    });

    it("adds the $reset function to the model", function() {
        var directive = compileDirective("osinfo", "selected");
        expect(angular.isFunction($scope.selected.$reset)).toBe(true);
    });

    it("model $reset resets the default selection", function() {
        var directive = compileDirective("osinfo", "selected");
        $scope.selected.osystem = makeName("os");
        $scope.selected.release = makeName("release");
        $scope.selected.$reset();
        expect($scope.selected.osystem).toBe($scope.osinfo.default_osystem);
        expect($scope.selected.release).toBe($scope.osinfo.default_osystem +
            "/" + $scope.osinfo.default_release);
    });

    it("default $scope.selected to be initialized with defaults", function() {
        var directive = compileDirective("osinfo", "selected");
        expect($scope.selected.osystem).toBe($scope.osinfo.default_osystem);
        expect($scope.selected.release).toBe($scope.osinfo.default_osystem +
            "/" + $scope.osinfo.default_release);
    });

    it("default $scope.selected to be initialized with weighted ubuntu os",
        function() {
            os = ["ubuntu", "Ubuntu"];
            release = ["ubuntu/trusty", "Ubuntu Trusty 14.04 (LTS)"];
            $scope.osinfo.osystems.push(os);
            $scope.osinfo.releases.push(release);
            $scope.osinfo.default_osystem = makeName("default_os");
            $scope.osinfo.default_release = makeName("default_release");
            var directive = compileDirective("osinfo", "selected");
            expect($scope.selected.osystem).toBe("ubuntu");
            expect($scope.selected.release).toBe("ubuntu/trusty");
        });

    it("default $scope.selected to be initialized with first available",
        function() {
            $scope.osinfo.default_osystem = makeName("default_os");
            $scope.osinfo.default_release = makeName("default_release");
            var directive = compileDirective("osinfo", "selected");
            expect($scope.selected.osystem).toBe($scope.osinfo.osystems[0][0]);
            expect($scope.selected.release).toBe($scope.osinfo.releases[0][0]);
        });

    it("default $scope.selected to be initialized to null when empty osinfo",
        function() {
            $scope.osinfo.osystems = [];
            $scope.osinfo.releases = [];
            $scope.osinfo.default_osystem = makeName("default_os");
            $scope.osinfo.default_release = makeName("default_release");
            var directive = compileDirective("osinfo", "selected");
            expect($scope.selected.osystem).toBeNull();
            expect($scope.selected.release).toBeNull();
        });

    it("default $scope.selected to be untouched", function() {
        var current = {
            osystem: "os",
            release: "release"
        };
        $scope.selected = current;
        var directive = compileDirective("osinfo", "selected");
        expect($scope.selected.osystem).toBe(current.osystem);
        expect($scope.selected.release).toBe(current.release);
    });

    it("initializes only selectable releases", function() {
        $scope.selected = {
            osystem: $scope.osinfo.osystems[0][0],
            release: ""
        };
        var directive = compileDirective("osinfo", "selected");
        expect(directive.isolateScope().releases).toEqual(
            getReleasesForOS(
                $scope.osinfo.osystems[0][0], $scope.osinfo.releases));
    });

    it("updates releases when osinfo changes", function() {
        var directive = compileDirective("osinfo", "selected");
        $scope.osinfo = makeOSInfo();
        $scope.selected = {
            osystem: $scope.osinfo.osystems[0][0],
            release: ""
        };
        $scope.$digest();
        expect(directive.isolateScope().releases).toEqual(
            getReleasesForOS(
                $scope.osinfo.osystems[0][0], $scope.osinfo.releases));
    });

    it("selectedOSChanged updates releases", function() {
        var directive = compileDirective("osinfo", "selected");
        $scope.selected = {
            osystem: $scope.osinfo.osystems[1][0],
            release: ""
        };
        $scope.$digest();
        directive.isolateScope().selectedOSChanged();
        expect(directive.isolateScope().releases).toEqual(
            getReleasesForOS(
                $scope.osinfo.osystems[1][0], $scope.osinfo.releases));
    });

    it("selectedOSChanged sets first release as selected release", function() {
        var directive = compileDirective("osinfo", "selected");
        $scope.selected = {
            osystem: $scope.osinfo.osystems[1][0],
            release: ""
        };
        $scope.$digest();
        directive.isolateScope().selectedOSChanged();
        var releases = getReleasesForOS(
                $scope.osinfo.osystems[1][0], $scope.osinfo.releases);
        expect($scope.selected.release).toEqual(releases[0][0]);
    });

    it("releases match os name", function() {
        var directive = compileDirective("osinfo", "selected");
        $scope.osinfo = {
            osystems: [['ubuntu', 'ubuntu'], ['ubuntu-core', 'ubuntu-core']],
            releases: [
                ['ubuntu/xenial', 'xenial'],
                ['ubuntu-core/16-pc', '16-pc']
            ],
            default_osystem: 'ubuntu',
            default_release: 'xenial'
        };
        $scope.selected = {
            osystem: 'ubuntu',
            release: ""
        };
        $scope.$digest();
        var release = directive.isolateScope().releases[0].map(function(txt) {
          return new String(txt);
        });
        expect(release).toEqual(
            ['ubuntu/xenial', 'xenial']);
    });

});
