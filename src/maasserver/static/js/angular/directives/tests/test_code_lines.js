/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for placeholder directive.
 */

describe("maasCodeLines", function() {

// Load the MAAS module.
beforeEach(module("MAAS"));

    // Create a new scope before each test.
    var $scope;

    beforeEach(inject(function($rootScope) {
        $scope = $rootScope.$new();
    }));

    // Return the compiled directive with the items from the scope.
    function compileDirective(maasCodeLines) {
        var directive;
        var html = [
            '<div>',
                '<code maas-code-lines="' + maasCodeLines + '"></code>',
            '</div>'
        ].join('');

        // Compile the directive.
        inject(function($compile) {
            directive = $compile(html)($scope);
        });

        // Perform the digest cycle to finish the compile.
        $scope.$digest();
        return directive.find('code');
    }

    it("spans should have the class line", function() {
        $scope.getText = function() {
            return "codetext";
        };

        var directive = compileDirective("getText()");
        expect(directive.find('span').hasClass("line")).toBe(true);
    });
});
