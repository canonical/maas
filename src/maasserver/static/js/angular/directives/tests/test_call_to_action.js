/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for Call-To-Action dropdown directive.
 */

describe("maasCta", function() {

    // Load the MAAS module.
    beforeEach(module("MAAS"));

    // Make items for the dropdown.
    function makeItems() {
        var i;
        var items = [];
        for(i = 0; i < 5; i++) {
            items.push({
                title: makeName("option")
            });
        }
        return items;
    }

    // Create a new scope before each test.
    var $scope;
    beforeEach(inject(function($rootScope) {
        $scope = $rootScope.$new();
        $scope.items = makeItems();
        $scope.active = null;
    }));

    // Return the compiled directive with the items from the scope.
    function compileDirective(maas_cta, ng_model, ng_change) {
        var directive;
        var html = '<div data-maas-cta="' + maas_cta + '" ' +
            'data-ng-model="' + ng_model + '" ' +
            'data-ng-change="' + ng_change + '"></div>';

        // Compile the directive.
        inject(function($compile) {
            directive = $compile(html)($scope);
        });

        // Perform the digest cycle to finish the compile.
        $scope.$digest();
        return directive;
    }

    it("default shown is false", function() {
        var directive = compileDirective("items", "active");
        expect(directive.isolateScope().shown).toBe(false);
    });

    it("default secondary is false", function() {
        var directive = compileDirective("items", "active");
        expect(directive.isolateScope().secondary).toBe(false);
    });

    it("sets default title to 'Take action'", function() {
        var directive = compileDirective("items", "active");
        expect(directive.find("a.cta-group__link").text()).toBe("Take action");
    });

    it("click link sets shown to true", function() {
        var directive = compileDirective("items", "active");
        directive.find("a.cta-group__link").click();
        expect(directive.isolateScope().shown).toBe(true);
    });

    it("click link--toggle sets shown to true", function() {
        var directive = compileDirective("items", "active");
        directive.find("a.cta-group__link--toggle").click();
        expect(directive.isolateScope().shown).toBe(true);
    });

    it("dropdown hidden when shown is false", function() {
        var directive = compileDirective("items", "active");
        var dropdown = directive.find("ul.cta-group__dropdown");
        expect(dropdown.hasClass("ng-hide")).toBe(true);
    });

    it("dropdown shown when shown is true", function() {
        var directive = compileDirective("items", "active");
        directive.isolateScope().shown = true;
        $scope.$digest();

        var dropdown = directive.find("ul.cta-group__dropdown");
        expect(dropdown.hasClass("ng-hide")).toBe(false);
    });

    it("dropdown secondary when secondary is true", function() {
        var directive = compileDirective("items", "active");
        directive.isolateScope().secondary = true;
        $scope.$digest();

        expect(directive.hasClass("secondary")).toBe(false);
    });

    it("dropdown list options", function() {
        var directive = compileDirective("items", "active");
        var links = directive.find("li.cta-group__item > a");

        var listItems = [];
        angular.forEach(links, function(ele, i) {
            listItems.push(angular.element(ele).text());
        });

        var expectTitles = [];
        angular.forEach($scope.items, function(item) {
            expectTitles.push(item.title);
        });
        expect(expectTitles).toEqual(listItems);
    });

    it("dropdown select sets shown to false", function() {
        var directive = compileDirective("items", "active");
        var links = directive.find("li.cta-group__item > a");

        // Open the dropdown.
        directive.find("a.cta-group__link--toggle").click();
        expect(directive.isolateScope().shown).toBe(true);

        // Clicking a link should close the dropdown.
        angular.element(links[0]).click();
        expect(directive.isolateScope().shown).toBe(false);
    });

    it("dropdown select sets model", function() {
        var directive = compileDirective("items", "active");
        var links = directive.find("li.cta-group__item > a");

        angular.element(links[0]).click();
        expect(directive.scope().active).toBe($scope.items[0]);
    });

    it("dropdown select sets title", function() {
        var directive = compileDirective("items", "active");
        var links = directive.find("li.cta-group__item > a");

        angular.element(links[0]).click();
        var title = directive.find("a.cta-group__link").text();
        expect(title).toBe($scope.items[0].title);
    });

    it("dropdown select sets secondary", function() {
        var directive = compileDirective("items", "active");
        var links = directive.find("li.cta-group__item > a");

        angular.element(links[0]).click();
        expect(directive.isolateScope().secondary).toBe(true);
    });

    it("clicking body will set shown to false", function() {
        var directive = compileDirective("items", "active");
        var links = directive.find("li.cta-group__item > a");

        // Open the dropdown.
        directive.find("a.cta-group__link--toggle").click();
        expect(directive.isolateScope().shown).toBe(true);

        // Click the body.
        var $document;
        inject(function($injector) {
            $document = $injector.get("$document");
        });
        angular.element($document.find('body')).click();

        expect(directive.isolateScope().shown).toBe(false);
    });
});
