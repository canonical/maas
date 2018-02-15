/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for the sticky header.
 */

xdescribe("maasStickyHeader", function() {

    // Load the MAAS module.
    beforeEach(module("MAAS"));

    // Create a new scope before each test.
    var $scope;
    beforeEach(inject(function($rootScope) {
        $scope = $rootScope.$new();
    }));

    // Return the compiled directive with the osinfo from the scope.
    function compileDirective() {
        var directive;
        var html = [
            '<div>',
                '<div class="maas-wrapper">',
                    '<header class="page-header" data-maas-sticky-header>',
                    '</header>',
                '</div>',
            '</div>'].join('');

        // Compile the directive.
        inject(function($compile) {
            directive = $compile(html)($scope);
        });

        // Perform the digest cycle to finish the compile.
        $scope.$digest();
        return directive;
    }

    it("changing header height, changes body padding-top", function(done) {
        var directive = compileDirective();
        var body = directive.find("div.maas-wrapper");
        var header = directive.find("header");
        var height = makeInteger(100, 3000);
        header.height(height);
        setTimeout(function() {
            expect(body.css("padding-top")).toBe(height + 20 + "px");
            done();
        }, 100);
    });

    it("changing header height quickly keeps body padding-top in sync",
        function(done) {
            var directive = compileDirective();
            var body = directive.find("div.maas-wrapper");
            var header = directive.find("header");
            var height = makeInteger(100, 3000);
            header.height(height);

            var checkAndIncrement, count = 0;
            checkAndIncrement = function() {
                expect(body.css("padding-top")).toBe(height + 20 + "px");

                count += 1;
                height += 1;
                header.height(height);
                if(count === 10) {
                    done();
                } else {
                    setTimeout(checkAndIncrement, 10);
                }
            };
            setTimeout(checkAndIncrement, 100);
        });

    it("removes padding-top on $destroy", function(done) {
        var directive = compileDirective();
        var body = directive.find("div.maas-wrapper");
        var header = directive.find("header");
        var height = makeInteger(100, 3000);
        header.height(height);
        setTimeout(function() {
            expect(body.css("padding-top")).toBe(height + 20 + "px");
            $scope.$destroy();
            expect(body.css("padding-top")).toBe('');
            done();
        }, 100);
    });
});
