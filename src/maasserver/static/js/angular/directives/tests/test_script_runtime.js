/* Copyright 2017 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for script runtime directive.
 */

describe("maasScriptRunTime", function() {

    // Load the MAAS module.
    beforeEach(module("MAAS"));

    // Create a new scope before each test.
    var $scope, $interval;
    beforeEach(inject(function($rootScope, $injector) {
        $interval = $injector.get('$interval');
        $scope = $rootScope.$new();
        $scope.startTime = null;
        $scope.runTime = null;
        $scope.estimatedRunTime = null;
        $scope.scriptStatus = null;
    }));

    // Return the compiled directive.
    function compileDirective(
        startTime, runTime, estimatedRunTime, scriptStatus) {
        var directive;
        var html = '<span data-maas-script-run-time="script-runtime" ' +
            'data-start-time="' + startTime + '" data-run-time="' +
            runTime + '" data-estimated-run-time="' + estimatedRunTime +
            '" data-script-status="' + scriptStatus + '"></span>';

        // Compile the directive.
        inject(function($compile) {
            directive = $compile(html)($scope);
        });

        // Perform the digest cycle to finish the compile.
        $scope.$digest();
        return directive;
    }

    it('should have span element', function () {
        var startTime = Date.now() / 1000;
        var runTime = '0:00:30';
        var estimatedRunTime = '0:00:35';
        var scriptStatus = 7;
        var directive = compileDirective(
            startTime, runTime, estimatedRunTime, scriptStatus);
        var spanElement = directive.find('span');
        expect(spanElement).toBeDefined();
        expect(spanElement.text()).toEqual('0:00:00 of ~' + estimatedRunTime);
    });

    it('should have applied template', function () {
        var startTime = Date.now() / 1000;
        var runTime = '0:00:30';
        var estimatedRunTime = '0:00:35';
        var scriptStatus = 7;
        var directive = compileDirective(
            startTime, runTime, estimatedRunTime, scriptStatus);
        expect(directive.html()).not.toEqual('');
    });

    it('should counter based on passed time', function () {
        var startTime = (Date.now() / 1000) - 5;  // 5 seconds
        var runTime = '0:00:30';
        var estimatedRunTime = '0:00:35';
        var scriptStatus = 7;
        var directive = compileDirective(
            startTime, runTime, estimatedRunTime, scriptStatus);
        var spanElement = directive.find('span');
        expect(spanElement).toBeDefined();
        expect(spanElement.text()).toEqual('0:00:05 of ~' + estimatedRunTime);
    });

    it('counter updated based on passed time not $interval', function () {
        var startTime = (Date.now() / 1000) - 5;  // 5 seconds
        var runTime = '0:00:30';
        var estimatedRunTime = '0:00:35';
        var scriptStatus = 7;
        var directive = compileDirective(
            startTime, runTime, estimatedRunTime, scriptStatus);
        // Flush should not cause the passed time to change.
        $interval.flush(1000);
        var spanElement = directive.find('span');
        expect(spanElement).toBeDefined();
        expect(spanElement.text()).toEqual('0:00:05 of ~' + estimatedRunTime);
    });
});
