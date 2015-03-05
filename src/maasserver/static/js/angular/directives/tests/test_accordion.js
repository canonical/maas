/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for accodion directive.
 */

describe("maasAccodion", function() {

    // Load the MAAS module.
    beforeEach(module("MAAS"));

    // Create a new scope before each test. Not used in this test, but
    // required to compile the directive.
    var $scope;
    beforeEach(inject(function($rootScope) {
        $scope = $rootScope.$new();
    }));

    // Return the compiled directive with the items from the scope.
    function compileDirective() {
        var directive;
        var html = [
            '<div>',
                '<div class="maas-accordion">',
                    '<h4 class="maas-accordion-tab active">One</h4>',
                    '<h4 class="maas-accordion-tab">Two</h4>',
                    '<h4 class="maas-accordion-tab">Three</h4>',
                '</div>',
            '</div>'
            ].join('');

        // Compile the directive.
        inject(function($compile) {
            directive = $compile(html)($scope);
        });

        // Perform the digest cycle to finish the compile.
        $scope.$digest();
        return directive.find(".maas-accordion");
    }

    // Compile the directive and get the tabs.
    var directive, tabs;
    beforeEach(function() {
        directive = compileDirective();
        tabs = directive.find('.maas-accordion-tab');
    });

    it("sets a new active removing other actives", function() {
        angular.element(tabs[1]).click();
        expect(angular.element(tabs[0]).hasClass("active")).toBe(false);
        expect(angular.element(tabs[1]).hasClass("active")).toBe(true);
        expect(angular.element(tabs[2]).hasClass("active")).toBe(false);

        angular.element(tabs[2]).click();
        expect(angular.element(tabs[0]).hasClass("active")).toBe(false);
        expect(angular.element(tabs[1]).hasClass("active")).toBe(false);
        expect(angular.element(tabs[2]).hasClass("active")).toBe(true);
    });

    it("leaves current active if clicked", function() {
        angular.element(tabs[0]).click();
        expect(angular.element(tabs[0]).hasClass("active")).toBe(true);
        expect(angular.element(tabs[1]).hasClass("active")).toBe(false);
        expect(angular.element(tabs[2]).hasClass("active")).toBe(false);
    });

    it("removes all click handlers on $destroy", function() {
        directive.scope().$destroy();
        angular.forEach(tabs, function(tab) {
            expect($._data(angular.element(tab)[0], 'events')).toBeUndefined();
        });
    });
});
