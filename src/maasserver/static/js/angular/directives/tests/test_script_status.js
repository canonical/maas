/* Copyright 2017 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for script status icon select directive.
 */

describe("maasScriptStatus", function() {

    // Load the MAAS module.
    beforeEach(module("MAAS"));

    // Create a new scope before each test.
    var $scope;
    beforeEach(inject(function($rootScope) {
        $scope = $rootScope.$new();
        $scope.scriptStatus = null;
        $scope.icon = null;
        $scope.tooltip = null;
    }));

    // Return the compiled directive with the maasScriptStatus from the scope.
    function compileDirective(scriptStatus, tooltip) {
        var directive;
        var html = '<div><span data-maas-script-status="script-status"' +
            'data-script_status="' + scriptStatus +
            '" data-tooltip="' + tooltip + '"></span></div>';

        // Compile the directive.
        inject(function($compile) {
            directive = $compile(html)($scope);
        });

        // Perform the digest cycle to finish the compile.
        $scope.$digest();
        return directive.find("span");
    }

    it("SCRIPT_STATUS.PENDING", function() {
        var tooltip = makeName("tooltip");
        var directive = compileDirective("0", tooltip);
        var select = directive.find("span");
        expect(select.attr("class")).toBe("icon icon--pending");
    });

    it("SCRIPT_STATUS.RUNNING", function() {
        var tooltip = makeName("tooltip");
        var directive = compileDirective("1", tooltip);
        var select = directive.find("span");
        expect(select.attr("class")).toBe("icon icon--running");
    });

    it("SCRIPT_STATUS.INSTALLING", function() {
        var tooltip = makeName("tooltip");
        var directive = compileDirective("7", tooltip);
        var select = directive.find("span");
        expect(select.attr("class")).toBe("icon icon--running");
    });

    it("SCRIPT_STATUS.PASSED", function() {
        var tooltip = makeName("tooltip");
        var directive = compileDirective("2", tooltip);
        var select = directive.find("span");
        expect(select.attr("class")).toBe("icon icon--pass");
    });

    it("SCRIPT_STATUS.FAILED", function() {
        var tooltip = makeName("tooltip");
        var directive = compileDirective("3", tooltip);
        var select = directive.find("span");
        expect(select.attr("class")).toBe("icon icon--status-failed");
    });

    it("SCRIPT_STATUS.ABORTED", function() {
        var tooltip = makeName("tooltip");
        var directive = compileDirective("5", tooltip);
        var select = directive.find("span");
        expect(select.attr("class")).toBe("icon icon--status-failed");
    });

    it("SCRIPT_STATUS.DEGRADED", function() {
        var tooltip = makeName("tooltip");
        var directive = compileDirective("6", tooltip);
        var select = directive.find("span");
        expect(select.attr("class")).toBe("icon icon--status-failed");
    });

    it("SCRIPT_STATUS.FAILED_INSTALLING", function() {
        var tooltip = makeName("tooltip");
        var directive = compileDirective("8", tooltip);
        var select = directive.find("span");
        expect(select.attr("class")).toBe("icon icon--status-failed");
    });

    it("SCRIPT_STATUS.TIMEDOUT", function() {
        var tooltip = makeName("tooltip");
        var directive = compileDirective("4", tooltip);
        var select = directive.find("span");
        expect(select.attr("class")).toBe("icon icon--timed-out");
    });

    it("UNKNOWN", function() {
        var tooltip = makeName("tooltip");
        var directive = compileDirective("99", tooltip);
        var select = directive.find("span");
        expect(select.attr("class")).toBe("icon icon--help");
    });
});
